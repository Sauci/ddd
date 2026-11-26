Plugins
=======

DDD knows what a global variable is, who produces it, who reads it and what the generated c
and a2l need to say about it - and nothing else. A project regularly needs one more thing per
variable that is true of that project and of no other: a key for a mechanism of its own
target, a version tied to the layout, a tag another tool reads. A plugin is how the project
adds it without DDD learning it.

A plugin is a python module the project names. It owns one ``extensions`` block on a
definition and one on the project, states a pydantic model for each so that a block is
validated where it is written and completed in the editor, and contributes three optional
hooks: checks over the resolved dictionary, comparison rules between two deliveries, and an
artefact of its own under ``ddd generate``. DDD carries the block into the dictionary and
never interprets it.

Naming a plugin
---------------

.. code-block:: json

   {
     "project": {
       "name": "LayoutDevice",
       "includes": ["storage.ddd.json"],
       "plugins": ["../plugins/ddd_layout.py"],
       "extensions": { "layout": { "max_key": 4095 } }
     }
   }

``plugins`` lists module spellings. A string ending in ``.py`` is a path relative to the
project file, for a plugin the project keeps in its own repository; anything else is a
dotted module name imported from the environment, for one installed as a distribution. A
plugin acts on a project because the project names it, never because it happens to be
installed. A sub-project may name plugins too, and the set in play is the union.
``ddd sources`` lists each plugin's file beside the description files - every ``.py`` file of
one that is a package, and a ``.py`` path whether or not it imports - so that a build re-runs
the generation when a plugin changes exactly as it does when a component does, and when its
repair follows a defect. Under ``--no-plugins``, which imports none of them, a module named
without a dot is listed by the file the finder locates for it, and a dotted name is left out,
since locating its file imports the packages above it.

``extensions`` on the project holds each plugin's settings, keyed by the plugin's name and
validated against its project model with defaults filled in. The key is spelled the way a
plugin's ``name`` is - ``[a-z][a-z0-9_]*`` - so a block keyed ``my-plugin`` or ``Layout``,
which no plugin could ever claim, is refused where it is written instead of being carried to
the end of the run as ``unknown-extension``. A definition states its block
under the same key:

.. code-block:: json

   {
     "name": "EngineHours",
     "kind": "parameter",
     "datatype": "uint32",
     "conversion": { "factor": 0.1 },
     "volatile": false,
     "extensions": { "layout": { "key": 12, "version": 3 } }
   }

Only the producing declaration states one. An ``input`` stating a block is
``consumer-extension``, for the reason that makes ``init``, ``section`` and ``id`` producer
keys: a block says what the object *is*, and a component that only reads it has no claim
over that. A block naming no loaded plugin is ``unknown-extension``; relaxing that check is
how a project deliberately carries a block no installed plugin interprets, which then reaches
the dictionary as written.

Writing one
-----------

A plugin module exposes ``PLUGIN``, an instance of ``ddd.plugins.Plugin``:

.. code-block:: python

   from pydantic import BaseModel, ConfigDict, Field

   from ddd.diagnostics import CheckInfo, Severity
   from ddd.plugins import CheckContext, CompareContext, GenerateContext, Plugin


   class Entry(BaseModel):
       model_config = ConfigDict(frozen=True, extra="forbid")
       key: int = Field(ge=0, le=65535)
       version: int = Field(ge=1)


   class Settings(BaseModel):
       model_config = ConfigDict(frozen=True, extra="forbid")
       max_key: int = Field(default=65535, ge=0, le=65535)


   def check(context: CheckContext) -> None: ...
   def compare(context: CompareContext) -> None: ...
   def backend(context: GenerateContext): ...


   PLUGIN = Plugin(
       name="layout",
       object_model=Entry,
       project_model=Settings,
       checks=(CheckInfo("layout/duplicate-key", Severity.ERROR, "two objects claim one key"),),
       check=check,
       compare=compare,
       backend=backend,
   )

