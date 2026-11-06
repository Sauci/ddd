### Verification of pass 1

By a reader who did not find these, on 2026-11-06, on the tree at master 2b4bae6c. Scratch:
`SCRATCH/verify-1-2/`. 31 CONFIRMED. No grade changes.

| id | verdict | grade (was -> now) | duplicate of | evidence | note |
| --- | --- | --- | --- | --- | --- |
| C1 | CONFIRMED | Critical -> Critical | - | verify-1-2/c1/run.txt | reproduced on gcc 15.2: delta 0 from -Og, poll spins to its bound at -O1/-O2/-O3, no warning under the CI -Werror set; the UB is the generated declarations, gcc is entitled to it |
| C2 | CONFIRMED | Critical -> Critical | - | verify-1-2/c2/run.txt | reproduced with the documented recipe: one array grown, one build under STRICT, exit 0, no finding, Arr and Out at the previous link's addresses; the clean-checkout zeros are documented, the stale case is not |
| C3 | CONFIRMED | Critical -> Critical | - | verify-1-2/c3/compare.txt, c3/abi.txt | reproduced: insertion is info and can replace under --strict; external member swapped, removed or dimensioned is no finding; an old-header consumer reads 0 in all four; reordering (the fixed case) is an error |
| C4 | CONFIRMED | Critical -> Critical | - | verify-1-2/c4/transcript.txt | reproduced: start page lists only b/ddd/fw/Fw.ddd.json; a created component and a hand-added include are written, check clean, and the next configure takes both entries back; correction: --target clean keeps the orphan, removing the build tree loses it |
| I1 | CONFIRMED | Important -> Important | - | verify-1-2/i1/run.txt | reproduced: default headers let the consumer write its input, -Werror clean, check clean; correction: the pointer cast is caught by -Wcast-qual in the CI set, a cast through uintptr_t, ddd_globals.h and the producer header are silent |
| I2 | CONFIRMED | Important -> Important | - | verify-1-2/i2/run.txt | reproduced: a shared type rescaled 0.1 to 0.01 checks clean under --strict and leaves every C file byte-identical, the a2l alone differs; concept.rst:394-396 and faq.rst:309 contradict each other as quoted; compare catches it against a baseline |
| I3 | CONFIRMED | Important -> Important | - | verify-1-2/i3/run.txt | reproduced: a read measurement widened 0..100 to 0..60000 is can replace under --strict, narrowing is an error, a reader omitting limits gets no mismatch; it is SPEC.md:1668 as written, against SPEC.md:1538 and comparing_deliveries.rst:528 |
| I4 | CONFIRMED | Important -> Important | - | verify-1-2/i4/run.txt | reproduced: unused constant changed or removed, raster event or cycle, section access or alignment, external header: each can replace under --strict while the a2l or ddd_types.h differ; a constant dimensioning an object is caught |
| I5 | CONFIRMED | Important -> Important | - | verify-1-2/i5/run.txt | reproduced on the demo without FEATURE_X: ValueG at 0x00000000 behind a comment; --strict stops and writes nothing; the only way through is address-missing=info, which then ships a really missing ValueE at 0; as SPEC.md:1923-1924, 2049-2051 design it |
| I6 | CONFIRMED | Important -> Important | - | verify-1-2/c2/run.txt | reproduced: an added object under STRICT fails every build, a reconfigure does not help, deleting the map needs a configure too; same cause as C2, one probe serves both |
| I7 | CONFIRMED | Important -> Important | - | verify-1-2/i7/run.txt | reproduced: const volatile stays read-only on MinGW gcc 15.2 (nm R, .calib READONLY) and in .rodata, flags A, on the fixtures of gcc 14.2, arm-none-eabi 14.2.1, clang 19.1.7; a write through its address faults; KNOWN holds (plan 2026-09-16:453-456 left it unmeasured) |
| I8 | CONFIRMED | Important -> Important | - | verify-1-2/i8/run.txt | confirmed as text: 3 IF_DATA XCP and no A2ML, MEMORY_SEGMENT or EPK in the vocabulary a2l, against ASAP2 1.6.1 3.5.75; one internal template, no option; KNOWN holds but its documented reader obligation is nowhere; what a tool does is unverified |
| I9 | CONFIRMED | Important -> Important | - | verify-1-2/i9/run.txt | confirmed: the demo writes SYMBOL_LINK "Diagnosis.faults" 0, the image holds Diagnosis alone, 3.5.123 defines the symbol of the linker map plus the element offset; correction: a map-based patcher fails, one reading debug information may resolve the path (unverified) |
| I10 | CONFIRMED | Important -> Important | - | verify-1-2/i10/run.txt | reproduced: MAP, VALUE, IDENTICAL, ROOT, MODULE pass check --strict and reach the a2l as /begin MEASUREMENT MAP, /begin MODULE MODULE, /begin GROUP ROOT; all five are in the 1.6.1 Index of Keywords and Enum Values, which Table 5 says identifiers must not match |
| I11 | CONFIRMED | Important -> Important | - | verify-1-2/i11/run.txt | reproduced on PE: the demo linked with --gc-sections against an empty main keeps 0 of 21 a2l objects (20 without it); no user page says so; correction: on PE neither used nor used,retain keeps it, retain being ELF-only |
| I12 | CONFIRMED | Important -> Important | - | verify-1-2/i12/run.txt | reproduced the template half: a house-style extern drops const and volatile, generate exits 0, the -O2 poll reads VSpeed once; the image half is the plan's own left-open item (2026-10-02-addresses-from-image.md:5606), KNOWN holds |
| I13 | CONFIRMED | Important -> Important | - | verify-1-2/i13/run.txt | three of the list reproduced: relaxed variant producers define Sig under VARIANT_A only and the VARIANT_B image fails to link; a vendor-defined object relaxed is still defined and the link fails; a structured parameter default is refused; the rest read off the pass transcript |
| I14 | CONFIRMED | Important -> Important | - | verify-1-2/i14/run.txt | reproduced: logger, not linking sensor, compiles with -DRING_SIZE=4096 -fshort-enums and prints ring size 4096 and a 1-byte enum; KNOWN dropped: no plan leaves it open, SPEC.md:2336-2337 and README.md:873-876 state it as the price |
| I15 | CONFIRMED | Important -> Important | - | verify-1-2/i15/run.txt | reproduced: check, list, dump, sources, artefacts, generate --dry-run, compare either side, check --baseline and ddd gui PROJECT before any connection import the project plugin; no switch; correction: sources and compare --help name plugins, neither says the module runs; lsp not rerun |
| M1 | CONFIRMED | Minor -> Minor | - | read off docs/concept.rst:402 | confirmed as text: "DDD is a command line tool", and the page names the language server, the gui and the toolbox nowhere (0 mentions each); line counts not rechecked |
| M2 | CONFIRMED | Minor -> Minor | - | read off docs/concept.rst:529-531, src/ddd/analysis.py:81-82, 915 | confirmed as text: mentions neither c nor a2l anywhere, against _A2L_MAX_DIMENSIONS (MATRIX_DIM in ASAP2 1.6.1) and _a2l_closure in analysis.py; the module docstring and the developer page hedge, the concept page does not |
| M3 | CONFIRMED | Minor -> Minor | - | verify-1-2/minors1/run.txt | reproduced with my own names: clock and exp pass check --strict; exp is a -Wbuiltin-declaration-mismatch warning, a source including <time.h> and the header fails, clock redeclared as different kind of symbol |
| M4 | CONFIRMED | Minor -> Minor | - | verify-1-2/minors1/run.txt | reproduced: init 250 under limits 10..20 on a uint8 and an axis 40,30,20,10 pass --strict; the limits half is SPEC.md:462-463 by design, the falling axis is stated nowhere |
| M5 | CONFIRMED | Minor -> Minor | - | verify-1-2/minors1/run.txt | reproduced: a hand-written Gone.h put at the path the manifest recorded is removed when the component leaves, against README.md:669 and base.py:131 |
| M6 | CONFIRMED | Minor -> Minor | - | read off SPEC.md:1883-1886 against SPEC.md:363-368 | confirmed as text: byte order is a property the descriptions cannot know and defaults to little, volatile is refused a default for the same reason; the map flow says nothing |
| M7 | CONFIRMED | Minor -> Minor | - | read off SPEC.md:2505-2507 against docs/faq.rst:271-276 | confirmed as text: from-elf writes the identity for every non-enum, the claim the FAQ says is an answer to state rather than a default to fall into |
| M8 | CONFIRMED | Minor -> Minor | - | verify-1-2/minors1/run.txt | reproduced: a measurement and a parameter in one read-write section check clean under --strict, then gcc: Learned causes a section type conflict with Count |
| M9 | CONFIRMED | Minor -> Minor | - | verify-1-2/i4/run.txt | reproduced on I4's project: N 4 to 5 under Arr[N] reads changed-interface ... (shape: [N] != [N]) |
| M10 | CONFIRMED | Minor -> Minor | - | verify-1-2/minors1/run.txt | reproduced without --strict only: a dump of a project failing missing-producer compares can replace with a changed-owner warning; under --strict it is an error and cannot replace |
| M11 | CONFIRMED | Minor -> Minor | - | verify-1-2/minors1/run.txt | reproduced: a hand-written uint32_t Speed beside DDD's uint16_t Speed = 100U links with no word under -fcommon and fails under -fno-common; no page says the guarantee needs -fno-common |
| M12 | CONFIRMED | Minor -> Minor | - | verify-1-2/minors1/run.txt | reproduced: a 128-character name of an array of 12 structures checks clean and reaches the a2l under --strict with first partial strings of 131 characters, against Table 5 and SPEC.md:422-425 |

