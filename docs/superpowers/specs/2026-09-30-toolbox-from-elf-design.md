# Toolbox: from ELF

- **Date:** 2026-09-30
- **Status:** designed, not implemented; worked on the local branch `feature/toolbox-from-elf`,
  which is not pushed
- **Touches:** the command line, a new ELF/DWARF reader, a new `ddd.toolbox` package, a
  fixture image and the fixtures it builds, packaging, the documentation

## 1 What this adds

A project adopting DDD rarely starts from nothing. Its variables already exist, in C, compiled
into an image that a debugger and a calibration tool already read. Describing each of them
again by hand is where adoption stalls, and it is also where a description first disagrees
with the code: a `uint16` typed as a `uint32`, a `volatile` forgotten, an array of eight
described as six.

This design adds a toolbox to the command line, `ddd tool`, and its first tool, `from-elf`. It
reads a linked ELF image and its DWARF debug information, and prints the DDD declarations of
the C variables it is asked for:

```
ddd tool from-elf build/firmware.elf 'Cal_*' Inlet
```

What an image knows, the tool states exactly: the datatype, the shape, `const` and `volatile`,
an enum's enumerators, a structure's members, the initial value and the section. What an image
does not know - a unit, a description, limits, a scaling, whether an array is a curve - it
leaves out, and says once that it did. The result is a starting point that loads: every entry
passes `ddd check --standalone` before it is printed, because DDD's own loader and analysis
judge it (section 5.2).

`ddd tool` is a namespace rather than a command, so that later tools join it without each
claiming a top level name. A tool is something run once, on the way into DDD or out of it,
rather than a step of the build.

## 2 Out of scope

- **An image without DWARF.** A symbol table gives a name, an address and a size. Four bytes
  are a `uint32`, a `sint32`, a `float32` or a structure, and a description that guessed would
  look exactly as confident as one that knew. Such an image is refused (exit `2`), with a
  message naming `-g`.
- **Relocatable objects (`.o`).** Linked images only (`ET_EXEC`, `ET_DYN`), where every address
  and every initial value is final. An object file's addresses are section relative, its common
  symbols have no section, and its debug information needs relocating first. None of that is
  hard, and none of it is needed while firmware images are the input. Refused (exit `2`).
- **Separate debug files** (`.gnu_debuglink`, `.dwo`, `.dwp`): the DWARF has to be in the image.
- **C++.** A C++ construct is an unsupported type (a class, a reference) or not a candidate at
  all (a variable in a namespace). Nothing is done to read them, and nothing is tested.
- **Checking the layout DDD would generate against the image's.** DDD states member order,
  datatypes and widths, never offsets (`SPEC.md` 3.7). The tool describes what DDD can state,
  and warns where the image shows something DDD cannot (section 4.5), without predicting the
  compiler.
- **Addresses.** Reading the address map straight out of the image (`SPEC.md` section 6) stays
  planned. The reader is built so that it can serve that later (section 5.1); this design does
  not.
- **Editing a project.** The tool prints; it never writes into a description file. Where the
  entries go is the user's decision, and merging them into an existing file is another tool.
- Everything section 4.8 lists as never inferred.

## 3 The command

### 3.1 Arguments

```
ddd tool from-elf IMAGE SYMBOL [SYMBOL ...] [--component NAME]
                  [--scope {output,local,input}] [-o FILE] [--force] [--format {text,json}]
```

`SYMBOL` is `[UNIT:]PATTERN`.

- `PATTERN` is a C identifier, matched exactly, or a glob (`*`, `?`, `[...]`), matched case
  sensitively (`fnmatch.fnmatchcase`) against the names of the candidates.
- `UNIT` narrows the match to one compilation unit, for a `static` that several units define.
  It matches the unit's `DW_AT_name` exactly or as its trailing path components: `cal.c`
  matches `src/app/cal.c` and not `src/app/xcal.c`. The argument is split at its last colon,
  which neither an identifier nor a glob contains, so a Windows path keeps its drive letter.

A candidate is a variable with a static address in the image: a `DW_TAG_variable` directly
under a compilation unit, whose location is an address, either on the entry itself or on a
definition completing it through `DW_AT_specification`. A function's `static` locals are not
candidates, since C gives them no name outside the function.

Every argument must match something:

- An argument that matches no candidate, exact name or glob, is `elf-symbol-missing`. When the
  name is in the ELF symbol table, the message adds that the unit defining it carries no debug
  information.
- A name defined by several units is `elf-symbol-ambiguous`, listing the units, whether an
  exact name or a glob reached it. `UNIT:` resolves it.
- A name that is only declared, whose storage the optimiser removed (a `DW_AT_const_value` in
  place of a location), or that is thread-local is `elf-no-storage`.

Entries come out in the order of the arguments, a glob's matches sorted by name and then by
unit. A variable matched by two arguments is printed once, where it was first matched.

### 3.2 Output

The default output is a JSON array of interface entries, the form a component's `interface`
list holds:

```json
[
  {
    "scope": "output",
    "definition": {
      "name": "Cal_Gain",
      "kind": "parameter",
      "datatype": "uint16",
      "conversion": { "kind": "identity" },
      "init": 300,
      "volatile": false
    }
  }
]
```

