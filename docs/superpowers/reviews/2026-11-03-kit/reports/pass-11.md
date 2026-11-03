## Pass 11: the toolbox and the ELF reader (SPEC 7.3)

### Scope covered

**Read in full, with line numbers:** `src/ddd/elf.py` 1-865, `src/ddd/addresses.py` 1-259, `src/ddd/toolbox/` (`__init__`, `checked`, `findings`, `from_elf`, `mapping`, `selection`, `values`), `docs/toolbox.rst` 1-258, `SPEC.md` 1995-2060 and 2478-2550, `docs/superpowers/specs/2026-09-30-toolbox-from-elf-design.md` and `2026-10-02-addresses-from-image-design.md`, the "left open" sections and rulings of both plans, `docker/build_elf_fixtures.py`, `docker/build_address_fixtures.py`, `tests/fixtures/elf/src/main.c`, `unit_a.c`, `gc_sections.c`, `tests/fixtures/addresses/oracle.c` and `project/`, `tests/test_elf_fixtures.py`, `tests/test_address_fixtures.py`. In `src/ddd/cli.py`: 75-98, 545-615, 981-1005, 1129-1243, 1365-1468. In pyelftools 0.33: `iter_DIE_children`, the line program header, `_read_dwarf_section`, `num_sections`.
**Read in part:** `tests/test_elf.py` 1-130, 856-1262 and every test name; `tests/test_toolbox_from_elf.py` 175-194, 775-894 and every test name; `tests/test_cli.py` 4356-4412 and the names around it. Passes 21 and 22 read the suites whole.

**Ran.** Every image was built with WSL `Ubuntu-24.04`, gcc 13.3.0 and g++ 13.3.0, GNU ld 2.42 and gold, x86-64, a PIE unless stated. All transcripts are under `SCRATCH/pass-11/`.
- `rt/`: one probe of 58 variables at DWARF 2, 3, 4, 5, strict 2, strict 4 and `-O2`, carried `from-elf` -> project -> `ddd generate all` -> gcc -> a fingerprint program (`sizeof`, `_Alignof`, `offsetof`, each bitfield's mask, each variable's bytes), compared with the same program over the source (`roundtrip.py`).
- `rand/`, `rand2/`: 800 random structures through the same chain.
- `var/`, `var2/`, `sec/`, `ovl/`, `c1/`, `bigdata/`: some 60 images over compiler and linker options, C++, assembler, odd types, sections, an overlay, `--only-keep-debug`.
- `hostile/`: 85 hand-made ELF and DWARF images (`mkelf.py`, `cases.py`) under a memory cap and a time limit; a seeded damage fuzz of 6,000 images over eight committed rows (`fuzz.py`, `fuzz-results.txt`).
- `mut/`: 60 hand-made mutants against the area's tests, in an exported copy of the tree.
- `big/`: a 72 MB `.debug_info`.
- The area's tests on the tree: all pass.

**Not covered.** No clang, lld, cross compiler or commercial compiler is here (GHS, TASKING, DIAB, IAR, CodeWarrior). Big endian, ARM and clang rest on the committed fixtures, which I read through the reader and through pyelftools directly. CMake flows are pass 9's. No calibration tool.

**Met again and cited, not re-filed, with what this pass adds:**
- pass 1 M7 (`from-elf` writes the identity claim): as filed, `from_elf.py:47-51`.
- pass 1 I12 (nothing holds the image to the description): the reader already has what a width check needs, `size_of` of the type a path ends at (`addresses.py:259`), and `test_every_sized_variable_is_the_size_the_symbol_table_gives_it` shows those sizes hold on every row.
- pass 8 M5 (`--image` on `ET_DYN`): as filed; every PIE here behaves so.
- pass 8 M15: `-g1` also reaches `from-elf`, as "`'V_Gain' is void`" (`var/transcript.txt`); `-gsplit-dwarf` with a glob says only "no variable matches".
- pass 5 M16 (caps stop at a declaration): `from-elf` prints a member of 2^40+1 elements, exit 0, `ddd check --strict` clean, `uint8_t m[1099511627777];` generated (`hostile/hm/`).
- pass 4 M2: unchanged.

