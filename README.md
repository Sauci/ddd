# DDD

![DDD](https://raw.githubusercontent.com/Sauci/ddd/master/assets/logo/ddd-icon-128.png)

DDD manages the **global variables** of a component based embedded software project.

Components are often written by different teams or companies and talk to each other by
reading and writing global variables.  DDD makes that interface explicit: every component
describes the variables it produces and consumes in a small json file, DDD checks that all
components agree, and then generates the c code so that nobody can write a variable that
belongs to somebody else.

See [SPEC.md](SPEC.md) for the specification this implementation follows.

```text
   *.ddd.json  --->  load  --->  resolve + check  --->  DataDictionary
                   (pydantic)      (ddd.analysis)      (the contract)
                                                              |
                          +-----------------------------------+
                          |                                   |
                     c backend                           a2l backend
                          |                                   |
        +-----------------+--------------+                    v
        v                                v               project.a2l
   ddd_globals.c                   <Component>.h
   (definitions)                   (declarations)
```

The front end never mentions c or a2l; a backend never touches the loader or the checks.
Everything they share is the [DataDictionary](src/ddd/ir.py) - `ddd dump` writes it out and
`ddd schema dictionary` publishes its schema.

The **full documentation is at <https://sauci.github.io/ddd/>** - a guided introduction, the
reference for every command, every check and every json field, and the reasoning behind the
design. It is generated from these sources: the root of the site lands on the newest release,
and <https://sauci.github.io/ddd/latest/> follows `master`, which is what the links below
point into, so that they describe the tree this README sits in rather than whatever was true
when somebody last wrote it down. This README is the short version.

`ddd --version` prints the release, and [CHANGELOG.md](CHANGELOG.md) says what changed in
it - including what a migration costs, since a minor release may still change the file format
while the major version is `0`. The check identifiers, the command names and the json file
formats are the tool's public interface; the generated a2l is ASAP2 1.6.1. Licence terms are
in [LICENSE](LICENSE), and problems belong in the
[issue tracker](https://github.com/Sauci/ddd/issues).

## Installation

Requires Python 3.12 or newer; the only runtime dependencies are pydantic and jinja2.

```bash
pip install ddd-tool                 # from the index
pip install ./ddd_tool-0.7.0-py3-none-any.whl   # from a delivered wheel, no network
ddd --version
```

The distribution is called `ddd-tool` because `ddd` was taken; the command, the importable
package and the `*.ddd.json` files are all still `ddd`.

**Platform support**: Python 3.12 or newer, on Windows and Linux - both are exercised by the
ci on every change.  The [CMake integration](#cmake-integration) needs CMake 3.20 when a
hand-written project description is passed with `PROJECT`, and CMake 3.30 when the project is
collected from the link graph.

The examples used below are part of the source distribution rather than the wheel. To follow
along, clone the repository or unpack the sdist, and from there the tool also runs without
being installed at all:

```bash
git clone https://github.com/Sauci/ddd && cd ddd
PYTHONPATH=src python -m ddd --help
```

## Quick start

```bash
ddd check    examples/demo/demo.ddd.json
ddd list     examples/demo/demo.ddd.json
cp -r "$(ddd templates-dir)" templates    # the c templates belong to the project: copy, then adapt
ddd generate all examples/demo/demo.ddd.json -o build/gen -t templates
```

`ddd check` on a project with problems prints one line per finding and exits with 1:

```text
$ ddd check examples/inconsistent/project.ddd.json
examples/inconsistent/component_b.ddd.json#component.interface[0]: error[multiple-producers]: 'SharedValue' is written by component 'ComponentB' and by component 'ComponentA'; exactly one writer is allowed
    note: examples/inconsistent/component_a.ddd.json#component.interface[0]: also written here
...
4 errors, 1 warning
```

Each finding is one line, however long, so that `grep` and a ci log parser see one record
per finding; only a `note:` continues on its own line.

## File formats

All files are plain json and **must be named `*.ddd.json`**.  In a repository full of json,
that double extension says at a glance which files belong to DDD, and it lets a build
script, a linter or an editor match them with one pattern.  A description file with any
other name is reported as `file-extension`; the check can be relaxed with
`-W file-extension=warning` while a project is being migrated.

The top level key decides what a file is: `project`, `component`, `types`, `units`,
`sections`, `constants` or `rasters`.
Unknown keys are rejected, so typos are found instead of silently ignored - with one
deliberate exception: a top level `$schema` key is allowed and ignored, because it is how an
editor binds a file to its schema.  The machine readable contract of each kind is available
with `ddd schema <kind>`, and writing it out turns the editor into the authoring aid:

```bash
ddd schema all -o schemas          # writes one file per format, to commit
```

Then point each description at the schema of its own kind.  The path is relative to the file,
and it has to be per file rather than an editor wide setting, because a project, a component
and a types file all end in `*.ddd.json` and only the content says which is which:

```json
{
  "$schema": "../../schemas/ddd_component.schema.json",
  "component": { ... }
}
```

With that binding in place the editor completes the keys, offers the datatypes, scopes and
kinds as dropdowns, and flags an unknown key while it is being typed rather than at the next
`ddd check`.  The documentation comes with it: every key explains itself on hover, and so does
every value of a dropdown - `uint16` says how much storage it costs and which values fit in
it, `"kind": "curve"` says what a curve is as against a value block.

### The checks in the editor too

A schema is per file and static, so there is a whole class of mistake it cannot see: that an
`axis` names an axis no component declares, that two components disagree about a unit, that
nobody produces an input.  Those need the whole
project resolved, which is what `ddd lsp` brings into the editor:

```bash
ddd lsp                      # speaks the Language Server Protocol on stdin and stdout
```

Editors that launch a server themselves - Neovim, Helix, Emacs - need only that command.
VS Code cannot start one without an extension, so there is one in
[editors/vscode](editors/vscode); it is a launcher and nothing more, which is why everything
below works the same either way.  Every release attaches a `ddd-<version>.vsix` to its
[GitHub release](https://github.com/Sauci/ddd/releases), which is a permanent link needing no
account and no network policy exception: that installs with
`code --install-extension ddd-<version>.vsix` or through **Install from VSIX…** in the
Extensions view.  It updates no more automatically than any other file, so reinstall it when
the python package is upgraded - the two share a version number.

The server reports on open and on save, and it publishes for
**every** file of the project rather than only the one in front of you, because half of a
disagreement is always in the other component.

Hovering anywhere in a declaration shows what the **project** made of that variable, which
the file under the cursor does not say: the shape a curve got from its axis, limits derived
from a datatype and a conversion nobody wrote down, who writes it and who reads it, what an
enum's numbers mean, and the initial values as a sparkline.

```text
CurveA — curve, uint16          |  unit        ms
Calibratable curve over AxisA   |  limits      0 .. 655.35 - the full range of the datatype
                                |  conversion  linear(factor=0.01, offset=0)
Local to Controller.            |  shape       [6]
                                |  axis        AxisA - 0 .. 8000 Hz
   █▄▃▂▁▁   6.5 .. 12 ms
```

Those are *initial* values: DDD describes an interface, and what an engineer calibrates lives
in the calibration tool, the hex file and the a2l.  A map is drawn a row at a time against one
shared scale, and an object whose values are all the same is stated rather than drawn - a row
of identical bars looks like a reading of the data rather than the absence of one.

It also navigates, which is where a data dictionary stops being a pile of files:

| from | go to definition | find references |
| --- | --- | --- |
| anywhere in a declaration - the name, the datatype, a number | the declaration that **writes** that object, in whichever component that is | every declaration of it |
| a structure name in a `typename` | where the structure is declared | every member nesting it |
| an `includes` entry | the file - wildcards land on every match | |

**Quick fixes** reconcile a `definition-mismatch`.  Put the cursor on a `unit`, a
`conversion`, a `datatype` or any other key the declarations have to agree on, and the editor
offers every way of reconciling it, ordered by which component owns the variable: a consumer
is shown the producer's value first, the producer its own.  A key nobody else states can be
**removed** instead of spread - two declarations disagree just as much when one says nothing,
and which way to settle it is yours.  The value is copied as you wrote it rather than
re-serialised, so `{ "kind": "linear", "factor": 0.25 }` arrives looking like itself; a
declaration that never mentioned the key gets it inserted, on one line or its own depending on
how that file is written.  Nothing is offered when everybody already agrees.

**Rename** (`F2`) on a variable name rewrites it in every component that declares it and in
every `axis`, `x_axis`, `y_axis` or `input` that names it.  A name c reserves, one that is
not a usable identifier, or one the project already declares is refused with the reason
before a single file is touched - a rename writes into several at once, and an unusable
name is otherwise noticed a build later.  Free text is left alone: a `description` that
mentions the old name still mentions it, because rewriting prose by substring is how a
rename tool starts corrupting files.

Which project a file belongs to is not something the file can say, so the server reads the
`ddd-build.json` that `ddd_generate` leaves in the build tree, and applies the same severities
the build applies.  Point it at an out-of-tree build with `-b DIR`; without it the usual build
directory names next to the workspace are searched.

A file no build claims is still checked, on its own, but only for what one file can decide.
Read alone a component has inputs nobody writes, outputs nobody reads and axes declared in
files nobody handed over, so `missing-producer`, `unused-output` and `unknown-reference` are
left out rather than reported about every declaration in it.  Everything a single file settles
by itself - an initial value that does not fit, a name c reserves, a duplicate declaration -
is reported as usual.

There are two ways to keep the schemas there, and the choice is about *when* they have to
exist:

* **Commit them.** An editor cannot bind to a file that is not there, so a colleague who
  clones the project finds validation working before building anything.  The cost is that
  they describe whichever DDD wrote them, so `ddd schema all -o schemas` has to be re-run
  after an upgrade.
* **Let the build write them**, with `SCHEMA_DIRECTORY` on `ddd_generate` (see
  [CMake integration](#cmake-integration)).  They are rewritten every time the project is
  configured, so they cannot describe a version that is no longer installed - but they only
  exist after the first configure, so add that directory to `.gitignore` and expect a fresh
  clone to have no validation until then.

Every file under [examples/](examples/) is bound this way, against the [schemas/](schemas/) of
this repository, so cloning it is enough to see the effect.

### Project description

```json
{
  "project": {
    "name": "DemoDevice",
    "description": "optional",
    "includes": ["components/*.ddd.json", "subsystems/logging/logging.ddd.json"]
  }
}
```

`includes` lists components **or other projects**; the kind of each file is detected from
its content.  Paths are relative to the file that contains them, `*`, `?` and `**`
wildcards are expanded, and a file reached over two different paths is loaded once.
Include cycles are reported instead of hanging.

`plugins` names the python modules the project extends itself with, and `extensions` holds
each one's settings, keyed by plugin name; see [Plugins](#plugins) below.

### Software component description

```json
{
  "component": {
    "name": "Controller",
    "description": "optional",
    "interface": [
      {
        "scope": "output",
        "condition": "defined(FEATURE_X)",
        "definition": {
          "kind": "measurement", "name": "ValueG", "datatype": "uint16",
          "conversion": {}, "volatile": false
        }
      }
    ]
  }
}
```

| key | meaning |
| --- | --- |
| `scope` | `input` (read), `output` (written, exactly one per variable), `local` (private to this component) |
| `condition` | c preprocessor expression wrapping the generated declaration; optional |
| `definition` | the variable definition object below |

A component may also declare the types and constants it publishes inside its own
description, in two optional keys - `types` and `constants` - whose entries are exactly
those of the standalone files below.  That co-locates a library's contract in one file
without scoping it: the names join the same project wide namespace, every check applies
unchanged, and any component may name them
([documentation](https://sauci.github.io/ddd/latest/file_formats/component.html)).

### Variable definition object

```json
{
  "kind": "measurement",
  "name": "ValueE",
  "description": "A measurement of the device",
  "datatype": "uint16",
  "unit": "Hz",
  "dimensions": [4],
  "conversion": { "kind": "linear", "factor": 0.25, "offset": 0.0 },
  "limits": { "min": 0, "max": 8000 },
  "init": 0,
  "volatile": true,
  "a2l": { "export": true, "format": "%8.3", "display_identifier": "ValE" }
}
```

| key | default | meaning |
| --- | --- | --- |
| `name` | required | c identifier of the object |
| `id` | none | identity of the object, twelve lowercase base32 characters, stated by the producer only; survives a rename and is compared by nothing |
| `kind` | required | see the next section |
| `datatype` | one of the two | `boolean`, `uint8`, `sint8`, `uint16`, `sint16`, `uint32`, `sint32`, `uint64`, `sint64`, `float32`, `float64`.  Exactly one of `datatype` and `typename` is stated |
| `typename` | one of the two | the name of a declared type, stated instead of `datatype`: a scalar type fixes what the value means, a structure makes this a structured variable |
| `description` | `""` | offered to the c templates as the text of a comment, and used as the a2l long identifier |
| `unit` | `""` | physical unit; components sharing a variable must agree on it |
| `conversion` | required beside `datatype` | raw to physical conversion, see below.  Stated by the declared type instead when `typename` names one |
| `limits` | derived | physical `min`/`max`.  Omitted, they follow from the datatype and the conversion - except for an `enum`, where they are the smallest and largest enumerator |
| `section` | none | the linker section the object is placed in, named in the project's sections file.  A storage key like `init`: the producer states it, and an object without one goes wherever the toolchain's defaults put it |
| `raster` | the component's | the measurement raster the producer updates the object in, written into the a2l as the DAQ event a tool preselects; stated by the producer only, on a measurement only, and defaulting to what its component declares |
| `init` | `null` | raw initial value; `null` means implicit zero initialisation |
| `volatile` | required | whether the generated declaration carries the c keyword of the same name.  Stated on every kind, and with no default, because nothing in the description derives it - see below |
| `a2l` | export | per object a2l tuning |
| `extensions` | none | settings for a [plugin](#plugins)'s block, keyed by plugin name, stated by the producing declaration only |

`init` accepts a scalar or a nested list matching the shape of the object.  A scalar given
for an array initialises **every** element, so `"dimensions": [10], "init": 1` is enough.

### Kinds of data object

Every definition states its `kind`.  A `measurement` is an online value that the software
writes and the calibration tool only reads; everything else is calibration data, which the
software never writes, so it is generated `const`.  (`kind` is stated rather than defaulting
to `measurement`, so that a file bound to `ddd schema` in an editor validates without the
ambiguity a defaulted discriminator leaves in the schema.)

| kind | extra keys | generated c | a2l |
| --- | --- | --- | --- |
| `measurement` | `dimensions` | `volatile uint16_t Speed;` | `MEASUREMENT` |
| `parameter` | - | `const volatile uint16_t Kp = 100U;` | `CHARACTERISTIC ... VALUE` |
| `value_block` | `dimensions` | `const volatile uint8_t Tbl[8] = ...;` | `CHARACTERISTIC ... VAL_BLK` |
| `axis` | `size`, `input` | `const volatile uint16_t Ax[6] = ...;` | `AXIS_PTS` |
| `curve` | `axis` | `const volatile uint16_t C[6] = ...;` | `CHARACTERISTIC ... CURVE` |
| `map` | `x_axis`, `y_axis` | `const volatile int8_t M[4][6] = ...;` | `CHARACTERISTIC ... MAP` |

The two qualifiers in that column are decided separately.  The `const` is the kind's doing,
and no description can take it off calibration data; the `volatile` next to it is what the
definition asked for, so the same parameter stating `"volatile": false` is generated
`const uint16_t Kp = 100U;`, and a measurement that states `false` is generated
`uint16_t Speed;`.

```json
{ "kind": "axis",  "name": "AxisA", "datatype": "uint16", "unit": "Hz",
  "conversion": { "kind": "linear", "factor": 0.25, "offset": 0.0 },
  "size": 6, "input": "ValueE", "init": [0, 3200, 6400, 12800, 19200, 32000],
  "volatile": false }

{ "kind": "map",   "name": "MapA", "datatype": "sint8", "unit": "%",
  "conversion": {}, "x_axis": "AxisA", "y_axis": "AxisB",
  "init": [[20, 24, 28, 30, 32, 30], [18, 22, 26, 28, 30, 28]], "volatile": false }
```

A curve or a map does not repeat the size of its tables: DDD takes the shape from the axes
it refers to, checks the init data against it and emits `[size of y][size of x]`, the layout
the a2l calls `ROW_DIR`.  Axes are shared (a2l `COM_AXIS`), so several curves and maps over
the same break points store them once.

#### Volatile

`volatile` is a key of every kind, it is required, and it has no default, because there is no
answer DDD could derive the way it derives limits from a datatype - the two answers cost
different things and only the project knows which of them it is paying for.  A measurement
needs it when something outside the reading component writes the variable: an interrupt, a
second core, a peripheral.  Calibration data needs it when a calibration tool is to change
the value in a running ecu, because with plain `const` the compiler is entitled to fold the
initialiser into the code that reads it, and gcc does wherever it can see that initialiser -
within one translation unit that is not an optimisation a debug build escapes but a
substitution the front end makes while parsing, so it happens at `-O0` as much as at `-O2`,
to an array element at a constant index as much as to a scalar, and to a value read once at
startup as much as to one read in a loop; across translation units it is what `-flto` does.
Where the load survives, `const` still lets the compiler serve two reads from one of them and
move it across a call.  Either way, a program that writes a new value through such an
object's address prints it back out of memory and then goes on computing with the old one.

What that buys is paid for out of the read only memory.  gcc treats a volatile access as a
side effect and takes the object out of the read only category, so `.rodata` becomes a plain
`.data`: measured with gcc 12.2.0 on DDD's own generated demo with this repository's own flag
set, `.rodata 84 / .data 2` becomes `.data 86`, and an explicitly attributed section moves the
same way.  The categorisation is target independent, but it is worth confirming once on the
toolchain you actually ship with.  On a flash target with an ordinary linker script that means a RAM address with a load
region in flash and a startup copy, so the tool programs a page the code never reads and the
next reset overwrites what it wrote.  A project that calibrates online handles that placement
in its linker script; one that does not states `false` and keeps its data in flash.
**DDD states no preference and reports nothing about the choice** - it generates what the
description says.

Two smaller consequences are worth knowing before writing `true`.  Handing a `const volatile`
array to a helper that takes a plain `const` one is
`error: passing argument 1 of 'sum' discards 'volatile' qualifier`, and the cast that would
paper over it is refused by the `-Wcast-qual` this project compiles with, so hand written
consumer code may need its helpers re-typed.  And the qualifier buys freshness by giving up
coherence: the compiler must re-read the object at every mention, so a parameter set read at
several points of one control step can straddle a calibration write, and a loop over a
`volatile` gain does not vectorise.

#### Conversions

The scaling of fixed point values and the enumerations live in `conversion`.  `kind` may be
omitted when the shape is unambiguous.

```json
{ "kind": "identity" }
{ "kind": "linear", "factor": 0.25, "offset": -40.0 }
{ "kind": "enum", "name": "StateA_t", "enumerators": { "STATE_OFF": 0, "STATE_FAULT": 15 } }
```

* `linear` means `physical = raw * factor + offset`
* `enum` requires an integer datatype and may also be written as a list of
  `{"name": ..., "value": ..., "description": ...}` objects to document each enumerator

### Types, units, sections, constants and rasters

Beside the project and the component there are five more file kinds, each listed in a
project's `includes` like a component and each with its own page in the documentation:

* a **types** file declares scalar types, structures and external types the project shares
  by name: a declaration states `"typename": "Sensor_t"` instead of `datatype`, the type
  fixes the datatype, unit, conversion and limits, and there is nothing left for two
  components to disagree about; an external type names a c type a hand written header
  defines, which a structure member carries verbatim
  ([documentation](https://sauci.github.io/ddd/latest/file_formats/types.html));
* a **units** file pins the unit spellings the project allows, so `Nm` here and
  `newton_meter` there is an `unknown-unit` finding instead of two quiet spellings of one
  quantity; declaring one is opt-in
  ([documentation](https://sauci.github.io/ddd/latest/file_formats/units.html));
* a **sections** file declares the linker sections of the project - the name, whether the
  running software can write it, the alignment it guarantees - and a definition places its
  object with `section`
  ([documentation](https://sauci.github.io/ddd/latest/file_formats/sections.html));
* a **constants** file declares named integer constants, and a shape names one where it
  would state a number - `"dimensions": ["PRESSURE_CELLS"]` - so a size lives in one place,
  the generated c declares the array by the name, and the a2l records it as a
  `SYSTEM_CONSTANT`
  ([documentation](https://sauci.github.io/ddd/latest/file_formats/constants.html));
* a **rasters** file declares the DAQ events a target's XCP configuration offers - a short
  name (eight characters at most), an event channel number and, optionally, a cyclic period -
  and a definition or its producing component names the one a measurement is updated in, so
  the generated a2l preselects the right event for a calibration tool
  ([documentation](https://sauci.github.io/ddd/latest/file_formats/rasters.html)).

Types and constants have a second home: the component that publishes them may declare them
inside its own description, with entries exactly as the standalone files write them, and the
standalone files remain the home of entries shared between components.  Units, sections and
rasters are project wide vocabularies and stay in files of their own.

[examples/structures](examples/structures) is a ready to run project declaring and consuming
structured types, and [examples/vocabulary](examples/vocabulary) is one that pins its unit
spellings, places its objects into declared memory sections, measures some of them on
declared rasters and dimensions its arrays by declared constants - one embedded in the pump
component, one shared in a standalone file; both projects check clean.

### Plugins

What is true of one project and of no other - a storage key, a layout version, a tag another
tool reads - lives in a **plugin**: a python module the project names under `plugins`, which
owns an `extensions` block on a definition and on the project, validates it with a pydantic
model of its own, and contributes checks (`-W layout/duplicate-key=warning` targets one),
comparison rules and an artefact (`ddd generate layout`). DDD carries the block into the
dictionary and never interprets it. The api is documented at
<https://sauci.github.io/ddd/latest/plugins.html>; [examples/plugins/ddd_layout.py](examples/plugins/ddd_layout.py)
is a worked example and [examples/layout](examples/layout) a project that names it.

## Consistency checks

`ddd checks` lists all of them.  Every check has an identifier and a default severity that
can be changed with `-W check=error|warning|info|ignore`; `--strict` turns all warnings into
errors.  Seven of them cannot be relaxed, because a file that cannot be read has nothing
further to say, or because a project cannot be interpreted without the plugins it names:
`file-not-found`, `json-syntax`, `file-kind`, `schema`, `include-cycle`, `plugin-not-found`
and `plugin-invalid`.  `ddd checks` marks them `(fixed)`.

| severity | check | reported when |
| --- | --- | --- |
| error | `multiple-producers` | a variable is written by more than one component |
| error | `missing-producer` | an input is written by nobody |
| error | `local-conflict` | a component local variable is used by another component |
| error | `definition-mismatch` | components disagree on kind, datatype, unit, scaling, shape, volatility, limits or axes.  Limits are compared only where both sides state them: a consumer that leaves them out defers to the producer; `volatile` is not relaxed that way, since every declaration states it and there is no silence to interpret |
| error | `duplicate-declaration` | a component declares the same variable twice |
| error | `duplicate-component` | two files use the same component name |
| error | `duplicate-type` | two files declare the same structured datatype name |
| error | `duplicate-unit` | a unit is declared more than once, in one file or across files |
| error | `duplicate-section` | a memory section is declared more than once, in one file or across files |
| error | `duplicate-constant` | a constant is declared more than once, in one file or across files |
| error | `duplicate-raster` | a measurement raster is declared more than once, in one file or across files |
| error | `duplicate-id` | two data objects of one project carry the same id |
| error | `duplicate-event` | two measurement rasters claim the same event channel number |
| error | `unknown-type` | a typename names no type any file declares |
| error | `unknown-unit` | a unit is not in the vocabulary the project declares |
| error | `unknown-section` | a definition names a memory section no file declares |
| error | `unknown-constant` | a shape names a constant no file declares |
| error | `unknown-raster` | a definition or a component names a measurement raster no file declares |
| error | `section-access` | a measurement is placed in a section the software cannot write |
| error | `type-kind` | a declared type is used where its shape does not fit |
| error | `type-cycle` | structures nest each other, so neither has a size |
| error | `enum-conflict` | one enum name, two different sets of enumerators |
| error | `init-invalid` | an initial value or enumerator does not fit the datatype or the shape |
| error | `unknown-reference` | a curve, map or axis refers to an object nobody declares |
| error | `reference-kind` | a reference points at an object of the wrong kind |
| error | `reserved-identifier` | a name collides with a c keyword or with something `<stdint.h>` declares |
| error | `name-collision` | two generated names would be the same c identifier or the same header |
| error | `consumer-storage` | an `input` declaration states `init` or `section`, which only the producing component decides |
| error | `consumer-raster` | an input declaration states a measurement raster only the producer decides |
| error | `consumer-identity` | an `input` declaration states an `id`, which only the producing component decides |
| error | `consumer-extension` | an `input` declaration states a plugin's `extensions` block, which only the producer decides |
| error | `raster-kind` | a raster is stated on a calibration object, which no daq list carries |
| error | `file-extension` | a description file is not named `*.ddd.json` |
| error | `include-cycle`, `file-not-found`, `file-kind`, `json-syntax`, `schema`, `plugin-not-found`, `plugin-invalid` | the file tree cannot be read; these seven cannot be relaxed |
| error | `include-empty` | an include pattern matches no file; relaxable, unlike the seven above |
| error | `unknown-extension` | an `extensions` block names a plugin the project does not load |
| warning | `storage-mismatch` | components disagree on how the a2l shows the object; the producer wins |
| warning | `section-alignment` | an object needs stricter alignment than its section guarantees |
| warning | `condition-mismatch` | declarations of one variable use different conditions |
| warning | `unused-output` | an output nobody reads |
| warning | `limits-out-of-range` | limits exceed what the datatype can represent |
| warning | `enum-duplicate-value` | two enumerators share a value |
| warning | `name-similar` | two variables differ only in upper/lower case |
| warning | `a2l-unrepresentable` | an object needs more dimensions than the generated a2l version has |
| warning | `address-missing` | an object in the a2l has no entry in the address map the run was given |
| info | `empty-component` | a component declares no variable |
| info | `incomplete-project` | a variable is missing from the dictionary and the finding that says why is silenced |
| info | `missing-id` | a producing declaration or instance states no `id` |

When components disagree, the declaration of the **producing** component is the reference:
its definition is the one that gets generated, and the diagnostics point at the deviating
consumer.

## Comparing two deliveries

`ddd check` answers "do these components fit together". A different question is "can this
delivery replace the one already out there", and that one cannot be answered from the
sources alone: the previous delivery has moved on. So archive its dictionary next to the
binary, and compare against it later:

```bash
ddd dump project.ddd.json > baseline.json     # at release time
ddd compare baseline.json project.ddd.json    # later, for the next delivery
ddd compare baseline.json project.ddd.json --renames renames.json   # ...and list what moved
ddd check project.ddd.json --baseline baseline.json   # both questions, one exit code
```

`--renames` writes the old-to-new name pairs of the comparison - each object's `id` (a member
of a renamed structure under the instance's id followed by its member path), its old
name and its new name - to a json file, so a migration tool can update the calibration
datasets, recordings, test scripts and requirement documents that key on the old spelling
without having to parse the findings above.

Either side may be an archived dictionary or a project description, so nothing has to be
staged into a temporary file. The comparison is **directional** - can the candidate stand in
for the baseline - and graded, because the changes are not equally bad:

| severity | check | reported when |
| --- | --- | --- |
| error | `removed-object` | an object is gone and a component read it |
| error | `changed-interface` | kind, datatype, unit, scaling, shape, axes or locality changed |
| error | `reused-name` | a name of the baseline now names a different object |
| warning | `renamed-object` | an object of the baseline is offered under a different name; its `id` is what says so |
| warning | `removed-unused-object` | an object is gone that no component read |
| warning | `changed-storage` | the initial value, `volatile`, the memory `section` or the measurement `raster` changed; on calibration data the volatility also decides whether the object still lives in read only memory |
| warning | `narrowed-limits` | the limits got tighter, so calibrated data may no longer fit |
| warning | `changed-owner` | another component produces it now |
| warning | `changed-condition` | the preprocessor condition changed |
| warning | `changed-a2l` | the a2l entry changed |
| warning | `project-mismatch` | the two sides name different projects, so the baseline may be the wrong file |
| warning | `missing-plugin` | a compared dictionary records a plugin this run has not loaded, so that plugin's rules did not run |
| info | `added-object` | the candidate declares something new |

Three details worth knowing. **Widening a limit is silent** - every value the baseline allowed
still fits - while narrowing it is a warning; and when the interface already changed, the
narrowed limits that follow from it are not reported separately, so the cause is not buried
under its own symptom. A rescaled conversion is an **error**, because that is the failure
which compiles, links, runs, and reports every value wrong by a constant factor. And
`reused-name` is an error for the same reason - a calibration dataset or a recorded
measurement keyed by that spelling binds to the new object exactly as readily as to the old
one - but a project that reuses names deliberately can relax it with `-W reused-name=warning`.

The two questions stay separate on purpose: a project can be internally consistent and still
not be a valid replacement, and the other way round. `ddd compare` on a project description
reports both.

## Generated files

**The c templates belong to the project.** What the generated sources look like - the comment
convention, the banner, the include guards, whether a variable is commented at all - is a
house style that does not follow from the data, so DDD renders jinja2 templates the project
supplies and `--template-dir` is required.  `ddd templates-dir` prints a working set to copy
and adapt; nothing falls back to it.

The templates also decide what the files are *called*, which is why there is no prefix
option: every `*.jinja2` in the directory renders to a file named like it without that
extension, a name starting with `_` is a helper that renders nothing on its own, and a name
containing `{component}` renders once per component.  Renaming a template renames its output.

With the example templates, `ddd generate all -o DIR -t DIR` writes - and rewrites only what
actually changed, so unchanged output does not trigger a rebuild:

| file | from | content |
| --- | --- | --- |
| `ddd_types.h` | `ddd_types.h.jinja2` | `<stdint.h>`/`<stdbool.h>` and one `typedef enum` per enum conversion |
| `ddd_globals.h` | `ddd_globals.h.jinja2` | `extern` declaration of every variable, for `ddd_globals.c` only |
| `ddd_globals.c` | `ddd_globals.c.jinja2` | the single definition of every global variable, grouped by owner |
| `<Component>.h` | `{component}.h.jinja2` | the interface of one component: nothing else is visible |
| `<Project>.a2l` | built in | the calibration description |

The a2l is the exception: its structure is dictated by ASAM MCD-2 MC rather than by a project,
and a malformed one is refused by the calibration tool, so that generator stays inside DDD.

```c
/* ddd_globals.c, as the example templates render it */
/** Measurement used as the input quantity of AxisA [Hz] */
volatile uint16_t ValueE = 0U;
/** Signed measurement with a fixed point conversion [degC] */
int16_t ValueF = -400;
#if defined(FEATURE_X)
/** Measurement that only exists when FEATURE_X is defined [V] */
uint16_t ValueG = 1000U;
#endif /* defined(FEATURE_X) */
```

How that reads is the *example* templates' choice, not DDD's: a project that wants a
different comment convention, a different banner, or no comments at all, says so in its own
copy.

```c
/* UserInterface.h - only what UserInterface declared */
/* inputs - produced elsewhere, UserInterface may only read them */
/** Measurement used as the input quantity of AxisA [Hz] */
extern volatile uint16_t ValueE;  /* produced by Controller */
/** Signed measurement with a fixed point conversion [degC] */
extern int16_t ValueF;  /* produced by Controller */
```

Access rules are enforced by visibility: a component includes its own header, and that
header declares only what the component declared.  The enforcement is the include path -
`ddd_globals.h` sits next to the component headers and declares everything, and only asks
in a comment not to be included; the cmake integration is what makes the path narrow in
practice.  With `--const-inputs` the enforcement becomes stronger,
inputs are then declared `extern const` so that writing to a foreign variable does not
compile.  The definition in `ddd_globals.c` stays non-const, which is a constraint violation
in strict c but is accepted by the usual embedded toolchains; that is why the option is
opt-in.

The artefact is part of the command: `ddd generate c` renders the c sources alone,
`ddd generate a2l` writes the a2l alone - no c, no template directory; the second run of a
build, once the linker has decided the addresses - and `ddd generate all` produces both in
one run.  Each artefact takes only its own options.  Useful ones: `--dry-run`
(reports what would be written and exits `0` either way, so it is not a staleness gate on
its own), `--force` (generate despite errors - the files are written using the producing
component's definition, but the command still reports every finding and still exits `1`),
`--byte-order big`, `--address-map addresses.json`.

## A2L support

The a2l file is ASAP2 1.6.1 and contains a `MEASUREMENT` per measurement, a `CHARACTERISTIC`
per parameter, value block, curve and map, an `AXIS_PTS` per axis, the `RECORD_LAYOUT`s they
deposit into, `COMPU_METHOD`s shared between objects with the same conversion and unit, a
`COMPU_VTAB` per enum and one `GROUP` per component.

* a linear conversion becomes `RAT_FUNC` with `COEFFS 0 1 -offset 0 0 factor`, which is the
  a2l way of writing `raw = (physical - offset) / factor`
* an identity conversion without unit uses `NO_COMPU_METHOD`
* a measurement or a value block with dimensions gets a `MATRIX_DIM`, listing the fastest
  running index **first** - the reverse of the c declaration, so `uint8_t T[2][3]` becomes
  `MATRIX_DIM 3 2 1`.  A curve and a map carry none: their shape is already given by the
  point counts of the axes they refer to
* a curve or map points at its axes with an `AXIS_DESCR` of attribute `COM_AXIS` plus an
  `AXIS_PTS_REF`; an axis referenced this way is always exported, because a dangling
  `AXIS_PTS_REF` would make the file invalid
* the address of an object is `0x00000000` unless `--address-map` provides the linker
  addresses (`ECU_ADDRESS` is simply the keyword the format uses);
  `SYMBOL_LINK` is always emitted, so a2l address patchers can fill them in after linking.
  The map is a flat json object of symbol to address, decimal or hexadecimal, produced from
  the linker output after the first build; a symbol that is not in it keeps address 0, and
  an address outside `0` .. `0xFFFFFFFF` is refused rather than written out malformed:

  ```json
  { "ValueE": "0x20000100", "AxisA": "0x08004000", "Kp": 134234112 }
  ```

* a2l has no notion of preprocessor conditions, so a conditional variable is exported with a
  comment stating the condition
* `"a2l": {"export": false}` keeps a variable out of the file

## Command line

| command | purpose |
| --- | --- |
| `ddd check FILE` | run all checks, exit 1 on errors; `--baseline` also compares |
| `ddd compare BASELINE CANDIDATE` | report whether one delivery can replace another; `--plugin` loads the plugins of an archived candidate |
| `ddd generate all\|c\|a2l\|<plugin> FILE -o DIR` | check and generate |
| `ddd list FILE` | table (or `--format json`) of variables, producers and consumers |
| `ddd dump FILE` | print the resolved dictionary, the contract the backends consume |
| `ddd id --assign FILE...` | write an identity into every producing declaration that has none |
| `ddd schema component\|constants\|dictionary\|project\|rasters\|sections\|types\|units\|all` | json schema of the file formats and of the contract; `all` writes them into a directory; `--plugin` closes the extension blocks over the named plugins' models |
| `ddd sources FILE` | list every description file the project is built out of, for a build system |
| `ddd build-info FILE -o FILE` | record which project a build runs DDD on and with which severities, for an editor |
| `ddd lsp` | run the language server, reporting the checks in the editor while a file is written |
| `ddd checks` | list the checks and their default severity; `--plugin` lists a plugin's checks after the built-in ones |
| `ddd cmake-dir` | print the directory holding the cmake integration module |
| `ddd templates-dir` | print the directory holding the example c templates, to copy into a project |

`FILE` may be a project or a single component file, which makes it possible to check a
component on its own before integrating it - add `-W missing-producer=ignore` in that case,
because the components producing the inputs are by definition not part of the file.

`--format json` prints machine readable diagnostics for a ci job. It is available on every
command that produces findings - `check`, `compare`, `generate`, `list`, `dump`, `sources` and
`checks`. The rest have nothing to format: `ddd schema` and `ddd build-info` emit json
already, `ddd lsp` speaks json-rpc on its own, `ddd cmake-dir` and `ddd templates-dir` print
a single path, and `ddd id --assign` reports which files it could not read and one total of
ids written across all of them, not a list of findings. `ddd dump` is the
one command whose stdout is *itself* the payload, so there the diagnostics go to stderr and
`--format` chooses how they are written; `ddd dump project.ddd.json > baseline.json` works
in either format.

Exit codes: `0` clean, `1` findings, `2` wrong usage.  `1` means at least one finding was
reported **as an error**: a run with only warnings exits `0`, which is what `--strict` is
for.

In the text format the findings, the summary and the verdict line all go to **stderr**, so
that `ddd dump > baseline.json` and `ddd list | ...` carry only the payload.  With
`--format json` the report is the payload and goes to stdout.

## CMake integration

[cmake/Ddd.cmake](cmake/Ddd.cmake) turns the whole workflow into two calls.  A component
registers its description on its own target, and the image collects the descriptions of the
components it links:

```cmake
list(APPEND CMAKE_MODULE_PATH "/path/to/ddd/cmake")   # `ddd cmake-dir` prints it
include(Ddd)

add_library(sensor_hub STATIC sensor_hub.c)
ddd_add_component(sensor_hub JSON sensor_hub.ddd.json)

add_library(controller STATIC controller.c)
target_link_libraries(controller PRIVATE sensor_hub)
ddd_add_component(controller JSON controller.ddd.json)

add_executable(firmware.elf main.c)
target_link_libraries(firmware.elf PRIVATE controller)
ddd_generate(firmware.elf NAME DemoDevice TEMPLATE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/templates")
```

`sensor_hub.c` then simply writes `#include "SensorHub.h"` - the header DDD generated for
that component, and nothing else is on its include path.  A complete, buildable example is
in [examples/cmake/](examples/cmake/).

**Collection follows the link graph.**  The descriptions travel as a transitive usage
requirement (`TRANSITIVE_LINK_PROPERTIES`, hence CMake **3.30**), so an image gets exactly
the components it links: an image linking only `sensor_hub` gets `SensorHub.h` and an a2l
with SensorHub's variables, and `controller` does not appear at all.  A project that would
rather keep a hand-written project description can pass `PROJECT <file>` instead, which
needs no 3.30 and no `ddd_add_component`.

`ddd_generate` creates three helper targets, named after the image without its extension:

| target | what it is |
| --- | --- |
| `firmware_ddd_generation` | runs the generator |
| `firmware_ddd_headers` | interface library carrying the include directory; linked into every registered component |
| `firmware_ddd_globals` | object library compiling every generated definition file, linked into the image |

plus `firmware_ddd_check` to run the consistency check on its own in ci, and one
`<target>.ddd` per component that checks a single component before it is integrated.  The
path of the generated a2l is available as the `DDD_A2L` property of the image.

A `ddd-build.json` is written into the output directory at configure time as well.  It names
the project description this image is generated from and the severity policy it is generated
under - the two things no `*.ddd.json` records, since without `PROJECT` the project
description is collected out of the link graph and does not exist in the source tree at all.
Nothing in the build reads it; it is there so that an editor can report what the build
reports.

Options: `PROJECT`, `NAME`, `OUTPUT_DIRECTORY`, `TEMPLATE_DIRECTORY`, `SCHEMA_DIRECTORY`,
`ADDRESS_MAP`, `BYTE_ORDER`,
`SEVERITY`, `LINK_LIBRARIES`, `DEPENDS`, `CONST_INPUTS`, `NO_A2L`, `STRICT` and
`NO_PROPAGATE_HEADERS`.  The last one matters for a project building **several** images from
the same components: their generated headers differ, so only one image may hand its headers
to the components automatically - the second call has to opt out and be wired explicitly.
DDD refuses the ambiguous case rather than letting an include order decide it.

The declared outputs are derived from the template names, and the a2l; a `{component}`
template is left out because its outputs are named after the components, which are only known
once the description files have been read.  That is why
consumers depend on `firmware_ddd_headers` rather than on an individual header path.

## Compiling the generated code (docker / WSL)

The generated c code is only worth something if a compiler accepts it, so the repository
ships a small linux image that does exactly that.  Run it from a WSL shell, where docker
speaks linux containers:

```bash
wsl -d Ubuntu
cd /mnt/c/path/to/ddd        # the working tree, seen from inside WSL

docker compose build
docker compose run --rm check            # ddd check on the demo project
docker compose run --rm generate         # ddd generate on the demo project, into build/gen
docker compose run --rm compile          # generate + compile + link + verify
docker compose run --rm compile-const    # same, with --const-inputs
docker compose run --rm cmake            # build examples/cmake through cmake/Ddd.cmake
docker compose run --rm test             # pytest with the coverage gate
docker compose run --rm coverage         # same, plus an html report
docker compose run --rm lint             # ruff + mypy
docker compose run --rm docs             # the html documentation, into build/docs/html
docker compose run --rm shell            # an interactive shell in the image
docker compose run --rm ddd ddd list examples/demo/demo.ddd.json
```

`compile` runs [docker/compile.sh](docker/compile.sh), which

1. generates the demo project into `build/gen`,
2. writes one translation unit per generated header that includes it **twice**, proving
   that every header is self contained and that its include guard works,
3. compiles everything with
   `-std=c11 -Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow -Wcast-qual -Wstrict-prototypes`,
4. links all objects into one binary, which is where a duplicated definition or a
   declaration without a definition would show up, and
5. compares `nm` against `ddd list --format json` so that every variable DDD promised is
   defined exactly once and nothing else is ([docker/verify_symbols.py](docker/verify_symbols.py)).

Steps 2 to 5 run twice, once plain and once with `-DFEATURE_X`, so the conditional
declarations are covered in both states:

```text
== symbols   [base]
19 of 20 declared variables are defined
  conditional, absent : ValueG
== symbols   [defines]
20 of 20 declared variables are defined
  conditional, present: ValueG
```

Point it at your own project with
`docker compose run --rm compile ddd-compile path/to/project.ddd.json build/mine`, and use the
`CDEFS`, `GENFLAGS`, `CFLAGS` and `CC` environment variables to change the defines,
the `ddd generate` flags, the warning set or the compiler.

The working tree is bind mounted at `/work` and `PYTHONPATH=/work/src` shadows the copy
installed in the image, so code changes take effect without rebuilding.  The container runs
as root, so output under `build/` belongs to root when the mount is a real linux filesystem.

## Development

```bash
python -m pytest              # the suite, the coverage gate and the doc checks
python -m pytest --no-cov     # quicker, while working on a single test
python -m ruff check .
python -m ruff format .
python -m mypy
```

Coverage runs with every test run and **a gap fails the run**: `--cov-fail-under=100` over
statements *and* branches, configured in [pyproject.toml](pyproject.toml).  The reasoning is
that a line nobody executes is a line nobody has ever seen behave - and in a code generator,
an unexercised branch means an output nobody has ever looked at.  Two consequences worth
knowing:

* the gate is what found the dead code this project used to carry (unused properties on the
  analysis and contract types); the fix was deleting them, not writing tests for them,
* the paths that only a coverage run reaches - unreadable files, malformed json, relaxed
  severities, odd float literals - live together in
  [tests/test_edge_cases.py](tests/test_edge_cases.py).

Three more suites guard things a type checker cannot:
[tests/test_backends.py](tests/test_backends.py) walks the import graph so the layering
cannot rot, [tests/test_hardening.py](tests/test_hardening.py) holds one test per defect that
once reached a customer-facing artefact or verdict, and
[tests/test_documentation.py](tests/test_documentation.py) with
[tests/test_transcripts.py](tests/test_transcripts.py) hold the documentation to the tool:
every check, command, object kind and datatype is named where it should be, no link points at
a file that no longer exists, and every command a page runs over the examples prints what the
page shows.

`docker compose run --rm coverage` writes a browsable report to `build/htmlcov/index.html`.

### Layout

| layer | knows about | does not know about |
| --- | --- | --- |
| [models/](src/ddd/models/) | the json file formats, storage sizes, value ranges | c, a2l |
| [loading.py](src/ddd/loading.py) | files, includes, globs | what the data means |
| [analysis.py](src/ddd/analysis.py) | ownership, agreement, references | any output format |
| [ir.py](src/ddd/ir.py) | **the contract**: the resolved dictionary | how it is rendered |
| [plugins.py](src/ddd/plugins.py) | the plugin api: the blocks, the hooks | the loader, the analysis, any backend |
| [backends/c/](src/ddd/backends/c/) | `uint16_t`, literals, include guards, templates | a2l, the loader |
| [backends/a2l/](src/ddd/backends/a2l/) | `UWORD`, compu methods, record layouts, templates | c, the loader |

A backend is anything with a `name` and a `generate(dictionary, output_dir)` method
([backends/base.py](src/ddd/backends/base.py)); adding an output format means adding a
package and listing it, and changing nothing else.  `tests/test_backends.py` enforces the
layering by walking the import graph, so the split cannot rot silently.

Diagnostics never raise: the loader and the analysis collect as many findings as possible in
one run.

## The specification

[SPEC.md](SPEC.md) is the authoritative contract: it states the file formats, the checks,
the command line and the generated artefacts this implementation is measured against, and
the test suite holds the two together.  Where this README summarises and the specification
binds, the specification wins.
