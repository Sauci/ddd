## Pass 1: is the concept sound?

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every transcript named below lies under `SCRATCH/pass-1/`. Line numbers are on the review tree.

### Scope covered

**Read in full, with line numbers:** `docs/concept.rst` (1-589); `SPEC.md` (1-2550, the whole file: the
pass names 1, 2, 3.3.1, 4, 4.1, 5, 6, and the questions reach 3.1, 3.5-3.11, 7, 7.1-7.3 too);
`README.md` (1-1058); `docs/faq.rst` (1-770); `docs/gui_security.rst`; `cmake/Ddd.cmake` (1-795);
`src/ddd/backends/c/model.py` (1-638); `src/ddd/backends/a2l/templates/project.a2l.jinja` (1-163);
the example templates `_macros`, `ddd_globals.c`, `ddd_globals.h`, `{component}.h`.

**Read in part:** `docs/build_integration.rst:560-683`; `docs/generated_artefacts.rst:325-476`;
`docs/comparing_deliveries.rst:240-304, 520-564`; `docs/plugins.rst:235-257`;
`docs/editor_integration.rst:215-235`; `docs/developer_documentation.rst:225-374`;
`docs/toolbox.rst:1-60`; `docs/acronyms.rst:160-199`; `src/ddd/backends/base.py:40-264`;
`src/ddd/compare.py:570-719`; `src/ddd/gui/contract.py:1615-1689`; `src/ddd/gui/queries.py:955-1034`;
`src/ddd/gui/api.py:2065-2139`; `src/ddd/gui/session.py:1-30`; `src/ddd/file_plans.py:1-60`;
`src/ddd/lsp/units.py:139-151`; `src/ddd/identity.py:1-60`; `tests/test_cmake.py:930-1004`;
`tests/test_compare.py:292-305`; designs `2026-09-17-web-gui` (1-360), `2026-09-22-gui-undo` (1-90),
`2026-09-23-gui-values` (1-40), `2026-09-23-gui-declarations` (1-40), `2026-09-25-gui-mismatch-fix`
(1-30), `2026-09-23-record-layouts` (1-60); "Left open" of plans `2026-09-16-review-fixes` and
`2026-10-02-addresses-from-image`. The earlier reports: `review-2026-09-15.md` (summary and the
findings on A2ML, sandboxing and the `.data` measure), `pass-1-2026-09-24.md`.

**ASAP2 1.6.1, read off the PDF (`pdf/asap2-1.6.1.txt`):** Table 5 (`ident`), 3.5.2 A2ML, 3.5.17
AXIS_DESCR, 3.5.22 BIT_MASK, 3.5.52-53 ECU_ADDRESS(_EXTENSION), 3.5.62 FNC_VALUES, 3.5.75 IF_DATA,
3.5.77 LAYOUT, 3.5.81 MATRIX_DIM, 3.5.84 MEASUREMENT, 3.5.86 MEMORY_SEGMENT, 3.5.87 MOD_COMMON,
3.5.91 NO_AXIS_PTS, 3.5.100 PROJECT_NO, 3.5.102 READ_WRITE, 3.5.103 RECORD_LAYOUT, 3.5.104
REF_CHARACTERISTIC, 3.5.112 ROOT, 3.5.123 SYMBOL_LINK, the keyword index.

**Ran:** well over a hundred runs of the real tool and of the compilers. Compilers: MinGW gcc 15.2 (no LTO in that build), and
gcc 13.3 x86-64 ELF with LTO, in the machine's WSL `Ubuntu-24.04`, which does run although Docker does
not. Placement on ARM, PowerPC, RISC-V, s390x, AArch64 and i686 is read with `readelf` off the
repository's committed fixtures (arm-none-eabi-gcc 14.2.1, gcc 14.2.0, clang 19.1.7). CMake 4.4 with
Ninja for the build flows; the GUI's api over HTTP for the collected project. `tests/test_address_fixtures.py`
and `tests/test_addresses.py` run, passing.

**Not covered:** no calibration tool is reachable, so nothing about what CANape or INCA do with a file is
established here; no clang or ARM compile of my own, only their committed images; the GUI's pages (the
api only); `src/ddd/analysis.py` and `src/ddd/backends/a2l/model.py` by search and by their output, not
read through; multi-image CMake builds by reading alone. As instructed I did not read
`coordinator-notes.md`, and I opened neither `SCRATCH/constprobe` nor `2026-11-03-kit/baseline.md`.

### Strengths

- **The dictionary really is one artefact, and the output really is reproducible.** Two copies of the demo
  in different places, and the same project as `ddd_generate` collects it (absolute includes, in a build
  directory), give byte-identical C, A2L, manifest and dictionary (`repro/transcript.txt`). `ddd compare`
  of two dumps runs no code (`trust/transcript.txt`).