### Strengths

- **Natural layouts round-trip exactly.** 400 random structures of mixed-width bitfields, arrays and floats with no unnamed field: `sizeof`, `offsetof` and every bitfield's mask identical after `from-elf` -> DDD -> gcc, DWARF 4 and 5 agreeing, no false `elf-bitfield-gap` in 800 (`rand/named.txt`). The "would fit" rule holds on this target.
- **Initial values survive byte for byte:** `-0.0`, denormals, `DBL_MAX`, `UINT64_MAX`, `INT64_MIN`, 3-D arrays, fills (`rt/rt-d5/diff.txt` shows no scalar).
- **The a2l of a round-tripped project is right:** 75 of 75 addresses checked equal `nm` plus `offsetof`, under `--strict` (`rt/rt-d5`).
- **Extraction is idempotent.** Extracting the generated image gives the same declarations but for enum conversions, which generated integers cannot carry (`var2/`).
- **Truncation and damage mostly end as they should.** 665 of 665 truncated files refused. 6,000 damaged images: no exception escaped `open_image` or `describe`, one hang (I6). No refusal among 3,282 carried a control character.
- **Type loops are refused cleanly.** Typedef, const/volatile, array, struct, struct pair and enum loops all answer exit 2 in 0.5 s. Chains deeper than the recursion limit refuse; shallower ones pass; none tracebacks.
- **Huge counts in a declaration are DDD's finding at once:** 2^64 elements, 2^40 structures, 100 dimensions, each exit 1, 0.5 s.
- **The refusals name the fix.** Type units, gcc LTO and zstd do; zlib and gnu-style compression, `-g3`, DWARF 64 at version 4, asan and `-fwhole-program` read right. Output is the same under three hash seeds.
- **The suite is mechanically strong:** 54 of 60 mutants killed (`mut/mutate-out.txt`). Its weakness is what it was never shown: C1 passes because every test of that branch is a double.

### Issues

#### Critical

- **C1. A positive enumerator of a signed enum is sign-extended from its form's width: gcc's 200 reads -56 and 40000 reads -25536, and every later stage agrees.**
  `src/ddd/elf.py:828-830`, `_DATA_WIDTHS` at `:68-75`.
  *Trigger* (`c1/status.c`, gcc 13.3): `typedef enum { STATUS_INVALID = -1, STATUS_OK = 0, STATUS_SNA = 200, STATUS_WARN = 40000 } Status_t; Status_t Inlet_Status = STATUS_SNA;`.
  *Observed*, at DWARF 2, 3, 4, 5 and `-fshort-enums`: `{"STATUS_INVALID": -1, "STATUS_OK": 0, "STATUS_SNA": -56, "STATUS_WARN": -25536}`, `"init": 200`, exit 0 and no warning. `ddd check --strict` exit 0. `ddd generate all` writes `STATUS_SNA = -56,` into `ddd_types.h`, `-56 "STATUS_SNA"` into the a2l's COMPU_VTAB and `int32_t Inlet_Status = 200;` into the definitions. Code recompiled against that header compares against -56; the tool shows 200 with no label. With `STATUS_SNA = 255` the only trace is `enum-duplicate-value ... STATUS_INVALID, STATUS_SNA all have the value -1`, which blames the source.
  *Why:* gcc writes a negative enumerator as `DW_FORM_sdata` and a non-negative one as `DW_FORM_dataN` by size, whatever the enum's sign. The branch sign-extends every `dataN` of a signed enum. Any enum with one negative enumerator and a positive one in 128..255 or 32768..65535 is hit. DWARF 5's `implicit_const`, used when a value repeats, escapes by luck, so one source reads differently by DWARF version (`rt/` `W_40K`: 40000 at 5, -25536 at 4).
  *Evidence the rule is wrong by the project's own sources:* `docs/superpowers/specs/2026-09-30-toolbox-from-elf-design.md:778-779` measured "a negative enumerator is `DW_FORM_sdata`, a positive one `DW_FORM_data1`", beside rule 4.3's "whatever DWARF form carries them". On all ten committed rows `SIGNED_NEG` is `sdata`; `SIGNED_POS` is `data1` on the eight gcc rows, `sdata` on clang (`mut/forms.txt`): no compiler of the matrix writes a negative as `dataN`, so the branch can only corrupt. It went unseen because the fixture's signed enum has `SIGNED_POS = 3` and its 200 is in an unsigned one (`tests/fixtures/elf/src/main.c:45,47`).
  *Change (S, with a fixture rebuild):* reinterpret only at the enum's full width (`width == 8 * byte_size`), where a value past the signed maximum cannot be positive; everywhere else a `dataN` is zero-extended. Add `SIGNED_BIG = 200` and `SIGNED_WIDE = 40000` to `Signed_e`.