- `--component NAME` prints a whole component file instead:
  `{"component": {"name": NAME, "types": [...], "interface": [...]}}`, with `types` present
  when a structure needs it. `NAME` is a C identifier of at most 128 characters
  (`C_IDENTIFIER_PATTERN`, `IDENTIFIER_MAX_LENGTH`), or the command line is refused (exit `2`).
- The array form has nowhere to put a `types` entry, so a structured object printed in it names
  a type the array does not carry. `elf-types-omitted` says so, once per run, and names
  `--component`.
- `--scope` sets the scope of every entry. `output`, the default, and `local` are the producer
  scopes: the entry states the storage keys `init` and `section`. `input` leaves them out,
  because a consumer must not state them (`consumer-storage`, `SPEC.md` 3.3.1.2). The default is
  `output` because an image shows what its firmware owns.
- The output goes to standard output, or to `-o FILE` through the writer `ddd dump -o` uses:
  the same bytes on every platform, and a file whose content would not change is left
  untouched. An `-o` naming the image is refused (exit `2`), since nothing DDD writes is ever a
  file it read.

### 3.3 Diagnostics and exit codes

Diagnostics go to standard error, in the text or JSON format of every other command
(`--format`), so that standard output carries the JSON and nothing else. A finding about a
variable is located at its declaration in the C source when DWARF records one
(`DW_AT_decl_file`, `DW_AT_decl_line`), with the path as the compiler recorded it, and at the
image otherwise.

The tool's own findings have identifiers of their own, prefixed `elf-`. They are not checks of
the project catalogue: `ddd checks` does not list them and `-W` does not take them, because
they judge an image, not a description.

| identifier | severity | when |
| --- | --- | --- |
| `elf-symbol-missing` | error | an argument matches no candidate (section 3.1) |
| `elf-symbol-ambiguous` | error | a name is defined by several units |
| `elf-no-storage` | error | declared only, optimised to a constant, or thread-local |
| `elf-type-unsupported` | error | a type DDD cannot state, at the path where it occurs (section 4) |
| `elf-type-conflict` | error | two different structures or enums under one name, or a synthesised name that is taken |
| `elf-init-unsupported` | error | an initial value DDD cannot state: NaN, an infinity, a boolean byte other than 0 and 1 |
| `elf-init-dropped` | warning | a structured object whose bytes in the image are not all zero (section 4.6) |
| `elf-bitfield-gap` | warning | bits skipped where the next bitfield would have fitted (section 4.5) |
| `elf-alignment` | warning | an alignment the source states explicitly (section 4.5) |
| `elf-qualifier-dropped` | warning | `const` or `volatile` on a structure member (section 4.4) |
| `elf-section` | warning | once per section name the output states (section 4.7) |
| `elf-name-synthesized` | warning | an anonymous structure or enum given a name (section 4.4) |
| `elf-types-omitted` | warning | the array output holds a structured object (section 3.2) |
| `elf-boolean-bitfield` | info | a `_Bool` bitfield described as a `uint8` one (section 4.4) |
| `elf-not-inferred` | info | once per run that prints an entry: what the output never states (section 4.8) |

DDD's own findings on the output (section 5.2) are reported with them, under DDD's own
identifiers such as `init-invalid` or `schema`, and located at the declaration of the variable
they concern.

A variable with an error is not printed. The exit code is the one every command has:

- `0`: every argument was described. Warnings and infos do not change the code.
- `1`: at least one error. Nothing is written, neither to standard output nor to `-o`, unless
  `--force` asks for the entries that were described. The code stays `1` either way, so that a
  script reads the verdict from the code rather than from the presence of the output.
- `2`: the command line or the image is unusable. That is a malformed argument; an image that
  cannot be read, is not ELF, carries no DWARF, or is relocatable; an `-o` naming the image; or
  `pyelftools` not installed, in which case the message names `pip install ddd-tool[elf]`.

## 4 From C to DDD

### 4.1 Kind

The variable's `const` decides between a measurement and a calibration object, and its shape
decides between the calibration kinds. The qualifier counts wherever it sits on the way from
the variable to its core type: on the variable's type, under a typedef, or on an array's
element type, since producers differ in where they put it.

| C variable | DDD |
| --- | --- |
| not `const`: a base type, an enum or a structure, scalar or array | `measurement`, with `dimensions` for an array |
| `const` scalar of a base type or an enum | `parameter` |
| `const` array of a base type or an enum | `value_block` |
| `const` structure | `parameter`, naming the structure as `typename` |
| `const` array of structures | `elf-type-unsupported`: a `parameter` has no `dimensions` (`SPEC.md` 3.3), and a `value_block` holds no structure (3.7) |

`const volatile` is a calibration kind with `volatile: true`. A curve, a map or an axis is
never inferred. Nothing in an image tells a table indexed by an axis from any other array, so a
`const` array is a value block, and `elf-not-inferred` says so when the run printed one.

### 4.2 Datatype and volatility

