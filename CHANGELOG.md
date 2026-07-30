# Changelog

Notable changes per release, newest first.  Versions follow
[semantic versioning](https://semver.org): while the major version is `0`, a minor bump may
change the file formats, and this file says how.

The check identifiers, the command names and the json file formats are the tool's public
interface; anything else - the layout of the generated c, the wording of a diagnostic - is
not, and the templates a project provides are its own.

## 0.2.0

Breaking changes to the description file format and to `ddd generate`.  Migrating an existing
project means editing its `*.ddd.json` files and its build integration; `ddd check` reports
every file that still needs it, so the migration is finished when the check is clean.

### The c templates now belong to the project

DDD no longer decides what the generated c looks like.  What used to be built in is shipped
as an example instead, and `ddd generate` requires the directory to render:

```bash
ddd templates-dir                      # prints a working set to copy
ddd generate project.ddd.json -o gen -t templates
```

Every `*.jinja2` in that directory renders to a file named like it without the extension, a
name starting with `_` is a helper that renders nothing, and a name containing `{component}`
renders once per component.  The templates therefore name the generated files, which is why
**`--prefix` is gone** - rename a template to rename its output.  In CMake, `PREFIX` is
replaced by a required `TEMPLATE_DIRECTORY`.

The a2l generator is unchanged and stays internal: ASAP2 is defined by ASAM, not by a project.

### `kind` is required on every definition

A definition no longer defaults to `measurement`; it states its kind, including a measurement:

```json
{ "kind": "measurement", "name": "ValueE", "datatype": "uint16" }
```

The default made a bare definition match two variants at once in the published json schema,
which an editor validating a file reported as an ambiguity.

### Datatypes are named without reference to c

| was | now |
| --- | --- |
| `bool` | `boolean` |
| `int8`, `int16`, `int32`, `int64` | `sint8`, `sint16`, `sint32`, `sint64` |

The unsigned and floating point names are unchanged.  The generated c and a2l are unaffected:
a `sint16` is still `int16_t` in c and `SWORD` in the a2l.

### Editor support

* a top level `$schema` key is accepted and ignored, so a description file can be bound to
  its schema; every other unknown key is still rejected as a typo,
* `ddd schema all -o DIR` writes every schema at once, for a project to commit,
* `ddd_generate(... SCHEMA_DIRECTORY <dir>)` writes them at configure time instead, so they
  cannot describe a version that is no longer installed,
* every field of every contract carries its documentation, so hovering a key explains it.

### Added

* `ddd sources FILE` lists every description file a project is built out of, which is what a
  build system needs to know when to run DDD again,
* `ddd templates-dir` prints the example templates,
* `-v` as a short form of `--version`,
* `name-collision`, `a2l-unrepresentable` and `project-mismatch` checks,
* archived dictionaries carry a `format` version, so a dump from a newer DDD is refused
  rather than misread,
* the documentation is published at <https://sauci.github.io/ddd/>, rebuilt from the sources
  on every change rather than written out by hand.

### Fixed

* **`MATRIX_DIM` was transposed.**  ASAP2 lists the fastest running index first, so a c array
  `[2][3]` is `MATRIX_DIM 3 2 1`; it was emitted in c order, and a calibration tool addressed
  the wrong element of every multi-dimensional object.
* **Names that would not compile passed the checks.**  Enum names, enumerator names and the
  identifiers `<stdint.h>` declares are now screened; enumerators of different enums, and an
  enumerator sharing a name with a variable, are reported as `name-collision`.
* `INT64_MIN` was emitted as a literal no c compiler accepts.
* A shell completion could execute code from somebody else's convention file.
* A legal name was rejected when a repeatable segment was followed by an optional one.
* `ddd sources` omitted a file it had read but rejected, so a build never noticed the fix.
* Descriptions and preprocessor conditions could break out of the comment they were written
  into; NaN, infinity, non-utf-8 files and several malformed inputs now produce a located
  finding instead of a traceback.
* `ddd check --baseline` reported the baseline's own findings as findings of the run.
* `ddd dump` writes only the dictionary to stdout, so `> baseline.json` archives it in both
  output formats.

## 0.1.0

First release.
