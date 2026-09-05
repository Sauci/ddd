# Plugins in the build

- **Date:** 2026-09-05
- **Status:** approved design, not yet implemented
- **Touches:** the cli (`generate`, `sources`), the loader, the CMake module, the
  specification and the pages that describe them

## 1 What this adds

Plugins arrived in 0.8.0 as the way a project extends DDD without DDD learning it: a project
names python modules, each owning an extension block, contributing checks and comparison
rules, and providing an artefact of its own under `ddd generate <name>`. The build
integration, which is how a real project runs DDD, cannot use any of it. The CMake module has
no notion of a plugin: the project description it generates carries a name, a description and
the file list, so a project that names plugins falls back to a hand-written file; the schemas
it writes for the editor are open over the extension blocks; and a plugin's artefact runs only
when somebody types its name, never as part of a build. `ddd sources` leaves the plugin modules
out, so a build does not know to run again when a plugin changes.

This design makes a plugin a first-class citizen of the build:

- `ddd generate all` produces every artefact the project has - the c sources, the a2l and the
  artefact of every plugin the project names that provides one;
- `ddd sources` lists the plugin modules beside the description files;
- `ddd_generate` takes `PLUGINS`, writes them into the project description it generates,
  closes the editor schemas over them, and depends on them.

Nothing changes for a project that names no plugin.

## 2 Out of scope

- A plugin's artefact under `ddd_generate` is produced but not declared as a build output,
  because its file names are the plugin's business and unknown at configure time. A target
  that consumes one depends on the generation target. Declaring them, for instance by asking
  the tool with `--dry-run --format json` at configure time, is deferred until a project
  needs it.
- Running CMake in continuous integration. The module is held to the specification by text
  pins, as it is today; the compose `cmake` service remains the place it is exercised.
- Any change to what a plugin is or exposes. `ddd.plugins.Plugin`, its hooks and its contexts
  are untouched.
- `ddd generate <name>` for a single plugin artefact, `ddd schema --plugin`, `ddd compare
  --plugin` and `ddd checks --plugin` stay exactly as they are.

## 3 `ddd generate all`

`all` means everything the project produces. After the c backend and the a2l backend, the run
appends the backend of every plugin the project names that provides one, in the order the
project names the plugins - the order the hooks already run in. Each backend receives the same
resolved dictionary and the same output directory; a plugin backend takes no option of its
own, so `-t`, `--const-inputs`, `--byte-order` and `--address-map` keep their meaning and
reach the built-in backends alone.

The artefacts go through the same rendering step as the built-in ones, which already refuses
two backends claiming one path before anything is written and names both; a plugin whose file
collides with a built-in file, or with another plugin's, is therefore refused the same way.
`--dry-run`, `--force`, the `wrote`/`unchanged` report and the `generated` list of
`--format json` cover the plugin files without distinction.

`ddd generate c` and `ddd generate a2l` do not run plugin backends: they name one built-in
artefact and produce that one. `ddd generate <name>` is unchanged.

## 4 `ddd sources`

The list a build system watches gains the file of every plugin module the project loaded: the
`.py` a path spelling names, resolved as the loader resolved it, or the file a dotted module
name imported from. The files join the same sorted list as the description files, in both
output formats - a build system wants one list, and a plugin's edit has to re-run the
generation exactly as a component's edit does. A module with no file, which only a namespace
package is, contributes nothing. A plugin that failed to load contributes nothing either: the
finding says why, and `ddd sources` stays tolerant of a project that does not check out, as it
is today.

The loader records the file when it loads the plugin, next to the spelling and the location it
already keeps, so that the workspace answers the question without importing anything twice.

## 5 The CMake module

### 5.1 `PLUGINS`