| DWARF base type encoding | byte size | datatype |
| --- | --- | --- |
| `DW_ATE_boolean` | 1 | `boolean` |
| `DW_ATE_unsigned`, `DW_ATE_unsigned_char` | 1, 2, 4, 8 | `uint8`, `uint16`, `uint32`, `uint64` |
| `DW_ATE_signed`, `DW_ATE_signed_char` | 1, 2, 4, 8 | `sint8`, `sint16`, `sint32`, `sint64` |
| `DW_ATE_float` | 4, 8 | `float32`, `float64` |

Any other pairing is `elf-type-unsupported`: another size (a `long double`, a 128 bit integer),
complex, fixed point, decimal, a character encoding such as `DW_ATE_UTF`. So are a pointer, a
union, a class, a reference, a function type and an `_Atomic` qualifier.

Every size and every signedness is read from DWARF, never from the C spelling. `long`, plain
`char` and an enum (`-fshort-enums`) differ from one target to the next, and the output
follows the target that built the image.

A typedef is transparent for the datatype: `uint16_t` and a project's `Temperature_t` both
become `uint16`. It does not become a scalar type, which would fix a unit and a conversion that
the image does not know (`SPEC.md` 3.7).

`volatile` is the qualifier, found the way `const` is (section 4.1).

### 4.3 Conversion

The conversion is `{"kind": "identity"}`, except for an enum, which becomes an `enum`
conversion:

- `name` is the typedef closest to the enum, else the tag, else a synthesised name (section
  4.4).
- `enumerators` lists them in declaration order, in the object spelling `{"NAME": value}`.
- The datatype is the enum's `DW_AT_byte_size`. It is signed when the enum's underlying type
  (`DW_AT_type`) is signed, or, where DWARF states no underlying type, when an enumerator is
  negative. Enumerator values are read with that signedness, whatever DWARF form carries them.

An enum always sits inline, on the definition or on the member, never as a `types` entry. The
array output then carries every enum it needs. Two enums under one name with different
enumerators are `elf-type-conflict`.

### 4.4 Structures

A structure becomes a `types` entry, `{"type": "struct", "name": ..., "members": [...]}`, with
its members in declaration order:

| member in C | DDD member |
| --- | --- |
| a base type or an enum | `value`, with `datatype` and `conversion` |
| an array of those | the same, with `dimensions` |
| a structure, or an array of them | `value`, with `typename` (and `dimensions`); the nested structure is an entry of its own |
| a bitfield of an integer or enum type | `bits`, with the declared type's `datatype`, its `conversion`, and the width as `bits` |
| a `_Bool` bitfield | `bits` with `uint8`, since DDD refuses a boolean bitfield (`SPEC.md` 3.3); `elf-boolean-bitfield` says so |

`const` or `volatile` on a member is dropped with `elf-qualifier-dropped`: DDD qualifies whole
objects, and a member carries neither (`SPEC.md` 3.7).

A member that is a pointer, a union, an anonymous structure or union, a flexible array or a
zero length array, or of any other unsupported type, is `elf-type-unsupported`, naming the path
to it (`Inlet_t.status.raw`). Every variable reaching the structure is then refused.

**Naming.** The name is the typedef closest to the structure (`Inlet_t`), else the tag
(`struct Inlet_s` gives `Inlet_s`), else a synthesised one. Closest to the structure rather
than to the variable, so that a variable declared through a second alias still names the
structure's one entry; a typedef naming an array of the structure names the array, not the
structure, and is passed over. A type a variable reaches directly, through arrays if
any, is named `<Variable>_t`; a type a member reaches is named `<Structure>_<member>_t`.
`elf-name-synthesized` states the name given. A synthesised name must be free: one that equals
another type's name is `elf-type-conflict`. Enums are named by the same rule.

**One entry per structure.** Every variable using a structure shares its one entry. DWARF gives
every unit that includes a header its own copy of the header's structures, and those copies are
one entry when they agree member for member: names, member kinds, datatypes, conversions,
shapes and widths. Copies that disagree are `elf-type-conflict`, naming both units, and every
variable reaching either copy is refused, so that the result does not depend on which unit came
first. A structure is listed after the structures it names, the order C would declare them in.

A structured variable is a `measurement` or a `parameter` (section 4.1) naming its structure as
`typename`, and it states no `init` (section 4.6).

### 4.5 Layout

DDD never states offsets (`SPEC.md` 3.7), and neither does the tool. It states member order,
datatypes and widths, and the compiler that builds DDD's generated structure lays it out.
Nothing in the A2L depends on that layout: a `bits` member reaches no A2L, and addresses come
from the build. What can differ is DDD's generated structure against the source's, where the
source asked for a layout that its members do not imply.

DWARF records none of those requests directly. Gcc 15 leaves unnamed and zero width bitfields
out of DWARF entirely, and states no packing (section 10). So the tool reads the two traces it
reliably can:

- `elf-bitfield-gap`: two consecutive bitfields do not abut, although the second would have fit
  at the end of the first without crossing a boundary of its declared type's size. That is the
  trace an unnamed or zero width bitfield leaves. "Would have fit" is the rule of the System V
  ABIs and of the AAPCS, which gcc and clang apply on every row of the matrix (section 6.3), and
  which the fixture tests confirm row by row. A gap the rule itself explains is padding the
  generated structure reproduces, and is not reported. Bit offsets come from
  `DW_AT_data_bit_offset`, or from DWARF 2 and 3's `DW_AT_bit_offset`, converted with the byte
  order (section 5.1).
