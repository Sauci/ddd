# String conversion

- **Date:** 2026-09-10
- **Status:** design approved, not implemented
- **Touches:** the models, the analysis, the data dictionary, the c backend, the a2l
  backend, the editor, the documentation and the demo

## 1 What this adds

Nothing in DDD carries text today. The eleven datatypes are numbers, the three conversions
map numbers, and every object kind maps onto one a2l record type. A software label, a
vehicle identification number, a part number in calibration memory, or the name of the
current state written into RAM is a byte array that every consumer reads as a row of
numbers - the generated c initialises it element by element, the a2l shows `86 49 46 50`
where an engineer expects `V1.2`, and a consumer that reads the bytes as text has agreed on
nothing with the producer that writes them.

This design adds a fourth conversion kind, `string`:

```json
{ "kind": "string" }
```

The conversion is where it belongs, because the conversion is what already answers how the
bytes in storage are to be read - as themselves, scaled, or named - and "as text" is the
fourth answer. The kind and the datatype stay what they are: a string measurement is a
`measurement`, a string parameter a `value_block`, and both are byte arrays in the c,
which is what a project on AUTOSAR's `Platform_Types.h` wants, there being no `char` in it.
It also mirrors what the a2l format itself does, which is to describe a string as a block
of `UBYTE` with an instruction to display it as text.

Two other homes were considered and rejected. A datatype `char` conflates storage with
reading: a `char` under the identity is a byte, so the datatype alone would never say
"text", and a `Platform_Types` project has no such type to spell. An object kind `text`
misplaces it: a kind is the storage class, `measurement` or calibration data, and a string
can be either.

## 2 Out of scope

- **Non-ASCII text.** The content of a string init is printable ASCII. The a2l is an ASCII
  format until 1.7's `ENCODING`, and a c literal carrying UTF-8 needs a policy about
  execution character sets that no target agrees on. Section 14 says how this may return.
- **Arrays of strings.** A string is exactly one dimension. Vector's own generator refuses
  the shape for the reason that decides it here: "the ASAP2 format does not support string
  arrays", and splits such an array into one object per string. DDD already has that
  split: an array of structures with a string member expands element by element,
  `Names[2].text` being a string of its own.
- **A `char` spelling in the c.** The templates render `c_type` or `datatype` as they do
  for every object; a project whose house style wants `char` writes that in its template.
- **Describing a RAM string as an a2l characteristic.** Vector's generator turns every
  string into an `ASCII` characteristic, writable or not, which shows the text but claims
  an adjustable object for storage the software writes. DDD keeps the record type
  following the kind. Section 14 names the option this could become.

## 3 The conversion

### 3.1 Spelling

`{ "kind": "string" }`, with no further keys. Unlike the other three kinds, `kind` is
required for it: the inference of section 3.4 of `SPEC.md` reads `{}` as the identity and
a string has no key of its own to be inferred from. The model is a fourth variant of the
tagged union in `src/ddd/models/conversion.py`, `StringConversion`, frozen and forbidding
extra keys like the others. Its forward and backward mappings are the identity on one
byte, so that `physical_range` and every caller of it need no special case: the raw range
of the datatype is the range of one byte. It describes itself as `string`, which is what
`definition-mismatch`, `changed-interface` and the hover print.

### 3.2 Where it may be written

Wherever a `datatype` and a `conversion` sit side by side - a definition, a structure
member, a scalar type - under rules that are the same in all three places, shared the way
`refuse_enum_on_non_integer` is shared, so that the verdict cannot depend on where the
pair happens to be written. Every rule is a shape error of one file, refused where it is
written as `schema`; no identifier is added to the public interface.

- **The datatype is `uint8` or `sint8`.** A string is bytes. Vector's checker accepts a
  `UBYTE` or an `SBYTE` record layout for an ASCII string and nothing else, and c allows a
  string literal to initialise an array of either character type.
- **The shape is exactly one dimension**, the length of the string in bytes. On a
  definition that is `dimensions` of length one, so the kind is `measurement` or
  `value_block`: a `parameter` has no dimensions, an `axis`, a `curve` and a `map` are
  tables of numbers. On a member it is a `value` member with one dimension; a `bits`
  member carries no string.
