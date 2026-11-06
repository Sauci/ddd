### Verification of pass 11

By a reader who did not find these, on 2026-11-06, on the tree at master 2b4bae6c. Scratch:
`SCRATCH/verify-11-12/`. 20 CONFIRMED. No grade changes.

| id | verdict | grade (was -> now) | duplicate of | evidence | note |
| --- | --- | --- | --- | --- | --- |
| C1 | CONFIRMED | Critical -> Critical | - | verify-11-12/p11/c1/forms.txt; verify-11-12/p11/c1/c1-fromelf.txt; verify-11-12/p11/c1/proj/c1-chain.txt; verify-11-12/p11/c1/proj/c1-compiled.txt; verify-11-12/p11/c1/implicit.txt; verify-11-12/p11/c1/s255.txt | reproduced with gcc 13.3 at DWARF 2, 3, 4, 5, strict 2, strict 4 and -fshort-enums: gcc writes every negative enumerator as sdata and every positive one as data1/data2, so STATUS_SNA 200 reads -56, STATUS_WARN 40000 reads -25536, 128 reads -128 and 32768 reads -32768, exit 0 with one info; check --strict exit 0; generate writes STATUS_SNA = -56 into ddd_types.h, -56 "STATUS_SNA" into the COMPU_VTAB and limits -25536 .. 0 on the measurement and on the value block whose init is {0, 200, 40000}; one program compiled against the source prints equal=1, against the generated header equal=0; wider than filed: the a2l's limits are wrong too |
| I1 | CONFIRMED | Important -> Important | - | verify-11-12/p11/i1/build.txt; verify-11-12/p11/i1/i1-a2l.txt; verify-11-12/p11/i1/i1-run.txt | reproduced: gold, --gc-sections, no -fdata-sections, a unit whose .data nothing reads: DW_OP_addr 0, 4, 8, 0x10, nm holds none of them; generate a2l --image writes First_Unused 0x4, Second_Unused 0x8, Struct_Unused.a 0x10, .b 0x14, exit 0, address-missing names only the object at offset 0; --strict on a project without that one exits 0 with the same addresses; from-elf on the same image says no section holds 0x4 (from_elf.py:138), but with .text at 0 it prints init 3850979413 (the bytes of push rbp; mov rsp,rbp) and section .text, exit 0 |
| I2 | CONFIRMED | Important -> Important | - | verify-11-12/p11/layout/fingerprint.txt; verify-11-12/p11/layout/fromelf.txt; verify-11-12/p11/layout/pair.txt | reproduced: packed, pack(2) and a packed member: 5 bytes b@1 -> 8 bytes b@4, 8 -> 12, 5 -> 8, same gcc over the source and over the generated header, no finding, check --strict clean; struct Pair packed (5 bytes) in one unit and natural (8) in another: one types entry, no elf-type-conflict, exit 0; KNOWN holds: plans/2026-09-30-toolbox-from-elf.md:6429 |
| I3 | CONFIRMED | Important -> Important | - | verify-11-12/p11/layout/fingerprint.txt; verify-11-12/p11/layout/fromelf.txt | reproduced on the four shapes filed: {uint8 a; uint32 :0; uint8 b} 5 b@4 -> 2 b@1, {a:3; :0; uint8 c} 8 c@4 -> 4 c@1, {uint32 :8; uint8 a} a@1 -> a@0, {uint8 a:2; uint32 :0} 4 -> 1, all silent; the control {a:3; :5; b:4} is warned elf-bitfield-gap; the pass's 86 of 176 random ratio was not re-measured |
| I4 | CONFIRMED | Important -> Important | - | verify-11-12/p11/layout/build.txt; verify-11-12/p11/layout/fingerprint.txt; verify-11-12/p11/layout/fromelf.txt | reproduced with a correction of the promise: _Alignas(64) on a variable, DW_AT_alignment 64 in the image, no finding, generated __alignof__ 4; a GNU vector reads float32[4], alignment 16 -> 4; under -gdwarf-4 -gstrict-dwarf no elf-alignment fires at all (a member _Alignas(16) warned at DWARF 5 only); SPEC.md:2539-2542's sentence sits in the paragraph on a structure's layout, so the broken promise is the guide's unqualified table row (docs/toolbox.rst:238-240) |
| I5 | CONFIRMED | Important -> Important | - | verify-11-12/p11/i5/build.txt; verify-11-12/p11/i5/i5.txt | reproduced: objcopy --only-keep-debug leaves .text, .rodata, .data, .bss NOBITS; from-elf small.debug prints V_U16, const float V_Gain, V_Zero and V_Struct with no init and no elf-init-dropped, exit 0, where the image gives 4660 and 1.5; the stripped image is refused 'build it with -g' |
| I6 | CONFIRMED | Important -> Important | - | verify-11-12/p11/i6/craft.txt; verify-11-12/p11/i6/sibling.txt; verify-11-12/p11/i6/sibling-a2l.txt; verify-11-12/p11/i6/linehdr.txt; verify-11-12/p11/i6/bomb-hang.txt | reproduced on my own images: a real gcc image (DWARF 5 and 4) with one 4-byte patch, a top-level struct's or enum's DW_AT_sibling pointing at itself: from-elf and the post-link generate a2l --image spin until killed at 30 s, memory flat; pyelftools 0.33 compileunit.py:216-222 follows the sibling unchecked; on the pass's crafted inputs (generator read): the 785-byte line header reached my 1.2 GB cap in 15 s then MemoryError exit 2, the 522 KB zlib bomb peaked at 1056 MB and exited 0, hang-1619 was still running at 45 s and 406 MB |
| I7 | CONFIRMED | Important -> Important | - | verify-11-12/p11/i7/build.txt; verify-11-12/p11/i7/i7.txt | reproduced: gcc -O2 -flto, nm holds V_Counter, generate a2l --image exit 2 'build it without -flto'; docs/build_integration.rst:604-610 names a build without -g and a non-ELF image and not LTO; KNOWN holds: plans/2026-09-30-toolbox-from-elf.md:6432 and ruling 16 |
| I8 | CONFIRMED | Important -> Important | - | verify-11-12/p11/i8/i8.txt | reproduced: uint8_t *p, a function pointer member, and a structure nesting the first: elf-type-unsupported naming the member, exit 1; not silent and documented (SPEC.md:2503-2504, docs/toolbox.rst:221-224); KNOWN holds: plans/2026-09-30-toolbox-from-elf.md:6437-6439 |
| M1 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m1/m1.txt | reproduced: float V = FLT_MAX and -FLT_MAX: init-invalid 'init value 3.4028235e+38 does not fit into float32 (-3.4028234663852886e+38 .. 3.4028234663852886e+38)', left out, exit 1, though 3.4028235e+38 packs to FLT_MAX exactly; tests/test_toolbox_from_elf.py:885-887 pins that spelling |
| M2 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m2/craft.txt; verify-11-12/p11/m2/m2.txt | reproduced on my own patches of a gcc image: a name's strp offset past .debug_str prints "name": "None", init 3, exit 0; .debug_str's header moved to 16 bytes before the end is not refused at open (elf.py:449-455 bounds allocated sections only), and its garbage names reach DDD's schema check, exit 1 |
| M3 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m3/m3.txt | reproduced on the pass's crafted bit_size_string.elf, its generator read (hostile/cases.py:165-170): TypeError: Object of type bytes is not JSON serializable from mapping.py:436 via :372, a traceback, exit 1 |
| M4 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m4/build.txt; verify-11-12/p11/m4/m4.txt | reproduced: an enum with a 1<<70 enumerator anywhere refuses from-elf V_Other and generate a2l --image of a project naming V_Other alone, 'TypeError: int() argument must be ... not 'ListContainer'', exit 2; -gdwarf64 -gdwarf-5 refused with pyelftools' MappingError, -gdwarf64 -gdwarf-4 reads; the address size 2 case was not run (no such compiler, crafted only) |
| M5 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m5/build.txt; verify-11-12/p11/m5/m5.txt | reproduced at a smaller size: one variable asked, 2,000 / 20,000 / 60,000 variables (.debug_info 0.13 / 1.3 / 4.0 MB): 1.1 / 6.5 / 19.4 s, linear in the image |
| M6 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m6/build.txt; verify-11-12/p11/m6/m6.txt | reproduced: -fcommon uint16_t Cal and uint32_t Cal, nm -S 4: uint16; Shared[2] and Shared[4], 16 bytes: dimensions [2]; weak uint16_t Weak_Cal over a strong uint32_t 0x12345678: uint16, init 22136; exit 0, no finding |
| M7 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m7/build.txt; verify-11-12/p11/m7/m7.txt | reproduced with a linker OVERLAY of .page1 and .page2 at 0x20000: Page2_Var prints page 1's 0x11111111 and section .page1, exit 0 |
| M8 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m8/build.txt; verify-11-12/p11/m8/m8.txt | reproduced with g++ 13.3: Derived : Base has one member, own; a static member is a value member at DWARF 4; ns::OnlyInNs is a candidate as OnlyInNs, and generate a2l --strict --image gives a DDD object OnlyInNs the address of _ZN2ns8OnlyInNsE, exit 0; against design 2026-09-30:64-65 |
| M9 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m9/m9.txt | reproduced: st_a.c:Gain st_b.c:Gain gives duplicate-declaration "component 'FromElf' declares 'Gain' twice", exit 1; the name never reaches the json, as from_elf.py:44-45 says, but it does reach the diagnostics |
| M10 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m10/build.txt; verify-11-12/p11/m10/m10.txt | reproduced both: an assembly global nm holds reads 'only declared here, and defined nowhere in the image'; a header's folded static const is ambiguous 'prefix it with one, as ka.c:K_Folded', and ka.c:K_Folded is elf-no-storage; KNOWN holds: plans/2026-10-02-addresses-from-image.md:5612, plans/2026-09-30-toolbox-from-elf.md:6435 |
| M11 | CONFIRMED | Minor -> Minor | - | verify-11-12/p11/m11/build.txt; verify-11-12/p11/m11/m11.txt; read off SPEC.md:2489-2494, docs/toolbox.rst:215-220, src/ddd/elf.py:11 | confirmed, wider: gcc 13.3 writes no DW_TAG_atomic_type at -gdwarf-4 strict or not, so _Atomic uint32_t reads as a plain uint32, exit 0, refused at DWARF 5 only; SPEC's list lacks 'an address no section holds'; elf.py:11 is contradicted by M4 |