- `elf-alignment`: `DW_AT_alignment` on a structure or a member, from `_Alignas` or an
  `aligned` attribute.

Packing (`#pragma pack`, `packed`) is not detected. Whether an offset is packed or is just the
target's own alignment depends on an ABI the tool does not model: i386 places a `double` at
offset 4 without any packing, and AVR aligns everything to one byte. The user guide says so.

### 4.6 Initial values

- **A variable in a section without contents** (`SHT_NOBITS`, such as `.bss`) states no
  `init`, whose default, `null`, is DDD's implicit zero initialisation. That is faithful: its
  source had no initialiser, or a zero one, and C zeroes static storage either way. A `.noinit` section, also without contents but not zeroed at startup,
  differs by placement only, and `section` carries placement (section 4.7).
- **Any other variable** has its bytes read at its address in its section's contents, and
  decoded in the image's byte order according to its datatype:
  - Integers and enums are written as integers.
  - A `boolean` is written as `true` or `false`. Any byte other than 0 or 1 is
    `elf-init-unsupported`.
  - A `float32` or `float64` is written as the shortest decimal that reads back to the same
    bits: `0.1f` is `0.1`, not `0.10000000149011612`. NaN and the infinities are
    `elf-init-unsupported`, because JSON has neither.
  - An array is a nested list in C order. An array whose elements are all equal is written as
    that one value, the fill `SPEC.md` 3.3 gives a scalar on an array-shaped object, so a zeroed
    array in `.data` is `0` rather than a list of zeros.
- **A structured variable** states no `init`, as `SPEC.md` 3.7 requires. If its bytes are in a
  section without contents, or are all zero, nothing is lost. Otherwise `elf-init-dropped`
  says so: DDD zero-initialises the object, and its values reach it from the running software
  or from the calibration tool.
- **Under `--scope input`**, no variable states `init` (section 3.2). Initial values are then
  not read at all, so neither `elf-init-unsupported` nor `elf-init-dropped` is reported.

### 4.7 Section

The image records the output section, the one the linker script produced. DDD's `section` is
the name the generated C writes into its attribute or pragma, which the linker script then
maps (`SPEC.md` 3.5). The two coincide when the linker script keeps the name, which is the
common arrangement for a calibration section (`.calib : { *(.calib) }`), and differ otherwise.

- A variable in a toolchain default section states no `section`, and is placed by the defaults
  as it was. The default sections are `.data`, `.bss`, `.rodata`, `.sdata`, `.sbss`, `.sdata2`,
  `.sbss2`, `.srodata`, `.data1` and `.rodata1`.
- A variable in any other section states that section's name. `elf-section` says, once per
  name, that it is the output section's name, and that the project must declare it in a
  sections file, or `ddd check` on the project reports `unknown-section`. `--standalone`
  holds that check back, which is why the output passes its own check (section 5.2).
- Under `--scope input`, no variable states `section`.

A name DDD cannot spell as a section - only letters, digits, `.`, `_` and `$` - is refused by
DDD's own `schema` finding (section 5.2).

### 4.8 What is never inferred

- **`unit` and `description`:** nothing in an image states them.
- **`limits`:** left out, so that DDD derives them from the datatype and the conversion.
- **A scaling:** the conversion is the identity, apart from enums. An image stores raw counts;
  the factor lives in the code that reads them.
- **`string`:** a `char` array stays bytes. That it holds text is a reading of the bytes, and
  DDD never infers a string either (`SPEC.md` 3.4).
- **Curves, maps and axes** (section 4.1), **rasters**, **`id`** (written by
  `ddd id --assign`), **the `a2l` block** and **`extensions`**.

`elf-not-inferred`, once per run, lists them. When the run printed a value block, it adds that
a curve, a map or an axis is declared differently.

## 5 Structure of the code

```
cli.py ──► ddd/elf.py (reader) ──► C model ──► ddd/toolbox/from_elf.py (translator) ──► JSON + diagnostics
                                                             │
                                          checked by DDD's loader and analysis (--standalone)
```

### 5.1 The reader: `src/ddd/elf.py`

It knows nothing of DDD: it imports `elftools` and the standard library and nothing else, so
that the planned address-map reading can use it without the toolbox.

```python
def open_image(path: Path) -> Image: ...  # raises ElfReadError, with its reason

@dataclass(frozen=True, slots=True)
class Image:
    path: Path
    byte_order: Literal["little", "big"]
    variables: tuple[Variable, ...]  # candidates, and names without storage
    sections: tuple[Section, ...]  # the allocated ones, thread-local ones left out
    symbols: frozenset[str]  # the symbol table's objects, for the missing-symbol hint
    contents: bytes
    def section_of(self, address: int) -> Section | None: ...
    def read(self, address: int, size: int) -> bytes | None: ...  # None without contents
```

`Image` is plain data that `open_image` fills, so a test builds one by hand around a
hand-built C model.

- **A `Variable`** has its name, its unit, where it is declared (file and line, when DWARF
  says), its storage (an address, or why it has none: declared only, a constant,
  thread-local) and its type.