`ddd_generate(<image> ... PLUGINS <spec>...)` names the plugins of the collected project.
A spec ending in `.py` is a path: it is made absolute against the current source directory,
the way the `JSON` arguments of `ddd_add_component` are, and has to exist at configure time,
a missing one being a fatal error for the same reason a missing description is. Any other spec
is a dotted module name and passes through as written; the tool decides whether it imports.
The specs are written into the `plugins` array of the project description the module
generates, in the order given, so the project the tool reads is exactly what the build
declared. The path specs are added to the dependencies of the generation command, so that
editing a plugin regenerates.

In `PROJECT` mode `PLUGINS` is a fatal error: the hand-written file names its own plugins, and
two lists would be two sources of truth. The module reads that file's `plugins` array instead,
for the schemas below; a path in it is resolved against the directory of the project file, as
the tool resolves it.

### 5.2 The schemas

`SCHEMA_DIRECTORY` writes the schemas closed over the project's plugins: the module passes
`--plugin <spec>` to `ddd schema all` for each plugin it knows, from `PLUGINS` in collected
mode and from the project file in `PROJECT` mode. A path spec reaches the tool absolute, so
that the working directory of the configure step does not matter. A project with no plugins
gets the schemas it gets today.

### 5.3 Outputs and dependencies

The generation command is unchanged in what it declares: the outputs are the files the
templates name, as today, and a plugin's files are produced beside them without being declared.
The dependencies gain the plugin files, from `PLUGINS` in collected mode and through `ddd
sources` in `PROJECT` mode, where the module already asks the tool what the project is built
out of and now hears the plugins too.

## 6 Specification and pages

- `SPEC.md` 3.11 states that `ddd generate all` produces the plugins' artefacts after the
  built-in ones, in the order the project names the plugins, and that a colliding path is
  refused; 7 states that `ddd sources` lists the plugin modules; 7.1 states `PLUGINS`, the
  closed schemas, the undeclared outputs and the `PROJECT` mode rule. The three "not yet"
  clauses go.
- `docs/plugins.rst` says where a plugin's artefact appears and that a build gets it through
  `PLUGINS`.
- `docs/command_line_interface.rst` says what `all` produces, and `docs/build_integration.rst`
  gains the `PLUGINS` row, the schema sentence, the consumer's dependency and the `PROJECT`
  rule; its hand-written-project paragraph and the tutorial's paragraph stop saying that
  naming plugins forces a hand-written file.
- `README.md` names `PLUGINS` beside the other `ddd_generate` options it lists, and the
  changelog gains an entry under Unreleased.

## 7 Testing

- `tests/test_cli.py`: over `examples/layout`, `ddd generate all` writes the plugin's
  `ddd_layout.h` beside the built-in files and lists it in `--format json`; `ddd generate c`
  and `a2l` do not; a plugin backend producing a path a built-in backend produces is refused
  with both names; `ddd sources` lists the plugin file in both formats and stays silent about a
  plugin that failed to load.
- `tests/test_plugins.py`: the artefact ordering follows the project's plugin order when two
  plugins provide one.
- `tests/test_documentation.py`: every option `ddd_generate` parses has a row in the option
  table of the build page; the generated project template of the module carries `plugins`;
  the module passes `--plugin` to its schema step. The transcript and reference pins hold the
  pages as before.
- The docker `cmake` service remains the end-to-end check; the example `CMakeLists.txt` is
  left as it is, since the demo project declares no extension blocks for the example plugin
  to act on.

## 8 Increments

1. `ddd sources` lists the plugin modules (loader records the file; cli; tests; spec).
2. `ddd generate all` runs the plugin backends (cli; tests; spec; command page; plugins page).
3. The CMake module: `PLUGINS`, the generated project, the schemas, the dependencies, the
   `PROJECT` rule (module; text pins; build page; tutorial; readme; changelog).

Each increment leaves the suite green and the pages true.

## 9 Deferred

- Declaring a plugin's artefacts as build outputs.
- A plugin artefact selected per build (`PLUGIN_ARTEFACTS`), should a project ever want a
  plugin's checks without its files.