- **What the C templates are handed is right.** Every datatype at both ends of its range, floats at their
  largest and smallest, a 2-D block, a scalar fill, a string with `"`, `\` and `?`, an enum: compiled with the
  CI flag set on gcc 13.3 and gcc 15.2, the stored values are those the description states, identical on
  both (`init/run.txt`, `init/out_linux.txt`).
- **The SPEC's folding story holds.** `const int K = 5` and `A[1]` read in their own unit are `movl $5` at
  `-O0`, on gcc 13.3 and 15.2 alike; `const volatile` reads survive at every level; a cross-unit `const`
  is served from one load across a call and folded under `-flto` (`c2/run_elf.txt`). SPEC.md:493-500 is
  accurate there.
- **Visibility holds as far as the concept page says it does**, and that page is honest about the rest
  (`docs/concept.rst:148-156`). A name not in the component's header is an undeclared identifier
  (`c5.txt`). A second hand-written definition is a link error under `-fno-common` (`c4.txt`).
- **The ownership checks are precise and fail closed.** Of seventeen descriptions an integrator might try,
  the sixteen the model does not take were each refused with a located finding rather than half-generated,
  and the seventeenth, a map over one axis twice, is valid (`expr/transcript.txt`).
- **The A2L records read correctly against 1.6.1.** Field order of MEASUREMENT, CHARACTERISTIC, AXIS_PTS and
  AXIS_DESCR; `COEFFS 0 1 -offset 0 0 factor`; AXIS_PTS inside REF_CHARACTERISTIC (3.5.104 allows it);
  `a.b[2].c` as an `ident` (Table 5). The reversed `MATRIX_DIM` with `ROW_DIR` agrees with 3.5.62's account of
  a cuboid (x fastest within an XY plane, z slowest), though the standard never ties its matrix notation to
  `xDim yDim zDim` in so many words. The flattening decision rests on a real measurement: CANape 15
  shows nothing for `TYPEDEF_STRUCTURE`/`INSTANCE` and refuses `1 71` (`docs/developer_documentation.rst:264-283`).
- **`--image` and `ADDRESSES_FROM_IMAGE` are the right architecture.** The a2l is a post-link step depending
  on the image (`cmake/Ddd.cmake:667-681`); offsets are held to a compiled `offsetof` oracle on five targets;
  it refuses LTO images and says why, and names a reason for each unplaced symbol.
- **The manifest's bounds hold where it matters:** artefact-scoped, a climbing path refused
  (`src/ddd/backends/base.py:178-186`).
- **The trust model is consistent:** every command over a project runs its plugins, nothing else does
  (`trust/transcript.txt`, listed in I15). A component alone cannot name a plugin, a dump runs none, and a
  description cannot name a template directory.
- **`id` fails in the safe direction:** 60 random bits from `secrets`, `duplicate-id` within a project, and a
  regenerated id is a loud `reused-name` plus `removed-object` (`cmp/transcript.txt`).
- **The GUI's file model fits the method:** no data of its own, fingerprints on every write, edits that read
  like hand edits, an undo that restores bytes and dies with the server. C4 is where it stops fitting.

### Issues

#### Critical

- **C1. `--const-inputs` miscompiles: a consumer sees a stale value of a variable its producer writes,
  silently, from `-Og` upward.** `src/ddd/backends/c/model.py:111-115, 624`, `cmake/Ddd.cmake:574-576`.
  Claims: `docs/concept.rst:193-200` ("generate exactly the code one expects"),
  `docs/generated_artefacts.rst:361-373`, `README.md:711-715`, `src/ddd/backends/c/options.py:20-23`,
  `docs/getting_started.rst:502-506`, `docs/file_formats/component.rst:243-246`.
  *Trigger* (`c1/`): `Prod` outputs a plain measurement, `Cons` declares it `input`, `ddd check` is clean, and
  `--const-inputs` writes `extern const uint16_t Speed;` beside `uint16_t Speed = 100U;`. The consumer:
  `uint16_t before = Speed; prod_step(); uint16_t after = Speed; return after - before;` (expected 7).
  *Observed*, `-std=c11 -Wall -Wextra -Wpedantic`, no warning at any level, gcc 13.3 and 15.2:

  | | `-O0` | `-Og -Os -O1 -O2 -O3` | `-O2 -flto`, `-O3 -flto` (13.3) |
  | --- | --- | --- | --- |
  | plain headers | 7 | 7 | 7 |
  | `--const-inputs` | 7 | **0** | **0** |

  `cons_delta` at `-O2` is `call prod_step; xor %eax,%eax; ret`. A cooperative wait,
  `while (Ready == 0) prod_step();`, spins until my guard stops it at `-O1 -O2 -O3` (1,000,000 iterations against
  3). An input stated `volatile` is unaffected. `c1/run.txt`, `c1/run_elf.txt`, `c1/cons_const_O2.s`.
  *Standard:* C11 6.2.7p2 (declarations of one object whose types are not compatible are undefined behaviour),
  6.7.3p10 (qualified types are compatible only if identically qualified), Annex J.2. That is undefined
  behaviour with no diagnostic required, not the "constraint violation" six
  places call it, and "a conforming compiler is entitled to reject it" is not what follows. SPEC.md:497-500 states
  the very mechanism for calibration objects ("serve two reads from one load and move that load across a call").
  SPEC.md:533-536 refuses a `volatile` disagreement because "two components disagreeing about it would compile
  different assumptions about the same address"; this option generates that disagreement.
  *Why nothing caught it:* the page "verifies the claim" by compiling and linking (`docs/generated_artefacts.rst:370-373`);
  no test runs the output. It works in a debug build and for code that reads once per activation, which is
  why it looks accepted in practice.
  *Consequence:* the one option that turns the third principle into a compiler rule is unsound.
  *Change:* (S) stop shipping const headers: `CONST_INPUTS` generates them into a separate directory and adds a
  target running `gcc -fsyntax-only` of the consumers against it. It finds the write and leaves the image's code
  defined (`c4.txt`). Or (S) make every input `extern const volatile` under the option: staleness goes,
  the undefined behaviour and the cost stay. Correct the six sentences either way.

- **C2. In the `ADDRESS_MAP` flow the a2l of any one build describes the previous link: all zeros after a clean
  checkout, stale after an edit, and no finding either way, `STRICT` included.** `cmake/Ddd.cmake:495-508,
  581-583, 646-655`, `SPEC.md:2262-2270`, `docs/build_integration.rst:663-667`.
  *Trigger:* the documented recipe, Ninja, image based at `0x10000000` (`cm1/`). (a) Clean tree, `STRICT`, one
  `cmake --build`: exit 0, `ECU_ADDRESS 0x00000000`, while the image holds `Speed` at `0x10007020`
  (`cm1/run.txt`). (b) A settled tree, one array grown in one description, one build: exit 0, no warning, `Aaa`
  in the a2l at `0x10007024` and in the image at `0x10007040`; a second build corrects it (`cm1/run4.txt`).
  *Why:* the generation runs before the link and reads the map the last link wrote. The file carries no mark of
  this, and an a2l with no addresses at all passes `--strict` (`elf1/run.txt`). The pages present the extra round as a
  first-build matter; what it does to every later build is said nowhere.
  *Consequence:* a job that builds once publishes zeros or addresses of a different image, and "a calibration
  tool reads and writes there as readily as anywhere else" (`SPEC.md:1458`), here into a neighbouring variable.
  *Change (S-M):* give the map flow the architecture `ADDRESSES_FROM_IMAGE` already has: the generation before
  the link leaves the a2l out, and `<stem>_ddd_a2l` depends on the image and the map and runs
  `generate a2l --address-map`. That also dissolves I6. Separately (S), a comment in the file when it was
  written with no address source.

- **C3. `ddd compare` calls a delivery clean whose structure layout moved: an inserted member is an `info`, and a
  changed external member is nothing at all, under `--strict` too.** `src/ddd/compare.py:682-692`,
  `SPEC.md:1555-1562`, `docs/comparing_deliveries.rst:258-264`; decision 3 of
  `docs/superpowers/plans/2026-09-16-review-fixes.md:57-59` ("A structure's layout is part of its interface").
  *Trigger:* baseline `Rec_t {speed, torque}`, candidate `{status, speed, torque}`.
  `ddd compare base.json cand/p.ddd.json --strict`: `info[added-object]`, "can replace", exit 0. A consumer compiled
  against the baseline and linked with the candidate's definitions: "producer wrote speed=1234; the delivered
  consumer reads 0" (`abi/run.txt`). An external member swapped for another external type, removed, or given a
  dimension: no finding, exit 0 (`cmp/transcript.txt`, `abi/run.txt`), although every member after it moved. The
  dictionary records those members (`types[].members`); `_compare_layouts` looks only at the names both sides
  share, in order, and the rest of the walk is over leaves, of which an external member is none.
  *Contradicts:* "A bitfield's width and the order of the members are the layout a released structure fixed for its
  consumers ... widening one moves every member after it" (`SPEC.md:1555-1557`). An insertion moves exactly the same
  addresses. "A change **shall** be graded by what it costs the consumers" (`SPEC.md:1538`).
  *Scope:* a consumer rebuilt from the new header is unharmed; a component delivered as a library is what the
  first paragraph of the README describes. See open question 1.
  *Change (S):* compare the member list of a structure both sides declare, positionally, external members with
  their type and shape included; any difference ahead of a shared member is `changed-interface`.

- **C4. Over a project CMake collected, `ddd gui` writes a new description into the build tree and adds it to a
  generated file; the next configure takes the entry back and a clean build loses the file.**
  `src/ddd/lsp/units.py:139-150`, `src/ddd/file_plans.py:348`, `src/ddd/lsp/units.py:337`, `src/ddd/shared_plans.py:557`,
  `src/ddd/gui/session.py:243-251`, `cmake/Ddd.cmake:343-353`.
  *Trigger* (`guicollect/`): a two-component collected project, `ddd gui b/ddd/fw/Fw.ddd.json` (the entry the start
  page lists from the build record; there is no other in this mode). `GET /api/files-plan?action=create&kind=component&...`
  plans `b/ddd/fw/newcomp.ddd.json` and an entry in `b/ddd/fw/Fw.ddd.json`; `POST /api/edit` answers 200 and
  `ddd check` is clean. The next `cmake` run rewrites the project through `file(GENERATE)`: includes back to the
  link closure, `newcomp.ddd.json` an orphan under `build/`, gone with the next clean (`guicollect/transcript2.txt`). An
  include added by hand through the api goes the same way (`guicollect/transcript.txt`). No finding, no refusal, no sentence in
  the plan. `adopt_units` and the shared plans create through the same `created_beside`.
  *Contradicts, by construction:* the GUI's model, "the description files are the project"
  (`src/ddd/gui/session.py:3`), against "which components belong together is a property of the build rather than
  of any authored file" (`SPEC.md:780-781`). Collected is the default mode of the module.
  *Change (S):* know a generated project (a key `ddd_generate` writes, or the `image` of the build record naming a
  path under the record's directory) and refuse every plan that would touch it, saying that membership is
  `ddd_add_component`'s; offer a new description only beside an existing source file, with the CMake line to add.

#### Important

- **I1. The headline promise is false by default: a component that declares `input` and writes the variable
  compiles, links and passes every check, which is the second writer the concept says it removes.**
  `README.md:10-11` ("so that nobody can write a variable that belongs to somebody else"), `docs/concept.rst:99-100,
  135-137` ("optionally, the only path that compiles at all"), `SPEC.md:1742`.
  *Trigger:* `#include "Cons.h"`, `Speed = 1;` under the default headers: compile exit 0 (`c4.txt`), `ddd check`
  clean. Under `--const-inputs`, direct assignment is an error (C11 6.5.16p2, a real constraint), but
  `memset(Arr, 0, sizeof Arr)` compiles with a warning, `*(uint16_t *)&Speed = 3` without one, and
  `#include "ddd_globals.h"` hands over a writable declaration of everything (`misc/run.txt`). The headers sit in one
  include directory, as README.md:707-711 and the concept page admit.
  *Consequence:* `multiple-producers` polices what components *say*. The default mode has no compile-time rule, and
  the optional one is C1.
  *Change:* reword the README (S). For real enforcement with no undefined behaviour (M): per-component include
  directories, since the module can read `component.name` off the file it registers, with `ddd_globals.h` in a
  directory only `<stem>_ddd_globals` sees; then `#include "UserInterface.h"` fails to compile. Plus C1's lint.