``name`` is the extension key, a lowercase identifier. Every model and every hook is
optional: a plugin with neither model states no block and only contributes hooks. Forbidding
extra keys on the models is what makes a typo inside a block a finding at the key, and a red
underline in the editor; it is a recommendation, not a rule.

Every check identifier is spelled ``<name>/<check>``. The prefix is the namespace: a plugin
cannot shadow a built-in check, two plugins cannot collide, and a severity override targets
one exactly as it targets a built-in check - ``-W layout/duplicate-key=warning``,
``--strict``, ``ignore``. The plugin's checks are registered when the plugin is loaded, so an
override naming one is accepted first and verified once the project is read - whether or not
the read reported findings of its own - and one that no loaded plugin registered is a usage
error, the same outcome an unknown built-in check gets. A run given a baseline is held to the
baseline's plugins as well, which it loaded to analyse it. While a plugin the run names was
skipped (``--no-plugins``), which checks it registers is not known, and an override naming a
plugin's check is accepted unverified.

The hooks
~~~~~~~~~

Each hook receives one context object rather than positional arguments, so that a field can
be added without breaking a plugin written against the previous version.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - context
     - fields
   * - ``CheckContext``
     - ``dictionary``, the resolved :doc:`data dictionary <data_dictionary>`; ``settings``,
       the block the project states, validated against ``project_model`` (built from ``{}``
       when the project states none, ``None`` for a plugin without one); ``bag``, the
       diagnostic bag; ``locate(name)``, where a finding about the object ``name`` belongs.
   * - ``CompareContext``
     - ``baseline`` and ``candidate``; ``settings``, the candidate's, from the block its
       project states or the one an archived candidate carries; ``bag``; ``locate``.
   * - ``GenerateContext``
     - ``settings``; ``generator``, the tool name and version the built-in backends put into
       their banners.

``check`` runs at the end of every analysis - ``ddd check``, ``generate``, ``list``,
``dump`` and the language server alike - over the whole dictionary, with every built-in
finding already in the bag. A hook reports with ``context.bag.add(check, message, location,
notes)``, exactly as a built-in check does. ``locate`` returns the producing declaration
under ``ddd check``, and the dump file when the dictionary was read back from an archive,
because a dump records a component's file name and not the position of each declaration.

**The dictionary a hook receives is the one every later step consumes.** It is handed over
as it is, not as a copy: the models are frozen, but the ``extensions`` blocks inside them are
ordinary dictionaries, so a hook that writes into one has changed what the backends render,
what ``ddd dump`` prints and archives, and what ``ddd compare`` reads back. That is worth
knowing in both directions. A hook that means to *report* on the project must not assign, and
a hook that needs to compute something for its own artefact should hand it to the artefact
rather than leave it in a block - a later release that copies the dictionary between the two
steps would take the value with it. The blocks are not offered as a channel between hooks.

``compare`` runs after the built-in comparison. The plugins in play are the candidate's: a
project description names its own, and an archived dump has ``ddd compare --plugin``. A
compared dictionary that records a plugin that is not among the candidate's is
``missing-plugin``, a warning saying that plugin's rules did not run, so that a comparison
can never silently skip one, save while the candidate's read skipped a plugin
(``--no-plugins``), which may be that one; it is reported at the file that records the
plugin. Unless ``--no-plugins`` skipped it, a plugin only the baseline names is one the run
did load - for the baseline's own analysis - and
whose comparison rules still did not run, which is why the warning says what is not in play
rather than what was never loaded, and why a ``-W`` naming one of its checks is accepted.

``backend`` returns an object satisfying the ``Backend`` protocol - a ``name`` and a
``generate(dictionary, output_dir)`` returning ``GeneratedFile`` entries - and is selected as
``ddd generate <name>``, with the common options ``-o``, ``--dry-run``, ``--force`` and
``--dictionary FILE``, which writes the resolved dictionary in the same write as the
artefact, and the severity and format options every analysis takes, ``-W``, ``--strict`` and
``--format``.
A plugin's artefact takes no option of its own, and none of the built-in artefacts' either:
``-t`` names the templates the c sources are rendered from, and ``--address-map`` and
``--byte-order`` belong to the a2l, so each is refused here as an unrecognized argument. It
runs under the same writer as the built-in artefacts, so two artefacts claiming one path are
refused exactly as between the c and the a2l backends. ``all`` runs them after the built-in
pair, in the order the project names the plugins, so a build gets a plugin's artefact without
naming it; ``ddd_generate`` names the plugins with ``PLUGINS`` (see :doc:`build_integration`).