No candidate of pass 11 is refuted or left plausible, and no grade changes. C1 is confirmed wider than
filed; I1, I4, I6, M3, M4, M9 and M11 carry corrections or limits of method.

Every image is mine, built in WSL Ubuntu-24.04 with gcc and g++ 13.3, GNU ld 2.42 and gold, as the
ordinary user; every run is the review tree's `ddd.exe` 0.11.0. Three hostile inputs are the
pass's crafted images, used as input after reading their generator: the line header, the zlib bomb
and `hang-1619.elf` (I6), and `bit_size_string.elf` (M3). Every capped run went through my own
`verify-11-12/scripts/capped.py`, a job object's memory cap and a wall clock.

**C1, confirmed and wider: Critical kept** (`p11/c1/`).
- The forms, read with pyelftools: in every signed enum gcc writes a negative enumerator as
  `DW_FORM_sdata` and a positive one as `DW_FORM_data1` or `data2`. That holds at DWARF 2, 3, 4,
  5, strict 2, strict 4 and under `-fshort-enums`. `elf.py:828-830` sign-extends each `dataN` of
  a signed enum, so:
  - 200 reads -56 and 40000 reads -25536;
  - 128 reads -128 and 32768 reads -32768;
  - `data4` values below 2^31 come out right;
  - an enum with no negative enumerator is unsigned and reads right;
  - a signed enum whose positive values are all below 128 reads right.
