Command line interface
======================

DDD is a plain command line tool: it reads json files, writes files or a report, and exits,
and everything a build or a delivery needs from it happens in one such run. That is what
makes it usable from wherever the build already lives - a makefile, a cmake project (see
:doc:`build_integration`), a batch file on an engineer's machine, or a ci job that never sees
a terminal. Two commands do not exit: ``ddd lsp``, the language server an editor keeps running
(see :doc:`editor_integration`), and ``ddd gui``, the preview of a browser interface, which
serves until it is interrupted. The one file the tool leaves behind for its own use is the
``ddd-build.json`` that ``ddd build-info`` writes for the language server and for ``ddd gui``,
which both apply the severities of the build that names a project.

The same discipline governs the output. The findings - everything the tool has to say about
a project - are written to standard error, one line per finding followed by a summary, while
what a command actually produces (a listing, the dumped dictionary, a json schema, the list
of source files) goes to standard output. The two never mix, so
nothing has to be filtered out of a redirection: ``ddd dump project.ddd.json >
baseline.json`` archives the dictionary and nothing else, even on a run that had something to
say about it.

For a job that files findings rather than reads them, nine commands understand
``--format json``: ``check``, ``compare``, ``generate``, ``list``, ``dump``, ``sources``,
``artefacts``, ``checks`` and ``tool``. That leaves out ``schema`` and ``build-info``, whose
output is json already, ``lsp``, which speaks json-rpc, ``gui``, which serves pages to a
browser, ``cmake-dir`` and ``templates-dir``, which print one path, and ``id``, which reports
the files it skipped and one total rather than findings. In json the diagnostics become part
of the document the command prints, next to whatever else it has to report:

.. code-block:: text

   $ ddd generate all examples/demo/demo.ddd.json -o build/gen -t examples/templates --format json
   {
     "diagnostics": [],
     "summary": {
       "error": 0,
       "warning": 0,
       "info": 0
     },
     "generated": [
       {
         "path": "build/gen/ddd_globals.c",
         "status": "created"
       },
       {
         "path": "build/gen/ddd_globals.h",
         "status": "created"
       },
       ...
       {
         "path": "build/gen/DemoDevice.a2l",
         "status": "created"
       }
     ]
   }

The one exception is ``ddd dump``, whose standard output is itself the payload: there the json
diagnostics go to standard error, so that both formats leave the dictionary alone. Given
``-o``, the dictionary goes into that file instead and standard output stays empty; the
diagnostics stay where they were, and in json they name the file written, with its status,
under the same ``generated`` key ``generate`` uses:

.. code-block:: text

   $ ddd dump examples/demo/demo.ddd.json -o build/dump/demo.json --format json
   {
     "diagnostics": [],
     "summary": {
       "error": 0,
       "warning": 0,
       "info": 0
     },
     "generated": [
       {
         "path": "build/dump/demo.json",
         "status": "created"
       }
     ]
   }

A ``path`` is spelled as the run was asked for it - relative when ``-o`` was relative - and a
``status`` is ``created``, ``updated``, ``unchanged`` or, for a file an earlier ``generate``
wrote into its output directory and this run no longer writes, ``removed`` (see
:ref:`what-a-run-owns`).

``ddd list --format json`` answers with the project, its components and one row per variable
beside the diagnostics. A row is the record the :doc:`data dictionary <data_dictionary>`
carries for that object, so the rows come in two shapes: a member of a structured variable
carries ``path``, ``instance`` and ``instance_id`` where a plain object carries ``id``. Every
row of either shape opens with ``name`` - a member's being its access path - so one key
answers what a row is about:

