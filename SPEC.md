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
be defined and declared by DDD. The tool generates the c code defining every global variable
of the project, which the example templates emit as a single file for the reasons section 5.1
gives, and which is compiled and linked into the firmware exactly once.

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

All description files used by DDD contain simple json formatting and shall be named
`*.ddd.json`, so that a description file is recognisable as such in a project that contains
json for many other purposes. The top level key of a file decides what the file is: `project` or
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
| `kind` | required | `measurement`, `parameter`, `value_block`, `curve`, `map` or `axis` |
| `datatype` | required | `boolean`, `uint8`, `sint8`, `uint16`, `sint16`, `uint32`, `sint32`, `uint64`, `sint64`, `float32`, `float64` |
| `description` | `""` | offered to the c templates as the text of a comment, long identifier in the a2l |
| `unit` | `""` | physical unit |
| `conversion` | identity | raw to physical conversion, section 3.4 |
| `limits` | derived | physical `min`/`max`; when omitted they follow from the datatype and the conversion, and for an `enum` from the smallest and largest enumerator |
| `init` | `null` | raw initial value; `null` means implicit zero initialisation |
| `a2l` | export | `export`, `format`, `display_identifier` |
| `volatile` | required | whether the generated c carries `volatile`, i.e. whether the value can change without the reading code having written it |

`volatile` has no default because there is nothing to derive one from: unlike `limits`, which
follow from the datatype and the conversion, it states something about the running system that
only the project knows. A measurement needs it when an interrupt, a second core or a
peripheral writes the variable; a calibration object needs it when a calibration tool is to
change the value while the software runs. Both answers have a price, and the tool asks rather
than picks one silently.

Kind specific attributes:

| kind | additional keys | storage | a2l |
| --- | --- | --- | --- |
| `measurement` | `dimensions` | writable ram variable | `MEASUREMENT` |
| `parameter` | - | `const` or `const volatile` scalar | `CHARACTERISTIC ... VALUE` |
| `value_block` | `dimensions` (mandatory) | `const` or `const volatile` array | `CHARACTERISTIC ... VAL_BLK` |
| `axis` | `size` (mandatory), `input` | `const` or `const volatile` array `[size]` | `AXIS_PTS` |
| `curve` | `axis` | `const` or `const volatile` array `[size of the axis]` | `CHARACTERISTIC ... CURVE` |
| `map` | `x_axis`, `y_axis` | `const` or `const volatile` array `[size of y][size of x]` | `CHARACTERISTIC ... MAP` |

* `dimensions` is a list of array dimensions, e.g. `[3, 4]` for `x[3][4]`. In the a2l the
  same object is described by a `MATRIX_DIM` listing the fastest running index first, i.e.
  in the reverse order - describing it in c order would state a transposed object.
* `init` is a scalar or a nested list matching the shape of the object. A scalar given for an
  array shaped object initialises every element.
* `axis`, `x_axis` and `y_axis` name an object of kind `axis` declared anywhere in the
  project; the axis is shared between all curves and maps referring to it (a2l `COM_AXIS`).
* `input` names the measurement that indexes an axis (a2l input quantity); when omitted the
  a2l uses `NO_INPUT_QUANTITY`.
* Calibration objects (everything except `measurement`) are always generated `const`, since
  the software never writes them, and additionally `volatile` when the declaration says so.
  An object a calibration tool changes in a running ecu needs both: plain `const` entitles the
  compiler to fold the initial value into the code that reads it wherever that value is
  visible at the point of the read, which within one translation unit is every optimisation
  level, `-O0` included, since the substitution happens in the c front end rather than in an
  optimiser, and which link time optimisation extends across translation units. Where the
  load does survive - a component reading through the generated header of another, compiled
  without `-flto` - `const` still lets the compiler serve two reads from one of them and move
  it across a call. Either way the tool writes a value the software does not pick up. What `const volatile` costs is the read only memory: the compiler
  treats every read as a side effect and drops the object out of the read only category, so
  it is emitted into a writable section instead of `.rodata` - measured with gcc 12.2.0, and
  worth confirming on the toolchain a project ships with - which on a flash target means a ram
  address with a load region and a startup copy that overwrites what the tool wrote unless the
  linker script says otherwise. DDD states no preference between the two and reports
  nothing about the choice: a project that calibrates online states `true` and places the
  object itself in its linker script, DDD's own memory placement being planned rather than
  implemented (section 3.6), and one that does not states `false` and keeps its data in flash.
* `volatile` buys freshness and gives up coherence, which is worth knowing before turning it
  on for a whole dictionary: the compiler has to re-read the object at every mention, so a set
  of parameters read at several points of one control step can straddle a calibration write
  and be used half old and half new, and a loop over a `const volatile` value is not
  vectorised.

#### 3.3.1 What each declaration of one object may state

Several components declare the same object, and the keys of a definition do not all mean the
same thing on each of those declarations. They fall into three groups.