**C1, confirmed with a correction of wording.** I wrote my own two-component project (`c1/`), checked it
clean under `--strict`, generated it with the example templates with and without `--const-inputs`, and
compiled each with MinGW gcc 15.2 under the CI's set (`-std=c11 -Wall -Wextra -Wpedantic -Werror
-Wconversion -Wshadow -Wcast-qual -Wstrict-prototypes`) at six levels. The const run gives
`extern const uint16_t Speed;` in `Cons.h` beside `uint16_t Speed = 100U;` in `ddd_globals.c`. A read,
a call to the producer, a second read: 7 under plain headers at every level; 0 under `--const-inputs` at
`-Og`, `-O1`, `-O2`, `-Os` and `-O3`, with no diagnostic; a bounded poll on a flag runs to its bound
(100000 against 2) at `-O1`, `-O2`, `-O3`. A `volatile` input, and a single read per call, are unaffected.
The `-O2` code of `cons_delta` is `call prod_step; xorl %eax,%eax; ret` (`c1/run.txt`). I looked for a
document that confines the option to a lint run and found none: `ddd_generate(... CONST_INPUTS)` feeds
it to the build that produces the image (`cmake/Ddd.cmake:574-576`, `docs/build_integration.rst:532-533`),
and `docs/concept.rst:195-198` says the usual toolchains "generate exactly the code one expects". The
pass's standard reading holds (C11 6.2.7p2 with 6.7.3p10: undefined behaviour, not a constraint); the
one correction is that gcc does not "miscompile": it is entitled to what it does, and the defect is the
pair of declarations the tool generates. Critical stands: an opted-in, documented build ships a consumer
that reads stale inputs.

**C2, confirmed with a correction.** My own project (`c2/`): two components, an image based at
`0x10000000` so that its addresses fit an `ECU_ADDRESS`, `ddd_generate(... ADDRESS_MAP ... STRICT)`, and
the extractor of `docs/build_integration.rst:648-661` copied verbatim as the `POST_BUILD` step; CMake
4.4.3, Ninja 1.13.2, MinGW gcc 15.2. Each object's `ECU_ADDRESS` is compared with `nm`'s address in the
image after every build (`c2/run.sh`). A clean configure and one build: exit 0, every address 0. A second
build settles. Then one array (`Arr`) grown from 2 to 40 elements in one description, one build: exit 0,
no finding, and the a2l holds `Arr` at `0x10007022` and `Out` at `0x10007026` while the image holds them at
`0x10007040` and `0x10007090`; the next build corrects both (`c2/run.txt`). Nothing in the file marks it.
The correction: part (a), zeros after a clean checkout passing `STRICT`, is the documented design
(`SPEC.md:2266-2270`, "so that first build passes under `STRICT` as well"); what no page says is (b),
that every later build whose edit moves an address publishes the previous link's addresses. Critical
stands on (b): the a2l of an ordinary incremental build points a calibration tool at other variables.
The guard I looked for, a finding when the map is older than the image it describes, does not exist:
the generation runs before the link and cannot know.

**C3, confirmed.** My own baseline (`c3/`), `Rec_t {speed, torque}` behind a producer and a reader, and
five candidates, each `ddd check --strict` clean. `ddd compare base.json <candidate> --strict`:
`status` inserted first is `info[added-object]` and "can replace", exit 0; the external member `h`
swapped from `Ha_t` to `Hb_t`, removed, or given `dimensions: [4]` is no finding at all and "can
replace", exit 0; the reordering the 2026-09-16 fix covers is `error[changed-interface]`, exit 1, so the
control works (`c3/compare.txt`). For the insertion and for each external change, a consumer compiled
against the baseline's header and linked with the candidate's definitions reads 0 where the producer
wrote 1234; built from one header it reads 1234 (`c3/abi.txt`). The refutation I looked for is SPEC's
own: `SPEC.md:1560-1562` lines up only shared members "since a member that arrived or left is already the
addition or the removal of the leaf it contributes". That covers the insertion as an `info`, which is
the grading the pass disputes on SPEC's own reason for reordering (`SPEC.md:1555-1559`), and it does not
cover an external member at all: its removal produces no finding of any kind, so SPEC's justification
fails on its own terms there. The grade rests on SPEC's reading that a released layout binds consumers
that are not rebuilt; under the other reading (pass 1 open question 1) the insertion half would be
Minor, the external half would still be a missed `changed-interface`. Critical stands. Pass 7 C1 later
files the same defect with further triggers (an appended member, a grown nested structure or array).

**C4, confirmed with a correction.** My own collected project (`c4/`): two components registered with
`ddd_add_component`, one image, `ddd_generate(fw NAME Fw ... NO_A2L)`, configured and built with CMake
4.4.3 and Ninja. `ddd gui` started with no project in the source directory, on `127.0.0.1`: `GET
/api/projects` lists one project, `b/ddd/fw/Fw.ddd.json`, the generated one. `ddd gui` on it: `GET
/api/files-plan?action=create&kind=component&name=newcomp&component=NewComp` plans
`b/ddd/fw/newcomp.ddd.json` and an entry in `b/ddd/fw/Fw.ddd.json`, and `POST /api/edit` answers 200;
`action=add` of a source-tree description that no target registers is planned and written the same way;
`ddd check` of the result exits 0. The next configure rewrites the project from `file(GENERATE)`: its
includes are back to the two registered files, no word anywhere (`c4/transcript.txt`). No refusal, no
note, in the plan or the reply. The correction: the pass says a clean build loses the file. `cmake --build
--target clean` does not (the new description is not a build output and stays, orphaned); it leaves the
project at the next configure and leaves the disk with the build tree, which a fresh checkout or a CI job
never has. The edit to `Fw.ddd.json` itself is overwritten outright. That `adopt_units` and the shared
plans create through the same `created_beside` is read off `src/ddd/lsp/units.py:139-150`, not run.
Critical stands: an edit the GUI wrote and answered 200 for is lost, in the module's default mode.

**I1, confirmed with a correction.** On C1's project, a consumer source writing `Speed`, which its
component declares `input`, compiled against the default headers under the CI's warning set with
`-Werror`: exit 0, and `ddd check` is clean (`i1/run.txt`). `README.md:9-11` ("generates the c code so that
nobody can write a variable that belongs to somebody else") is false for the default headers; the rest
of the documents say so honestly (`docs/concept.rst:135-157`, `docs/file_formats/component.rst:241-243`),
so this is the headline against the body. Under `--const-inputs`: a direct assignment is an error; a
`memset` and a cast `*(uint16_t *)&Speed` each draw a warning, so both stop a `-Werror` build. The
correction: the pass says the cast compiles "without one"; it does warn, under `-Wcast-qual`, which the
CI's set holds. What is silent even with `-Werror` is a cast through `uintptr_t`, an include of
`ddd_globals.h`, and an include of the producer's own header (`Prod.h`), each of which writes freely.
Important stands: the first promise a reader meets does not hold in the default mode.

**I2, confirmed with a correction.** My own project (`i2/`): a scalar type `Temp_t` (`sint16`, linear
0.1) named by the producer and the reader of `ValueF`. `ddd check --strict` is clean; the type's factor
changed to 0.01, it is still clean, and `ddd generate all` writes `Controller.h`, `UserInterface.h`,
`ddd_globals.c`, `ddd_globals.h` and `ddd_types.h` byte-identical to the 0.1 run, only `Drift.a2l`
differing (`i2/run.txt`), so no consumer source recompiles. `ddd compare` against a dump archived at 0.1
does report `changed-interface`. The two documents, both read: `docs/concept.rst:393-396`, the
redundancy "is precisely what allows DDD to notice that the two sides have drifted apart, which a single
shared declaration could never do"; `docs/faq.rst:308-309` and `README.md:473-474`, with a type "there
is nothing left for them to disagree about". Neither says what the type gives up. `ObjectView`
(`src/ddd/backends/c/model.py:42-91`) holds no unit except inside `comment`, and no conversion or limits.
The correction: the pass says a scale macro needs "a plugin backend"; a plugin's block reaching
`ObjectView.extensions` would do, which is still Python. The GUI's reconcile preview was not looked at.
Important stands: the concept's own motivating failure passes the documented best practice untouched.

**I3, confirmed: the behaviour is the one SPEC.md prescribes, and the finding is against that rule.** My
own project (`i3/`): `Speed`, a measurement with a reader, limits `[0, 100]` in the baseline. `ddd compare
base.json <candidate> --strict`: widened to `[0, 60000]`, "can replace", exit 0, no finding; narrowed to
`[0, 50]`, `error[narrowed-limits]`, exit 1. `ddd check --strict` of the widened project is clean while
the reader omits its limits, as `docs/faq.rst:235-243` recommends, and is `definition-mismatch` only if
the reader restates them (`i3/run.txt`). So a reader that followed the FAQ is told nothing by either
question. The code is `SPEC.md:1668` to the letter ("Widening a limit **shall** be silent, because every
value the baseline allowed still fits"); that sentence and `docs/comparing_deliveries.rst:526-528`
("there is nothing a consumer or a calibration dataset can trip over") reason from data flowing into
the software, which a measurement's reader is not, against `SPEC.md:1538`'s "graded by what it costs the
consumers". Important stands, as a decision for the maintainer rather than a slip in the code.

**I4, confirmed.** My own project (`i4/`) with a constant vocabulary (`N`, dimensioning `Arr`, and
`GAIN`, used by no object), a raster `10ms` of event 1, a section `.calib` (read-only, alignment 4)
holding `Kp`, and an external type `Drv_t` from `drv.h` inside a structure. Each change alone, each
`ddd check --strict` clean, compared against a dump of the baseline with `--strict`: `GAIN` 2 to 3,
`GAIN` removed, the raster's event 1 to 7, its cycle 10 to 20 ms, the section's alignment 4 to 64, its
access to read-write, and the external header renamed are all "can replace", exit 0, no finding. The
outputs do differ: `SYSTEM_CONSTANT "GAIN" "3"` and `ddd_types.h`, `EVENT 7` in the a2l, `#include
"other_drv.h"` in `ddd_types.h` (`i4/run.txt`). The dictionary carries `constants` and `rasters` and has
no `sections` key, as the pass says. The control: `N` changed 4 to 5 is `changed-interface` on `Arr`.

**I5, confirmed; the behaviour is the designed one and the finding is against the design.** The demo
(`examples/demo/demo.ddd.json`) rendered with the example templates and linked with MinGW gcc 15.2
without `FEATURE_X`, its map extracted with the documented `nm` reading (`i5/run.txt`). `ddd generate
a2l --address-map`: `warning[address-missing]` for `ValueG` (and for the member `Diagnosis.faults`, which
a symbol lister cannot answer), and the record reads `/* only present in the build when:
defined(FEATURE_X) */` then `ECU_ADDRESS 0x00000000`. With `--strict`: an error, exit 1, nothing
written. `-W address-missing=warning` beside `--strict` still stops; `address-missing=info` gets
through, and then a map that has lost the unconditional `ValueE` too writes it at `0x00000000` with
exit 0. `tests/test_cmake.py:940-944` lowers the check to `info` for exactly this reason, as the pass
says. `SPEC.md:1923-1924` and `2049-2051` state the design (a comment, address 0, `SYMBOL_LINK` for a
downstream tool), so the code does what SPEC says; the finding stands against `SPEC.md:1787-1789`'s own
reason for one definition file, an a2l "describing storage the image does not contain". I ran the map
route only; that `--image` sees the variable's absence is read off the pass's transcript.

**I6, confirmed.** Same run, same cause as C2: with the tree settled, one measurement added to a
description under `STRICT` gives `error[address-missing] ... no entry for 'Extra'` and stops before
anything compiles, so the map is never rewritten; three builds in a row, then a reconfigure, fail the
same way; deleting the map alone leaves Ninja with a missing input; deleting it and configuring again
builds, with every address 0 for one build (`c2/run.txt`). Renaming is the same code path (a name absent
from the map); I ran the addition only.

**I7, confirmed; the KNOWN tag holds.** I compiled `const volatile int V = 5;`, a `.calib` variant and
plain `const` controls with MinGW gcc 15.2 at `-O2`: `nm` prints `R` for both `const volatile` objects,
and `.calib` is `READONLY` (`i7/run.txt`). No clang compiler is installed here (only clangd and
clang-tidy; the clang directory on the PATH does not exist), so for the other toolchains I read the
repository's own images with pyelftools: `Cal_Tunable`, `const volatile uint8_t` in
`tests/fixtures/elf/src/main.c:22`, is in `.rodata` with flags `A` on `armv7m.elf` (arm-none-eabi-gcc
14.2.1), `x86_64.elf` (gcc 14.2.0) and `riscv32.elf` (clang 19.1.7), and the manifest records the same for
the other rows but PowerPC, where plain `const` and `const volatile` alike land in `.sdata`. A hosted
write through the address of such an object segfaults (exit 139). Against `README.md:426-433`,
`docs/concept.rst:345-346`, `docs/generated_artefacts.rst:466-476` ("`R` to `D`", "`A` to `WA`") and
`docs/getting_started.rst:231-234`. `SPEC.md:503-504` hedges ("should be confirmed"); the other pages do
not, and "target independent" is contradicted. The plan does leave it open
(`docs/superpowers/plans/2026-09-16-review-fixes.md:453-456`, "was not re-measured"). gcc 12.2.0 itself
was not available to me.

**I8, confirmed as to the file and the documents; the tool-side effect is unverified.** `ddd generate a2l`
of `examples/vocabulary` writes three `/begin IF_DATA XCP` blocks and no `A2ML`, no `MEMORY_SEGMENT`, no
`EPK` (`i8/run.txt`). ASAP2 1.6.1 3.5.75, read off the pass's text of the standard: the parameters of an
`IF_DATA` "have to be described in the ASAM MCD-2 MC metalanguage". `README.md:46` names "ASAP2 1.6.1";
`docs/concept.rst:236-238` says "There is nothing for a project to decide there, so there is no template
option for the a2l either". The a2l backend holds one template, `project.a2l.jinja`, and `generate a2l
--help` offers no template or fragment option. The KNOWN tag holds: the plan left the A2ML to the
maintainer, "documented as a reader obligation instead" (`2026-09-16-review-fixes.md:86-87`), and no
user page or README contains the word A2ML (a recursive grep outside `docs/superpowers`), so the
obligation it chose was never written; `docs/faq.rst:612-618` says the module-level DAQ comes from the XCP
stack's configuration without naming what a reader must merge. Whether CANape or INCA load the file as
it is cannot be settled here. Important stands on the broken "ASAP2 1.6.1" and the missing extension
point.

**I9, confirmed with a narrower effect.** The demo's a2l (from I5's run) writes `/begin MEASUREMENT
Diagnosis.faults` with `SYMBOL_LINK "Diagnosis.faults" 0`; the demo image linked here holds the symbol
`Diagnosis` and no symbol of any kind named `Diagnosis.` anything (`i9/run.txt`). ASAP2 1.6.1 3.5.123:
the first parameter is the "Name of the symbol within the corresponding linker map file", the second the
"Offset of the Symbol relative to the symbol's address in the linker map file", the description naming
arrays as the case for it. `SPEC.md:1929-1931` makes the path the `SYMBOL_LINK` symbol by design, and
`docs/faq.rst:548-551` promises that "an a2l address patcher can resolve the symbols against the linked
image itself". The correction: what fails for certain is an updater that works from a linker map, as
the standard describes; one that reads the image's debug information may well resolve a member path, and
no such tool was available. Important stands for the record that does not meet the standard's
definition and the promise made of it.

**I10, confirmed.** My own project (`i10/`): project `MODULE`, component `ROOT`, measurements `MAP` and
`IDENTICAL`, parameter `VALUE`. `ddd check --strict` is clean, and `generate a2l --strict` writes `/begin
PROJECT MODULE`, `/begin MODULE MODULE`, `/begin MEASUREMENT MAP`, `/begin MEASUREMENT IDENTICAL`, `/begin
CHARACTERISTIC VALUE` and `/begin GROUP ROOT` (`i10/run.txt`). Table 5 of ASAP2 1.6.1, the `ident` row:
"Identifiers generally must not match to the following defined ASAM MCD-2 MC keywords and enum values.
All keyword and enum values are listed in the Index of Keywords and Enum Values", and that index lists
`IDENTICAL`, `MAP`, `MODULE`, `ROOT` and `VALUE`. What a given parser does with them was not tried. `MAP`
(manifold absolute pressure) is an ordinary signal name, which is why Important stands.

**I11, confirmed with a correction.** The demo's `ddd_globals.c` linked by MinGW gcc 15.2 against a
`main` that references nothing: 20 of the a2l's 21 objects are in the image without `--gc-sections`
(`ValueG` being compiled out), none with `-Wl,--gc-sections`, with or without `-fdata-sections`
(`i11/run.txt`). `SPEC.md:1783` says "The definitions reach the image whole"; the object library
(`cmake/Ddd.cmake:720-722`) answers an archive's selective pull, not the linker's section collection. The
only page naming `--gc-sections` is `docs/developer_documentation.rst:349`, about the ELF reader. The
correction: I ran PE, not ELF; there neither `__attribute__((used))` nor `used, retain` keeps the object
(gcc says `'retain' attribute ignored`), so the remedy the pass names holds on ELF with a recent binutils
only, which the pass's own transcript shows and I did not rerun.

**I12, confirmed; the KNOWN tag holds.** The example templates copied (`i12/tpl`), with the component
header's input line spelled `extern {{ entry.variable.c_type }} {{ entry.variable.name }}{{
entry.variable.array_suffix }};` as a house style plausibly writes it, from documented fields. `ddd
generate c --const-inputs` of C1's project exits 0 and writes `extern uint16_t VSpeed;` and `extern
uint16_t Speed;` into `Cons.h`, beside `volatile uint16_t VSpeed = 100U;` in `ddd_globals.c`; a consumer
writing `Speed` compiles under `-Werror`, and a poll on `VSpeed` compiled at `-O2` loads it once and
decides with a `cmove` (`i12/run.txt`). No finding at any step, against `docs/concept.rst:87-89` ("those
four cannot disagree with each other"). The image half (a `uint32_t` definition passing as `UWORD` under
`--image`) needs an ELF build and was not rerun; the plan states that very effect as left open:
"A variable whose C type has drifted from its DDD declaration still gets its address, and only the a2l's
reader notices" (`docs/superpowers/plans/2026-10-02-addresses-from-image.md:5606`).

**I13, confirmed on the three consequences I ran; the rest of the list is read off the pass's
transcript.** (a) `Sig` produced by `VariantA` under `defined(VARIANT_A)` and by `VariantB` under
`defined(VARIANT_B)`: `multiple-producers`; relaxed to a warning, `ddd_globals.c` defines `Sig` under
`#if defined(VARIANT_A)` alone, and the `VARIANT_B` image fails to link with `undefined reference to
'Sig'`. (b) A counter a vendor library defines, read by `App`: `missing-producer`; relaxed with
`-W missing-producer=ignore`, `ddd_globals.c` still defines `volatile uint32_t LibCounter;` and the link
beside the library fails with `multiple definition of 'LibCounter'` under `-fno-common`. (c) A
structured parameter with `"init": { "kp": 5 }` is refused (`schema`, the value must be a number)
(`i13/run.txt`). Each of these is a design limit rather than a slip, and the pass grades the set as one
concept finding; Important stands for (a) and (b), where the only routes the tool leaves produce a
build that does not link.

**I14, confirmed; the KNOWN tag is dropped.** My own CMake project (`i14/`): `sensor` with `PUBLIC
RING_SIZE=4096` and `PUBLIC -fshort-enums`, `logger` registered beside it and linking nothing, one image
linking both. `logger.c` is compiled with `-DRING_SIZE=4096 ... -fshort-enums` and prints `logger ring
size 4096, sizeof(enum level) 1` where its own default is 8 and its enums are ints elsewhere
(`i14/run.txt`); nothing warns. The tag: the pass names no plan, and none of `docs/superpowers/plans/`
leaves this open; `SPEC.md:2336-2337`, `README.md:873-876` and `cmake/Ddd.cmake:738-746` state it as "the
price" of the design. A stated trade-off is not a plan's open item, so the tag goes and the grade stays
on the effect: an ABI flag reaching a library that never asked for it, in silence.

**I15, confirmed with a small correction.** A project naming `probe_plugin.py`, a valid empty plugin that
appends to a marker file when imported (`i15/`). Each verb run once with the marker cleared: `check`,
`list`, `dump`, `sources`, `artefacts`, `generate c --dry-run`, `compare` with the description on either
side, and `check --baseline` all import it; a component checked alone, a dump compared with a dump, `id
--assign` and `schema` do not; `ddd gui --no-browser PROJECT` imports it within six seconds with no
connection made, and prints only its address (`i15/run.txt`). No verb has a switch to refuse plugins.
`SPEC.md:1137-1141` states it ("Naming a plugin runs its module: on every command over the project");
the README's plugin section (`README.md:509-518`) and its editor line (`README.md:151`, other editors "need
only that command") do not. The correction: `ddd sources --help` says it prints "the module of every
plugin" and `ddd compare --help` documents `--plugin`; neither says that a project's module is executed.
The language-server part needs an LSP client and was not rerun.

**M4, confirmed; one half is the designed behaviour.** `init` 250 on a `uint8` with limits 10 to 20, and
an axis of points 40, 30, 20, 10, pass `ddd check --strict` (`minors1/run.txt`). Not comparing `init`
with the limits is `SPEC.md:462-463` by design ("physical while `init` is raw"), the pass's point being
that the physical reading is computed elsewhere; a falling axis is stated nowhere.

**M10, confirmed with a narrower trigger.** A project dumped clean, then dumped again after its producer
left (`ddd dump` exit 1 with `missing-producer`, the file written as `SPEC.md:2105-2109` says it is).
`ddd compare base.json broken.json`: `warning[changed-owner]`, "can replace", exit 0; with `--strict` the
warning is an error and the verdict is "cannot replace", exit 1 (`minors1/run.txt`). So it compares clean
by default only, and a delivery gate run under `--strict` catches it.

```verdicts
1|C1|CONFIRMED|Critical|Critical|-|reproduced on gcc 15.2: delta 0 from -Og, poll spins to its bound at -O1/-O2/-O3, no warning under the CI -Werror set; the UB is the generated declarations, gcc is entitled to it
1|C2|CONFIRMED|Critical|Critical|-|reproduced with the documented recipe: one array grown, one build under STRICT, exit 0, no finding, Arr and Out at the previous link's addresses; the clean-checkout zeros are documented, the stale case is not
1|C3|CONFIRMED|Critical|Critical|-|reproduced: insertion is info and can replace under --strict; external member swapped, removed or dimensioned is no finding; an old-header consumer reads 0 in all four; reordering (the fixed case) is an error
1|C4|CONFIRMED|Critical|Critical|-|reproduced: start page lists only b/ddd/fw/Fw.ddd.json; a created component and a hand-added include are written, check clean, and the next configure takes both entries back; correction: --target clean keeps the orphan, removing the build tree loses it
1|I1|CONFIRMED|Important|Important|-|reproduced: default headers let the consumer write its input, -Werror clean, check clean; correction: the pointer cast is caught by -Wcast-qual in the CI set, a cast through uintptr_t, ddd_globals.h and the producer header are silent
1|I2|CONFIRMED|Important|Important|-|reproduced: a shared type rescaled 0.1 to 0.01 checks clean under --strict and leaves every C file byte-identical, the a2l alone differs; concept.rst:394-396 and faq.rst:309 contradict each other as quoted; compare catches it against a baseline
1|I3|CONFIRMED|Important|Important|-|reproduced: a read measurement widened 0..100 to 0..60000 is can replace under --strict, narrowing is an error, a reader omitting limits gets no mismatch; it is SPEC.md:1668 as written, against SPEC.md:1538 and comparing_deliveries.rst:528
1|I4|CONFIRMED|Important|Important|-|reproduced: unused constant changed or removed, raster event or cycle, section access or alignment, external header: each can replace under --strict while the a2l or ddd_types.h differ; a constant dimensioning an object is caught
1|I5|CONFIRMED|Important|Important|-|reproduced on the demo without FEATURE_X: ValueG at 0x00000000 behind a comment; --strict stops and writes nothing; the only way through is address-missing=info, which then ships a really missing ValueE at 0; as SPEC.md:1923-1924, 2049-2051 design it
1|I6|CONFIRMED|Important|Important|-|reproduced: an added object under STRICT fails every build, a reconfigure does not help, deleting the map needs a configure too; same cause as C2, one probe serves both
1|I7|CONFIRMED|Important|Important|-|reproduced: const volatile stays read-only on MinGW gcc 15.2 (nm R, .calib READONLY) and in .rodata, flags A, on the fixtures of gcc 14.2, arm-none-eabi 14.2.1, clang 19.1.7; a write through its address faults; KNOWN holds (plan 2026-09-16:453-456 left it unmeasured)
1|I8|CONFIRMED|Important|Important|-|confirmed as text: 3 IF_DATA XCP and no A2ML, MEMORY_SEGMENT or EPK in the vocabulary a2l, against ASAP2 1.6.1 3.5.75; one internal template, no option; KNOWN holds but its documented reader obligation is nowhere; what a tool does is unverified
1|I9|CONFIRMED|Important|Important|-|confirmed: the demo writes SYMBOL_LINK "Diagnosis.faults" 0, the image holds Diagnosis alone, 3.5.123 defines the symbol of the linker map plus the element offset; correction: a map-based patcher fails, one reading debug information may resolve the path (unverified)
1|I10|CONFIRMED|Important|Important|-|reproduced: MAP, VALUE, IDENTICAL, ROOT, MODULE pass check --strict and reach the a2l as /begin MEASUREMENT MAP, /begin MODULE MODULE, /begin GROUP ROOT; all five are in the 1.6.1 Index of Keywords and Enum Values, which Table 5 says identifiers must not match
1|I11|CONFIRMED|Important|Important|-|reproduced on PE: the demo linked with --gc-sections against an empty main keeps 0 of 21 a2l objects (20 without it); no user page says so; correction: on PE neither used nor used,retain keeps it, retain being ELF-only
1|I12|CONFIRMED|Important|Important|-|reproduced the template half: a house-style extern drops const and volatile, generate exits 0, the -O2 poll reads VSpeed once; the image half is the plan's own left-open item (2026-10-02-addresses-from-image.md:5606), KNOWN holds
1|I13|CONFIRMED|Important|Important|-|three of the list reproduced: relaxed variant producers define Sig under VARIANT_A only and the VARIANT_B image fails to link; a vendor-defined object relaxed is still defined and the link fails; a structured parameter default is refused; the rest read off the pass transcript
1|I14|CONFIRMED|Important|Important|-|reproduced: logger, not linking sensor, compiles with -DRING_SIZE=4096 -fshort-enums and prints ring size 4096 and a 1-byte enum; KNOWN dropped: no plan leaves it open, SPEC.md:2336-2337 and README.md:873-876 state it as the price
1|I15|CONFIRMED|Important|Important|-|reproduced: check, list, dump, sources, artefacts, generate --dry-run, compare either side, check --baseline and ddd gui PROJECT before any connection import the project plugin; no switch; correction: sources and compare --help name plugins, neither says the module runs; lsp not rerun
1|M1|CONFIRMED|Minor|Minor|-|confirmed as text: "DDD is a command line tool", and the page names the language server, the gui and the toolbox nowhere (0 mentions each); line counts not rechecked
1|M2|CONFIRMED|Minor|Minor|-|confirmed as text: mentions neither c nor a2l anywhere, against _A2L_MAX_DIMENSIONS (MATRIX_DIM in ASAP2 1.6.1) and _a2l_closure in analysis.py; the module docstring and the developer page hedge, the concept page does not
1|M3|CONFIRMED|Minor|Minor|-|reproduced with my own names: clock and exp pass check --strict; exp is a -Wbuiltin-declaration-mismatch warning, a source including <time.h> and the header fails, clock redeclared as different kind of symbol
1|M4|CONFIRMED|Minor|Minor|-|reproduced: init 250 under limits 10..20 on a uint8 and an axis 40,30,20,10 pass --strict; the limits half is SPEC.md:462-463 by design, the falling axis is stated nowhere
1|M5|CONFIRMED|Minor|Minor|-|reproduced: a hand-written Gone.h put at the path the manifest recorded is removed when the component leaves, against README.md:669 and base.py:131
1|M6|CONFIRMED|Minor|Minor|-|confirmed as text: byte order is a property the descriptions cannot know and defaults to little, volatile is refused a default for the same reason; the map flow says nothing
1|M7|CONFIRMED|Minor|Minor|-|confirmed as text: from-elf writes the identity for every non-enum, the claim the FAQ says is an answer to state rather than a default to fall into
1|M8|CONFIRMED|Minor|Minor|-|reproduced: a measurement and a parameter in one read-write section check clean under --strict, then gcc: Learned causes a section type conflict with Count
1|M9|CONFIRMED|Minor|Minor|-|reproduced on I4's project: N 4 to 5 under Arr[N] reads changed-interface ... (shape: [N] != [N])
1|M10|CONFIRMED|Minor|Minor|-|reproduced without --strict only: a dump of a project failing missing-producer compares can replace with a changed-owner warning; under --strict it is an error and cannot replace
1|M11|CONFIRMED|Minor|Minor|-|reproduced: a hand-written uint32_t Speed beside DDD's uint16_t Speed = 100U links with no word under -fcommon and fails under -fno-common; no page says the guarantee needs -fno-common
1|M12|CONFIRMED|Minor|Minor|-|reproduced: a 128-character name of an array of 12 structures checks clean and reaches the a2l under --strict with first partial strings of 131 characters, against Table 5 and SPEC.md:422-425
```