#### Important

- **I1. A variable the linker discarded under gold keeps its offset in the discarded section as its DWARF address: `--image` writes it into the a2l with no finding, and `from-elf` can read code as its initial value.**
  `src/ddd/addresses.py:204-218`, `src/ddd/elf.py:360-366,605`. Contradicts `SPEC.md:2493-2494` ("leaves its DWARF address at 0 or at all ones") and `docs/toolbox.rst:218-220`.
  *Trigger* (`var/gc2/`): `-fuse-ld=gold -Wl,--gc-sections`, no `-fdata-sections`, a unit whose `.data` nothing references. `nm` holds none of these names and no allocated section lies below 0x270.
  *Observed:* `ddd generate a2l --image whole-gold.elf`, exit 0: `First_Unused 0x00000004`, `Second_Unused 0x00000008`, `Third_Unused 0x00000010`, `Struct_Unused.a 0x00000020`. `address-missing` names only the objects at offset 0, under `--strict` too. The same run on `from-elf` says "has an address, 0x4, that no section of the image holds": the check exists at `from_elf.py:138` and not in `addresses.py`. With text at 0 and the offset landing in `.text`, `from-elf` prints `"init": 3850979413, "section": ".text"`, exit 0 (`var/gc3-transcript.txt`).
  GNU ld writes 0 throughout, which the reader catches. Older lld is said to leave the addend likewise; not measured. Discarded objects are the case pass 1 I11 describes, tool-only objects under `--gc-sections`.
  *Change (S):* an external variable with no object symbol of its name at its address is not placed, whatever the address; only a `static` needs care, since `-Wl,-x` drops local symbols (design section 3.1). `addresses.py` also takes `image.section_of`.

- **I2. A packed structure is described as an unpacked one, in silence (KNOWN: toolbox plan "Packing is not detected").**
  `src/ddd/toolbox/mapping.py:385-415`, `docs/toolbox.rst:164-165`.
  *Trigger* (`rt/`): `struct { uint8_t a; uint32_t b; } __attribute__((packed))` reads 5 bytes with `b` at 1 in the source; generated 8 bytes with `b` at 4; `#pragma pack(2)` likewise, a packed member likewise. Exit 0, no finding, `ddd check --strict` clean.
  *Adds:* one name laid out two ways, packed in one unit and not in another, a classic bug, also passes as one entry, because `_register` compares the description and no offsets (`var/transcript.txt`, `pack.elf`), against "Two structures of one name that differ ... are `elf-type-conflict`" (`docs/toolbox.rst:147-149`).
  *Consequence:* a wire or NVM layout changes when generated C replaces the source. The page says so; the run does not. The offsets and the size that show it are in the model and read by nobody.
  *Change (S-M, with I3):* compare each member's offset and `Struct.size` with the natural layout under an alignment cap by `e_machine`, warn `elf-layout`, and put offsets in the conflict comparison.

