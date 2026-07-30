# DDD Specification

## 1 Introduction

The objective of DDD is to handle global variables in the scope of an embedded software
development project. It shall support component-based development methods, where individual
components may be developed by different developers working in separate teams/companies.

The interfaces between the software-components consist simply in reading from / writing to
global variables. DDD shall provide tools to avoid issues commonly associated with extensive
use of global variables.

DDD covers a central role in the firmware build process: it is the single place where the
data of a project is declared, it emits the c code that allocates that data, and it emits
the ASAM MCD-2 MC description that lets measurement and calibration tools work with it. On
top of that it enforces the component interface rules: ownership, scope and agreement
between the components that share the data.

DDD is not tied to any industry. The terms used throughout this document - target, firmware,
measurement, calibration parameter - describe the roles the data plays, not the kind of
device the software runs on.

### 1.1 Interface specification

DDD allows the software developer to clearly specify the (global variable) interface of a
software-component. The scope of each variable can be defined (input/output/local of the
component). The specification also includes physical units, scaling information for
fixed-point datatypes, enums etc.

### 1.2 Consistency check

When assembling several components into a complete project, DDD ensures consistency of the
global variable interfaces. It checks that each variable is written by only one component,
and that components which consume inputs agree on datatypes/units/scaling etc.

### 1.3 Source code generation

In order to enforce the access rules specified for each component, the global variables shall
be defined and declared by DDD. The tool generates a global definition c-code file, which
contains all used global variables. This file can later be compiled and linked to the project
in the build process.

DDD shall also generate a variable declaration c-header for each software component. This
header shall only contain declarations for the variables specified in the interface
description of the component.

### 1.4 Calibration tool support

DDD shall support the A2L file format (ASAM MCD-2 MC), to integrate the resulting sw into
common measurement and calibration tools. This covers both directions of the data model:
values the tool only *measures*, and values the tool *calibrates* - single parameters, value
blocks, curves, maps and their axes.

### 1.5 Position in the build process

```text
  component json files
          |
          v
    +-----------+   .c/.h    +--------------+   .elf    +---------------+
    |    DDD    |----------->| compile/link |---------->| address import|
    +-----------+            +--------------+           +-------+-------+
          |                                                     |
          |  a2l  <-------------------------------------------- +
          v
   calibration tool
```

DDD is run twice per build: once to generate the sources, and once after linking to produce
an a2l that carries the real addresses taken from the linker output.

## 2 Concepts

| term | meaning |
| --- | --- |
| **project** | a named set of components and/or sub-projects |
| **component** | a software unit with an explicitly declared data interface |
| **declaration** | one entry of a component interface: a scope, an optional condition and a definition |
| **data object** | the thing being declared: a measurement, parameter, value block, curve, map or axis |
| **scope** | ownership and visibility of a data object with respect to the declaring component |
| **conversion** | the rule that maps the raw (implementation) value to the physical value |
| **producer** | the component that owns a data object; its declaration is the authoritative one |
| **data dictionary** | the resolved result: every object with its owner, users, shape and limits worked out. It is the contract between the checking front end and the output backends, and DDD publishes it |

### 2.1 Scope

| scope | meaning |
| --- | --- |
| `input` | the component reads the object; another component has to produce it |
| `output` | the component owns the object; exactly one component may do so |
| `local` | the component owns the object exclusively; no other component may use it |

For measurements, `output` means the component writes the variable. For calibration objects,
which the software never writes, `output` means the component provides the data and other
components may read it; `local` is the normal choice for data that only parametrises the
owning component.

## 3 File formats

All files used by DDD contain simple json formatting and shall be named `*.ddd.json`, so
that a description file is recognisable as such in a project that contains json for many
other purposes. The top level key of a file decides what the file is: `project` or
`component`. Unknown keys are rejected, with one exception: a top level `$schema` key shall
be accepted and ignored, since it is the standard way an editor binds a json file to its
schema and thereby turns the published contract into completion, hover documentation and
as-you-type validation. The formal contract is published by the tool itself as a json
schema, in one file per format, and every authored field of it shall carry its
documentation. The binding is per file rather than per directory because the kind of a
description is in its content and not in its name.

### 3.1 Project description

Contains a list of components (or other (sub-)projects).

```json
{
  "project": {
    "name": "DemoDevice",
    "description": "optional",
    "includes": ["components/*.ddd.json", "subsystems/logging/logging.ddd.json"]
  }
}
```

* `"name"` - identifier of the project, also used as a2l project and module name
* `"description"` - optional free text
* `"includes"` - paths to component or sub-project files, relative to this file. The kind of
  each included file is detected from its content. Shell wildcards are expanded. A file
  reached through several paths is loaded once; include cycles are an error.