- **No `unit`, no `limits`, no `a2l.format`.** Vector's manual states the rule for its own
  strings, "no conversion rule is allowed", and DDD's reasons are the same: text has no
  unit, no physical range and no display format. Each is refused where it is stated. A
  scalar type has no `a2l` block, so only the first two apply there.

A scalar type may carry a string conversion, and then fixes the datatype and the reading
for every declaration and member that names it, while the length stays theirs to state,
exactly as the shape of any typed object is the declaration's. The shape rule is therefore
checked where the type is *named*: a declaration naming a string type states one
dimension and is a measurement or a value block, and a member naming one is a `value`
member with one dimension. A violation is `schema` at that declaration or member, raised by
the analysis with a note pointing at the type, the precedent being the infinite-limits
refusal that `_limits_stay_finite` raises under the same identifier. A declaration naming a
string type may still state an `a2l` block, so `a2l.format` is refused there by the same
analysis pass.

### 3.3 Structured objects

A string member reaches the dictionary as a leaf whose conversion is the string, at its
access path, and the leaf's kind is the instance's: a member of a measurement-kind instance
is a string measurement, a member of a parameter-kind instance a string parameter. An
array of structures expands as it does today, one leaf per element, which is how an array
of strings is written.

## 4 Initial values

`init` gains a third spelling for a string object: a JSON string.

```json
{ "name": "SwLabel", "kind": "value_block", "datatype": "uint8",
  "conversion": { "kind": "string" }, "dimensions": [16],
  "init": "V1.2.3", "volatile": false }
```

- The content is printable ASCII, code points 0x20 to 0x7E. Anything else - a control
  character, a non-ASCII letter - is `init-invalid` at `definition.init`, because neither
  the c literal nor the a2l could carry it unambiguously.
- The string is **shorter than the dimension**, so that the terminating zero fits: a
  string of sixteen characters in sixteen bytes is legal c and refused by C++, and the
  reader of the generated file cannot tell that the terminator is missing. Too long is
  `init-invalid`, counted against the resolved dimension, so a length spelled as a
  constant name is resolved first, as every init shape is. The empty string is allowed:
  it is an explicit initialiser, all zeros, which is not the same as no initialiser.
- The two existing spellings remain for a string object: a single integer fills every
  byte, and a list of integers sets each byte, both raw and both checked as today. A
  project that keeps a fixed-width field without a terminator writes the list.
- A JSON string on an object whose conversion is not a string is `init-invalid`, at
  `definition.init`, saying which conversion the object has. The model accepts the
  spelling on every object, because the conversion of a declaration naming a type is only
  known once the type is, and one finding identifier for every wrong init is worth more
  than refusing half the cases a step earlier.
- A consumer stating an init is `consumer-storage`, as it is for every init.

The `InitValue` type of `src/ddd/models/objects.py` gains a `str` arm. Every reader of an
init - `flatten`, `broadcast`, `check_shape`, the c initialiser, the hover's drawing, the
list command's cell, the comparison's advisory `init` field - is given the string branch,
because a string is neither a scalar to broadcast nor a list to walk.

## 5 What resolves

- **Limits** are the raw range of the datatype, 0 to 255 or -128 to 127, which is what the
  a2l record states for an ASCII object; nobody can state others.
- **Comparison.** `conversion_identity` dumps the model as it does for the identity and
  the linear kinds, so `{"kind": "string"}` compares as written: a byte array turning into
  text is `definition-mismatch` inside a project, `conversion: string != identity`, and a
  `changed-interface` between two deliveries, with no code that knows about strings.
- **Readings.** `raw_reading` answers nothing for a string, as it does for the identity:
  one byte has no reading of its own, and the whole init is shown as text where an init
  is shown.
- **The enum registry** is untouched; a string names nothing.

## 6 The c

The declaration does not change: `uint8_t SwLabel[16]`, qualified as its kind and its
`volatile` say, dimensioned by the constant name where the project spells one. The
templates are untouched.