.. code-block:: text

   $ ddd list examples/demo/demo.ddd.json --format json
   {
     "project": "DemoDevice",
     "components": [
   ...
     "variables": [
       {
         "name": "AxisA",
   ...
         "name": "Diagnosis.faults",
         "path": "Diagnosis.faults",
         "instance": "Diagnosis",
   ...
     "diagnostics": [],
     "summary": {
       "error": 0,
       "warning": 0,
       "info": 0
     }
   }

``ddd artefacts --format json`` answers with ``artefacts``, one ``{"name", "kind"}`` per
artefact with ``kind`` either ``built-in`` or ``plugin``, and ``plugins_without_artefact``,
the names the text format puts in a note:

.. code-block:: text

   $ ddd artefacts examples/layout/project.ddd.json --format json
   {
     "artefacts": [
       {
         "name": "c",
         "kind": "built-in"
       },
   ...
       {
         "name": "layout",
         "kind": "plugin"
       }
     ],
     "plugins_without_artefact": [],
     "diagnostics": [],
     "summary": {
       "error": 0,
       "warning": 0,
       "info": 0
     }
   }

``ddd checks --format json`` is a list rather than an object, one entry per check, each
carrying ``check``, ``default_severity``, ``description``, ``overridable``,
``needs_every_component`` and ``comparison`` - the last three being the facts the text format
marks with ``(fixed)``, ``(project)`` and ``(comparison)``. ``ddd sources --format json``
carries its listing as ``sources``, described with the command further down this page.

The exit code is the same everywhere, which lets a build system treat DDD like a compiler:

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - code
     - meaning
   * - ``0``
     - the command did what it was asked and found nothing worth reporting.
   * - ``1``
     - findings: at least one diagnostic of severity ``error`` survived the severity policy.
       ``ddd sources`` and ``ddd artefacts`` also exit ``1`` when the root file cannot be read
       at all, and ``ddd id`` when one of the files it was given was not readable as json, or
       could not be written back, and had to be skipped - the others are stamped either way,
       and it reports each skipped file without a diagnostic.
   * - ``2``
     - the command line itself was wrong: a missing or malformed argument, an unknown
       severity, or an unknown check that names no plugin, in ``-W``, a fixed check
       overridden, or a missing ``-t`` where the c sources are part of the run - raised
       before any analysis, so the project was never examined and nothing but the error
       is printed. A usage error raised by a step that follows the analysis instead - a
       plugin hook that raises, an override naming a plugin check no loaded plugin
       registers, a ``--renames`` file, a dumped dictionary or an artefact that cannot be
       written, an output path naming a file the run itself read (``dump -o``,
       ``compare --renames`` and ``generate --dictionary`` each refuse one, naming it, since
       nothing DDD writes is ever a file it read), an address map that cannot be read,
       ``ddd compare --plugin`` refused beside a project description on the *candidate*
       side, which names its own plugins, or a run that would write nothing - reports the
       findings of the run
       first, in the requested format, before the error follows; the exit code is still
       ``2``.
   * - ``130``
     - the run was interrupted: Ctrl-C, or anything else that raises ``KeyboardInterrupt``,
       inside DDD or inside a plugin's hook. It is the code a shell reports for a command
       killed by ``SIGINT``, and it is distinct from ``1`` and ``2`` so that a script does
       not read a run somebody stopped as a project with errors. The run prints one line,
       ``ddd: interrupted``, and no traceback.

A reader of standard output that stops reading is not an error either: ``ddd schema component
| head -1`` ends at ``0`` and in silence, where the broken pipe used to be reported as a usage
error and failed a paging script under ``set -o pipefail``.

Every long option is spelled in full. ``argparse`` offers any unambiguous prefix by default,
and DDD turns that off: ``--stand`` for ``--standalone`` would work until the day a second
option begins with those letters, and the script that took the offer would then fail with
"ambiguous option" and nothing else to go on.

The commands
------------

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - command
     - purpose
   * - ``ddd check FILE``
     - run every consistency check on a project or on a single component; with ``--baseline``
       also answer whether that project can still replace a published delivery, so that one
       command and one exit code cover both questions, and with ``--standalone`` judge a
       component on its own, holding back the checks that need the rest of the project.
   * - ``ddd compare BASELINE CANDIDATE``
     - report whether the candidate delivery can stand in for the baseline. Either side may be
       an archived dictionary or a project description; ``--plugin`` loads the plugins of an
       archived candidate, since only a project description names its own, and ``--renames``
       also writes the old-to-new name pairs the identities revealed, for migrating datasets
       and recordings.
   * - ``ddd generate c|a2l|all|<plugin> FILE -o DIR``
     - check the project and, if it is consistent, write the named artefact into ``DIR``:
       ``c`` renders the c sources, ``a2l`` writes the a2l file, ``all`` produces both and
       the artefact of every plugin the project names that provides one, and the name of such
       a plugin runs its backend alone. Each
       artefact takes only its own options - ``-t`` names the directory of jinja2
       templates the c sources are rendered from, required wherever c is rendered and with no
       default, because which files the project wants and what they look like is not
       something DDD can guess; ``--address-map`` and ``--byte-order`` belong to the a2l.
       ``all`` alone takes ``--without c`` or ``--without a2l``, repeatable, which leaves that
       built-in artefact out while still producing the plugins' - the run a build wants when
       the a2l is written later, once the addresses are known. Naming ``c`` instead is not the
       same thing: it produces no plugin artefact at all, and says nothing about it.
       Subtracting an artefact takes its options with it, so ``--without a2l`` beside an
       ``--address-map`` is refused rather than quietly ignored, and a run that has subtracted
       the c neither wants nor accepts ``-t``.
       ``--dry-run`` reports what would be written without writing anything, ``--force``
       generates in spite of errors. Every artefact also takes ``--dictionary FILE``, which
       writes the resolved data dictionary - the text ``ddd dump`` prints - in the same write as
       the artefacts, so that all of them are written or none is; a path an artefact of the
       run is written to is refused. That is how a build keeps the dictionary beside what it
       generated, in one analysis and one report of its findings.
   * - ``ddd list FILE``
     - print the table of variables with their kind, datatype, unit, shape, initial value
       with its physical reading, producer and consumers - the quickest answer to "who
       writes this?". With ``--standalone`` a component is listed on its own, the checks
       that need the rest of its project held back as ``check --standalone`` holds them.
   * - ``ddd dump FILE [-o FILE]``
     - print the resolved data dictionary, the contract every backend consumes. This is what
       gets archived next to a delivery and handed to ``ddd compare`` later. ``-o`` writes it
       into a file instead, the way ``generate`` writes an artefact: the same bytes on every
       platform, and a file whose content would not change is left untouched, which is what a
       build depending on it needs and what a redirection cannot promise. Unlike ``generate``,
       a finding does not hold the dictionary back: errors and all, the dictionary is what the
       project resolved to and ``-o`` writes it, so a script archiving a delivery reads the
       exit code rather than the presence of the file. Only a root that cannot be read leaves
       the file as it was - there is then no dictionary at all. ``--standalone``
       dumps a component on its own, as it does for ``list``.
   * - ``ddd id --assign FILE...``
     - write an ``id`` into every producing declaration of the given description files that
       has none, as one added line each: the file keeps its byte order mark, its line endings
       and its formatting, and the new text is staged beside it and renamed onto it, so a run
       that dies leaves a hand-authored description as it was. A declaration that has one is
       left alone, so a second run changes nothing. The identity is what lets ``ddd compare`` report a rename as a
       rename, and what ``missing-id`` asks for.
   * - ``ddd schema KIND``
     - print the json schema of ``component``, ``constants``, ``dictionary``, ``project``,
       ``rasters``, ``sections``, ``types`` or ``units``, for an editor that offers completion
       inside a
       ``*.ddd.json`` file or for a validator in a ci job; ``all`` writes every schema into
       a directory; ``--plugin`` closes the ``extensions`` property of ``component`` and
       ``project`` over the named plugins' models.
   * - ``ddd sources FILE``
     - list every file the project is built out of - the description files and the modules of
       the plugins it names - for the dependency list of a build system. It reports its
       findings without letting them change its exit code.
   * - ``ddd artefacts [FILE]``
     - list the artefacts ``generate`` accepts for this project: the built-in ``c`` and
       ``a2l``, and the name of every plugin it names that provides one. What each writes is
       not listed, because a plugin's file names follow from the resolved project rather than
       from the plugin alone - ``ddd generate all --dry-run`` reports those. A plugin that
       provides no backend is no artefact of its own; it is named in a note rather than left
       out in silence, which would read as the plugin having failed to load. Such a plugin is
       not idle: the block it contributes is part of the vocabulary a project's own templates
       read, and those are rendered by ``c``. With ``--plugin`` and no file it answers the same question for a
       build that has not assembled its project description yet.
   * - ``ddd lsp``
     - run the language server, speaking the Language Server Protocol on stdin and stdout,
       so an editor reports the checks while a description file is being written; see
       :doc:`editor_integration`.
   * - ``ddd gui [PROJECT]``
     - preview: serve a browser interface over one project's description files, on this
       computer by default, and open the browser on it. The project opens on a graph
       of its modules, an arrow per pair coloured by the worst disagreement between
       them, with the component table, a Units tab - listing the project's units and
       maintaining its vocabulary - a Findings tab of every finding, worst first, and a
       Compare tab asking whether the open project can replace a baseline delivery the
       reader names, one tab away. A variable's panel shows every key its declarations
       share, says which of them they disagree about, and settles one on every declaration
       at once. A ``definition-mismatch`` finding carries that settlement as a button of
       its own, one per disagreeing key, reaching every declaration that disagrees, not only the
       one the finding names. Opened on a consumer it takes the producing component's
       value; opened on the producer's own row, where the same disagreement is filed a
       second time, it sends that value outward - never a direction the reader chooses.
       That value may be silence: a producer stating no unit where its readers state
       one is settled by taking it out of all of them, from either row.
       Nothing is offered where the variable has no single producer - several components
       writing it, or none, leaves no owner to take a direction from; the variable's own
       panel, one click from the finding, still settles any value the reader chooses, unless
       it would leave the file unable to load. A key is offered only where one change settles
       it for every declaration: never ``kind``, the one key no edit may carry between
       declarations, and not a key some declaration could neither take nor drop - one its
       named type fixes, one its kind does not allow, or the ``datatype``, ``conversion`` or
       ``typename`` its own storage is made of. A component's page
       adds a declaration to its interface - a variable
       already declared, carrying the producer's keys where there is one and the
       project's own where there is not, or a new object of one of six kinds - and
       takes one away. Its table's Shape column opens the page of a curve, a map, an
       axis or any other declaration shaped in one or two dimensions: its values as a
       grid, laid against its axes' breakpoints or plain indices and named with the axis
       on each edge, in physical or in raw by a toggle. A curve, a map and an axis are
       offered whatever type they name; anything else states its own dimensions and its
       own datatype, so a dimensioned declaration naming a structured type is shown
       there and not offered, and so is a deeper shape. One cell
       is changed at a time, previewed - in a sentence naming what it sets and the
       producing file it lands in - and applied like every other change here, and put
       back by the same undo. A table copied from a spreadsheet is pasted anywhere in
       the grid to replace every value of the object at once - the object's own shape,
       or exactly one row and one column larger for the header pasted along with it -
       previewed and undone the same way. Its header is discarded unread, so one naming
       a different axis is caught only by that preview, not by the paste itself. Under
       the grid, the object's values are drawn as a picture too: a marker at each point
       and a line joining them where a row holds more than one, laid against its axis's
       own breakpoints - unevenly spaced, exactly as those breakpoints are - or over
       plain indices where it has none, with its declared limits ruled across it
       wherever they fall inside the drawn range. It follows the same toggle, offers no
       control of its own, changes nothing, and is drawn under a read-only grid exactly
       as under a writable one, left undrawn only where there is no grid to begin with.
       The toggle always rescales to its own range: for a positive conversion the same
       numbers in a different unit draw the very same picture, only the readings along
       its edges changing; a negative one - legal here - mirrors the curve instead of
       leaving it alone. A Types tab lists the types the project declares, with
       what each fixes and what names it;
       what a scalar type fixes is changed there, and renaming one rewrites every
       declaration and member naming it in one edit.
       Every change is written into the files in their own layout and checked
       the way ``ddd check`` checks them. A change applied here can be undone while
       the server runs, from a button beside the project's name naming what it would
       put back: the files are shown first, the lines on request, and a file that
       changed on disk since is named and left alone. The list of what can be undone
       lives in the running server and ends with it.
       The Compare tab's baseline is a dumped dictionary, or a project or component
       description, at a path under the directory ``ddd gui`` was started in, refused, and
       told why, when it is outside that directory, unreadable, not valid json, a
       description or a dictionary this DDD could not read, or json that is neither. Its
       verdict answers only whether the project can replace that
       baseline, not whether the project is itself consistent: the project's own findings,
       the Findings tab's own question, take no part in it. A finding that names a place in
       this project leads there, as on the Findings tab: a plugin's comparison rule files at
       the declaration it is about. The comparison's own findings name the whole delivery
       rather than a place in one file, and the baseline's own, marked ``in the baseline:``,
       name a place in the baseline's files rather than in this project's - for those the
       panel says so rather than offering to go anywhere. The renames the comparison finds
       are drawn here as a
       table, exactly what ``ddd compare --renames`` would write to a file, and are not
       written from this tab.
       A Shared files tab lists what the project declares in its shared files: every constant,
       from a constants file or a component's own list, every memory section, declared in a
       sections file and nowhere else, and every measurement raster, declared in a rasters file
       and nowhere else. A row says which vocabulary an entry belongs to, what it states - a
       constant its value, a section the access the running software has to it and the alignment
       it guarantees, a raster its event and its cycle, stated together as ``event 1, 10ms`` or
       as ``event 2`` alone where it states none - and what names it. What an entry states is
       changed there: a constant's value and its description, a section's access, its alignment
       and its description, a raster's event, its cycle and its description. Renaming one
       rewrites every place naming it in one edit - for a constant every shape spelling it; for
       a section its own entry and every definition placing data in it; for a raster its own
       entry, every definition measured in it and a component's own default naming it for
       everything it produces - since a rename reaching the entry alone would leave those
       definitions, or that default, naming a section or a raster nothing declares. A section's
       name is judged as the linker string it is rather than as a c identifier, which is why a
       leading dot is an ordinary spelling; a name outside the letters, digits, ``.``, ``_`` and
       ``$`` that spelling allows is refused, being one whose file would then not load, and so
       is a name the project already declares as a section, for a rename and for a new entry
       alike, because each entry carries its own access and alignment and merging two would move
       data into memory with different properties. A raster's name is judged as the short name
       of an XCP event it is, rather than as a c identifier either: a name outside the printable
       ASCII, with no space, that a short name allows, or one longer than the eight characters
       the a2l field holds, is refused, being one whose file would then not load, and so is a
       name the project already declares as a raster - ``'10ms' is already a raster this project
       declares`` - for a rename and for a new entry alike, because each entry carries its own
       event and cycle and merging two would sample one signal on another's channel. One of the
       three is declared there too, writing ``constants.ddd.json``, ``sections.ddd.json`` or
       ``rasters.ddd.json`` beside the project description and adding it to ``includes`` where
       the project has no file of that kind - refused instead of written while a file the
       project includes could not be read at all, since one of those may be the file the new one
       would be a second of. A section is declared with both an access and an alignment, the
       format defaulting neither: an entry missing one is an entry whose file would not load.
       What each may say is the model's rule rather than the interface's, and a refusal names it
       - the access is one of two words, the alignment a power of two written as a whole number.
       A raster is declared with an event alone, the format defaulting its cycle and its
       description both: a raster whose cycle is left unstated is not cyclic - crank
       synchronous, on change, on demand - a real kind of raster and not an omission. A refusal
       names what either may say - the event a channel number from 0 to 65535 written without a
       decimal point, the cycle a count of 1 to 255 times a decade from 1ns to 1s written as one
       string. Making a raster that is already declared acyclic is not something the tab does:
       a raster states no cycle by leaving the key out of its entry, and an emptied Cycle field
       asks for the empty string instead, which is no period and is refused as one. An event
       another raster already states is refused too, naming which
       one - ``event 1 is already claimed by raster '10ms'`` - whether it is being declared or
       changed: an event is a property of the target's XCP configuration, distinct across the
       project, so not free for a second raster to claim. Removing one is refused while anything
       still names it - a shape, for a constant; a definition placing data there, for a section;
       a definition measured in it or a component's own default naming it, for a raster, its own
       refusal counting every shape rather than naming one: ``2 shapes name 10ms, so it cannot
       be removed.`` The last one a file declares is removed like any other, leaving a file that
       declares nothing, which loads and is reported as ``empty-vocabulary``; the last constant
       a component declares takes the component's ``constants`` key with it, since a component
       that publishes none leaves the key out. A constant value no shape can use is reported
       there by ``dimension-value`` rather than refused: the interface does not invent a rule
       the format itself does not have. A finding
       naming a constant, a section or a raster leads to the tab, a name no file declares
       landing on the form that declares it.
       A Files tab lists the root project's own ``includes``, one row per entry in the
       description's own order - a pattern's own row followed immediately by every file it
       matched, indented beneath it - each named as the description spells it, or, for one
       of a pattern's files, by its path relative to the project's own directory, or by its
       base name where it lies outside that directory. A row's Kind is read off the same
       ``State.files`` every other tab reads, and its Findings column counts what is filed
       on its file there, and on an entry's own row what is filed on the entry itself as
       well: a pattern's own row adds up every file it matched, and a row naming nothing
       has only its entry's. Its State is read off ``State.files`` where the row's file is
       there - blank for a file that loaded, ``did not load`` for one that did not - and off
       the entry where it is not: blank for a pattern's own row, ``names no file`` for an
       entry naming nothing at all, a plain path to no file or a pattern matching none, and
       ``not read by the last analysis`` for a file an entry names that the revision the
       page holds has not read. Among the causes of that last: the root's own schema failing
       before its includes are read, a plugin's model raising while the project is read, a
       pattern matching a file created since, or an entry the description gained since,
       which the tab's own New file and Add show until the revision after them arrives:
       measured, never on a copy of ``examples/vocabulary``, and for about a second on a
       project of 18000 findings. New file, Add a file and Remove are its three actions, the
       first two above the table and the third opened by selecting a row. New file takes a
       kind - ``component``, ``types``, ``units``, ``constants``, ``sections`` or
       ``rasters``, offered as ``GET /api/files`` sends the list, the page keeping no copy of
       its own - and a name, creating the file beside the project description and adding it
       to the includes in the same edit: a vocabulary file declares nothing and a component
       takes a second name of its own, while a units file is the exception, listing every
       unit the project states where no file of its tree is a units file already, so the one
       click cannot fail a passing project with ``unknown-unit`` at once, and created empty
       where a sub-project's own units file has opted the whole tree in already. Add a file
       takes a path, written from the project description's own directory or absolute,
       appended to the includes exactly as written, and previews the errors the analysis
       counts it bringing rather than refusing for them: it informs rather than refuses.
       Remove offers to take every entry of the selected row's own key out of the includes -
       the files stay on disk - refused where the analysis counts an error more at some place
       than the project has there now, naming the first and how many. Both count place by
       place, so an error that takes the place of another of its check at a place within a
       file is not counted: Add's preview can leave it out, and a removal can let it through,
       but never in a project with no errors. On a whole file, or on no place at all, the two
       are told apart by their words as well, and such an error is counted. An allowed
       removal a pattern still keeps in the project all the same says so, naming the pattern.
       Each is refused in the server's own words. New file: a kind it does not create - ``no
       file of kind 'project' can be created here; the kinds that
       can are component, types, units, constants, sections and rasters``; a name outside
       what a file may be called - ``'a.b' cannot name a new file: a name is one or more
       of the letters a to z and A to Z, the digits 0 to 9, '_' and '-', and .ddd.json is
       added to it``; a file of that name there already, naming both - ``units.ddd.json
       is there already, beside project.ddd.json``; a component with no second name - ``a
       new component needs a name, besides its file's``; one no c identifier - ``'2Motor'
       cannot name a component, not being a usable c identifier``; one c or a generated
       header reserves - ``'int' cannot name a component, being reserved by c or by a
       header DDD generates``; and one taken already, naming the component that has it
       - ``this project has a component called 'Pump' already`` - or naming it and the
       case-folded spelling offered - ``this project has a component called 'Pump' already,
       and 'pump' differs from it only in upper and lower case, so the two would ask for
       the same generated header``. A first units file is refused too, where a file of the
       project did not load - ``b.ddd.json did not load, so a first units file could not
       list every unit in use``. Add a file: a path lying outside what ``ddd gui`` serves,
       naming the path and the directories served - ``../outside.ddd.json lies outside
       what ddd gui serves, /home/you/project; start it in a directory holding this file
       to add it here``; one naming no file - ``missing.ddd.json names no file; a file not
       there yet is created, not added``; the project's own description - ``p.ddd.json is
       this project's own description, which it cannot include``; a file the project has
       already, naming the entry - ``./a.ddd.json is part of this project already, as the
       entry 'a.ddd.json'`` - or naming the pattern that brings it in - ``lib/l.ddd.json is
       part of this project already: the pattern 'lib/*.ddd.json' brings it in``; a python
       file - ``tool.py is a python file, which a project names among its plugins rather
       than its includes``; and one no kind the loader recognises at all - ``notes.json
       is no kind of file a project includes: it cannot be read as json, or its top level
       holds none of project, component, types, units, sections, constants and rasters``.
       Remove: a file only a pattern brings in, naming it - ``a.ddd.json has no entry of
       its own: the pattern 'lib/*.ddd.json' brings it in, and only the whole pattern
       can be removed``; a path no entry or pattern reaches - ``no entry of p.ddd.json's
       includes names other.ddd.json, and none of its patterns matches it``; and, where
       the analysis counts more errors at their places without it, naming the first and
       how many - ``removing constants.ddd.json would leave one error more than the
       project has now at its place, in pump.ddd.json: 'PressureTrend' is dimensioned by
       'TREND_SAMPLES', which is not a constant any file of this project declares`` for
       one, and, for several, ``removing sections.ddd.json would leave 3 errors more than
       the project has now at their places, the first in pump.ddd.json: 'PumpSpeed' is
       placed in '.fast_ram', which is not a section any file of this project declares``.
       Adding and removing alike are refused ``stale`` sooner than judged where a file
       changed since the project was analysed, naming every one changed - ``pump.ddd.json,
       rasters.ddd.json changed since the project was analysed, so the change cannot be
       judged until the project is analysed again`` - or a pattern reaches a file created
       since, naming every one that appeared - ``new.ddd.json appeared since the project was
       analysed, so the change cannot be judged until the project is analysed again`` - and
       are allowed unjudged instead of refused, with the same reason stated rather than a
       verdict, where the project's own last analysis did not run to its end at all - ``not every
       analysis of this project ran to its end, so what removing lib/b.ddd.json leaves
       cannot be judged``, adding answered the same way about what it would bring.
       What the page reads and writes is bounded by the directory ``ddd gui`` was started in,
       and by the project's own where a project elsewhere was named on the command line. A file
       the project includes from outside those is read by ``ddd check`` like any other and named
       by the findings on it, but is not opened, edited or drawn into a preview here: the
       refusal names the directories served, and starting ``ddd gui`` in one that holds them all
       opens them together.
       ``-b DIR`` names a build directory as for ``ddd lsp``, ``--host ADDRESS``
       listens beyond this computer for a container, ``--port N`` fixes the port and
       ``--no-browser`` only prints the address. It serves until interrupted, and its
       options are not yet part of the stable interface.
   * - ``ddd build-info FILE -o FILE``
     - record which project description a build runs DDD on and under which severity policy,
       the ``ddd-build.json`` the language server and ``ddd gui`` read; ``ddd_generate()``
       calls it at configure time, so a hand-rolled build is the only caller that needs it
       directly.
   * - ``ddd checks``
     - list every check with its identifier, its default severity, whether it can be relaxed
       (``(fixed)`` if not), whether it needs every component of a project (``(project)``)
       and whether it grades a delivery comparison rather than one project (``(comparison)``);
       ``--plugin`` lists a named plugin's own checks after the built-in ones.
   * - ``ddd cmake-dir``
     - print the directory holding ``Ddd.cmake``, so that a ``CMakeLists.txt`` finds the
       integration module of the installation it is actually using.
   * - ``ddd templates-dir``
     - print the directory holding the example c templates, to copy into a project as a
       starting point for its own. They are an example and not a default: no run of
       ``generate`` falls back to them.
   * - ``ddd tool from-elf IMAGE SYMBOL...``
     - print, as json, the declarations of the C variables a linked ELF image's DWARF
       describes - by name, by glob, or narrowed to a unit as ``UNIT:NAME`` - checked by DDD
       itself before they are printed; :doc:`toolbox` is the guide. Needs the ``elf`` extra.

``FILE`` is a project description or a single component description in every command that
takes one. A component checks, lists and dumps on its own - with ``--standalone`` holding
back the checks that need the rest of the project - which is what lets a supplier verify a
component long before an integrator ever sees it. ``ddd generate`` takes no ``--standalone``:
generating from a component is generating the c and the a2l of a project of one, and the
inputs nobody produces there are errors that stop the run. A supplier who wants the files
anyway asks for them with ``--force``, or silences the checks it has decided about with
``-W``.

The ``-t`` of the c-rendering artefacts has no default at all: an invocation that renders c
without it is refused rather than falling back to templates of DDD's own.

.. code-block:: text

   $ ddd generate all examples/demo/demo.ddd.json -o build/gen
   ddd: the c sources are part of this run, so -t/--template-dir is required

A default would have to be somebody's house style, and a project that inherited one without
choosing it would find out which one only by reading the generated code; :doc:`templates`
makes that case at length. The a2l is the opposite case, since its structure is ASAM's rather
than the project's: the a2l backend is internal and there is no template directory to give
it - which is why ``ddd generate a2l``, the run a build repeats after linking to fill the
addresses in, does not even accept one.

``cmake-dir`` and ``templates-dir`` exist for a related reason. Neither the cmake module nor
the example templates have a fixed path once DDD is installed - a wheel, an editable install
and a source checkout put them in three different places - so a project asks the tool it is
actually running where they are instead of hard-coding a guess:

.. code-block:: text

   $ ddd templates-dir
   /home/you/ddd/examples/templates

How both directories are used from a ``CMakeLists.txt`` is in :doc:`build_integration`.

Severity options
----------------

``check``, ``compare``, ``generate``, ``list`` and ``dump`` all reach the same analysis, so
they all take the same two options for deciding how loud a finding is: ``-W CHECK=SEVERITY``
(repeatable, also spelled ``--severity``) sets one check to ``error``, ``warning``, ``info``
or ``ignore``, and ``--strict`` reports every warning as an error.

The reason the policy lives on the command line rather than in the description files is that
the same finding means different things in different places. A component checked on its own
has no counterpart: the components producing its inputs are by definition not part of the
file, nobody reads its outputs yet, and the types, units, sections, constants and rasters it
names are declared in files it was not handed - so the checks that need the rest of the
project have to be held back, while everything DDD can decide from the file alone still
applies. That is what ``--standalone`` does on ``check``, ``list`` and ``dump``, in one option
rather than in a list of ``-W`` a build has to keep in step with the registry;
:doc:`consistency_checks` names the checks it covers, and an explicit ``-W`` on the same run
still wins over it.

.. code-block:: text

   $ ddd check examples/demo/components/controller.ddd.json
   examples/demo/components/controller.ddd.json#component.interface[0]: error[missing-producer]: 'ValueA' is read by component 'Controller' but no component declares it as output
   examples/demo/components/controller.ddd.json#component.interface[1]: error[missing-producer]: 'ValueB' is read by component 'Controller' but no component declares it as output
   examples/demo/components/controller.ddd.json#component.interface[2]: warning[unused-output]: 'ValueE' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[3]: warning[unused-output]: 'ValueF' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[4]: warning[unused-output]: 'StateA' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[5]: warning[unused-output]: 'StateName' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[6]: warning[unused-output]: 'ValueG' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[10]: warning[unused-output]: 'AxisA' is written by component 'Controller' but read by nobody
   2 errors, 6 warnings

   $ ddd check examples/demo/components/controller.ddd.json --standalone
   ok: 14 variables in 1 component are consistent

A check identifier or a severity that DDD does not know is a usage error rather than a silent
no-op, because the opposite behaviour would let a typo in a ci script disable a check for
years without anybody noticing:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json -W no-such-check=ignore
   ddd: unknown check 'no-such-check'

   $ ddd check examples/demo/demo.ddd.json -W unused-output=nope
   ddd: unknown severity 'nope' for check 'unused-output', expected one of error, warning, info, ignore

Both exit with ``2``. Eight checks cannot be relaxed at all - ``file-not-found``,
``json-syntax``, ``file-kind``, ``schema``, ``include-cycle``, ``include-depth``,
``plugin-not-found`` and
``plugin-invalid`` - because a file that cannot be read has nothing further to say, a
project cannot be interpreted without the plugins it names, or an include tree DDD refuses
to follow stays unread whatever the finding is reported as - and a run that carried on
regardless would report the absence of findings about a project it never saw. ``ddd checks``
marks those ``(fixed)``, and an attempt to override one is refused rather than ignored:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json -W schema=ignore
   ddd: the severity of check 'schema' cannot be changed

``--strict`` is the other end of the same dial: it turns every warning into an error, which is
what a delivery build wants, while the daily build of the same project stays readable. The
full list of checks, with the reasoning behind each default severity, is in
:doc:`consistency_checks`.

The sources of a project
------------------------

A project description does not name its components on the command line; it pulls them in
through ``includes``, possibly through wildcards, and possibly through further project files.
A build system that made the generated code depend on the project file alone would therefore
be wrong in the ordinary case: editing a component would change nothing the build can see, and
the image would happily link yesterday's globals and ship yesterday's a2l.

``ddd sources`` closes that gap. It prints one absolute path per line: the project file
itself, every description it includes however deeply, and the module of every
:doc:`plugin <plugins>` those files name, since a plugin decides what the generation writes
as much as a description does. The demo names none, so its listing is descriptions alone:

.. code-block:: text

   $ ddd sources examples/demo/demo.ddd.json
   /home/you/ddd/examples/demo/components/controller.ddd.json
   /home/you/ddd/examples/demo/components/sensor_hub.ddd.json
   /home/you/ddd/examples/demo/components/user_interface.ddd.json
   /home/you/ddd/examples/demo/demo.ddd.json
   /home/you/ddd/examples/demo/subsystems/logging/event_logger.ddd.json
   /home/you/ddd/examples/demo/subsystems/logging/logging.ddd.json

The paths are absolute and always written with forward slashes, on Windows as well, so the
list can be pasted into a makefile, a ninja file or a cmake dependency list without being
translated first, and a file reached over two different include paths appears once.

The command is deliberately more tolerant than the others: a project whose interfaces disagree
still has a well defined set of source files, and a build system asking what to watch deserves
an answer even while the project does not check out. Only a file that cannot be read at all is
fatal. Tolerant is not silent: a finding the load turned up - a missing include, say - is
reported on stderr after the listing, so a configure step hears about it from the run that
found it rather than from whichever DDD command the build runs next. This is what
``cmake/Ddd.cmake`` uses to make a hand written project description watch its own components,
described in :doc:`build_integration`.

With ``--format json`` the same list arrives as the ``sources`` array of a json document, next
to the diagnostics and their summary, exactly as the other commands report them.

Reference
---------

The reference below is generated from the argument parser of the tool itself, so an option
that is added, renamed or removed cannot leave its documentation behind.

.. autoprogram:: ddd.cli:_build_parser()
   :prog: ddd