Both returns are checked where they are made: ``backend`` returns a backend - a ``name`` that
is a string and a callable ``generate`` - and ``generate`` returns a list of
``GeneratedFile``, each a ``Path`` and the ``str`` to write to it. Anything else is a usage
error naming the plugin and the hook it came from, rather than an ``AttributeError`` from
somewhere further down. ``output_dir`` is handed to ``generate`` already resolved, so a path
built from it is absolute and says what it means: build every path from it, and keep every
one inside it. A file that lands outside the output directory - through ``..``, or an
absolute path elsewhere entirely - is a usage error naming the backend and the path, before
anything is written. Two paths that resolve to one file are the clash above, however
differently they are spelled: a plugin's artefact must not take the name of a built-in one,
and neither a ``..`` in the middle nor a directory junction makes a second claim on that name
a different one.

A c header a plugin writes declares or includes everything it names. ``docker/compile.sh``
compiles every generated header on its own - the header included twice and nothing else
before it - so a header that takes the address of an object and includes nothing is a header
that only compiles after something else has been included first, which is not a promise a
generated file can make. The example plugin's table includes ``ddd_globals.h``, the header
the shipped c templates write; templates of another shape spell that declaration differently,
and the rule is the same.

A finding is held to its shape where the bag takes it: ``check`` and ``message`` are strings,
``location`` is a ``Location`` or ``None`` (a ``Path`` is not one), ``severity`` is a
``Severity`` or ``None`` (the string ``"warning"`` is not one), and ``notes`` are pairs of a
string and such a location. A call that gets one wrong raises a ``TypeError`` naming the
argument, inside the hook, so that it is reported as the hook's failure below, rather than
ending the run at the report with the findings lost.

A ``check`` or ``compare`` hook returns nothing. One that hands its findings back, one that
yields and one declared ``async`` run none of what they were written to run - calling any of
them only makes the list, the generator or the coroutine - so that a rule that never applied
would read as a rule that passed; each is refused, as a failure of the hook that names what it
returned. Report with ``context.bag.add``, in a plain ``def``.

A hook that raises is a defect of the plugin, not a finding about the project: the exception
is reported as a usage error naming the plugin and the hook, with exit code 2, after the
findings the run had already gathered. A hook, or a validator on a plugin's own model,
returns; one that calls ``sys.exit`` is reported the same way, naming the code it exited with,
rather than ending the run with that code and printing nothing. The language server, which has
no usage error to give, reports either of them as a ``plugin-invalid`` finding and keeps
serving the workspace; and a module body that exits while it is imported is ``plugin-invalid``
exactly as one that raises there, whatever it raises but ``KeyboardInterrupt``, which still
interrupts: an ``asyncio.CancelledError`` or an exception class of the plugin's own that
derives from ``BaseException``, and a module-level ``__getattr__`` that raises when ``PLUGIN``
is asked for. A plugin named by a ``.py`` path the system refuses to resolve - one holding a
NUL - is ``plugin-not-found``, as a path to nothing is. A plugin's name, and each check it
registers, must match its grammar whole: a name ending in a newline is refused. The
``name`` and the ``generate`` of the backend a ``backend`` hook returns are read once, as
plugin code, and one that raises is a failure of that hook. What no part of this names ends
``ddd`` at exit code ``2`` with one line, ``ddd: unexpected`` and the type, and never at ``1``.

