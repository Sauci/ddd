# DDD Specification

- [DDD Specification](#ddd-specification)
  - [1 Introduction](#1-introduction)
    - [1.1 Requirement words](#11-requirement-words)
    - [1.2 Interface specification](#12-interface-specification)
    - [1.3 Consistency check](#13-consistency-check)
    - [1.4 Source code generation](#14-source-code-generation)
    - [1.5 Calibration tool support](#15-calibration-tool-support)
    - [1.6 Position in the build process](#16-position-in-the-build-process)
  - [2 Concepts](#2-concepts)
    - [2.1 Scope](#21-scope)
  - [3 File formats](#3-file-formats)
    - [3.1 Project description](#31-project-description)
    - [3.2 Software component description](#32-software-component-description)
    - [3.3 Data object definition](#33-data-object-definition)
      - [3.3.1 One object, several declarations](#331-one-object-several-declarations)
        - [3.3.1.1 Interface](#3311-interface)
        - [3.3.1.2 Storage](#3312-storage)
        - [3.3.1.3 Presentation](#3313-presentation)
        - [3.3.1.4 Description and condition](#3314-description-and-condition)
      - [3.3.2 Naming a declared type](#332-naming-a-declared-type)
    - [3.4 Conversions](#34-conversions)
    - [3.5 Memory placement *(planned)*](#35-memory-placement-planned)
    - [3.6 Build record](#36-build-record)
    - [3.7 Type description](#37-type-description)
  - [4 Consistency checks](#4-consistency-checks)
    - [4.1 Comparing two deliveries](#41-comparing-two-deliveries)
  - [5 Generated artefacts](#5-generated-artefacts)
    - [5.1 C code](#51-c-code)
    - [5.2 A2L](#52-a2l)
  - [6 Address information](#6-address-information)
  - [7 Tool interface](#7-tool-interface)
    - [7.1 Build system integration](#71-build-system-integration)
    - [7.2 Editor integration](#72-editor-integration)
  - [8 Implementation status](#8-implementation-status)

## 1 Introduction

The objective of DDD is to handle global data in the scope of an embedded software
development project. It **shall** support component-based development methods, where individual
components can be developed by different developers working in separate teams/companies.

The interfaces between the software-components consist simply in reading from / writing to
global data. DDD **shall** provide tools to avoid issues commonly associated with extensive
use of global data.

DDD covers a central role in the firmware build process: it is the single place where the
data of a project is declared, it emits the C code that allocates that data, and it emits
the ASAM MCD-2 MC description that lets measurement and calibration tools work with it. On
top of that it enforces the component interface rules: ownership, scope and agreement
between the components that share the data.

DDD is not tied to any industry. The terms used throughout this document - target, firmware,
measurement, calibration parameter - describe the roles the data plays, not the kind of
device the software runs on.

### 1.1 Requirement words

This specification uses its requirement words with fixed meanings:

| word | meaning |
| --- | --- |
| **shall**, **shall not** | a binding requirement on DDD; an implementation that does otherwise does not conform |
| **must**, **must not** | a validity constraint on data handed to DDD; a violation is reported - under the named check for description data, as a usage error for a command line input - rather than making the tool non-conforming |
| **should**, **should not** | a recommendation; deviation is allowed but wants a reason |
| **may** | a permission: genuinely optional, neither required nor recommended |
| **can** | a statement of capability or possibility, carrying no requirement |

Plain present tense describes the specified behaviour of DDD and binds like **shall** -
"the matches are processed in sorted order" requires exactly that; the explicit words mark
the sentences where the kind of obligation is the point. They are set in bold wherever they
bind; set plain, they are ordinary English.

### 1.2 Interface specification

DDD allows the software developer to clearly specify the (global data) interface of a
software-component. The scope of each data object can be defined (input/output/local of the
component, [section 2.1](#21-scope)). The specification also includes physical units, scaling
information for fixed-point datatypes, enums etc. ([section 3.3](#33-data-object-definition)).

### 1.3 Consistency check

When assembling several components into a complete project, DDD ensures consistency of the
global data interfaces. It checks that each data object is produced by only one component,
and that components which consume inputs agree on datatypes/units/scaling etc.
([section 4](#4-consistency-checks)).

### 1.4 Source code generation

In order to enforce the access rules specified for each component, the global data objects **shall**
be defined and declared by DDD. The tool generates the C code defining every global data object
of the project, which the example templates emit as a single file for the reasons [section 5.1](#51-c-code)
gives, and which is compiled and linked into the firmware exactly once.

DDD **shall** also generate a declaration C header for each software component. This
header **shall** only contain declarations for the data objects specified in the interface
description of the component.

### 1.5 Calibration tool support

DDD **shall** support the A2L file format (ASAM MCD-2 MC), to integrate the resulting software into
common measurement and calibration tools ([section 5.2](#52-a2l)). This covers both directions of the data model:
values the tool *measures*, and values the tool *calibrates* - single parameters, value
blocks, curves, maps and their axes.

### 1.6 Position in the build process

```text
  component JSON files
          |
          v
    +-----------+   .c/.h    +--------------+   .elf    +---------------+
    |    DDD    |----------->| compile/link |---------->| address import|
    +-----------+            +--------------+           +-------+-------+
          |                                                     |
          |  A2L  <-------------------------------------------- +
          v
   calibration tool
```

DDD is run once per build to generate the artefacts, the A2L among them: without address
information every object carries address zero, and `SYMBOL_LINK` names the symbol either way
([section 6](#6-address-information)). A build that wants the A2L to carry the real
addresses - they exist only after linking - runs DDD a second time with a map taken from the
linker output; one that does not need them stops after the first.

## 2 Concepts

| term | meaning |
| --- | --- |
| **project** | a named set of components and/or sub-projects |
| **component** | a software unit with an explicitly declared data interface |
| **image** | one linked binary; the components it actually links decide which objects it carries, and one component can be linked into several images ([section 3.6](#36-build-record)) |
| **declaration** | one entry of a component interface: a scope, an optional condition and a definition |
| **definition** | the part of a declaration that says what the object is - kind, datatype, shape, conversion and the rest of [section 3.3](#33-data-object-definition) |
| **data object** | the thing being declared: a measurement, parameter, value block, curve, map or axis |
| **measurement** | a data object the software writes and reads - the producer writing, consumers reading - and a calibration tool can do both as well |
| **calibration object** | a data object the software never writes - a parameter, value block, curve, map or axis - generated `const` and changed, if at all, by a calibration tool |
| **scope** | ownership and visibility of a data object with respect to the declaring component |
| **producer** | the component that owns a data object; its declaration is the authoritative one |
| **consumer** | a component that declares a data object as its `input`; it reads what another component produces |
| **declared type** | a scalar or structure a types file declares ([section 3.7](#37-type-description)), named by `datatype` where a base datatype would stand |
| **access path** | the C expression that reads a member of a structured object - `Inlet.cell[2].raw` - and the name the A2L and the address map know it by ([section 5.2](#52-a2l)) |
| **conversion** | the rule that maps the raw (implementation) value to the physical value |
| **check** | one consistency rule, with a stable identifier and a default severity ([section 4](#4-consistency-checks)) |
| **finding** | one reported violation of a check, located where it is written; findings reported as errors fail the run ([section 7](#7-tool-interface)) |
| **data dictionary** | the resolved result: every object with its owner, users, shape and limits worked out. It is the contract between the checking front end and the output backends, and DDD publishes it |
| **delivery** | the archived data dictionary of one shipped state of a project; [section 4.1](#41-comparing-two-deliveries) compares two of them |

### 2.1 Scope

| scope | meaning |
| --- | --- |
| `input` | the component reads the object; another component has to produce it |
| `output` | the component owns the object; exactly one component **may** do so |
| `local` | the component owns the object exclusively; no other component **may** use it |

For measurements, `output` means the component writes the variable. For calibration objects,
which the software never writes, `output` means the component provides the data and other
components **may** read it; `local` is the normal choice for data that only parametrises the
owning component.

## 3 File formats

All description files used by DDD contain simple JSON formatting, encoded UTF-8 - a byte
order mark is tolerated on reading, since Windows editors like to prepend one - and **must** be
named `*.ddd.json` (`file-extension`), so that a description file is recognisable as such in a project that
contains JSON for other purposes. The top level key of a file decides what the file is:
`project` ([section 3.1](#31-project-description)), `component` ([section 3.2](#32-software-component-description))
or `types` ([section 3.7](#37-type-description)). Unknown keys
are rejected, with one exception: a top level `$schema` key **shall** be accepted and ignored,
since it is the standard way an editor binds a JSON file to its schema and thereby turns the
published contract into completion, hover documentation and as-you-type validation. The
formal contract is published by the tool itself as a JSON schema (`ddd schema`), one file
per format - project, component, types and the data dictionary - and every authored
field of it **shall** carry its documentation. The binding is per file rather than per directory
because the kind of a description is in its content and not in its name.

### 3.1 Project description

Contains a list of components, types files and/or other (sub-)projects.

```json
{
  "project": {
    "name": "DemoDevice",
    "description": "optional",
    "includes": ["components/*.ddd.json", "subsystems/logging/logging.ddd.json"]
  }
}
```

* `"name"` - C identifier of the project, also used as A2L project and module name
* `"description"` - optional free text
* `"includes"` - paths to component, types or sub-project files, relative to this file. The
  kind of each included file is detected from its content. A file reached through several
  paths is loaded once - identity being the resolved path: absolute, symlinks followed, case
  compared as the platform compares it - and include cycles are an error.

An entry of `includes` containing one of `*`, `?` or `[` is a wildcard pattern, expanded
with the usual shell rules: `*` and `?` match within one path component, `[...]` is a
character class, and `**` matches directories recursively. Only regular files are matched,
and the matches are processed in sorted order of their resolved paths, so which component
loads first does not depend on how a file system happens to enumerate a directory. A
pattern that matches nothing is `include-empty`. An entry without a wildcard character is a
literal path naming exactly one file, and if that file does not exist the finding is
`file-not-found` rather than `include-empty` - a pattern **may** legitimately be empty, a named
file **may** not be missing.

### 3.2 Software component description

The top level key `"component"` is mandatory, and it contains the following elements:

* `"name"` The name of the component - a C identifier, since it becomes the name of a
  generated header and of an A2L group; every component of a project needs a distinct one
* `"description"` Optional free text
* `"declarations"` A list of declarations; each declares one data object

Each declaration contains:

* `"scope"` One of input/output/local, indicating the scope of the declaration
  ([section 2.1](#21-scope))
* `"condition"` A C preprocessor conditional expression which will wrap the generated
  declarations of the object (optional; [section 3.3.1](#331-one-object-several-declarations))
* `"definition"` A definition object ([section 3.3](#33-data-object-definition))

### 3.3 Data object definition

A definition describes one data object. The key `"kind"` selects the type of object and is
required on every definition, including a `"measurement"`: a defaulted discriminator leaves
the published JSON schema unable to say which variant an unmarked definition is, which an
editor validating a file against that schema reports as an ambiguity.

Attributes common to every kind:

| key | default | meaning |
| --- | --- | --- |
| `name` | required | C identifier of the object |
| `kind` | required | `measurement`, `parameter`, `value_block`, `curve`, `map` or `axis` |
| `datatype` | required | `boolean`, `uint8`, `sint8`, `uint16`, `sint16`, `uint32`, `sint32`, `uint64`, `sint64`, `float32`, `float64` |
| `description` | `""` | offered to the C templates as the text of a comment, long identifier in the A2L |
| `unit` | `""` | physical unit |
| `conversion` | identity | raw to physical conversion, [section 3.4](#34-conversions) |
| `limits` | derived | physical `min`/`max`; when omitted they follow from the datatype and the conversion, and for an `enum` from the smallest and largest enumerator |
| `init` | `null` | raw initial value; `null` means implicit zero initialisation |
| `a2l` | export | `export`, `format`, `display_identifier` |
| `volatile` | required | whether the generated C carries `volatile`, i.e. whether the value can change without the reading code having written it |

`volatile` has no default because there is nothing to derive one from: unlike `limits`, which
follow from the datatype and the conversion, it states something about the running system that
only the project knows. A measurement needs it when an interrupt, a second core, a
peripheral or a calibration tool writes the variable; a calibration object needs it when a
calibration tool is to change the value while the software runs. Both answers have a price, and the tool asks rather
than picks one silently.

The `a2l` block holds what only the calibration tool sees: `export` decides whether the
object appears in the A2L at all ([section 3.3.1](#331-one-object-several-declarations)); `format` is the display format, written as
`%`, an optional total width, `.` and the number of decimals - `"%5.2"`, `"%.3"` - and
`display_identifier` is an alternative display name, a C identifier. The latter two are
emitted as the A2L keywords of the same names when stated, and left out of the A2L when not.

`boolean` is one byte holding 0 or 1: its raw range - and, under the identity conversion, its
derived limits - is 0..1, the generated C type is `bool` (`<stdbool.h>` is included where
needed), the A2L describes it as `UBYTE`, and it does not count as an integer datatype for an
enum conversion.

Kind specific attributes:

| kind | additional keys | storage | A2L |
| --- | --- | --- | --- |
| `measurement` | `dimensions` | writable RAM variable | `MEASUREMENT` |
| `parameter` | - | `const` or `const volatile` scalar | `CHARACTERISTIC ... VALUE` |
| `value_block` | `dimensions` (mandatory) | `const` or `const volatile` array | `CHARACTERISTIC ... VAL_BLK` |
| `axis` | `size` (mandatory), `input` | `const` or `const volatile` array `[size]` | `AXIS_PTS` |
| `curve` | `axis` (mandatory) | `const` or `const volatile` array `[size of the axis]` | `CHARACTERISTIC ... CURVE` |
| `map` | `x_axis`, `y_axis` (both mandatory) | `const` or `const volatile` array `[size of y][size of x]` | `CHARACTERISTIC ... MAP` |

* `dimensions` is a list of array dimensions, e.g. `[3, 4]` for `x[3][4]`; a measurement
  without it is a scalar. In the A2L the same object is described by a `MATRIX_DIM` listing
  the fastest running index first, i.e. in the reverse order - describing it in C order
  would state a transposed object.
* `init` is a scalar or a nested list matching the shape of the object. A scalar given for an
  array shaped object initialises every element.
* `axis`, `x_axis` and `y_axis` name an object of kind `axis` declared anywhere in the
  project; the axis is shared between all curves and maps referring to it (A2L `COM_AXIS`).
  Referring is not using: the reference resolves against every declaration of the project
  and obliges the referring component to nothing, so an axis no `input` declaration reads is
  still `unused-output`, and a component that wants the axis in its own header declares it
  as its `input`.
* `input` names the measurement that indexes an axis (A2L input quantity); when omitted the
  A2L uses `NO_INPUT_QUANTITY`.
* Calibration objects (everything except `measurement`) are always generated `const`, since
  the software never writes them, and additionally `volatile` when the declaration says so.
  An object a calibration tool changes in a running ECU needs both: plain `const` entitles the
  compiler to fold the initial value into the code that reads it wherever that value is
  visible at the point of the read, which within one translation unit is every optimisation
  level, `-O0` included, since the substitution happens in the C front end rather than in an
  optimiser, and which link time optimisation extends across translation units. Where the
  load does survive - a component reading through the generated header of another, compiled
  without `-flto` - `const` still lets the compiler serve two reads from one of them and move
  it across a call. Either way the tool writes a value the software does not pick up. What `const volatile` costs is the read only memory: the compiler
  treats every read as a side effect and drops the object out of the read only category, so
  it is emitted into a writable section instead of `.rodata` - measured with GCC 12.2.0, and
  worth confirming on the toolchain a project ships with - which on a flash target means a RAM
  address with a load region and a startup copy that overwrites what the tool wrote unless the
  linker script says otherwise. DDD states no preference between the two and reports
  nothing about the choice: a project that calibrates online states `true` and places the
  object itself in its linker script, DDD's own memory placement being planned rather than
  implemented ([section 3.5](#35-memory-placement-planned)), and one that does not states `false` and keeps its data in flash.
* `volatile` buys freshness and gives up coherence, which is worth knowing before turning it
  on for a whole dictionary: the compiler has to re-read the object at every mention, so a set
  of parameters read at several points of one control step can straddle a calibration write
  and be used half old and half new, and a loop over a `const volatile` value is not
  vectorised.

#### 3.3.1 One object, several declarations

Several components declare the same object, and the keys of a definition do not all mean the
same thing on each of those declarations. They fall into three groups.

A project that relaxes `missing-producer` can hold objects no component produces
([section 5.1](#51-c-code)). Everywhere the rules below say "the producer", such an object
falls back to its first declaration in load order - includes order, wildcard matches sorted
([section 3.1](#31-project-description)) - so the resolved answer is stable rather than an
accident of the file system.

##### 3.3.1.1 Interface

`kind`, `datatype`, `unit`, `conversion`, the shape (`dimensions` or `size`), the referenced
objects - `axis`, `x_axis`, `y_axis` and the `input` of an axis - and `volatile`. Every
declaration **must** state the same thing and a
disagreement is `definition-mismatch`. `volatile` is interface rather than storage because it
reaches every consumer's header as a type qualifier and tells their code whether the value can
change under it; two components disagreeing about it would compile different assumptions about
the same address. Being required on every definition, it is stated by every declaration, so
there is always an answer to compare rather than a silence to interpret. `limits` are the one
interface key a declaration **may** leave out, because DDD derives them from the datatype and the
conversion: omitting them defers to whoever states them, and only two *stated* sets of limits
can disagree.

##### 3.3.1.2 Storage

`init`. What an object starts out as is decided by the component that produces it, so a
declaration whose scope is `input` **must not** state one at all (`consumer-storage`).
This is not an opinion to be outvoted: it is a claim over storage the component does not own,
and it is reported where it is written rather than where it is overruled.

##### 3.3.1.3 Presentation

The `a2l` block, which no generated C depends on. `format` and
`display_identifier` are taken from the producer, and a consumer stating something else is
told so by `storage-mismatch`. (The check names of [section 4](#4-consistency-checks) use *storage* more broadly than
this section's groups - `storage-mismatch` polices presentation, and `changed-storage` of
[section 4.1](#41-comparing-two-deliveries) covers the volatility too. Identifiers are pinned once published; where the
words differ, the groups of this section are the precise statement.) `export` is the exception, and in the other direction: any
component **may** state it, whether it produces the object or not, because which signals a
calibration engineer needs to see is not a property of whoever happens to produce the object -
a component reading a value out of a library it does not own has as good a claim to measuring
it. The stated answers are combined rather than ranked. The object is exported if any
declaration states `true`, and left out only when every declaration that speaks states
`false`; unstated everywhere, it is exported. Two consumers can therefore never conflict over
it, there is no finding to invent for a disagreement between them, and the verdict does not
depend on which components an image happens to link. A dictionary that omits the `a2l` block
altogether therefore exports its objects, which is what makes an older or third party
dictionary readable without rewriting it.

##### 3.3.1.4 Description and condition

`description` is per declaration and free: two components **may** describe the same object in
their own words, and DDD does not compare them. The producer's text is the one that reaches
the generated C comment and the A2L long identifier; a consumer's text reaches no output.
`condition` is per declaration as well but **should** agree, and `condition-mismatch` says so as
a warning rather than an error, since components legitimately guarded by different
expressions is a thing a project does. Conditions are compared as text, stripped of
surrounding whitespace - `A && B` and `B && A` are different conditions, since deciding
their equivalence would take a preprocessor - and a declaration stating none disagrees with
one stating some. The dictionary records the producer's condition on the object, and every
declaration's own condition with its declaring component.

#### 3.3.2 Naming a declared type

`datatype` accepts one of the base datatypes **or** the name of a type the project declares in a
types file ([section 3.7](#37-type-description)). One key names a type everywhere - on a component declaration and on a
structure member alike - rather than a second key beside it: a `type` key would have to mean "the
name of a declared type" in those two places and "which shape this entry has" at the top of a
types entry, and one key with one meaning is worth what it costs.

What it costs is that the published schema can no longer say `datatype` is one of eleven values.
A mistyped base datatype is a well formed *name*, so a name that reads as a storage stem with the
digits wrong - `uint166`, `int16`, `float3`, `sint_16` - is refused outright to put the rejection
back where the typo is made. The refused class is precise: one of the stems `bool`, `boolean`,
`int`, `uint`, `sint`, `float`, `double`, `char`, `short`, `long`, `byte`, `word` - compared
without regard to case - followed by nothing but digits and underscores. `Int16_t` and
`intensity` pass; `UINT16` and `word_8` do not. The refusal is part of the published contract,
so it is reported as `schema` rather than under a name of its own, and it applies where a type
is named into being - the `name` of a types file entry - as much as where one is used, so a
type that could never be referenced cannot be declared either. What that cannot catch, a
transposition such as `unit16`, is reported as `unknown-type` with the nearest name suggested.

Naming a type and then restating what it fixes is an error rather than an override, so that "where
is this object's unit written down" has one answer.

A declaration naming a **scalar type** is an ordinary object whose datatype, unit, conversion and
limits come from the type. A declaration naming a **structure** is a structured object: it
generates one C object, and reaches the A2L as one object per member ([section 5.2](#52-a2l)).

### 3.4 Conversions

```json
{ "kind": "identity" }
{ "kind": "linear", "factor": 0.25, "offset": -40.0 }
{ "kind": "enum", "name": "StateA_t", "enumerators": { "STATE_OFF": 0, "STATE_FAULT": 15 } }
```

* `identity` has no further keys.
* `linear` means `physical = raw * factor + offset`; `factor` defaults to 1.0 and **must not** be
  zero, `offset` defaults to 0.0, and both **must** be finite.
* `enum` requires an integer datatype. `name` is required: it is the C identifier of the
  generated `typedef enum`, the identity under which `enum-conflict` compares enumerator
  lists, and the name of the A2L `COMPU_VTAB`. `enumerators` is required and non-empty;
  it **may** also be given as a list of `{"name", "value", "description"}` objects. An enum
  converts nothing - physical and raw value coincide - so the limits of an enum object,
  stated or derived, are enumerator values.
* `kind` **may** be omitted, unlike the `kind` of a definition, because the other keys decide it:
  a conversion stating `enumerators` or `name` is an `enum`, one stating `factor` or `offset`
  is `linear`, and one stating nothing - `{}` - is the identity. Unknown keys are rejected as
  everywhere, so a conversion cannot match two kinds at once.

### 3.5 Memory placement *(planned)*

A `memory` attribute **shall** select the memory the object is placed in
(`ram`, `rom`, `internal_ram`) and optionally name an explicit linker section. The generated
code **shall** carry the corresponding section attribute and the A2L **shall** describe the memory
layout with `MOD_PAR` / `MEMORY_SEGMENT`.

### 3.6 Build record

A build knows two things no description file records: which project description DDD is run
on, and under which severity policy. In the collected mode of the CMake integration
([section 7.1](#71-build-system-integration)) the
project description is not even in the source tree - it is assembled in the build directory
out of the C link closure, so which components belong together is a property of the build
rather than of any file somebody wrote. A build **shall** therefore write a record of how it runs
DDD (`ddd build-info`), so that a tool outside the build can check exactly what the build
checks instead of re-deriving a project from the file tree and guessing at the severities.
The language server of [section 7.2](#72-editor-integration) is the reader this exists for.

The file is named `ddd-build.json` and lives beside the artefacts of the target that wrote
it. It is deliberately *not* named `*.ddd.json`: that extension means "a DDD description
file", `file-extension` enforces it, and `file-kind` would then reject this content for
having none of the top level keys a description **may** have. It is a document *about* a project
rather than one.

| key | meaning |
| --- | --- |
| `format` | version of this document format, raised only when its shape changes; today `1` |
| `project` | absolute path of the project description the build runs DDD on; absolute because this file lives in the build tree while the project **may** not |
| `image` | the build target the record was written for, by name (e.g. `firmware.elf`); a component linked into both a firmware and a test binary belongs to two projects, which need not agree about it |
| `strict` | whether the build reports warnings as errors |
| `severity` | the severity overrides the build applies, as `check=severity` ([section 4](#4-consistency-checks)), in the order given |

The path in `project` is recorded and never checked when the record is written: in the
collected mode the description is produced at the end of the configure run, after the process
that writes this file, so requiring it to exist would fail every first configure.

Unlike the description formats and the data dictionary, this document has no published JSON
schema. Nobody authors it - a build writes it and a tool reads it - so the schema would serve
neither an editor nor a hand. Its `format` key is what a reader checks instead, and a record
it does not understand is one it declines rather than misreads.

### 3.7 Type description

A `types` file declares the types a project names, so that components agree by naming rather
than by each copying out the same answer. It is listed in the `includes` of a project
([section 3.1](#31-project-description)) like a
component file and recognised by its top level key: `types`, a list of entries, each stating
its `type` - `scalar` or `struct`.

```json
{
  "types": [
    {
      "type": "scalar",
      "name": "Temperature_t",
      "datatype": "uint16",
      "unit": "degC",
      "conversion": { "kind": "linear", "factor": 0.1, "offset": -40.0 }
    },
    {
      "type": "struct",
      "name": "Inlet_t",
      "members": [
        { "name": "raw", "member": "value", "datatype": "uint16", "dimensions": [4] },
        { "name": "latest", "member": "value", "datatype": "Temperature_t" },
        { "name": "ready", "member": "bits", "datatype": "uint8", "bits": 2 }
      ]
    }
  ]
}
```

* a **scalar** type fixes `datatype`, `unit`, `conversion` and `limits` - exactly what makes two
  declarations interchangeable, and nothing else. `kind`, `dimensions`, `init`, `volatile` and
  `a2l` stay on the declaration, because two measurements of one type can differ in whether an
  interrupt writes one of them. Its `datatype` is a base datatype: a scalar type cannot be
  declared in terms of a second one, so a chain of aliases - and with it a scalar cycle -
  cannot be written at all.
* a **struct** type declares `members`, in the order they are laid out. `member` states the
  shape of each: a `value` - a datatype, base or declared, optionally an array (`dimensions`) -
  or `bits`, an integer datatype and a width (`bits`). A `bits` member takes no `dimensions`.

A member says what its bytes mean as well as where they are: it carries `unit`, `conversion`
and `limits` of its own, or names a scalar type that fixes them, never both. Its `a2l` block
stays its own either way - a scalar type fixes what a value means, not how a tool displays it.
A member carries no `init` and no `volatile`, which belong to a declaration rather than to a
type, and no `kind`: a storage class qualifies a whole C object, so the declaration decides
and a structure mixing measured and calibrated members is not something this format can
express.

A declaration naming a structure is a `measurement` or a `parameter` - the two kinds that are
plain storage; a `value_block`, `curve`, `map` or `axis` refers to other objects or is an
array of one datatype, and a structure is neither (`type-kind`). A structured measurement **may**
carry `dimensions`: an array of structures contributes its members once per element, each at
its own path. A declaration naming a structure **must not** carry `init` (`type-kind`): an
initial value spelled out per member would restate the structure the type already fixes, so a
structured object is zero initialised, and its values are put there by the running system -
the starting code for a measurement, the calibration tool for a parameter. Of its `a2l`
block, `export` decides for the whole object ([section 3.3.1](#331-one-object-several-declarations)) and each member's own `export` for the member;
`format` and `display_identifier` are per member, a whole structure having no display format
of its own.

Bit positions and member offsets are not stated and never will be. C leaves both to the compiler,
so DDD reads them back out of the build rather than predicting them - which is why the address map
of [section 6](#6-address-information) is keyed on access paths. The limits of a bitfield do follow from its stated width,
since offering a two bit field over the whole range of the word carrying it would invite a value
it cannot hold.

## 4 Consistency checks

Every check has a stable identifier and a default severity. The identifiers are part of the
tool interface - a build script pins them in its severity overrides - so they **shall not** change
once published. The severity of a check can be changed per project run, so that a team can
fine tune its error management policy; the checks that make a file unreadable cannot be
relaxed. The authoritative list is the one the tool prints itself (`ddd checks`).

An override is written `check=severity` (`ddd check -W unused-output=info`), with `error`,
`warning`, `info` and `ignore` as the severities - `ignore` drops the finding entirely. The
option is repeatable; for one check the last override wins, and `--strict` then promotes what
is still a warning to an error. Overriding a check that cannot be relaxed is a usage error
rather than a finding, like naming an unknown check or severity.

Four checks need every component of a project to mean anything - `unknown-type`,
`missing-producer`, `unknown-reference` and `unused-output` - and it is exactly these the
language server holds back when it checks a file belonging to no project ([section 7.2](#72-editor-integration)).

The `schema` check carries every violation of the published file contracts ([section 3](#3-file-formats)), including the
rules this document states in prose - a zero `factor`, an enum conversion on a non-integer
datatype, a key restated that a named type already fixes: they are shape errors of one file,
located where they are written, and need no identifier of their own.

Errors:

* `multiple-producers` - an object is produced by more than one component
* `missing-producer` - an input object is produced by nobody
* `local-conflict` - a component local object is declared by another component as well
* `definition-mismatch` - components disagree on kind, datatype, unit, scaling, shape,
  volatility, referenced objects - axes and the `input` of an axis - or on limits where both
  of them state limits: a declaration
  that omits limits defers to the producer rather than disagreeing with it, a relaxation
  `volatile` has no use for, being required on every definition ([section 3.3.1](#331-one-object-several-declarations))
* `duplicate-declaration` - a component declares the same object more than once
* `consumer-storage` - an `input` declaration states `init`. What an object starts out as is
  decided by the component that produces it, so a reader stating one is claiming storage it
  does not own, rather than holding an opinion to be outvoted
* `duplicate-component` - two files declare the same component name
* `duplicate-type` - two files declare the same type name
* `unknown-type`, `type-kind`, `type-cycle` - a `datatype` names neither a base datatype nor a
  type any file of the project declares, a declared type is used where its shape does not fit,
  or structures nest each other so that neither has a size
* `enum-conflict` - one enum name is used with different enumerators
* `init-invalid` - an initial value or an enumerator does not fit the datatype or the shape
* `unknown-reference`, `reference-kind` - a curve, map or axis refers to an object that does not exist or has the wrong kind
* `reserved-identifier` - a name collides with a C keyword, with a name `<stdint.h>` or
  `<stdbool.h>` declares, or with an identifier the C standard reserves for the
  implementation - a double underscore anywhere, or a leading underscore followed by a
  capital. The set is fixed by the standard rather than read out of any header, so the
  verdict does not depend on a toolchain
* `name-collision` - two names that are distinct in the description files become the same
  C identifier or the same generated file: enumerators of different enums, an enumerator and
  a data object, a data object and the name of an enum or of a declared type, or two component names
  differing only in case
* `file-extension` - a description file is not named `*.ddd.json`
* `json-syntax`, `schema`, `file-kind`, `file-not-found`, `include-cycle` - the file tree
  cannot be read; these five are the ones whose severity cannot be changed
* `include-empty` - a wildcard include matches no file; relaxable, because a pattern that is
  legitimately empty in one variant of a project is a normal thing to allow. A literal
  include naming a missing file is `file-not-found` instead ([section 3.1](#31-project-description))

Warnings:

* `storage-mismatch` - components disagree on how the A2L presents the object; the producer
  wins
* `condition-mismatch` - declarations of one object use different preprocessor conditions
* `unused-output` - an output is read by nobody
* `limits-out-of-range` - limits exceed what the datatype can represent
* `enum-duplicate-value` - two enumerators share a value
* `name-similar` - two object names differ only in upper/lower case
* `a2l-unrepresentable` - an object cannot be fully described by the A2L version DDD writes;
  today that is an array of more than three dimensions, which `MATRIX_DIM` of 1.6.1 cannot
  carry

Information:

* `empty-component` - a component declares no data object at all

### 4.1 Comparing two deliveries

The checks above answer whether a set of components fits together. DDD **shall** also answer
whether one delivery can replace another, which is a different and directional question, and
one that cannot be answered from the description files alone: the delivery being replaced has
moved on. The data dictionary of a delivery is therefore the artefact to archive (`ddd dump`,
[section 7](#7-tool-interface)), and the comparison is a function of two of them.

A change **shall** be graded by what it costs the consumers:

Errors - the consumers of the object become wrong, whether or not they still compile:

* `removed-object` - an object is gone that a component read
* `changed-interface` - kind, datatype, unit, scaling, shape, referenced objects or locality
  changed; locality is whether the object is local to its component ([section 2.1](#21-scope)), since a
  local object becoming shared - or the reverse - changes who **may** use it

Warnings - behaviour or tooling changes, but no consumer becomes wrong:

* `removed-unused-object` - an object is gone that no component read
* `changed-storage` - the initial value or the volatility changed; on a calibration object the
  volatility also decides whether a tool can still change the value in a running ECU, and
  which memory the object ends up in
* `narrowed-limits` - the physical limits got tighter, so calibrated data **may** no longer fit
* `changed-owner` - another component produces the object now
* `changed-condition` - the preprocessor condition changed; the producer's, which is the one
  the dictionary records on the object ([section 3.3.1](#331-one-object-several-declarations))
* `changed-a2l` - the A2L entry changed
* `project-mismatch` - the two dictionaries name different projects, so the baseline is
  probably not the predecessor of this candidate

Information:

* `added-object` - the candidate declares an object the baseline did not

Widening a limit **shall** be silent, since every value the baseline allowed still fits. Limits
that got tighter **shall not** be reported on an object whose interface changed as well: the
interface change is the finding to act on, and the narrowing would only bury it. This is
deliberately coarser than "tighter *as a consequence of* the interface change", which
nothing can decide - an independent narrowing of the same object is therefore also held
back until the interface change is resolved.

## 5 Generated artefacts

### 5.1 C code

The C sources **shall** be rendered from templates the *project* provides, and DDD **shall** ship no
default set. What the generated code looks like - the comment convention, the banner, the
include guards, whether an object is commented and in which form - does not follow
from the declared data: it is the house style of the software the code is generated into, it
differs between projects, and a generator that fixes it imposes one project's habits on every
other. DDD therefore owns the data and the project owns its presentation. Example templates
**shall** be shipped and locatable, as a starting point to copy rather than as a fallback.

The set of generated files **shall** follow from the template directory alone, so that a build
system can declare its outputs without running the generator first:

| template | renders to |
| --- | --- |
| `<name>.jinja2` | `<name>`, once per project |
| `_<name>.jinja2` | nothing; a helper the other templates **may** import |
| `{component}<rest>.jinja2` | one file per component, the component's name replacing the placeholder |

The component name replaces every occurrence of the placeholder verbatim - a component
`SensorHub` renders `{component}.h.jinja2` to `SensorHub.h` - so the case of a generated
file is the case of the component's name. A template in a subdirectory of the template
directory is importable but never rendered. A project template receives two variables:
`filename`, the name of the file being rendered, and `model`, the resolved view of the
dictionary; a `{component}` template additionally receives `header`, the view of its
component. The rendering is strict - a name a template misspells is an error, not silent
empty output.

Whatever the templates spell, the *data* they are given is fixed: measurements are writable
variables and calibration objects are `const`, each of them additionally `volatile` when its
declaration states so, a declaration that carries a condition is offered with that condition
so it can be wrapped in `#if` / `#endif`, and input objects are marked `const` for the
consumer header when the project asks for it (`ddd generate --const-inputs`), so that a
write access does not compile. The qualifier reaches the hand
written code that reads the object, so a project that turns `volatile` on for an array finds
that passing it to a helper typed for a plain `const` one no longer compiles and re-types the
helper - the cast that would silence it is itself refused by a warning set containing
`-Wcast-qual`.

The example templates generate the definitions into one file per project and the declarations
into one header per component, and the build integration of [section 7.1](#71-build-system-integration) expects that
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
calibration tool reads, and the A2L is left describing storage the image does not contain.

None of this forbids the arrangement: a `{component}` template renders a `.c` as readily as a
`.h`. A project that wants its definitions spread over several files **may** also write several
project wide templates, each rendering the part it selects, and the build integration compiles
every one of them; per-component sources it does not compile, for the reason above.

Generated output is deterministic to the byte: objects are sorted by name within their
component's group, member paths by path, components keep the include order of the project,
and wildcard includes expand in sorted order ([section 3.1](#31-project-description)) - the same project generates the
same bytes on any machine. Files are written UTF-8, and a rendered file whose content has not
changed is left untouched, so a regeneration does not cascade into a rebuild.

Assignment of objects to freely chosen generated `.c`/`.h` files is *planned*.

### 5.2 A2L

ASAM MCD-2 MC output containing:

* `MEASUREMENT` for every measurement, `CHARACTERISTIC` for parameters, value blocks, curves
  and maps, `AXIS_PTS` for axes
* `RECORD_LAYOUT` per datatype and storage category; maps are stored row wise, i.e. the C
  declaration is `[y][x]` and the A2L index mode is `ROW_DIR`
* `AXIS_DESCR` with `COM_AXIS` and `AXIS_PTS_REF` for the axis of a curve or map
* `COMPU_METHOD` shared between objects with the same conversion and unit, `COMPU_VTAB` per
  enum
* one `GROUP` per component, referencing the measurements and characteristics it declares
* the address field of every object taken from the address information (`ECU_ADDRESS` is
  the keyword the format uses for it), `SYMBOL_LINK` always; an object the address
  information does not cover keeps address `0x00000000` ([section 6](#6-address-information))
* deterministic order: records sorted by object name, member paths by path, `GROUP`s in the
  component order of the project

A structured object ([section 3.3.2](#332-naming-a-declared-type)) reaches the A2L as one object per value-holding member,
named by its C access path - `Inlet.latest.value`, `Inlet.cell[2].raw` - which is at once the
A2L name, the `SYMBOL_LINK` symbol and the key of the address map ([section 6](#6-address-information)). A member of a
measurement-kind object becomes a `MEASUREMENT`, of a parameter-kind object a
`CHARACTERISTIC` - `VALUE` when scalar, `VAL_BLK` with `MATRIX_DIM` when an array. An array
of structures is expanded element by element instead, one set of members per `[index]`.
Members use the ordinary per-datatype `RECORD_LAYOUT` - the structure itself gets no record
of its own - and the component's `GROUP` references the member paths. A `bits` member reaches
no A2L at all: `SYMBOL_LINK` can carry a byte offset but not a bit position, so a bitfield
waits for a build to report both the word and the bits ([section 8](#8-implementation-status)).

Selectable output versions (1.5.1, 1.6, 1.7), `FUNCTION` and nested groups, `IF_DATA` for
XCP/CCP with measurement rasters, and A2L *import* for migration and merging are *planned*.

## 6 Address information

The addresses of the generated objects are only known after linking. DDD accepts a symbol to
address map in JSON form (`ddd generate --address-map`): one flat JSON object mapping each
symbol to its address. The key is the C identifier of an object or, for the member of a
structured object, its access path - `Inlet.cell[2].raw` - exactly as the A2L names it
([section 5.2](#52-a2l)). The address is a JSON number, or a string read as hexadecimal with a `0x`
prefix and as decimal without, and **must** fit an unsigned 32 bit `ECU_ADDRESS`. A key the
project does not know is ignored, and an object the map does not cover keeps address
`0x00000000` rather than failing the run: a map extracted from a linker output legitimately
omits the objects a condition compiled away, and `SYMBOL_LINK` lets a downstream tool resolve
those it cares about. Reading the linker output directly (ELF/DWARF, IEEE-695) and
cross-checking the linked symbols against the declarations is *planned*.

## 7 Tool interface

DDD is a command line tool, so that it can be driven from make, batch and CI jobs. It offers
at least: checking a project (`ddd check`, [section 4](#4-consistency-checks)), comparing two
deliveries (`ddd compare`, or `ddd check --baseline` for both questions in one exit code;
[section 4.1](#41-comparing-two-deliveries)), generating the artefacts
(`ddd generate`, [section 5](#5-generated-artefacts)), listing the resolved data objects
(`ddd list`), writing out the data
dictionary itself (`ddd dump`), printing the JSON schema
of the file formats and of the dictionary (`ddd schema`), listing the files a project
description depends on (`ddd sources`, what lets a build system re-run its configure step
when one changes), recording how a build is configured to run DDD (`ddd build-info`,
[section 3.6](#36-build-record)) so that
a tool outside the build can apply the same project and the same severities, serving the
checks to an editor over the Language Server Protocol (`ddd lsp`, [section 7.2](#72-editor-integration)),
listing the available
checks (`ddd checks`), and reporting where its build system integration and its example
templates live (`ddd cmake-dir`, `ddd templates-dir`). Every command that reports findings
can produce machine readable JSON, and the exit code distinguishes clean runs (0), findings
(1) and usage errors (2). A findings exit is reserved for findings reported *as errors*: a
run whose findings are all warnings is a clean run unless `--strict` says otherwise.

The data dictionary **shall** be writable and readable as JSON, so that a generator DDD does not
ship can consume it without depending on the implementation.

### 7.1 Build system integration

DDD ships a CMake module with two calls: `ddd_add_component(<target> JSON <file>...)`
registers descriptions - component and types files alike - on their target, and
`ddd_generate(<image> ...)` generates for an image. It generates into the build tree, exposes
the generated headers to the components through an interface library and compiles the
generated definition sources into the image as an object library of their own, so that an
object no compiled code references is not dropped ([section 5.1](#51-c-code)).

`ddd_generate` knows two modes. In the collected mode - the default - the registered
descriptions travel the link graph as a transitive target property, and the project
description is assembled in the build directory from the closure the image actually links
([section 3.6](#36-build-record)); it needs a CMake new enough to carry properties across links. With
`PROJECT <file>` a hand written project description is used instead - the mode for an older
CMake, or for a project layout the link graph does not mirror. An `ADDRESS_MAP <file>` names
the address map of [section 6](#6-address-information): the map is a
dependency of the generation, so rewriting it after linking is what makes the next build run
DDD a second time with real addresses ([section 1.6](#16-position-in-the-build-process)) - the
C sources that second run re-renders are byte identical and trigger no rebuild
([section 5.1](#51-c-code)).

### 7.2 Editor integration

The checks **shall** also be served over the Language Server Protocol (`ddd lsp`), so that a
project is checked while it is written rather than when it is built. The same loader, the same
analysis and the same severity policy answer both, since an editor that disagrees with the
build about what is wrong is worse than an editor that says nothing.

The server offers, from a description file: the findings of [section 4](#4-consistency-checks), drawn over the key they
are about rather than over the file; go to definition and find references across files, which
is the question a schema cannot answer at all - the producer of an `input` is in a file the
author might not know the name of; a summary of a data object on hover; renaming an object
everywhere the project writes it, refused up front for a name the C namespace cannot take or
the project already spends - on another object, an enum, an enumerator or a type - since a
rename that silently merges two objects compiles, links, and shares storage nobody meant
to; and
quick fixes that reconcile one key across the declarations of one object, in either direction,
including removing a key the others do not have.

Which project a file belongs to comes from the build records of [section 3.6](#36-build-record), found by
searching the build directories the client names - or, unconfigured, the usual suspects
`build`, `out` and `cmake-build-*` under the workspace - recursively for `ddd-build.json`.
A file claimed by several builds is checked under each of them and the findings published
together: a component linked into two images is in two projects, and the answer to which one
the reader cares about is both. A file belonging to no configured build is still checked, on
its own, with the four checks that need every component of a project ([section 4](#4-consistency-checks)) held back: a
component read alone has inputs nobody produces and outputs nobody reads by construction
rather than by mistake, and reporting those buries the findings that are about the file in
front of the reader. Each check declares whether it needs the whole project, so the two modes
cannot drift apart.

An editor extension **shall** do no more than launch the server and point it at the build
directories: everything a reader sees is the tool's answer, so that an editor DDD ships
nothing for is not a second class one.

## 8 Implementation status

| section | status |
| --- | --- |
| [3.1](#31-project-description) project description, includes, sub-projects | implemented |
| [3.2](#32-software-component-description) component description, scopes, conditions | implemented |
| [3.3](#33-data-object-definition) measurements, parameters, value blocks, curves, maps, axes | implemented |
| [3.4](#34-conversions) conversions incl. enums | implemented |
| [3.5](#35-memory-placement-planned) memory placement | planned |
| [3.6](#36-build-record) build record | implemented (`ddd build-info`, written by `ddd_generate`) |
| [3.7](#37-type-description) type description, scalar and struct types | implemented (`ddd schema types`, `examples/structures`); A2L bitfield members await a build that reports their bits |
| [4](#4-consistency-checks) consistency checks | implemented |
| [4.1](#41-comparing-two-deliveries) comparing two deliveries | implemented (`ddd compare`, `ddd check --baseline`) |
| [5.1](#51-c-code) C code generation from project templates | implemented (`--template-dir`, `ddd templates-dir`); per-file assignment planned |
| [5.2](#52-a2l) A2L generation | implemented for 1.6.1; other versions, `FUNCTION`, `IF_DATA`, import planned |
| [6](#6-address-information) address information | JSON map implemented, ELF/DWARF import planned |
| [7](#7-tool-interface) command line interface | implemented |
| [7](#7-tool-interface) data dictionary as a published contract | implemented (`ddd dump`, `ddd schema dictionary`) |
| [7.1](#71-build-system-integration) build system integration | implemented (`cmake/Ddd.cmake`, `ddd cmake-dir`) |
| [7.2](#72-editor-integration) editor integration | implemented (`ddd lsp`: diagnostics, navigation, hover, rename, quick fixes; VS Code launcher extension) |
