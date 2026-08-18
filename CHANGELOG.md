# Changelog

Notable changes per release, newest first.  Versions follow
[semantic versioning](https://semver.org): while the major version is `0`, a minor bump may
change the file formats, and this file says how.

The check identifiers, the command names and the json file formats are the tool's public
interface; anything else - the layout of the generated c, the wording of a diagnostic - is
not, and the templates a project provides are its own.

## 0.0.1

Initial release.

DDD describes the global variables of a component based embedded software project in json
description files, checks that every component agrees on them, and generates the artefacts a
build and a calibration tool consume.

* **Six description file kinds.**  A *project* file names the components and the shared
  vocabularies of an image; a *component* file declares that component's data interface -
  measurements, parameters, curves, maps, axes and value blocks, each stating its `kind`,
  its storage (`datatype` or `typename`), its `conversion` and its `volatile` qualifier
  explicitly; a *types* file declares scalar types and structures a project shares by name;
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
