# `ddd generate a2l --image`: addresses straight out of the linked image

Status: design agreed with the maintainer on 2026-10-02, section by section. Not yet planned.

## 1. Goal

Today the a2l's addresses come from a JSON map, `{"Symbol": "0x20000100"}`, that the project writes
itself after the link: an `nm` script the build page offers as an example to adapt, which also has to
compute every structure member's address by hand (`Inlet.latest`, `Inlet[2].raw`), since `nm` prints
none. In cmake that is a two-run flow: the first build links with every address 0, a post-build
step writes the map, and the next build regenerates the a2l.

This design removes both burdens, which is what the maintainer asked for:

- **No extraction script.** DDD reads every address the a2l carries out of the linked ELF image
  itself, objects by name and members by access path, from the image's DWARF.
- **No two-run build.** The a2l becomes one step after the link, and one build gives the complete
  a2l.

SPEC.md section 6 has planned this: "Reading the linker output directly (ELF/DWARF, IEEE-695) and
cross-checking the linked symbols against the declarations is *planned*." This design does the
ELF/DWARF half of the reading. The JSON map stays supported exactly as it is.

### Not in this design

Each is recorded in section 9.

- **Comparing each linked variable's type with its declaration**, e.g. DDD saying `uint16` where
  the C code has `int32_t`. The maintainer set it aside.
- **Bitfield members in the a2l.** They stay out, as they are today. The image does say where a
  bitfield's bits are, so describing one with a `BIT_MASK` is now possible, and it is left open.
- **IEEE-695** and every image format but ELF.
- **Images the reader refuses**: relocatable objects, images without DWARF, DWARF type units, gcc's
  link-time optimisation, damaged files. They are refused here as `ddd tool from-elf` refuses them.

## 2. The command line

`ddd generate a2l --image firmware.elf`, and the same option on `ddd generate all`.

- **What it reads.** Every symbol the a2l carries an `ECU_ADDRESS` for, as `addressed_symbols`
  lists them, is looked up in the image. An object is found by its name. A structure member is found
  by its access path - `Inlet.latest`, `Inlet[2].raw`, `Grid[1][2].v`, `Outer.inner.x` - as the
  variable's address plus the offsets its DWARF type gives (section 4).