### 3.2 Software component description

The top level key `"component"` is mandatory, and it contains the following elements:

* `"name"` The name of the component
* `"description"` Optional free text
* `"declarations"` A list of variable declaration objects

Each variable declaration contains:

* `"scope"` One of input/output/local, indicating the scope of the declaration
* `"condition"` A c-preprocessor conditional expression which will wrap the generated variable
  declarations (optional)
* `"definition"` A variable-definition object

### 3.3 Variable definition object

A definition describes one data object. The key `"kind"` selects the type of object and is
required on every definition, including a `"measurement"`: a defaulted discriminator leaves
the published json schema unable to say which variant an unmarked definition is, which an
editor validating a file against that schema reports as an ambiguity.

Attributes common to every kind:

| key | default | meaning |
| --- | --- | --- |
| `name` | required | c identifier of the object |
| `kind` | `measurement` | `measurement`, `parameter`, `value_block`, `curve`, `map` or `axis` |
| `datatype` | required | `bool`, `uint8`, `int8`, `uint16`, `int16`, `uint32`, `int32`, `uint64`, `int64`, `float32`, `float64` |
| `description` | `""` | offered to the c templates as the text of a comment, long identifier in the a2l |
| `unit` | `""` | physical unit |
| `conversion` | identity | raw to physical conversion, section 3.4 |
| `limits` | derived | physical `min`/`max`; when omitted they follow from the datatype and the conversion, and for an `enum` from the smallest and largest enumerator |
| `init` | `null` | raw initial value; `null` means implicit zero initialisation |
| `a2l` | export | `export`, `format`, `display_identifier` |

Kind specific attributes:

| kind | additional keys | storage | a2l |
| --- | --- | --- | --- |
| `measurement` | `dimensions`, `volatile` | writable ram variable | `MEASUREMENT` |
| `parameter` | - | `const` scalar | `CHARACTERISTIC ... VALUE` |
| `value_block` | `dimensions` (mandatory) | `const` array | `CHARACTERISTIC ... VAL_BLK` |
| `axis` | `size` (mandatory), `input` | `const` array `[size]` | `AXIS_PTS` |
| `curve` | `axis` | `const` array `[size of the axis]` | `CHARACTERISTIC ... CURVE` |
| `map` | `x_axis`, `y_axis` | `const` array `[size of y][size of x]` | `CHARACTERISTIC ... MAP` |

* `dimensions` is a list of array dimensions, e.g. `[3, 4]` for `x[3][4]`. In the a2l the
  same object is described by a `MATRIX_DIM` listing the fastest running index first, i.e.
  in the reverse order - describing it in c order would state a transposed object.
* `init` is a scalar or a nested list matching the shape of the object. A scalar given for an
  array shaped object initialises every element.
* `axis`, `x_axis` and `y_axis` name an object of kind `axis` declared anywhere in the
  project; the axis is shared between all curves and maps referring to it (a2l `COM_AXIS`).
* `input` names the measurement that indexes an axis (a2l input quantity); when omitted the
  a2l uses `NO_INPUT_QUANTITY`.
* Calibration objects (everything except `measurement`) are always generated `const`, so
  that they are placed in read only memory. `volatile` is not merely ignored on them: it
  is a key of `measurement` alone, so a calibration object carrying it is rejected.

### 3.4 Conversions

```json
{ "kind": "identity" }
{ "kind": "linear", "factor": 0.25, "offset": -40.0 }
{ "kind": "enum", "name": "StateA_t", "enumerators": { "STATE_OFF": 0, "STATE_FAULT": 15 } }
```

* `linear` means `physical = raw * factor + offset`; `factor` must not be zero.
* `enum` requires an integer datatype; enumerators may also be given as a list of
  `{"name", "value", "description"}` objects.
* `kind` may be omitted when the shape of the object is unambiguous.

### 3.5 Naming convention

A project may point at a naming convention with its `"naming"` key. The convention is a
file whose top level key is `"naming"` - named `*.ddd.json` like every other description
file, though only project and component files are checked for that extension - and it
describes a name as an ordered sequence of *segments* joined by a separator. Each segment
carries either a controlled vocabulary of tokens with their meanings, or a regular expression
for a free position. A segment may be marked optional (only at the end) or repeatable (only
one), so that a name always splits unambiguously.

The segmented form is required rather than a single expression for the whole name, because it
is what lets the tool report *which part* of a name is wrong and *what may follow* a partially
typed one. Both shall be offered: names shall be validated with the position of the offending
part, and the valid continuations of a prefix shall be printable for a shell completion. Every
declared name shall be checked against the convention as part of checking the project
(`naming`). Component names are not subject to it. Only the convention of the *root*
project applies: a sub-project cannot impose one on the project that includes it, so the
verdict on a name does not depend on which file the run started from.