- **I3. Half the layouts an unnamed or zero width bitfield changes are silent: `_gap` looks only at a following bitfield, and `Struct.size` is never compared.**
  `src/ddd/toolbox/mapping.py:464`, `:385-415`. The page's "The tool warns about the two traces it can read" (`docs/toolbox.rst:161-163`) understates what it can read.
  *Trigger, gcc x86-64, source then generated, no finding* (`rt/rt-d5/diff.txt`): `{uint8_t a; uint32_t :0; uint8_t b;}` `b` at 4 then 1, size 5 then 2; `{uint32_t a:3; uint32_t :0; uint8_t c;}` `c` at 4 then 1; `{uint32_t :8; uint8_t a;}` `a` at 1 then 0; `{uint8_t a:2; uint32_t :0;}` size 4 then 1.
  *Measured* (`rand2/unnamed.txt`): of 400 random structures with unnamed fields, 176 change layout; 90 warned, **86 silent**, no false warning.
  *Change:* the check of I2 covers these with no ABI question at all, since an offset past the natural slot needs no packing theory.

- **I4. An alignment stated on a variable is not read, though DWARF states it and the spec promises the finding.**
  `src/ddd/elf.py:183-198,589-621`. Contradicts `SPEC.md:2542` and `docs/toolbox.rst:238-240` ("an alignment the source states").
  *Trigger* (`rt/`): `_Alignas(64) uint32_t V_AlignedVar = 7;`. `readelf` shows `DW_AT_alignment: 64` on the variable; `from-elf` says nothing; generated `alignof` is 4. A DMA or cache-line buffer loses its alignment.
  A GNU vector type reads as a plain `float32[4]`, its 16 byte alignment lost likewise (`var2/transcript.txt`). Under `-gstrict-dwarf` no `elf-alignment` fires for anything, while `sizeof` still differs 32 against 8 (`rt/rt-d4s`).
  *Change (S):* read `DW_AT_alignment` on the variable and report it; `DW_AT_GNU_vector` the same way.

- **I5. An image holding only debug information prints every declaration with its initial value gone, exit 0.**
  `src/ddd/elf.py:517`, `src/ddd/toolbox/from_elf.py:148`. The design puts separate debug files out of scope (`:46`, "the DWARF has to be in the image"), and this file passes that test.
  *Trigger* (`var/keepdebug-transcript.txt`): `objcopy --only-keep-debug small.elf small.debug`; its `.text`, `.rodata` and `.data` are `NOBITS`. `ddd tool from-elf small.debug V_U16 V_Gain` gives `V_U16` and `V_Gain` with no `init` where the image has `4660` and `1.5`, and no finding: `elf-init-dropped` exists only for structures.
  *Plausible use:* a stripped image is refused with "build it with -g", so the next thing to try is its `.debug` companion. A `const float` gain of 1.5 becomes a generated zero.
  *Change (S):* an image whose executable sections have no contents is refused from `from-elf`. `--image` may keep reading it, since its addresses are right.

- **I6. A 710 byte image never returns, and a 785 byte one takes all the memory, against "a damaged file is a usage error".**
  `src/ddd/elf.py:370,698,712,741-745` through pyelftools `iter_DIE_children`, which follows `DW_AT_sibling` unchecked; `elf.py:551-553` through the line header's counts. Contradicts `docs/toolbox.rst:184-188`, `elf.py:388-391` ("An image is untrusted input").
  *Trigger* (`hostile/`): `DW_AT_sibling` pointing at its own entry on a top-level type, a member or an enumerator: killed at 40 s, spinning (`sibling_self_*.elf`, `transcript-1.txt`). A DWARF 5 line header with an empty entry format and a count of 2^40: 3 GB in 40 s, stopped only by my job object's cap, then `MemoryError`, exit 2 (`line_dirs_huge.elf`, `transcript-4.txt`). A zlib section grows 522 KB to 1 GB (`bomb_512mb.elf`).
  *Not only crafted:* one of 6,000 random damages hung, a word overwritten in `.debug_abbrev` (seed 1619, `hang-1619.elf`), `read_variables` looping over the same entries with its list growing, 415 MB at 45 s.
  *Reach:* the CLI and CMake's step after the link, where it stalls a build; the GUI does not read images (grep of `src/ddd`).
  *Change (S-M):* walk children with a forward-only cursor of the reader's own, refuse a sibling that does not advance, and read the line table only when a finding needs a path. See open question 3.