- Carried on: `--component` plus a reader, `ddd check --strict` exit 0, then `generate all`:
  - `ddd_types.h` holds `STATUS_SNA = -56,`;
  - the a2l holds `-56 "STATUS_SNA"` in the `COMPU_VTAB`;
  - the definitions hold `int32_t Inlet_Status = 200;`.
- What this adds to the pass: the a2l's limits are derived from the wrong enumerators and come out
  as -25536 .. 0. That holds both for the `MEASUREMENT` and for the value block, whose initial
  values {0, 200, 40000} lie outside them.
- The same program, compiled with MinGW gcc 15.2, prints `equal=1` against the source and
  `equal=0` against the generated header.
- DWARF 5's `implicit_const` escapes, so one source reads 40000 at version 5 and -25536 at 4.
- The 255 variant gives the `enum-duplicate-value` warning that blames the source.
- The pass's test claim holds: `tests/test_elf.py:328-345` parametrizes `data1 0xFF` on a 4-byte
  `int` enum and asserts -1, which is the reading that corrupts gcc's output.

**I1, confirmed with a correction of reach** (`p11/i1/`).
- What gold writes: an unreferenced unit's DWARF addresses become the offsets 0, 4, 8 and 0x10
  inside the discarded section. `nm` holds none of the names.