- **Combinations.** `--image` and `--address-map` cannot be combined: a usage error naming both. A
  run that does not write the a2l refuses `--image`, as it refuses `--address-map` today ("belongs to
  the a2l artefact, left out by --without").
- **Which images.** What `ddd.elf.open_image` reads: a linked ELF (`ET_EXEC` or `ET_DYN`) with
  DWARF 2 to 5. Its refusals are usage errors, exit 2, with the reader's own sentences.
- **Byte order.** The image states its own, so `--image` sets the a2l's byte order. A `--byte-order`
  that agrees is accepted; one that contradicts the image is a usage error naming both, so a big
  endian target can no longer get a little endian a2l by mistake. Without `--image`, nothing
  changes: `--byte-order`, default little.
- **What cannot be placed** gets address 0 and is reported by the existing `address-missing` check
  (a warning by default, an error under `--strict`, and a run reporting it as an error writes
  nothing unless `--force`), exactly as a map that leaves a symbol out. With an image, each symbol's
  reason is a note of that finding (section 4).
- **Range.** An address outside `0 .. 0xFFFFFFFF` for a symbol the a2l carries is a usage error, as
  it is for the map, naming the symbol and where the address came from.

## 3. Where the code lives

Reading a build's addresses is core, not a backend's business: the a2l only consumes the result,
and SPEC.md gives address information a section of its own.

- **`src/ddd/addresses.py`** (new, core, beside `src/ddd/elf.py`): a build's address information,
  from either source.
  - `load_address_map(path, carried)` moves here from `ddd/backends/a2l/options.py`, unchanged in
    behaviour, with its tests. Its one caller is `generate` in `cli.py`.
  - `addresses_from_image(image, symbols)` is new. It returns the same `{symbol: address}` as the
    map, and the reason for each symbol it could not place.
- **The a2l backend keeps what is the a2l's own:** which symbols get an `ECU_ADDRESS`
  (`addressed_symbols`), the 32 bits of that field, now checked for both sources, and how an address
  is written. `ADDRESS_MAX` stays there.
- **`cli.py` chooses the source**: `--address-map` or `--image`. It opens the image through
  `open_image` only when `--image` is given, and hands the reasons to `address-missing`.
- **`ddd.elf`, the reader,** records whether a variable has external linkage, which DWARF states
  (`DW_AT_external`). pyelftools is already a runtime dependency (#76).
- `ddd.backends` stops re-exporting `load_address_map`. Its users move to `ddd.addresses`.

## 4. Placing a symbol

`addresses_from_image(image, symbols)` places each symbol on its own.

**The variable.** The image's variable of that name with external linkage. Two units describing
one variable at one address, as `-fcommon` or the `common` attribute make them, are one variable,
as `ddd tool from-elf` already treats them. A `static` of the same name never matches: every object
a dictionary describes is a global.

**The access path,** read as the a2l spells it: the object's name, then any number of steps.
Typedefs and `const`/`volatile` are seen through before each step.

- `.name` takes the named member's offset within a structure.
- `[i]`, one per dimension, takes `i` times the size of the array's element. An array of two
  dimensions takes two indices, row-major, as C lays it out.

**The reasons** a symbol is not placed, one note each:

- the image defines no variable of that name;
- only a `static` of that name exists;
- the variable has no storage, with the reader's own reason: declared only, folded into a constant,
  removed, discarded by the linker, thread-local, or a location that is not a fixed address;
- the variable's type has no member of that name, meaning the C code and the declaration disagree;
- a step indexes something that is not an array, or names a member of something that is not a
  structure;
- an index is out of range;
- a step names a bitfield, which an address cannot describe. The a2l carries no bitfield today, so
  this guards rather than happens.

The type at the end of a path is not compared with the declaration (section 1).

## 5. cmake: `ddd_generate(<image> ... ADDRESSES_FROM_IMAGE)`

An opt-in keyword. A project that does not give it builds exactly as today.

- **Before the link,** the generation runs as today but without the a2l, as `NO_A2L` already does
  (`--without a2l`). The C sources, the headers and the dictionary are unchanged.
- **After the link,** a second custom command runs `ddd generate a2l <project> --output-dir <dir>
  --image $<TARGET_FILE:<image>>`, with `STRICT`, `SEVERITY` and `BYTE_ORDER` passed on as given.
  - It declares the a2l as its output and depends on the image target and on the project's inputs.
    So it runs again whenever the image relinks or a description changes, and never otherwise.
  - A new target, `<stem>_ddd_a2l`, built by default (`ALL`), drives it.
  - The a2l keeps its path, and the image's `DDD_A2L` property still names it.
  - The output directory's manifest already lets an `a2l` run share a directory with an `all` run
    without touching the C it wrote (`backends/base.py`, `Manifest`).
- **One build gives the complete a2l:** no empty map seeded at configure time, no second build.
- **Contradictions** fail at configure time, naming both keywords: `ADDRESSES_FROM_IMAGE` with
  `ADDRESS_MAP`, and with `NO_A2L`.
- **Under `STRICT`,** an `address-missing` fails the post-link step, and the build stops rather than
  ship an a2l with addresses at 0.

## 6. Testing

**Unit tests of `addresses_from_image`,** over images built by hand as the toolbox's tests build
them. One test per rule of section 4:

- external linkage against a `static` of the same name, and a common pair;
- each reason;
- members' offsets, array elements in one and two dimensions, nested structures, typedefs and
  qualifiers;
- an index out of range;
- **bitfields**: a structure whose value members follow bitfields of several widths and signedness,
  each value member placed at its own offset, and a path naming a bitfield refused with its reason.

**Real images,** built in Docker and committed like the toolbox's fixture matrix, so that the suite
needs neither Docker nor a compiler. They come from a small DDD project holding scalars, a
structure, an array of structures, a nested structure, and **structures mixing bitfields with value
members**: bitfields of several widths and signedness, storage units of different sizes, a field
that would cross a boundary, and value members after them.

- Its C is what `ddd generate c` writes for the project, committed beside it. A test regenerates it
  with the current DDD and compares, so that the images can never drift from what DDD generates.
- It is compiled and linked for four toolchains of the matrix: little and big endian, 32 and 64 bit,
  gcc and clang.
- The oracle is the toolchain, never our reader: each symbol's address from `nm`, and each member's
  offset from the compiler's own `offsetof` and `sizeof`, compiled into the image and read back with
  binutils.
- For each image, `ddd generate a2l --image` must write exactly the oracle's `ECU_ADDRESS` for every
  object and member, and the image's byte order. It must give no bitfield an address.
- A contradicting `--byte-order` exits 2, as does `--image` combined with `--address-map`.

Bitfields get this much because their packing decides where every member after them lands, and the
ABIs differ on it: which storage unit holds a field, the padding after it, and whether a field may
cross a unit's boundary.

**cmake.** The existing cmake test, which builds a real image with the host toolchain, gains an
`ADDRESSES_FROM_IMAGE` build:

- one build gives an a2l whose addresses match `nm` and `offsetof` on that image;
- a second build with nothing changed runs no step;
- relinking the image regenerates the a2l;
- `ADDRESSES_FROM_IMAGE` with `ADDRESS_MAP`, or with `NO_A2L`, fails at configure time, naming both.

The project's usual gates apply: 100 % line and branch coverage, ruff, format and mypy clean, every
refusal sentence asserted whole, every hidden branch and data value pinned by a named test.

## 7. Documentation

- **SPEC.md:**
  - section 6 says the a2l's addresses may come from the image, and how;
  - IEEE-695 and the cross-check of the declarations stay planned;
  - section 7 gains `--image`;
  - section 7.1 gains the cmake keyword.
- **The build page:** it leads with the image route, `ADDRESSES_FROM_IMAGE` and one build. The `nm`
  recipe stays, for a build whose image carries no DWARF.
- **The command page** gets `--image`, the cmake reference `ADDRESSES_FROM_IMAGE`, and the README its
  rows.
- **The CHANGELOG's Unreleased section** gets both.

## 8. Errors at a glance

| Case | Outcome |
| --- | --- |
| `--image` with `--address-map` | usage error, exit 2 |
| `--image` in a run without the a2l | usage error, exit 2 |
| an image the reader refuses | usage error, exit 2, the reader's sentence |
| `--byte-order` contradicting the image | usage error, exit 2 |
| a carried address beyond 32 bits | usage error, exit 2, naming the symbol and the image |
| a symbol the image cannot place | `address-missing`, its reason as a note; address 0 |
| `ADDRESSES_FROM_IMAGE` with `ADDRESS_MAP` or `NO_A2L` | cmake configure error naming both |

## 9. Left open

- **Comparing each linked variable's type with its declaration** (SPEC.md section 6's other half).
- **Bitfield members in the a2l:** the address of the field's storage unit and a `BIT_MASK`, now
  that the image says where the bits are. Only for `--image`, since a JSON map still cannot.
- **IEEE-695** images.
- **Pointer members in `ddd tool from-elf`**, deferred by the maintainer on 2026-10-02 as "quite a
  change", with a note kept so it is not forgotten:
  - a pointer reached through a typedef could become a member naming that typedef as an external
    type, with no change to DDD's language;
  - a plain `T *member;` needs DDD itself to state pointers.

  It is recorded here and in the toolbox plan's "What was left open".
