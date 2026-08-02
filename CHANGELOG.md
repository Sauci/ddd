# Changelog

Notable changes per release, newest first.  Versions follow
[semantic versioning](https://semver.org): while the major version is `0`, a minor bump may
change the file formats, and this file says how.

The check identifiers, the command names and the json file formats are the tool's public
interface; anything else - the layout of the generated c, the wording of a diagnostic - is
not, and the templates a project provides are its own.

## Unreleased

### Structured datatypes, first part

A new description file kind, `types`, declares structures that a project shares between its
components.  A member is a `value` (a datatype, optionally an array), a `bits` (a c bitfield) or
a `struct` (another declared structure), and each shape carries only the keys it needs:

```json
{ "types": [ { "name": "Status_t", "members": [
  { "name": "ready", "member": "bits", "kind": "measurement", "datatype": "uint16", "bits": 1 }
] } ] }
```

The file is listed in the `includes` of a project, `ddd schema types` publishes its schema, and
`examples/structures` is a working one.  Three checks come with it: `duplicate-type`,
`unknown-type` and `type-cycle`.

A member states no bit position and no offset, and never will: c leaves both to the compiler, so
DDD will read the real layout back out of the build rather than predict it.

**Not yet available**: referring to a structure from a component declaration, so no variable has
one yet, and nothing structured reaches the generated c or the a2l.  When it does, a structure
will be flattened into one a2l object per member rather than described as an a2l structure -
CANape 15 accepts the native `TYPEDEF_STRUCTURE` form and then displays nothing for it, which is
recorded under "what the calibration tools actually implement" in the developer documentation.

### `ddd lsp`: the checks, in the editor

A language server, speaking the Language Server Protocol on stdin and stdout.  It reports the
consistency checks while a description file is being written - which a json schema cannot do,
being per file and static: whether an `axis` names a declared axis, whether exactly one
component produces a name, whether two components agree on a unit, whether a name follows the
convention.

It navigates as well.  Go to definition on an `input` - or on an `axis`, `x_axis`, `y_axis` or
`input` reference - lands on the declaration that writes it, in whichever component that turns
out to be; find references lists every declaration of it.  The same works from a `type` to the
structure it nests and back, and from an `includes` entry or a project's `naming` to the files
they name, wildcards included.

It reports on open and on save, and publishes for every file of a project rather than only the
one on screen, because half of a disagreement is always in the other component.  Which project
a file belongs to is read from the `ddd-build.json` below, so the editor applies the severities
the build applies; a file no build claims is checked on its own with `missing-producer`
silenced.  Editors that launch a server themselves need nothing further, and `-b DIR` points at
an out-of-tree build.

No new dependency: the protocol framing is a hundred lines and DDD still installs with
pydantic and jinja2 alone.

A VS Code extension comes with it, in `editors/vscode`, because VS Code cannot start a language
server without one.  It is a launcher and deliberately nothing more - two settings, one restart
command - so an editor that starts servers itself needs none of it.

It is **not published to the marketplace**.  Every release attaches a `ddd-<version>.vsix` to
its GitHub release, installable with `code --install-extension ddd-<version>.vsix` or through
"Install from VSIX…" in the Extensions view.  There is no automatic update for an extension
that did not come from the marketplace, so reinstall it when you upgrade the python package.

### `ddd build-info`, so a build can tell an editor what it does

A new command, and a `ddd-build.json` that `ddd_generate()` now writes into its output
directory at configure time.  It records the two things no description file can state: which
project description this image is generated from, and the severity policy it is generated
under.

Without `PROJECT`, the project description is collected out of the c link graph and written
into the build tree, so nothing in the source tree names it - which means a tool reading only
`*.ddd.json` cannot work out which components belong together.  Nothing in the build reads the
new file; it exists so that an editor can report what the build reports, the same bargain
`SCHEMA_DIRECTORY` already makes for the json schemas.

A `SEVERITY` naming a check that does not exist is now refused while the project is being
configured, rather than when the build later runs the check.

### The published schemas carry their documentation

`ddd schema` writes the same contract as before - nothing it publishes accepts or rejects a
file it did not accept or reject previously - and a lot more of what an editor can show while a
description file is being written:

* every key of every format now has a description, including the 27 in the dictionary and
  naming schemas that used to hover blank;
* every value of a closed set has one too.  `uint16` says how much storage it costs and which
  values fit in it, `"kind": "curve"` says what a curve is as against a value block.  The text
  is both spelled out in the description of the key and repeated in `enumDescriptions`, the
  array VS Code reads to document each entry of the completion dropdown;
* each file states its dialect, `https://json-schema.org/draft/2020-12/schema`, so a validator
  no longer has to guess which version of json schema it is reading, and is titled for the
  format it describes rather than for the python class behind it;
* descriptions are rendered as the markdown an editor shows, so a reference written for the api
  documentation no longer arrives as the literal characters `` :class:`Foo` `` or points a
  reader at a python module they do not have.

The rules that span several keys - which keys a `bits` member takes, that a segment has tokens
or a pattern and not both - are stated in the descriptions rather than as constraints, so a
validating editor still accepts a few files that `ddd check` rejects.

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