- **I2. Drift is detected between descriptions, never between a description and code, and declared types remove even
  that: the concept's own failure still passes `ddd check` with byte-identical headers.**
  `docs/concept.rst:29-37, 87-91, 392-396`, `docs/faq.rst:288-309`, `README.md:472-476`, `SPEC.md:551-555`,
  `src/ddd/backends/c/model.py:41-90`.
  *Trigger:* `ValueF` named `Temp_t` by producer and consumer; change the type's factor from 0.1 to 0.01 (the story of
  concept.rst:29-33). `ddd check`: ok. `Cons.h`, `Prod.h`, `ddd_globals.c/.h`, `ddd_types.h`: identical, so no consumer
  even recompiles; only the a2l differs (`misc/run.txt`).
  *The documents disagree with each other.* concept.rst:394-396: redundancy "is precisely what allows DDD to notice
  that the two sides have drifted apart, which a single shared declaration could never do". faq.rst:309 and
  README.md:474 recommend the single shared declaration: "there is nothing left for them to disagree about".
  concept.rst:87-91: "the only place the information is written down ... one edit in one file". With restated
  definitions it is one edit per declaring file; with a type it is one edit nobody downstream has to see. No page says
  the choice trades detection away.
  *Restating is weaker than it reads.* The check compares JSON. The C that multiplies by 0.1 is hand-written, and the
  generated code cannot help it: `ObjectView` offers a template no unit, conversion or limits, only a comment carrying
  the unit (`src/ddd/backends/c/literals.py:166-180`), so a project cannot generate `#define ValueF_FACTOR` without writing a plugin backend.
  And the fix is one click: the quick fix and the GUI's settle reconcile "in either direction" (`SPEC.md:2358-2360`,
  `README.md:200-210`), the producer's author can push the new value into every consumer's file, and "a reader added
  this way agrees with its producer by construction" (`docs/superpowers/specs/2026-09-23-gui-declarations-design.md:18-21`). The check goes green with
  the code untouched and no preview says so. `ddd compare` does catch the rescale, if a baseline was archived.
  *Change:* say in the concept page what is and is not detected, and when to name a type (S); offer `unit`, `conversion`
  and `limits` on `ObjectView`, with scale macros in the example templates, so a rescale reaches the consumer's
  header and its rebuild (S); say in each reconcile preview that the consumers' code is not touched (S). See open question 3.