- **I7. An image built with gcc `-flto` cannot use `--image` at all, and no build page says so (KNOWN: toolbox plan, ruling 16).**
  `src/ddd/elf.py:487-492`. `docs/build_integration.rst`, which leads with `ADDRESSES_FROM_IMAGE`, never mentions it; only `SPEC.md:2547` and `docs/toolbox.rst:186` do.
  *Trigger* (`var/lto-transcript.txt`): `ddd generate a2l --image small-lto.elf`, exit 2, "build it without -flto", though `nm` holds both variables. LTO is a product decision on small targets, and `README.md:421` and `docs/concept.rst:342` treat it as ordinary. The route left is the `nm` map with member offsets by hand, which the feature exists to remove.
  *Change:* say so on the build page now (S); reading it is the plan's `DW_AT_abstract_origin` work (M). See open question 4.

- **I8. One pointer member refuses every variable reaching the structure (KNOWN: toolbox plan "Pointer members are refused, and must not be forgotten").**
  `src/ddd/toolbox/mapping.py:324-325`, `elf.py:78`.
  *Trigger:* `struct { uint8_t *p; ... }`, `struct { void (*f)(void); }`, `elf-type-unsupported` (`var2/transcript.txt`). The plan records a real firmware's `App_Values` refused for one member. Not silent; a stop for adoption, since pointers in structures are ordinary C. It is listed because it still stands and matters, as the plan asks.
  The plan's two paths stand: a typedef'd pointer as an `external` type (one task), a plain `T *` needs DDD to state pointers.

#### Minor

- **M1. A float32 of `FLT_MAX` is refused with a false reason.** `src/ddd/toolbox/values.py:48-52`. `float V = FLT_MAX;`: `shortest_float32` gives `3.4028235e+38`, numerically past the float32 maximum, and DDD's check says `init value 3.4028235e+38 does not fit into float32 (-3.4028234663852886e+38 .. 3.4028234663852886e+38)`, `'V_FMax' is left out`; `-FLT_MAX` likewise (`rt/d5.stderr`, `var2/transcript.txt`). The value holds and SPEC 7.3 says it is spelled so. `tests/test_toolbox_from_elf.py:885`, `test_the_largest_float32_is_not_spelled_past_what_a_float32_holds`, pins that it is spelled past. Plausible as a minimum tracker's start. Change (S): when the shortest spelling overshoots, use the exact value.

- **M2. A damaged debug string becomes a variable or member named `None`, exit 0.** `src/ddd/elf.py:857,864`: pyelftools answers an unterminated or out of range `DW_FORM_strp` with `None`, `_decoded` writes `str(None)`. `hostile/out/strp_cut_no_terminator.txt`: `"name": "None"`, `"init": 5`. 106 of 6,000 damaged images printed such a name. `elf.py:449-455` refuses a section past the end of the file for allocated sections only, so a debug section past the end reads as far as it goes (`debug_str_past_eof.elf`); the plan's "every section with contents lies within its file" holds of those alone. Change (S): `_text` refuses `None`; the bound covers every section with contents.