### 3.6 Memory placement *(planned)*

A `memory` attribute shall select the memory the object is placed in
(`ram`, `rom`, `internal_ram`) and optionally name an explicit linker section. The generated
code shall carry the corresponding section attribute and the a2l shall describe the memory
layout with `MOD_PAR` / `MEMORY_SEGMENT`.

## 4 Consistency checks

Every check has a stable identifier and a default severity. The identifiers are part of the
tool interface - a build script pins them in its severity overrides - so they shall not change
once published. The severity of a check can be changed per project run, so that a team can
fine tune its error management policy; the checks that make a file unreadable cannot be
relaxed. The authoritative list is the one the tool prints itself (`ddd checks`).

Errors:

* `multiple-producers` - a variable is written by more than one component
* `missing-producer` - an input variable is written by nobody
* `local-conflict` - a component local variable is used by another component
* `definition-mismatch` - components disagree on kind, datatype, unit, scaling, shape,
  referenced axes, or on limits where both of them state limits: a declaration that omits
  them defers to the producer rather than disagreeing with it
* `duplicate-declaration` - a component declares the same variable more than once
* `duplicate-component` - two files declare the same component name
* `enum-conflict` - one enum name is used with different enumerators
* `init-invalid` - an initial value or an enumerator does not fit the datatype or the shape
* `unknown-reference`, `reference-kind` - a curve, map or axis refers to an object that does not exist or has the wrong kind
* `reserved-identifier` - a name collides with a c keyword or with an identifier one of the
  headers the generated code includes already declares
* `name-collision` - two names that are distinct in the description files become the same
  c identifier or the same generated file: enumerators of different enums, an enumerator and
  a variable, or two component names differing only in case
* `naming` - a declared name does not follow the naming convention of the project
* `file-extension` - a description file is not named `*.ddd.json`
* `json-syntax`, `schema`, `file-kind`, `file-not-found`, `include-cycle` - the file tree
  cannot be read; these five are the ones whose severity cannot be changed
* `include-empty` - an include pattern matches no file; relaxable, because a pattern that is
  legitimately empty in one variant of a project is a normal thing to allow

Warnings:

* `storage-mismatch` - components disagree on the initial value, on `volatile` or on the
  `a2l` block; the producer wins
* `condition-mismatch` - declarations of one variable use different preprocessor conditions
* `unused-output` - an output is read by nobody
* `limits-out-of-range` - limits exceed what the datatype can represent
* `enum-duplicate-value` - two enumerators share a value
* `name-similar` - two variables differ only in upper/lower case
* `a2l-unrepresentable` - an object cannot be fully described by the a2l version DDD writes;
  today that is an array of more than three dimensions, which `MATRIX_DIM` of 1.6.1 cannot
  carry

Information:

* `empty-component` - a component declares no variable at all

### 4.1 Comparing two deliveries

The checks above answer whether a set of components fits together. DDD shall also answer
whether one delivery can replace another, which is a different and directional question, and
one that cannot be answered from the description files alone: the delivery being replaced has
moved on. The data dictionary of a delivery is therefore the artefact to archive, and the
comparison is a function of two of them.

A change shall be graded by what it costs the consumers:

Errors - the consumers of the object become wrong, whether or not they still compile:

* `removed-object` - an object is gone that a component read
* `changed-interface` - kind, datatype, unit, scaling, shape, axes or locality changed

Warnings - behaviour or tooling changes, but no consumer becomes wrong:

* `removed-unused-object` - an object is gone that no component read
* `changed-storage` - the initial value or the volatility changed
* `narrowed-limits` - the physical limits got tighter, so calibrated data may no longer fit
* `changed-owner` - another component produces the object now
* `changed-condition` - the preprocessor condition changed
* `changed-a2l` - the a2l entry changed
* `project-mismatch` - the two dictionaries name different projects, so the baseline is
  probably not the predecessor of this candidate

Information:

* `added-object` - the candidate declares an object the baseline did not

Widening a limit shall be silent, since every value the baseline allowed still fits. Limits
that got tighter shall not be reported on an object whose interface changed as well: the
interface change is the finding to act on, and the narrowing would only bury it. This is
deliberately coarser than "tighter *as a consequence of* the interface change", which
nothing can decide - an independent narrowing of the same object is therefore also held
back until the interface change is resolved.

## 5 Generated artefacts

### 5.1 C code

