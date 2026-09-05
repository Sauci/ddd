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
``ddd sources`` lists each plugin's file beside the description files, so that a build re-runs
the generation when a plugin changes exactly as it does when a component does.

``extensions`` on the project holds each plugin's settings, keyed by the plugin's name and
validated against its project model with defaults filled in. A definition states its block
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
override naming one is accepted first and verified once the project is read; one that no
loaded plugin registered is a usage error, the same outcome an unknown built-in check gets.

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
       the project block validated against ``project_model`` (built from ``{}`` when the
       project states none, ``None`` for a plugin without one); ``bag``, the diagnostic bag;
       ``locate(name)``, where a finding about the object ``name`` belongs.
   * - ``CompareContext``
     - ``baseline`` and ``candidate``; ``settings``, the candidate's; ``bag``; ``locate``.
   * - ``GenerateContext``
     - ``settings``; ``generator``, the tool name and version the built-in backends put into
       their banners.

``check`` runs at the end of every analysis - ``ddd check``, ``generate``, ``list``,
``dump`` and the language server alike - over the whole dictionary, with every built-in
finding already in the bag. A hook reports with ``context.bag.add(check, message, location,
notes)``, exactly as a built-in check does. ``locate`` returns the producing declaration
under ``ddd check``, and the dump file when the dictionary was read back from an archive,
because a dump records a component's file name and not the position of each declaration.

``compare`` runs after the built-in comparison. The plugins in play are the candidate's: a
project description names its own, and an archived dump has ``ddd compare --plugin``. A
compared dictionary that records a plugin the run has not loaded is ``missing-plugin``, a
warning saying that plugin's rules did not run, so that a comparison can never silently skip
one.

``backend`` returns an object satisfying the ``Backend`` protocol - a ``name`` and a
``generate(dictionary, output_dir)`` returning ``GeneratedFile`` entries - and is selected as
``ddd generate <name>``, with the common options ``-o``, ``--dry-run`` and ``--force``. It
runs under the same writer as the built-in artefacts, so two artefacts claiming one path are
refused exactly as between the c and the a2l backends. ``all`` runs them after the built-in
pair, in the order the project names the plugins, so a build gets a plugin's artefact without
naming it.

A hook that raises is a defect of the plugin, not a finding about the project: the exception
is reported as a usage error naming the plugin and the hook, with exit code 2.

Writing a well-behaved plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every identifier a hook reports belongs in ``checks``: an undeclared one resolves to a fixed
``unknown check`` error and cannot be overridden, the same as a typo in a built-in check's
name. Keep the module itself stateless - it is imported once per process and reused across
every project and every run of the language server, so anything it accumulates in a global
leaks between projects that have nothing to do with each other; editing the plugin file only
takes effect the next time a process starts. ``GeneratedFile``, what a ``backend`` hook
returns from ``generate``, is imported from ``ddd.backends``. A block read back from an older
dump may predate a field the plugin added since - ``model_validate`` fills it from the
model's default if there is one, and raises otherwise - and what to do about that gap is the
plugin's own decision, not one the api makes for it.

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