- `--image` writes 0x4, 0x8, 0x10 and 0x14 with no finding, so the defect is as filed.
- The correction: `--strict` does stop a run whose project also names the object at offset 0,
  because that one is caught. A run is silent under `--strict` when no object of the project sits
  at offset 0, as in my second project.
- GNU ld 2.42 differs from the pass's "writes 0 throughout": it drops a wholly discarded unit's
  DWARF, and the reader answers "holds no variable named". Either way GNU ld is caught.
- With a linker script that puts `.text` at 0, `from-elf` takes code as the initial value.

**I4, confirmed with a correction of the promise** (`p11/layout/`).
- The effect is as filed: a variable's `_Alignas(64)` and a GNU vector's 16 bytes are both lost in
  silence.
- `SPEC.md:2539-2542` ("an alignment the source states is `elf-alignment`") closes a paragraph
  about the layout of a structure. Read in that context, it does not promise a finding on a
  variable. The guide's findings table does: `docs/toolbox.rst:238-240` says "an alignment the
  source states" with no qualifier. The grade stands on the effect.

**I6, confirmed, partly on the pass's inputs** (`p11/i6/`).
- The sibling loop is mine: two real gcc 13.3 images, each with one patched word. Both spin, in
  `from-elf` and in the post-link `generate a2l --image`, which is where it would stall a build.
- The line-header count, the zlib bomb and the seed-1619 image are the pass's crafted files:
  - my cap stopped the line header at 1.2 GB after 15 s, where the pass saw 3 GB at 40 s;
  - the bomb completed at a 1056 MB peak;
  - 1619 was still growing at 45 s.

**M3 and M4, confirmed within limits.**
- M3 rests on the pass's crafted image; I read the generator before running it. No compiler
  writes `DW_AT_bit_size` as a string.
- M4's address-size-2 case was not run, for want of a 16-bit compiler. Its 128-bit enumerator and
  DWARF 64 at version 5 were reproduced with gcc 13.3.

**M9 and M11, confirmed with corrections.**
- M9: `FromElf` never reaches the json, which is what `from_elf.py:44-45` claims. It does reach the
  reader through a diagnostic about a component that does not exist.
- M11 is wider than filed: plain `-gdwarf-4`, and not only strict DWARF, drops `_Atomic` with gcc
  13.3.