- **The C model** is made of frozen dataclasses: `Base(encoding, size, name)`,
  `Enum(name, tag, size, signed, enumerators)`, `Struct(name, tag, size, members, alignment)`,
  `Member(name, type, bit_offset, bit_size, alignment)`, `Array(element, dimensions)`,
  `Qualified(inner, const, volatile)`, `Typedef(name, inner)` and `Unsupported(what)`.
- **A type the tool cannot describe is data, not an exception.** An `Unsupported` node sits at
  the exact place where it occurs, so the translator can name the path and go on with the other
  variables. A pointer is an `Unsupported` leaf whose pointee is never followed, so a structure
  pointing at itself stays finite. Types are memoised by DIE offset, so a type reached twice is
  built once.
- **Every DWARF variation stops here.** The translator never sees one. These are:
  - a definition completing a declaration (`DW_AT_specification`)
  - a qualifier on an array or on its element
  - nested array types or several subranges
  - `DW_AT_count` or `DW_AT_upper_bound`
  - `DW_AT_data_bit_offset` or the older `DW_AT_bit_offset`, whose counting depends on the byte
    order
  - a member offset given as a constant or as a location expression
  - `DW_OP_addr` or `DW_OP_addrx` through `.debug_addr`
  - thread-local locations
  - enumerator values in any form
  - strings in `.debug_str` or through `.debug_str_offsets`
  - compressed debug sections
- **It reads DIEs through two narrow protocols.** `Entry` (tag, attributes, children, offset)
  is satisfied by pyelftools' `DIE`. `Unit` (its name, its top entry, expression parsing,
  `.debug_addr` and the file table) is satisfied by a thin adapter over a pyelftools
  compilation unit, whose file-table arithmetic is a pure function of plain data. A test double
  can then reach the branches no C compiler produces, such as a non-zero `DW_AT_lower_bound` or
  a location list (section 7).

### 5.2 The translator: `src/ddd/toolbox/from_elf.py`

The package is `ddd.toolbox`, not `ddd.tools`, so that it is not confused with the repository's
`tools/` directory.

```python
def describe(
    image: Image, symbols: Sequence[str], *, scope: Scope, component: str | None
) -> Description: ...  # entries, types, diagnostics
```

It selects (section 3.1), maps (sections 4.1 to 4.4), names and merges the types (section 4.4),
decodes the initial values (section 4.6), and has DDD check the result. It builds plain
dicts in the key order the examples use: `name`, `kind`, `datatype` or `typename`,
`dimensions`, `conversion`, `init`, `section`, `volatile`. Members follow the order of
`SPEC.md` 3.7's example: `name`, `member`, `datatype` or `typename`, `conversion`,
`dimensions`, `bits`.

**DDD checks what the translator built.** The translator writes the component, with its
`types`, into a temporary directory, whichever output was asked for, and runs DDD's loader and
analysis on it under the standalone policy, exactly what `ddd check --standalone` runs, with
one addition: `missing-id=ignore`. Every producing entry would otherwise earn DDD's
`missing-id`, since the tool writes no `id` on purpose and `elf-not-inferred` already says so.
For the array output, the component is named `FromElf`, a name that never reaches the output.
Every finding points into that file:

- A finding under `component.interface[<i>]` concerns the i-th variable.
- A finding under `component.types[<j>]` concerns that type and every variable reaching it.

These are DDD's own pointer spellings, dotted, as `ddd check --format json` prints them.

The findings are reported, located at the variables' declarations. Variables with an error are
removed, and the check runs again on what remains, until it reports no error. Running again is
not optional: a load error, such as `schema`, stops DDD before its analysis, so an analysis
error such as `init-invalid` only appears once the load errors are gone (measured on
2026-09-30). The errors of every pass are reported; the warnings and infos of the last pass
only, so that nothing is reported twice. A finding that points at neither is a fault of the
tool: it is reported as it is, and the run exits `1`.

DDD's rules are therefore stated once, in DDD. The translator neither repeats nor predicts
them. The element and leaf caps, the nesting depth, an enumerator wider than a C `int` and a
name longer than 128 characters are all DDD's findings, reported under DDD's identifiers.

### 5.3 The command line

`cli.py` adds the `tool` subparser group, whose one tool is `from-elf`; `ddd tool` without a
tool is a usage error listing them. The handler imports `ddd.elf` inside itself, so that
`ddd --help` and every other command work without `pyelftools`. A `ModuleNotFoundError` for
`elftools` becomes the exit `2` of section 3.3. The handler also turns `ElfReadError` into exit
`2`, prints the diagnostics with the existing machinery, and writes the output under the rules
of section 3.3.

### 5.4 The dependency

- A new `requirements-elf.txt` holds `pyelftools>=X,<1`. `X` is the oldest release the whole
  fixture matrix passes on, found in the first increment by running the reader tests against
  releases down from 0.33, the newest on 2026-09-30.
- `[tool.hatch.metadata.hooks.requirements_txt.optional-dependencies]` gains
  `elf = ["requirements-elf.txt"]`, and `dev` becomes
  `["requirements-dev.txt", "requirements-elf.txt"]`. Every environment that runs the suite
  therefore has the reader's dependency with one version bound: CI's `pip install -e ".[dev]"`,
  the `ddd:dev` image's `.[dev,docs]`, and a local venv.
