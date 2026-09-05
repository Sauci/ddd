# Changelog

Notable changes per release, newest first.  Versions follow
[semantic versioning](https://semver.org): while the major version is `0`, a minor bump may
change the file formats, and this file says how.

The check identifiers, the command names and the json file formats are the tool's public
interface; anything else - the layout of the generated c, the wording of a diagnostic - is
not, and the templates a project provides are its own.

## Unreleased

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