The c sources shall be rendered from templates the *project* provides, and DDD shall ship no
default set. What the generated code looks like - the comment convention, the banner, the
include guards, whether an object is commented and in which form - does not follow
from the declared data: it is the house style of the software the code is generated into, it
differs between projects, and a generator that fixes it imposes one project's habits on every
other. DDD therefore owns the data and the project owns its presentation. Example templates
shall be shipped and locatable, as a starting point to copy rather than as a fallback.

The set of generated files shall follow from the template directory alone, so that a build
system can declare its outputs without running the generator first:

| template | renders to |
| --- | --- |
| `<name>.jinja2` | `<name>`, once per project |
| `_<name>.jinja2` | nothing; a helper the other templates may import |
| `{component}<rest>.jinja2` | `<Component><rest>`, once per component |

A template in a subdirectory of the template directory is importable but never rendered.

Whatever the templates spell, the *data* they are given is fixed: measurements are writable
variables and calibration objects are `const`, a declaration that carries a condition is
offered with that condition so it can be wrapped in `#if` / `#endif`, and input objects are
optionally marked `const` for the consumer header so that a write access does not compile.

Assignment of objects to freely chosen generated `.c`/`.h` files is *planned*.

### 5.2 A2L

ASAM MCD-2 MC output containing:

* `MEASUREMENT` for every measurement, `CHARACTERISTIC` for parameters, value blocks, curves
  and maps, `AXIS_PTS` for axes
* `RECORD_LAYOUT` per datatype and storage category; maps are stored row wise, i.e. the c
  declaration is `[y][x]` and the a2l index mode is `ROW_DIR`
* `AXIS_DESCR` with `COM_AXIS` and `AXIS_PTS_REF` for the axis of a curve or map
* `COMPU_METHOD` shared between objects with the same conversion and unit, `COMPU_VTAB` per
  enum
* one `GROUP` per component, referencing the measurements and characteristics it declares
* the address field of every object taken from the address information (`ECU_ADDRESS` is
  the keyword the format uses for it), `SYMBOL_LINK` always

Selectable output versions (1.5.1, 1.6, 1.7), `FUNCTION` and nested groups, `IF_DATA` for
XCP/CCP with measurement rasters, and a2l *import* for migration and merging are *planned*.

## 6 Address information

The addresses of the generated objects are only known after linking. DDD accepts a symbol to
address map in json form. Reading the linker output directly (ELF/DWARF, IEEE-695) and
cross-checking the linked symbols against the declarations is *planned*.

## 7 Tool interface

DDD is a command line tool, so that it can be driven from make, batch and ci jobs. It offers
at least: checking a project, comparing two deliveries, generating the artefacts, listing the
resolved data objects,
writing out the data dictionary itself, validating and explaining names against the naming
convention and completing partially typed ones, printing the json schema of the file formats
and of the dictionary, listing the available checks, and reporting where its build system
integration and its example templates live. Every command that reports findings can produce machine readable
json, and the exit code distinguishes clean runs, findings and usage errors. A findings exit
is reserved for findings reported *as errors*: a run whose findings are all warnings is a
clean run unless `--strict` says otherwise.

The data dictionary shall be writable and readable as json, so that a generator DDD does not
ship can consume it without depending on the implementation.

### 7.1 Build system integration

DDD ships a CMake module which registers the description of a component on its target and
collects, for an image, the descriptions of the components that image actually links. It
generates into the build tree, exposes the generated headers to the components through an
interface library and compiles the single definition file into the image. Registering a
component and generating for an image shall each take one call.

## 8 Implementation status

| section | status |
| --- | --- |
| 3.1 project description, includes, sub-projects | implemented |
| 3.2 component description, scopes, conditions | implemented |
| 3.3 measurements, parameters, value blocks, curves, maps, axes | implemented |
| 3.4 conversions incl. enums | implemented |
| 3.5 naming convention | implemented (`ddd name`, `ddd complete`, `naming` check) |
| 3.6 memory placement | planned |
| 4 consistency checks | implemented |
| 5.1 c code generation from project templates | implemented (`--template-dir`, `ddd templates-dir`); per-file assignment planned |
| 5.2 a2l generation | implemented for 1.6.1; other versions, `FUNCTION`, `IF_DATA`, import planned |
| 4.1 comparing two deliveries | implemented (`ddd compare`, `ddd check --baseline`) |
| 6 address information | json map implemented, ELF/DWARF import planned |
| 7 command line interface | implemented |
| 7 data dictionary as a published contract | implemented (`ddd dump`, `ddd schema dictionary`) |
| 7.1 build system integration | implemented (`cmake/Ddd.cmake`, `ddd cmake-dir`) |