The initialiser is the one thing that changes. A string init renders as a c string
literal, `"V1.2.3"`, with `"` and `\` escaped and `?` written as `\?` so that two of them
before `=`, `/` or `(` cannot form a trigraph under a pedantic pre-C23 dialect. C fills the
elements the literal does not cover with zero, and the length rule of section 4 guarantees
the terminator is among them. An integer or a list init renders exactly as today.

```c
const uint8_t SwLabel[16] = "V1.2.3";
```

## 7 The a2l

Every claim in this section was checked against the 1.51 specification, the 1.61 demo file
Vector ships, and Vector's ASAP2 Tool-Set manual; section 13 says what each one settles.

### 7.1 A string parameter

A `value_block` under a string conversion, and a string member of a parameter-kind
instance, become a `CHARACTERISTIC` of type `ASCII`:

```text
/begin CHARACTERISTIC SwLabel "Software label"
  ASCII 0x00000000 RL_VALUES_UBYTE 0 NO_COMPU_METHOD 0 255
  SYMBOL_LINK "SwLabel" 0
  NUMBER 16
/end CHARACTERISTIC
```

- The record layout is the ordinary one of the datatype, `RL_VALUES_UBYTE` or
  `RL_VALUES_SBYTE`: the demo's ASCII object uses `FNC_VALUES 1 UBYTE ROW_DIR DIRECT`,
  which is what DDD already writes for a value block.
- The conversion is `NO_COMPU_METHOD`, always, since no unit can be stated; no method is
  created and no `FORMAT` is written.
- The limits are the datatype's raw range, as on every ASCII object in the sources.
- The length is `NUMBER`, the array size in bytes. The 1.51 text already notes that
  `NUMBER` "should be replaced by MATRIX_DIM", yet the 1.61 demo and Vector's current
  generator both emit `NUMBER` for an ASCII object and Vector's checker accepts either, so
  `NUMBER` is the spelling every reader of a 1.6.1 file understands. The `MATRIX_DIM`
  spelling waits for 1.7 output, section 14. No `MATRIX_DIM` is written beside it.
- `DISPLAY_IDENTIFIER`, the condition comment and the address are as for every object.
- An array of structures with a string member yields one such record per element, at the
  element's path, which is the shape Vector's `SPLIT` produces.

`CharacteristicView` gains a `number` field beside `matrix_dim`, and the template writes
whichever is set.

### 7.2 A string measurement

The format has no string measurement, in any version: the `Datatype` of a `MEASUREMENT`
is an enumeration of numeric types from 1.51 through 1.7.1, and the keywords that give a
characteristic its text - `ASCII`, `NUMBER`, 1.7's `ENCODING` - exist on a
`CHARACTERISTIC` alone. A `measurement` under a string conversion, and a string member of
a measurement-kind instance, are therefore described as what the format can say, the byte
array they are, with an `ANNOTATION` that tells the reader what they are looking at:

```text
/begin MEASUREMENT StateName "Name of the current state"
  UBYTE NO_COMPU_METHOD 0 0 0 255
  ECU_ADDRESS 0x00000000
  SYMBOL_LINK "StateName" 0
  MATRIX_DIM 16 1 1
  /begin ANNOTATION
    ANNOTATION_LABEL "string"
    /begin ANNOTATION_TEXT
      "16 bytes of text; ASAP2 1.6.1 has no string measurement, so the tool shows the bytes"
    /end ANNOTATION_TEXT
  /end ANNOTATION
/end MEASUREMENT
```

- `ANNOTATION` is a documented child of `MEASUREMENT` since 1.51, all three of its parts
  optional, whose purpose the specification gives as "an application note which explains
  the function of an identifier for the calibration engineer" - exactly this note. Tools
  show it in the object's properties. `ANNOTATION_ORIGIN` is not written.
- The `MATRIX_DIM` is the ordinary array form; a raster and its `IF_DATA` are written as
  for every measurement, since measuring a byte array over DAQ is legitimate.
- No finding is raised. The author cannot fix what the format lacks, and a warning for
  every string measurement of a project would be noise that trains people to ignore
  warnings; the documentation says what the tool will show.

`MeasurementView` gains an `annotation` field, `None` for every object that is not a
string.

### 7.3 Untouched

Groups, exports and the reference closure do not change: a string is referred to by
nothing and refers to nothing. The compu method builder never sees a string object, since
`reference` answers `NO_COMPU_METHOD` for it before any key is built - the same early
return the identity without a unit takes.

## 8 The dictionary

Two shapes of the document change: `conversion` carries a fourth `kind`, and `init` may
be a string. Both are visible to a consumer validating against the published schema, so
`DICTIONARY_FORMAT` becomes 8. A dictionary of format 7 or older reads back unchanged - it
contains no string, since nothing could have written one - and a reader of format 7
refuses a format 8 file as it refuses any newer one. The three committed schemas that
carry a conversion or an init, the component, types and dictionary schemas, are
regenerated with `ddd schema all -o schemas`; the test that pins them says so.

`enums` does not change. The `string` conversion is recorded on each object that carries
it, `{"kind": "string"}`, and nowhere else.

## 9 Editor and command line

- **Hover.** The conversion row reads `string`. A string init is shown as `init "V1.2.3"`,
  quoted, with no reading beside it; no sparkline is drawn for it. The limits row and
  everything else are as for any byte array.
- **`ddd list`.** The INIT column shows a string init quoted, `"V1.2.3"`, where a list is
  abbreviated to `[...]`. The json payload carries the string as data.
- **Completion and validation.** The published schema lists the fourth `kind`, so an editor
  offers it and refuses a misspelling as it is typed; the `init` property accepts a string.
- **Navigation, rename, the id action.** Nothing: a string names no identifier.

## 10 Checks

No check identifier is added. What the feature reports, by identifier:

- `schema`: a string conversion on a datatype other than `uint8` or `sint8`; on a
  `parameter`, `axis`, `curve` or `map`; on a `measurement` or `value_block` with other
  than one dimension; on a `bits` member or a `value` member with other than one
  dimension; beside a `unit`, `limits` or `a2l.format`; and the same rules for a
  declaration or member naming a string scalar type, raised by the analysis.
- `init-invalid`: a string init that is too long, that is not printable ASCII, or that is
  written on an object whose conversion is not a string.
- `definition-mismatch` and `changed-interface`: unchanged code, a changed answer.
- `consumer-storage`: a consumer stating a string init, as any init.

`limits-out-of-range` cannot arise, since limits are refused, and `a2l-unrepresentable` is
not raised for a string: the byte array is representable, only its reading is not.

## 11 Testing

Tests first, in the files that own each concern:

- `tests/test_models.py`: the four variants parse; `kind` is required for a string; the
  datatype, shape, `unit`, `limits`, `format` and `bits` refusals on a definition, a member
  and a scalar type, each naming the key it is refused at; `conversion_identity`,
  `physical_range` and `raw_reading` for a string.
- `tests/test_analysis.py`: a declaration and a member naming a string scalar type with the
  wrong kind or shape, with the note at the type; `a2l.format` on such a declaration; the
  three `init-invalid` cases; a string measurement and a string value block resolving with
  the datatype's limits; a string member of a measurement-kind and of a parameter-kind
  instance, and of an array of structures, as leaves.
- `tests/test_a2l.py`: the ASCII record with `NUMBER` and no `FORMAT`, for a value block
  and for a leaf; the byte-array measurement with its annotation, for a measurement and
  for a leaf, and with a raster; no compu method for either.
- `tests/test_generation.py`: the literal, its escapes for `"`, `\` and `?`, the empty
  string, a list init on a string object; and the demo's generated c compiled by
  `tests/test_cmake.py`.
- `tests/test_compare.py`: a byte array becoming a string is a breaking change;
  identical strings compare equal.
- `tests/test_cli.py` and `tests/test_lsp.py`: the list cell and the hover for a string
  init.
- `tests/test_documentation.py`: the regenerated schemas are current; every transcript on
  the touched pages is re-run by `tests/test_transcripts.py`.
- The `DICTIONARY_FORMAT == 7` assertions in `tests/test_constants.py`,
  `tests/test_external.py` and `tests/test_plugins.py` move to 8.

## 12 Documentation

- `SPEC.md`: section 3.3 (the `init` bullet, the `unit`, `limits` and `a2l` rows), 3.4 (the
  fourth kind and its rules), 3.7 (a member and a scalar type under a string), 4 (the
  causes listed under `schema` and `init-invalid`), 5.1 (the initialiser), 5.2 (the two
  records) and 5.3 (format 8).
- `README.md`: the conversions list and the a2l bullets.
- `docs/file_formats/conversions.rst`: a `string` section with the file spelling, the c
  and both a2l records, and "all three kinds" becoming four.
- `docs/file_formats/variable_definition.rst`: the `init` paragraph and the rows for
  `unit`, `limits` and `a2l`.
- `docs/file_formats/types.rst`: the member and scalar type rows that name the conversion.
- `docs/generated_artefacts.rst`: the "what is emitted for what" table and a subsection
  for strings under the a2l heading.
- `docs/data_dictionary.rst`: format 8, and the transcript that shows a newer format being
  refused.
- `docs/consistency_checks.rst`: where the causes of `schema` and `init-invalid` are
  enumerated.
- `CHANGELOG.md`: an `## Unreleased` entry stating the new kind and the new init spelling,
  the dictionary format, and that description files need no migration. The release that
  ships it is a minor one, the file formats having grown.
- `examples/demo/components/controller.ddd.json`: a string measurement `StateName`, output
  of the controller and input of the user interface, and a local string value block
  `SoftwareLabel` with an init, so that every page that lists the demo shows the fourth
  kind and the compile test covers the literal. Every transcript that counts or lists the
  demo's variables is re-run.

## 13 Evidence

What each source settles, so that a later reader knows which claims rest on what:

- **ASAM MCD-2 MC 1.51**, the paid specification, kept as `docs/superpowers/ASAP2.pdf` and
  git-ignored: the `MEASUREMENT` datatype enumeration is numeric; `ASCII (string)` is a
  `CHARACTERISTIC` type; `NUMBER` "specifies the number of values and characters" for a
  value block and a string and "should be replaced by MATRIX_DIM"; `ANNOTATION` is a child
  of `MEASUREMENT` with three optional parts.
- **ASAM's public MCD-2 MC wiki**: the same datatype list with the 64 bit types, and
  ASCII under characteristics only.
- **The a2lfile crate's encoding of 1.7.1**: the measurement block carries neither
  `NUMBER` nor `ENCODING`, both of which sit on `CHARACTERISTIC` and
  `TYPEDEF_CHARACTERISTIC`; `BLOB` is "an array of bytes without any interpretation".
  pya2l's model has the same datatype list.
- **Vector's `ASAP2_Demo_V161.a2l`**: an ASCII object over `FNC_VALUES 1 UBYTE ROW_DIR
  DIRECT`, limits `0 255`, `NUMBER 42`, with the remark that UBYTE is necessary for ASCII;
  a `UBYTE` measurement with `MATRIX_DIM 16 1 1`; `ANNOTATION` in use.
- **Vector's ASAP2 Tool-Set manual, version 20**: a string is its own object type and
  always an ASCII characteristic with `NUMBER`; "for string objects, no conversion rule is
  allowed"; "the ASAP2 format does not support string arrays"; the checker accepts a
  `UBYTE` or `SBYTE` layout, `NUMBER` or a `MATRIX_DIM` whose only non-1 dimension is X.

Not verified, as with every feature so far: opening a generated file in a calibration tool.
One tool's gap is on record: NI's toolkit is reported to reject ASCII characteristics, with
a value block as the workaround; that is that tool's limitation and not the format's.

## 14 Deferred

- **1.7 output.** `MATRIX_DIM` instead of `NUMBER` on an ASCII object, and `ENCODING` for
  a string that is not ASCII, once selectable a2l versions exist.
- **Non-ASCII content**, which needs `ENCODING` and a c literal policy for the execution
  character set.
- **A RAM string as an ASCII characteristic**, Vector's arrangement, as an a2l option for a
  project that wants the text visible in the tool and accepts a polled, dataset-bound
  object for it.
- **`TYPEDEF_CHARACTERISTIC` for scalar string types**, when 1.7's typedefs are emitted.