```verdicts
11|C1|CONFIRMED|Critical|Critical|-|gcc 13.3 at DWARF 2-5, strict and short enums writes negative enumerators sdata and positive ones data1/data2; 200 reads -56, 40000 -25536, 128 -128, 32768 -32768, exit 0; check --strict clean; ddd_types.h STATUS_SNA = -56, COMPU_VTAB -56, and (wider) the a2l limits -25536..0 exclude the real 200 and 40000; the same program prints equal=1 on the source and 0 on the generated header
11|I1|CONFIRMED|Important|Important|-|gold --gc-sections leaves DWARF addresses 0x4, 0x8, 0x10 of a discarded unit; --image writes them with no finding, --strict exit 0 when no project object sits at offset 0 (only that one is caught); from-elf takes .text bytes as init when text lies at 0; GNU ld 2.42 drops the unit's DWARF instead
11|I2|CONFIRMED|Important|Important|-|packed, pack(2) and a packed member: 5 b@1 -> 8 b@4, 8 -> 12, 5 -> 8 against the same gcc, no finding, check --strict clean; one struct name packed in one unit and natural in another is one entry, no elf-type-conflict; KNOWN holds (toolbox plan :6429)
11|I3|CONFIRMED|Important|Important|-|the four filed shapes all change layout in silence (b@4 -> 1, c@4 -> 1, a@1 -> 0, size 4 -> 1); the {a:3; :5; b:4} control is warned; the 86 of 176 random ratio not re-measured
11|I4|CONFIRMED|Important|Important|-|_Alignas(64) on a variable: DW_AT_alignment 64 in the image, no finding, generated alignof 4; GNU vector 16 -> 4; strict DWARF 4 fires no elf-alignment at all; correction: SPEC.md:2539-2542 is about structure layout, the broken promise is docs/toolbox.rst:238-240
11|I5|CONFIRMED|Important|Important|-|--only-keep-debug file: .text/.rodata/.data/.bss NOBITS; from-elf prints V_U16 and const float V_Gain with no init and no finding, exit 0, where the image gives 4660 and 1.5
11|I6|CONFIRMED|Important|Important|-|my own real gcc images with one patched DW_AT_sibling pointing at itself spin in from-elf and in generate a2l --image until killed at 30 s; pyelftools follows the sibling unchecked; on the pass's crafted inputs the line header hit my 1.2 GB cap in 15 s (MemoryError, exit 2), the bomb peaked at 1056 MB, hang-1619 ran past 45 s
11|I7|CONFIRMED|Important|Important|-|gcc -flto image: generate a2l --image exit 2 'build it without -flto' though nm holds the variable; docs/build_integration.rst:604-610 does not say so; KNOWN holds (toolbox plan :6432, ruling 16)
11|I8|CONFIRMED|Important|Important|-|a data pointer, a function pointer and a structure nesting one: elf-type-unsupported naming the member, exit 1; documented and not silent; KNOWN holds (toolbox plan :6437)
11|M1|CONFIRMED|Minor|Minor|-|FLT_MAX and -FLT_MAX refused init-invalid 'does not fit into float32', left out, exit 1, though 3.4028235e+38 packs to FLT_MAX; test_toolbox_from_elf.py:885 pins the spelling
11|M2|CONFIRMED|Minor|Minor|-|my own patch: a strp past .debug_str gives a variable named None, init 3, exit 0; .debug_str moved past the end is not refused at open and its garbage names reach the schema check
11|M3|CONFIRMED|Minor|Minor|-|the pass's crafted bit_size_string.elf (generator read): TypeError bytes not JSON serializable at mapping.py:436, traceback, exit 1
11|M4|CONFIRMED|Minor|Minor|-|a 1<<70 enumerator anywhere refuses from-elf and --image of a project not naming it, in TypeError's words, exit 2; -gdwarf64 at 5 MappingError, at 4 reads; address size 2 not run
11|M5|CONFIRMED|Minor|Minor|-|one variable asked of 2,000 / 20,000 / 60,000 variables: 1.1 / 6.5 / 19.4 s, linear in the image
11|M6|CONFIRMED|Minor|Minor|-|-fcommon uint16/uint32 Cal (nm 4 bytes) reads uint16; Shared[2]/[4] reads [2]; weak uint16 over strong uint32 0x12345678 reads uint16 init 22136; exit 0
11|M7|CONFIRMED|Minor|Minor|-|OVERLAY .page1/.page2 at 0x20000: Page2_Var prints page 1's 0x11111111 and section .page1, exit 0
11|M8|CONFIRMED|Minor|Minor|-|g++ 13.3: Derived loses its base members, a static member is a value member at DWARF 4, ns::OnlyInNs is a candidate and --image --strict gives a DDD OnlyInNs the address of _ZN2ns8OnlyInNsE
11|M9|CONFIRMED|Minor|Minor|-|two unit-prefixed statics give "component 'FromElf' declares 'Gain' twice", exit 1; the name stays out of the json and reaches the diagnostics
11|M10|CONFIRMED|Minor|Minor|-|assembly global nm holds reads defined nowhere; a folded header static is ambiguous then elf-no-storage once prefixed; KNOWN holds (addresses plan last item, toolbox plan :6435)
11|M11|CONFIRMED|Minor|Minor|-|wider: gcc 13.3 drops DW_TAG_atomic_type at -gdwarf-4 strict or not, _Atomic uint32_t reads uint32, exit 0; SPEC's no-storage list lacks the no-section reason the guide has; elf.py:11 contradicted by M4
```