- The sdist's include list gains `/requirements-elf.txt`.
- pyelftools 0.33 ships `py.typed`, so mypy reads its annotations and needs no stub override.
  Where strict mode refuses a call its partial annotations leave untyped, the relaxation is an
  override on `ddd.elf` alone, the one module that imports it.
- `requirements.txt` does not change. The README's claim of two runtime dependencies stays
  true, and so does `test_the_runtime_requirements_are_what_the_package_imports`.

## 6 Fixtures

Docker builds the fixture images, and they are committed. The tests read the committed files
and need neither Docker nor a compiler, so the suite runs the same on a machine without Docker,
on one with it, and in CI. Docker is needed only to rebuild the fixtures after their source
changes.

### 6.1 The source

`tests/fixtures/elf/src/` holds four units and a shared header:

- `main.c` holds a variable for every case of section 4, each named for its case. It also holds
  the entry symbol and the probes of section 6.4.
- `unit_a.c` and `unit_b.c` hold a `static` of the same name, a structure from `shared.h` that
  they share, and a structure whose tag is the same in both and whose members are not.
- `nodebug.c` is compiled without `-g`, so that its variable is in the symbol table and in no
  DWARF: the case of `elf-symbol-missing`'s hint.

Values are chosen so that a byte order mistake cannot pass: `0x1234`, `0x12345678`,
`0x0102030405060708`, `-2` and `1.5f`. `-O2` keeps an unused `static` only when it is marked
`__attribute__((used))`; one `static const` is deliberately left unmarked and folded into the
code, so that gcc replaces its storage by a `DW_AT_const_value` and `elf-no-storage` has a real
case (measured with gcc 15 on 2026-09-30; built on the gcc rows only, since clang may drop the
entry). A case that a toolchain cannot build, such as thread-local storage on a bare-metal
target, is compiled out of that row by a macro, and the manifest says which cases each row
has.

### 6.2 The image and the build

- **`docker/elf-fixtures/Dockerfile`** is a Debian image pinned by digest, holding the cross
  gcc packages, clang, lld and each target's binutils. It lives in `docker/`, which
  `pyproject.toml` describes as the scripts the container runs.
- **`docker/elf-fixtures/build_fixtures.py`** compiles every row and writes the files below.
- **The compose service `elf-fixtures`** has an image tag of its own. Like `gui-screenshots`,
  it hands what it wrote back to the checkout's owner.
- **Flags:** `-O2 -g<version> -ffreestanding -nostdlib`, statically linked where the target
  links that way, with `-ffile-prefix-map` so that DWARF names `main.c` rather than
  `/work/...`.
- **It writes** into `tests/fixtures/elf/`:
  - `<row>.elf` for every row
  - `stripped.elf`, one row's image without its DWARF
  - `main.o`, a relocatable object with DWARF, so that `.o` is refused for being relocatable
    rather than for lacking DWARF
  - `manifest.json`
- **And `examples/firmware/firmware.elf`**, a copy of the `armv7m` row. The suite re-runs every
  `$ ddd ...` transcript of the documentation in a scratch copy of `examples/`
  (`tests/test_transcripts.py`), and a page showing commands must run at least one of them, so
  the user guide's examples need an image there. A test holds the copy byte for byte to the
  row.

```bash
docker compose run --rm elf-fixtures
```

### 6.3 The matrix

| row | compiler | byte order | width | DWARF | covers as well |
| --- | --- | --- | --- | --- | --- |
| `x86_64` | gcc, `-static-pie` | little | 64 | 5 | the host's default; an `ET_DYN` image |
| `i686` | gcc | little | 32 | 4 | 8 byte types aligned to 4 inside a structure |
| `armv7m` | arm-none-eabi-gcc | little | 32 | 4 | short enums, unsigned `char`: the typical microcontroller |
| `armv7m-dwarf2` | arm-none-eabi-gcc, `-gstrict-dwarf` | little | 32 | 2 | old toolchains: `DW_AT_bit_offset`, offsets as expressions, enums without an underlying type |
| `armeb` | arm-none-eabi-gcc `-mbig-endian`, Cortex-R | big | 32 | 4 | |
| `aarch64` | gcc | little | 64 | 5 | |
| `powerpc` | gcc | big | 32 | 3 | the MPC5xxx family of automotive ECUs; big endian `DW_AT_bit_offset` |
| `s390x` | gcc, `-gz` | big | 64 | 5 | compressed debug sections |
| `riscv32` | clang, lld | little | 32 | 5 | a second DWARF producer; `DW_OP_addrx` |
| `aarch64_be` | clang, lld | big | 64 | 4 | clang in big endian |

Debian trixie packages every row's compiler (checked on 2026-09-30: cross gcc 14.2 for i686,
arm-none-eabi, aarch64, powerpc, s390x and x86-64; clang, lld and llvm 19), so no row needs a
substitute. The manifest records which compiler built each.

### 6.4 The manifest and the oracle

The oracle is the compiler and its binutils, never the reader under test.
`tests/fixtures/elf/manifest.json` records:

