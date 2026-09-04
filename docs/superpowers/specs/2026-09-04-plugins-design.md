# Plugins

- **Date:** 2026-09-04
- **Status:** approved design, not yet implemented
- **Touches:** the models, the loader, the analysis, the data dictionary, the diagnostics,
  the comparison, the generation, the cli, the language server, the published schemas

## 1 What this adds

DDD is generic on purpose: it knows what a global variable is, who produces it, who reads it
and what the generated c and a2l need to say about it, and nothing else. A project that runs
on a target with a non-volatile memory manager needs one more thing per variable - a 16 bit
storage id and a layout version, with a rule that the version moves whenever the layout does -
and that thing is true of that project and of no other. Building it into DDD would make every
project carry keys it cannot use, and the next project's addition would do the same again.

This design lets a project extend DDD with what only it needs, without DDD learning it:

- a project names its **plugins**, python modules the project ships or installs;
- a plugin owns one **extension block**, a json object under `"extensions"` on a data object
  definition and on the project, validated against a pydantic model the plugin declares;
- a plugin contributes **checks**, findings on the resolved dictionary reported and policed
  like the built-in ones; **comparison rules**, findings between a baseline and a candidate;
  and a **backend**, an output of its own under `ddd generate`;
- the dictionary carries every block in resolved form and records which plugins interpreted
  it, so an archived dump keeps every question a plugin can ask answerable across releases.

The mechanism is the deliverable. The first plugin, for non-volatile memory, ships as an
example so that the api has a real consumer the test suite exercises, and the documentation
describes the api rather than that plugin.

## 2 Out of scope

