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
    - [3.5 Memory placement](#35-memory-placement)
    - [3.6 Build record](#36-build-record)
    - [3.7 Type description](#37-type-description)
    - [3.8 Unit vocabulary](#38-unit-vocabulary)
    - [3.9 Constant vocabulary](#39-constant-vocabulary)
  - [4 Consistency checks](#4-consistency-checks)
    - [4.1 Comparing two deliveries](#41-comparing-two-deliveries)
  - [5 Generated artefacts](#5-generated-artefacts)
    - [5.1 C code](#51-c-code)
    - [5.2 A2L](#52-a2l)
  - [6 Address information](#6-address-information)
  - [7 Tool interface](#7-tool-interface)
    - [7.1 Build system integration](#71-build-system-integration)
    - [7.2 Editor integration](#72-editor-integration)

## 1 Introduction

The objective of DDD is to handle global data in the scope of an embedded software
development project. It **shall** support component based development methods, in which
individual components can be developed by different developers working in separate teams or
companies.

The interfaces between software components consist of reading and writing global data. DDD
**shall** provide tools to avoid the issues commonly associated with extensive use of
global data.

DDD occupies a central role in the firmware build process. It is the single place where the
data of a project is declared, it emits the C code that allocates that data, and it emits
the ASAM MCD-2 MC description that lets measurement and calibration tools work with that
data. In addition, it enforces the component interface rules: ownership, scope and
agreement between the components that share the data.

DDD is not tied to any industry. The terms used throughout this document, such as target,
firmware, measurement and calibration parameter, describe the roles the data plays, not the
kind of device the software runs on.

### 1.1 Requirement words

This specification uses its requirement words with fixed meanings:

| word | meaning |
| --- | --- |
| **shall**, **shall not** | a binding requirement on DDD; an implementation that behaves otherwise does not conform |
| **must**, **must not** | a validity constraint on data handed to DDD; a violation is reported under the named check for description data, or as a usage error for a command line input, and does not make the tool non-conforming |
| **should**, **should not** | a recommendation; deviation is allowed but requires a reason |
| **may** | a permission: genuinely optional, neither required nor recommended |
| **can** | a statement of capability or possibility, carrying no requirement |

Plain present tense describes the specified behaviour of DDD and binds like **shall**: the
sentence "the matches are processed in sorted order" requires exactly that. The explicit
words mark the sentences in which the kind of obligation is the point. They are set in bold
wherever they bind; set plain, they are ordinary English.

### 1.2 Interface specification

DDD allows the software developer to specify the global data interface of a software
component. The scope of each data object can be defined as input, output or local to the
component ([section 2.1](#21-scope)). The specification also includes, among the
other properties of [section 3.3](#33-data-object-definition), physical units, scaling
information for fixed point datatypes, and enumerations.

### 1.3 Consistency check

When several components are assembled into a complete project, DDD ensures the consistency
of the global data interfaces. It checks that each data object is produced by exactly one
component, and that the components which consume an object agree on its datatype, unit,
scaling and the other interface properties ([section 4](#4-consistency-checks)).

### 1.4 Source code generation

In order to enforce the access rules specified for each component, the global data objects
**shall** be defined and declared by DDD. The tool generates the C code defining every
global data object of the project. The example templates emit these definitions as a single
file, for the reasons given in [section 5.1](#51-c-code), and that file is compiled and
linked into the firmware exactly once.

DDD **shall** also generate a declaration C header for each software component. This header
**shall** contain declarations only for the data objects specified in the interface
description of the component.

### 1.5 Calibration tool support

DDD **shall** support the A2L file format (ASAM MCD-2 MC), so that the resulting software
integrates into common measurement and calibration tools ([section 5.2](#52-a2l)). This
support covers both directions of the data model: the values the tool *measures*, and the
values the tool *calibrates*, namely single parameters, value blocks, curves, maps and
their axes.

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

DDD is run once per build to generate the artefacts, the A2L among them. Without address
information, every object in the A2L carries address zero, and `SYMBOL_LINK` names the
symbol in every case ([section 6](#6-address-information)). A build that requires the A2L
to carry the real addresses, which exist only after linking, runs DDD a second time with a
map taken from the linker output. A build that does not require them stops after the first
run.

## 2 Concepts

| term | meaning |
| --- | --- |
| **project** | a named set of components and/or sub-projects |
| **component** | a software unit with an explicitly declared data interface |
| **image** | one linked binary; the components it actually links decide which objects it carries, and one component can be linked into several images ([section 3.6](#36-build-record)) |
| **declaration** | one entry of a component interface: a scope, an optional condition and a definition |
| **definition** | the part of a declaration that says what the object is: kind, datatype, shape, conversion and the remaining keys of [section 3.3](#33-data-object-definition) |
| **data object** | the subject of a declaration: a measurement, parameter, value block, curve, map or axis |
| **measurement** | a data object the software writes and reads, the producer writing and the consumers reading; a calibration tool can both read and write it as well |
| **calibration object** | a data object the software never writes: a parameter, value block, curve, map or axis, generated `const` and changed, if at all, by a calibration tool |
| **scope** | ownership and visibility of a data object with respect to the declaring component |
| **producer** | the component that owns a data object; its declaration is the authoritative one |
| **consumer** | a component that declares a data object as its `input`; it reads what another component produces |
| **declared type** | a scalar or structure declared by a types file ([section 3.7](#37-type-description)) and named by `typename` where storage is stated |
| **constant** | a named integer declared by a constants file ([section 3.9](#39-constant-vocabulary)); a shape names it where it would state a number |
| **access path** | the C expression that reads a member of a structured object, for example `Inlet.cell[2].raw`; it is the name under which the A2L and the address map know the member ([section 5.2](#52-a2l)) |
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

For measurements, `output` means that the component writes the variable. For calibration
objects, which the software never writes, `output` means that the component provides the
data and other components **may** read it; `local` is the normal choice for data that only
parametrises the owning component.

## 3 File formats

All description files used by DDD contain plain JSON, encoded UTF-8; a byte order mark is
tolerated on reading, because Windows editors commonly prepend one. A description file
**must** be named `*.ddd.json` (`file-extension`), compared without regard to case, so
that it is recognisable as a DDD description in a project that contains JSON for other
purposes. The top level key of a file
decides what the file is: `project` ([section 3.1](#31-project-description)),
`component` ([section 3.2](#32-software-component-description)),
`types` ([section 3.7](#37-type-description)), `units` ([section 3.8](#38-unit-vocabulary)),
`sections` ([section 3.5](#35-memory-placement)) or
`constants` ([section 3.9](#39-constant-vocabulary)); only the first two can be the root of
a run. A file stating none of these keys, or several at once, is refused (`file-kind`).
JSON allows one object to spell the same key twice, as in `"init": 0, "init": 255`,
and parsers generally resolve the duplication silently in favour of the last spelling, so
the value the author reads first is not the value a tool would use, and in a grown
description file such a divergence is costly to locate. A key **must not** be
repeated inside one object; the file is refused (`json-syntax`) rather than read with the
surviving value. A file that is not valid UTF-8, or whose nesting exceeds the depth the
parser accepts, is refused the same way (`json-syntax`). Unknown keys are rejected, with one exception: a top level `$schema` key
**shall** be accepted and ignored, because it is the standard way an editor binds a JSON
file to its schema and thereby turns the published contract into completion, hover
documentation and validation while typing. The formal contract is published by the tool
itself as a JSON schema (`ddd schema`), in one file per format, covering project,
component, types, units, sections, constants and the data dictionary, and every authored
field of it
**shall** carry its documentation. The binding is per file rather than per directory
because the kind of a description is stated in its content, not in its name.

### 3.1 Project description

Contains a list of components, types files, units files, sections files, constants files
and/or other (sub-)projects.

```json
{
  "project": {
    "name": "DemoDevice",
    "description": "optional",
    "includes": ["components/*.ddd.json", "subsystems/logging/logging.ddd.json"]
  }
}
```

- `"name"` (required): the C identifier of the project, also used as the A2L project and
  module name.
- `"description"` (optional): free text.
- `"includes"` (optional): paths to component, types, units, sections, constants or
  sub-project files,
  relative to this file; an absolute path is taken as written. The kind of each included
  file is detected from its content. A
  file reached through several paths is loaded once; file identity is the resolved path,
  that is the absolute path with symbolic links followed, compared as the platform compares
  paths. Include cycles are an error.

An entry of `includes` containing one of `*`, `?` or `[` is a wildcard pattern, expanded
with the usual shell rules: `*` and `?` match within one path component, `[...]` is a
character class, and `**` matches directories recursively. A dot prefixed file is matched
like any other file, and whether matching honours case follows the platform, like the file
identity above. Only regular files are matched, the file stating the pattern is never
among the matches, and the matches are processed in sorted
order of their resolved paths, ordered again as the platform compares them, so that which
component loads first does not depend on how a file system happens to enumerate a
directory. A pattern that matches nothing is `include-empty`, and a pattern the platform
cannot expand counts as matching nothing. An entry without a wildcard
character is a literal path naming exactly one file, and if that file does not exist, or
names a directory, the
finding is `file-not-found` rather than `include-empty`: a pattern **may** legitimately be
empty, while a named file **may** not be missing.

### 3.2 Software component description

The top level key `"component"` is required, and it contains the following elements:

- `"name"` (required): the name of the component. It is a C identifier, because it becomes
  the name of a generated header and of an A2L group, and every component of a project
  needs a distinct one.
- `"description"` (optional): free text.
- `"interface"` (required): the data interface, a list of declarations, each declaring one
  data object. The key is required with no default, so that a component with nothing to
  declare states an empty list rather than omitting a key that might merely have been
  forgotten. The same reasoning makes `volatile` and `kind` required on a definition.

Each declaration contains:

- `"scope"` (required): one of `input`, `output` or `local`, the scope of the declaration
  ([section 2.1](#21-scope)).
- `"condition"` (optional): a C preprocessor conditional expression which wraps the
  generated declarations of the object
  ([section 3.3.1](#331-one-object-several-declarations)). The expression **must** be a
  single line and **must not** contain `#` or a comment token (`//`, `/*`, `*/`)
  (`schema`): the text is emitted verbatim behind `#if`, where any of them could change
  the meaning of the generated file. A condition consisting only of whitespace counts as
  no condition.
- `"definition"` (required): a definition object
  ([section 3.3](#33-data-object-definition)).

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
| `datatype` | one of the two | `boolean`, `uint8`, `sint8`, `uint16`, `sint16`, `uint32`, `sint32`, `uint64`, `sint64`, `float32`, `float64`; exactly one of `datatype` and `typename` is stated ([section 3.3.2](#332-naming-a-declared-type)) |
| `typename` | one of the two | the name of a declared type ([section 3.7](#37-type-description)), stated instead of `datatype` |
| `description` | `""` | offered to the C templates as the text of a comment, long identifier in the A2L |
| `unit` | `""` | physical unit; checked against the vocabulary where the project declares one ([section 3.8](#38-unit-vocabulary)) |
| `conversion` | required beside `datatype` | raw to physical conversion ([section 3.4](#34-conversions)); a `typename` fixes it instead |
| `limits` | derived | physical `min`/`max` with `min` not above `max`, stated together or not at all; when omitted they follow from the datatype and the conversion, and for an `enum` from the smallest and largest enumerator |
| `init` | `null` | raw initial value; `null` means implicit zero initialisation |
| `section` | none | linker section the object is placed in ([section 3.5](#35-memory-placement)); a storage key the producer states |
| `a2l` | export | `export`, `format`, `display_identifier` |
| `volatile` | required | whether the generated C carries `volatile`, that is whether the value can change without the reading code having written it |

`volatile` has no default because there is nothing to derive one from. Unlike `limits`,
which follow from the datatype and the conversion, it states something about the running
system that only the project knows. A measurement needs it when an interrupt, a second
core, a peripheral or a calibration tool writes the variable; a calibration object needs it
when a calibration tool is to change the value while the software runs. Both answers have a
cost, and the tool therefore asks instead of choosing one silently.

The `a2l` block holds what only the calibration tool sees. `export` decides whether the
object appears in the A2L at all
([section 3.3.1](#331-one-object-several-declarations)). `format` is the display format,
written as `%`, an optional total width, `.` and the number of decimals, for example
`"%5.2"` or `"%.3"`. `display_identifier` is an alternative display name, a C identifier.
The latter two are emitted as the A2L keywords of the same names when stated, and left out
of the A2L when not stated.

The datatypes map to C and to the A2L as follows, and their raw ranges are the starting
point of derived limits:

| datatype | C type | raw range | A2L type |
| --- | --- | --- | --- |
| `boolean` | `bool` (`<stdbool.h>`) | 0..1 | `UBYTE` |
| `uint8` | `uint8_t` | 0..255 | `UBYTE` |
| `sint8` | `int8_t` | -128..127 | `SBYTE` |
| `uint16` | `uint16_t` | 0..65535 | `UWORD` |
| `sint16` | `int16_t` | -32768..32767 | `SWORD` |
| `uint32` | `uint32_t` | 0..4294967295 | `ULONG` |
| `sint32` | `int32_t` | -2147483648..2147483647 | `SLONG` |
| `uint64` | `uint64_t` | 0..18446744073709551615 | `A_UINT64` |
| `sint64` | `int64_t` | -9223372036854775808..9223372036854775807 | `A_INT64` |
| `float32` | `float` | ±3.4028234663852886e38 | `FLOAT32_IEEE` |
| `float64` | `double` | ±1.7976931348623157e308 | `FLOAT64_IEEE` |

Derived limits are the raw range pushed through the conversion: under the identity they are
the raw ends themselves, and under a linear conversion each end is converted, the pair
being swapped into order when `factor` is negative. A pairing of datatype and conversion
whose derived limits are not finite, the converted raw range overflowing the largest
finite floating point value, is refused where it is written (`schema`), because no finite
stated limits could repair a conversion that overflows by itself. `boolean` does not count as an integer
datatype: an enum conversion refuses it, and so does a `bits` member
([section 3.7](#37-type-description)).

Every name is a C identifier of at most 128 characters, the bound the A2L format places on
an identifier, which is tighter than the bound of C. The cap holds wherever a name is
written: objects, components, projects, enums, enumerators, types, members and
`display_identifier`.

Kind specific attributes:

| kind | additional keys | storage | A2L |
| --- | --- | --- | --- |
| `measurement` | `dimensions` (optional) | writable RAM variable | `MEASUREMENT` |
| `parameter` | none | `const` or `const volatile` scalar | `CHARACTERISTIC ... VALUE` |
| `value_block` | `dimensions` (required) | `const` or `const volatile` array | `CHARACTERISTIC ... VAL_BLK` |
| `axis` | `size` (required), `input` (optional) | `const` or `const volatile` array `[size]` | `AXIS_PTS` |
| `curve` | `axis` (required) | `const` or `const volatile` array `[size of the axis]` | `CHARACTERISTIC ... CURVE` |
| `map` | `x_axis`, `y_axis` (both required) | `const` or `const volatile` array `[size of y][size of x]` | `CHARACTERISTIC ... MAP` |

- `dimensions` is a non-empty list of array dimensions, each an integer of at least 1
  (`schema`) or the name of a declared constant
  ([section 3.9](#39-constant-vocabulary)), for
  example `[3, 4]` or `["PRESSURE_CELLS", 4]`; the `size` of an axis follows the same
  rule, and a
  measurement without `dimensions` is a scalar. In the A2L the same object is described by a
  `MATRIX_DIM` listing the fastest running index first, that is in the reverse order,
  because describing it in C order would state a transposed object; the list is padded with
  ones to the three entries version 1.6.1 expects.
- `init` is a scalar or a nested list matching the shape of the object. A scalar given
  for an array shaped object initialises every element; the scalar fill applies to the
  whole object only, not to a nested position. An initial value **must** fit the raw
  range of its datatype and **must** match the shape of the object (`init-invalid`). It is
  compared neither against the limits, which
  are physical while `init` is raw, nor against the enumerators of an enum conversion.
  The value is raw rather than physical because the generated C carries it verbatim, and
  because under a linear conversion most physical values are the exact image of no raw
  count, so a physical spelling would either round silently or refuse ordinary values.
  The hover of [section 7.2](#72-editor-integration) and the table of `ddd list` state
  the physical reading beside the raw value.
- `axis`, `x_axis` and `y_axis` name an object of kind `axis` declared anywhere in the
  project; the axis is shared between all curves and maps referring to it (A2L `COM_AXIS`).
  Referring is not using: the reference resolves against every declaration of the project
  and obliges the referring component to nothing, so an axis that no `input` declaration
  reads is still `unused-output`, and a component that wants the axis in its own header
  declares it as its `input`.
- `input` names the measurement that indexes an axis (A2L input quantity); when omitted,
  the A2L uses `NO_INPUT_QUANTITY`.
- Calibration objects (every kind except `measurement`) are always generated `const`,
  because the software never writes them, and additionally `volatile` when the declaration
  says so. An object a calibration tool changes in a running target needs both qualifiers.
  Plain `const` entitles the compiler to fold the initial value into the code that reads it
  wherever that value is visible at the point of the read; within one translation unit that
  holds at every optimisation level, `-O0` included, because the substitution happens in
  the C front end rather than in an optimiser, and link time optimisation extends it across
  translation units. Where the load does survive, for example in a component reading
  through the generated header of another and compiled without `-flto`, `const` still lets
  the compiler serve two reads from one load and move that load across a call. In either
  case the tool writes a value the software does not pick up. What `const volatile` costs
  is the read only memory: the compiler treats every read as a side effect and drops the
  object out of the read only category, so it is emitted into a writable section instead of
  `.rodata`. This behaviour was measured with GCC 12.2.0 and **should** be confirmed on the
  toolchain a project ships with. On a flash target it means a RAM address with a load
  region and a startup copy that overwrites what the tool wrote, unless the linker script
  says otherwise. DDD states no preference between the two and reports nothing about the
  choice: a project that calibrates online states `true` and places the object through its
  linker script or by naming a `section` ([section 3.5](#35-memory-placement)), and a
  project that does not calibrate online states `false` and keeps its data in flash.
- `volatile` buys freshness and gives up coherence, which is worth knowing before it is
  turned on for a whole dictionary: the compiler has to re-read the object at every
  mention, so a set of parameters read at several points of one control step can straddle a
  calibration write and be used partly old and partly new, and a loop over a
  `const volatile` value is not vectorised.

#### 3.3.1 One object, several declarations

Several components declare the same object, and the keys of a definition do not all mean
the same thing on each of those declarations. They fall into three groups.

A project that relaxes `missing-producer` can hold objects that no component produces
([section 5.1](#51-c-code)). Wherever the rules below say "the producer", such an object
falls back to its first declaration in load order, that is includes order with wildcard
matches sorted ([section 3.1](#31-project-description)), so that the resolved answer is
stable rather than an accident of the file system.

##### 3.3.1.1 Interface

The interface keys are `kind`, the storage (`datatype` or `typename`), `unit`,
`conversion`, the shape (`dimensions` or `size`), the referenced objects (`axis`, `x_axis`,
`y_axis` and the `input` of an axis) and `volatile`. Every declaration **must** state the
same thing, and a disagreement is `definition-mismatch`. `volatile` is interface rather
than storage because it reaches every consumer's header as a type qualifier and tells their
code whether the value can change under it; two components disagreeing about it would
compile different assumptions about the same address. Being required on every definition,
it is stated by every declaration, so there is always an answer to compare rather than a
silence to interpret. `limits` are the one interface key a declaration **may** leave out,
because DDD derives them from the datatype and the conversion: omitting them defers to
whoever states them, and only two *stated* sets of limits can disagree
(`definition-mismatch`). The resolved limits come from the producer when it states them,
otherwise from the first declaration in load order that states them, and otherwise they
are derived; every other declaration that states limits is compared against that stated
reference.

##### 3.3.1.2 Storage

The storage keys are `init` and `section` ([section 3.5](#35-memory-placement)). What an
object starts out as, and where it lives, is decided by the component that produces it, so
a declaration whose scope is `input` **must not** state either key (`consumer-storage`).
This is not an opinion to be outvoted: it is a claim over storage the component does not
own, and it is reported where it is written rather than where it is overruled.

##### 3.3.1.3 Presentation

The presentation keys are those of the `a2l` block, on which no generated C depends.
`format` and `display_identifier` are taken from the producer, and a consumer stating
a different answer is told so by `storage-mismatch`. A declaration stating neither key
defers: only two stated answers can disagree, and a consumer's statement never replaces a
producer's silence in the output, which keeps the emitted presentation the producer's
alone. The check names of
[section 4](#4-consistency-checks) use *storage* more broadly than this section's groups:
`storage-mismatch` polices presentation, and `changed-storage` of
[section 4.1](#41-comparing-two-deliveries) covers the volatility as well. Identifiers are
pinned once published; where the words differ, the groups of this section are the precise
statement. `export` is the exception, and in the other direction: any component **may**
state it, whether it produces the object or not, because which signals a calibration
engineer needs to see is not a property of whoever happens to produce the object, and a
component reading a value out of a library it does not own has an equal claim to measuring
it. The stated answers are combined rather than ranked: the object is exported if any
declaration states `true`, and it is left out only when every stated answer is `false`;
when no declaration states it, the object is exported. Two consumers can therefore never
conflict over it, there is no finding to invent for a disagreement between them, and the
verdict does not depend on which components an image happens to link. A dictionary that
omits the `a2l` block altogether therefore exports its objects, which is what makes an
older or third party dictionary readable without rewriting it.

##### 3.3.1.4 Description and condition

`description` is per declaration and free: two components **may** describe the same object
in their own words, and DDD does not compare the texts. The producer's text is the one that
reaches the generated C comment and the A2L long identifier; a consumer's text reaches no
output. `condition` is per declaration as well but **should** agree, and
`condition-mismatch` says so as a warning rather than an error, because components
guarded by legitimately different expressions occur in practice. Conditions are
compared as text, stripped of surrounding whitespace: `A && B` and `B && A` are different
conditions, because deciding their equivalence would require a preprocessor, and a
declaration stating no condition disagrees with one stating some. The dictionary records
the producer's condition on the object, and every declaration's own condition with its
declaring component.

#### 3.3.2 Naming a declared type

A definition states its storage exactly once: `datatype` names one of the eleven base
datatypes, and `typename` names a type the project declares in a types file
([section 3.7](#37-type-description)); stating both, or neither, is refused (`schema`). Two
keys are used rather than one union so that each key keeps a single meaning. The published
schema keeps `datatype` at exactly eleven values: an editor completes and documents
precisely them, and a mistyped `uint166` is refused as it is typed rather than reported as
a type nobody declares one build later. In addition, the use site tells base storage from a
declared type at a glance, which one key accepting both never could.

A `typename` **must not** spell a base datatype, compared without regard to case
(`schema`): a type called `uint16`, or `UINT16`, wears the name of storage it is not, and
every declaration naming it would read like a typo. Any other name is simply a name;
`Int16_t` is unambiguous, because the key already says that it is declared. The same rule
holds where a type is named into being, that is on the `name` of a types file entry. A
`typename` naming no type any file of the project declares is `unknown-type`, and the
nearest name is suggested: `unit16` receives the suggestion `uint16`.

Naming a type and then restating what it fixes is an error rather than an override, so that
the question "where is this object's unit written down" has exactly one answer.

A declaration naming a **scalar type** is an ordinary object whose datatype, unit,
conversion and limits come from the type. A declaration naming a **structure** is a
structured object: it generates one C object, and it reaches the A2L as one object per
member ([section 5.2](#52-a2l)).

### 3.4 Conversions

```json
{ "kind": "identity" }
{ "kind": "linear", "factor": 0.25, "offset": -40.0 }
{ "kind": "enum", "name": "StateA_t", "enumerators": { "STATE_OFF": 0, "STATE_FAULT": 15 } }
```

- `identity` has no further keys.
- `linear` means `physical = raw * factor + offset`; `factor` defaults to 1.0 and **must
  not** be zero, `offset` defaults to 0.0, and both **must** be finite.
- `enum` requires an integer datatype. `name` is required: it is the C identifier of the
  generated `typedef enum`, the identity under which `enum-conflict` compares enumerator
  lists, and the name of the A2L `COMPU_VTAB`. `enumerators` is required and non-empty;
  it **may** also be given as a list of `{"name", "value", "description"}` objects. An
  enumerator name **must not** repeat within one conversion (`schema`), and every
  enumerator value **must** fit a 32 bit C `int`, the type C gives an enumerator, whatever
  the object's datatype would hold (`init-invalid`). An enum
  converts nothing: physical and raw value coincide, so the limits of an enum object,
  stated or derived, are enumerator values.
- `kind` **may** be omitted, unlike the `kind` of a definition, because the other keys
  decide it: a conversion stating `enumerators` or `name` is an `enum`, one stating
  `factor` or `offset` is `linear`, and one stating nothing, `{}`, is the identity. Unknown
  keys are rejected here as everywhere, so a conversion cannot match two kinds at once.

A conversion **must** be stated wherever storage is named by `datatype`, that is on a
definition, on a member and on a scalar type, although the identity would be derivable
(`schema`). That it is derivable is exactly why it is asked for: raw equalling physical is
an engineering claim about the data, not a formatting accident, and a forgotten scaling on
a fixed point value displays raw counts without any visible failure. A definition or
member naming a `typename` states no conversion, because the type fixes it
([section 3.3.2](#332-naming-a-declared-type)).

`linear` with `factor` 1 and `offset` 0 is not the identity: conversions compare as written
(`definition-mismatch`), and the A2L carries what was written, a `RAT_FUNC` against an
`IDENTICAL` ([section 5.2](#52-a2l)). One mapping, spelled two ways, is a disagreement
about the spelling, and the spelling is what every consumer's tooling sees.

Where several declarations state one enum with the same enumerators, the generated header
and the dictionary carry the declaration that documents the most of them, the count of
stated enumerator descriptions deciding and their texts breaking ties, so that the result
does not depend on the order in which the project includes its components.

### 3.5 Memory placement

Each data object of an embedded project lives in a memory with a character of its own, such
as RAM, flash, calibratable ROM behind an emulation overlay, or non-volatile memory (NVM),
and the linker places the object there by section. DDD carries that placement: a `sections` file declares the
sections a project uses, as an includable vocabulary like the units file
([section 3.8](#38-unit-vocabulary)), and a definition names one of them.

```json
{
  "sections": [
    { "section": ".data", "access": "read-write", "alignment": 4 },
    { "section": ".calib", "access": "read-only", "alignment": 4,
      "description": "calibration flash, tool writable through the emulation overlay" },
    { "section": ".nvm", "access": "read-write", "alignment": 8 }
  ]
}
```

A sections file declares at least one section (`schema`).

- `"section"` (required): the name as the linker script spells it. It is a linker name
  rather than a C identifier, so `.calib` is a normal spelling, and it contains no
  whitespace (`schema`). A section declared twice,
  by one file or by two, is `duplicate-section`.
- `"access"` (required): `read-write` or `read-only`, from the point of view of the running
  software. Whether a calibration tool can write a read-only section, for example through
  an emulation overlay or a calibratable flash, is a property of the target and is
  deliberately not modelled: DDD cannot tell a plain ROM from a calibratable one, and the object's
  `volatile` already states what the software has to assume
  ([section 3.3](#33-data-object-definition)).
- `"alignment"` (required): the alignment the section guarantees, in bytes, a power of two.
- `"description"` (optional): free text.

A definition **may** then state its `section`, a storage key like `init`
([section 3.3.1.2](#3312-storage)): the producer states it, a consumer stating one claims
storage it does not own (`consumer-storage`), and a structured object is placed whole, its
members having no placement of their own for the same reason they carry no `volatile`. A
`section` names a declared section the way a `typename` names a declared type: naming one
that no file declares is `unknown-section`, with the nearest name suggested, and there is
no free text fallback, because a section without declared properties would be a name the
checks can say nothing about. An object without a `section` is placed by the toolchain's
defaults, which is what makes the vocabulary adoptable gradually.

Two checks tie placement to what the description already says. A measurement is written by
the software, so placing one in a `read-only` section is `section-access`. An object whose
datatype needs stricter alignment than its section guarantees is `section-alignment`; for a
structured object the need is estimated as the strictest of its members' datatypes, and the
compiler's word is final, because reading the real layout back is what the address
information of [section 6](#6-address-information) is for.

The generated C carries the placement in whatever spelling the toolchain wants, such as an
`__attribute__((section(...)))` or a pragma; the spelling is left to the templates, exactly
as the rest of the house style is ([section 5.1](#51-c-code)): DDD resolves the section name
per object, the dictionary records it, and the templates receive both the name on every
placed object and the objects grouped per section, ordered strictest alignment first with
names breaking ties, so that data of one section packs without padding. The example
templates spell the GCC attribute. Describing the layout in the A2L with `MEMORY_SEGMENT`
is *planned*: a segment's address and size exist only after linking, so
they **shall** arrive with the address information rather than being restated in the
vocabulary, because the linker script already owns them and a copy would drift. The
`MOD_PAR` block that will carry them already exists for the constant vocabulary
([section 5.2](#52-a2l)).

### 3.6 Build record

A build knows two things that no description file records: which project description DDD is
run on, and under which severity policy. In the collected mode of the CMake integration
([section 7.1](#71-build-system-integration)) the project description is not even in the
source tree: it is assembled in the build directory out of the C link closure, so which
components belong together is a property of the build rather than of any authored file. A build **shall** therefore write a record of how it runs DDD (`ddd build-info`), so
that a tool outside the build can check exactly what the build checks instead of
re-deriving a project from the file tree and guessing at the severities. The language
server of [section 7.2](#72-editor-integration) is the reader this record exists for.

The file is named `ddd-build.json` and lives beside the artefacts of the target that wrote
it. `ddd build-info` writes wherever its `-o` argument points; `ddd-build.json` is the
name under which the language server searches ([section 7.2](#72-editor-integration)), so
a record that wants to be found keeps it. It is deliberately *not* named `*.ddd.json`: that extension means a DDD description
file, `file-extension` enforces it, and `file-kind` would then reject this content for
having none of the top level keys a description **may** have. It is a document *about* a
project rather than a description of one.

| key | meaning |
| --- | --- |
| `format` | version of this document format, raised only when its shape changes; today `1` |
| `project` | absolute path of the project description the build runs DDD on; absolute because this file lives in the build tree while the project **may** not |
| `image` | the build target the record was written for, by name, for example `firmware.elf`; a component linked into both a firmware and a test binary belongs to two projects, which need not agree about it |
| `strict` | whether the build reports warnings as errors |
| `severity` | the severity overrides the build applies, as `check=severity` ([section 4](#4-consistency-checks)), in the order given |

The path in `project` is recorded and never checked when the record is written: in the
collected mode the description is produced at the end of the configure run, after the
process that writes this file, so requiring it to exist would fail every first configure.

Unlike the description formats and the data dictionary, this document has no published JSON
schema. Nobody authors it: a build writes it and a tool reads it, so a schema would serve
neither an editor nor an author. Its `format` key is what a reader checks instead, and a
record it does not understand is one it declines rather than misreads.

### 3.7 Type description

A `types` file declares the types a project names, so that components agree by naming
rather than by each copying out the same answer. It is listed in the `includes` of a
project ([section 3.1](#31-project-description)) like a component file, and only there:
handed to the tool as the root of a run, it is refused, with a hint that it belongs in a
project's `includes`. It is recognised by its top level key: `types`, a non-empty list of
entries (`schema`),
each stating its `type`, either `scalar` or `struct`.

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
        { "name": "raw", "member": "value", "datatype": "uint16", "conversion": {}, "dimensions": [4] },
        { "name": "latest", "member": "value", "typename": "Temperature_t" },
        { "name": "ready", "member": "bits", "datatype": "uint8", "conversion": {}, "bits": 2 }
      ]
    }
  ]
}
```

- A **scalar** type fixes `datatype`, `unit`, `conversion` and `limits`, which is exactly
  what makes two declarations interchangeable, and nothing else; `name`, `datatype` and
  `conversion` are required, `unit` and `limits` are optional. `kind`, `dimensions`,
  `init`, `volatile` and `a2l` stay on the declaration, because two measurements of one
  type can differ in whether an interrupt writes one of them. Its `datatype` is a base
  datatype: a scalar type cannot be declared in terms of a second one, so a chain of
  aliases, and with it a scalar cycle, cannot be written at all.
- A **struct** type declares `members` (required and non-empty), in the order they are
  laid out. Two members of one structure **must not** share a name (`schema`). Every
  member states `name`, `member` and its storage, and beside a `datatype` also its
  `conversion` (required). `member` is the shape. A `value` member holds a base `datatype`
  or a declared `typename`, optionally as an array (`dimensions`). A `bits` member holds a
  base integer `datatype` (a declared type carries no bitfield) and a width (`bits`,
  required there) of at least one bit and at most what that datatype holds; a `bits`
  member takes no `dimensions`.

Two entries of one file **must not** share a name (`schema`); the same name declared by
two files is `duplicate-type` ([section 4](#4-consistency-checks)).

A member says what its bytes mean as well as where they are: it carries `unit`,
`conversion` and `limits` of its own, or it names a scalar type that fixes them, never
both. Its `a2l` block stays its own either way, because a scalar type fixes what a value
means, not how a tool displays it. A member carries no `init` and no `volatile`, which
belong to a declaration rather than to a type, and no `kind`: a storage class qualifies a
whole C object, so the declaration decides, and a structure mixing measured and calibrated
members is not something this format can express.

A declaration naming a structure is a `measurement` or a `parameter`, the two kinds that
are plain storage; a `value_block`, `curve`, `map` or `axis` refers to other objects or is
an array of one datatype, and a structure is neither (`type-kind`). A structured
measurement **may** carry `dimensions`: an array of structures contributes its members once
per element, each at its own path. A declaration naming a structure **must not** carry
`init` (`type-kind`): an initial value spelled out per member would restate the structure
the type already fixes, so a structured object is zero initialised, and its values are put
there by the running system, by the starting code for a measurement and by the calibration
tool for a parameter. Of its `a2l` block, `export` decides for the whole object
([section 3.3.1](#331-one-object-several-declarations)) and each member's own `export` for
the member; `format` and `display_identifier` are per member, a whole structure having no
display format of its own.

Bit positions and member offsets are not stated, and this specification will not add them.
C leaves both to the compiler, so DDD reads them back out of the build rather than
predicting them, which is why the address map of
[section 6](#6-address-information) is keyed on access paths. The limits
of a bitfield do follow from its stated width, because offering a two bit field over the
whole range of the word carrying it would invite a value the field cannot hold.

### 3.8 Unit vocabulary

A `units` file declares the units a project spells, so that one quantity cannot drift into
two spellings. `unit` is free text wherever it is written, because DDD cannot know that
`Nm` and `newton_meter` mean the same thing, and without a vocabulary the drift is
invisible: each object agrees with itself, the A2L grows one `COMPU_METHOD` per spelling
([section 5.2](#52-a2l)), and the calibration tool shows two units for one quantity.

```json
{
  "units": [
    "rpm",
    { "unit": "Nm", "description": "torque, newton metre" },
    { "unit": "degC", "description": "temperature" }
  ]
}
```

The file is listed in the `includes` of a project ([section 3.1](#31-project-description))
like a types file, and only there: handed to the tool as the root of a run, it is refused,
with a hint at the include that carries it. The file declares at least one unit
(`schema`). An entry is a bare spelling, or an object
adding a `description`, which is where the meaning of a unit is written down once, instead
of being implied by every object that happens to use it. Case counts: `mV` and `MV` are
different units. The same unit declared twice, by one file or by two, is `duplicate-unit`.

Declaring the vocabulary is opt-in: a project without a units file keeps its units free.
With a vocabulary, every stated unit, whether on a definition, on a structure member or on
a scalar type, is checked where it is written (`unknown-unit`), with the nearest declared
spelling suggested. The empty unit is always allowed: a dimensionless value states no unit
rather than a spelling of one.

### 3.9 Constant vocabulary

A `constants` file declares named integer constants, so that a size lives in one place and
is shared by name. An array dimension is commonly a named constant of the C project,
stated once and used by every loop that walks the array; a bare number in a description
restates that constant and drifts from it silently. The file is an includable vocabulary
like the units file ([section 3.8](#38-unit-vocabulary)): it is listed in the `includes`
of a project ([section 3.1](#31-project-description)) and only there, and handed to the
tool as the root of a run it is refused, with a hint at the include that carries it. The
file declares at least one constant (`schema`).

```json
{
  "constants": [
    { "name": "PRESSURE_CELLS", "value": 8, "description": "cells of the pressure manifold" },
    { "name": "AXIS_POINTS", "value": 16 }
  ]
}
```

- `"name"` (required): a C identifier. The name reaches the generated C, so the length cap
  of [section 3.3](#33-data-object-definition), `reserved-identifier` and `name-collision`
  apply to it. The same name declared twice, by one file or by two, is
  `duplicate-constant`.
- `"value"` (required): an integer of at least 1, written as a number. The value is a
  literal only: an expression would put a parser and an evaluation order into a
  description format, and a constant cannot name another constant, for the reason a scalar
  type cannot be declared in terms of a second one
  ([section 3.7](#37-type-description)): what cannot be written cannot cycle.
- `"description"` (optional): free text.

A shape then names a constant where it would state a number: an entry of `dimensions`, or
the `size` of an axis, is either an integer or the name of a declared constant
([section 3.3](#33-data-object-definition)), and a list mixes the two freely. Naming a
constant that no file of the project declares is `unknown-constant`, with the nearest name
suggested. A name and its value are different spellings of one size: declarations of one
object **must** agree on the spelling (`definition-mismatch`), exactly as conversions
compare as written ([section 3.4](#34-conversions)), because the spelling is what reaches
every consumer's header. In a delivery comparison a dimension likewise compares as its
spelling and its value ([section 4.1](#41-comparing-two-deliveries)).

The generated C renders a constant-dimensioned object by the constant's name, and the
templates receive the declared constants to emit ([section 5.1](#51-c-code)); the A2L
states one `SYSTEM_CONSTANT` per declared constant and resolved numbers in every record
([section 5.2](#52-a2l)).

## 4 Consistency checks

Every check has a stable identifier and a default severity. The identifiers are part of the
tool interface, because a build script pins them in its severity overrides, so they **shall
not** change once published. The severity of a check can be changed per project run, so
that a team can fine tune its error management policy; the checks that make a file
unreadable cannot be relaxed. The authoritative list is the one the tool prints itself
(`ddd checks`).

An override is written `check=severity` (`ddd check -W unused-output=info`), with `error`,
`warning`, `info` and `ignore` as the severities; `ignore` drops the finding entirely. The
option is repeatable, and for one check the last override wins; `--strict` then promotes
what is still a warning to an error. Overriding a check that cannot be relaxed is a usage
error rather than a finding, as is naming an unknown check or severity.

Seven checks need every component of a project to mean anything: `unknown-type`,
`unknown-unit`, `unknown-section`, `unknown-constant`, `missing-producer`,
`unknown-reference` and
`unused-output`. Exactly these are the checks the language server holds back when it checks
a file belonging to no project ([section 7.2](#72-editor-integration)).

The `schema` check carries every violation of the published file contracts
([section 3](#3-file-formats)), including the rules this document states in prose, such as
a zero `factor`, an enum conversion on a non-integer datatype, or a key restated that a
named type already fixes: they are shape errors of one file, located where they are
written, and need no identifier of their own.

A finding about several declarations of one object is reported once per declaration that
deviates, anchored where the deviation is written, with a note pointing at the reference,
which is the producer's declaration or the first loaded one
([section 3.3.1](#331-one-object-several-declarations)). `multiple-producers` is therefore
reported on every producer after the first, `missing-producer` once per consumer, and
`unused-output` once, on the producer. A scope clash involving a `local` declaration is
`local-conflict` alone, never `multiple-producers` as well.

Errors:

- `multiple-producers`: an object is produced by more than one component.
- `missing-producer`: an input object is produced by nobody.
- `local-conflict`: a component local object is declared by another component as well.
- `definition-mismatch`: components disagree on kind, datatype, unit, scaling, shape,
  volatility, referenced objects (axes and the `input` of an axis), or on limits where both
  of them state limits. A declaration that omits limits defers to the producer rather than
  disagreeing with it, a relaxation `volatile` has no use for, being required on every
  definition ([section 3.3.1](#331-one-object-several-declarations)).
- `duplicate-declaration`: a component declares the same object more than once.
- `consumer-storage`: an `input` declaration states `init` or `section`. What an object
  starts out as, and where it lives, is decided by the component that produces it, so a
  reader stating either is claiming storage it does not own, rather than holding an opinion
  to be outvoted.
- `duplicate-component`: two files declare the same component name.
- `duplicate-type`: two files declare the same type name.
- `duplicate-unit`: two files declare the same unit ([section 3.8](#38-unit-vocabulary)).
- `duplicate-section`: two files declare the same memory section
  ([section 3.5](#35-memory-placement)).
- `duplicate-constant`: two files declare the same constant name
  ([section 3.9](#39-constant-vocabulary)).
- `unknown-type`, `type-kind`, `type-cycle`: a `typename` names no type any file of the
  project declares, a declared type is used where its shape does not fit, or structures
  nest each other so that neither has a size.
- `unknown-unit`: a unit is not in the vocabulary the project declares
  ([section 3.8](#38-unit-vocabulary)); declared nowhere, units stay free text and the
  check never fires.
- `unknown-section`: a definition names a memory section no file declares
  ([section 3.5](#35-memory-placement)). Unlike a unit there is no free text fallback,
  because a section without declared properties is a name the placement checks can say
  nothing about.
- `section-access`: a measurement, which the software writes, is placed in a `read-only`
  section.
- `unknown-constant`: a shape names a constant that no file of the project declares
  ([section 3.9](#39-constant-vocabulary)); the nearest declared name is suggested.
- `enum-conflict`: one enum name is used with different enumerators. The ordered name and
  value pairs are compared, so a reordering conflicts and the free text descriptions do
  not.
- `init-invalid`: an initial value or an enumerator does not fit the datatype or the shape.
- `unknown-reference`, `reference-kind`: a curve, map or axis refers to an object that does
  not exist or has the wrong kind.
- `reserved-identifier`: a name collides with a C keyword, with a name `<stdint.h>` or
  `<stdbool.h>` declares, or with an identifier the C standard reserves for the
  implementation, that is a double underscore anywhere, or a leading underscore followed by
  a capital letter. The set is fixed by the standard rather than read out of any header, so
  the verdict does not depend on a toolchain.
- `name-collision`: two names that are distinct in the description files become the same
  C identifier or the same generated file. Exactly these pairs are compared: enumerators of
  different enums, an enumerator and a data object, a data object and the name of an enum
  or of a declared type, a declared constant and a data object, an enum, an enumerator or
  a declared type, and two component names differing only in case.
- `file-extension`: a description file is not named `*.ddd.json`.
- `json-syntax`, `schema`, `file-kind`, `file-not-found`, `include-cycle`: the file tree
  cannot be read. These five are the checks whose severity cannot be changed.
- `include-empty`: a wildcard include matches no file. It is relaxable, because a pattern
  that is empty in one variant of a project is legitimate. A
  literal include naming a missing file is `file-not-found` instead
  ([section 3.1](#31-project-description)).

Warnings:

- `storage-mismatch`: components disagree on how the A2L presents the object; the producer
  wins.
- `section-alignment`: an object needs stricter alignment than its section guarantees. This
  is a warning rather than an error because the need is the description's estimate, and the
  compiler's word on the real layout is final.
- `condition-mismatch`: declarations of one object use different preprocessor conditions.
- `unused-output`: an output is read by nobody.
- `limits-out-of-range`: limits exceed what the datatype can represent under the
  conversion; for an enum that is the span of its enumerators. The comparison allows a
  relative tolerance of 1e-9 at the range ends, so a limit spelled exactly at the edge of
  a floating point range is not refused for rounding.
- `enum-duplicate-value`: two enumerators share a value.
- `name-similar`: two object names differ only in upper and lower case.
- `a2l-unrepresentable`: an object, or a member of a structured object, cannot be fully
  described by the A2L version DDD writes;
  today that is an array of more than three dimensions, which the `MATRIX_DIM` of
  version 1.6.1 cannot carry. The check fires only for an object the A2L exports, and the
  emitted file writes every dimension out regardless, which a 1.7 reader accepts.

Information:

- `empty-component`: a component declares no data object at all.

### 4.1 Comparing two deliveries

The checks above answer whether a set of components fits together. DDD **shall** also
answer whether one delivery can replace another, which is a different and directional
question, and one that cannot be answered from the description files alone, because the
delivery being replaced has moved on. The data dictionary of a delivery is therefore the
artefact to archive (`ddd dump`, [section 7](#7-tool-interface)), and the comparison is a
function of two of them. Either side **may** also be given as a project or component
description, which is resolved to its dictionary on the spot; the archived dictionary is
what keeps the question answerable after the descriptions have moved on. The baseline is
analysed in its own right, and only its error findings are carried into the report, each
prefixed with "in the baseline:", so that a broken baseline is visible without drowning
the comparison.

A change **shall** be graded by what it costs the consumers.

Errors, because the consumers of the object become wrong, whether or not they still
compile:

- `removed-object`: an object is gone that a component read.
- `changed-interface`: kind, datatype, unit, scaling, shape, referenced objects or locality
  changed. Locality is whether the object is local to its component
  ([section 2.1](#21-scope)); a local object becoming shared, or the reverse, changes who
  **may** use it.

Warnings, because behaviour or tooling changes while no consumer becomes wrong:

- `removed-unused-object`: an object is gone that no component read.
- `changed-storage`: the initial value, the volatility or the section changed. On a
  calibration object the volatility also decides whether a tool can still change the value
  in a running target, and the section says literally which memory the object ends up in.
- `narrowed-limits`: the physical limits got tighter, so calibrated data **may** no longer
  fit.
- `changed-owner`: another component produces the object now.
- `changed-condition`: the preprocessor condition changed, namely the producer's, which is
  the one the dictionary records on the object
  ([section 3.3.1](#331-one-object-several-declarations)).
- `changed-a2l`: the resolved A2L presentation changed, that is the export (compared as
  resolved, [section 3.3.1](#331-one-object-several-declarations)), `format` or
  `display_identifier`. A changed unit is `changed-interface`, and descriptions, of
  objects and of enumerators alike, are not compared.
- `project-mismatch`: the two dictionaries name different projects, so the baseline is
  probably not the predecessor of this candidate.

Information:

- `added-object`: the candidate declares an object the baseline did not.

Widening a limit **shall** be silent, because every value the baseline allowed still fits.
Limits that got tighter **shall not** be reported on an object whose interface changed as
well: the interface change is the finding to act on, and the narrowing would only bury it.
This is deliberately coarser than reporting only a narrowing that is a consequence of the
interface change, which nothing can decide; an independent narrowing of the same object is
therefore also held back until the interface change is resolved.

## 5 Generated artefacts

### 5.1 C code

The C sources **shall** be rendered from templates the *project* provides, and DDD
**shall** ship no default set. What the generated code looks like, that is the comment
convention, the banner, the include guards, and whether an object is commented and in which
form, does not follow from the declared data: it is the house style of the software the
code is generated into, it differs between projects, and a generator that fixes it imposes
one project's habits on every other. DDD therefore owns the data, and the project owns its
presentation. Example templates **shall** be shipped and locatable, as a starting point to
copy rather than as a fallback.

The set of generated files **shall** follow from the template directory alone, so that a
build system can declare its outputs without running the generator first:

| template | renders to |
| --- | --- |
| `<name>.jinja2` | `<name>`, once per project |
| `_<name>.jinja2` | nothing; a helper the other templates **may** import |
| `{component}<rest>.jinja2` | one file per component, the component's name replacing the placeholder |

The component name replaces every occurrence of the placeholder verbatim, so a component
`SensorHub` renders `{component}.h.jinja2` to `SensorHub.h`, and the case of a generated
file is the case of the component's name. A template in a subdirectory of the template
directory is importable but never rendered. A project template receives two variables:
`filename`, the name of the file being rendered, and `model`, the resolved view of the
dictionary; a `{component}` template additionally receives `header`, the view of its
component. The rendering is strict: a name a template misspells, or a template that does
not parse, is a usage error naming the template and the line
([section 7](#7-tool-interface)), not silently empty output. A template directory containing no template, and two artefacts claiming the
same output path, are usage errors rather than findings
([section 7](#7-tool-interface)).

Whatever the templates spell, the *data* they are given is fixed: measurements are writable
variables and calibration objects are `const`, each of them additionally `volatile` when
its declaration states so; a declaration that carries a condition is offered with that
condition, so that it can be wrapped in `#if` / `#endif`; and input objects are marked
`const` for the consumer header when the project asks for it
(`ddd generate --const-inputs`), so that a write access does not compile. The qualifier
reaches the hand written code that reads the object, so a project that turns `volatile` on
for an array finds that passing it to a helper typed for a plain `const` one no longer
compiles, and re-types the helper; the cast that would silence it is itself refused by a
warning set containing `-Wcast-qual`. The declared constants
([section 3.9](#39-constant-vocabulary)) are offered to the templates as well, and an
object dimensioned by a constant carries the constant's name in its definition and in
every declaration; the example templates emit each constant as a `#define`.

The example templates generate the definitions into one file per project and the
declarations into one header per component, and the build integration of
[section 7.1](#71-build-system-integration) expects that arrangement. The asymmetry is
deliberate: splitting the declarations is what enforces the access rules, because a
component sees the objects it declared and a reference to any other global is an undeclared
identifier, whereas splitting the definitions enforces nothing, because after linking there
are only symbols. Three things argue for the single file instead.

Every object has a definition site. The objects of a project partition by owner, so a file
per owner would cover all of them but the ones no component owns, which arise whenever
`missing-producer` is relaxed, to generate a single component on its own or an image that
deliberately links a subset of the project. Those objects have no component and would have
no file; the project wide file defines them like any other.

The build system can name what it compiles. The rule above lets it derive the generated
files from the template directory, and a `{component}` template is the one entry it cannot
resolve, because the component names come out of the description files and, for an image,
the subset that matters comes out of its link graph. A generated header survives that,
because a consumer depends on the directory it lives in rather than on its name; a source
has to be named before it can be compiled.

The definitions reach the image whole. An object that no compiled code references, for
example a measurement only the calibration tool reads, has nothing to pull it out of a
library archive, so the definitions are compiled as a unit of their own and linked into the
image rather than into the libraries of the components that own them. A definition file per
component invites the second arrangement, in which the linker drops precisely the objects
nobody but the calibration tool reads, and the A2L is left describing storage the image
does not contain.

None of this forbids the arrangement: a `{component}` template renders a `.c` as readily as
a `.h`. A project that wants its definitions spread over several files **may** also write
several project wide templates, each rendering the part it selects, and the build
integration compiles every one of them; per-component sources it does not compile, for the
reason above.

Generated output is deterministic to the byte: objects are sorted by name within their
component's group, member paths by path, components keep the include order of the project,
and wildcard includes expand in sorted order ([section 3.1](#31-project-description)), so
the same project generates the same bytes on any machine. Names sort by code point, an
upper case name before every lower case one and `cell[10]` before `cell[2]`, which is a
spelling rule rather than a locale's; only file paths order as the platform compares them.
Files are written UTF-8, and a rendered file whose content has not changed is left
untouched, so that a regeneration does not cascade into a rebuild.

Assignment of objects to freely chosen generated `.c`/`.h` files is *planned*.

### 5.2 A2L

ASAM MCD-2 MC output containing:

- `MEASUREMENT` for every measurement, `CHARACTERISTIC` for parameters, value blocks,
  curves and maps, `AXIS_PTS` for axes.
- `RECORD_LAYOUT` per datatype and storage category; maps are stored row wise, that is the
  C declaration is `[y][x]` and the A2L index mode is `ROW_DIR`.
- `AXIS_DESCR` with `COM_AXIS` and `AXIS_PTS_REF` for the axis of a curve or map.
- `COMPU_METHOD` shared between objects with the same conversion and unit, `COMPU_VTAB`
  per enum.
- one `GROUP` per component that contributes at least one exported object, referencing
  the measurements and characteristics it declares; a component contributing none gets no
  empty `GROUP`.
- the address field of every object taken from the address information (`ECU_ADDRESS` is
  the keyword the format uses for it), `SYMBOL_LINK` always; an object the address
  information does not cover keeps address `0x00000000`
  ([section 6](#6-address-information)).
- deterministic order: records sorted by object name, member paths by path, `GROUP`s in the
  component order of the project.

The file opens with `ASAP2_VERSION 1 61` and one `PROJECT` holding one `MODULE`, both named
after the project ([section 3.1](#31-project-description)). The `PROJECT` carries a
`HEADER` stating the project description, the project name as `PROJECT_NO` and the
generator with its version; the `MODULE` carries a `MOD_COMMON` stating the
byte order and fixed alignments (1/2/4/8, floats 4/8) and, when the project declares
constants ([section 3.9](#39-constant-vocabulary)), a `MOD_PAR` stating one
`SYSTEM_CONSTANT` per declared constant in name order. Every record spells its sizes as
resolved numbers, because the format accepts no symbol where a `MATRIX_DIM` expects a
count. The byte order is the build's to
state (`ddd generate --byte-order little|big`, default little, emitted as
`MSB_LAST`/`MSB_FIRST`): it is a property of the target the description files cannot know,
and a tool reading multi byte values under the wrong one misreads every value.

Generated identifiers are deterministic: record layouts `RL_VALUES_<TYPE>` and
`RL_AXIS_<TYPE>` per datatype and storage category, computation methods `CM_<enum>`,
`CM_LIN_<unit>` and `CM_IDENT_<unit>`, the unit slugged into identifier characters with
`_2`, `_3` appended on a collision, and one `COMPU_VTAB` named `VTAB_<enum>` per enum. An
enum is a `TAB_VERB` referring to its `COMPU_VTAB`. A linear conversion is a `RAT_FUNC`
whose `COEFFS` state raw as a function of physical, so the stated slope is the inverse of
`factor`. An identity with a unit is `IDENTICAL`, and one without a unit gets no method at
all: the record says `NO_COMPU_METHOD`. What the description files do not carry is emitted
neutrally: resolution and accuracy of a `MEASUREMENT` and the `MaxDiff` of a
`CHARACTERISTIC` are 0, and the display format defaults to `%8.0` for integral values,
that is an integer datatype under an identity or under a linear conversion whose `factor`
and `offset` are whole numbers, and to `%8.3` otherwise, overridden per object by `format`
([section 3.3](#33-data-object-definition)). An object stating no `description` carries
its name as the A2L long identifier. Quoted strings escape backslash and quote and
replace control characters by a space, and numbers are written in their shortest round trip
form, an integral value without a decimal point.

Export is closed over references: an exported curve or map pulls the axes it refers to into
the A2L, and a pulled in axis pulls the measurement indexing it, whatever their own
`export` says, because an `AXIS_PTS_REF` to an absent axis would be an invalid file rather
than a smaller one.

A record whose object is declared under a preprocessor condition is preceded by a comment
naming that condition, because the format has no conditional construct of its own.

A structured object ([section 3.3.2](#332-naming-a-declared-type)) reaches the A2L as one
object per value-holding member, named by its C access path, for example
`Inlet.latest.value` or `Inlet.cell[2].raw`, which is at once the A2L name, the
`SYMBOL_LINK` symbol and the key of the address map
([section 6](#6-address-information)). A member of a measurement-kind object becomes a
`MEASUREMENT`, and a member of a parameter-kind object becomes a `CHARACTERISTIC`, as
`VALUE` when scalar and as `VAL_BLK` with `MATRIX_DIM` when an array. An array of
structures is expanded element by element instead, one set of members per `[index]`.
Members use the ordinary per-datatype `RECORD_LAYOUT`, the structure itself getting no
record of its own, and the
component's `GROUP` references the member paths. A `bits` member reaches no A2L at all:
`SYMBOL_LINK` can carry a byte offset but not a bit position, so a bitfield waits for a
build to report both the word and the bits *(planned)*.

Selectable output versions (1.5.1, 1.6, 1.7), `FUNCTION` and nested groups, `IF_DATA` for
XCP/CCP with measurement rasters, and A2L *import* for migration and merging are *planned*.

## 6 Address information

The addresses of the generated objects are only known after linking. DDD accepts a symbol
to address map in JSON form (`ddd generate --address-map`): one flat JSON object mapping
each symbol to its address. The key is the C identifier of an object or, for the member of
a structured object, its access path, for example `Inlet.cell[2].raw`, exactly as the A2L
names it ([section 5.2](#52-a2l)). The address is a JSON number, or a string read as
hexadecimal with a `0x` prefix and as decimal without one, and it **must** fit an unsigned
32 bit `ECU_ADDRESS`. A key the project does not know is ignored, and an object the map
does not cover keeps address `0x00000000` rather than failing the run: a map extracted from
a linker output legitimately omits the objects a condition compiled away, and `SYMBOL_LINK`
lets a downstream tool resolve those it cares about. Reading the linker output directly
(ELF/DWARF, IEEE-695) and cross-checking the linked symbols against the declarations is
*planned*.

## 7 Tool interface

DDD is a command line tool, so that it can be driven from make, batch and CI jobs. It
offers at least: checking a project (`ddd check`, [section 4](#4-consistency-checks));
comparing two deliveries (`ddd compare`, the baseline before the candidate, or
`ddd check --baseline` for both questions in one exit code;
[section 4.1](#41-comparing-two-deliveries)); generating the artefacts (`ddd generate`,
[section 5](#5-generated-artefacts)); listing the resolved data objects (`ddd list`, as a
table stating the physical reading of a stated initial value beside the raw one, or, in
JSON, as an object carrying `project`, `components` and `variables` beside
the findings);
writing out the data dictionary itself (`ddd dump`); printing the JSON schema of the file
formats and of the dictionary (`ddd schema`, one kind to stdout or every kind written into
a directory with `ddd schema all -o`, each file named `ddd_<kind>.schema.json`); listing
the files a project description
depends on (`ddd sources`, which lets a build system re-run its configure step when one
changes; in JSON the paths are a `sources` list beside the findings); recording how a
build is configured to run DDD (`ddd build-info`,
[section 3.6](#36-build-record)), so that a tool outside the build can apply the same
project and the same severities; serving the checks to an editor over the Language Server
Protocol (`ddd lsp`, [section 7.2](#72-editor-integration)); listing the available checks
(`ddd checks`, each with its default severity, the unrelaxable ones marked); reporting
where its build system integration and its example templates
live (`ddd cmake-dir`, `ddd templates-dir`; a piece not installed is a usage error); and
printing its own version (`ddd --version`). The root handed to a command is a project or a
single component file; a component alone is checked with every check, the whole project
ones included, because holding them back is the editor's leniency
([section 7.2](#72-editor-integration)), not the command line's.

Every command that reports findings can produce machine readable JSON (`--format json`): a
`diagnostics` list, each finding carrying `check`, `severity`, `message`, a `location` of
`path`, `pointer`, `line` and `column`, and `notes` of the same shape, and a `summary`
counting by severity. In plain text, a finding is written
`path:line:column#pointer: severity[check]: message`, the pieces of the location present
as far as they are known and its notes indented beneath it; findings are ordered by
severity, then path, then location, numeric parts of a pointer compared as numbers; and a
clean `ddd check` closes with an `ok:` line counting the objects and components it found
consistent. `generate` adds the files it wrote with their status (`created`, `updated` or
`unchanged`), and `dump`
keeps its stdout for the dictionary, reporting findings on stderr. The exit code
distinguishes clean runs (0), findings (1) and usage errors (2). A findings exit is
reserved for findings reported *as errors*: a run whose findings are all warnings is a
clean run unless `--strict` says otherwise. `ddd generate` with error findings writes
nothing, because a stale artefact is preferable to a wrong one written halfway into a
build, unless `--force` asks for the outputs anyway; the exit stays a findings exit in
either case. `ddd generate --dry-run` reports what it would write and writes nothing.

The data dictionary **shall** be writable and readable as JSON, so that a generator DDD
does not ship can consume it without depending on the implementation. The dictionary names
its own format (`format`, today `4`), raised only when the document's shape changes, so
that an archived delivery says which shape it carries, which is what the build record's
`format` does for it ([section 3.6](#36-build-record)). A reader handed a dictionary whose
`format` is newer than the one it implements refuses it (`schema`), located at the file;
formats up to its own it validates strictly.

### 7.1 Build system integration

DDD ships a CMake module with two calls: `ddd_add_component(<target> JSON <file>...)`
registers descriptions, component and types files alike, on their target, and
`ddd_generate(<image> ...)` generates for an image. It generates into the build tree,
exposes the generated headers to the components through an interface library and compiles
the generated definition sources into the image as an object library of their own, so that
an object no compiled code references is not dropped ([section 5.1](#51-c-code)).

`ddd_generate` knows two modes. In the collected mode, which is the default, the registered
descriptions travel the link graph as a transitive target property, and the project
description is assembled in the build directory from the closure the image actually links
([section 3.6](#36-build-record)); it needs a CMake new enough to carry properties across
links, and the module itself refuses a CMake older than its stated floor with a message
naming it. The assembled project is named by `NAME`, defaulting to the image's name sanitised
into an identifier, and that name becomes the A2L project, module and file name
([section 5.2](#52-a2l)); its includes keep the link graph's traversal order, first
occurrence kept, which orders the components and with them the `GROUP`s, while the objects
themselves sort by name regardless ([section 5.1](#51-c-code)). With `PROJECT <file>` a
hand written project description is used instead, which is the mode for an older CMake, or
for a project layout the link graph does not mirror; `NAME` is then ignored in favour of
the name written inside the file. An `ADDRESS_MAP <file>` names the address map of
[section 6](#6-address-information): the map is a dependency of the generation, so
rewriting it after linking is what makes the next build run DDD a second time with real
addresses ([section 1.6](#16-position-in-the-build-process)), and the C sources that second
run re-renders are byte identical and trigger no rebuild ([section 5.1](#51-c-code)). A
map named inside the build tree that does not exist yet is seeded empty at configure time,
so that the first build runs with address zero instead of failing over a file only the
link can produce.

The remaining keywords mirror the command line: `TEMPLATE_DIRECTORY` (required,
`--template-dir`), `OUTPUT_DIRECTORY` (defaulting into the build tree), `BYTE_ORDER`,
`CONST_INPUTS`, `NO_A2L`, `STRICT` and repeatable `SEVERITY` entries written
`check=severity` ([section 4](#4-consistency-checks)), the latter two also recorded in the
build record, plus `LINK_LIBRARIES` for compiling the generated definitions, `DEPENDS` for
extra generation dependencies, and `NO_PROPAGATE_HEADERS` to stop the generated headers
being linked into every registered component.

### 7.2 Editor integration

The checks **shall** also be served over the Language Server Protocol (`ddd lsp`), so that
a project is checked while it is written rather than when it is built. The same loader, the
same analysis and the same severity policy answer both, because an editor that disagrees
with the build about what is wrong is worse than an editor that says nothing.

The server offers, from a description file: the findings of
[section 4](#4-consistency-checks), drawn over the key they are about rather than over the
file; go to definition and find references across files, which is the question a schema
cannot answer at all, because the producer of an `input` is in a file the author might not
know the name of; a summary of a data object on hover, the physical reading of its
initial value included; renaming an object everywhere the
project writes it, refused up front for a name the C language does not allow or one the
project already uses, whether for another object, an enum, an enumerator, a type or a
constant,
because a rename that silently merges two objects compiles, links, and shares storage
nobody intended to share; and quick fixes that reconcile one key across the declarations of one object, in either
direction, including removing a key the others do not have.

Which project a file belongs to comes from the build records of
[section 3.6](#36-build-record), found by searching the build directories the client names,
or, unconfigured, the conventional directories `build`, `out` and `cmake-build-*` under the
workspace, recursively for `ddd-build.json`. A file claimed by several builds is checked
under each of them and the findings published together: a component linked into two images
is in two projects, and the answer to which one the reader cares about is both. A file no
build record claims is looked for in a containing project instead: the server walks from
the file's directory up to the workspace root, and the file is checked under the project
descriptions of the nearest directory that include it. A file
belonging to no build and to no such project is still checked, on its own, with the seven
checks that
need every component of a project ([section 4](#4-consistency-checks)) held back: a
component read alone has inputs nobody produces and outputs nobody reads by construction
rather than by mistake, and reporting those buries the findings that are about the file in
front of the reader. Each check declares whether it needs the whole project, so the two
modes cannot drift apart.

The server re-reads a file from disk when it is opened or saved. Each finding is also
published at the locations of its notes, so that both sides of a conflict carry a mark.
The build records a search discovers are announced as log messages, and a record that
cannot be read is skipped.

A message body the server cannot parse is answered with the protocol's parse or
invalid-request error and does not stop the server; a corrupted frame header, after which
no message boundary can be trusted, ends the session with a message rather than a failure
trace.

The server speaks the protocol on stdin and stdout, and takes the build directories as
repeatable `-b` arguments; the shipped VS Code extension exposes them as the setting
`ddd.buildDirectories`, and the executable to launch as `ddd.executable`.

An editor extension **shall** do no more than launch the server and point it at the build
directories: everything a reader sees is the tool's answer, so that an editor DDD ships
nothing for is not at a disadvantage.
