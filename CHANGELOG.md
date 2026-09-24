# Changelog

Notable changes per release, newest first.  Versions follow
[semantic versioning](https://semver.org): while the major version is `0`, a minor bump may
change the file formats, and this file says how.

The check identifiers, the command names and their options, the json file formats - the
description files and, beside them, the address map, the dumped dictionary, the `--renames`
file and the `ddd-build.json` - the `ddd_generate()` and `ddd_add_component()` signatures and
the names a c template renders from are the tool's public interface, and a release that
changes one of them says here what the migration costs.  Anything else - the layout of the
generated c, the wording of a diagnostic - is not, and the templates a project provides are
its own.  A check identifier is the one entry of that list a release only ever adds to: a
name a project has written into a severity override does not change once it has been
published, as the specification requires ([section 4](SPEC.md#4-consistency-checks)).

## 0.11.0

* **A browser interface, as a preview.**  `ddd gui` serves a browser interface over one
  project's description files on the developer's own computer and opens the browser on it:
  the project opens on a canvas of its modules, an arrow per producing-consuming pair
  coloured by the worst disagreement between its ends, and the component table one tab
  away.  A declaration's unit is no longer changed in the table; selecting a declaration
  opens a panel for its variable - every declaration of it, who produces and who reads it,
  and the unit each states - where one unit is chosen for the variable and applied to every
  declaration at once, with the lines each file will change shown on request, under Show
  changes; a red or orange arrow on the canvas opens the same panel.  A unit a declared type
  fixes is shown with its type and left to the type.  It is the first step of a GUI for
  developers who would rather not edit JSON, and its options are not yet part of the public
  interface.  Installing it needs no Node.js: a release carries the compiled pages, and so do
  the wheel ci builds for every branch it runs on and the development build it publishes to
  TestPyPI of the last commit of every push to `master` and to this repository's pull
  requests, once its checks pass - `0.10.1.dev57` for run 57, the commit it was built from
  named in its metadata.  `--host` can also serve it from a container: published on the
  host's loopback alone, with the token in the address as the only guard beyond it.

  A third tab, Units, is a table of every unit the project states or its vocabulary lists -
  its description, how many variables, types and structure members state it, and its
  findings; selecting one opens its panel beside the table, every place it is stated
  included.  A unit is renamed everywhere at once - every declaration, structure member and
  scalar type stating it, and its vocabulary entry - and renaming onto a unit that exists
  merges the two spellings.  A vocabulary's description is edited from a unit's panel, a unit
  outside the vocabulary is added to it, and a unit nothing states any more is removed from
  it; a project with no units file adopts one, writing every unit already in use into it, so
  that adopting reports nothing it did not report before.  Every change is previewed - which
  files, and the exact lines on request - and written to every file or none, as every change
  here is.

  A variable's panel now carries every key its declarations share rather than the unit alone:
  a row per key - what the variable is made of, what it means, what shape it has and which
  declarations it points at - a column per declaration, and the rows they disagree about
  first.  Selecting a row offers the values already in play, each naming the components
  stating it and marking the producer's, and the field the key takes: one of the eleven
  datatypes, a type, an axis, a measurement or a declared constant the project has, true or
  false, a minimum and a maximum, or the unit picker with the project's vocabulary behind
  it.  A conversion and a list of dimensions are carried from the declaration that states
  them rather than composed here, and `kind` is shown and never settled, since it decides
  which other keys a declaration may carry at all.  What is chosen is applied to every
  declaration at once, with the lines each file will change shown on request, exactly as a
  unit already was.

  A fourth tab, Findings, is a table of every finding of the project, worst first, each leading
  to what it names - the variable's panel, the unit's, the type's, or the component's page - or
  saying plainly when there is nowhere to go, as for a file that did not load.  A producing
  declaration without an identity is given one from there, previewed like every other change.

  Every change the interface writes can be undone while the server runs, one change at a time,
  from a button beside the project's name saying what it would put back - "Undo the unit of
  ValueA", "Undo the vocabulary adopted".  Pressing it shows which files would be put back and,
  on request, the exact lines; pressing again writes them, a file the change created taken away
  with the rest.  The interface holds what each change replaced rather than a way to invert it,
  so a file comes back exactly as its author wrote it; a file changed on disk since is refused
  and named, and its change stays on the list to be undone once the file is put back.  The list
  lives in the running server, is capped at fifty changes and ends when `ddd gui` does, which is
  the one thing it leaves behind: nothing is written into the project for it.

  A fifth tab, Types, is every type the project declares - scalars, structures and the
  external ones a vendor's header defines - with what each fixes, what it is used by, and
  the findings filed on it.  What a scalar type fixes is changed from there, previewed like
  every other change and undone the same way; a type is renamed everywhere it is named, its
  own entry and every declaration and member spelling it, in one all-or-nothing edit, and a
  name that c or the project has already spent is refused before anything is written, in the
  same words the editor refuses it with.  A finding filed on a type's entry now leads to the
  type it is about, and a declaration whose datatype, unit, conversion or limits a type
  fixes says which type, and takes the reader there.

  A component's page can now add a declaration to its interface.  Choosing a variable
  another component already declares adds it with the producer's definition where there is
  one, and the project's existing declaration where there is not, less its `id` and its
  `init`, so the new reader agrees with it by construction.  Choosing a name nothing
  declares instead adds a new object of one of the six kinds, asking for what a loadable
  declaration needs - the kind's required keys, and exactly one of `datatype` or
  `typename`, with the identity `conversion` written in once a `datatype` is chosen; a
  scope of `output` stamps it with a fresh `id`.  A unit, limits or a richer conversion
  are left for the variable's own panel afterwards, where a reader already knows to find
  them.  Removing a declaration is offered from that panel too, first naming what else
  declares it, or that nothing does any longer.  All three are previewed before anything
  is written, and undone the same way as every other change.

  A component's table now gains a Shape column between Type and Unit, a button wherever
  there is a grid to open and plain text or nothing where there is not.  A curve, a map,
  an axis and any declaration shaped in one or two dimensions show their values there as
  a grid, laid against their axes' breakpoints, each edge named with its axis and, where
  the readings are physical, that axis's unit; an object with no axis is laid over plain
  indices instead.  A curve, a map and an axis are offered whatever type they name,
  their shape following from their axes; anything else has to state both its own
  dimensions and its own datatype, so a dimensioned declaration naming a structured
  type is shown and not offered, and so is a shape of more dimensions than two: a
  structure holds no values of its own, and a grid draws rows of cells and nothing
  deeper.  The readings switch between physical values and raw counts with a toggle.
  One cell is changed at a time: type a value, see what it would set and which file
  that lands in, apply it, and put it back with the undo control already there -
  except an object that has no one
  producing declaration, because nothing produces it or because more than one thing
  does, whose grid opens read-only rather than being refused.  A physical value no raw count
  represents is stored as the count nearest it and then shown as what was
  stored - typing `12.004` into a `uint16` at ×0.01 stores `1200`, and the grid then
  reads `12`.  A value outside the object's declared limits - shown beside its kind and
  datatype - is stored rather than refused: `limits-out-of-range` weighs the limits
  against the storage and nothing in the analysis weighs an init against them, so
  refusing here would make the grid stricter than `ddd check` and leave cells a person
  wrote by hand that the interface could not edit.  A value the datatype itself
  cannot hold is refused in the tool's own words instead, and so is what is not wholly a
  number, and nothing is written.  An
  object initialised with text shows a sentence saying so rather than a grid; one stated
  once draws that value in every cell with a note, and one stating nothing draws greyed
  zeros with a note.  A finding filed on an object's `init` now leads to this grid, the
  way every other finding already leads to what it names.

* **The editor's reconcile quick fix is no longer offered for a value that already means what
  it would be set to.**  Taking the producing component's value, or spreading one declaration's
  value to the rest, now writes nothing to a declaration that already states it, however
  differently spelled: a conversion written over four lines and the same conversion written on
  one are one value, as the checks have always counted them.

* **The editor offers no unit to a declaration whose type fixes it.**  A declaration naming a
  declared type takes its `unit`, `conversion` and `limits` from the type, and the loader
  refuses one of them stated beside the `typename`.  A `definition-mismatch` on such a
  declaration was offered the producer's `unit` or `conversion` all the same, or the one
  every other declaration states, and "Apply this unit to N other declarations" from another
  declaration wrote into it too: each fix left a file that no longer loaded.  None of the
  three is offered to a declaration naming a type any longer, and "Apply this unit", or the
  same action for a `conversion` or `limits`, leaves it out of the declarations it counts and
  changes.

* **Renaming a unit from the editor, and quick fixes for an unknown one.**  `F2` on a unit -
  from any place it is stated, or from its entry in a units file - renames it everywhere at
  once, the vocabulary included, and merges the two spellings where the new one is listed
  there already, as the Units tab's rename does; it is refused, naming the file, while a file
  of the project does not load.  An `unknown-unit` finding offers "Add 'RPM' to the
  vocabulary", and, for each spelling close enough to suggest, "Rename 'RPM' to 'rpm'
  everywhere".

* **`unknown-unit` suggests a spelling that only differs in case.**  Its did-you-mean scored
  a candidate as written, so `RPM` for the declared `rpm` shared no character with it and
  suggested nothing - the likeliest near miss going unmentioned.  Spellings are now compared
  lowercased first, so `RPM` suggests `rpm`; the vocabulary itself still tells the two apart,
  and `mV` and `MV` remain two units.  The language server's rename-everywhere quick fix,
  which offers exactly what the finding suggests, gains the same spellings.

* **Tables that keep their point counts in front.**  A project states `"point_counts":
  "leading"` - once, in a project file, and a component may state otherwise for the curves,
  maps and axes it defines - when its firmware stores each table's number of axis points ahead
  of its data, in the table's own type.  The c declares such a table flat, counts first
  (`M[2 + (11) * (8)] = { 8, 11, ... }`), and the a2l describes it with `NO_AXIS_PTS_X` and
  `NO_AXIS_PTS_Y` ahead of `FNC_VALUES` or `AXIS_PTS_X` in a record layout of its own.  Two
  checks come with it: `point-counts-unrepresentable` refuses a table whose type cannot hold
  its counts, and `point-counts-mismatch` warns when a table and its axis disagree; `ddd
  compare` reports a changed convention as `changed-interface`.  The c templates are offered
  each object's `dimensions` and `point_counts`.  The dumped dictionary is format 9, adding
  `point_counts` to every object; a format 8 dictionary reads back unchanged.  The address map
  recipe of the build integration page now runs `nm --extern-only`, so two file-local statics
  sharing a name no longer make the map refuse to load.

## 0.10.0

This release is two things at once.  It finishes what 0.9.0 started - constants that hold any
number, string data, the dumped dictionary written as a file rather than redirected, a
component listed and dumped on its own - and it carries the answer to a review of the whole
tool, which read every page, ran every command and weighed every file DDD writes: the seven
entries that follow are what that review found, area by area.

An entry that costs a project anything ends with **Migration:** what, and read together
those come to five things.  A description is refused in a handful of spellings it used to be
accepted in, each of which broke something further along - the compiler, a calibration tool,
an a2l field - and each named where it is written.  Three edits a delivery comparison used to
pass now say "cannot replace", and each is a change of what a consumer compiles against.  A
`ddd generate` run owns the directory it writes into and takes back what it no longer writes.
The a2l, the dumped dictionary and - for a project whose wildcard includes match names
differing in case - the generated c come out once with a diff nobody wrote: shorter derived
limits, a byte order mark, another component order, and identical bytes ever after.  And a
script reading what DDD prints sees one new exit code, absolute paths where a comparison used
to print the path as typed, and a plugin's own output on stderr.  Nothing else that was valid
stops being valid.

* **The editor answers about the project, and about the document you have open.**  Fifteen
  defects of the language server, found by a review of the whole tool, most of them on the
  most ordinary setup there is - a checkout nobody has built yet.

  *What is checked.*  A project description opened in a tree with no build record was read as
  "a component on its own", so the nine checks that need every component of a project were
  silenced for the whole project - and because opening a file republishes everything it
  covers, opening
  `project.ddd.json` **withdrew** the missing producers and unused outputs from the components
  that were already showing them.  A project file is now checked as the project it is; the
  thinner policy stays for a component read alone.  The containing-project stage applies the
  default severities, which no page said and every page now does.  A component linked into two
  images is drawn once rather than once per image, unless the two disagree about how loudly to
  report it.

  *What ends the session.*  A build record naming a check this version has not got ended the
  server on the first document opened - the client restarts it five times and gives up - and
  is now skipped and announced like a record that cannot be read.  So are a code action whose
  `context` is null, an `initialize` naming a workspace folder without a `uri`, a document
  nested deeper than a position in it can be located (which also ended `ddd id --assign` in a
  traceback; it now reports the file and exits with the findings code), and a
  `Content-Length` spelled the way python reads a number rather than the way the protocol
  writes one - `1_2` was twelve, and the frame ended in the middle of the body.  A request
  arriving before `initialize` or after `shutdown` is refused with the code the protocol
  reserves for it, a second `initialize` with the invalid-request error, and `exit` without
  `shutdown` now ends the run with 1 rather than 0.

  *Where the answer lands.*  Everything published, answered and edited is now spelled the way
  the client spelled the document it opened, and resolved for every file it never opened.  A
  workspace opened through a junction, a `subst` or mapped drive, a symlink or with a
  different case had its findings published against a resource the editor was not showing, and
  its renames applied to a document that was not on screen; through such a spelling the open
  file was also found as its own containing project and reported three missing producers the
  project does produce.  A document under a scheme other than `file:` is refused instead of
  being read as a relative path - `untitled:Untitled-1` used to publish `file-not-found` for a
  phantom file in the workspace.  A note with no place of its own is published at the first
  line of the file its finding is on, where it used to carry an empty uri that a client reads
  as `file:///`.

  *What the editor offers.*  `F2` on an enum name or an enumerator opened a rename box whose
  rename returned an empty edit - and, where a variable of that name existed elsewhere, renamed
  *that* instead; the rename subjects are now matched where they are declared.  A rename and
  the quick fixes are refused, naming the file, while a file of the project did not load, for
  the reason a drifted buffer is already refused: a project is indexed from what loaded, so the
  edit would rewrite every other file and leave that one behind.  Hovering a declared type
  where it is declared, or a `typename` inside a types file, answered nothing at all and now
  describes the type.  A unit or a condition holding a backtick or a pipe - `defined(A) ||
  defined(B)` is an ordinary condition - broke the hover's table; both are now escaped.

  *What the server hears and looks at.*  The extension's file watcher has fed
  `workspace/didChangeWatchedFiles` since it was written and the server had no branch for it,
  so a file rewritten by a build or a branch switch changed nothing on screen until somebody
  saved; the server now checks again on it.  A junction inside a build tree turned one record
  into a record per level of the loop - twenty-two announcements and every finding published
  twenty-two times - and records are now counted resolved.  A record whose severities name a
  plugin's check that nothing registers is reported as `plugin-invalid` on the project file,
  which is what `ddd check` refuses the same `-W` for.  And the log no longer says that every
  file is checked on its own, which denied exactly the findings the next message published.

  *What it costs per save.*  A document no build record claims is checked through the project
  above it, and finding that project means loading every candidate and asking it - an answer
  that was then thrown away, so the project was read a second time to be checked, and twice
  more by the first hover or jump after the save.  The read is now handed on rather than
  dropped: one read of the project per refresh, and one per request that has to look above
  the document, where each of the two cost two.

  **Migration:** none for a description file, a build record or a command.  An editor
  extension other than the shipped one sees three protocol changes: `exit` without `shutdown`
  exits 1, requests outside the session are refused rather than served, and a non-`file:`
  document is refused.  The shipped VS Code extension sends `shutdown` first; its launch test
  no longer pins the lenient exit, and its handshake has a timeout.

* **The generated artefacts.**  Everything a review of the whole tool found between a
  description and the files written from it: four ways the c or the a2l was not what the
  description said, four inputs that passed every check and reached a compiler, and the
  example templates a project copies as its starting point.

  *A description may say `/*`.*  The generated c defused the marker that ends a comment and
  not the one that opens another inside it, so a description, a unit, a member, an enumerator
  or a constant carrying `/*` rendered `/** opens a comment /* inside */` into the definition
  file, the shared header, the types header and the component's own header at once - and
  `-Wcomment`, which `-Wall` turns on, reports `"/*" within comment`, so the warning set this
  repository verifies the generated code with stopped the build on all four.  Both markers are
  now spaced apart: `/*` renders as `/ *`, beside the `*/` that already rendered as `* /`.

  *The a2l says what it is encoded in.*  The file is utf-8, as every artefact is, and said
  so nowhere: ASAP2 1.6.1 has no `ENCODING` keyword - that arrives with 1.7 - and section 1.5
  of the standard tells a reader to detect the encoding from a byte order mark and to read the
  file as ISO-8859-1 where there is none.  A unit as ordinary as `°C` therefore reached a
  calibration tool as `Â°C`, or stopped its parser.  The a2l now opens with a utf-8 byte order
  mark.  It is the one generated file that carries one: the c sources and the dumped
  dictionary stay utf-8 with lf and no mark, because a compiler and a json reader already know
  what they are reading.

  *A derived limit is the number the description implies.*  Limits nobody states are
  derived by running the raw ends of the datatype through the conversion, and the product was
  written out as the binary arithmetic left it: a `uint8` under `{"factor": 0.03}` stated an
  upper limit of `7.6499999999999995` - below `7.65`, the value its own largest raw count
  stands for - and an `sint16` under `0.1` stated `3276.7000000000003`, one step past the raw
  range.  A calibration tool that holds data to the limits it reads was refusing the value the
  description implies, and the engineer reading the a2l saw a number nobody wrote.  Both ends
  are now rounded to twelve significant digits, the width a reading has always been spelled
  at, wherever they are derived: the a2l, the dumped dictionary, the hover in the editor and
  the checks.  A delivery comparison weighs a narrowing with the same relative tolerance
  `limits-out-of-range` already weighed a stated limit with, because rounding alone would
  only move the problem: every dictionary archived before this release carries the unrounded
  end, and a candidate that states the limits its datatype implies was tightening it by
  3e-13 - a `narrowed-limits` warning, and under `--strict` a "cannot replace", on every
  rescaled object of every old baseline.

  *Two names the generated files could not carry.*  An axis whose `input` named a
  structured variable passed every check, because an instance of a structure is of kind
  `measurement` and only its declared type says that it is not one quantity.  The a2l then
  bound the axis - and the `COM_AXIS` of every curve over it - to `Inst`, while the only
  records in the file were `Inst.a` and the other members: the dangling reference the export
  closure exists to prevent, which an ASAP2 checker reports and a calibration tool answers by
  dropping the reference or refusing the module.  It is now `reference-kind`, and the axis is
  dropped as every wrong-kind reference is.  Beside it the backend now writes
  `NO_INPUT_QUANTITY` for any input quantity the dictionary it is rendering does not carry, so
  a dictionary read back from a dump, written by another producer or edited by a hook still
  renders a module that loads.  Separately, `name-collision` weighed a declared constant
  against data objects, enums, enumerators and types but not against the members of a
  structure - and the example templates emit every constant as a `#define` above the
  structures, so a constant `raw` beside a member `raw` wrote `#define raw 4` a few lines
  above `uint16_t raw;` and no compiler accepted the header.  That pair is now compared too,
  reported at the constant with a note at the member.

  *Two initial values and shapes that reached the compiler.*  An `init` of `1e-50` on a
  `float32` is inside the range that datatype states and past the precision it has: nothing
  reported it, and the generated c carried `1e-50F`, which gcc refuses outright - `floating
  constant truncated to zero`, an error under the same warning set - because the value the
  storage would hold is not the value the description states.  A non-zero initial value a
  floating point datatype rounds to zero is now `init-invalid`.  And a declaration's own
  shape states at most 64 dimensions: six hundred of one element each were under every cap
  there was - they multiply out to one - and ended `ddd generate c` in a `RecursionError`
  where a finding was owed, the walks that expand a shape descending once per dimension.  It
  is `schema` at the `dimensions` that state it, and the declaration is dropped, as for
  every other shape past a limit.

  *A template renders a constant as a literal.*  A `ConstantView` offers `.literal` beside
  `.value`: the value as a c literal of the narrowest type that holds it.  The two differ only
  at the ends of the 64 bit range, where there is no literal to write out bare -
  `-9223372036854775808` is a unary minus over a literal too large for any signed type, and
  `18446744073709551615` has no signed type at all, so a compiler reads it as unsigned and
  says so - and the example types header renders `.literal` now.  `.value` is unchanged and
  stays the number, for a template that does its own formatting.

  *The example templates compile what they generate.*  `docker/compile.sh` compiles every
  generated header on its own, the header included twice and nothing before it, which is what
  proves each is self contained; three legitimate projects ended there with `ISO C forbids an
  empty translation unit`.  The example types header included `<stdint.h>` only when a
  datatype of the project asked for it, and every other generated header includes that one and
  nothing else, so a project whose objects are all floating point and one that declares no
  object at all generated a guard around nothing and two empty translation units out of it;
  it is included unconditionally now, and `model.needs_stdint` still answers the question for
  a project's own templates.  The definition file, which an image registering no component
  left holding one comment, carries a typedef that declares a name and no storage.  And the
  example plugin's table of addresses and sizes includes `ddd_globals.h`, without which the
  one artefact that example exists to show was the one the shipped harness could not compile.

  *Four messages that named the wrong thing.*  A template error gave the line of the file the
  failing frame belongs to under the name of the file being rendered, so a macro imported from
  a helper reported a line of the importing template - usually a blank one; the helper is named
  beside the line now.  A `-t` that does not exist, and a `-t` naming one template rather than
  the directory holding it, both read as a directory holding no template.  A path longer than
  the platform accepts came back as `No such file or directory` about a directory that is
  sitting there, and now says that the path itself was refused and how long it is.  And the
  a2l transliterates `²` and `³`, without which `m/s²` and `m/s` asked for one method name and
  whichever was met second was pushed onto `_2`.

  **Migration:** three descriptions that used to check clean are now errors, and each is a
  line to change.  An axis whose `input` names a structured variable: point it at the plain
  measurement that indexes it, or leave the `input` out, which reads `NO_INPUT_QUANTITY` as it
  always did.  A constant sharing a name with a structure member: rename either.  An `init` a
  `float32` rounds to zero: it was never that value.  A shape of more than 64 dimensions is
  refused, which no description states.  a2l and dictionary files regenerate with the shorter
  derived limits and the a2l with three bytes in front of it, so a diff against an archived
  artefact shows both; no stated limit changes and no check turns into a finding, because
  `limits-out-of-range` weighs a stated limit against the derived range with a relative
  tolerance of 1e-9, which spans the rounding.  A tool that reads the a2l as ASCII or as
  ISO-8859-1 without looking at the first three bytes sees them; every reader that follows the
  standard's own rule, and every one that already read the file as utf-8, is unaffected.
  Nothing that reads a file *back* into DDD is: the a2l is the one artefact DDD never reads,
  and the files it does - a description, a dumped dictionary, a build record - are read with a
  mark tolerated and are still written without one.  Prose carrying neither comment marker
  renders exactly as it did.  Templates a project wrote are untouched: `.literal` is a name
  added beside `.value`, and the changes to the example templates are changes to the copy
  `ddd templates-dir` hands out, not to anything a project already has - a project that took
  that copy and generates for a float-only or object-less image wants the same two edits.
* **The verdict on a delivery.**  Everything a review of the whole tool found in the answer
  to "can this delivery replace the one before it?": three changes it did not see at all, a
  name it did not see reused, a note that cost more than the comparison it annotates, four
  findings that said the wrong thing about an initial value, and an archived dictionary read
  more loosely than the description it was dumped from.

  *An `init` compares as the bytes it stores.*  DDD offers two spellings of one array - a
  scalar fills every element of it, and a string's text is the character codes it stands for -
  and the comparison read the spelling.  Respelling `7` on a `uint8[4]` as `[7, 7, 7, 7]`, or
  a list of character codes as the text it spells, was a `changed-storage` warning and, under
  the `--strict` gate the comparison page recommends, a delivery that "cannot replace" its
  predecessor over generated code that is byte for byte the same file.  The two spellings now
  reduce to one before they meet; the dumped dictionary is untouched and still carries the
  init as the description wrote it, so an archive says what was stated.

  *The layout a released structure fixed for its consumers.*  Swapping two members of a
  structure moves every address after the first of them and narrowing a bitfield changes the
  value every reader takes out of the word - and every member of the edited type compared
  identical to the byte, so the comparison reported nothing at all and the delivery that had
  moved every offset of every variable of that type "can replace" its predecessor, `--strict`
  or not.  This is what the `Member` docstring published in two schemas had always promised a
  comparison reports.  A member's `bits` is a compared interface field now, and the order of
  the members is compared once at the structure, where the edit is - one line of one types
  file, however many variables of that type a project declares.

  *A structured variable is compared as the variable it is.*  The dictionary offers the plain
  objects and the members, never the variables, so two things fell between them.  Renaming
  `Sensor_t` to `Sensor2_t` with the members untouched changes what every consumer's header
  declares - `extern Sensor2_t Inlet` - and was silent, while inside one project the same
  disagreement is a `definition-mismatch`.  And the volatility, section, raster, producer and
  condition a member carries only because its variable states them were compared under every
  member: one edit on one declaration was three findings for a three member structure, and
  one per member of every element of an array of them.  The variable is now paired and
  compared like any other object - its `type`, array shape and locality as interface, the
  rest as storage - and each of those is reported once, where it is written.

  *A name freed by a removal and taken by a rename.*  `reused-name` is the failure that
  compiles, links, runs and reads the wrong storage, and it proved the reuse from one end
  only: it caught a rename landing on a name the baseline's own object had left, and not the
  mirror case - an unstamped `A` removed and a stamped `B` renamed onto the spelling it freed
  - which was two warnings and "can replace", although a dataset keyed by `A` now binds to
  what was `B`'s storage.  A rename proves the reuse from either end now, and the finding
  carries a note naming what the baseline called the object standing under the name.

  *The note under a removal, and what it cost.*  A `removed-object` carries a note when
  exactly one addition is identical to it, which is the only help a project that never adopts
  `id` gets.  It asked that of every removal against every addition of the same kind,
  datatype and unit, so the naming-convention sweep `--renames` exists for - a project without
  ids renaming everything at once - was quadratic: 5 000 objects took three minutes and 53 000
  never finished.  Candidates are grouped on everything the note compares now, and a crowd of
  additions alike in all of it is given up on rather than worked through; 5 000 objects compare
  in a tenth of a second.

  *Four findings about an initial value.*  `changed-storage` printed both inits whole, in
  python's spelling: a `uint8[100000]` block with one element changed was one warning of
  600 017 characters, in the text report and in the json, and the reader still had to find the
  element that moved; a list read `(7, 7, 7, 8)` where the description file, `ddd list` and
  the hover all write `[7, 7, 7, 8]`.  Both sides are json now, cut short past a few elements,
  with the first index they part at named beside them.  Beside those, a list nested one level
  too deep was refused as "init is a list but the object is a scalar" of an object declaring
  `"dimensions": [2]` two lines above - the shape checks name the element they are judging now
  - and `2.0` on a `boolean` was refused as "init value 2", a complaint about a whole number
  nobody had written.

  *An archived dictionary is held to what a description is held to.*  A dump's `format` was
  read as whatever coerced to a number, so one stamped `"9"` or `9.0` went past the check that
  refuses a dictionary from a newer DDD - there was nothing there to compare - and was then
  coerced into the very 9 that check exists to refuse, comparing clean and "can replace"; `0`
  and `-3` were accepted the same way.  It is a strict whole number of at least 1 now.  And
  the dump was handed to a json parser with no hook for a key spelled twice, where every
  description file goes through one that refuses it, so a baseline carrying `"name": "P",
  "name": "Q"` read back as a delivery of a project the line above says it is not.  Both go
  through one reader now.

  **Migration:** three deliveries that used to compare clean now report an error, and each of
  the three is a real change of what a consumer compiles against: a structure whose members
  were reordered, a bitfield whose width changed, and a structured variable whose type was
  renamed.  A project that means one of them accepts it the way it accepts any other, with
  `-W changed-interface=warning` on that run.  `reused-name` fires in one arrangement more,
  and relaxes with `-W reused-name=warning` as before.  In the other direction a comparison
  reports less: a respelled `init` is no longer a change, and an edit to a structured
  variable is one finding instead of one per member, so a script counting findings sees fewer
  of them.  A dumped dictionary is unchanged and still format 8 - nothing DDD writes carries a
  `format` that is not a number, or a key twice - but a file edited by hand into either is now
  refused where it used to be read.  The `--renames` file is unchanged; the specification
  spelled a member's id `<id>` followed by `.` and the member path, where the tool has always
  written the access path, `abcdefghjkmn[0].a` with no `.` before the index, so a migration
  script written from that sentence matched nothing and now has the spelling to key on.

* **The command line, and what a plugin may reach from it.**  What a review of the whole tool
  found at the boundary between the commands, the plugins they run, the paths they are given
  and the streams they write to.

  *A plugin prints on stderr.*  A hook, and the backend a `backend` hook returns, now runs
  with standard output bound to standard error - the arrangement `ddd lsp` has always made
  before a plugin could reach the protocol wire.  Standard output is a document on the command
  line too: a `print` left in a check hook wrote its line in front of the `--format json`
  report of `check`, `generate` and `list`, so a job's `json.loads` failed on it, and in front
  of the dictionary of `ddd dump > baseline.json`, so what a build archived was not json; a
  plugin's backend did the same to `generate --format json`, and both wrote onto the stdout
  `dump -o` promises empty.  What a plugin prints is redirected rather than swallowed: it is
  read on stderr, beside everything else DDD says about a run.

  *An output file is never a source file.*  `ddd dump -o`, `ddd compare --renames` and
  `ddd generate --dictionary` each name a file on the command line, and the obvious way to
  get one wrong is to complete the name of a description sitting in the same directory:
  `ddd dump components/sensor_hub.ddd.json -o components/sensor_hub.ddd.json` replaced the
  hand-written component with the dictionary, said `wrote ... (updated)` and exited 0.  All
  three now refuse a target that resolves to a file the run read - a description of the
  project, one of its includes, a plugin module, or an archived dictionary being compared -
  as a usage error naming it, before anything is written.

  *A finding says where the file is.*  A `location` is "an absolute, forward-slashed path
  together with the json pointer", and every finding of an analysis was one, because the
  loader resolves what it reads.  The findings the command line places itself were not: a
  comparison's own findings, the ones `check --baseline` adds, the note about an address map
  and everything reported about an archived dictionary carried the path as it was typed, so
  `--format json` handed a dashboard a `location.path` of `work/p.ddd.json` that nobody can
  resolve without knowing the working directory of the run - beside absolute paths in the
  same document.  In text they also sorted apart: within one severity the findings sort by
  path, so a relative one landed after every absolute one instead of beside the findings of
  the file it is about, which is not what the comparison page says.  All of them are built
  from the resolved path now.

  *An option is spelled in full.*  `argparse` accepts any unambiguous prefix of a long option
  unless it is told not to, so `ddd check p.ddd.json --stand` and `ddd generate all ... --dict
  d.json` worked - and would break the day a second option starts with those letters, with
  "ambiguous option" as the whole of the explanation.  Every command and every artefact now
  takes its options spelled out.

  *Ctrl-C, and what a plugin cannot be blamed for.*  A hook that raised a `BaseException`
  which is neither `Exception` nor `SystemExit` - `asyncio.CancelledError`, or one a plugin
  declared itself - escaped as a traceback under the findings exit code; it is the plugin's
  failure like any other, named as one.  A `KeyboardInterrupt` inside a hook is not: it still
  stops the run, and the run now ends with `ddd: interrupted` and **exit code 130**, the code
  a shell reports for a command killed by `SIGINT`, instead of thirty lines of python.  A
  plugin's own model is held to the same rule as its hooks, as it already was for the other
  two.

  *A closed pipe is not an error.*  `ddd schema component | head -1` ended with
  `ddd: [Errno 32] Broken pipe` and exit 2, which fails a paging script on the tool's side
  under `set -o pipefail`; the run now ends at 0 and in silence.

  *`-o .` names a directory.*  `ddd dump p.ddd.json -o .` and `generate --dictionary .` ended
  with `WindowsPath('.') has an empty name` - python's words about pathlib, printed as the
  whole of what the run had to say about a missing file name.  Both now say which option
  needs a file.

  *Six messages that said too little.*  `ddd id --assign` stopped at the first file it could
  not write, with `[Errno 13] Permission denied: 'ro.ddd.json'` and no total, the files after
  it unstamped - where a file that cannot be *parsed* has always been reported while the
  others are stamped; a file that cannot be written is now reported the same way and the run
  goes on.  `--address-map`, `ddd schema -o` and `ddd build-info -o` handed back the bare
  errno text, naming neither the option nor what the run was doing with the file; they say
  `cannot read the address map '...'` and `cannot write '...'` now, as `compare` and
  `generate` already did.  The verdict line printed two file names, which for two deliveries
  of one project kept in a directory each read `pressure.ddd.json can replace
  pressure.ddd.json`; where the names coincide it now prints the paths as they were typed.  A
  dumped dictionary handed to `check`, `list` or `dump` was refused as a vocabulary file
  stating three kinds at once - "file has 'types' and 'constants' and 'rasters' at the top
  level" - and is now recognised and pointed at `ddd compare`.  And `missing-plugin` for the
  baseline was located at the candidate, which does not record the plugin it is about, and
  said the run "has not loaded" a plugin the run had loaded to analyse that very baseline: it
  sits at the file that records the plugin now and says the plugin is not among the
  candidate's, which is what did not run.  A `-W` naming a check of such a plugin is accepted
  for the same reason, instead of being refused as naming a check nothing registers.

  *A redirected run reads in the order it happened.*  `ddd list p.ddd.json > log 2>&1` put the
  two errors of the run at the top of the file and the table at the bottom: redirected, stdout
  is block buffered and stderr is not, so the table arrived when the process ended.  `list`
  and `dump` now flush before their findings, as `sources` and `artefacts` already did.  The
  table also padded its columns to a count of code points, which is not a count of columns: a
  unit such as `温度` is two code points and four columns wide, so every cell after it on that
  row started two columns right of its header.  It is measured by display width now.

  *Every row of `ddd list --format json` carries a `name`.*  A member of a structured variable
  was published as a row carrying `path` and no `name` at all - `name` being a property of the
  model rather than a field of it - while a plain object carried `name` and no `path`, so a
  script keying the rows on `name` dropped every member of every structure in silence.  Both
  shapes now open with `name`, a member's being its access path.  And the json payloads
  themselves are documented for the first time: `list`, `artefacts`, `checks` and the
  `generated` key of `generate` and `dump -o` are on the CLI page with an example each, and
  their shapes are stated in the specification beside the commands.

  *The address map is read like every other file, and its grammar is the documented one.*
  The map `--address-map` names was read as plain utf-8 where the description files, the
  dumped dictionaries and the build records are all read `utf-8-sig`, so a map a Windows tool
  or Notepad wrote came back as `Unexpected UTF-8 BOM (decode using utf-8-sig)` - python's
  advice to a programmer, for a file nobody writes by hand.  Its addresses were parsed with
  python's `int()`, which took `0x1_0000` as `0x00010000`, `+5` as `5` and the Arabic-Indic
  `١٢` as `12`; a string address is now written in decimal or behind a `0x` prefix and in no
  other way, whatever whitespace surrounds it.  And a symbol the map states twice is refused,
  where the second address used to win in silence, as the description loader already refuses
  a repeated key.  Every complaint about a map spells its path forward-slashed, as the rest
  of the tool does.

  *What a check hook changes is what everything after it sees.*  A hook is handed the
  resolved dictionary itself, and the `extensions` blocks inside its frozen models are
  ordinary dictionaries, so a hook that writes into one has changed what the backends render,
  what `ddd dump` prints and what `ddd compare` reads back.  Nothing said so.  The plugins
  page now does, in both directions: a hook that reports does not assign, and a value a
  plugin computes for its own artefact belongs to that artefact rather than to a block.
  Read-only views were the alternative and were not taken: they would copy every block on
  every run against something no plugin has a reason to do, change the type every plugin
  already written against the api sees, and still leave `object.__setattr__` one line away -
  a guarantee that reads as complete and is not.

  *A `-W` is held to the plugins of the run, and grades this run alone.*  An override naming a
  plugin's check is verified once the project has been read, and the run used to return before
  verifying it whenever the read reported an error: `ddd check p.ddd.json -W layout/x=error`
  over a project with a missing include reported the missing file and never a word about
  `layout/x`, so a typo on the command line surfaced only on the first run that happened to
  load cleanly - the run that no longer needed telling.  The plugins are loaded by the time an
  include goes missing, so the override is now held to them either way.  With `--baseline` the
  plugins of the run include the baseline's own, which were loaded to analyse it, so a `-W`
  naming one of their checks is accepted there as `ddd compare` already accepts it.  And a
  `-W` no longer reaches the baseline's own analysis at all: `-W unused-output=error`, a run
  asking to be told about *its own* unread outputs, promoted a predecessor's into an error,
  carried it over as `in the baseline:` and refused a verdict on a delivery that is fine -
  where `--strict`, which says the same thing in one word, had always left the baseline alone.
  The errors that analysis does produce are carried at the severity it gave them, so the one
  line saying the dictionary the comparison rests on cannot be trusted is not relaxed away by
  this run's policy.  `--standalone` still reaches it: that says how the file was handed over,
  and the baseline was handed over the same way.

  *What the pages had wrong about all of this.*  `ddd compare --plugin` is refused beside a
  project *candidate*, which names its own plugins - not "beside a description", which is what
  section 7 and the CLI page said while 3.11 and the code said the other thing.  The build
  page now says that configuring imports the plugins a project names, so `cmake` runs that
  python before it has built anything, and that the published pre-commit hook needs Python
  3.12 - which a machine with an older `python3` used to learn from pip, in a message naming
  nothing of the project's.  The CLI page no longer says a component "generates on its own":
  `ddd generate` has no `--standalone`, and a component whose inputs nobody produces generates
  under `--force` or under a `-W` it has decided about.  The templates page says that a
  template directory is code, rendered in an unsandboxed environment, which had been stated
  for plugins alone - a template reads as data and is not.  The plugins page's list of what a
  plugin's artefact accepts was missing `--dictionary`.  And two of the tool's own texts had
  fallen behind the pages that quote them as authoritative: `ddd checks` describes
  `init-invalid` as it fires - an enumerator, a shape and a string init included, as the
  specification, the checks page and the README already said - and `ddd sources --help` says
  it lists the plugin modules as well as the descriptions.

  **Migration:** a script spelling an option by a prefix - `--stand`, `--dict` - now fails
  with "unrecognized arguments" and needs the option's full name; nothing else on any command
  line changes.  The text report of the findings is unchanged - every path is still rendered
  against the directory the command ran in.  A reader of `--format json` that resolved
  `location.path` against the working directory gets the same file; one that compared it with
  a path as typed no longer matches, and should compare resolved paths.  The message of a
  finding about a baseline that cannot be read now spells the file out in full, as the same
  message about a description has always done.  A caller that reads exit codes sees one more:
  130, for a run stopped by hand.  A plugin that printed to standard output on purpose - to
  produce a document of its own there - writes a file instead.  A script that matched the
  wording of `missing-plugin`, or the verdict line of two deliveries whose file names
  coincide, matches new text; no check identifier, option or file format changes.  A run that
  relaxed or silenced a check so that its *baseline* would resolve - `-W
  file-extension=warning` over a tree that does not follow the naming convention - now reports
  that check as `in the baseline:` and attempts no comparison: give the run a baseline that
  checks clean on its own, or the archived `ddd dump` of it, which is what a delivery
  comparison has always asked for.  A `-W` that named a check of a plugin the project does not
  name, and went unnoticed because the project happened not to load, is now the usage error it
  always was.  An address map whose writer spelled an address `+5` or `0x1_0000`, or that
  states one symbol twice, is now refused instead of read: both come from a generator, and
  the message names the symbol.  A reader of `ddd list --format json` that keyed its rows on
  `name` now sees the members of every structured variable it used to drop; one that keyed on
  `path` is unaffected, since the key is still there.

* **The build that runs the generator.**  What a review of the whole tool found between DDD
  and the build system driving it: what a run leaves behind in the directory it writes to,
  the project description the cmake module assembles, the keywords it is called with, and the
  address map the linker hands back.

  *`ddd generate` owns its output directory.*  A run wrote what it rendered and removed
  nothing, and what it renders follows from the descriptions - so a component dropped from an
  image's link graph stopped being rendered and **left its header where it was**, on the
  include path of every other component, where a translation unit went on compiling against
  the interface of a component the image no longer links.  The build system could not clean
  it either: a per-component header is named from inside a description file, so it is not
  among the outputs `ddd_generate()` declares, and `ninja -t clean` left it behind with the
  rest.  A run now records the files it wrote, and the artefact each came from, in
  `.ddd-manifest.json` beside them, and the next run removes the recorded files it no longer
  writes, reporting each as `removed`.  Only files DDD itself wrote are ever removed - a file
  the manifest does not name is left alone - and only the artefacts the run produced are
  weighed, so `ddd generate a2l` into the directory a `generate all` filled still regenerates
  the a2l without touching the c sources the image was built from, and so does a
  `--without`.  The record is written in the same all-or-nothing step as the artefacts and
  renamed after them, so a run that fails, or that changes nothing, changes nothing; a
  `--dry-run` says what it would remove and removes nothing.

  *An include that names a file is that file.*  An entry of `includes` holding one of `*`,
  `?` or `[` was a pattern, and the cmake module writes the includes of a collected project as
  literal absolute paths - so a checkout under a directory somebody named `proj [v2]` turned
  every one of them into a character class that matches nothing, and **every build failed**
  with `include-empty` on a project whose files were all there, the message calling a pattern
  what the module had written as a path.  A literal reading is now tried first: an entry
  naming an existing file is that file, whatever is in its name, and an entry naming none is
  expanded as before.

  *An address map may carry what the a2l never addresses.*  Every entry was held to the
  `0 .. 0xFFFFFFFF` an `ECU_ADDRESS` holds, "whether or not DDD knows the symbol" - and the
  recipe the build page documents extracts *every* defined symbol of the image, so on a 64 bit
  host the hundred entries of the c runtime sitting above 4 GB stopped the generation with a
  usage error.  **Every build after the first failed**, on the very host the page tells the
  reader to try the two-run flow on, and the a2l kept `ECU_ADDRESS 0x00000000` for ever.  Only
  the symbols the a2l states an address for are weighed now; the rest are counted among the
  entries the a2l does not carry and named in the note under `address-missing`, where a stale
  or renamed symbol is already read beside the object it belongs to.

  *A keyword given no value is refused, and named.*  `ddd_generate(fw.elf ... ADDRESS_MAP
  ${DDD_MAP})` with `DDD_MAP` unset or empty - the ordinary CMake mistake - reads to
  `cmake_parse_arguments()` exactly like a keyword nobody gave, and neither call looked at
  `KEYWORDS_MISSING_VALUES`.  So the a2l was generated with every `ECU_ADDRESS 0x00000000`,
  no map was seeded and none was a dependency, and the two-run flow the map was configured for
  never happened - in silence, under a `cmake_minimum_required(VERSION 3.31)` project without
  so much as an author warning.  `PROJECT` without a value fell into the collected mode and
  generated out of the link graph instead of out of the file the caller meant.  Both calls now
  stop the configure step, naming the keyword.

  *The module and the tool are one release.*  Nothing compared them, and `ddd cmake-dir`
  invites a project to copy `Ddd.cmake` into its own tree, where it sits beside whichever
  `ddd` the environment has.  Every option the module passes is checked by the tool's
  argument parser when the build runs it, so a module newer than its tool configured cleanly
  and then failed with `generate: error: unrecognized arguments: --dictionary`, which names
  the option and not the mismatch behind it, while a module older than its tool built quietly
  under the option set of a release nobody was running.  Including the module now runs `ddd
  --version` once and refuses the pair, naming both versions and the tool.

  *A description that does not parse is still checked.*  A component whose file was not valid
  json at configure time was read as a file of some other kind and dropped from its own
  `<target>.ddd` target - so `ninja comp.ddd` answered `no work to do` about a file that does
  not parse, and went on answering it, the target being built at configure time, until
  somebody configured again.  Fixing the typo and asking again therefore reported success
  without having checked anything.  Such a file is now checked like a component, which is the
  command that has something to say about it.

  *The build page does not promise an isolation the module does not build.*  It said the
  header generated for a component "is the only one on its include path"; the module puts the
  whole output directory on every component's include path, so `#include "Controller.h"` from
  another component's source compiles.  The page and the README now say what is built - one
  directory, holding the headers of that image and no others - and what the isolation rests
  on.

  *A generation reads the project once rather than once per component.*  Three phases of a
  run walked the whole project again for every component in it, which a large project pays
  for quadratically: the c model asked the dictionary for the objects of each component, a
  scan of every object there is; the a2l looked for the members of each component's
  structured variables by walking every member of the project; and the alignment of a placed
  structure was worked out once per route through the type graph, which doubles per level of
  a structure holding two of the next one.  A build with an address map also built the whole
  a2l model a second time, to read off it which symbols the file carries.  Measured on one
  machine over a synthetic project of a thousand components and fifty-three thousand
  variables: the c model 7.7 s to 0.9 s, rendering the c sources 7.4 s to 1.1 s, the a2l
  model 3.1 s to 0.4 s, rendering the a2l 3.3 s to 0.7 s, and the symbols an address map is
  weighed against 2.8 s to 0.1 s; twenty-two levels of a structure holding two of the next
  went from 0.7 s to nothing.  Nothing about what is generated changes.

  **Migration:** a directory that a `ddd generate` run is pointed at now belongs to that run:
  its own files are untouched, but a file DDD wrote there and no longer writes is deleted at
  the next run, where it used to accumulate.  Two runs generating into one directory - which
  already overwrote each other's artefacts - now also take each other's files back, and want
  a directory each.  A `.ddd-manifest.json` appears beside the artefacts; a build that lists
  its output directory, or archives it as a delivery, sees one more file, and a run into a
  directory that has none removes nothing, so the first run after this upgrade cleans nothing
  up.  `ddd generate --format json` can report a fourth `status`, `removed`, beside `created`,
  `updated` and `unchanged`.  A project whose `includes` holds an entry spelled exactly like
  a file beside it - `a[12].ddd.json`, with a file of that very name - now reads that file
  instead of expanding the class; renaming either one is what keeps the class.  A
  `ddd_generate()` or `ddd_add_component()` call whose keyword expanded to nothing now fails
  the configure step where it used to be ignored: give the keyword a value, or leave it out.
  An address map entry outside `0 .. 0xFFFFFFFF` for a symbol the a2l never names is read
  where it used to be refused; a build that relied on that refusal to catch a wrong map reads
  the `address-missing` note instead, which names every entry the a2l does not carry.  A
  project whose `Ddd.cmake` is a copy of another release's now fails the configure step
  instead of the build step or nothing at all: copy the module of the tool being used, which
  is what `ddd cmake-dir` prints, or point `DDD_EXECUTABLE` at the matching tool.  A target
  registering a description that does not parse now fails its `<target>.ddd` target, with the
  syntax error, where it used to report nothing to do.

* **What a file says, and what it is told it says.**  What a review of the whole tool found
  in the reader of a description: a spelling that meant something its author did not write,
  and three ways a finding about it named the wrong place or was printed more times than
  there were mistakes.

  *A number in a list `init` is written as a number.*  A quoted value nested inside a list
  was read as whatever it looked like: `["1", "2"]` on a `uint8[2]` was accepted and dumped
  as `[1, 2]`, and `["on", "off"]` - words a lax boolean reading turns into truth values -
  reached the generated c as `{ 1U, 0U }`.  The specification, the type's own contract and
  the published schema agree that a quoted number is text and that text does not belong
  inside a list; only the reader disagreed, because the arm that claims a quoted value at the
  top level - a string object's init is its text - has no counterpart one level down, and the
  lax pass below it parsed `"1"`, `" 1 "`, `"1_0"`, `"1e2"`, `"on"`, `"off"`, `"yes"` and
  `"true"` into numbers.  Every arm of a nested init value is now held to the spelling.  What
  is written as a number still reads as one wherever it stands: a whole number on a float
  object, a fraction, a json `true`.

  *One mistake in a nested `init` is one finding.*  A value inside a list failed again at
  every level above it, because a list is not a number either: `[[1, 2], [3, null]]` on a
  `[2][2]` map was three `schema` errors, two of them saying that a list should have been a
  valid integer, and an init nested a hundred deep was a hundred errors.  The count told the
  reader to go looking for problems that were not there, and reading stops the run, so that
  was the whole answer.  A place that holds what failed is now reported only where nothing
  under it is, so the finding sits on the element that is wrong.

  *A finding under a definition names the key it is about.*  A definition is a tagged union,
  and the reader lost the document on the tag: every segment below it was then judged by its
  spelling alone, so a malformed `extensions` block whose plugin is named with punctuation,
  or named after one of the variants - `map`, `axis`, `enum`, `string`, `linear` and `curve`
  are all legal plugin names - was reported at `definition.extensions` with the key gone, and
  the editor underlined the whole block.  Two such blocks in one definition, or in one
  project, were even one finding: the reader fixed the first, ran again and met the second.
  Each now names its key and is counted apart.

  *A table typed one datatype too narrow is one mistake.*  It was one `init-invalid` per
  element: a `uint8[4096]` initialised with 300 printed 4096 identical lines at one pointer -
  half a megabyte of text - carried 4096 diagnostics in `--format json`, and put 4096 of them
  on one range in the editor, where they can only be read one on top of another.  The values
  of one initialiser that are wrong in the same way are now one finding, which names how many
  there are and, where they differ, the first few of them.  A declaration with one wrong
  value reads exactly as it did.

  *A spelling that reaches the compiler is spelled the way the compiler reads it.*  Five
  places where a description was accepted and something downstream then refused it, or
  quietly took it to mean something else.  A variable, type, constant or enumerator named
  `size_t`, `NULL`, `wchar_t`, `ptrdiff_t`, `max_align_t` or `offsetof` passed
  `reserved-identifier` and stopped the build in the generated header, because the
  `<stdint.h>` a types header includes brings `<stddef.h>` in with it; those six and the C23
  `_WIDTH` macros - `UINT8_WIDTH`, `SIZE_WIDTH` and the rest of the family the check already
  promised to cover - are now reserved with the rest.  An `a2l.format` was matched by an
  engine in which `\d` is every decimal digit Unicode has, so `"%٣.٢"` in Arabic-Indic
  digits was written into the a2l as a `FORMAT` string no calibration tool parses, while the
  published schema, where `\d` is `[0-9]`, refused it; both now say `[0-9]`.  A raster name
  was capped at eight *characters* where the a2l field it is sized for is nine *bytes*, so
  eight letters outside ASCII would have overrun it; a name is now printable ASCII.  A
  `condition` ending in `\` spliced the declaration generated below it into the `#if` and
  the compiler stopped there; it is refused where the other ways out of an expression are.
  And a root file whose name begins with `~` was looked for in a home directory: `ddd check
  ~x.ddd.json` reported `C:/Users/x.ddd.json: file-not-found`, a path nobody wrote.
  Expanding a tilde is the shell's business, and the tool no longer does it a second time.

  *`ddd id --assign` writes into the file it was given, or into none of it.*  The new key
  used to be written straight onto the description, so a kill or a full disk between the
  truncation and the write left a hand-authored file truncated or empty, with nothing left
  to put back; the text is now staged in a sibling and renamed onto the file, the way every
  artefact DDD writes already is.  Two more things it did to a file it was pointed at: a
  declaration whose `name` key carried a json escape - `"name"`, which is `name` - was
  skipped without a word, `wrote 0 ids` and exit 0, while `ddd check` went on reporting
  `missing-id` for it; and a file written with bare carriage returns was given one line
  ending of a kind the rest of it does not use, the search for the file's own having looked
  for a line feed only.

  *A reference is spelled the way the thing it names is.*  A `raster` on a definition or a
  component was free text where the declaration it points at is eight printable characters
  without a space, so `"raster": ""` was answered with `unknown-raster: 'V' is measured in
  ''`, sending the reader after a declaration no rasters file could have carried; it is now
  refused where it is written, as a `section` reference always has been, and the
  specification says so about both.  An `extensions` block is keyed by a plugin's name and
  is now spelled like one: a key such as `a.b` or `c[1]` also made a pointer no consumer can
  split - an editor underlined two keys, or an array element - for a block that could never
  have named a plugin.

  *What the file says, where the file says it.*  The mapping form of `enumerators` is
  rewritten into the list the model holds before it is validated, so a mistake inside it was
  reported at `enumerators[0].value`, a key and an index the file has not got; it is now
  reported at the key that holds it.  The same shorthand published neither the bound on a
  value nor the pattern a name is held to, where the list form publishes both, so an editor
  bound to the schema accepted `{"1bad": 0}` and a value past 64 bits and `ddd check` then
  refused them.  Five keys the loader reads as whole numbers - `dimensions`, `size`, an
  enumerator's `value`, `event` and `alignment` - now say in their published description
  that the number is written without a decimal point, which is a rule json schema cannot
  carry: its `integer` admits `4.0`, and the loader does not.

  *Two answers a run should not have.*  A `cycle` written with five thousand digits was
  answered with python's advice about `sys.set_int_max_str_digits`; a count that long is no
  period, and the tool now says so in its own words.  And a description file larger than the
  memory left to the run ended it with a `MemoryError` traceback, where every other way the
  read can fail - missing, unreadable, not utf-8, a directory - is a located finding and the
  rest of the tree is still read.

  *Read once, and answer without reading at all.*  A dumped dictionary handed to `compare` or
  to `check -b` was read and parsed twice per side - once to find out what kind of file it is
  and once to validate it - which on the 45 MB dump of a thousand-object project is about a
  third of a second thrown away per pass.  It is now read once and handed on.  And `ddd
  --version` and `ddd --help` used to build every contract in the package before answering,
  0.40 s for a line of text that looks at none of them; the command line now reaches each
  layer from the handler that needs it, and answers in 0.12 s.  A cmake configure step asks
  for the version once per project and a pre-commit hook once per file.  Reading a dumped
  dictionary also gained what a description already had: a finding inside it names the key it
  is about, so two malformed `extensions` blocks in a dump are two findings rather than one
  about the whole block.

  *A finding sits where the mistake is written, and names the bound it is about.*  An
  enumerator no storage can hold was reported at the `conversion` of a declared type and at
  the whole `definition` of a declaration, so an editor underlined the name, the datatype and
  the limits of a declaration to say something about one enumerator; both now point at the
  conversion.  A bitfield names itself there: two bits of a `uint8` hold 0 to 3, and the
  finding said that 5 does "not fit into uint8" - a claim about a byte the reader knows to be
  false, about a bound written two keys away - where it now says "the 2-bit field of uint8",
  as the member's limits do; a value past both the field and the c `int` every enumerator has
  to be representable in is one finding rather than two.  The note of an `enum-conflict` said
  "first defined as" and pointed at the best documented copy rather than the first one,
  because the better documented spelling replaces the registered one; the spelling is what
  the types header takes, and the place now stays where the enum was first written.  And
  `duplicate-id` is read over every declaration rather than the surviving ones: a copied
  declaration whose type nobody declares hid the copied id along with itself, so the second
  half of one edit's mistake surfaced only once the first half was fixed.

  *What is reported, and when.*  Five places where a run said less than it knew, or said it
  twice.  `incomplete-project` - the trace a declaration leaves when the finding that dropped
  it is silenced - was held back with the checks that need every component of a project, so a
  component checked on its own with any *other* check relaxed lost a variable from `ddd list`
  and `ddd dump` with nothing said at all, which is the one outcome the trace exists to
  prevent.  It is no longer one of that set: a run handed a single file weighs the cause
  instead and stays quiet only where it is itself the reason nobody reported it - a constant
  declared in a file nobody handed over is not an omission, a `-W dimension-value=ignore`
  is.  Two of its other appearances were wrong the other way round.  A declaration whose own
  reference was refused *and reported* earned the trace as well, an info saying that the
  cause is not reported filed beside the error that is the cause; it now says nothing, and
  the object that did go in silence keeps the trace of its own.  And a text `init` on an
  object that is not a string was refused only once the declaration resolved, so silencing
  the unknown constant that sizes it silenced that too - it is a rule about the conversion,
  and is now answered where the conversion is read, whatever the shape turns out to be.  The
  second copy of a `duplicate-declaration` is finally what the checks page says it is,
  ignored for the rest of the run: its unit, its section and its raster were still read, and
  answered with findings the reader can only fix by deleting the copy the first finding
  already names.  And a conflicting second copy of an enum screens the enumerators it adds,
  which take an identifier in the shared types header like any others and used to take one
  unscreened.

  *What the dictionary carries.*  Three claims about it that were not true of it, and one
  answer that depended on the include order.  A structure member naming a type nobody
  declares carried no storage at all - no `datatype`, no `type`, no `external` - which read
  back out of a dump, compared clean against a member that holds a value, and reached a
  `--force` types header as `None ghost;`.  The contract now asks every member to hold
  something, and such a member records the name it was declared as, which is what the
  `unknown-type` finding beside it is about and what the compiler then asks for.  The leaves
  of an instance, and the rows the tool lists from them, are ordered with every `[n]` read as
  the number it is, so an instance of twelve reads `[0], [1], [2]` where it read `[0], [10],
  [11], [1]`.  Under a silenced `local-conflict` or `multiple-producers` the owning
  declaration - whose unit, conversion and `init` reach every consumer's header - was
  whichever one the project happened to include first; it is now the `local` declaration,
  else the first producer by component name, so two files generate the same bytes whatever
  order a third lists them in.  And the ordering walk over the declared structures no longer
  claims that the structures of a `type-cycle` are left out of the dictionary: they are in it
  like any others, and the error is what stops anything being generated from them.

  *One rule, one place.*  Four rules were written out twice between the analysis and the
  comparison - the raw range a bitfield member holds, how a finding spells what an object
  refers to, what an absent condition is called, and what makes a variable local - and one
  pair had already drifted: an absent condition read "no condition" in a project report and
  "none" in a delivery comparison, which put "uses condition no condition" into one sentence.
  Each is written once now, and `condition-mismatch` says `none`, the way every other
  unstated value in a finding does.

  **Migration:** a list `init` holding a quoted number or one of those words is now refused
  with a `schema` finding at the element that holds it, where it used to load, generate and
  dump.  Write the value without the quotes: `["1", "2"]` becomes `[1, 2]`.  A string object
  is untouched - its init is its text, written as one string rather than as a list of them.
  The other three change what a run says about a file it already refused, not what it
  accepts: a file with one of these mistakes now reports fewer findings than before - one
  where there was one per enclosing list, one per block and one per element - so a build that
  counts findings rather than reading them counts differently.  Four more spellings are
  refused where they used to load: a name reserved by `<stddef.h>` or by the `_WIDTH` family,
  an `a2l.format` written in non-ASCII digits, a raster name outside printable ASCII, and a
  `condition` ending in a backslash.  Each of them broke something further along - the
  compiler, the calibration tool, the a2l event field - so the description that carried one
  had to change anyway; the finding now names it.  And a path beginning with `~` is read as
  the name it is: a project that relied on the tool expanding it passes the expansion from
  its shell instead.  Three more spellings join them: a `raster` reference outside what a
  rasters file may declare, an `extensions` key outside `[a-z][a-z0-9_]*`, and - on Windows
  only - a wildcard `includes` entry spelled with a bare drive, `C:*.ddd.json`, which used
  to expand in the directory the process happened to be in and now expands in the project's,
  the way the same spelling without the wildcard always did.  Each of the first two was
  already reported at the end of the run, as `unknown-raster` or `unknown-extension`; the
  finding moves to where it is written and becomes a `schema` error.  The reader refuses
  nothing else it used to accept, and nothing in this entry changes an exit code: what does
  change is the number of findings a run prints.  A component read on its own - `ddd check
  --standalone`, a build's per-component target, a file no build claims in an editor -
  reports one `incomplete-project` info per declaration a relaxed check of the caller's own
  took out of the dictionary, where it used to report none; a run that relaxes none is
  untouched.  A project run reports one fewer wherever the object's own reference was refused
  and reported, and one more wherever a text `init` sits on an object that is not a string and
  never resolved.  An archived dump is read back as it always was, with one exception: one
  carrying a structure member with no `datatype`, no `type` and no `external` - which only a
  dump taken from a project with an `unknown-type` error can hold - is now a `schema` error
  naming the member, where it used to load and compare as though the member held something.
  Re-dump it from the project it came from, with the type declared.

* **The same project generates the same bytes on any machine.**  The one promise of the
  generated output that the tool did not keep, and the last thing a review of the whole tool
  found: the matches of a wildcard `includes` entry
  were sorted as the platform compares two paths, which is case insensitively on Windows and
  by code point on Linux.  A project whose `components/*.ddd.json` matched `Zeta.ddd.json`
  and `alpha.ddd.json` therefore loaded them in one order here and the other order there, and
  since the components keep their include order, the definition file, every component header
  and the a2l `GROUP`s came out differently on the two machines - a diff nobody wrote, in
  files a build compares to decide whether to recompile.  The matches now sort by the code
  point of their POSIX spelling, which is what every name in a generated file already sorts
  by; whether two paths are the *same* file still follows the platform, that being a property
  of the file system rather than of the output.

  **Migration:** a project whose wildcard includes match file names differing in case class -
  an upper case initial beside a lower case one - regenerates its c and its a2l once, with
  the components in a different order; the content of each is unchanged, and nothing about
  what the project *means* depends on the order.  A project whose matched names sort alike in
  both readings, which is every project whose files follow one convention, is untouched.

* **Constants hold any number.**  A constant's `value` was an integer of at least 1, because
  a constant was thought of as a size; but every declared constant is emitted - a `#define`
  through the c templates, a `SYSTEM_CONSTANT` in the a2l - whether or not a shape names it,
  so an offset, a gain or a count of zero was refused for no reason it had.  The value is now
  a whole number of either sign a 64 bit target holds, or a finite number written with a
  fraction, and the spelling decides which: `2` is whole, anything with a point or an
  exponent is not, and a template emits the number in its shortest spelling that reads back
  as the same one - `2.50` as `2.5`, `1e3` as `1000.0` - which keeps the type the author
  picked and not the format.  The size rule moves to where it applies: a shape naming a
  constant that is zero, negative or fractional is the new check `dimension-value`, an error
  reported at the `dimensions` entry or the `size` that names it, and the declaration is
  dropped as for `unknown-constant`.  Unlike that check it needs only the file in front of it,
  so `--standalone` and the language server report it too.  **Migration:** none for a
  description file - every value that was valid still is, and means the same.  A template
  that assumed a constant is a positive integer - formatting it with an unsigned suffix, say
  - should now expect any number.  The dumped dictionary stays format 8, whose other changes
  are listed below; a reader that only knows format 7 refuses a format 8 file as it refuses
  any newer one.

* **Strings.**  A fourth conversion kind, `{"kind": "string"}`, reads a one dimensional
  `uint8` or `sint8` array as text, on a measurement, a value block, a structure member or a
  scalar type; its `init` may be written as a string, printable ASCII shorter than the
  dimension, and the generated c carries it as a string literal.  A calibration string
  reaches the a2l as a `CHARACTERISTIC` of type `ASCII` with a `NUMBER`; a string measurement
  stays the byte array it is, with an `ANNOTATION` saying so, because no version of the
  format has a string measurement.  A string states no unit, limits or display format, and
  the rules are `schema` where they are broken; a wrong string init is `init-invalid`.
  Between deliveries a string `init` compares as the bytes it stores - its text padded with
  zeros to the dimension - so `"Hi"` and `[72, 105, 0, 0]` on a `uint8[4]` are the same
  initial value and neither spelling is reported as a change of the other.
  **Migration:** one spelling changes meaning, see the end of this entry; otherwise none for
  a description file - no existing file carries the kind, and `{}` is the identity it always
  was.  The dumped dictionary is format 8, for the new kind and the
  string `init`; a format 7 dictionary reads back unchanged, and a reader that only knows 7
  refuses a format 8 file as it refuses any newer one.  One spelling changes meaning: a
  quoted number as an `init`, `"12"`, used to be read as the number and is now text, refused
  on anything but a string object as `init-invalid` - spell the number as a number.

* **A delivery comparison spells an enum change out.**  `changed-interface` printed a
  reordered or revalued enumeration as `enum(Mode_t) != enum(Mode_t)`, the name being all
  the description of an enum said; the finding now lists the enumerators on both sides, in
  the spelling `enum-conflict` already uses inside a project.

* **The sdist no longer carries `docs/superpowers/`.**  The design and planning records of
  each feature were shipped beside the documentation, and nothing an sdist is sent to reads
  them.

* **`ddd dump -o FILE` writes the dictionary into a file.**  Archiving the dictionary meant
  redirecting stdout, which leaves the bytes to the shell - the `>` of Windows PowerShell 5.1
  re-encodes them as UTF-16, which `ddd compare` refuses to read back - and empties the
  target before the tool has even started.  `-o` writes the text stdout would have carried
  the way `generate` writes an artefact: utf-8 with lf on every platform, staged, and left
  untouched when its content would not change.  Unlike `generate`, a finding does not hold it
  back - the dictionary is what the project resolved to, errors and all, which is what makes
  it the thing to archive beside a delivery that failed - so only a root that cannot be read
  leaves the file as it was, there being no dictionary then.  A build gates on the exit code,
  which stays what it was, as do the findings on stderr; the json report there names the file
  written, as `generate`'s does.  A target that resolves to a file the run read is refused,
  as it is for `--renames` and `--dictionary`.
  **Migration:** none.

* **`ddd generate --dictionary FILE` writes the dictionary beside the artefacts, and the
  cmake build does.**  Every artefact takes it: the resolved dictionary, the text `ddd dump`
  prints, goes into the same write as the artefacts - all of them or none, a file whose
  content would not change left untouched - and a path an artefact of the run is written to
  is refused.  `ddd_generate()` passes it, so a build now writes `<project name>.dictionary.json`
  into its output directory - the name the a2l takes, which beside `PROJECT` is the one
  written inside that file - which is what a template author reads and what a delivery
  archives for a later `ddd compare`; its path is the image's `DDD_DICTIONARY` property.
  **Migration:** a cmake build gains one file in its output directory; `NO_DICTIONARY` leaves
  it out.

* **A component lists and dumps on its own.**  `ddd list` and `ddd dump` take the
  `--standalone` of `ddd check`, holding back the checks that need every component of a
  project, `-W` still applying on top.  Without it a component carrying a plugin's
  `extensions` block was refused by both with `unknown-extension`, because only a project
  names its plugins.
  **Migration:** none.

* **An image lists from the build.**  `ddd_generate()` adds a `<stem>_ddd_list` target
  printing the table of the image's variables - `ddd list` on the image's project, under the
  build's severities, with its plugins loaded and every producer and consumer resolved.
  **Migration:** none.

## 0.9.0

* **A reference into another component's local object is a use.**  A curve, map or axis of one
  component that named an axis or a measurement another component declared `local` was
  accepted: `local-conflict` compared declarations alone, so the referring object compiled,
  linked and reached the a2l bound to that private object, which is exactly the coupling
  `local` forbids.  Such a reference - an `axis`, an `x_axis`, a `y_axis` or the `input` of an
  axis - is now `local-conflict` too, reported at the reference rather than at a declaration,
  with a note at the local declaration.  The object is not dropped: the mistake is the
  ownership violation, not a missing object, and a component that declares the object as well
  as referring to it gets one finding for each, where it wrote each of them.
  **Migration:** a project whose build turns red on the new finding either declares the object
  `output` in its owning component, so that the reference is a legitimate shared use, or moves
  the referring object into that component.

* **Every integer a description states fits 64 bits.**  A `limits` bound or an enumerator's
  value too large for a float ended the run in an `OverflowError` traceback, because both are
  converted to a float before they are weighed against the range of a datatype; a constant, a
  bare dimension or a section's `alignment` of the same size was accepted in silence, with no
  finding of any kind; and a whole number between `2**64` and the largest float - past every
  datatype, but small enough to survive the conversion - was quietly read as a float, so an
  oversized `limits.max` was answered with `limits-out-of-range` and an oversized `init` as a
  number written fractionally, neither of which is what the author wrote.  Every integer a
  description states - a limit, an initial value, an enumerator's value, a constant, a
  dimension, a section's `alignment` - is now bounded to `-2**63 .. 2**64-1`, what a `sint64`
  and a `uint64` span together, and a wider one is `schema` where it is written, "does not fit
  64 bits", before any arithmetic sees it.
  **Migration:** a limit or an initial value written as a whole number between `2**64` and the
  largest float used to be accepted as a float and answered, if at all, several passes later;
  it is refused now, at the key that states it.  No datatype DDD offers holds such a value, so
  the number itself is the mistake: state one the object's datatype can carry.

* **A json document nested too deeply to read is a finding, not a traceback.**  The reader
  that loads description files already reported `json-syntax` for a document nested deeper
  than python's parser goes; four other paths ran that parser without catching what it raises
  there, so `ddd compare` on a dumped dictionary, the sniff that decides whether a side of a
  comparison is a project, a component or a dictionary, the language server's document reader
  and `ddd id --assign` each ended in a `RecursionError`, at whatever line the stack happened
  to run out on.  Each now
  answers the way an unreadable file already was answered: `json-syntax`, "the json is nested
  too deeply to read", from `ddd compare`; "not readable as json, skipped" from
  `ddd id --assign`; no spans, and the rest of the workspace still served, in the language
  server.  A `ddd compare` side that is not valid utf-8 was a usage error - exit 2, as though
  the command line were wrong - because the sniff let the decoding error out; the file now
  reaches the reader that has a message for it, and is a finding, exit 1, like any other
  unreadable file.

* **An include tree and a structure nest at most 64 levels.**  Five hundred projects each
  including the next ended in a `RecursionError`, two frames a level; a thousand structures
  nesting each other did the same in the walks over the type graph, and five hundred were
  enough when a variable of the outermost sat in a declared section, which walks the chain a
  third time.  Includes now nest at most 64 levels - the root of the run is the first, and a
  component file counts as a level like any other - and a deeper entry is the new check
  `include-depth`, at the entry that crosses the limit; that entry is not followed, the rest
  of the project is read as usual, and the severity is fixed, because the entry is left out
  whatever the finding is called.  It is reported once the whole tree has loaded, and only for
  a file no shallower route read, so which of two includes was written first cannot decide
  whether it is reported.  A structure nests at most 64 levels too - one level is one
  structure, a member naming a scalar or an external type adding none - and a deeper one is
  `schema` at the innermost type that crosses the limit, with every type nesting it unusable
  for the same reason and every declaration naming one of them dropped.  The walks over the
  type graph are iterative now, and each type is walked once a pass rather than once per route
  into it: a diamond - a type that two members of one structure both nest - used to be
  re-entered from every branch, so seventy-two types took more than two minutes to answer and
  now take milliseconds.
  **Migration:** an include tree deeper than 64 levels, or a structure nesting deeper than
  that, was read before if the interpreter's stack happened to hold, and is refused now:
  flatten the tree, or the type, to stay inside the limit.

* **An array, a map and a structure are capped before anything expands them.**  Nothing
  bounded a shape.  A `uint8` array of `[1000000000]` with a scalar `init` passed the check in
  half a second and was then broadcast into one c literal per element: `ddd generate c` had
  written nothing after three minutes.  A two member structure over `[100000, 1000]` was still
  being flattened when it was killed after two and a half minutes, and twenty rungs of types
  each nesting the rung below twice - 1 048 576 leaves - were reported consistent after 39
  seconds.  A 5000 by 5000 map with a scalar `init` wrote 125 MB of `ddd_globals.c` in 19
  seconds.  An array now holds at most 10 000 000 elements, a map at most 10 000 000 over the
  product of its two axes, a structure type at most 100 000 leaves - whether or not anything
  declares a variable of it - and an array of structures at most 100 000 leaves in total, a
  leaf being one value member of one element, which the dictionary, the a2l and the generated
  code each carry an entry of.  Each is `schema` where the shape is written: at `dimensions`,
  at the `size` of an axis, at the whole declaration of a map, which states no shape of its
  own, and at the innermost type that crosses it for a structure.  The declaration is dropped,
  so each of the runs above is one finding in half a second now, with nothing written.
  **Migration:** a project declaring an array, a map or a structure past one of these limits
  used to be analysed and generated, slowly, and is refused now.  A shape that large is
  usually a constant that resolved to the wrong number; one that is meant needs splitting into
  objects a calibration tool can carry.

* **A finding on a key that only looks numeric is reported.**  The findings of one file are
  ordered by their json pointer, so that `interface[10]` follows `interface[2]` rather than
  preceding it, and whether a part of a pointer was an index was decided by `str.isdigit`,
  which is true of a superscript two and of every other unicode digit `int` refuses.  A
  document with such a key has a finding of its own to report - an extra top-level key is
  `schema` - and sorting the findings for display raised instead: the run printed
  `ddd: invalid literal for int() with base 10: '²'` and exited 2, the code for a mistyped
  command line.  A part is an index by its position in the split now, not by what it looks
  like, so the finding is reported at the key it belongs to and the run exits 1.

* **A scalar type is checked where it is declared.**  The `limits` and the enumerators of a
  declared scalar type were checked once per declaration naming it, and each finding was
  rendered at `component.interface[N].definition.limits` - a pointer into a file that does not
  contain a `limits` key, and may not state one, since a declaration naming a type restates
  none of what the type fixes.  A type no declaration named was not checked at all.  Both are
  checked where the type is declared now, once and whether or not anything names it:
  `limits-out-of-range` at its `limits`, the names and values of its enum at its `conversion`;
  a declaration naming a type is still checked for what it adds of its own, its `init`.  The
  enum of a declared type reaches the types header on the same terms as a structure member's:
  a member naming a scalar enum type used to give the a2l a `COMPU_VTAB` for a name the
  generated `ddd_types.h` declared no `typedef enum` for, two artefacts of one run disagreeing
  about what the name means.  An inline enum that disagrees with a declared type's enum of the
  same name is `enum-conflict`, with a note at the type, even when nothing names that type.
  **Migration:** two spellings of one enum name, one on a declared type nobody names and one
  written inline on a declaration, were silent before and are `enum-conflict` now.  The header
  carries the type's spelling, so either make the declaration agree with it or give one of the
  two enums a name of its own.

* **A dangling reference drops the referring object.**  With `unknown-reference` or
  `reference-kind` relaxed, a curve whose axis nobody declares was kept anyway: the c
  backend declared it as a scalar, and the a2l backend wrote no `CHARACTERISTIC` for it
  while its component's `GROUP` still named it.  An axis whose `input` nobody declares was
  kept whole instead: the a2l backend wrote its `AXIS_PTS` with an input quantity naming a
  measurement that does not exist, a file a calibration tool refuses whole.  The referring
  object is now dropped the way an object referring to a dropped declaration already was,
  transitively, and `incomplete-project` reports the absence when the finding is silenced.
  **Migration:** a project relaxing either check, or simply reading the dictionary with
  `ddd list` or `ddd dump`, now gets a smaller, consistent result instead; an unforced
  `ddd generate` left at error severity already wrote nothing and still does.  A baseline
  dumped by an older DDD that still carries such an object compares against the same
  project as a removal - `removed-object` where another component read the object,
  `removed-unused-object` where none did - which is the honest verdict, since the object
  is gone.

* **A failed step after the analysis no longer discards the findings.**  A plugin hook
  that raised, an address map that could not be read, a `--renames` file or an artefact
  that could not be written, a `--plugin` refused beside a description, or a run that
  would write nothing turned the whole run into one usage error line, and the findings
  of the analysis - the ones the reader of a failed run needs - were gone with it.
  They are now printed first, in the requested format, and the usage error follows;
  the exit code is still 2.  The `--renames` failure names the option, and a write
  failure names the file rather than its directory.

* **A dropped declaration is still a declaration.**  A producer naming an unknown type made
  every consumer a `missing-producer`, and a consumer dimensioned by an unknown constant made
  its producer an `unused-output`, each finding pointing at the file the mistake was not in.
  Ownership is now decided over every declaration, dropped ones included; an object whose
  producing declaration was dropped is left out of the dictionary whole, with every
  declaration of it; where one producer resolved and another was dropped, the object is
  built from the one that resolved, whichever file the project lists first; a second
  declaration of a dropped name is a `duplicate-declaration`.
  `incomplete-project`, which fires when the finding explaining a drop is silenced, now
  reaches every declaration the dictionary omits on that account: a variable of a poisoned
  type, the consumers of a dropped producer, a curve over a dropped axis - it used to name
  only the dropped declaration itself, so most of what a silenced check removed went
  unmentioned.  Its message says what is missing: the component whose declaration went, or,
  for an object that went with what it refers to, the reference that pulled it down.

* **The specification catches up with the tool.**  `SPEC.md` now states what 0.8.0 and this
  release do: `ddd check --standalone` and the per-component `<target>.ddd` target, the empty
  address map that raises no `address-missing`, the `COMPU_METHOD` sharing key and the display
  format rule, the closure over an exported axis's input, the A2L file name and record order,
  the `<stem>_ddd_headers` and `<stem>_ddd_globals` targets and `DDD_A2L`, the plugin name
  grammar and its reserved names, the shape of the `--renames` file, the verdict of a
  comparison, the orders of the listings, and a section describing the data dictionary.  It
  defines "instance" and "leaf" and uses "storage" for the key group alone.  No behaviour
  changed.

* **The published schemas refuse a base datatype's name in any case, as the loader does.**  A
  declared type may not be called after the storage it is not, and the loader refused
  `UINT16` as readily as `uint16`; the type name pattern published in the schemas refused
  only the lower-case spelling, so an editor bound to a schema called a file good that
  `ddd check` then rejected.  The pattern now spells every letter of every base datatype as a
  two-letter character class - a json schema pattern carries no flags, and the inline
  `(?i:...)` form is recent enough that an editor's engine may not have it - and the two
  agree, so `UINT16` is underlined where it is typed instead of at the next build.
  **Migration:** nothing the tool itself accepts or refuses has changed, and no description
  file that used to load stops loading.  What changes is what an editor says while the file
  is being written, so a project that keeps a copy of the schemas in its own tree regenerates
  it - `ddd schema all -o <directory>`, or a configure run where `ddd_generate()` writes them
  through `SCHEMA_DIRECTORY`.

* **The sdist carries what its own tests and its documentation build read.**  The archive
  ships the tests and the documentation on purpose - it is what an evaluator is sent - but
  not what either of them reads outside `src/`: from an unpacked archive the documentation
  tests stopped at collection on `.github/workflows/docs.yml`, and the documentation build,
  which takes its logo and its favicon from `assets/logo/`, failed on the two missing images
  under `-W`.  It now carries `assets/`, the editor extension's sources under
  `editors/vscode/`, `.github/workflows/` and `.pre-commit-hooks.yaml`.  A test derives the
  paths the suite and the docs build spell as `ROOT / ...`, and the images `docs/conf.py`
  names, from the sources themselves and holds the include list to them, so the next path
  added that way is answered in the ordinary test run rather than by whoever installs from the
  archive.

* **The language server decodes the uri VS Code sends on Windows.**  A client spells a
  Windows file as `file:///c%3A/...`, drive lower-cased and colon escaped, and the server read
  that as the relative path `/c:/...`: it analysed a file that does not exist and exited on
  the first `didOpen`, trying to publish under a uri it could not form.  The escaped drive
  colon is now restored before the path is decoded, and the server no longer dies on the uri
  a Windows client sends.

* **Edits are computed against the editor's buffer.**  Rename and the quick fixes read
  positions from, and wrote edits for, the file on disk, while the client applies an edit to
  what is on screen; one unsaved line above a declaration was enough to rewrite an unrelated
  line.  The server now keeps the text of every open document (`textDocumentSync.change` is
  `1`, full content), computes positions and edits against it, refuses a rename that an open
  buffer with unsaved changes would leave half applied, naming the file, withholds a quick
  fix it cannot check against every other declaration, and answers a client that takes
  `documentChanges` with the version each edit was computed for.  The analysis still reads
  the disk on open and save, as before.

* **Opening a repository runs its plugins, and the pages now say so.**  A description names
  the plugins the server runs, and the server runs the plugins of every project it finds above
  an opened file.  The VS Code extension declines a workspace that has not been trusted
  (Restricted Mode), and the editor page, the extension's README, the plugins page and the
  specification state the boundary.

* **Renaming a type or a constant from the editor.**  `F2` on the `name` of a declared type
  or on any `typename` spelling it rewrites the declaration and every definition and member
  naming it; on a declared constant or any dimension or axis `size` spelling it, the
  declaration and every dimension.  The refusals are the variables' - a reserved or unusable
  name, one the project already uses - plus a type name spelling a base datatype.

* **Plugins in the build.**  `ddd sources` lists the modules of the plugins a project names
  beside its description files, each by the file it was imported from, so a build re-runs the
  generation when a plugin changes.  `ddd generate all` produces the artefact of every plugin
  the project names that provides one, after the built-in artefacts and in the order the
  project names the plugins; a path two backends claim is refused before anything is written.
  `ddd_generate` takes `PLUGINS <spec>...`, writes them into the project description it
  generates, closes the schemas of `SCHEMA_DIRECTORY` over them - or over the plugins a
  `PROJECT` file names - and depends on the ones that are files; the plugins' artefacts
  arrive beside the built-in ones.

* **The registered components' compile usage travels with `<stem>_ddd_headers`.**  In the
  collected mode, `ddd_generate()` used to apply the interface include directories, compile
  definitions and compile options of every registered component privately to
  `<stem>_ddd_globals`, the object library compiling the definition file.  It now carries them
  as interface usage on `<stem>_ddd_headers`, which `<stem>_ddd_globals` links for them.
  Only the definition file could be compiled before: `ddd_types.h` includes the headers
  declaring the external types, so the include directory alone never sufficed, and a component
  including its own generated header had to find those headers by itself.  Linking
  `<stem>_ddd_headers` is enough now.  The price is that every registered component compiles
  under the union of those compile definitions and compile options, including ones belonging to
  components it does not link; `ddd_types.h` holds the external includes of the whole project
  and every component header includes it, so all of them have to read those headers alike, and
  a project whose components disagree about such a flag has to settle it itself.
  **Migration:** a component that wired up an external type's header by hand, only so that its
  own generated header would compile, can drop that wiring.

* **`NO_A2L` no longer silently drops the plugins' artefacts.**  In the cmake integration it
  selected the `c` artefact instead of `all`, and `all` is the only run that produces a
  plugin's artefact, so a build that asked for no a2l quietly got no plugin output either -
  quietly because a plugin's files are its own and are not declared as outputs, so nothing
  failed until a consumer looked for one.  `ddd generate all` now takes a repeatable
  `--without c|a2l`, which leaves that built-in artefact out of the run and produces
  everything else, and `NO_A2L` passes `--without a2l` rather than narrowing the run.  A run
  that `--without` leaves with nothing to write is refused instead of reporting success.
  **Migration:** none for a build using `NO_A2L`; it now gets the plugin artefacts it asked
  for.  A command line spelling `ddd generate c` to avoid the a2l keeps its meaning, and
  should become `ddd generate all --without a2l` if the project names a plugin.

* **`ddd artefacts` reports what a project can be asked to generate.**  It prints the built-in
  `c` and `a2l` and the name of every plugin the project names that provides one, in text or
  json, and is tolerant the way `ddd sources` is: which artefacts exist follows from the
  plugins a project names, not from whether its interfaces agree.  Given `--plugin` instead of
  a project it answers the same question for a build that has not assembled its project
  description yet, which is the spelling the CMake integration can use at configure time.
  What each artefact *writes* is deliberately not reported: a plugin's file names follow from
  the resolved dictionary, and `ddd generate all --dry-run` already lists them.  A plugin that
  provides no backend is no artefact of its own; it is named in a note rather than passed over,
  since an unexplained absence reads as a plugin that failed to load.  The note says where its
  output does come from: the block such a plugin contributes is part of the vocabulary the
  project's own templates read, and those are rendered by the `c` artefact.

* **`ddd-compile` counts a structured variable as the one symbol it is.**  The symbol check
  behind it read `ddd list --format json`, which reports what can be *described*: the leaves of
  a structured variable, and none at all for an external member.  Those leaves carry no `name`,
  only the path and the instance they belong to, so the check crashed on the first project that
  declared a structure; and a structure whose members are all external had real storage, a real
  symbol and no entry at all, so the check called its definition stray and failed a correct
  project.  It reads `ddd dump --format json` now, whose `objects` and `instances` are exactly
  what the definition file defines - one symbol each, however many leaves a structure has.

* **`--without` subtracts an artefact's options along with the artefact.**  `--without a2l`
  beside an `--address-map` used to load and validate the map, and could abort the run over a
  file it would never read - the two-run flow the option exists for, where the map does not
  exist before the link.  Options belonging to an artefact that was left out are now refused,
  `--byte-order` among them, and the address map is not opened at all.  `--without c` no longer
  demands `-t`: the template directory is asked for once the subtraction is known, so a run
  producing only the a2l and the plugins' artefacts needs no templates it will not read.

* **A run that would write nothing is refused the same way whatever the project.**  The check
  sat after the findings gate, so the identical command line was a usage error on a consistent
  project and a list of that project's findings on any other.  It now runs before the gate.

* **`ddd-compile` finds the headers of external types more reliably.**  It searches for an
  `include` directory from the description upwards, so pointing it at one component of a
  project reaches the project's own; `INCLUDES` now adds to that rather than replacing it; and
  a path containing a space is no longer split into two compiler arguments.

* **`NO_A2L` stops making the address map a dependency of the generation.**  A map named beside
  it was still seeded and still depended on, so a post-link step rewriting it re-rendered every
  c source on every build, for a file the run no longer passes to the generator.

* **The demo declares an external type.**  `SensorHub` declares `DriverState_t`, whose header
  the demo keeps beside its descriptions in `examples/demo/include`, and a `SensorDiagnosis_t`
  structure that carries it next to an ordinary member; `Diagnosis` is a variable of that
  structure.  The generated `ddd_types.h` therefore includes the vendor header, which is what
  the feature looks like in the generated code, and the demo now shows the rest of it too: an
  external member reaches no a2l record, contributes no leaf to `ddd list`, and is storage DDD
  carries without describing.  The shipped cmake example publishes the directory holding that
  header from `sensor_hub` alone, so `event_logger`, which does not link `sensor_hub`, compiles
  the generated headers only because `ddd_generate()` hands the registered components the
  compile usage it collected - the cmake test that builds the example now fails if it stops.
  `ddd-compile` takes an `INCLUDES` variable for the same reason, defaulting to the project's
  own `include` directory when it has one.

* **A plugin module is registered before its body runs.**  A plugin loaded from a `.py` path
  reached `sys.modules` only once its body had finished, so a module that looks itself up
  while it runs - a `@dataclass` under `from __future__ import annotations`, resolving its own
  forward references through `sys.modules` - found nothing there, and the plugin was refused as
  `plugin-invalid` with "failed to import: 'NoneType' object has no attribute '__dict__'", a
  reason naming neither the dataclass nor anything its author could act on.  The module is
  registered before it runs now, the way importlib's own recipe does it, and a body that fails
  is no longer left cached half-run: one that raises, and one that calls `sys.exit` - which
  used to end the process with the code it named - are both `plugin-invalid`, the second
  "exited during import: SystemExit(3)", and the entry is removed again, so the next load in
  the same process - the language server re-analysing after a keystroke - reports that failure
  again instead of "exposes no PLUGIN".

* **A backend's files stay inside the output directory.**  A path a backend handed back was
  compared with the other artefacts' exactly as it was spelled, and then written exactly as it
  said.  A plugin could therefore claim `ddd_globals.h` under a spelling the clash check did
  not recognise - `<output>/sub/../ddd_globals.h`, or the same directory reached through a
  junction - and overwrite the c backend's header in silence; and a path never anchored to the
  output directory at all - a bare `ddd_globals.c`, or one climbing above what `-o` named - was
  written wherever it pointed, beside the process's working directory or a level above the
  directory the reader asked for.  The output directory is resolved once now, before any
  backend runs, so every backend is handed an absolute directory; every path one returns is
  anchored there when it is relative, resolved, and measured against it.  One that lands
  outside is a usage error naming the backend and the path, exit 2, before anything is written,
  and two that resolve to one file are the refusal two artefacts claiming one path always got,
  whichever spelling each of them used.  What a run reports, and the `path` of each entry of
  `--format json`, still reads as the `-o` the reader typed: a relative one stays relative, and
  a junction is named as typed rather than as the directory its files land in.
  **Migration:** a plugin backend returning a path outside `-o`, or a bare relative path that
  used to land beside the process rather than in the output directory, is refused now.  Build
  every path from the `output_dir` the hook is handed, which arrives resolved.

* **A hook that exits the interpreter is the plugin's failure, not the run's verdict.**
  `sys.exit()` in a hook is not an `Exception`, so it escaped the guard every other mistake in
  a hook goes through: `ddd check` ended with the code the hook named, printed none of the
  findings the run had already gathered, and the language server died with it - a hook exiting
  0 answered a run whose findings were already in the bag with a silent success.  A hook that
  exits is now reported exactly as one that raises: `ddd: plugin 'layout' failed in its check
  hook: SystemExit(0)`, exit 2, after the findings; the language server reports it as
  `plugin-invalid` and keeps serving the workspace.  `KeyboardInterrupt` is not caught and
  still interrupts.  The models a plugin declares are held to the same rule, because a
  validator on one of them is plugin code that runs on every `extensions` block DDD reads: a
  `ValueError` or an `AssertionError` from one is the block's finding, as it always was, but
  anything else it raises - and a `sys.exit` - is now `ddd: plugin 'layout' failed validating
  an 'extensions' block: SystemExit(9)`, exit 2, or `plugin-invalid` in the language server,
  instead of a pydantic traceback or a silent exit.  The server says so wherever it meets the
  failure: a project read only to find out whether it contains an opened file is reported at
  that project's description, and the file is still checked for what one file settles, so a
  broken plugin is never the unexplained reason a reader is given the thinner answer.
  **Migration:** a hook calling `sys.exit` used to end the run with its own code, which a build
  script could read as success; it is a usage error now.  A hook reports through the bag and
  returns, and a validator on a plugin's own model raises `ValueError` to refuse a block.

* **What a plugin's backend returns, and what a template raises, are usage errors.**  A
  `backend` hook returning `None` - the shape a hook that reads its settings and forgets to
  build one takes - or returning something that is not a backend crashed later, as
  `AttributeError: 'NoneType' object has no attribute 'name'`, out of a frame naming neither
  the plugin nor the hook; a `generate` returning a string was iterated over its characters
  before failing the same way.  Both are checked where they are returned now: a backend needs a
  `name` that is a string and a `generate` that is callable, and `generate` needs a list whose
  every entry carries a `Path` and a `str`, each failure one line naming the plugin and the
  hook it came from, exit 2.  A template raising what jinja does not wrap as an error of its
  own - `{{ 1 / 0 }}`, a filter handed the wrong type - escaped as a python traceback through a
  library the template's author never imported; it is now the one line every other template
  mistake already was, `ddd: cannot render template 'ddd_globals.c.jinja2', line 2: division by
  zero`.

* **A generation writes every file or none.**  Each file was written straight onto its target
  in turn, so a failure on the third - a target that is a directory, a permission problem, a
  full disk - left the first two replaced with the new render, the third as it was and the rest
  untouched: an output directory holding half of one run and half of another, which may not
  compile together, and nothing saying which file was which.  Every file's status is decided
  first, against the bytes on disk; each file that needs writing is then staged as a sibling
  `<name>.ddd-staging` - a suffix no artefact carries and nobody hand-writes, so a file of the
  reader's own sitting beside a target, `ddd_globals.c.tmp` say, is never staged over and then
  deleted - and only once all of them are staged is each renamed onto its target.  A
  failure removes the temporaries and the targets that run had created, and the `cannot write`
  line names the real target rather than the temporary that could not be moved onto it; a
  target the run had already updated keeps its new content, the bytes it held being gone once
  its own rename went through.  An unchanged file is still left alone and keeps its mtime, so a
  build that watches mtimes still skips what a rerun did not change.
  **Migration:** the rename is `os.replace`, which fails where writing straight onto the file
  used to go through.  On Windows, replacing a file another process holds open raises
  `PermissionError` instead of overwriting it, so a build that regenerates while a compiler or
  an editor holds a generated header open has to close it first; and where a target is one name
  of a hard link, the other name keeps the old bytes rather than seeing the update.

* **`ddd sources` says what it found beside what it listed.**  A missing include was silent in
  text mode: the command printed the listing, exited `0`, and dropped the `file-not-found` its
  loader had already recorded.  A hand-written build asking it for a dependency list therefore
  configured without a word about the mistake and met it later, from whichever DDD command the
  build ran next, rather than from the run that had already found it.  The findings now follow
  the listing on stderr, the way `--format json` has always carried them in its `diagnostics`
  and the way `ddd artefacts` already ended its own listing.  The exit code is untouched: `0`
  whatever the findings, `1` only when the root file cannot be read at all - the contract `ddd
  artefacts` has too, and the exit code table of the command line page names both commands now.
  **Migration:** a script reading `ddd sources` in text form sees findings on stderr that were
  not there before; stdout and the exit code are unchanged.  `--format json` is the parseable
  form, and has carried the same findings all along.

* **`ddd checks` says which checks a single component cannot answer.**  The listing marked a
  check whose severity cannot be relaxed `(fixed)` and said nothing else about any of them, so
  nothing the tool printed distinguished the checks `ddd check --standalone` holds back - the
  ones that need every component of the project - from the ones a single file settles, and a
  build writing a per-component target had to take that list from the documentation.  A check
  that needs the whole project is marked `(project)` now, one that grades a delivery comparison
  rather than a project `(comparison)`, beside the existing `(fixed)`; no check in the registry
  carries two today, and one that did would share a single parenthetical, `(fixed, project)`.
  Every entry of `--format json` carries the same two facts, as `needs_every_component` and
  `comparison`, beside the `overridable` it already had.
  **Migration:** a script parsing the text listing meets the new markers at the end of a line
  that used to end with the check's description, and `--format json` gained two keys.  Read the
  two booleans from the json form, which is the parseable one, rather than matching the markers.

* **Two declarations of one object whose enums disagree are one finding.**  A producer and a
  consumer stating the same enum with its enumerators in a different order, or with one of them
  on a different value, were reported twice: `enum-conflict`, which owns that disagreement and
  names the enumerators of both sides, and `definition-mismatch` as well, because the comparison
  of two declarations folded the enumerator table into the conversion it compares.  The second
  finding could not even say what differed - that comparison explains a conversion by naming it,
  so the message read `conversion: enum(Mode) != enum(Mode)`, the same text on both sides.  An
  enum is compared by its name there now: a reordering or a changed value is `enum-conflict`
  alone, and `-W enum-conflict=ignore` silences it outright where it used to leave
  `definition-mismatch` behind - the check being silenced is the one that owns the mistake -
  while two declarations naming different enums are the `definition-mismatch` they always were,
  `conversion: enum(OtherMode) != enum(Mode)`.  Identity and linear conversions are still
  compared in full, and the delivery comparison, which runs no `enum-conflict` of its own, still
  compares the enumerators itself - and still describes the difference as `enum(Mode) !=
  enum(Mode)` under `changed-interface`, because `EnumConversion.describe` names the enum and
  nothing else; that message is a known follow-up rather than part of this change.

## 0.8.0

* **Checking a component on its own.**  `ddd check --standalone` holds back the checks that
  need every component of a project, derived from the registry the way the language server
  derives them, and an explicit `-W` on the same run still wins.  The CMake module's
  per-component target uses it instead of naming two checks by hand, so a component that
  takes a type, a unit, a section, a constant or a raster from the project's vocabulary checks
  clean alone.  An empty address map is a first run rather than a map with holes: it raises no
  `address-missing`, so a strict two-run flow passes the seeded first build.
* **The published schemas accept what the loader accepts.**  An empty conversion, the
  enumerators of an enum as a `{"NAME": value}` mapping and a unit as a bare spelling were
  read by `ddd check` and refused by the schemas `ddd schema` publishes, so an editor bound to
  them underlined every recommended shorthand; the conversion union is published as `anyOf`
  and the two shorthands beside their object forms.  The example projects carry identities,
  and the tests re-run every command the documentation shows over them.
* **Quick fixes follow the checker on `limits`.**  A declaration that leaves the limits out
  defers to the one that states them, which `definition-mismatch` counts as agreement; the
  editor no longer offers to spread or strip a range in that case, and only two stated ranges
  that differ are offered a fix.

* **Fixes from a whole-project review.**  A section name is spelled with letters, digits,
  `.`, `_` and `$`, since the generated C writes it into a string literal; an enumerator
  value, a raster event and a section alignment are integers rather than quoted numbers, as
  the published schemas already said; a raster `cycle` is matched whole.  Findings at one
  place are listed in the order they were reported, so `reused-name` precedes the removal
  it explains; a plain object's consumers are sorted, as the dictionary documents; a spelled
  dimension has to agree with the numeric one in an archived dictionary.  `ddd id --assign`
  fills an explicit `"id": null` and keeps each line's own ending.  In `--renames`, a member
  of a renamed structured variable is listed under the instance's id followed by its member
  path.  A baseline is analysed without `--strict` and the comparison runs on whatever
  resolved.  The a2l keeps one `COMPU_METHOD` per display format, caps every synthesised
  identifier at 128 characters, leaves out a curve whose axis is unknown rather than writing
  it incomplete, and `a2l-unrepresentable` follows the file's own export closure; a
  structure member's enumerators and limits are held to its storage like a declaration's.
  The language server survives a plugin that raises during a hover, keeps its wire clean of
  whatever a plugin prints, refuses a negative `Content-Length`, matches a symlinked
  document to its build, keeps every workspace folder, and keeps the host of a `file://`
  uri.  The CMake module passes the a2l options only when the a2l is generated.  A plugin
  cannot be named `c`, `a2l` or `all`, and two plugin files whose paths differ only in
  punctuation are two plugins.  The example plugin reports a key claimed twice in an
  archived baseline and honours an object's condition in the header it writes.

* **Plugins.**  A project names python modules under `plugins`, each owning an `extensions`
  block on a definition and on the project that DDD validates against the plugin's own
  pydantic model, carries into the dictionary in resolved form and never interprets.  A plugin
  contributes checks, reported and policed like the built-in ones under identifiers spelled
  `<plugin>/<check>`; comparison rules, run after the built-in comparison; and an artefact,
  selected as `ddd generate <name>`.  Five built-in checks arrive with it: `plugin-not-found`
  and `plugin-invalid`, with a fixed severity, `unknown-extension`, `consumer-extension`,
  and `missing-plugin`, which says when a compared dictionary was produced with a plugin the
  run has not loaded.  `ddd schema --plugin` publishes a schema closed over a project's
  plugins, `ddd compare --plugin` loads them for an archived candidate, and
  `ddd checks --plugin` lists their checks.  `examples/plugins/ddd_layout.py` is a worked
  example.  **Migration:** none for an existing project - no key is required and nothing is
  stamped.  The dictionary format moves from 6 to 7: every object, every instance and the
  dictionary itself carry `extensions`, and the dictionary records `plugins`; a dictionary
  dumped by an older DDD reads back with all of them empty.
* **`id` on a producing declaration: the identity of a data object, which survives a
  rename.**  Twelve lowercase base32 characters, opaque, written by `ddd id --assign` rather
  than typed by hand.  `duplicate-id` refuses two objects of one project sharing one, and
  `consumer-identity` refuses it on an `input` declaration, the same reasoning that already
  refuses `init` and `section` there; `missing-id` reports a producing declaration that states
  none, at `info`, so an unmigrated project sees it without being held to it.  `ddd compare`
  now pairs objects on the id before falling back to the name, so a rename is one
  `renamed-object` finding with the ordinary interface comparison still run across it, rather
  than a removal and an addition that never meet; a name freed by a rename and claimed by a
  different object is `reused-name`, an error, because a calibration dataset or a recording
  keyed by that spelling binds to the new object exactly as readily as it did to the old one.
  **Migration:** the dictionary format is 6, and every object of a freshly dumped dictionary
  now carries `id`, `null` where nothing was stamped, exactly like `section` or `raster`; a
  leaf of a structured object carries the same thing under `instance_id`.  Run
  `ddd id --assign` over the description files once and commit the result; until then
  `missing-id` reports at info, which a migrated project turns into its gate with
  `-W missing-id=error`.  A baseline archived at format 5 or older carries neither key at all,
  which is not the same as having none stated - its objects pair by name and no rename is ever
  inferred against it.
* **`ddd id --assign FILE...`** writes an id into every producing declaration and instance
  that has none, editing the files in place; a declaration that already carries one is left
  alone, so a second run changes nothing.
* **`ddd compare --renames PATH`** writes the old-to-new name pairs of the comparison - each
  object's id, its old name and its new name - so a calibration dataset, a recording or a test
  script keyed by the old spelling can be migrated without parsing the comparison's own
  findings.

## 0.7.0

* **Seventh description file kind: measurement rasters.**  A `rasters` file names the DAQ
  events a target's XCP configuration offers - a short name, an event channel number and,
  optionally, a cyclic period - and a definition or its producing component names the one a
  measurement is updated in, resolved exactly like a memory section: the declaration's own
  `raster`, else its component's default, else nothing.  Five checks keep the vocabulary
  honest: `duplicate-raster` and `duplicate-event` catch two rasters sharing a name or an
  event channel, `unknown-raster` catches naming one nothing declares, `consumer-raster`
  catches an `input` declaration claiming an event it does not own, and `raster-kind` catches
  one stated on a calibration object, which no DAQ list ever carries.  An exported measurement
  with a raster now reaches the generated a2l with an `IF_DATA XCP` block naming its event
  channel, so a calibration tool preselects the right one instead of an engineer guessing
  which task moves the signal.  **Migration:** none for existing description files - a
  measurement naming no raster, whose component names none either, reaches the a2l exactly as
  before.  The archived dictionary format moves from 4 to 5; a dictionary dumped by an older
  DDD still reads back, with every object's raster resolving to `null`.
* **The documentation deployment reads back what it published.**  The archive branch is a git
  push and the site is an artifact handed to Pages, and nothing made the two agree: 0.6.0
  reached `gh-pages` with a version index naming it while the site went on serving a build
  assembled before the release existed - a complete set of documentation at a url that
  answered 404, offered by no menu, with every step of every job reporting success.  The
  deploy job now ends by fetching the published `versions.json` and the directory it just
  wrote, and fails if the site is not serving them.  Re-running the workflow republishes the
  archive branch as it stands, which is the fix when it does fail.
* **The editor extension is no longer published to the Visual Studio Marketplace.**  It never
  was: the step needed a personal access token from an Azure DevOps organisation owning a
  `sauci` publisher, neither was ever created, and it failed on every release it ran on while
  the rest of the pipeline reported success around it - with four pages meanwhile telling a
  customer to search the Extensions view for an item that answers 404.
  **Migration:** install the `ddd-<version>.vsix` attached to the
  [GitHub release](https://github.com/Sauci/ddd/releases), which is what every page now says
  and what the release has always carried.  Building, testing, packaging and attaching the
  extension are unchanged; only the marketplace upload is gone.

## 0.6.0

* **The docker development image builds and its services run again.**  `docker/Dockerfile`
  still copied a `completion` directory that was removed before 0.5.0, so `docker compose
  build` failed on the first `COPY` and every service with it; and the `generate` service
  still used the pre-artefact command line, so it exited with a usage error.  Both are the
  local equivalents of ci jobs, which is where the breakage stayed invisible: ci installs the
  package itself and never builds this image.
* **A structure kept out of the a2l is now a change `ddd compare` can see.**  The export
  decision of a structured variable reaches its members: the resolved dictionary records on
  each leaf what the variable's `a2l.export` and the member's own together come to, where it
  used to record only the member's half and leave the a2l backend to put the two together at
  render time.  Everything else read one half and believed it, so a delivery that stopped
  exporting a structure compared clean against its predecessor while every one of its members
  left the file.  The comparison now reports one `changed-a2l` per member.
  **Migration:** none for the description files.  A dictionary dumped by 0.5.0 states the
  member's half alone; compared against a new one, the leaves of a variable that was never
  exported report `changed-a2l` once, on the delivery that re-dumps them.
* **New check `address-missing` (warning).**  An object the a2l carries with no entry in the
  `--address-map` the run was given is now reported instead of silently written at address
  zero.  It fires only when a map is supplied - without one every address is zero by
  construction, which is the run a build makes before it has linked anything.  The entries of
  the map that match no object are named in a note, because a renamed object usually loses
  its address and leaves its old spelling behind in the same file.  `--strict` makes it fatal,
  which is what a post-link build wants.
* **New check `incomplete-project` (info).**  Relaxing a check that *drops* a declaration -
  `unknown-type`, `unknown-constant`, `type-kind` - never put the variable back; it only hid
  why it went.  With the cause silenced, `ddd list` printed a table one row short and exited
  zero and `ddd dump` archived a dictionary an object was missing from, with nothing said.
  The consequence is now reported when its cause is not.  Like the other checks that need the
  whole project to be right about anything, it stays quiet for a file the language server
  reads on its own.
* **The language server survives a badly shaped message, and reads a byte order mark.**  A
  correctly framed request missing the `params` an editor always sends used to raise out of
  the loop and end the session; it is now refused with json-rpc `InvalidParams` (-32602) and
  the conversation goes on.  Description files are read as `utf-8-sig`, the encoding the
  loader has always used: read as plain utf-8 a file carrying a byte order mark - what several
  Windows editors and PowerShell redirection write - did not parse, so every finding collapsed
  onto the first character and hover, go to definition, rename and the code actions all
  answered nothing, on a file `ddd check` called perfectly good.  A `file://` uri is no longer
  unescaped twice, which made `a%20b.ddd.json` name `a b.ddd.json`.
* **The language server reads the project once per save rather than once per keypress.**  The
  build records and the loaded projects are kept between requests and dropped at every open,
  save and rename.  A hover used to walk every configured build directory looking for
  `ddd-build.json` and then re-read and re-validate every description file of every image the
  component is linked into, twice over.
* **`ddd generate` names its artefact: `c`, `a2l` or `all`.**  The artefact is part of the
  command and each carries only the options of what it produces: `-t/--template-dir`
  (required) and `--const-inputs` exist on `c` and `all`, `--byte-order` and
  `--address-map` on `a2l` and `all`.  `ddd generate a2l` is the second run of a build
  stated as such: the first run generates the c the image is built from, the linker decides
  the addresses, and the second writes only the a2l with `--address-map` carrying them -
  instead of re-rendering every source and reporting each unchanged.
  **Migration:** `ddd generate PROJECT ...` becomes `ddd generate all PROJECT ...`, and
  `--no-a2l` becomes the `c` artefact.  `ddd_generate()` in the CMake integration emits the
  new form itself; a build calling the tool directly changes its command lines.
* **The generated definition file is compiled with the full interface compile usage of the
  registered components.**  In the collected mode, `ddd_generate()` used to hand
  `<image>_ddd_globals` only the *include directories* of the registered components; it now
  forwards their interface compile definitions and compile options as well, resolved through
  each component's public link closure, still without creating any link edge.  Includes
  alone were a trap: a hand written header named by an external type may change its layout
  under the component's interface defines, and the definition file then found every header,
  compiled cleanly, and laid the variables out differently than the image using them.
  A `LINK_LIBRARIES` entry that only re-stated a registered component's own usage can be
  dropped; the option remains for the hand written `PROJECT` mode and for what no
  description implies, such as a header the project's own c templates include.
* **The c views spell types in the description's vocabulary too, and boolean initialisers
  need no header.**  Every view offering `c_type` (the ISO spelling, `uint16_t`) now offers
  `datatype` beside it - the type as the description spells it: `uint16`, `boolean`, or the
  declared name of a structure or external type.  A platform whose header already provides
  those names (AUTOSAR's `Platform_Types.h` spells them exactly) renders `datatype` and
  drops the per-template mapping tables.  A `boolean` initial value is now emitted as `1`/`0`
  rather than `true`/`false`: the words need `<stdbool.h>` before C23 and do not exist on
  AUTOSAR platforms at all, while the numerals mean the same thing everywhere - and the
  initialiser is the one c fragment a template cannot respell.

## 0.5.0

Initial release.

DDD describes the global variables of a component based embedded software project in json
description files, checks that every component agrees on them, and generates the artefacts a
build and a calibration tool consume.

* **Six description file kinds.**  A *project* file names the components and the shared
  vocabularies of an image; a *component* file declares that component's data interface -
  measurements, parameters, curves, maps, axes and value blocks, each stating its `kind`,
  its storage (`datatype` or `typename`), its `conversion` and its `volatile` qualifier
  explicitly - and may declare the types and constants it publishes inline, entries exactly
  those of the standalone files and names in the same project wide namespace; a *types*
  file declares scalar types, structures and external types a project shares by name, an
  external type naming a c type a hand written header defines, carried verbatim by a
  structure member and included by the generated types header;
  a *units* file pins the unit spellings a project allows; a *sections* file declares the
  linker sections a definition may place its object in; a *constants* file declares the
  named integer constants a shape may state instead of a number, carried into the generated
  c by name and into the a2l as `SYSTEM_CONSTANT`s.  Every format is published as a json
  schema (`ddd schema component|constants|dictionary|project|sections|types|units|all`).
* **Consistency checks with stable identifiers.**  `ddd check` verifies the description as
  a whole - one producer per variable, agreeing declarations, resolvable types, units,
  sections and constants, representability in the a2l - and reports each finding under a
  stable check id with a default severity a project can raise, lower or silence per check (`-W`,
  `SEVERITY` in CMake).  `ddd checks` lists them all.
* **C generation from project owned templates.**  `ddd generate` renders the jinja2
  templates of the project - DDD ships a working example set behind `ddd templates-dir`,
  never a built in fallback - producing the variable definitions, per component `extern`
  headers and the types header.
* **A2L generation** following ASAM MCD-2 MC (ASAP2) 1.6.1, structures flattened into one
  record per member, with `--address-map` supplying the addresses a build reports.
* **Deliveries.**  `ddd dump` archives the resolved dictionary (format 4) and
  `ddd compare` reports whether one delivery can replace another; against a baseline from
  format 3 or older, which recorded no dimension spellings, dimensions compare by value.
* **CMake integration.**  `cmake/Ddd.cmake` (behind `ddd cmake-dir`) provides
  `ddd_add_component()` and `ddd_generate()`, collecting the project from the c link graph
  or taking an explicit `PROJECT`, wiring the checks into the build and recording the
  build's configuration in a `ddd-build.json` for editors to pick up (`ddd build-info`).
* **Editor support.**  `ddd lsp` is a language server that reports the checks while a file
  is written, navigates between the components that share a variable, and renames across a
  project; `editors/vscode` holds the VS Code extension that launches it.

The requirements are stated in [`SPEC.md`](SPEC.md), the authoritative contract for the
behaviour of the tool.