- **Blocks on components, type members, sections, rasters, units and constants.** A
  definition and the project are the two places the case in hand needs; every other model
  stays closed and opens when a plugin needs it, one at a time ([section 14](#14-deferred)).
- **Blocks stated by a consumer.** Only a producing declaration may state one
  ([section 4.2](#42-who-may-state-a-block)), so there is never a second block for one object
  to disagree with.
- **Discovery through entry points.** A plugin acts on a project because the project names
  it, never because it happens to be installed. An installed distribution is named by its
  module name; nothing scans the environment.
- **A plugin api version.** DDD is `0.x` and the plugin contract is the `Plugin` dataclass
  and the context objects of [section 3](#3-the-plugin-object), documented like the file
  formats and versioned by the changelog with them.
- **A plugin that changes the dictionary.** A plugin reports; it never adds, removes or edits
  an object. A dictionary that depended on which plugins were installed would make two dumps
  incomparable.
- **Reading a block without its plugin.** DDD can carry a block it does not understand only
  where the project relaxes `unknown-extension` ([section 4.3](#43-validation)); that is the
  documented escape hatch, not a mode.

## 3 The plugin object

### 3.1 The module

A plugin is a python module exposing a module level name `PLUGIN`, an instance of the frozen
dataclass `ddd.plugins.Plugin`:

```python
from ddd.plugins import Plugin, CheckContext, CompareContext, GenerateContext

PLUGIN = Plugin(
    name="nvm",
    object_model=NvmEntry,          # pydantic model of the block on a definition, or None
    project_model=NvmSettings,      # pydantic model of the block on the project, or None
    checks=(...),                   # CheckInfo entries, every identifier prefixed "nvm/"
    check=check,                    # Callable[[CheckContext], None] or None
    compare=compare,                # Callable[[CompareContext], None] or None
    backend=backend,                # Callable[[GenerateContext], Backend] or None
)
```

`name` matches `^[a-z][a-z0-9_]*$` and is the extension key: the block of this plugin is
`"extensions": {"nvm": {...}}`. Every hook is optional, and so is each model; a plugin with
neither model states no block and only contributes hooks.

The models are ordinary pydantic models, which is what lets DDD validate a block without
knowing its shape and publish its schema with the generator it already has
([section 9.1](#91-ddd-schema)). The example forbids extra keys, so that a typo inside a
block is refused where it is typed; DDD recommends that and the documentation says why, but
does not enforce it - a plugin that wants an open block is entitled to one.

### 3.2 The contexts

A hook receives one context object rather than positional arguments, so the api can grow a
field without breaking a plugin written against the previous one:

| context | fields |
| --- | --- |
| `CheckContext` | `dictionary`, `settings`, `bag`, `locate` |
| `CompareContext` | `baseline`, `candidate`, `settings`, `bag`, `locate` |
| `GenerateContext` | `settings`, `generator` |

`settings` is the project block validated against `project_model`: an instance of that model,
built from `{}` when the project states no block so that defaults apply, and `None` for a
plugin that declares no project model. A project model with a required field and no block in
the project is a `schema` finding at `project.extensions.<name>` saying the plugin requires
settings.

`bag` is the ordinary `DiagnosticBag`; a hook reports with `bag.add("nvm/duplicate-id",
message, location, notes)`, exactly as the built-in checks do, and the severity policy of the
run applies ([section 6.1](#61-registration-and-policy)).

`locate(name)` returns a `Location` for a finding about the object or instance `name`, or
`None` when nothing answers to it. Under `ddd check` the loader is still at hand, so the
location is the producing declaration, `component_a.ddd.json#component.interface[3]`; from
an archived dump it is the dump file, because a dump records a component's file name and not
the position of each declaration. A plugin never has to know which it got.

`generator` is the tool name and version the built-in backends put into their banners.

### 3.3 Loading

A project names a plugin in one of two spellings. A string ending in `.py` is a path relative
to the project file that names it, the way `includes` and the template directory are
relative; anything else is a dotted module name imported from the environment. The first is
the project that keeps its plugin in its own repository, the second is one that installs a
shared plugin as a distribution. Loading uses `importlib` alone, so the runtime dependencies
stay pydantic and jinja2.

Failures are errors with fixed severity, like `file-not-found` and `schema`, because a project
cannot be interpreted without the plugins it names:

- `plugin-not-found`: the path does not exist, or the module name does not import because
  nothing provides it.
- `plugin-invalid`: the module raises on import, exposes no `PLUGIN`, exposes one that is not
  a `Plugin`, or exposes one whose `name` is malformed, whose check identifiers are not all
  prefixed with its own name, or whose check identifiers collide with each other. Two plugins claiming one name is `plugin-invalid` on the second, with a note
  at the first; the same module named twice, by two project files or in two spellings that
  resolve to one file, is loaded once and is not a finding.

A hook that raises is a defect of the plugin, not a finding about the project. The exception
propagates wrapped with the plugin's name and the hook it was in, and the cli reports it as a
usage error the way it reports a template that does not render: one line, exit code 2, and no
half-written output.

## 4 The files

### 4.1 The keys

The project file gains two keys:

```json
{
  "project": {
    "name": "engine",
    "includes": ["components/*.ddd.json"],
    "plugins": ["tools/ddd_nvm.py"],
    "extensions": { "nvm": { "max_id": 4095 } }
  }
}
```

`plugins` is a list of module spellings ([section 3.3](#33-loading)), each non-empty. A
sub-project may name plugins too, and the set in play is the union: a plugin a sub-project
brings applies to the whole project, because the blocks it interprets may sit in any
component. `extensions` maps a plugin name to an object.

A data object definition gains `extensions` with the same shape, on every kind, and therefore
on an instance of a declared type, which is a definition like any other:

```json
{
  "name": "EngineHours",
  "scope": "output",
  "kind": "parameter",
  "datatype": "uint32",
  "section": ".nvm",
  "extensions": { "nvm": { "id": 12, "version": 3 } }
}
```

The built-in schema publishes both keys as open: a mapping whose values are objects. What
closes them is the plugin's model, at validation and in a schema published for the project's
plugins ([section 9.1](#91-ddd-schema)).

### 4.2 Who may state a block

Only a producing declaration - scope `output` or `local` - may state `extensions` on a
definition. An `input` stating one is `consumer-extension`, an error, on the reasoning
`consumer-storage` applies to `section` and `init` and `consumer-identity` applies to `id`: a
block says something about what the object *is*, and a component that only reads it has no
claim over that. The finding is reported where the block is written.

This is also what keeps `definition-mismatch` out of it. That check compares a consumer's
definition with the producer's on the fields both may state; a block is never stated twice
for one object, so there is nothing to compare and no agreement rule to write.

### 4.3 Validation

Reading a file does not change: pydantic validates it with `extensions` as an open mapping,
and the file is a `schema` finding on any other problem exactly as today. The plugins are then
imported - the root project's when it is read, a sub-project's when it is - and, once every
file is in, a final pass validates each block against the model of the plugin that owns it. A
pass at the end rather than at each file, because a component included before the
sub-project that names its plugin would otherwise be refused for a block that is about to
become valid.

A block that fails its model is a `schema` finding, at the pointer of the failing key inside
the block - `component.interface[3].definition.extensions.nvm.id` - reported through the same
path pydantic errors on the built-in keys take, so that an editor underlines the value and not
the definition.

A block naming no loaded plugin is `unknown-extension`, an error. It is overridable, and
relaxing it is how a project deliberately carries a block that no installed plugin interprets:
the block then reaches the dictionary as written, un-validated, and every hook ignores it.
The check is flagged as *needing every component*, on the reasoning that flag exists for: it
concludes from an absence. The language server's standalone mode reads one component with no
project above it, sees no plugin list, and would otherwise report every block in the file as
unknown for no better reason than what it was not shown.

## 5 The dictionary

`ResolvedObject`, `ResolvedInstance` and `DataDictionary` gain `extensions`, a mapping from
plugin name to the block in **resolved form**: the validated model dumped back to json, with
defaults filled in, keys sorted by plugin name. Resolved rather than as written, because
everything else in the dictionary is resolved - limits derived, rasters resolved, dimensions
counted - and because two dumps then compare on one shape even when a plugin has since added
a field with a default. A block carried under a relaxed `unknown-extension` is the one
exception, and is carried as written because nothing can resolve it.

A leaf carries no block, the way it carries no `id` of its own. The case in hand stamps a
structured variable as a whole - one storage id, one version - and a plugin that needs the
block of a leaf's instance finds it under `instance`.

`DataDictionary.plugins` records the names of the plugins in play, sorted, so that a reader
of a dump knows what interpreted it, and so that a comparison can say when a rule did not run
([section 7.2](#72-a-plugin-this-run-has-not-loaded)). Names rather than module spellings: a
path is relative to a project file the dump no longer has, and the name is what the blocks
are keyed by.

`DICTIONARY_FORMAT` goes from 6 to 7. A dump of format 6 or older loads with every
`extensions` empty and `plugins` empty, which a compare hook is told nothing beyond: an
absence in an older baseline is not a difference, the rule the id pairing and the deferred
shape comparison already apply to a silence.

The templates receive the blocks through the model view they already get, so a project whose
c carries a table derived from a block renders it from its own templates and no hook is
needed for that. The example templates are untouched.

## 6 Checks

### 6.1 Registration and policy

A plugin's `CheckInfo` entries are registered on the diagnostic bag when the plugin is
loaded, and from then on `bag.add` resolves them as it resolves a built-in check: default
severity, `-W nvm/version-not-bumped=warning`, `--strict`, `ignore`. `CHECKS` stays the
registry of the built-in checks and is not mutated; the bag carries the plugin's entries next
to it, so two runs in one process - the language server checking two projects with different
plugins - cannot leak a check from one into the other.

The severity policy is parsed before any file is read, which is before any plugin is known.
An override naming a check with a slash in it is therefore accepted provisionally, and every
provisional override is verified once loading is done: one that no loaded plugin registered is
a usage error, the same outcome an unknown built-in check gets today, reported the same way.

A plugin check identifier is `<name>/<check>`, where `<check>` follows the grammar of the
built-in identifiers. The prefix is what makes the namespace: a plugin cannot shadow a
built-in check and two plugins cannot collide, and a policy file that targets `nvm/...` reads
as what it is.

### 6.2 When the hooks run

`analyze` runs every check hook at its end, over the dictionary it built, in the order the
project lists the plugins. Inside `analyze` rather than beside it, so that nothing that
analyses a project - `ddd check`, `generate`, `list`, `dump`, the language server, a test
calling `analyze` directly - can forget to. A hook sees the whole dictionary and every
built-in finding is already in the bag.

## 7 Comparison

### 7.1 The hooks

`compare` runs every compare hook after the built-in comparison, for the plugins in play, in
project order. The baseline is whatever `ddd compare` was given as a baseline, resolved to a
dictionary as today, and the hook is told nothing about which it was.

The plugins in play are the candidate's. When the candidate is a project description, they are
the ones it names and nothing else; `--plugin` beside a project description is a usage error,
because a project's interpretation must not depend on the command line. When the candidate is
an archived dump, nothing names them, and `ddd compare --plugin SPEC` loads them, repeatable,
in the spellings of [section 3.3](#33-loading) with a path relative to the working directory.
`settings` for a hook running over a dump is rebuilt from the dump's project block, which is
why the dictionary carries it.

### 7.2 A plugin this run has not loaded

Either dictionary may record a plugin that this run has not loaded - a dump made with a plugin
the project has since dropped, or a run over two dumps without `--plugin`. That is
`missing-plugin`, a warning, once per plugin and side: `the baseline was produced with plugin
'nvm', which this run has not loaded; its comparison rules did not run`. A comparison that
silently skipped a rule would be a confident "can replace" with a hole in it, and the finding
is what closes the hole.

## 8 Generation

A plugin's `backend` hook returns an object satisfying the existing `Backend` protocol. It is
selected as `ddd generate <name>`, next to `c`, `a2l` and `all`, and takes the common
generation options - `-o`, `--dry-run`, `--force` - and neither the template directory nor
the address map, which belong to the built-in artefacts. `all` stays the built-in pair and
does not run plugin backends: a plugin's output is asked for by name, the way the a2l is
asked for after linking.

The backend runs under the existing `render` and `write`, so two artefacts claiming one path
are refused between a plugin and the c backend exactly as between the c and a2l backends, and
`--dry-run` and the write statuses behave the same. The artefact names of a run are known
only once the project is read, so the plugin artefacts are validated after argument parsing:
`ddd generate nvm` on a project naming no such plugin is a usage error naming the plugins the
project does have.

## 9 Tool interface

### 9.1 `ddd schema`

`ddd schema <kind> --plugin SPEC` publishes the schema of a kind with the plugins' models
merged in: on `component` and `project`, the `extensions` property gains one property per
plugin, holding that plugin's model schema rendered through the same generator that
documents the built-in models, and closes over them with `additionalProperties: false`. A
project commits those files and points its descriptions at them, and its editor validates a
block as it is typed. Without `--plugin` the property stays open, as
[section 4.1](#41-the-keys) says. The `dictionary` schema stays open in every case: a dump
is a produced document and its reader is not typing into it.

### 9.2 `ddd checks`

`ddd checks --plugin SPEC` lists the plugins' checks after the built-in ones, in both
formats, with the same columns.

### 9.3 Built-in checks added

| check | severity | reported when | overridable | needs every component |
| --- | --- | --- | --- | --- |
| `plugin-not-found` | error | a project names a plugin that cannot be found | no | no |
| `plugin-invalid` | error | a plugin module does not expose a well formed `PLUGIN` | no | no |
| `unknown-extension` | error | a block names a plugin the project does not load | yes | yes |
| `consumer-extension` | error | a declaration that reads a variable states a block | yes | no |
| `missing-plugin` | warning | a compared dictionary records a plugin this run has not loaded | yes | n/a |

## 10 The example plugin

`examples/plugins/ddd_nvm.py`, name `nvm`, and a project under `examples/nvm/` that names it,
which the tests load. It exists to exercise every part of the api with a real rule set; the
documentation points at it and does not describe its rules.

### 10.1 Its blocks

On a definition, `{"id": 0..65535, "version": >= 1}`, both required, extra keys forbidden. On
the project, `{"max_id": 0..65535}`, defaulting to 65535, so that a project reserves the top
of the range for its memory manager. The default is what exercises settings built from `{}`.

### 10.2 Its checks

Within one dictionary:

- `nvm/duplicate-id`, error: two objects carry one storage id.
- `nvm/id-out-of-range`, error: a storage id is above `max_id`.

Between two deliveries, entries paired on the storage id, and objects paired on the DDD `id`
where both sides state one:

- `nvm/version-not-bumped`, error: same storage id on both sides, the layout changed, and the
  version did not increase. The layout is kind, datatype or type, shape, unit and conversion,
  the set `changed-interface` compares; for a structured variable it is the layout of its
  leaves.
- `nvm/needless-version`, warning: the version changed while the layout did not.
- `nvm/reused-id`, error: a storage id on both sides now belongs to a different object, told
  apart by the DDD `id` when both sides state one and by name otherwise.
- `nvm/id-changed`, error: one object, paired by DDD `id`, carries a different storage id, so
  its stored entry would be orphaned and a fresh one created.
- `nvm/removed-entry`, warning: a storage id of the baseline is gone, and the object that
  carried it was not reported as `nvm/id-changed`.

### 10.3 Its backend

`ddd generate nvm -o DIR` writes `ddd_nvm.h`, one table entry per stamped object sorted by
storage id - id, version, size and symbol - rendered by plain string building. The point is to
exercise the hook, not to propose a c style, and the file it writes is one the example c
templates do not, so the path collision the tests provoke uses a template added for that test.

## 11 Testing

- `tests/test_plugins.py` - the mechanism. Loading by path and by module name; not found;
  invalid, one case per reason of [section 3.3](#33-loading); two plugins with one name; the
  same module named twice; a block validated at the pointer of its failing key;
  `unknown-extension`, and the block carried as written when it is relaxed;
  `consumer-extension`; a block on an instance; resolved blocks and the plugin list in the
  dump; a format 6 baseline loading with empty blocks; a provisional override for a prefixed
  check and the usage error for one no plugin registered; a hook's finding under `-W` and
  `--strict`; the check hook reached through `ddd check` and through the language server; a
  hook that raises, reported as a usage error naming the plugin and the hook; `--plugin` on
  compare with a dump candidate, refused beside a project candidate; `missing-plugin` on each
  side; `ddd generate <name>`, its path collision with the c backend, and the usage error for
  a name no plugin provides; `ddd schema --plugin` merging and closing the property;
  `ddd checks --plugin`.
- `tests/test_nvm_plugin.py` - the rule matrix of [section 10.2](#102-its-checks), each rule
  with the case that fires it and the nearest case that does not, and the header the backend
  writes.
- `tests/test_backends.py` - the layering gains a row: `plugins.py` imports no backend, no
  loader and no analysis. The `Backend` protocol is structural, so the plugin module types its
  hook against it under `TYPE_CHECKING` and imports nothing from `backends` at runtime.
- `tests/test_documentation.py` passes without amendment only if the five checks of
  [section 9.3](#93-built-in-checks-added) are named in both `README.md` and `SPEC.md`, which
  [section 12](#12-documentation) is.
- `tests/test_comparison_tables.py` - a recorded decision that `extensions` is in **neither**
  comparison table: a block is a plugin's to compare, and putting it in `_INTERFACE_FIELDS`
  would turn the commit that stamps a project into a `changed-interface` on every object.
- The committed `schemas/*.schema.json` are regenerated, and the existing test that they
  match `ddd schema` keeps them honest.

## 12 Documentation

- `SPEC.md` gains section 3.11, plugins: the keys, who may state a block, validation, the
  plugin object and its hooks, the dictionary, and the tool interface; section 4 gains the
  four checks and section 4.1 `missing-plugin`; section 7 gains `--plugin` and
  `generate <name>`.
- `README.md` gains the five check rows, `--plugin` and `generate <name>` where the commands
  are listed, and a short paragraph under the file formats saying what `plugins` and
  `extensions` are, pointing at the documentation page.
- `docs/plugins.rst`, new: what a plugin is and is not, the two keys, the `Plugin` dataclass
  and the three contexts field by field, the check identifier convention, loading and its
  failures, the resolved form in the dictionary, the comparison over dumps and
  `missing-plugin`, publishing schemas for a project's plugins, and a pointer at
  `examples/plugins/ddd_nvm.py` as the worked example. It documents the api and not the
  example's rules.
- `docs/data_dictionary.rst` - `extensions`, `plugins`, format 7.
- `docs/command_line_interface.rst` - `--plugin` on `schema`, `checks` and `compare`;
  `generate <name>`.
- `docs/consistency_checks.rst` - the five checks, and a paragraph on plugin check
  identifiers under the severity policy.
- `docs/developer_documentation.rst` - the layering table gains `plugins.py`.
- `CHANGELOG.md` records format 7, the two keys, the five checks, the api, and that an
  existing project migrates at no cost: no key is required, no id or block is stamped.

## 13 Increments

1. **The record** - `plugins` and `extensions` on the project, `extensions` on a definition,
   `ddd.plugins` with the `Plugin` dataclass, loading, block validation, the four in-project
   checks of [section 9.3](#93-built-in-checks-added), format 7, `ddd schema --plugin`. Useful
   alone: a project's blocks are validated and published, and reach the templates.
2. **The hooks** - registration and the provisional policy, the check hook inside `analyze`,
   the compare hook with `--plugin` and `missing-plugin`, `ddd generate <name>`,
   `ddd checks --plugin`.
3. **The example and the page** - `ddd_nvm.py`, `examples/nvm/`, its tests, `docs/plugins.rst`
   and the rest of [section 12](#12-documentation).

## 14 Deferred

- **Blocks on the other models.** A component, a type member, a section or a raster opens to
  `extensions` when a plugin needs it, each with its own "who may state it" rule; a member's
  block would in particular raise the question of whether it belongs to the type or to each
  instance, which the leaf rule of [section 5](#5-the-dictionary) deliberately does not answer.
- **Blocks stated by a consumer.** A plugin that wants to know what a reader needs of an
  object - a rate, a staleness bound - needs a block on an `input` and an agreement rule
  beside `definition-mismatch`. Wait for the plugin.
- **A block on a leaf.** The instance carries one for the whole structure; a per-member
  stamp waits for a memory manager that stores members separately.
- **Entry point discovery.** Naming a plugin is deliberate ([section 2](#2-out-of-scope)); an
  installed plugin that acts on every project without being named is a different design.
- **Plugin backends under `all`.** Asked for by name until a project wants them in the
  default run.
- **Language server features for a block.** Hover and completion come from the published
  schema already; a code action a plugin contributes is a second api and waits for a case.
- **Positions in the dictionary.** A dump records a component's file name and not each
  declaration's pointer, which is why `locate` is file-level from a dump. Recording the
  pointer would sharpen a finding from a dump and would also make the dump depend on the
  layout of the files it came from; wait for someone to need it.