**Interface** - `kind`, `datatype`, `unit`, `conversion`, the shape (`dimensions` or `size`),
the referenced axes, and `volatile`. Every declaration shall state the same thing and a
disagreement is `definition-mismatch`. `volatile` is interface rather than storage because it
reaches every consumer's header as a type qualifier and tells their code whether the value can
change under it; two components disagreeing about it would compile different assumptions about
the same address. Being required on every definition, it is stated by every declaration, so
there is always an answer to compare rather than a silence to interpret. `limits` are the one
interface key a declaration may leave out, because DDD derives them from the datatype and the
conversion: omitting them defers to whoever states them, and only two *stated* sets of limits
can disagree.

**Storage** - `init`. What a variable starts out as is decided by the component that produces
it, so a declaration whose scope is `input` shall not state one at all (`consumer-storage`).
This is not an opinion to be outvoted: it is a claim over storage the component does not own,
and it is reported where it is written rather than where it is overruled.

**Presentation** - the `a2l` block, which no generated c depends on. `format` and
`display_identifier` are taken from the producer, and a consumer stating something else is
told so by `storage-mismatch`. `export` is the exception, and in the other direction: any
component may state it, whether it produces the object or not, because which signals a
calibration engineer needs to see is not a property of whoever happens to write the variable -
a component reading a value out of a library it does not own has as good a claim to measuring
it. The stated answers are combined rather than ranked. The object is exported if any
declaration states `true`, and left out only when every declaration that speaks states
`false`; unstated everywhere, it is exported. Two consumers can therefore never conflict over
it, there is no finding to invent for a disagreement between them, and the verdict does not
depend on which components an image happens to link. A dictionary that omits the `a2l` block
altogether therefore exports its objects, which is what makes an older or third party
dictionary readable without rewriting it.

`description` is per declaration and free: two components may describe the same object in
their own words, and DDD does not compare them. `condition` is per declaration as well but
should agree, and `condition-mismatch` says so as a warning rather than an error, since
components legitimately guarded by different expressions is a thing a project does.

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

### 3.7 Build record

A build knows two things no description file records: which project description DDD is run
on, and under which severity policy. In the collected mode of the CMake integration the
project description is not even in the source tree - it is assembled in the build directory
out of the c link closure, so which components belong together is a property of the build
rather than of any file somebody wrote. A build shall therefore write a record of how it runs
DDD (`ddd build-info`), so that a tool outside the build can check exactly what the build
checks instead of re-deriving a project from the file tree and guessing at the severities.
The language server of section 7.2 is the reader this exists for.

The file is named `ddd-build.json` and lives beside the artefacts of the target that wrote
it. It is deliberately *not* named `*.ddd.json`: that extension means "a DDD description
file", `file-extension` enforces it, and `file-kind` would then reject this content for
having none of the top level keys a description may have. It is a document *about* a project
rather than one.

| key | meaning |
| --- | --- |
| `format` | version of this document format, raised only when its shape changes |
| `project` | absolute path of the project description the build runs DDD on; absolute because this file lives in the build tree while the project may not |
| `image` | the build target the record was written for; a component linked into both a firmware and a test binary belongs to two projects, which need not agree about it |
| `strict` | whether the build reports warnings as errors |
| `severity` | the severity overrides the build applies, as `check=severity`, in the order given |

The path in `project` is recorded and never checked when the record is written: in the
collected mode the description is produced at the end of the configure run, after the process
that writes this file, so requiring it to exist would fail every first configure.

Unlike the description formats and the data dictionary, this document has no published json
schema. Nobody authors it - a build writes it and a tool reads it - so the schema would serve
neither an editor nor a hand. Its `format` key is what a reader checks instead, and a record
it does not understand is one it declines rather than misreads.

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
  volatility, referenced axes, or on limits where both of them state limits: a declaration
  that omits limits defers to the producer rather than disagreeing with it, a relaxation
  `volatile` has no use for, being required on every definition (section 3.3.1)
* `duplicate-declaration` - a component declares the same variable more than once
* `consumer-storage` - an `input` declaration states `init`. What a variable starts out as is
  decided by the component that produces it, so a reader stating one is claiming storage it
  does not own, rather than holding an opinion to be outvoted
* `duplicate-component` - two files declare the same component name
* `duplicate-type` - two files declare the same structured datatype name
* `unknown-type`, `type-cycle` - a structure member nests a structure that does not exist, or
  structures nest each other so that neither has a size
* `enum-conflict` - one enum name is used with different enumerators
* `init-invalid` - an initial value or an enumerator does not fit the datatype or the shape
* `unknown-reference`, `reference-kind` - a curve, map or axis refers to an object that does not exist or has the wrong kind
* `reserved-identifier` - a name collides with a c keyword or with an identifier one of the
  headers the generated code includes already declares