- **I3. Limits are graded in the wrong direction for a measurement: widening, which is what can break a consumer, is
  silent even under `--strict`.** `SPEC.md:1668`, `docs/comparing_deliveries.rst:525-529` ("there is nothing a consumer or a
  calibration dataset can trip over"), `src/ddd/compare.py:981`, `tests/test_compare.py:292-296`.
  *Trigger:* measurement `Speed` read by a consumer, limits `[0, 100]` to `[0, 60000]`: `exit=0`, no finding. Narrowing it:
  `narrowed-limits` warning (`cmp/transcript.txt`). "Every value the baseline allowed still fits" is the argument for data
  flowing *into* the software. A measurement's limits are the producer's promise to its readers: a table
  indexed by that value, or a saturating step sized for it, is what a wider range breaks. A consumer that left limits out,
  as faq.rst:238-243 recommends, gets no `definition-mismatch` either, so neither question ever mentions it.
  *Change (S):* grade by direction of flow: on a measurement with readers widening is a warning and narrowing is at most
  an `info`; calibration data stays as it is.

- **I4. The comparison compares objects, not the vocabularies they reach the outputs through: constants, raster event
  numbers, section properties and external headers change in silence.** `src/ddd/compare.py:598-603`, `SPEC.md:1018-1020, 1596-1600`.
  *Trigger*, each `exit=0` with no finding (`cmp/transcript.txt`): constant `GAIN` 2 to 3, or removed, though SPEC 3.9 says "a gain, an
  offset or a count of zero belongs here" and every constant reaches the C and the `SYSTEM_CONSTANT`; raster `10ms` renumbered
  from event 1 to 7, or its cycle changed, though every `IF_DATA` in the a2l changes and `changed-storage` says the raster is "which event
  a measuring tool receives the value in"; a section's `access` or `alignment`; an external type's `header`. All but the
  sections are in the dictionary already.
  *Change (S; M for sections, which the dictionary does not carry):* compare `constants` and `rasters` as entries and external
  types by header. A changed constant is `changed-interface`, a changed event `changed-storage`.

- **I5. A conditional object compiled out still reaches the a2l, at address 0, and a project with one cannot use `STRICT`.**
  `SPEC.md:1923-1924, 2049-2057`, `docs/build_integration.rst:595-606`, `src/ddd/backends/a2l/templates/project.a2l.jinja:60-62`.
  *Trigger:* the demo built without `FEATURE_X`: `MEASUREMENT ValueG ... ECU_ADDRESS 0x00000000`, with a comment as the only
  mark; `--strict` stops the run, so `STRICT` is reachable only with `address-missing` lowered, which hides real holes too
  (`elf1/run.txt`). The suite's own test of the recipe has to lower it, for this reason (`tests/test_cmake.py:940-944`).
  DDD has no way of being told a condition's truth, and with `--image` it can see that the variable is absent.
  *Contradicts:* the single-file rationale's evil, "the A2L is left describing storage the image does not contain"
  (`SPEC.md:1788-1789`), and faq.rst:684-685.
  *Change (S):* an object with a `condition` that the image or a non-empty map does not place is left out of the a2l and
  reported at `info`; an unconditional one stays `address-missing`.

- **I6. `STRICT` with the documented `ADDRESS_MAP` recipe: adding or renaming any object stops the build for good.**
  `cmake/Ddd.cmake:581-583`, `SPEC.md:2267-2270`.
  *Trigger:* a settled build, one new measurement in a description: the pre-link generation reads the old map, reports
  `error[address-missing]` for it and writes nothing; nothing compiles or links, so the map never changes. Three builds in a row
  fail the same way (`cm1/run2.txt`). A reconfigure alone does not help, deleting the map alone leaves ninja with a missing input;
  deleting it and configuring does (`cm1/run5.txt`). "So that first build passes under `STRICT` as well" covers the first build
  alone. *Change:* C2's.

- **I7. "`const volatile` leaves `.rodata` for `.data`" is false on every current toolchain reachable here, and the cost
  model built on it misleads.** `README.md:426-436` ("The categorisation is target independent"), `SPEC.md:500-505`,
  `docs/concept.rst:344-349`, `docs/generated_artefacts.rst:467-476`, `docs/getting_started.rst:231-234`. KNOWN in part: "was not
  re-measured" (`2026-09-16-review-fixes.md:453-456`).
  *Evidence:* gcc 13.3 ELF and gcc 15.2 MinGW: `nm` says `R` for `const volatile int V`, and a `.calib` holding one has flags `A`
  (`c2/run_elf.txt`). The repository's own images: `Cal_Tunable`, `Gain` and `Tuning` in `.rodata` on armv7m (14.2.1), x86_64,
  s390x, aarch64, i686 and riscv32 (clang 19), and `.sdata` for the small ones on powerpc (`c2/fixtures.txt`). Only the page's gcc
  12.2.0 is left, unverifiable here, and "target independent" is contradicted by that same set.
  *Consequence:* `volatile: true` does not move a value to RAM. A project reasoning from the page expects a RAM address and a startup
  copy, and gets a flash address a tool cannot write without an overlay; on a hosted build a write through the address of a `const volatile`
  object is a segmentation fault where the page's account has it in `.data` (`c6.txt`). SPEC's hedge ("should be confirmed") does not reach the other pages.
  *Change (S):* re-measure from the fixture manifest, say what is version dependent, and pin it with a test on those images.

- **I8. The a2l has no extension point, so "there is nothing for a project to decide there" is false, and a file with
  rasters does not meet the standard the README names.** `docs/concept.rst:234-238, 504`, `README.md:46`, `docs/faq.rst:612-618`,
  `src/ddd/backends/a2l/templates/project.a2l.jinja:84-92`, `SPEC.md:1946-1948`. KNOWN: P10-M13, left as "documented as a
  reader obligation", which did not happen: no page names the A2ML.
  *Evidence:* `examples/vocabulary` writes 3 `IF_DATA XCP` and 0 `A2ML` (`misc2.txt`), and 3.5.75 requires the metalanguage to describe
  what an `IF_DATA` holds. The file also cannot state what a tool needs to connect or to trust it: the module's `IF_DATA
  XCP`, `MEMORY_SEGMENT`, `EPK`/`ADDR_EPK` (no tool can tell that this a2l belongs to this image), `ECU_ADDRESS_EXTENSION`,
  `READ_WRITE`, `BIT_MASK`. A plugin cannot amend it (`record-layouts-design`: "A plugin cannot amend the a2l") and a2l import
  is *planned*. So the arrow `final_a2l --> mc_tool: measure and calibrate` needs a merging script, the very thing the fourth
  principle says a generator should not force. `point_counts` is the proof: one project needed its a2l to differ, and it took a
  feature in the tool. I found no record that a generated file has ever been loaded in CANape or INCA; the CANape result above
  used hand-written files.
  *Change (M):* a project-provided fragment pasted verbatim into the `MODULE` (`--a2l-module-fragment`, `A2L_MODULE_FRAGMENT`),
  the way the C templates hand the same decision to the project. Name the A2ML on the pages now (S).

- **I9. `SYMBOL_LINK` on a member names no linker symbol, so the patcher route the documents promise cannot work for structured
  objects.** `src/ddd/backends/a2l/templates/project.a2l.jinja:66, 102, 118`, `SPEC.md:1929-1931`, `docs/concept.rst:456-458`,
  `docs/faq.rst:548-551`, `README.md:755`.
  *Evidence:* `SYMBOL_LINK "Inlet.latest.value" 0` (`misc2.txt`). ASAP2 1.6.1 3.5.123: "Name of the symbol within the corresponding linker map file",
  with the offset of the element from that symbol as the second parameter. The map holds `Inlet`, not the path. A map
  stating `Inlet` itself counts as "the a2l does not carry" it (`misc2.txt`, section h), and `--strict` then stops.
  *Change (S):* with `--image`, write `SYMBOL_LINK "Inlet" <offset>`; before the link, say on the pages that the record names a path no
  map can answer. Whether a real updater accepts the path spelling is unverified.

- **I10. Names the a2l format forbids pass every check.** `SPEC.md:1393-1403`, `src/ddd/models/reserved.py:67`; a note of Table 5 keeps
  identifiers off the keywords and enum values the standard's index lists, and `MAP`, `VALUE`, `IDENTICAL`, `ROOT` and `MODULE` are all in that index.
  *Trigger:* a measurement `MAP` (manifold absolute pressure), a parameter `VALUE`, a measurement `IDENTICAL`, component `ROOT`,
  project `MODULE`: `ddd check` ok; the file holds `/begin MEASUREMENT MAP`, `/begin GROUP ROOT "ROOT"`, `/begin MODULE MODULE`
  (`misc/run.txt`). What a parser does is unverified; `docs/developer_documentation.rst:278-280` records CANape silently dropping what
  it cannot resolve and says "the burden of catching it sits here".
  *Change (S):* check names reaching the a2l against the standard's index of keywords.

- **I11. "The definitions reach the image whole" is not true under `--gc-sections`, the usual embedded link.** `SPEC.md:1783-1789`,
  `cmake/Ddd.cmake:720-722`, `examples/templates/ddd_globals.c.jinja2:2-6`.
  *Trigger:* the demo linked with `-Wl,--gc-sections`, with or without `-fdata-sections`, against a `main` referencing nothing: 21 of the
  a2l's objects gone, all at address 0 in it, a warning at least (`elf1/run.txt`). The object the design is argued from, "a measurement only
  the calibration tool reads", is the one dropped, and no user page says so. `__attribute__((used))` does not keep it; `used, retain` does,
  on gcc 13.3 with binutils 2.42 (`c5.txt`).
  *Change (S):* say so in 5.1 and on the template page, and give the example templates a macro a project sets.

- **I12. Nothing holds the rendered C or the linked image to the description, so "those four cannot disagree" is true only of the shipped
  templates.** `docs/concept.rst:87-89, 226-229`, `SPEC.md:2015, 2059-2060`. KNOWN: "Comparing each linked variable's type with its declaration",
  `2026-10-02-addresses-from-image.md:5606`.
  *Trigger:* a project template dropping `{{ variable.qualifier }}` and printing its own `extern`: `generate --const-inputs` exit 0, `Cons.h` non-const,
  `VSpeed` no longer volatile (`misc/run.txt`). `ValueE` defined `uint32_t` while the a2l says `UWORD`: `--image` places it with no finding (`elf1/run.txt`).
  *Consequence:* the third principle ("carried by what comes out of the generator") and the fourth (the project writes the generator's output) meet here and
  neither side verifies. `docker/verify_symbols.py` checks names, on a docker path a project may not take.
  *Change (M):* the second run already has the DWARF in hand: compare size, encoding, qualifiers and shape there. It is the most valuable next feature
  of the method, since it closes the loop for every template and every hand edit.

- **I13. A real integrator cannot express several ordinary things, and some of them force a lie.** `SPEC.md:108-113, 584-587, 921, 927-931`; refusals in `expr/transcript.txt`.
  - *An object DDD does not define.* "Shall be defined and declared by code DDD renders" (SPEC 1.4), yet SPEC.md:586-587 argues from "a value out of a library it does not own".
    No scope says so: the choices are a fake owner component, which defines it a second time, or `missing-producer=ignore` plus a template skipping `<unresolved>`.
  - *Software-written calibration data* (a learned value, a RAM mirror): `kind` fixes `const`. It must be stated a `measurement`, which is then read-only to the tool, or a `parameter`, which the software cannot write.
  - *Two writers by design* (handshake, boot then application): `multiple-producers`. The natural way out is declaring `input` and writing anyway, the one lie the tool cannot see (I1).
  - *Ownership or type per variant:* two producers under exclusive conditions are `multiple-producers`, and relaxed, only the first's condition reaches `ddd_globals.c`, so the other variant fails to link (`expr/transcript.txt`). A variant has to be a project.
  - *A structured parameter's values:* no `init` and no array of them (`type-kind`, `schema`). `const Cfg_t Cfg;` is all zeros in flash with no way to state a default (and in `.bss` under `-fcommon`, `c2/run_elf.txt`).
  - *A top-level global of an external type* (an OS handle), a pointer, `_Atomic`: refused. SPEC.md:365-366 says a second core "needs" `volatile`; it does not give atomicity or ordering (C11 5.1.2.4p25), and nothing else can be stated.
  - *An axis indexed by a structure member or an array element;* a curve carrying its own axis; a measurement writable from the tool, though SPEC.md:163 and README.md:371-373 say a tool may write one while `docs/acronyms.rst:176-178` admits the a2l says otherwise.
  - *Two instances of one component, or two suppliers' locals of one name:* `duplicate-component`, `local-conflict`: there is no namespace, and `local` still has external linkage.
  *Change:* the first is the one to do (M): a scope or key for an object the project describes and does not define, carried to the a2l and left out of the definitions. It also serves migration, which `from-elf` opens. The others are decisions, see open question 4.

- **I14. One component's public flags silently reach every other component, a consequence of the project-wide `ddd_types.h`.** `cmake/Ddd.cmake:707-718, 738-746`, `SPEC.md:2334-2337`, `README.md:873-876`. KNOWN: stated as "the price".
  *Trigger* (`cm2/`): `sensor` has `PUBLIC RING_SIZE=4096` and `PUBLIC -fshort-enums`; `logger` does not link it. `logger.c` compiles with both, and prints "logger ring size 4096" instead of its own 8 (`cm2/run.txt`). An ABI flag on an unrelated library, no warning.
  *Also:* "nothing else is visible" (`README.md:676`) and "containing the declarations of that component and nothing else" (`docs/concept.rst:139-140`) exclude every enum, constant, structure and external header of the project, and one edited enum rebuilds everything.
  *Change (M):* a types header per component holding the closure of what its declarations name; the analysis knows it. The flags then need to travel only along real uses, and the union can go.

- **I15. Read-only verbs run a repository's python, the concept's own use case runs it unreviewed, and no switch prevents it.** `SPEC.md:1137-1141`, `README.md:151, 509-518`, `docs/concept.rst:17-21`.
  *Evidence* (`trust/transcript.txt`): plugin imported by `check`, `list`, `dump`, `sources`, `artefacts`, `generate` (`--dry-run` too), `compare` with a description on either side, `check --baseline`, `ddd lsp` on opening a component beside the project, and `ddd gui PROJECT` before any browser connects. Not by a component checked alone, a dump, `id --assign`, `build-info`, `schema`.
  *Consistent and documented (SPEC 3.11, 7.2, plugins.rst:245-251, editor_integration.rst:215-225, the extension's README, gui_security.rst:126-130). But* a reader meets it only there: not in the README's plugin section or its quick start, where README.md:151 says other editors "need only that command"; not in any `--help`; not on `ddd gui`'s terminal. The concept's opening scenario is "an artefact an integrator can check before the first build": a supplier's sub-project may name plugins (`SPEC.md:1134`), so that check runs the supplier's code. The gate exists in one editor extension; `ddd lsp` has none.
  *Change (S):* one sentence in the README and on `check --help`; `--no-plugins` on `check`, `list`, `dump`, `sources` and `compare`, reporting that a named plugin did not run, and a `ddd lsp --no-plugins` other editors can default to.

#### Minor

- **M1. The concept page describes a generator; the repository is now mostly an editor.** `docs/concept.rst:402` "DDD is a command line tool"; no mention of the language server, the GUI or the toolbox. By line count: core and backends about 16,700 lines of python, editor stack about 39,800 (`lsp` 4,952, `gui` 8,580, edit and plan modules 6,464, the page 19,800 beside about 12,000 lines of its stories and tests). The rules it follows ("the files are the project", "preview every write") are good and written only in design records. Add them as a principle (S).
- **M2. "Mentions neither c nor a2l anywhere" is not what the front end does.** `docs/concept.rst:529-531`, `src/ddd/analysis.py:4` against `:81-82` (`_A2L_MAX_DIMENSIONS`), `:915` (`_a2l_closure`), `src/ddd/models/reserved.py`, the a2l block in the models. The guard tests spellings such as `UWORD`, not knowledge. Reword (S).
- **M3. `reserved-identifier` leaves out C11 7.1.3p1's third family, library names of external linkage.** `SPEC.md:1393-1403`. Objects `time`, `log`, `signal` pass `--strict`; `log` is a `-Wbuiltin-declaration-mismatch` warning, and a component including `<time.h>` gets `'time' redeclared as different kind of symbol` (`misc2.txt`).
- **M4. An `init` outside the object's limits, and an axis whose points do not rise, pass `--strict`.** `SPEC.md:462-463`. `init` 60000 under limits 0..100; axis `[5, 1, 1]` (`misc2.txt`). The stated reason, raw against physical, does not hold: `ddd list` and the hover already compute the physical reading.
- **M5. "Only what this tool wrote is ever removed" is not what the manifest can know.** `src/ddd/backends/base.py:131-133, 175-187`, `README.md:668-669`. A component dropped and a hand-written `Gone.h` put at the recorded path: `removed mf/out/Gone.h` (`misc/run.txt`). Record a hash (S).
- **M6. `--byte-order` defaults where `volatile` refuses to.** `SPEC.md:1883-1886` against `SPEC.md:363-368` ("asks instead of choosing one silently"). In the map flow a big-endian target that forgets it gets `MSB_LAST` with no finding; `--image` is safe.
- **M7. `from-elf` writes the claim the FAQ says must not be defaulted into.** `SPEC.md:2505-2507` against `docs/faq.rst:271-276`: every non-enum becomes `{"kind": "identity"}`, an `info` says so once, and once pasted nothing marks it unverified. Omit it, so `schema` asks the author, or take a flag.
- **M8. A clean check, then a compile error in a generated file: a measurement and a parameter in one `read-write` section.** `SPEC.md:752-754`. `'Count' causes a section type conflict with 'Learned'`, on both compilers (`c3/run.txt`). The template owns the spelling, so `section-access` could note it.
- **M9. `changed-interface 'Arr' ... (shape: [N] != [N])`.** `src/ddd/compare.py:410`: a constant's value changed and the message shows two equal spellings (`cmp/transcript.txt`). Show the numbers.
- **M10. A dictionary dumped from a failing project compares clean.** `SPEC.md:2105-2109`. `ddd dump` exit 1, then `ddd compare base.json broken.json`: `warning[changed-owner] ... produced by nobody`, "can replace" (`abi/run.txt`). An object with readers and no producer deserves an error whatever else; a dump could also record that its analysis failed.
- **M11. The one-definition guarantee rests on `-fno-common`, and no page says so.** A hand-written `uint32_t Speed;` beside DDD's `uint16_t Speed = 100U;` links under `-fcommon`, the default before gcc 10, with an alignment warning at most (`c4.txt`).
- **M12. A 128 character name, as an array of structures, overruns the bound SPEC cites.** `SPEC.md:422-425`; Table 5 counts an array index within the partial string's 128 characters. `generate` exit 0, first partial string 131 characters (`longname.txt`).

### Status of the 2026-09-15 findings in this area

Listed only where not plainly fixed. The pass has no predecessor of its own; these are the concept-level ones.

| finding | status | where |
| --- | --- | --- |
| P9-I2, a structure's layout outside the comparison | PARTLY: order and bit width fixed (`compare.py:662-700`, reproduced); insertion and external members still silent | C3 |
| P10-M13, `IF_DATA XCP` with no A2ML | STILL OPEN: plan says "documented as a reader obligation" (`2026-09-16-review-fixes.md:87`), and no page names the A2ML | I8 |
| SD-M1, the `.rodata` / `.data` numbers | The page was dated rather than re-measured (left open in the plan); the claim is now contradicted | I7 |
| Open question 11, the server refusing plugins without a trusted workspace | Settled by the extension's gate; `ddd lsp` itself has none | I15 |

### Open questions

1. **Which consumer does `ddd compare` protect, one that is rebuilt or one that is not?** The documents use both: "every consumer is regenerated and recompiled against it, so nobody is left wrong" (`docs/comparing_deliveries.rst:291-292`, for `volatile`) and "the layout a released structure fixed for its consumers" (`SPEC.md:1555`, for member order). *Not rebuilt:* C3 stands, and `volatile` false to true is also an error, since a delivered reader caches. *Rebuilt:* reordering stops being an error and C3 drops to Minor, while I3 and I4 stay. I would answer "not rebuilt": the README opens on other companies' components, and it is the safe grade.
2. **Does `--const-inputs` stay?** Lint-only (C1's first change) keeps the benefit with none of the risk. Keeping it as is needs at least `const volatile` on every input and a loud note in the option's help.
3. **What is a consumer's restatement, the interface or a copy?** Today a consumer must restate everything (`volatile`, `kind`, `conversion`), then a tool copies it for them, while a type removes it. The rule `limits` already follows could be the whole model: *a consumer states what its code relies on; what it states is compared; what it omits defers.* That keeps detection exactly where an assumption exists, shrinks the files of a 15,000 object project and much of what the editor stack exists to keep in step, and gives declared types an honest role. A format change (L), worth deciding before 1.0.
4. **Which of I13 does DDD want to express?** My order: externally defined objects; `init` on a structured parameter; writable calibration storage, `READ_WRITE` with it; the rest only on request. Variants as images is a fair answer if it is written down.
5. **The a2l: a fragment hook (I8), or a full model of `MEMORY_SEGMENT`, `EPK` and the XCP module block?** I would take the hook and refuse the model.
6. **Float-typed point counts** (KNOWN, `2026-09-23-record-layouts-design.md:40-42`). `NO_AXIS_PTS_X FLOAT32_IEEE` is grammatical, but no request needed it and no tool has been shown reading it. Refusing it until one has is safer than keeping it open.
7. **Can somebody load one generated a2l in CANape and in INCA?** An hour's work that settles I8, I9, I10 and the `MATRIX_DIM` reading, and belongs on the release checklist.

### Test gaps

- Nothing runs generated code. `tests/test_generation.py:233-245` asserts the text `extern const uint8_t X;`; `compile-const` compiles and links. A test that builds at `-O2`, runs a read around a call and compares is what C1 needed.
- `tests/test_compare.py:292-296` pins widening as silent on a measurement (`declare` defaults to one, `tests/conftest.py:47-52`), so it holds I3 in place. By grep, no test inserts a member or changes an external member, a constant no shape names, a raster's event number or a section's properties between two deliveries.
- `tests/test_cmake.py:985-1004` asserts that three builds settle, with `address-missing=info` beside `STRICT`. No test compares the a2l with the image after one build, after an edit, or adds an object under `STRICT`.
- No GUI test opens a collected project (by grep over `tests/test_gui_*.py`).
- The a2l is tested by substring. No test parses it against a grammar or checks its names against the keyword index, and no tool has read one.
- The `.rodata` claim has a ready oracle in `tests/fixtures/elf/manifest.json` and no test reading it.

### Assessment

#### Verdict by principle

| principle | verdict | why |
| --- | --- | --- |
| Every component declares its data interface explicitly | holds with a caveat | The description is explicit and strictly checked. But it is compared with descriptions only, "the only place ... one edit in one file" contradicts the restatement, and several ordinary interfaces cannot be stated (I2, I13) |
| Exactly one component owns each variable | holds with a caveat | True and well reported for what components declare, and resolution is sound. A component declaring `input` that writes anyway is invisible by default (I1) |
| Access rules are enforced by what is generated | does not hold as stated | The visibility half holds for a component that includes only its own header. The rest is an include directory and a comment, the one enforcing option is unsound (C1), and a template can drop the rule unverified (I12) |
| DDD owns the data, the project owns the presentation | holds for the C, does not hold for the a2l | Templates work as promised and render strictly, though they are not offered the unit, conversion or limits (I2). "Nothing for a project to decide" in the a2l is false (I8) |
| Everything passes through the dictionary (unnumbered) | holds | Single artefact, published, reproducible. The front end does know two facts about the outputs (M2) |

#### The pass's questions

- **Premises:** global variables as the interface and one file per component hold together. Restating against sharing does not: the documents argue both and name no cost (I2). An integrator cannot state I13's list.
- **The C, under C11 and real compilers:** visibility, `const` and folding, `volatile` reads, initialisers and conditions in the C hold. `--const-inputs` does not (C1). Placement is misdescribed (I7). Sections conflict at compile time (M8). One definition rests on `-fno-common` (M11).
- **The a2l:** the records read as 1.6.1 and flattening is justified. Addresses are the weak point (C2, I5, I6), `SYMBOL_LINK` on members is not what the standard defines (I9), `IF_DATA` has no A2ML and no way to get one (I8), and reserved names pass (I10). Never shown to load in a tool.
- **`check` and `compare`:** the two questions are the right ones. `check` is sound on descriptions. `compare` is not sound on layout, limits or vocabularies (C3, I3, I4) and has no stated cost model (question 1). `id` is a sound basis for what it claims, declaration continuity: it stays on a repurposed declaration and reports a rename (`id_kept_on_a_different_object_same_shape`), so `--renames` would migrate data onto a new meaning; say that in the page.
- **Image and project:** one dictionary per image and refusing the ambiguous second `ddd_generate` are sound. Link-graph collection works, at the cost of I14; a library in the closure whose object the linker never pulled is still described, its measurement simply never written. Reproducibility holds. The manifest holds, M5 aside.
- **Trust:** consistent everywhere, stated where a plugin author looks and not where a reader of a delivery looks (I15).
- **One concept?** The comparator follows from ownership, and `from-elf` from the migration a generator needs (M7 aside). The editor follows from the files being the artefact and fits, except that it treats a build's generated file as authored (C4) and makes agreement mechanical (I2). The principles have not kept up (M1).
- **What the design makes hard:** variants beyond text conditions, instances of a component, namespaces, objects shared across images, objects defined elsewhere, non-const calibration storage, an a2l with anything DDD did not generate.
- **What DDD should refuse to become:** a calibration tool (it holds defaults; datasets, hex and connection stay out, and the GUI's grid should keep saying "initial values"); an a2l editor beyond a verbatim fragment; a C parser (ask the image, not the source); a hosted or multi-user service; a runtime or RTE; and a tool that rewrites another team's file without saying that their code was not looked at.

The method is sound at its core and overclaims at its edges: declaring interfaces as data, resolving one owner, generating one dictionary and rendering everything from it is a good idea well executed, and on what it checks (descriptions against descriptions) it is rigorous and reproducible. What is wrong is the boundary with the real world, which the documents describe more confidently than the tool delivers it. The only compile-time enforcement miscompiles (C1), the map flow ships addresses of the wrong image (C2), the delivery verdict misses the most common structural change (C3), and the GUI loses work in the build's default mode (C4). Each has a small fix and none needs the concept changed, and a suite of 100 % coverage catches none of them, because nothing in it runs the C it generates, compares an a2l with its image, or opens the GUI on a collected project. The structural decision worth taking before 1.0 is whether a consumer restates, shares or pins (question 3), and the most valuable next feature is holding the linked image to the description (I12), which turns "cannot disagree" from a claim about the generator into a fact about the build.

```candidates
1|C1|src/ddd/backends/c/model.py:114|--const-inputs is undefined behaviour gcc miscompiles: a consumer reads a stale value at -Og and above, no diagnostic
1|C2|cmake/Ddd.cmake:582|ADDRESS_MAP flow: the a2l of one build holds zeros or the previous link's addresses, no finding even under STRICT
1|C3|src/ddd/compare.py:690|compare passes a moved structure layout as clean: inserted member is info, changed external member is nothing
1|C4|src/ddd/lsp/units.py:139|ddd gui over a collected project writes descriptions into the build tree and a generated file; the next configure drops them
1|I1|README.md:10|Nobody can write a foreign variable is false by default: a component writing its input compiles, links and checks clean
1|I2|docs/concept.rst:90|Silent drift stays: declared type rescale passes check with identical headers, templates get no scale, reconcile is one click
1|I3|SPEC.md:1668|Limits graded backwards for a measurement: widening is silent under --strict, and it is what breaks a reader
1|I4|src/ddd/compare.py:598|compare ignores vocabularies: constants, raster event numbers, section properties and external headers change in silence
1|I5|SPEC.md:1923|A compiled-out conditional object reaches the a2l at address 0, and a project with one cannot use STRICT
1|I6|SPEC.md:2269|STRICT with the ADDRESS_MAP recipe: adding or renaming an object stops the build for good
1|I7|README.md:432|const volatile leaves .rodata for .data is false on gcc 13, 14, 15 and clang 19, including the repository's own images
1|I8|src/ddd/backends/a2l/templates/project.a2l.jinja:85|The a2l has no extension point: IF_DATA without A2ML, no MEMORY_SEGMENT, EPK or module XCP, and nothing for a project to decide is false
1|I9|src/ddd/backends/a2l/templates/project.a2l.jinja:66|SYMBOL_LINK on a member names no linker symbol, so the promised patcher route fails for structured objects
1|I10|SPEC.md:1393|Names the a2l format forbids (MAP, VALUE, ROOT, MODULE) pass every check
1|I11|SPEC.md:1783|The definitions reach the image whole is false under --gc-sections; tool-only objects are dropped and templates do not retain them
1|I12|SPEC.md:2015|Nothing holds rendered C or the linked image to the description: a template can drop qualifiers, a uint32 passes as UWORD (KNOWN)
1|I13|SPEC.md:108|The model cannot express objects defined elsewhere, writable calibration data, designed second writers, structured parameter values and more
1|I14|cmake/Ddd.cmake:710|One component's public flags silently reach every component through the project-wide types header (KNOWN)
1|I15|README.md:509|Read-only verbs run a repository's python with no opt-out, and the README, --help and the gui terminal do not say so
1|M1|docs/concept.rst:402|The concept page never mentions the editor stack, now more than twice the size of the core
1|M2|docs/concept.rst:530|The front end mentions neither c nor a2l is false: analysis.py knows MATRIX_DIM's limit and the a2l closure
1|M3|SPEC.md:1393|reserved-identifier omits C11 7.1.3p1 library names: objects time, log, signal pass --strict
1|M4|SPEC.md:462|An init outside the limits and a non-rising axis pass --strict
1|M5|src/ddd/backends/base.py:181|The manifest removes a hand-written file at a recorded path, against only what this tool wrote is ever removed
1|M6|SPEC.md:1884|--byte-order defaults to little where volatile refuses to default; silent in the map flow
1|M7|SPEC.md:2505|from-elf writes the identity claim the FAQ says must not be defaulted into
1|M8|SPEC.md:752|A measurement and a parameter in one read-write section: clean check, then a section type conflict
1|M9|src/ddd/compare.py:410|changed-interface says shape: [N] != [N] when a constant's value changed
1|M10|SPEC.md:2105|A dictionary dumped from a failing project compares clean; produced by nobody is only a warning
1|M11|docs/concept.rst:203|One definition rests on -fno-common: a hand-written second definition links silently under -fcommon
1|M12|SPEC.md:422|A 128 character name as an array of structures overruns MAX_PARTIAL_IDENT with its index
```