A hook, and the backend a ``backend`` hook returns, runs with ``sys.stdout`` bound to
``sys.stderr``, and so does everything else of the plugin's that DDD runs: the module while it
is imported, so a ``print`` at the top of it, or a banner an imported library prints, is
caught; every validation against, and copy of, one of its models, so a ``print`` in a
``@field_validator`` or a ``@model_validator`` is too; and the rendering of their schema by
``ddd schema --plugin``. Standard output is a document wherever DDD writes one there - the
``--format json`` report, the dictionary ``ddd dump`` prints, the list ``ddd sources`` prints,
the json-rpc wire of the language server - and ``ddd dump -o`` promises it empty, so a
``print`` left in a plugin would otherwise be read as part of one of them and a build's
``json.loads`` would fail on it. It is redirected rather than silenced: what a plugin prints is
still its author's to read, on the stream every other word DDD says about a run goes to. A
plugin that wants to write a file of its own writes one; a plugin that wants to be quiet prints
nothing.

What is redirected is ``sys.stdout``: a ``print``, and anything else that writes to it. Three
things reach standard output all the same, inside a document or, under ``ddd lsp``, between two
messages of the wire, and are the plugin's to keep off it: a child process that inherits the
descriptor (``subprocess.run(...)`` without ``capture_output=True`` or a ``stdout=`` of its
own), a write to the descriptor itself (``os.write(1, ...)``), and a write to the interpreter's
own handle (``sys.__stdout__``).

Two more things are worth knowing. Under ``ddd dump --format json`` the findings document goes
to standard error, as the dictionary takes standard output, so what a hook prints shares
standard error with it, ahead of the document, and a consumer reading the findings from there
has to keep a plugin from printing. And the redirect is the interpreter's: ``sys.stdout`` is
bound for every thread of the process while the plugin's code runs, not only the one running
it, so a thread that writes to ``sys.stdout`` meanwhile - a thread of the plugin's own, or
``ddd gui``'s - writes to standard error for as long as that lasts.

The models are the one place where raising is part of the contract. A ``@field_validator`` on
``object_model`` or ``project_model`` runs on every block written against it, and the
``ValueError`` or ``AssertionError`` pydantic turns into a ``ValidationError`` is how a model
refuses a block: that verdict is a ``schema`` finding on the reader's file, located at the
failing key. Anything else the model raises is the plugin's own defect and is reported the way
a hook's is - one line naming the plugin, exit 2, ``plugin-invalid`` in the language server and
beside the listing of ``ddd sources`` and ``ddd artefacts``, which exit 0.

Writing a well-behaved plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every identifier a hook reports belongs in ``checks``: an undeclared one resolves to a fixed
``unknown check`` error and cannot be overridden, the same as a typo in a built-in check's
name. Keep the module itself stateless - it is imported once per process and reused across
every project and every run of the language server, so anything it accumulates in a global
leaks between projects that have nothing to do with each other; editing the plugin file only
takes effect the next time a process starts. ``ddd gui`` says so, with ``plugin-changed`` on
the file of a plugin named by its path that changed since it imported it, until it is
restarted or the file holds the bytes it was imported from again; a module a plugin imports is
not watched, and a plugin named as a module is not compared, so editing either takes a restart
unsaid. A ``.py`` plugin is one module, loaded from the
location the project names rather than imported as part of a package: it has no package of
its own, so ``from . import helper`` is "attempted relative import with no known parent
package", and a plain ``import helper`` is resolved against ``sys.path`` like any other
import, finding the file next to the plugin only where the environment would have found it
from anywhere else too. Code shared between plugins belongs in a package the environment can
import, which a project names by its dotted spelling. ``GeneratedFile``, what a ``backend``
hook returns from ``generate``, is imported from ``ddd.backends``. A block read back from an
older dump may predate a field the plugin added since - ``model_validate`` fills it from the
model's default if there is one, and raises otherwise - and what to do about that gap is the
plugin's own decision, not one the api makes for it.