* `name-collision` - two names that are distinct in the description files become the same
  c identifier or the same generated file: enumerators of different enums, an enumerator and
  a variable, a variable and the name of an enum, or two component names differing only in
  case
* `naming` - a declared name does not follow the naming convention of the project
* `file-extension` - a description file is not named `*.ddd.json`
* `json-syntax`, `schema`, `file-kind`, `file-not-found`, `include-cycle` - the file tree
  cannot be read; these five are the ones whose severity cannot be changed
* `include-empty` - an include pattern matches no file; relaxable, because a pattern that is
  legitimately empty in one variant of a project is a normal thing to allow

Warnings:

* `storage-mismatch` - components disagree on how the a2l presents the object; the producer
  wins
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
* `changed-storage` - the initial value or the volatility changed; on a calibration object the
  volatility also decides whether a tool can still change the value in a running ecu, and
  which memory the object ends up in
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
variables and calibration objects are `const`, each of them additionally `volatile` when its
declaration states so, a declaration that carries a condition is offered with that condition
so it can be wrapped in `#if` / `#endif`, and input objects are optionally marked `const` for
the consumer header so that a write access does not compile. The qualifier reaches the hand
written code that reads the object, so a project that turns `volatile` on for an array finds
that passing it to a helper typed for a plain `const` one no longer compiles and re-types the
helper - the cast that would silence it is itself refused by a warning set containing
`-Wcast-qual`.

The example templates generate the definitions into one file per project and the declarations
into one header per component, and the build integration of section 7.1 expects that
arrangement. The asymmetry is deliberate: splitting the declarations is what enforces the
access rules, since a component sees the objects it declared and a reference to any other
global is an undeclared identifier, whereas splitting the definitions enforces nothing - after
linking there are only symbols. Three things argue for the single file instead.

Every object has a definition site. The objects of a project partition by owner, so a file per
owner would cover all of them but the ones no component owns - which arise whenever
`missing-producer` is relaxed, to generate a single component on its own or an image that
deliberately links a subset of the project. Those objects have no component and would have no
file; the project wide file defines them like any other.

The build system can name what it compiles. The rule above lets it derive the generated files
from the template directory, and a `{component}` template is the one entry it cannot resolve,
since the component names come out of the description files and, for an image, the subset that
matters comes out of its link graph. A generated header survives that because a consumer
depends on the directory it lives in rather than on its name; a source has to be named before
it can be compiled.

The definitions reach the image whole. An object that no compiled code references - a
measurement only the calibration tool reads - has nothing to pull it out of a library archive,
so the definitions are compiled as a unit of their own and linked into the image rather than
into the libraries of the components that own them. A definition file per component invites
the second arrangement, in which the linker drops precisely the objects nobody but the
calibration tool reads, and the a2l is left describing storage the image does not contain.

None of this forbids the arrangement: a `{component}` template renders a `.c` as readily as a
`.h`. A project that wants its definitions spread over several files may also write several
project wide templates, each rendering the part it selects, and the build integration compiles
every one of them; per-component sources it does not compile, for the reason above.

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
and of the dictionary, recording how a build is configured to run DDD (`ddd build-info`) so
that a tool outside the build can apply the same project and the same severities, serving the
checks to an editor over the Language Server Protocol (`ddd lsp`), listing the
available checks, and reporting where its build system
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
interface library and compiles the generated definition sources into the image as an object
library of their own, so that an object no compiled code references is not dropped
(section 5.1). Registering a component and generating for an image shall each take one call.

### 7.2 Editor integration

The checks shall also be served over the Language Server Protocol (`ddd lsp`), so that a
project is checked while it is written rather than when it is built. The same loader, the same
analysis and the same severity policy answer both, since an editor that disagrees with the
build about what is wrong is worse than an editor that says nothing.

The server offers, from a description file: the findings of section 4, drawn over the key they
are about rather than over the file; go to definition and find references across files, which
is the question a schema cannot answer at all - the producer of an `input` is in a file the
author may not know the name of; a summary of a data object on hover; renaming an object
everywhere the project writes it, refused up front for a name the c namespace cannot take; and
quick fixes that reconcile one key across the declarations of one object, in either direction,
including removing a key the others do not have.

Which project a file belongs to comes from the build records of section 3.7, found under the
build directories the client names. A file belonging to no configured build is still checked,
on its own, with the checks that need every component of a project held back: a component read
alone has inputs nobody produces and outputs nobody reads by construction rather than by
mistake, and reporting those buries the findings that are about the file in front of the
reader. Each check declares whether it needs the whole project, so the two modes cannot drift
apart.

An editor extension shall do no more than launch the server and point it at the build
directories: everything a reader sees is the tool's answer, so that an editor DDD ships
nothing for is not a second class one.

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
| 3.7 build record | implemented (`ddd build-info`, written by `ddd_generate`) |
| 7.2 editor integration | implemented (`ddd lsp`: diagnostics, navigation, hover, rename, quick fixes; VS Code launcher extension) |