- **For each row:** the compiler and its version, the target, the flags and the cases built.
- **The target's traits, as the toolchain itself states them:**
  - byte order, `char` signedness, `sizeof(long)` and `sizeof(long double)`, from the
    predefined macros (`__BYTE_ORDER__`, `__CHAR_UNSIGNED__`, `__SIZEOF_LONG__`,
    `__SIZEOF_LONG_DOUBLE__`)
  - enum size and the alignment of a `uint64_t` inside a structure, from the sizes GNU
    `readelf -s` reports for probe variables
  - whether the DWARF carries `DW_AT_alignment` at all, from GNU `readelf --debug-dump=info`
- **For each fixture variable:** its section, whether that section has contents, and its size,
  from GNU `readelf -s` and `readelf -S`.
- **SHA-256 hashes** of the fixture source, the Dockerfile and the build script, each hashed
  with its line endings normalised, so that a Windows checkout converting them does not read as
  drift.

GNU `readelf` is the one tool for every row: it reads the headers, symbols and DWARF of any
target's ELF, where `objdump` and `nm` are built for one target.

Target-independent expectations come from the values the source states: `Cal_Gain` is a
`uint16` parameter initialised to `300` on every row. Target-dependent expectations come from
the traits: `long` is `sint32` or `sint64`, and plain `char` is `uint8` or `sint8`.

## 7 Testing

Tests first, in the files that own each concern:

- **`tests/test_elf.py` tests the reader:**
  - On every row of the manifest: the candidates, their types, sections and sizes against the
    manifest, `init` bytes in both byte orders, thread-local and removed storage, the DWARF 2
    to 5 variants and compressed sections.
  - The refusals: a file that is not ELF, a truncated one, `stripped.elf` and `main.o`.
  - The test double of section 5.1, for the branches no compiler produces.
  - **The drift guard:** the hashes in the manifest must match the files. If they do not, the
    test fails naming `docker compose run --rm elf-fixtures`.
- **`tests/test_toolbox_from_elf.py` tests the translator** on hand-built C models:
  - every rule of section 4, including what no fixture compiler produces cleanly, such as a
    128 bit type, a NaN initial value or a synthesised name that is taken
  - selection, ordering and deduplication
  - the shortest float spelling
  - the check by DDD: a model DDD refuses, such as an enumerator wider than an `int`, is
    reported under DDD's identifier and left out, while the others are printed
- **`tests/test_cli.py` tests the command** end to end on the fixtures:
  - both outputs, and `--scope`
  - `--component` output passing `ddd check --standalone` without an error
  - exit codes `0`, `1` and `2`, and `--force`
  - `-o`, including an `-o` naming the image
  - `--format json`
  - every refusal and warning, located at `main.c:<line>`
  - the missing dependency: `sys.modules["elftools"] = None`, and exit `2` naming the extra
- **`tests/test_documentation.py`:** its command lists, its `--format json` list and its
  requirements checks take the new command and the new requirements file as they require.

Nothing skips when `pyelftools` is missing: a test that skips reports success without having
run, which `requirements-dev.txt` already refuses for its own tools. The 100% branch coverage
gate covers `ddd.elf` and `ddd.toolbox` like the rest of the package. The matrix, the test
double and the hand-built models together reach every branch, and none is excluded.

## 8 Documentation

- **`SPEC.md`:**
  - The list of commands in section 7 names `ddd tool from-elf`.
  - A new section 7.3, *Toolbox*, holds sections 3 and 4 of this design as normative rules.
  - Section 6's "Reading the linker output directly (ELF/DWARF) … is *planned*" stays, since
    address maps still do not read ELF, and gains a pointer to the reader of section 7.3.
- **`README.md`:**
  - the command, in the list the documentation tests hold it to
  - the `elf` extra beside the two runtime dependencies
- **`docs/toolbox.rst`**, in the index, is the user guide:
  - installing the extra, and the `-g` requirement
  - one worked example of each output, as transcripts over `examples/firmware/firmware.elf`
    that the suite re-runs
  - the table of what is and is not inferred
  - the layout caveat of section 4.5
  - that a structure's `types` entry belongs once in a project: in a shared types file when two
    components need it
- **`docs/command_line_interface.rst`:** the command's row in the command table, and its place
  among the commands taking `--format json`.
- **`docs/developer_documentation.rst`:** how to rebuild the fixtures, and why they are
  committed.
- **`CHANGELOG.md`:** an `## Unreleased` entry, a minor release's worth, the command line having
  grown.

## 9 Delivery

The work is local, beside a development in progress on `feature/gui-large-projects`, which it
must not disturb:

- It lives in a git worktree beside the main checkout,
  `/home/sauci/Documents/Github/ddd-toolbox-from-elf`, on the local branch
  `feature/toolbox-from-elf`, made from `master` at `06d8737`. It is outside the checkout, so
  that `ruff check .` there, or the `lint` service that bind mounts it, never reads this work.
- **Nothing is pushed.** There is no remote branch and no pull request. Commits stay local, and
  what becomes of the branch is the maintainer's decision.
- The worktree has its own `.venv`. The main checkout's `.venv` is never touched.
- Docker runs from the worktree under its own compose project name (`-p ddd-toolbox`), and the
  fixture image has its own tag. The `ddd:dev` image, which the main checkout's services run,
  is never built or retagged from here.
