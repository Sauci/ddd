# DDD

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

`ddd --version` prints the release. The check identifiers, the command names and the json
file formats are the tool's public interface and do not change within a major version; the
generated a2l is ASAP2 1.6.1. Licence terms are in [LICENSE](LICENSE), and problems belong
in the [issue tracker](https://github.com/Sauci/ddd/issues).

## Installation

Requires Python 3.12 or newer; the only runtime dependencies are pydantic and jinja2.

```bash
pip install ddd-tool                 # from the index
pip install ./ddd_tool-0.1.0-py3-none-any.whl   # from a delivered wheel, no network
ddd --version
```

The distribution is called `ddd-tool` because `ddd` was taken; the command, the importable
package and the `*.ddd.json` files are all still `ddd`.

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
ddd generate examples/demo/demo.ddd.json -o build/gen
```

`ddd check` on a project with problems prints one line per finding and exits with 1:

```text
$ ddd check examples/inconsistent/project.ddd.json
examples/inconsistent/component_b.ddd.json#component.declarations[0]: error[multiple-producers]: 'SharedValue' is written by component 'ComponentB' and by component 'ComponentA'; exactly one writer is allowed
    note: examples/inconsistent/component_a.ddd.json#component.declarations[0]: also written here
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

The top level key decides what a file is: `project` or `component`.  Unknown keys are
rejected, so typos are found instead of silently ignored.  The machine readable contract is
available with `ddd schema project` / `ddd schema component`.

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

### Software component description

```json
{
  "component": {
    "name": "Controller",
    "description": "optional",
    "declarations": [
      {
        "scope": "output",
        "condition": "defined(FEATURE_X)",
        "definition": { "name": "ValueG", "datatype": "uint16" }
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

### Variable definition object

```json
{
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
| `kind` | `measurement` | see the next section |
| `datatype` | required | `bool`, `uint8`, `int8`, `uint16`, `int16`, `uint32`, `int32`, `uint64`, `int64`, `float32`, `float64` |
| `description` | `""` | becomes a doxygen comment and the a2l long identifier |
| `unit` | `""` | physical unit; components sharing a variable must agree on it |
| `conversion` | identity | raw to physical conversion, see below |
| `limits` | derived | physical `min`/`max`.  Omitted, they follow from the datatype and the conversion - except for an `enum`, where they are the smallest and largest enumerator |
| `init` | `null` | raw initial value; `null` means implicit zero initialisation |
| `a2l` | export | per object a2l tuning |

`init` accepts a scalar or a nested list matching the shape of the object.  A scalar given
for an array initialises **every** element, so `"dimensions": [10], "init": 1` is enough.

### Kinds of data object

`kind` may be omitted, in which case the object is a measurement - an online value that the
software writes and the calibration tool only reads.  Everything else is calibration data:
the software never writes it, so it is generated `const` and ends up in read only memory.

| kind | extra keys | generated c | a2l |
| --- | --- | --- | --- |
| `measurement` | `dimensions`, `volatile` | `uint16_t Speed;` | `MEASUREMENT` |
| `parameter` | - | `const uint16_t Kp = 100U;` | `CHARACTERISTIC ... VALUE` |
| `value_block` | `dimensions` | `const uint8_t Tbl[8] = ...;` | `CHARACTERISTIC ... VAL_BLK` |
| `axis` | `size`, `input` | `const uint16_t Ax[6] = ...;` | `AXIS_PTS` |
| `curve` | `axis` | `const uint16_t C[6] = ...;` | `CHARACTERISTIC ... CURVE` |
| `map` | `x_axis`, `y_axis` | `const int8_t M[4][6] = ...;` | `CHARACTERISTIC ... MAP` |

```json
{ "kind": "axis",  "name": "AxisA", "datatype": "uint16", "unit": "Hz",
  "size": 6, "input": "ValueE", "init": [0, 3200, 6400, 12800, 19200, 32000] }

{ "kind": "map",   "name": "MapA", "datatype": "int8", "unit": "%",
  "x_axis": "AxisA", "y_axis": "AxisB",
  "init": [[20, 24, 28, 30, 32, 30], [18, 22, 26, 28, 30, 28]] }
```

A curve or a map does not repeat the size of its tables: DDD takes the shape from the axes
it refers to, checks the init data against it and emits `[size of y][size of x]`, the layout
the a2l calls `ROW_DIR`.  Axes are shared (a2l `COM_AXIS`), so several curves and maps over
the same break points store them once.

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

## Consistency checks

`ddd checks` lists all of them.  Every check has an identifier and a default severity that
can be changed with `-W check=error|warning|info|ignore`; `--strict` turns all warnings into
errors.  Five of them cannot be relaxed, because a file that cannot be read has nothing
further to say: `file-not-found`, `json-syntax`, `file-kind`, `schema` and `include-cycle`.
`ddd checks` marks them `(fixed)`.

| severity | check | reported when |
| --- | --- | --- |
| error | `multiple-producers` | a variable is written by more than one component |
| error | `missing-producer` | an input is written by nobody |
| error | `local-conflict` | a component local variable is used by another component |
| error | `definition-mismatch` | components disagree on kind, datatype, unit, scaling, shape, limits or axes.  Limits are compared only where both sides state them: a consumer that leaves them out defers to the producer |
| error | `duplicate-declaration` | a component declares the same variable twice |
| error | `duplicate-component` | two files use the same component name |
| error | `enum-conflict` | one enum name, two different sets of enumerators |
| error | `init-invalid` | an initial value or enumerator does not fit the datatype or the shape |
| error | `unknown-reference` | a curve, map or axis refers to an object nobody declares |
| error | `reference-kind` | a reference points at an object of the wrong kind |
| error | `reserved-identifier` | a name collides with a c keyword or with something `<stdint.h>` declares |
| error | `name-collision` | two generated names would be the same c identifier or the same header |
| error | `naming` | a name does not follow the naming convention of the project |
| error | `file-extension` | a description file is not named `*.ddd.json` |
| error | `include-cycle`, `file-not-found`, `file-kind`, `json-syntax`, `schema` | the file tree cannot be read; these five cannot be relaxed |
| error | `include-empty` | an include pattern matches no file; relaxable, unlike the five above |
| warning | `storage-mismatch` | components disagree on `init`, `volatile` or the `a2l` block; the producer wins |
| warning | `condition-mismatch` | declarations of one variable use different conditions |
| warning | `unused-output` | an output nobody reads |
| warning | `limits-out-of-range` | limits exceed what the datatype can represent |
| warning | `enum-duplicate-value` | two enumerators share a value |
| warning | `name-similar` | two variables differ only in upper/lower case |
| warning | `a2l-unrepresentable` | an object needs more dimensions than the generated a2l version has |
| info | `empty-component` | a component declares no variable |

When components disagree, the declaration of the **producing** component is the reference:
its definition is the one that gets generated, and the diagnostics point at the deviating
consumer.

## Naming conventions

Most projects agree that a name means something - which part says what the value *is*, which
says what it is *about*, which says how it was *conditioned*. DDD can hold that agreement in
a `*.ddd.json` file and enforce it, and because the convention is described as a sequence of
**segments** rather than as one regular expression, it can do two things a regex cannot: point
at the part of a name that is wrong, and complete a name you are half way through typing.

```json
{
  "naming": {
    "name": "demo-convention",
    "separator": "_",
    "segments": [
      { "name": "role", "tokens": [
          { "value": "val", "description": "a measured or computed value" },
          { "value": "flg", "description": "a boolean flag" }] },
      { "name": "subject", "pattern": "^[A-Z][A-Za-z0-9]*$", "repeatable": true },
      { "name": "qualifier", "optional": true, "tokens": [
          { "value": "raw", "description": "unconditioned" },
          { "value": "flt", "description": "filtered" }] }
    ]
  }
}
```

A segment carries either a **vocabulary** of tokens with their meanings, or a **pattern** for
a free position. `optional` may only appear at the end and `repeatable` on one segment, so a
name always splits unambiguously. A complete example is in [examples/naming/](examples/naming/).

**Where a name is wrong**, not merely that it is:

```text
$ ddd name -c convention.ddd.json vl_InletTemperature_flt flg_Valid_fltr
vl_InletTemperature_flt
^^
  'vl' is not a known role (val, flg, cnt, par, axs, crv, map, tbl) - did you mean 'val'?
flg_Valid_fltr
          ^^^^
  'fltr' is not a known qualifier (raw, flt, phys, req, max, min) - did you mean 'flt'?
```

**What an unfamiliar name means**, which is the other half of the job:

```text
$ ddd name -c convention.ddd.json val_InletTemperature_flt
val_InletTemperature_flt  (demo-convention)
  val                      role         a measured or computed value
  InletTemperature         subject      what the value is about, in upper camel case
  flt                      qualifier    filtered
```

**Completion in the terminal.** `ddd complete` prints one candidate per line and always exits
zero, because a completion that reports an error is worse than one that offers nothing:

```bash
export DDD_CONVENTION=/path/to/convention.ddd.json
source completion/ddd.bash
ddd name val_Inlet<TAB>          # offers the qualifiers once the subject is typed
```

**In the project.** A project points at its convention, and then every declared name is
checked on every run - the `naming` check, an error by default and relaxable like any other:

```json
{ "project": { "name": "P", "naming": "convention.ddd.json", "includes": ["*.ddd.json"] } }
```

The convention belongs to the project rather than to the command line, so whoever checks the
project gets the same verdict as whoever wrote it. Only variable names are checked: a
component name lives in another namespace, and a convention written for variables would
reject every one of them.

## Comparing two deliveries

`ddd check` answers "do these components fit together". A different question is "can this
delivery replace the one already out there", and that one cannot be answered from the
sources alone: the previous delivery has moved on. So archive its dictionary next to the
binary, and compare against it later:

```bash
ddd dump project.ddd.json > baseline.json     # at release time
ddd compare baseline.json project.ddd.json    # later, for the next delivery
ddd check project.ddd.json --baseline baseline.json   # both questions, one exit code
```

Either side may be an archived dictionary or a project description, so nothing has to be
staged into a temporary file. The comparison is **directional** - can the candidate stand in
for the baseline - and graded, because the changes are not equally bad:

| severity | check | reported when |
| --- | --- | --- |
| error | `removed-object` | an object is gone and a component read it |
| error | `changed-interface` | kind, datatype, unit, scaling, shape, axes or locality changed |
| warning | `removed-unused-object` | an object is gone that no component read |
| warning | `changed-storage` | the initial value or `volatile` changed |
| warning | `narrowed-limits` | the limits got tighter, so calibrated data may no longer fit |
| warning | `changed-owner` | another component produces it now |
| warning | `changed-condition` | the preprocessor condition changed |
| warning | `changed-a2l` | the a2l entry changed |
| warning | `project-mismatch` | the two sides name different projects, so the baseline may be the wrong file |
| info | `added-object` | the candidate declares something new |

Two details worth knowing. **Widening a limit is silent** - every value the baseline allowed
still fits - while narrowing it is a warning; and when the interface already changed, the
narrowed limits that follow from it are not reported separately, so the cause is not buried
under its own symptom. And a rescaled conversion is an **error**, because that is the failure
which compiles, links, runs, and reports every value wrong by a constant factor.

The two questions stay separate on purpose: a project can be internally consistent and still
not be a valid replacement, and the other way round. `ddd compare` on a project description
reports both.

## Generated files

`ddd generate -o DIR` writes, and rewrites only what actually changed, so unchanged output
does not trigger a rebuild:

| file | content |
| --- | --- |
| `ddd_types.h` | `<stdint.h>`/`<stdbool.h>` and one `typedef enum` per enum conversion |
| `ddd_globals.h` | `extern` declaration of every variable, for `ddd_globals.c` only |
| `ddd_globals.c` | the single definition of every global variable, grouped by owner |
| `<Component>.h` | the interface of one component: nothing else is visible |
| `<Project>.a2l` | the calibration description |

```c
/* ddd_globals.c */
/** Measurement used as the input quantity of AxisA [Hz] */
volatile uint16_t ValueE = 0U;
/** Signed measurement with a fixed point conversion [degC] */
int16_t ValueF = -400;
#if defined(FEATURE_X)
/** Measurement that only exists when FEATURE_X is defined [V] */
uint16_t ValueG = 1000U;
#endif /* defined(FEATURE_X) */
```

```c
/* UserInterface.h - only what UserInterface declared */
/* inputs - produced elsewhere, UserInterface may only read them */
extern volatile uint16_t ValueE;  /* produced by Controller */
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

Useful options: `--prefix device` (renames the shared files, and rewrites the component
headers with them since each one includes `<prefix>_types.h`), `--no-a2l`, `--dry-run`
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
| `ddd compare BASELINE CANDIDATE` | report whether one delivery can replace another |
| `ddd generate FILE -o DIR` | check and generate |
| `ddd list FILE` | table (or `--format json`) of variables, producers and consumers |
| `ddd dump FILE` | print the resolved dictionary, the contract the backends consume |
| `ddd schema project\|component\|naming\|dictionary` | json schema of the file formats and of the contract |
| `ddd name -c CONV NAME...` | explain a name, or point at the part that is wrong |
| `ddd complete -c CONV PREFIX` | list the names a prefix may grow into, for shell completion |
| `ddd sources FILE` | list every description file the project is built out of, for a build system |
| `ddd checks` | list the checks and their default severity |
| `ddd cmake-dir` | print the directory holding the cmake integration module |

`FILE` may be a project or a single component file, which makes it possible to check a
component on its own before integrating it - add `-W missing-producer=ignore` in that case,
because the components producing the inputs are by definition not part of the file.

`--format json` prints machine readable diagnostics for a ci job. It is available on every
command that produces findings - `check`, `compare`, `generate`, `list`, `dump`, `name` and
`checks` - which leaves out only `schema` and `cmake-dir`, whose output is machine readable
already, and `complete`, which prints one candidate per line for a shell. `ddd dump` is the
one command whose stdout is *itself* the payload, so there the diagnostics go to stderr and
`--format` chooses how they are written; `ddd dump project.ddd.json > baseline.json` works
in either format.

Exit codes: `0` clean, `1` findings, `2` wrong usage.  `1` means at least one finding was
reported **as an error**: a run with only warnings exits `0`, which is what `--strict` is
for.  Two commands differ on purpose: `ddd complete` always exits `0`, and `ddd name` exits
`2` when the convention itself cannot be read, `1` when a name does not fit it.

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
ddd_generate(firmware.elf NAME DemoDevice)
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
| `firmware_ddd_globals` | object library compiling the one definition file, linked into the image |

plus `firmware_ddd_check` to run the consistency check on its own in ci, and one
`<target>.ddd` per component that checks a single component before it is integrated.  The
path of the generated a2l is available as the `DDD_A2L` property of the image.

Options: `PROJECT`, `NAME`, `OUTPUT_DIRECTORY`, `PREFIX`, `ADDRESS_MAP`, `BYTE_ORDER`,
`SEVERITY`, `LINK_LIBRARIES`, `DEPENDS`, `CONST_INPUTS`, `NO_A2L`, `STRICT` and
`NO_PROPAGATE_HEADERS`.  The last one matters for a project building **several** images from
the same components: their generated headers differ, so only one image may hand its headers
to the components automatically - the second call has to opt out and be wired explicitly.
DDD refuses the ambiguous case rather than letting an include order decide it.

Only `<prefix>_globals.c`, `<prefix>_globals.h`, `<prefix>_types.h` and the a2l are declared
as outputs of the generator; the per-component headers are written next to them but their
names live inside the description files, so they are unknown at configure time.  That is why
consumers depend on `firmware_ddd_headers` rather than on an individual header path.

## Compiling the generated code (docker / WSL)

The generated c code is only worth something if a compiler accepts it, so the repository
ships a small linux image that does exactly that.  Run it from a WSL shell, where docker
speaks linux containers:

```bash
wsl -d Ubuntu
cd /mnt/c/path/to/ddd        # the working tree, seen from inside WSL

docker compose build
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

Steps 3 to 5 run twice, once plain and once with `-DFEATURE_X`, so the conditional
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

Two more suites guard things a type checker cannot:
[tests/test_backends.py](tests/test_backends.py) walks the import graph so the layering
cannot rot, and [tests/test_documentation.py](tests/test_documentation.py) asserts that every
check, command, object kind and datatype is named in the README and the SPEC, and that no
link in either points at a file that no longer exists.

`docker compose run --rm coverage` writes a browsable report to `build/htmlcov/index.html`.

### Layout

| layer | knows about | does not know about |
| --- | --- | --- |
| [models/](src/ddd/models/) | the json file formats, storage sizes, value ranges | c, a2l |
| [loading.py](src/ddd/loading.py) | files, includes, globs | what the data means |
| [analysis.py](src/ddd/analysis.py) | ownership, agreement, references | any output format |
| [ir.py](src/ddd/ir.py) | **the contract**: the resolved dictionary | how it is rendered |
| [backends/c/](src/ddd/backends/c/) | `uint16_t`, literals, include guards, templates | a2l, the loader |
| [backends/a2l/](src/ddd/backends/a2l/) | `UWORD`, compu methods, record layouts, templates | c, the loader |

A backend is anything with a `name` and a `generate(dictionary, output_dir)` method
([backends/base.py](src/ddd/backends/base.py)); adding an output format means adding a
package and listing it, and changing nothing else.  `tests/test_backends.py` enforces the
layering by walking the import graph, so the split cannot rot silently.

Diagnostics never raise: the loader and the analysis collect as many findings as possible in
one run.

## Notes on the specification

SPEC.md leaves a few things open; the choices made here are:

* the variable definition object is the table above, extended with `limits`, `volatile` and
  `a2l` so that a2l can be generated without a second source of information
* a project references its members through `includes`, and a member's kind is detected from
  its content rather than being declared twice
* `local` variables are defined in `ddd_globals.c` like every other variable, but they are
  only declared in the header of the owning component
* the producer of a variable is the authority on its definition
* generated files carry no time stamp, so a regeneration without a change to the input
  produces a byte identical result