Naming a plugin runs it. That is true of every ``ddd`` command on the project, and of the
language server, which runs the plugins of every project it analyses when a file is opened
or saved; the :doc:`editor page <editor_integration>` says what that means for a repository
you did not write, and why the server will not run there until you trust the workspace. It
is true of the cmake integration too: ``ddd_generate()`` runs ``ddd`` at configure time, so
the plugins a project names are imported when CMake runs, not only when the generation does
(see :doc:`build_integration`). Only ``--no-plugins`` runs none, on ``ddd check``, ``ddd
list``, ``ddd dump``, ``ddd sources`` and ``ddd compare``, both sides of a comparison alike, and
on ``ddd lsp``, at every read the server makes: no module a description names is imported,
each entry naming one is reported as
``plugin-skipped``, a warning, and its blocks are carried into the dictionary as written,
neither validated nor reported as ``unknown-extension``. ``ddd generate``, ``ddd artefacts``
and ``ddd gui`` do not take it, each running what the project names as a build does.

The templates a run renders from are code in the same sense, and easier to overlook because
a template looks like data: they are jinja2, rendered in an ordinary unsandboxed
environment, so ``-t`` names a directory whose contents run with the privileges of the run.
:doc:`templates` says so beside the rest of what a template directory decides. Review one
the way you review a plugin.

What the dictionary carries
---------------------------

Every block reaches the dictionary in resolved form - validated and dumped back with its
defaults filled in - under ``extensions`` on the object and on the dictionary itself, and the
dictionary records the names of the plugins in play under ``plugins``. That is what keeps a
plugin's questions answerable across releases: the archived dump of the previous delivery is
the database, and ``ddd compare`` is the query. A leaf of a structured variable carries no
block; its instance carries one for the whole structure, and a plugin reaches it through the
leaf's ``instance``. The c templates receive the block on every object view, so a table the
project derives from a block renders from its own templates without a hook.

A model reads back its own dump. A block is dumped with ``model_dump(mode="json",
by_alias=True, round_trip=True)``: a field with an alias is keyed by it, as the file and the
published schema key it, and ``round_trip`` leaves every ``@computed_field`` out and writes a
``Json`` field back as json text, so that a model forbidding extra keys reads the dump of a
block as it read the block. A hook reading a block itself - ``Entry.model_validate(block)``, as
the worked example does - reads it by alias, as the loader reads a file.

Over a project, the settings a hook is handed are never read back from the dictionary:
``settings`` is validated from the block the project states, once, while the files are read:
the dictionary's dump of the settings is written from that instance, and every hook of the run
is handed a shallow copy of it (``model_copy()``), so a default drawn afresh at each
validation - a time, a uuid - is drawn once. A hook should not change its settings: a field it
assigns is its own copy's, but a value it changes in place - a list it appends to - is the
instance's, and the hooks after it see the change, as does every comparison ``ddd gui`` runs
over the revision while the revision stands. Only an archived dictionary, under
``ddd compare --plugin``, has its settings validated from the block it carries. A model whose
dump does not read back as its block did is handed its settings in full over a project, and
fails or differs wherever its dump is read: in a hook reading a block from the dictionary, and
in the settings of an archived dictionary. One that cannot validate its own dump fails there,
the settings of an archive a usage error naming the plugin: one requiring a field its dump
leaves out (``Field(exclude=True)``), one with a ``strict`` enum or date, which the dump
writes as a string, one whose serializer changes the shape of a value, and one whose validator
refuses what it hands back. One whose dump validates into another value - its validator
changes what it is given, and takes what it handed back - reads a value nobody stated, and
fails nothing.

The editor
----------

``ddd schema component --plugin tools/ddd_layout.py -o schemas/ddd_component.schema.json``
publishes the schema with the ``extensions`` property closed over the plugin's model, and
likewise for ``project``; commit those files and point the ``$schema`` key of each
description at them, and the editor validates a block as it is typed. The dictionary schema
stays open, a dump being a produced document. ``ddd checks --plugin`` lists a plugin's checks
after the built-in ones.

A worked example
----------------

``examples/plugins/ddd_layout.py`` stamps an object with a key and a version and ties the
version to the layout; ``examples/layout`` is a project that names it. It exercises every part
of the api described above with a rule set small enough to read in one sitting, and is meant
to be copied and rewritten rather than reused.