- The plan is `docs/superpowers/plans/2026-09-30-toolbox-from-elf.md`, with its progress log.

## 10 Evidence

What each source settles, so that a later reader knows which claims rest on what:

- **gcc 15.2.0 (Ubuntu 15.2.0-16ubuntu1), x86_64, its default DWARF 5, `gcc -g -c`**, checked
  with `readelf --debug-dump=info` on 2026-09-30:
  - `struct { uint8_t a:2; uint8_t :3; uint8_t b:2; uint8_t :0; uint8_t c:1; }` has three
    members, `a`, `b` and `c`, at `DW_AT_data_bit_offset` 0, 5 and 8. The unnamed and zero
    width fields have no entry, and appear only as gaps.
  - A `packed` structure of a `uint8_t` and a `uint32_t` has `DW_AT_byte_size` 5 and its second
    member at offset 1, with no attribute stating the packing.
  - `_Alignas(16)` on a member gives `DW_AT_alignment` 16, on both the member and the
    structure.
- **`SPEC.md`:**
  - A `bits` member reaches no A2L (5.2).
  - Offsets are not stated and will not be (3.7).
  - A structured object carries no `init`, and is a `measurement` or a `parameter` (3.7).
  - A `parameter` has no `dimensions` (3.3).
  - `section` names a declared section, and `unknown-section` is reported otherwise (3.5).
  - A consumer states no storage key (3.3.1.2).
- **`ddd check --standalone`** holds back the checks that need the rest of a project,
  `unknown-section`, `unknown-type`, `missing-producer` and `unused-output` among them
  (`needs_every_component` in the registry).
- **PyPI, 2026-09-30:** pyelftools 0.33 is the newest release, and its installed package
  carries `py.typed` and no `.pyi` files.
- **gcc 15.2.0 at `-O2`, DWARF 5, 4 and 2, linked `-nostdlib`, read through pyelftools 0.33**
  on 2026-09-30:
  - An `extern` declaration completed by a definition gives two entries: the declaration
    carries the name, the type and `DW_AT_declaration`; the definition carries
    `DW_AT_specification`, its own `DW_AT_decl_line` and the location.
  - `const uint8_t a[4]` qualifies both the array and its element.
  - An enum carries `DW_AT_type` and `DW_AT_encoding` at DWARF 5 and at non-strict DWARF 2; a
    negative enumerator is `DW_FORM_sdata`, a positive one `DW_FORM_data1`.
  - DWARF 5 states bitfields with `DW_AT_data_bit_offset`. DWARF 4 and 2 state
    `DW_AT_byte_size`, `DW_AT_bit_offset` counted from the storage unit's most significant
    end, and `DW_AT_data_member_location`, a constant at 4 and `DW_OP_plus_uconst` at 2.
    `8 * location + 8 * byte_size - bit_offset - bit_size` gives DWARF 5's offsets exactly on
    little endian.
  - A thread-local variable's location ends in `DW_OP_form_tls_address` at DWARF 5 and in
    `DW_OP_GNU_push_tls_address` at 4 and 2.
  - An unused `static const` has `DW_AT_const_value` and no location.
  - The DWARF 5 file table counts from 0, with directory 0 the compilation directory; 4 and 2
    count from 1, with directory 0 the unit's `DW_AT_comp_dir`.
  - `-gz=zlib` writes `SHF_COMPRESSED` sections still named `.debug_*`, which pyelftools
    decompresses transparently.
  - `-fPIE -static-pie -nostdlib` gives an `ET_DYN` image pyelftools reads like the others.
- **pyelftools 0.33 on damaged input**: an empty, a three byte and a garbage file raise
  `ELFError`; a truncated one raises `ELFParseError`, an `ELFError`, at its first section read.
  `DWARFInfo.get_addr(cu, index)` resolves `DW_OP_addrx`, and `strx` forms arrive translated.
- **Debian trixie, 2026-09-30:** `debian:trixie-slim` at
  `sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a` packages every
  row's compiler (section 6.3).
- **`ddd check --standalone --format json`** on a component with one bad entry of each kind,
  on 2026-09-30: pointers are dotted (`component.interface[4].definition`,
  `component.types[0].members[0].conversion`); a `schema` error stops the run before the
  analysis; every producing entry without an `id` earns `missing-id` as an info.
- **Baseline:** the worktree at `06d8737` passes the suite, 4714 tests at 100% coverage.

Not yet verified, and settled by the fixture build (the plan's first task):
- clang's DWARF for the same bitfield and alignment cases
- that every row links `-nostdlib` with its thread-local case, and gcc 14 folds the
  `static const` the way gcc 15 does

## 11 Deferred

- **Addresses from the image:** the address map of `SPEC.md` section 6, read by the same
  reader, and the cross-check of the linked symbols against the declarations that the section
  plans.
- **Relocatable objects and separate debug files.**
- **A sections file** for the sections the output names, rather than a warning per name.
- **Checking the layout:** compiling DDD's generated structure with the image's own toolchain
  and comparing offsets, which is the one reliable way to catch packing.
- **Merging into an existing component**, rather than printing.
- **More tools:** the toolbox is where a tool on the way into DDD, or out of it, belongs.