- **M3. A crafted attribute still ends in a traceback, exit 1.** `src/ddd/toolbox/mapping.py:372`, `:436`: `DW_AT_bit_size` as a string passes `open_image`, which validates no attribute's type, and `json.dumps` raises `TypeError` in `describe`, outside the net of `elf.py:414` and past `main`'s `(OSError, ValueError)` (`hostile/out/bit_size_string.txt`). Against `elf.py:390-391`. Change (S): the reader states that a size is an int.

- **M4. One odd type anywhere refuses the whole image, in python's words.** `src/ddd/elf.py:12-14,414-416`, whose docstring says an indescribable type "becomes an `Unsupported` node ... rather than an exception". `from-elf odd128.elf V_Other` or any `--image` run on an image holding one variable of an enum with a 128 bit enumerator: `is not an ELF image this tool can read: TypeError: int() argument must be a string, a bytes-like object or a real number, not 'ListContainer'` (`var/transcript.txt`). A CU of address size 2, as a 16 bit target would write (crafted; no such compiler here): `AssertionError: 2` (`hostile/`). `-gdwarf64 -gdwarf-5`: `('expected 1, found 0', MappingError('no decoding mapping for 0 [content_type]'))`, against "versions 2 to 5". The net also makes any bug of the reader read as a fault of the image. See open question 1. Change (M): build types only for the variables asked for, with M5, and catch per variable.

- **M5. Every run pays for the whole image.** `src/ddd/elf.py:369-379`: every variable's type is built whatever was asked. `open_image` on a 72 MB `.debug_info`, 60,000 variables: 80 s, then 0.05 s to place three symbols (`big/timeit.txt`). With `ADDRESSES_FROM_IMAGE` that is a cost of every link. Change: as M4.

- **M6. Units that disagree about one variable: the first unit's name wins, in silence.** `src/ddd/toolbox/selection.py:64,86-97`, `addresses.py:207`. `-fcommon` with `uint16_t Cal;` and `uint32_t Cal;`: `uint16`, `nm -S` says 4 bytes. `uint32_t Shared[2]` and `[4]`: dimensions `[2]`, 16 bytes. `__attribute__((weak)) uint16_t Weak_Cal` over a strong `uint32_t Weak_Cal = 0x12345678`: `uint16`, `"init": 22136`, exit 0 (`var/common-transcript.txt`). The design's opening names this drift as what the tool ends. The two types are in hand, and `st_size` too. Change (S): `elf-type-conflict` where a name at one address has two sizes.

- **M7. Sections at one address: the first wins.** `src/ddd/elf.py:231-233`. A real `OVERLAY` linker script, `.page1` and `.page2` at 0x20000: `Page2_Var` prints page 1's values and `"section": ".page1"`, exit 0 (`ovl/transcript.txt`). Change (S): the symbol's `st_shndx`, or a finding where two sections hold the address.

- **M8. C++ is misdescribed in silence where the design says it is refused or no candidate.** `src/ddd/elf.py:741-745,591-593` against the design's `:64-65`; `docs/toolbox.rst` says nothing of C++. `struct Derived : Base { uint16_t own; }`: one member, base members gone. A static member at DWARF 4 becomes a value member at offset 0. A namespace's `ns::OnlyInNs` is a candidate by its short name, since gcc puts its definition at the unit's top through `DW_AT_specification`, so a DDD object `OnlyInNs` compiled out of a mixed image gets the address of `_ZN2ns8OnlyInNsE`, `--image --strict`, exit 0 (`var/transcript.txt`, `var/cppns-transcript.txt`). Change (S): refuse a structure with `DW_TAG_inheritance` or a member without a location or bit offset, and a variable whose `DW_AT_specification` sits inside another scope.

- **M9. The name that "never reaches the output" reaches the reader.** `src/ddd/toolbox/from_elf.py:44-45`. `from-elf st.elf st_a.c:Gain st_b.c:Gain`: `component 'FromElf' declares 'Gain' twice (as output and as output)` (`var/transcript.txt`). No such component exists for the user.

- **M10. Two sentences the plans left (KNOWN).** `src/ddd/toolbox/selection.py:80`: a global defined in assembly reads "defined nowhere in the image" while `nm` holds it (`var/transcript.txt`, `asm5.elf`; addresses plan's last item). A header's folded `static const` is `elf-symbol-ambiguous`, telling the reader to prefix a unit, and prefixing one then earns `elf-no-storage` (`var/cppns-transcript.txt`, `st-o2.elf`; toolbox plan's "four small findings").

- **M11. Small untrue sentences.** `SPEC.md:2503-2504`: an `_Atomic` type is refused only where DWARF states it; `-gdwarf-4 -gstrict-dwarf` prints `_Atomic uint32_t` as a plain `uint32` (`bigdata/atom-transcript.txt`). `SPEC.md:2491-2494` omits the reason `docs/toolbox.rst:220` lists, an address no section holds. `elf.py:11`: "Every variation of DWARF stops here", see M4.

### Status of the 2026-09-15 findings in this area

None: the toolbox and the image reader are new since that review.

### Open questions

1. **Which compilers is the reader for?** Only gcc and clang are measured, and automotive projects often use others. If they are in scope, M4's whole-image refusal must become per variable and rows are needed; if not, the docs should say gcc and clang.
2. **Layout: warn, refuse, or say it in DDD?** I2 and I3 can be a warning, or an error for structures whose layout would change. Either way DDD still cannot generate the packed one, because "DDD states no offsets" is a principle (`SPEC.md:2539`). The answer decides whether `from-elf` is honest about packed projects or useful for them.
3. **Is a hostile image in scope?** `elf.py:388` says untrusted. If yes, I6 stands as graded; if the image is the build's own, it drops to Minor and the docstring and the page should say "damaged" with less reach.
4. **Read gcc LTO or keep refusing it?** I7. Decides whether `ADDRESSES_FROM_IMAGE` is the default route for LTO projects or the map stays theirs.
5. **Are gold and old lld supported linkers?** The cure of I1 needs no answer, but the sentence in `SPEC.md:2493` does.

### Test gaps

- **C1 is pinned by doubles at a form no compiler writes.** `tests/test_elf.py:254-264,328-345`. Dropping the sign extension fails only those; the matrix passes. No row has a positive enumerator of 128 or more in a signed enum.
- **Nothing tests the round trip.** No test takes `from-elf`'s output on to `ddd generate` and a compiler, the question this pass was asked; the address fixtures go the other way. A committed image of the generated C of a `from-elf` output, compared to the source's offsets as `oracle.c` does, keeps the suite compiler-free.
- **No loop, sibling, huge count or debug-section-past-EOF test.** `tests/test_elf.py:1467` damages a zlib stream, an entry and a compression type; the plan's seeded fuzz is not in the suite.
- **`tests/test_toolbox_from_elf.py:885`** pins the spelling, and nothing takes `FLT_MAX` through `checked`.
- **`gc-sections.elf` is `-fdata-sections` on GNU ld only;** no test puts an address outside every section through `--image`.
- **`_gap` is tested only on a following bitfield:** no value member after a gap, no trailing field, no size (`tests/test_toolbox_from_elf.py:789-817`).
- **Five surviving mutants are real gaps** (`mut/mutate-out.txt`; a sixth is equivalent):
  - `spelled.endswith(asked)`, because `src/app/xcal.c` shares an address with `cal.c` and `_distinct` hides it (`:178`);
  - a case-blind glob;
  - `.srodata` out of the defaults, the test being parametrized over the constant itself (`:1023`);
  - `DW_OP_addr` followed by anything accepted as an address;
  - a wrong nesting at three dimensions, the test being cubic (`:849`).

### Assessment

The reader is careful, well separated and honest about most of what it cannot do. For gcc and clang's ordinary output, the layouts, addresses and initial values I could check are right, byte for byte against the compiler. But the question was whether a wrong answer ever comes out silently, and it does. The worst is C1, a plain bug on every gcc row: an ordinary signed enum gets wrong values, DDD's "own check" passes them, and they reach the header and the a2l. It was invisible because each test of that branch is a double and the fixture's numbers are too small; the design's own evidence already contradicted the rule. Behind it sits a pattern: the model holds offsets, sizes, symbols and alignment that nobody compares, so packing, zero width fields, a variable's alignment, a gold-discarded address, a weak override and a debug-only file all pass in silence, where one cross-check against the image's own facts would catch most. "DDD itself checks every entry" is true and proves less than it sounds: that check judges the declaration, never the image. Hostile input is mostly refused, with a real hang left through `DW_AT_sibling`. None of this needs a redesign. A fix for C1, an `elf-layout` warning, a symbol cross-check and a round-trip fixture are days of work, and the first of them should come before the next release.

```candidates
11|C1|src/ddd/elf.py:828|A positive enumerator of a signed enum is sign-extended: gcc's 200 reads -56, 40000 reads -25536, clean under --strict, into the header and the a2l
11|I1|src/ddd/addresses.py:204|A variable discarded under gold keeps its section offset: --image writes 0x4 into the a2l with no finding, from-elf can read code as its init
11|I2|src/ddd/toolbox/mapping.py:385|A packed structure is described as an unpacked one in silence, and one name laid out two ways is no conflict (KNOWN)
11|I3|src/ddd/toolbox/mapping.py:464|Half the layouts an unnamed or zero width bitfield changes are silent: 86 of 176; _gap sees only a following bitfield, Struct.size is never compared
11|I4|src/ddd/elf.py:589|An alignment stated on a variable is not read though DWARF states it, against an alignment the source states is elf-alignment
11|I5|src/ddd/elf.py:517|An --only-keep-debug file prints every declaration with its init gone, exit 0, no finding
11|I6|src/ddd/elf.py:370|A 710 byte image never returns through DW_AT_sibling, a 785 byte one takes all the memory, against a damaged file is a usage error
11|I7|src/ddd/elf.py:487|An image built with gcc -flto cannot use --image at all, and no build page says so (KNOWN)
11|I8|src/ddd/toolbox/mapping.py:325|One pointer member refuses every variable reaching the structure (KNOWN)
11|M1|src/ddd/toolbox/values.py:48|A float32 of FLT_MAX is refused with a false reason; the test's name says the opposite of what it pins
11|M2|src/ddd/elf.py:857|A damaged debug string becomes a variable named None, exit 0; debug sections past the end of the file are not refused
11|M3|src/ddd/toolbox/mapping.py:372|A crafted attribute still ends in a traceback, exit 1, outside the net of open_image
11|M4|src/ddd/elf.py:414|One odd type anywhere refuses the whole image in python's words: 128 bit enumerator, address size 2, -gdwarf64 at 5; the docstring says otherwise
11|M5|src/ddd/elf.py:369|Every run pays for the whole image: 80 s at 72 MB of .debug_info to place three symbols
11|M6|src/ddd/toolbox/selection.py:64|Units disagreeing about one variable, -fcommon or weak: the first unit's name wins in silence, uint16 where nm says 4 bytes
11|M7|src/ddd/elf.py:231|Sections at one address, a linker OVERLAY: the first wins, a variable gets the other page's values and section
11|M8|src/ddd/elf.py:741|C++ is misdescribed in silence: base members dropped, a static member at offset 0, a namespace variable a candidate by its short name
11|M9|src/ddd/toolbox/from_elf.py:44|The name that never reaches the output reaches the reader: component 'FromElf' declares 'Gain' twice
11|M10|src/ddd/toolbox/selection.py:80|Two sentences the plans left: defined nowhere of an assembly global, ambiguous of a folded static (KNOWN)
11|M11|SPEC.md:2503|Small untrue sentences: _Atomic is refused only where DWARF states it, SPEC omits the no-section reason, every variation stops here
```
