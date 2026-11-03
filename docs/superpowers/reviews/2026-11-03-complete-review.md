# Complete review of DDD, 2026-11-03

A full review of the whole project at master `2b4bae6c` (merge of PR #83), asked for by the maintainer
to answer three questions - is the concept sound, is the code split cleanly, does the documentation
miss anything - beside the usual one, does it work. It runs as a sequence of independent passes, each
by one reviewer reading the material fresh, followed by a verification of every finding by a second
reviewer and two sweeps for what the passes missed.

It follows the review of 2026-09-15 (branch `review/complete-review-2026-09-15`), whose findings were
fixed on 2026-09-16, and replaces the one started on 2026-09-24 and stopped after its first pass
(branch `review/complete-review-2026-09-24`). Since 2026-09-15 master gained the local web GUI, the
language server's edit plans, the toolbox and the ELF reader, the a2l's addresses read from the linked
image, record layouts and release 0.11.0: 515 files, 125,731 lines added and 5,393 removed since
0.11.0 alone.

Line numbers refer to the review tree, whose code is master `2b4bae6c`. **Work in progress**: passes are
added as they finish, a finding is a candidate until its verification is recorded, and the summary is
written last. The kit that drives the review is in `2026-11-03-kit/` beside this file.

## Baseline

On master at `2b4bae6c`, Windows 11, Python 3.13, the review tree's own venv, from Git Bash:

- `python -m pytest`: 7,042 tests collected, three failures, coverage 100.00 % of lines and branches
  (14,908 statements, 4,184 branches). The failures are all of this machine, none of them fails in CI:
  - `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`
    needs the Windows symlink privilege, which this shell does not hold. Known since 2026-09.
  - `tests/test_gui_api.py::TestEdit::test_the_longest_name_a_file_can_be_created_under_is_written` and
    `tests/test_gui_api.py::TestCreatingAFile::test_the_longest_name_a_file_can_be_created_under_is_planned_and_written`
    answer `500 unwritable`, because this machine runs with `LongPathsEnabled = 0`, stock Windows, and the
    temporary directory plus a name of 244 bytes passes 260 characters. New since the last review, and
    a small finding in its own right: the limit the GUI states counts the name, not the path, and the
    suite is not green on a stock Windows machine.
- `ruff check .`, `ruff format --check .` (170 files), `mypy` (strict, 91 source files): clean.
- `gui/`: `npm run schemas`, `lint` (biome, 224 files, one info), `typecheck`, `test` (Vitest, 38 files,
  959 tests, 100 % statements/branches/functions/lines over `src/api`, `src/lib`, `src/state`), `build`: clean.
- `npm run e2e` with the installed Edge (`PLAYWRIGHT_CHANNEL=msedge`), against a real `ddd gui`: 294 journeys
  passed in 13 minutes; `mapped.spec.ts` stays out of the run without `DDD_MAPPED_DRIVE`, as documented.

## The coordinator's own reading

Read and measured directly by the coordinator before any pass ran, and deliberately not handed to the
passes of part A, so that their readings stay independent. Each item is compared with what the passes
found once they have reported.

### R1. `--const-inputs` changes what the compiler may assume (reproduced)

`docs/concept.rst:193-200` and `README.md:711-715` say the mismatch between a consumer's
`extern const` and the definition's non-const is "a constraint violation in strict c ... even though
the usual embedded toolchains accept it and generate exactly the code one expects". Two things are
wrong with that:

- It is not a constraint violation. Two declarations of one object in different translation units
  with incompatible types is undefined behaviour under C11 6.2.7p2, which requires no diagnostic.
- The code is not what one expects. gcc 15.2 at `-O2` treats an `extern const int` that is not
  volatile as unchanged across a call to another translation unit:

  ```c
  extern const int ValueF;
  void step(void);
  int twice(void) { int before = ValueF; step(); return before + ValueF; }
  int wait_for_ten(void) { while (ValueF < 10) { step(); } return ValueF; }
  ```

  `twice` loads `ValueF` once and doubles it (`leal (%rbx,%rbx), %eax`); `wait_for_ten` loads it once,
  and if it is below ten spins in `.L5: call step; jmp .L5` forever. The same source with plain
  `extern int` re-reads it after every call. So a consumer built with `--const-inputs` that reads a
  non-volatile input on both sides of a call sees a stale value, and a loop waiting on one never ends.
  A measurement is exactly an object another component writes, and `volatile` is `false` on most of
  them, as the document itself says it may be. Probe: `SCRATCH/constprobe/`.

### R2. Measured shape of `src/ddd` (39,696 lines, 89 files)

`SCRATCH/layers.py` computes the import graph, top-level and lazy, `SCRATCH/layers.txt` its output.

- `ddd.lsp` is no longer the language server alone: `lsp.ranges` has 21 importers and `lsp.navigation`
  18, most of them outside `lsp/`. `ddd.editing`, `ddd.identity` and fourteen root modules import it,
  and `lsp.edits`, `lsp.units` and `lsp.navigation` import them back, so the package boundary is a cycle
  in both directions. `identity.py` says it itself: `ranges` "happens to live under the language
  server". `lsp/__init__.py` still opens "The language server".
- Fourteen modules at the package root are imported by the GUI alone or by each other, and describe
  themselves in the GUI's words ("as the Units tab of `ddd gui` shows them", "the unit panel"), while
  calling themselves transport-neutral: `declaration_plans`, `file_plans`, `shared_plans`, `type_plans`,
  `project_shared`, `project_types`, `project_units`, `variables`, `variable_keys`, `object_values`,
  `finding_routes`, `finding_fixes`, `findings_by_file`, `graph`. Nothing in the tree says they are a layer.
- `tests/test_backends.py`'s guards name the front end and the backends. Neither `gui/` nor `lsp/` nor the
  fourteen modules is guarded, so "the layering cannot rot silently" holds for less than half the code.
- `docs/developer_documentation.rst:19-58` (Layers) does not have a row for `src/ddd/gui/` or for any of
  the fourteen; line 75 says "six smaller modules sit beside them"; line 92 calls `lsp/` "a second front
  end". `README.md:1033-1041` (Layout) stops at the backends as well.
- `gui.api.Api` is one class of 1,366 lines. `cli._build_parser` is one function of 426.

### R3. Measured shape of `gui/src` (production code 16,000 lines, generated 6,560)

`SCRATCH/tslayers.py`. The direction is mostly sound: `components` and `ui` import no `state`, no query
library and only the types of `api`; `lib` is pure and sits under a 100 % gate; `screens` hold the hooks.
A cycle `api/client` <-> `state` exists (`api/client.ts:1` imports `state/edits`, `state/revisions.ts:1`
imports `api/client`). No identifier pattern, numeric range or datatype table turned up in `lib/`,
`screens/` or the views by a first grep, which is good, and is for pass 3 to confirm or refute by reading.

### R4. The documents

- `docs/index.rst` has `gui_security` and no page on using the GUI: there is no guide to a part of the
  product that is, measured in lines, as large as all of the rest. `docs/developer_documentation.rst`'s
  section The browser interface is mostly the mechanics of test fixtures and benchmarks; no page says how
  the GUI is put together.
- `SPEC.md`, which calls itself the authoritative contract, mentions `ddd gui` twice (lines 785, 2136) and
  specifies nothing of it.
- `SPEC.md:2215` says the dictionary's `format` is "today `8`"; `src/ddd/ir.py:645` says 9. Reported on
  2026-09-24 and still there.
- Production code cites planning artefacts in 103 places ("Task 2 is the only caller", "part 5's stack",
  "Appendix A of docs/superpowers/plans/...", `graph.py`, `gui/compare.py`, `gui/queries.py`,
  `declaration_plans.py`, ...).

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

## Pass 2: the split of the Python code

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-2/`. Line numbers are on the review tree.

**The answer, plainly.** Half of it is clean and half of it is not, and the line between the two is where the
editor features arrived. The generator (`models`, `loading`, `analysis`, `ir`, `compare`, `plugins`,
`backends`, `toolbox`) is well split: it runs and passes its tests with `ddd.gui` and `ddd.lsp` refused at
import. The transport is at the edge. The split between UI and backend *inside the editor features* is not
clean: there is a layer of about 9,000 lines that reads and changes a project for an editor, it has no name,
no row in the documentation and no guard, nearly a third of it lives inside the package named after the language
server, and the GUI and fourteen modules at the root of the package import that package to get it. Some of its
rules live in the clients. The guards that "keep the layering from rotting" hold eight rules and let 33 of 33
realistic violations through.

### Scope covered

**Read in full, with line numbers:** `src/ddd/gui/api.py` (1-2486), `gui/session.py` (1-1039), `editing.py`
(1-982), `lsp/navigation.py` (1-930), `lsp/units.py` (1-624), `lsp/edits.py` (1-954), `project_units.py`,
`type_plans.py`, `declaration_plans.py`, as the pass asks; and `lsp/ranges.py`, `lsp/diagnostics.py`,
`lsp/discovery.py`, `variables.py`, `variable_keys.py`, `project_types.py`, `project_shared.py`,
`shared_plans.py`, `file_plans.py`, `object_values.py`, `finding_routes.py`, `finding_fixes.py`, `identity.py`,
`deliveries.py`, `loading.py`, `gui/routes.py`, `gui/derived.py`, `gui/compare.py`, `gui/queries.py`,
`lsp/__init__.py`, `gui/__init__.py`, `ddd/__init__.py`. `docs/developer_documentation.rst` 1-200 and
895-1194; `docs/concept.rst` 510-589; `README.md` 1025-1058; `tests/test_backends.py` 1-289;
`tests/test_file_plans.py` 2124-2142; `tests/test_cli.py` 3726-3751.

**Read in part:** `lsp/server.py` 1-300 and its outline; `gui/server.py` 1-260, 952-1057 and its outline;
`gui/contract.py` 1-120; `gui/depth.py` 1-80; `analysis.py` its outline and 2551-2640; `cli.py` 1-60, 192-215,
822-1011, 1129-1309, 1602-1625, 1878-1918 and its outline; `backends/base.py` 25-54, 255-434; `diagnostics.py`
345-394; `file_names.py` 1-40.

**Docstring and public surface only:** every other module: the first line of its docstring and its public names
(`graph.txt`, last section, for all 87 modules), and the whole docstring of the 27 that bear on the split.

**Measured** (`graph.py`, `edges.py`, `sizes.py`, `closure.py`, `clones.py`, `words.py`, `who_uses.py`,
`parallel.py`): the import graph with top level, lazy and `TYPE_CHECKING` edges kept apart, with and without the
parent package an import runs; fan-in, fan-out, strongly connected components, dependency levels; what a fresh
interpreter really loads for each module, plain and with `ddd.gui` and `ddd.lsp` refused; code against prose per
module; repeated functions and token runs; who uses which symbol of `ddd.lsp`; commits per file since 2026-09-17.

**Probed:** the core with the editor layers refused (`probe_a.txt`); 1,293 core tests the same way
(`core_tests_blocked.txt`); a batch tool with `ddd.gui` refused, against the api, byte for byte (`probe_b.txt`,
`probe_b2.txt`); rules held twice, run against each other (`probe_c.txt`, `probe_d.txt`, `probe_f.txt`); the api
in process with no socket and a 1,200 component project (`probe_e.txt`); `ddd id --assign` against the engine on
Linux under WSL, with the models stubbed and both writers' own code (`wsl_identity.txt`); 40 injected imports
against every layering guard (`mutate.txt`); the first two moves of the target structure on a scratch copy
(`trial.txt`).

**Not covered:** the bodies of `compare.py`, `models/`, `backends/` apart from `base.py`, `toolbox/`, `elf.py` and
`lsp/hover.py`; and the TypeScript under `gui/`, which is pass 3's. Nothing here repeats pass 1's concept findings.

### Strengths

- **The generator does not know the editor.** `models`, `loading`, `ir`, `diagnostics`, `plugins`, `analysis`,
  `compare`, `deliveries`, `addresses`, `elf`, `toolbox/`, `backends/` have no edge to `ddd.gui` or `ddd.lsp`, top
  level or lazy (`graph.txt`). With both refused at import, load, analyse, `ddd check`, `ddd dump`, compare, render
  c and a2l and write all work (`probe_a.txt`), and 1,293 tests of 19 core test files pass (`core_tests_blocked.txt`,
  after three `try`s in `tests/conftest.py`, see Test gaps; `test_elf.py` did not collect, for a helper my copy
  lacked).
- **Every row of the documented layer table holds in the real graph.** Backends reach `ir`, `models` and their own
  package; c and a2l have no edge between them; `plugins` reaches `diagnostics`, `ir` and `names` at runtime;
  `elf` imports no `ddd` module; `models` reaches only `names`; `lsp` and `gui` reach no backend. The problem is what
  the table leaves out (I5), not what it says.
- **Nothing below the GUI imports the GUI.** The one edge into `ddd.gui` from outside it is `cli.py:1612`, lazy.
  `ddd.lsp` has none. The GUI is genuinely on top.
- **No import cycle at module level** once package `__init__` files are set aside (`graph.txt`). The two cycles
  through lazy imports are small (M1).
- **Transport is at the edge.** `http.server` and sockets are in `gui/server.py` alone; json-rpc's framing in
  `lsp/protocol.py` alone. `gui/api.py` answers with no socket: `Api.handle` runs in process (`probe_e.txt` §1), which
  is how `tools/bench_gui.py` already drives it, and `gui/server.py` is a security edge of its own. (The language
  server's *shapes* are another matter: see "Is transport kept at the edge?" under Assessment.)
- **The plan functions really are reusable.** A batch tool with `ddd.gui` refused made thirteen edits through them,
  with no error after any, and left every file byte for byte what the same edits through the api left; it took about
  twenty lines of glue (`probe_b.txt`).
- **Several copied rules agree today.** `lsp/units.py:text_edits` against `editing.edit_text`: 28 of 28 same bytes over
  LF, CRLF, tabs, one line, a merge and neighbouring removals (`probe_c.txt` §5). `rename_problem` against the loader
  and the analysis: 102 of 102 on an empty project, 61 of 64 inside one (`probe_d.txt`, `probe_f.txt`; two of the three
  differences are the edit being stricter, the third is M6). `file_plans._component_name`: 14 of 14 (`probe_f.txt`).
  `object_values._acceptable` against the loader and `_check_init`: 262 of 264, the two being one case (M5). `KINDS`, `SCOPES`, `ROLES`,
  `KEY_ORDER`, `EDITORS`, `SETTABLE`, `REQUIRED` and the `Vocabulary` tables all match the models today (`probe_d.txt`).
- **The engine is one job done well.** `editing.py` is cohesive, verifies each edit against the parsed document, keeps
  access and retries on Windows. It is a module in the wrong place only because of what it imports (I2).

### Issues

#### Critical

None. The split produces no wrong C, a2l or dictionary, and I found no file lost by it. The worst reproduced effects
are in the list below.

#### Important

- **I1. The edit layer has no name and no home, and its dependency runs the wrong way.**
  `src/ddd/lsp/navigation.py:142` (`Index`), `lsp/ranges.py:83` (`Document`), `lsp/units.py:64` (`PlannedEdit`),
  `lsp/edits.py:563` (`settle`), `lsp/diagnostics.py:95` (`run_build`). Everything that reads or changes a project
  for an editor is about 9,000 lines (table under Assessment), split between the package root and `ddd.lsp`. 14 root
  modules import `ddd.lsp` (35 edges) and so do 4 GUI modules (10 edges); from outside the package `ranges` has
  fan-in 15, `navigation` 13, `units` 7, `edits` 6 (`scc_with_parents.txt`). Of `ddd.lsp`'s 4,952 lines about 2,600
  are not about a language client at all: `Index`, `rename_problem`, `settle`, `reconciliations`, the unit plans,
  `Run`, `group_findings`, `discover` (`who_uses.txt`). Since 2026-09-17 `lsp/hover.py` and `lsp/protocol.py` took 0
  commits and `lsp/server.py` 1, while `lsp/edits.py` took 18, `units.py` 14, `navigation.py` 12, `diagnostics.py` 8:
  the language server has stood still and its package has been the GUI's backend. The code says so itself:
  `identity.py:9-10` "happens to live under the language server", `value_identity.py:15-18` on what a value is
  becoming "the language server's to say", `lsp/navigation.py:759-765` choosing where a rule lives by which import
  would cycle, `file_plans.py:533-535`.
  *Trigger:* with `ddd.lsp` refused, `import ddd.variables`, `variable_keys`, `project_units`, `project_types`,
  `project_shared`, `type_plans`, `shared_plans`, `declaration_plans`, `object_values`, `file_plans`,
  `finding_routes`, `finding_fixes` each raise `ImportError`, and `editing.edit_text` and `identity.assign` raise it
  on first call (`probe_a.txt`). *Consequence:* a second interface or a batch tool cannot avoid the language server's
  package, a change for the page lands in a package named for another client, and where a rule goes is decided by
  which import would cycle. *Change:* the target structure, moves 5 to 7 (M each, L together).

- **I2. Importing `ddd.lsp.ranges` loads the whole language server, and two deferred imports hide a 12-module cycle
  behind it.** `src/ddd/lsp/__init__.py:12-15`, `editing.py:22-24, 481, 527`, `identity.py:13-18, 173`.
  `ddd/lsp/__init__.py` re-exports `Server` and `serve`, so any import under `ddd.lsp` loads `server`, `protocol`,
  `hover` and the rest. Counting the parent package an import runs, `{editing, identity, lsp, lsp.*}` is one strongly
  connected component of 12 modules (`scc_with_parents.txt`); the function-level imports are what keep it from
  failing at import, and both docstrings say so. *Trigger:* `import ddd.file_plans`, documented "transport-neutral",
  loads `ddd.lsp.server` and `ddd.lsp.protocol` (`closure.txt`: all 12 plan and read modules do); `ddd id --assign`,
  the pre-commit hook, needs them too and fails without them (`probe_a.txt`). `src/ddd/gui/__init__.py:6-7` already
  states the right rule ("Nothing is imported here"). *Change:* an empty `lsp/__init__.py`, the two imports moved up:
  S. Tried on a scratch copy (`trial.txt`): the plans stop loading `server`, `protocol` and `hover`; one line of a test is
  repointed (`tests/test_plugins.py:52`); over 29 test files and 3,572 tests the same four fail before and after, the
  known symlink one and three that fail in the scratch copy before any change. Moving `ranges.py` out as well
  (60 spellings, `sed`) gives the same four, and `ddd.editing` then loads nothing of `ddd.lsp`.

- **I3. Rules a second client needs live in the clients.** `src/ddd/gui/api.py:2144-2294` (`_addition`, `_removal`,
  `_judged`), `:1791-1850` (`_appeared_since`, `_changed_since`), `:1513` (`_refuse_unanalysed`), `:1957-2006`
  (`_required_keys`, `_declared`), `:2386-2420` (`_number`, `_folded`), `gui/session.py:736-772` (`findings_with`,
  `_runs`), `:847-908` (`_creatable`, `_confined`, `_included`), `:933-945` (`kind_of`), `cli.py:939-1010` (the
  `address-missing` check), `:1129-1296` (assembling a generate run). About 225 code lines of `gui/api.py` are
  project rules, not routes. The core modules point upward at them in prose: `file_plans.py:533-535` says the kind
  rule is one "this module, importing nothing of `ddd.gui`, cannot ask"; `lsp/units.py:146-149` and
  `shared_plans.py:571` shape every plan around "the only creation `ddd.gui.session._confined` allows".
  *Trigger:* `remove_plan` for `constants.ddd.json` of `examples/vocabulary`, applied by the batch tool: written,
  and the project then fails with `unknown-constant`; the same request through the api is `409 ... would leave one
  error more` (`probe_b.txt`, `probe_b2.txt`). `add_plan` takes `x.py`; only `gui/api.py:2180` refuses it. A batch
  tool has `new_errors` and cannot get its `after` without `gui/session.py`. *Consequence:* whatever else makes these
  edits can break a project the GUI would protect, or has to copy the rules. `generate` cannot be reused without
  `ddd.cli`. *Change:* move 8 and 9: file judgement beside `file_plans.py`, `kind_of` into `loading.py`, `Session`
  below the GUI, `_number`, `_folded` and the empty description into their plans, the generate run and the address
  checks out of `cli.py`. M.

- **I4. The guards hold eight rules; "cannot rot silently" is false.** `KNOWN` (2026-09-15, pass 7 test gaps).
  `tests/test_backends.py:32-41, 66-160`, `tests/test_file_plans.py:2124-2142`; the claims at
  `docs/developer_documentation.rst:106-112`, `docs/concept.rst:578-583`, `README.md:1047-1048`. Nothing covers `gui`,
  `lsp`, `editing`, a plan, `compare`, `deliveries`, or `models` importing anything. *Trigger:* forty forbidden imports
  injected one at a time into a scratch copy, every layering test run each time (`mutate.txt`). Caught: the 7
  controls. Not caught: all 33 others, among them the file formats importing a backend or the analysis, the loader or
  the analysis importing the gui's api, `ir` importing the command line, the a2l backend importing the language
  server, the language server importing a backend (the table's own row) or the gui, `editing` importing the session,
  and `file_plans` importing the gui lazily, the one module its guard names. The helper itself has three holes, each
  passing a directly guarded file: `from ddd import backends` in `loading.py`, `from .backends import base` in
  `plugins.py`, `from . import names` in `elf.py` ("imports no ddd module at all"), and `importlib`. Ruff's `TID` rules
  are not on. *Change:* one table-driven test over every module, with a ratchet of today's violations that only shrinks
  ("What the guards should then say", under Assessment): S.

- **I5. The documented layers leave out 39 % of the code, and three sentences about the rest no longer hold.**
  `docs/developer_documentation.rst:19-58, 75, 78-83, 92-97`, `README.md:1033-1041`, `src/ddd/__init__.py:3-9`. This
  page is for "whoever has to change DDD ... before moving something". `gui/` (8,580 lines) and 20 root modules (6,645
  lines: `editing`, every plan and read model, `deliveries`, `graph`) have no row and no statement of what they may
  import; "The browser interface" names some of them as sitting "beside" each other and never says what is below
  what. No longer so: `:75` "Six smaller modules"; `:78-79` "`cli.py` is the only module that knows about ... exit codes and
  where output goes" against `gui/server.py:70, 931-932, 978-993, 1027` and `gui/session.py:546, 686`; `:92-96`
  `ddd.lsp` as "a second front end" against 19 modules importing it. `src/ddd/__init__.py:3-9` says "each knowing only
  what is below it" of a list with `ir` above `loading` and `analysis`, both of which import it. The README table has no
  `lsp`, `gui`, `toolbox`, `elf`, `addresses`. Pass 1 M1 and M2 cover `docs/concept.rst`. *Consequence:* the page that
  should stop the next module landing in the wrong place does not mention where it would go. *Change:* the table of the
  target structure, written last: S.

- **I6. `ddd id --assign` is a second edit engine without the first one's protections.** `src/ddd/identity.py:198-208`
  against `editing.py:919-963, 472-491`. *Trigger, reproduced on Linux with both writers' own code
  (`wsl_identity.txt`):* a file of mode 640 is left 644, 600 is left 644, and a read-only 444 is rewritten and left 644,
  where the engine leaves each as it was. `editing.py:949-956` records this very defect, a read-only file made writable
  and a file left root's in a container, as fixed; `identity.py:57-63` and `docs/command_line_interface.rst:163-165`
  promise a file that cannot be written is reported, and a read-only one on Linux is not. It does not retry on Windows
  (`_patiently`), and it reads by python's parser, so it rewrites a
  file the loader refuses: a key spelled twice, or `NaN`, answers 1 and writes (`probe_c.txt` §4), against "must not
  rewrite one it could not read" (`identity.py:169-171`), where the engine refuses both. It runs as a pre-commit hook on
  every staged description (`.pre-commit-hooks.yaml`), and `docker-compose.yml` mounts the checkout and names no user,
  so run there it also leaves the file root's (read off the line). A third staging writer is
  `backends/base.py:264`, and `STAGING_SUFFIX` is spelled three times (`file_names.py:16`, `identity.py:66`,
  `backends/base.py:33`, pinned by tests). *Change:* `assign` builds its `FileChange`s and calls `apply_changes`, keeping
  its insertion: S. No test checks a mode after `ddd id`.

- **I7. "Load, gate, analyse, keep the plugins" exists six times and "compare, then hooks" three, and the copies have
  already diverged once.** `cli.py:1896-1917`, `deliveries.py:136-146`, `lsp/diagnostics.py:171-177, 201-217`,
  `lsp/hover.py:97-105`, `toolbox/checked.py:89-91`; compare at `cli.py:847-856`, `cli.py:899-908`,
  `gui/compare.py:233-248`. `gui/compare.py:19-24` and `lsp/diagnostics.py:63-68` record the result: the GUI compared
  without the hooks and "answered 'can replace' for a delivery the command exits 1 on". Each comment now says what the
  others do; nothing makes them. They differ legitimately in what a `PluginError` becomes and in the verify step, which
  a parameter can hold. *Consequence:* the next step of the pipeline, or a change in its order, is written six times.
  *Change:* one `resolved_project(path, bag, *, includes)` and one `compare_deliveries(...)` in `deliveries.py`, which
  `cli`, `lsp` and `gui` call: M.

- **I8. The UI's vocabulary is below the UI, and "transport-neutral" is taken to mean "UI-neutral".**
  `src/ddd/finding_routes.py:205-224` (`Route.kind`, "Which screen the page opens"), `variable_keys.py:54-75` (`EDITORS`,
  "Which field the page offers"), `project_shared.py:106-122` (`Vocabulary.keys` "in the order the panel draws them",
  `strings` "so the panel shows them without their quotes", `states` "The row's States cell"), `project_types.py:41-45`,
  `declaration_plans.py:33-37` ("in the order the form offers them"), `finding_fixes.py:52` ("What the button says"),
  `project_units.py:1`, `project_types.py:1`, `project_shared.py:1`, `shared_plans.py:1`, `variables.py:1`,
  `variable_keys.py:1` (each module's first line names a tab or a panel). Counted in prose and identifiers per module in
  `words.txt`. `finding_routes.py:11` says "Pure: no GUI" of a module whose answer is a screen of the page, and
  `:217-224` explains that the list of screens is therefore "stated twice and pinned together" by a test, because
  `contract.FindingRoute.kind` cannot import it. *Consequence:* a change of what the page shows edits a "core" module, and a second interface
  inherits screens it does not have. *Change:* screens and fields to `ddd.gui` (`route_of`, `Route`, `EDITORS`, the
  `states` cell, form orders); what is about the project stays (`ABOUT_THE_DECLARATION`, `UNIT_CHECKS`, `KeyOffer` less
  `editor`, the rows): part of move 7.

- **I9. One rule twice, fixed once: every keystroke in a Shared files panel parses every file of the project, for
  nothing.** `src/ddd/shared_plans.py:113-152` against `lsp/units.py:177-218`; `gui/api.py:1193-1198`. The two functions
  read a project's vocabulary files the same way. `unit_project` learnt not to parse every file (`_may_list_units`,
  `:204-218`, measured there at 1.4 s of 1.5 s, plan `2026-09-30-gui-large-projects`); `project_of` did not, and
  `_shared_plan` calls it unconditionally although "`project` is unused by three of the four" verbs
  (`gui/api.py:1888-1889`), and "a panel asks for a plan on every keystroke" (`project_shared.py:168`). *Trigger, in
  process over 1,200 components of 30 declarations (`probe_e.txt` §6):* `GET /api/unit-plan?action=describe` 570 to 626
  ms; `GET /api/constant-plan?action=set` of one key of a one-entry file 1,727 to 2,212 ms. The two also disagree on
  what an unparsed file means (`untellable` has no counterpart). *Change:* one function; ask it only for `add`: S.

- **I10. Each plan route is the same thirty lines, and each plan the same class.** `KNOWN` in part
  (`2026-09-23-gui-values.md:1503`, then "eight spellings of one idea"). `src/ddd/gui/api.py:797, 921, 1115, 1169, 1219,
  1321, 1402, 1433`: eight handlers differing in about four lines. `409 if refused.code in REFUSALS else 500` is now
  written 12 times, the not-found mapping 8, the "did not load" sentence 3. 1,894 of the file's 13,144 tokens are in
  repeated runs of 50 or more (`clones.txt`). Below it: five one-field plan classes (`lsp/units.py:74`, `type_plans.py:59`,
  `shared_plans.py:90`, `declaration_plans.py:130`, `object_values.py:284`; `project_units.py:254-256` "two different
  dataclasses sharing one shape"), six identical refusal classes (`lsp/units.py:160`, `type_plans.py:42`,
  `shared_plans.py:96`, `declaration_plans.py:141`, `object_values.py:41`, `file_plans.py:239`), and six shapes for what
  one file takes (`PlannedEdit`, `FileEdit`, `Planned`, `FileChange`, `_FilesPlanned`, and the tuples of
  `variables.py:170`, for which my batch tool had to write a class). Exact copies: `_protocol_edit`
  (`lsp/edits.py:949`, `lsp/units.py:618`), `_raw` (`lsp/units.py:504`, `shared_plans.py:550`), `_names`, `_plan`, the
  lookup in `project_shared.py:538, 590, 653` and `project_types.py:186`. *Consequence:* `gui/api.py` is the most changed
  file of the package (75 commits since 2026-09-17, against 54 for the next), and each new route copies its neighbour, drift
  included. *Change:* one `Plan`, one `PlanRefusal`, one `_answered(revision, plan)`: S to M, about 200 lines fewer.

#### Minor

- **M1. Two cycles through lazy imports, and two small inversions.** `diagnostics.py:365` imports `loading.resolve_path`
  (`{diagnostics, ir, loading, plugins}`, and its comment says this line is what keeps the graph acyclic);
  `gui/server.py:70` imports `EXIT_OK` and `EXIT_USAGE` from `ddd.cli` (`{cli, gui.server}`); `loading.py:14` imports
  `ir` only for `load_dictionary`, the reader of the other format. `analysis.py:18` takes its comparison primitives from
  `compare.py`, which the docs call a consumer of the dictionary: documented in `compare.py`, harmless, but the guard does
  not know `compare` sits inside the front end's closure. *Change:* `resolve_path` to a leaf, `EXIT_*` to `names.py`,
  `load_dictionary` to `deliveries.py`: S.
- **M2. `gui/api.py:140-143` imports `_name_in`, `_read_json`, `_served`, `_source` from `gui/session.py`.** The only
  private names reached across modules in the package (`who_uses.txt`); they are the rules of I3 not yet given a name.
- **M3. "Values arrive as json text, never as parsed values" is not what two modules do.** `declaration_plans.py:320`
  (`read_object`, and `declare_object`) and `project_types.py:263` (`fixed_by`), against `editing.py:11-15`,
  `lsp/units.py:504-507` and `shared_plans.py:550-554`, each of which spells out what `ensure_ascii` is for. *Trigger:*
  reading a variable with `"unit": "°C"`, `"factor": 1e-1`, `"min": -4.0e1` writes `"\u00b0C"`, `0.1`, `-40.0` into the
  reader's file (`probe_c.txt` §2). `check` stays clean, so the effect is cosmetic, in the most common non-ascii unit of
  the domain. `GET /api/type` answers `"\u00b0C"` and `{"factor": 0.1}` where its docstring says "as the json text it is
  written as" (`probe_e.txt` §3).
- **M4. What kind of file this is, answered five ways.** `loading.py:67, 734-766` (the rule), `gui/session.py:58, 933-945,
  985-987`, `lsp/diagnostics.py:155-158`, `deliveries.py:210-217`; `session.KINDS` restates `FILE_KINDS` with no test
  pinning them. *Trigger (`probe_c.txt` §1):* a dumped dictionary is `file-kind` to the loader and `types` to `kind_of`, so
  `GET /api/files-plan?action=add` previews it where `gui/api.py:2186` refuses a file of no kind (`probe_e.txt` §4); a file
  with `project` and `component` is `file-kind` and `project`. `Upper.DDD.JSON` loads with no finding, "compared without
  regard to case" (`SPEC.md:194`, `loading.py:727`), and `GET /api/projects` does not list it (`gui/session.py:958`,
  `probe_e.txt` §5); `lsp/navigation.py:540` depends on the platform. *Change:* one public `file_kind(data)` in `loading`.
- **M5. A cell the plan takes and the file refuses.** `object_values.py:501` holds the datatype's rule and not the model's
  `within_64_bits` (`models/common.py:179`). *Trigger:* `GET /api/value-plan?name=A1&at=[1]&raw=18446744073709551616` on a
  float32 axis answers 200, `POST /api/edit` writes it, and the component stops loading with `schema` (`probe_e.txt` §2).
  Undo puts it back. The two checks are otherwise one rule written twice: share one `init_problem(value, datatype)`.
- **M6. `rename_problem` takes a constant named as a structure member, and the next check refuses it.**
  `lsp/navigation.py:792` against `analysis.py:1918-1925`. *Trigger:* renaming constant `OTHER` to `rpm`, a member of a
  structure: no refusal, then `name-collision` (`probe_f.txt`). The class of defect `_occupy`'s docstring
  (`lsp/navigation.py:354-360`) records for enumerators. *Change:* note member names in `Index.occupied` for a constant.
- **M7. One fix, two diffs.** `finding_fixes.py:89` sets `definition.id`, which the engine appends after the last key;
  `identity.py:160` and so the language server and `declaration_plans._stamped` put it after `name` (`probe_c.txt` §3),
  against `finding_fixes.py:8-10` "only how the edit is spelled differs".
- **M8. 31 regular expressions over pointer shapes, in 7 modules, and no module that owns the shapes.**
  `lsp/navigation.py:50-104`, `lsp/edits.py:138, 142`, `finding_routes.py:93-122, 191`, `project_shared.py:235, 241, 551, 603,
  607`, `project_types.py:30`, `toolbox/checked.py:39-40`, `gui/derived.py:36`; `component.interface` is spelled in 12 files.
  Several are pinned to each other by tests rather than shared. `KNOWN` for `WITHIN_DECLARATION`, written twice
  (`2026-09-22-gui-findings.md`, "One pattern, written twice"), still open.
- **M9. 73 citations of planning artefacts in 25 modules.** `part 13`, `part 14's third task` (`project_shared.py:81`,
  `lsp/navigation.py:771`), `Task 2 is the only caller` (`graph.py:5`), `ruling P19a-14`, `run 37737377854`
  (`gui/server.py:129-134`), `Appendix A` (`gui/queries.py:7`), `the branch's final review` (`finding_routes.py:165`). 18 are in
  `gui/server.py`. A future reader cannot resolve most of them from the tree; those that name a measurement should state it.
- **M10. Docstrings the code has outgrown.** `lsp/server.py:1, 3-4` ("six messages", "Everything that decides anything lives
  in `lsp.diagnostics` and `lsp.discovery`"), `lsp/protocol.py:4-9`, `variable_keys.py:6-7` and `finding_routes.py:11-12` ("nothing
  else reads them": `declaration_plans.py:30`, `project_shared.py:33`, `project_units.py:20` do), `lsp/navigation.py:110-111`
  (the docstring of `_BASE_DATATYPES` describes something else), `shared_plans.py:48-56` (`CONSTANTS_FILE` kept for tests).
- **M11. The pair of an index and a document cache is threaded by hand.** `cache: dict[Path, Document]` is written 126 times in 18
  modules, and arguments no one reads are kept "for the shape": `lsp/units.py:319-320`, `declaration_plans.py:255-258`,
  `project_shared.py:176`. One small `ProjectView(index, documents, unread)` would carry them. Part of move 5, not urgent.

### Status of the 2026-09-15 findings in this area

| finding | status | where |
| --- | --- | --- |
| Pass 7 test gap, "`compare.py`, `identity.py`, `build_info.py`, `cli.py` and `src/ddd/lsp/` sit outside the import-graph guard" (`review-2026-09-15.md:3033`) | STILL OPEN, and wider: `gui`, `editing` and every plan since | I4 |
| P7-M2, the layer table never names `lsp`, `identity`, `build_info` | FIXED for those (`developer_documentation.rst:47-49, 86-97`); REGRESSED in kind: `gui/` and 20 root modules have no row | I5 |
| P9-M11, the table's wording about the analysis | FIXED on the developer page (`:32-34, 60-64`); STILL OPEN at `README.md:1037` | I5 |
| Pass 10's "outside `cli.py` nothing prints, exits or names a stream" (`review-2026-09-15.md:3932`, a strength then) | No longer true: `gui/server.py`, `gui/session.py` | I5, M1 |

### Open questions

1. **Is a second interface, or a batch tool making these edits, a goal?** If yes, all of the moves are worth making. If no,
   moves 0 to 4 and the documentation remove what hurts, and moves 7 to 9 can wait for the first reason.
2. **Does anything outside this repository import `ddd.lsp.*`, `ddd.editing` or `ddd.gui.*`?** I did not look (ptf is ruled out).
   If something does, each move keeps a shim for a release; if not, the renames are free.
3. **What is the layer called, and is it one package?** I propose `ddd.editing`, today's module becoming `ddd.editing.engine`.
   The answer changes only names.
4. **Is `ddd.gui.api.Api` a supported in-process interface?** It works as one (`probe_e.txt` §1) and is documented as internal
   (`gui/api.py:5-6`). If it becomes supported, `Session` may stay nearer the GUI and a batch tool drives the api; if not, I3 stands.
5. **Where does an id go?** After `name`, as `ddd id` writes it, or where the engine appends it (M7). Either is fine; one is.

### Test gaps

- `tests/conftest.py:28, 31, 32` import `ddd.gui.session`, `ddd.lsp.navigation` and `ddd.lsp.protocol` at module level, so every
  test of the core loads both editor layers and nothing can notice the core coming to depend on them. Three `try`s were all it
  took for 1,293 core tests to pass with both refused. A test file `tests/test_core_alone.py` in a sub-interpreter would pin it.
- Only one module's closure is tested (`test_the_module_imports_nothing_of_the_gui`, for `file_plans`, at import time, so a lazy
  import passes it) and `ddd --version`'s. Its siblings say the same thing in prose and are not held to it.
- No test checks a file's mode after `ddd id --assign` (I6); the engine's is at `tests/test_editing.py:577-580`.
- Nothing pins `gui/session.py:KINDS` to `loading.FILE_KINDS`, nor `type_plans.SETTABLE` and `REQUIRED` or a `Vocabulary`'s
  `keys`, `required`, `strings` to the models' fields. `Vocabulary.__post_init__` checks the record against itself only.
- No differential between `_acceptable` and the loader plus `_check_init` (M5), between `rename_problem` and the analysis's
  collisions (M6), or between `text_edits` and `edit_text` (it holds, and only my probe says so).

### Assessment

The core is split cleanly, the transport is at the edge, and nothing below the GUI imports the GUI; but what was added for the
editors grew without a layer of its own, so the question "UI or backend?" has no clean answer for about 9,000 lines: part of the
backend lives in the language server's package, part at the root with its modules named after tabs, part in `gui/api.py` and
`gui/session.py`, and the guards and the documentation stop where the generator stops. It has already cost: a comparison without
hooks, a permission fix that reached one writer of two, a performance fix that reached one reader of two, and about thirty lines
per route. None of it is hard to mend: the plan functions are reusable as they stand and the moves below are mostly mechanical, the
100 % coverage making them safe to make. A couple of days' work (moves 0 to 4) removes the worst of it.

#### The real layers, against the documented ones

Measured from the graph (`graph.txt`, `levels.txt`), with the lines of each. A module of `ddd.lsp` is split by symbol
(`who_uses.txt`): what only a language client needs, and the rest.

| real layer | modules | lines | in the layer table? |
| --- | --- | --- | --- |
| leaves, importing nothing of ddd | `names`, `pointers`, `file_names`, `difflib_lock`, `build_info`, `elf` | 1,192 | `names`, `elf`, `build_info` |
| file formats | `models/` | 3,609 | yes |
| one lazy cycle | `diagnostics`, `ir`, `plugins`, `loading` | 3,545 | yes |
| resolution and comparison | `compare`, `analysis`, `deliveries`, `addresses` | 5,308 | not `deliveries` |
| output | `backends/` | 2,621 | yes |
| one-off tools | `toolbox/` | 1,179 | yes |
| **the edit layer, unnamed** | `editing`, `identity`, `value_identity`, `variables`, `variable_keys`, `project_units`, `project_types`, `project_shared`, `type_plans`, `shared_plans`, `declaration_plans`, `object_values`, `file_plans`, `finding_routes`, `finding_fixes`, `findings_by_file`, `graph`, and of `ddd.lsp` the 2,598 lines that are not about a client | 9,040 | `identity`; `lsp` as if it were all client |
| language client | `lsp/server`, `protocol`, `hover`, and 829 lines of `navigation`, `edits`, `units`, `diagnostics`, `ranges` | 2,354 | yes |
| browser | `gui/` | 8,580 | no |
| command line | `cli` | 2,076 | yes |

The documented picture, front end to dictionary to backends, is right for the first six rows. It has nothing to say about the last
four but `lsp` and `cli`, and what it says of `lsp` holds for half of what that row names. Highest fan-in: `diagnostics` 30, `lsp.ranges` 21,
`loading`, `models.common` and `lsp.navigation` 18, `ir` 17; highest fan-out: `gui.api` 30, `cli` 21 (17 lazy), `file_plans` and `gui.session`
11 (`graph.txt`). That two of the five most imported modules of the package sit under `lsp/` says what I1 says. 36 % of the package's lines are prose.

**Directions that run the wrong way:** root modules and the GUI into `ddd.lsp` (I1); `diagnostics` into `loading`, `loading` into `ir`
for a reader that belongs elsewhere, `gui.server` into `cli` (M1); the plans' shape into `gui.session._confined`, in prose (I3);
read models into `finding_routes`, a module about screens (I8). **Modules with more than one reason to change:** `lsp/navigation.py` (the
jumps; the index; what a name may be; finding a document's project), `lsp/edits.py` (the quick fixes; the settlement rule), `lsp/units.py`
(the plans; their text edits; how a file is created), `lsp/diagnostics.py` (a run; drawing it), `gui/api.py` (routes; project rules; caching),
`gui/session.py` (session state; file kinds; project discovery), `cli.py` (the command line; a generate run; the `address-missing` check),
`project_shared.py` (a vocabulary's rules; a row's cells).

**Can the core be used and tested without the editor layers?** Yes, as measured, but for `ddd id`. **Could a second interface or a batch tool be
built without `ddd.gui` or `ddd.lsp`?** Without `ddd.lsp`: no, not one edit (`probe_a.txt`). Without `ddd.gui`: yes, in about twenty lines, and it gets every
byte right and loses every rule of I3 (`probe_b.txt`). With `ddd.gui.api.Api` in process: yes, today, against an api documented as internal.
**Is transport kept at the edge?** HTTP and json-rpc's framing, yes. The language server's shapes, no: `lsp/ranges.py:121-129`, `:232-245`, `lsp/navigation.py:900, 907-910`,
`lsp/edits.py:195-199, 618, 951-954`, `lsp/units.py:621-624`, `lsp/diagnostics.py:364-370` build them in the modules the GUI imports for its rules; the GUI never reads them.

#### Are the large files large because the job is large?

| file | lines | code | prose | verdict |
| --- | --- | --- | --- | --- |
| `analysis.py` | 3,692 | 2,200 | 34 % | The job. One class of 85 methods, most of the 72 registered checks, and three names used from outside it (`analyze`, `close_units`, `PRODUCER_KEYS`). Cohesive around one shared state; splitting it into mixins would move lines, not reasons. Leave. |
| `gui/api.py` | 2,486 | 1,832 | 20 % | Partly. 36 routes is a large job. Of the code, 200 lines are imports, about 240 are I10's boilerplate, about 225 are I3's rules, about 100 are dispatchers. About 1,950 lines once the boilerplate and the rules go. |
| `cli.py` | 2,076 | 1,426 | 23 % | Mostly. 16 commands. `_build_parser` (426 lines) is long because it is a flat declaration of them, and reads well; leave it. `_command_generate` and the address checks are what does not belong. |
| `gui/contract.py` | 1,798 | 548 | 41 % | The job: 76 models, one per shape on the wire. About twenty mirror a dataclass field for field (`parallel.txt`), which is the price of keeping the wire at the edge. Leave. |
| `gui/queries.py` | 1,114 | 454 | 29 % | The job, repetitive: the three vocabularies' `Set`, `Rename` and `Remove` differ by a noun. Declarative and harmless. Leave, or a factory if a fourth vocabulary comes. |
| `gui/session.py` | 1,039 | 532 | 37 % | `Session` itself is one job and a careful one. The file's helpers are I3's. |

#### Rules held in more than one place

| rule | where | state |
| --- | --- | --- |
| writing a description file safely | `editing.py:919`, `identity.py:198`, (`backends/base.py:264`) | **diverged**, reproduced: I6 |
| what a kind of file is; its suffix | `loading.py:67, 727, 734`, `gui/session.py:58, 933, 958, 985`, `lsp/diagnostics.py:155`, `deliveries.py:210`, `file_plans.py:216, 228`, `lsp/navigation.py:540` | **diverged**, reproduced: M4 |
| a project's vocabulary files | `lsp/units.py:177`, `shared_plans.py:113` | **diverged**, reproduced: I9 |
| json text is not re-serialised | `editing.py:11`, `lsp/units.py:504`, `shared_plans.py:550`, `file_plans.py:420`; `declaration_plans.py:320`, `project_types.py:263` | **diverged**, reproduced: M3 |
| a value fits its datatype | `analysis.py:2551`, `models/common.py:179`, `object_values.py:481` | **diverged**, reproduced: M5 |
| which names are taken | `analysis.py:1865` and its siblings, `lsp/navigation.py:751, 353` | **diverged**, reproduced: M6 |
| where an id goes | `identity.py:160`, `declaration_plans.py:269`, `finding_fixes.py:89` | **diverged**, reproduced: M7 |
| load, gate, analyse; compare, then hooks | I7's six and three | diverged once, mended, still six and three |
| a new component's name | `analysis.py:1792`, `file_plans.py:452` | agrees, 14 of 14 |
| an operation becomes an edit | `editing.py:516`, `lsp/units.py:601` | agrees, 28 of 28; the second is not verified |
| pointer shapes | M8's seven modules | partly pinned by tests |
| `KINDS`, `SCOPES`, `ROLES`, `CREATABLE`, `SETTABLE`, `REQUIRED`, `Vocabulary`'s tables | beside the models | agree today, most unpinned |
| what screens exist | `finding_routes.py:205`, `gui/contract.py` `FindingRoute`, the page | pinned by a test, because of I8 |

#### The target structure

```
src/ddd/
  names.py pointers.py file_names.py paths.py build_info.py difflib_lock.py elf.py   leaves; paths.py takes resolve_path; names.py takes EXIT_*
  models/  diagnostics.py  ir.py  plugins.py  loading.py                             as they are; loading.py gains file_kind(), loses load_dictionary
  compare.py  analysis.py  addresses.py  deliveries.py                               deliveries.py gains resolved_project(), compare_deliveries(), load_dictionary
  generating.py                                                                      new: what _command_generate does, less arguments and printing; address checks to addresses.py
  backends/  toolbox/                                                                as they are
  editing/                  no ui word, no transport; imports the above, never backends, lsp, gui, cli
    document.py             lsp/ranges.py, less the protocol's positions (329 lines)
    engine.py               editing.py
    identity.py             identity.py, writing through the engine
    value_identity.py       value_identity.py
    index.py                lsp/navigation.py: Index, Site, UnitSite, index(), LOAD_CHECKS, rename_sites, rename_problem; pointer shapes (about 670)
    runs.py                 lsp/diagnostics.py: Run, run_build, run_project, group_findings, finding_identity; navigation's Loaded, resolve_projects; lsp/discovery.py
    settle.py               lsp/edits.py: settle, settled_at, reconciliations, PROPAGATED_KEYS, DEFERRED_KEYS (about 700)
    plans.py                one Plan, PlannedEdit, PlanRefusal; created_beside, entry_appended; preview (planned, hunks)
    vocabularies.py         project_shared.py: the Vocabulary record and its judges, less the cells
    unit_plans.py type_plans.py shared_plans.py declaration_plans.py value_plans.py     from lsp/units.py, the root, object_values.py
    file_plans.py           today's, plus the judgement of gui/api.py (_addition, _removal, _judged, _appeared_since)
    views/                  variables, variable_keys less EDITORS, project_units, project_types, the rows of project_shared, grid (object_values.py), graph, findings_by_file
    session.py              gui/session.py, in neutral words; find_projects beside it
  lsp/                      the client: server, protocol, hover; queries.py (the jumps, about 260), quick_fixes.py (actions and spelling, text_edits, about 350), published.py (collect, _as_lsp, about 150), positions.py (about 70); an empty __init__
  gui/                      the client: server, api, routes, contract, queries, depth, derived; screens.py (route_of, Route, EDITORS, a row's cells, form orders); compare what is left of it
  cli.py                    the command line, imports the rest lazily, as it does
```

**What the guards should then say.** One test, `tests/test_layers.py`, walks every module of `src/ddd`, reads every import (top level, lazy,
relative, `from ddd import x`, `TYPE_CHECKING` apart) and refuses `importlib.import_module` outside `plugins.py`. A module not in the table fails it, so a new
module has to choose a layer.

| layer | may import |
| --- | --- |
| leaves | nothing of ddd |
| `models` | leaves |
| `diagnostics`, `ir`, `plugins`, `loading` | leaves, `models`, each other in that order; `plugins` names a backend only under `TYPE_CHECKING` |
| `compare`, `analysis`, `addresses`, `deliveries` | the above |
| `backends` | leaves, `models`, `ir`; c never a2l, a2l never c |
| `generating` | the above, and `backends` |
| `toolbox` | `compare` to `deliveries` and below; no backend |
| `editing` | `compare` to `deliveries` and below; no backend, no `toolbox`, no `generating` |
| `lsp`, `gui` | `editing` and below it; never each other, never `cli`, no backend |
| `cli` | anything, lazily |

Beside it: a sub-interpreter test that `import ddd.editing.*` leaves no `ddd.lsp`, `ddd.gui`, `http.server` or `jinja2` in `sys.modules`; a word guard that
`newText`, `as_uri`, `"uri"` occur only under `lsp/` and sockets only in `gui/server.py`; and a ban on tab, panel, page and row in the identifiers of
`ddd.editing`, in the manner of the one `ddd.models` already has for `uint16_t`.

#### The order of the moves

| # | move | removes | size |
| --- | --- | --- | --- |
| 0 | `tests/test_layers.py` as a ratchet: today's violations listed, the list only shrinks. `tests/conftest.py` stops importing the editors at module level | I4 | S |
| 1 | `lsp/__init__.py` empty; `editing.py` and `identity.py` import at the top. Tried on a scratch copy: 3,572 tests, nothing changes (`trial.txt`) | I2 | S |
| 2 | `lsp/ranges.py` to its home; `resolve_path` to a leaf; `EXIT_*` to `names.py`; `load_dictionary` to `deliveries.py`. Tried for `ranges.py`: 60 spellings, nothing changes (`trial.txt`) | M1, the SCCs | S |
| 3 | `identity.assign` through the engine; `file_kind()` in `loading`; `init_problem()`; member names in `occupied`; `ensure_ascii=False` | I6, M3, M4, M5, M6 | S |
| 4 | One `Plan`, one `PlanRefusal`, one `_answered()`; `project_of` and `unit_project` one function, asked only for `add` | I9, I10 | S to M |
| 5 | Split `lsp/navigation.py`, `lsp/diagnostics.py`, `lsp/discovery.py`: about 1,040 lines down, 62 src and 108 test references | I1 | M |
| 6 | Split `lsp/edits.py`, `lsp/units.py`: about 1,230 lines down, 49 src and 49 test references | I1 | M |
| 7 | `ddd/editing/` made; the root's plans and read models moved in (about 4,900 lines, mechanically); their docstrings lose the tabs; screens and fields to `gui/screens.py` | I1, I8 | M |
| 8 | The rules out of `gui/api.py` and `gui/session.py`; `Session` to `editing/session.py` | I3, M2 | M |
| 9 | One `resolved_project`, one `compare_deliveries`, `generating.py`; `gui/compare.py` shrinks to its words | I7, I3 | M |
| 10 | The layer table, the README table, `ddd/__init__.py`, `concept.rst`; the ratchet's list is empty by now and goes | I5 | S |
| 11 | The prose: planning artefacts, stale claims | M9, M10 | S |

About two to three weeks in all, L; moves 0 to 4 are a day or two and stand on their own. Each move is behaviour preserving, and 5 to 7 are mostly `sed`
and a full run. If the answer to open question 1 is no, I would stop after 4 and 10.

#### What I would leave exactly as it is, and why

- **`models/`, `ir.py`, `backends/`, `plugins.py`.** The strongest part of the design, measured clean; a third backend needs nothing changed. `elf.py`, `addresses.py`,
  `toolbox/` likewise: each is held to its row and keeps to it.
- **`analysis.py` as one module**, for the reason in the table.
- **`gui/server.py`** as the separate security edge; only its exit codes and its usage errors go back to `cli.py`.
- **`gui/contract.py`, `gui/queries.py`, `gui/routes.py`, `gui/depth.py`**: the wire, declared once, at the edge.
- **`lsp/protocol.py`, `lsp/hover.py`**: untouched for six weeks, and client through and through.
- **The engine's body** (`editing.py`), and `Session`'s threading: moved, not changed. **`_build_parser`** and `cli.py`'s lazy imports: long and right.
- **The rule that a plan is computed and not written**, every client previewing the same operations. It is the best idea in the edit layer, and the reason this can
  be fixed by moving things.

```candidates
2|I1|src/ddd/lsp/navigation.py:142|The edit layer has no home: 14 root modules and the GUI import ddd.lsp for their domain model, about 2,600 of its lines are not about a client
2|I2|src/ddd/lsp/__init__.py:12|Importing ddd.lsp.ranges loads the language server; two deferred imports hide a 12-module cycle; ddd id needs it
2|I3|src/ddd/gui/api.py:2203|Rules a second client needs live in the clients: file judgement, confinement, kinds, value parsing, generate; a batch removal breaks what the GUI refuses
2|I4|tests/test_backends.py:66|The import guards hold eight rules: 33 of 33 realistic violations pass, against cannot rot silently (KNOWN)
2|I5|docs/developer_documentation.rst:19|The layer table leaves out gui and 20 root modules, 39 % of the code, and three sentences about the rest no longer hold
2|I6|src/ddd/identity.py:198|ddd id --assign is a second edit engine: 600 and 444 left 644 on Linux, and it rewrites a file the loader refuses
2|I7|src/ddd/deliveries.py:136|Load, gate, analyse exists six times and compare then hooks three; the copies have diverged once already
2|I8|src/ddd/finding_routes.py:205|The UI's vocabulary is below the UI: screens, fields, panel orders and row cells in modules called pure and transport-neutral
2|I9|src/ddd/shared_plans.py:136|project_of parses every file on every Shared files keystroke, for nothing: 1.7 to 2.2 s at 1,200 components, where unit_project was fixed
2|I10|src/ddd/gui/api.py:797|Eight plan routes are one route copied, over five identical plan classes and six identical refusal classes (KNOWN in part)
2|M1|src/ddd/diagnostics.py:365|Two cycles through lazy imports and two small inversions: diagnostics to loading, gui.server to cli, loading to ir
2|M2|src/ddd/gui/api.py:140|gui/api.py imports four private names of gui/session.py
2|M3|src/ddd/declaration_plans.py:320|read_object and fixed_by re-serialise: a unit of °C is written \u00b0C, against values arrive as json text
2|M4|src/ddd/gui/session.py:933|What kind of file this is, answered five ways: a dump is types to the page, Upper.DDD.JSON is not listed
2|M5|src/ddd/object_values.py:501|A cell the plan takes and the file refuses: a whole number past 64 bits in a float object stops the component loading
2|M6|src/ddd/lsp/navigation.py:792|rename_problem takes a constant named as a structure member, and the next check refuses it
2|M7|src/ddd/finding_fixes.py:89|One id fix, two diffs: after the last key in the GUI, after name in ddd id and the editor
2|M8|src/ddd/lsp/navigation.py:50|31 regular expressions over pointer shapes in 7 modules, none owning them (KNOWN in part)
2|M9|src/ddd/gui/server.py:129|73 citations of planning artefacts in 25 modules that a future reader cannot resolve
2|M10|src/ddd/lsp/server.py:1|Docstrings the code has outgrown: six messages, nothing else reads them, a wrong docstring on _BASE_DATATYPES
2|M11|src/ddd/lsp/units.py:319|An index and a document cache threaded by hand, 126 annotations in 18 modules, with arguments nobody reads
```

## Pass 3: the split between the UI and the backend, and inside the front end

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-3/`. Line numbers are on the review tree.

**The answer, plainly.** The line between the page and the server is mostly in the right place, and better kept than the size of
the page suggests: the server composes every plan and every diff, the page matches no refusal text, the shapes on the wire are
generated, and the views are pictures of their props. It leaks in three places, and each leak has already produced wrong behaviour on
a real `ddd gui`: **numbers** (the page parses and converts them as doubles, and the wire is `float`, so a 64 bit value is shown and
written wrong without a word), **one missing read model** (the component's table reads the raw file in a `.tsx`, and is wrong about a
type's unit and about which declarations have a grid), and **one missing judge** (`settle` and `type-plan` take any value, by design,
so the page is the only guard of what a file can hold, and its guard has a hole). Inside the page the direction of the imports is
sound, and the `*View` half of the split holds. The `screens` half does not: the rule "no decision in a `.tsx`" is restated in eight
plans and not kept, and three panels are one panel copied.

### Scope covered

**Read in full, with line numbers:** `gui/src/api/*` (client, types, token, signIn), `gui/src/app/*`, `gui/src/state/*`, `gui/src/main.tsx`,
every file of `gui/src/lib/` but the tails of `layout.ts` (80-293) and `layoutAnswers.ts` (60-137); every file of `gui/src/screens/`;
of `gui/src/components/`: `VariablePanelView`, `VariableKeysTable`, `KeyChooser`, `FileActionsView`, `FilesTableView`, `ValuesGridView`,
`ValuesPlotView`, `DeclarePanelView`, `DimensionsField`, `ConstantPanelView`, `TypePanelView`, `SharedAddView`, `SharedTableView`,
`FindingPanelView`, `CompareView`; `ui/Table.tsx`; `gui/scripts/*`, `gui/package.json`, `vite.config.ts`, `tsconfig.json`, `biome.json`;
`src/ddd/gui/contract.py`, `queries.py`, `routes.py`, and as the twins of the page's rules `object_values.py`, `variable_keys.py`,
`finding_routes.py`, `models/conversion.py`, `models/objects.py`, `models/component.py`, `models/common.py` 120-224, `lsp/units.py` 80-160 and
221-460, `value_identity.py` 40-80, `gui/api.py` 215-325, 1219-1247, 1395-1461, 2386-2420. `tests/test_gui_contract.py`. The "Left open" of every GUI plan.

**Read in part:** `UnitPanelView`, `SectionPanelView`, `RasterPanelView` (first half, the rest by search); `UnitsTableView`, `TypesTableView`,
`FindingsTableView`, `CompareTableView`, `UndoStripView`, `AdoptBannerView`, `Changes`, `UnitPicker`, `FlowEdge`, `ModuleNode`, the rest of `ui/` (searched
for domain words, none found). **Not covered:** `styles/`, `stories/`, `.ladle/`, the journeys beyond searching them, `gui/session.py` and `server.py` (passes 2 and 12).

**Ran:** the import graph (`tsgraph.py` -> `graph.txt`); sizes, prose, decisions and likeness of the panels (`measure_fe.py` -> `measure_fe.txt`); the contract's surface
(`probe_contract.txt`); a dozen mutations through `tsc` and vitest on a scratch copy (`mutate.py` -> `mutate.txt`; baseline tsc 0 errors, vitest 959 of 959);
the page's own `lib` functions, run unbuilt under node, against a real `ddd gui` over HTTP (`probe_numbers`, `probe_tables`, `probe_u64`, `probe_declare`, `probe_rules`, `probe_rest`,
`probe_guard`, `probe_limits`, `probe_misc`, `probe_removal`, `probe_offered`, each `.py` and `.txt`), and the real page in Edge over a real `ddd gui` (`browser/*.mjs` ->
`browser_u64.txt`, `browser_limits.txt`, `browser_paste.txt`). I did not run pytest or the journeys. One side effect: the mutation run went through a junction to `gui/node_modules` and rewrote vitest's
cache there (`.vite/vitest/.../results.json`, git-ignored); the junction is gone and `git status` is clean at `35aca14a`.

### Strengths

- **The direction of the imports is sound, measured.** 116 production files. No cycle of value imports between files, and one of types (`lib/layout.ts`, `lib/layoutAnswers.ts`). `lib` imports nothing from `app`, `screens`,
  `components` or `ui`; `components` nothing from `screens`, `app` or `state`, and from `api` only types (22 of 22). Two cycles between folders, none between files of them, both cheap (M2).
- **The views are pictures of their props.** Across 29 files of `components/`: no `useState`, no `useQuery`, no `useMutation`; one `useEffect` (a scroll, in `FindingsTableView`) and two `useRef` (that box; a focus, in `FileActionsView`). All 37 queries and 15 mutations are in `screens/` and `app/`.
- **Shapes on the wire are one definition.** 133 generated names, from the models the server validates and answers with, regenerated in CI before the type check and never committed. Renaming one field gives 58 type errors. Queries go through `queryOf<Q>`,
  so a parameter the server does not take fails the type check.
- **No refusal text is matched by the page.** No `message.includes`, no prefix test: the page looks at codes only and draws the server's sentences as they come. `CompareReply.baseline_findings` is told apart structurally.
- **A plan is the server's.** The page never computes an operation or a hunk: it asks, draws the hunks, posts the operations back. It sends text for a constant's value, a section's and a raster's keys and a unit, and the server judges it in its own
  words (`probe_rules.txt` 2, 3): `5.0` stays `5.0`, and the largest uint64 as a constant's value comes through exact. This is the right pattern, and C1 is what the page gets where it does not follow it.
- **What can be asked is mostly answered, not restated:** `kinds`, `scopes`, `creatable`, `adoptable`, `carried`, `choices`. The add form's composed definition was judged right by the server on 24 of 24 combinations (`probe_declare.txt`), both storages and neither refused in the server's words.
- **The hand tables agree today.** 12 of 12 (`probe_tables.txt`); `offers` against the plans 12 of 12 answers; "may this go" 7 of 7; `ADDRESS_LIMIT` is exact to the byte (65521 answered, 65522 is 414); `segments` 13 of 13 spellings.
- **Dependencies:** six in production, each used, each where it should be (`react-aria-components` in `ui/` alone, `dagre` in the worker's chunk alone, measured in the bundle). A licence gate. Nothing to remove.
- **The server decides little that is the page's.** `Route.kind` and `EDITORS` speak of screens and fields (pass 2 I8), and from this side that costs only their words: the page maps them one to one.

### Issues

#### Critical

- **C1. The grid holds a 64 bit integer as a double: a value past 2^53 is shown wrong, and a typed or pasted one lands in the file as another number, without a word.**
  `gui/src/lib/objectValues.ts:104` (`Number(text)`), `:32`, `gui/src/api/client.ts:366`, `src/ddd/gui/contract.py:1447`, `:1411`, `:1437` (`float` on the wire), `gui/src/components/ValuesGridView.tsx:211`.
  Trigger, in the real page (`browser_u64.txt`, `probe_u64.txt`), a `uint64` block whose file holds `[9007199254740993, 18446744073709551615]`:
  the wire answers `[[9007199254740992.0, 1.8446744073709552e+19]]`, and the grid shows `9007199254740992` and `18446744073709552000`, a number the datatype cannot hold, under a meta line reading `0 … 18446744073709552000`.
  Typing the 64 bit mask `0x8000000000000001` (`Number` takes hex) offers `Sets element 1 of u64_block to 9223372036854776000`; Apply writes `9223372036854776000`, which is `0x80000000000000C0`: bit 0 gone, bits 6 and 7 set, no finding, since it fits. Typing `9007199254740993` writes `...992`.
  Pasting `9007199254740993, 9007199254740995` plans `9007199254740992, 9007199254740996`. Typing the file's own `18446744073709551615` is refused with `18446744073709552000 does not fit into uint64`, a number nobody typed. Expected: what was typed, or a refusal.
  It contradicts `models/common.py:206` ("the range of a 64 bit datatype does not survive a float") and `models/conversion.py:357`. No test holds a value past 2^53 through the page or the wire, and no spec mentions it (`grep`: none). Narrow, and silent where it bites: it reaches the C of every component reading the value.
  *Change:* text across the line (the boundary below, move 1): cells answered as exact text, what was typed sent as text, parsed, converted and rounded by the server. M. A stop-gap in hours: refuse any whole number whose text does not survive `Number`, and say the grid cannot show it.

#### Important

- **I1. `settle` and `type-plan` take any value, so the page is the only guard of what a file can hold, and its guard passes what the loader refuses.** `src/ddd/gui/api.py:1219`, `gui/src/lib/variableKeys.ts:468` (`limitsRaw`), `:491`.
  Trigger (`browser_u64.txt`): open the `limits` row of a `uint64` measurement stating `max 18446744073709551615`, typing nothing. The Max field reads `18446744073709552000`, the row `will change`, Apply is offered. Pressed, it writes that number and `a.ddd.json` stops loading: `schema`, "does not fit 64 bits". Undo puts it back.
  Asked without the page (`probe_guard.txt`): `datatype "uint7"`, `unit 5`, a conversion with factor 0, `size 0`, `dimensions "N"` are each planned and applied by `settle`, and the files stop loading; a type's `limits` with max below min likewise. The vocabularies' plans refuse all of it (`project_shared.Vocabulary`'s judges, 3 of 3), and so does `value-plan` (2 of 2).
  `KNOWN` as a design: spec `2026-09-20-gui-other-keys-design.md` 4.2 ("the page sends only a value one of section 4.1's editors can produce"). It contradicts `variableKeys.ts:464-466` ("a pair the models refuse ... never becomes a value to settle on"). Adds to pass 2 I3: a second client has no guard at all here.
  *Change:* one judge, the models asked of the definition as the plan would leave it, in `settle` and `type-plan`, as the vocabularies have; what is wrong only in context stays written and reported, as the spec rules. The page's Min and Max travel as text. S to M.

- **I2. A variable stating no limits cannot be given any: Min and Max end in "Nothing to change".** `src/ddd/lsp/edits.py:549` (`key in DEFERRED_KEYS and stated is None`), `gui/src/components/KeyChooser.tsx:81`.
  Trigger (`browser_limits.txt`): a measurement with no `limits`, its row selected, Min `0`, Max `100`: the section reads `Nothing to change`, no Apply, the file untouched; the same on a variable of two declarations (`probe_limits.txt`). The rule that a declaration may defer to whoever states limits is applied when nobody does.
  It contradicts spec 5.2 ("a min and a max ... before it offers to apply") and `gui/src/lib/declarations.ts:36` (`limits` "left for the key chooser to add afterwards"): a declaration made in the GUI can never have limits. No journey has this case; every one starts from stated limits. A type's limits work.
  *Change:* where no declaration states the key, the settlement writes it, at least on the producer. S; which declarations is a decision (question 3).

- **I3. The component's table is a second reader of the file format, in a `.tsx`, and it is wrong twice.** `gui/src/screens/ComponentPage.tsx:150`, `:46`, `:166-169`, the claim at `:157-161`.
  The one screen with no read model: it reads `GET /api/file` by string pointers. Trigger (`browser_u64.txt`, `probe_offered.txt`): a `value_block` or `measurement` naming a *scalar* type with dimensions has no button in its Shape cell, on the comment's ground that such a declaration is structured and the dictionary holds no such object; `GET /api/values` answers it (`typed_block` 200, `[4]`, by its address it edits and writes correctly, `probe_misc.txt`).
  A `curve` naming a structure has the button, and the grid answers 404. And the Unit column reads `none` for every declaration naming a type (`typed_block`, `typed_meas`, `cur_typed`: `Speed_t` fixes `rpm`), with the panel beside it saying `rpm, from Speed_t`.
  `docs/file_formats/types.rst:193` describes naming a scalar type as how components agree about a value, so this is an ordinary project. The comment reasons from `examples/`, where every `typename` is a measurement or a parameter. *Consequence:* each of these rules exists twice, the second copy unreachable by vitest.
  *Change:* `GET /api/component?file=` answering rows - scope, name, kind, type, effective unit, shape text, whether a grid opens, asked of the code that draws the grid. The page loses `SHAPED_BY_KIND`, `shapeOf`, `offered`, `valueAt`, `lib/values.ts`, `lib/formats.ts`. M.

- **I4. "A file-format change the page has not caught up with fails the build" is false.** `gui/scripts/schemas.mjs:1-3`, spec `2026-09-17-web-gui-design.md:401-403`, `gui/src/lib/formats.ts:4`, `src/ddd/gui/contract.py:415`.
  Trigger (`mutate.txt`): renaming `kind`, then `interface`, throughout `generated/component.ts`: tsc exit 0, vitest 959 of 959. `ComponentPage` reads `data` (`Any`) through strings; the type guards one `?.component?.name`, behind a cast. Of the eight generated file-format modules, one type of `component.ts` and one of `sections.ts` are imported; `constants`, `dictionary`, `project`, `rasters`, `types`, `units` by nothing (`graph.txt`).
  *Change:* with I3 gone there is nothing left to guard; `SectionAccess` can come from the contract, and `schemas.mjs` loses its first half. S after I3. Until then, correct the two sentences.

- **I5. The shapes are one definition; the routes, the replies, the refusal codes and the kinds are not.** `src/ddd/gui/routes.py:41` (a `Route` names no reply), `gui/src/api/client.ts:154` (`body as T`, 35 sites), `gui/src/lib/findings.ts:256`, `gui/src/api/client.ts:183`, `src/ddd/gui/contract.py:1415`, `:1434`, `gui/src/lib/refusals.ts:30`.
  Trigger, measured (`mutate.txt`, table below): `FindingRoute.kind` gaining a word passes tsc and vitest, and `routeOf` opens the component's page for it - the very failure `finding_routes.py:210-224` spends a docstring guarding on the Python side, which stops at the contract. A new parameter of `FindingsQuery` is dropped by `findingsQuery`'s hand list, silently. A conversion kind added to the models reaches `physicalOf` and `rawOf`, which compute with it, as `{[k: string]: unknown}`, and reads as the identity.
  A wrong path passes tsc, and fails vitest only because `client.test.ts` keeps its own list; nothing compares that list with `ROUTES`. The error body and its codes (`stale`, `unreadable`, `not-found`) are in no schema: 21 string comparisons, pinned by journeys.
  *Change, in order:* `switch` with `never` in `routeOf`, `findingsQuery` through `queryOf`, the codes as a `Literal` in the contract (S together); a `reply` on `Route`, a generated route table, one generic `ask(route, query)` replacing 35 hand pairings (M); `Conversion` typed, or gone from the page with C1's move.

- **I6. Three panels are one panel, copied; two more are nearly.** `gui/src/screens/{Constant,Section,Raster}Panel.tsx`, `gui/src/components/{Constant,Section,Raster}PanelView.tsx`, also `UnitPanel`, `TypePanel`. `KNOWN` in part (`2026-10-08-gui-journeys-every-action.md`, P19b-24; `2026-09-28-gui-rasters.md`).
  Measured (`measure_fe.txt`, code lines with each vocabulary's noun normalised): screens 0.84-0.86 alike, `UnitPanel` 0.70, views 0.80-0.81. `Outcome` four times; `use*Plan` five; `refusalOf` three times, two of them identical (`UnitPanel.tsx:35`, `TypePanel.tsx:40`), eight screens importing it from `UnitPanel`; the test for a stale refusal in 13 places of ten files, `isStale` used by one; `Apply to {n} file` six times; `routeOfUse` three times.
  *Consequence, already happened:* the panels differ on what a refusal leaves standing (P19b-24, "the unit panel keeps its Apply, the type panel withdraws it"), `TypePanelView` decides a route in a `.tsx`, and a fourth vocabulary falls through to a constant's panel in four unguarded chains (`SharedPage.tsx:152-168`).
  *Change:* one `useOffers(requests, ask, label, invalidate)` and one `Outcome`, `refusalOf` beside `isStale` in `lib/refusals.ts`; a panel keeps its fields. By my estimate about 600 of the five panels' 2,200 lines of code go, and there is one rule for a refusal. M. A generic vocabulary panel on `Vocabulary`'s descriptor is a further decision (question 4).

- **I7. The rule "no decision may live in a `.tsx`" is not kept, and what breaks it is reachable only by a browser journey.** Stated in eight plans (`2026-09-28-gui-rasters.md:43` ...) and at `gui/src/app/useDebounced.ts:24`. `KNOWN` (`2026-09-20-gui-other-keys.md`, "A screen's own state is guarded by the journeys alone"; `2026-10-08-gui-journeys-every-action.md`).
  Measured: `screens/` 3,608 lines of code, about 600 conditionals (a rough count), 119 `useState`, no unit test; vitest's gate reaches `api`, `lib`, `state`. Decisions that are no wiring: `ComponentPage.tsx:44-65,166-169`, `DeclarePanel.tsx:41-60` (`requestOf`), `TypePanel.tsx:197-204` (`active`), `VariablePanel.tsx:162-194` (`selected`, `range`, `target`), `UnitPanel.tsx:35`, `DeclarePanelView.tsx:43-56` (`scopeOf`), `ConstantPanelView.tsx:76,262-287`, `TypePanelView.tsx:68-69,279-291`.
  Mutation: `SHAPED_BY_KIND` losing `map`, `refusalOf` inverted: tsc 0, vitest 959 of 959 (`mutate.txt`). Only a journey can catch them, and a journey has the example's cases, which is how I3 lived.
  *Change:* move what is listed into `lib`, S each. Then either enforce the rule (a lint on what a screen may contain) or restate it as "no domain decision", which is what is worth keeping (question 5).

- **I8. A plan is a GET, so the request line bounds what can be pasted.** `gui/src/api/client.ts:381`, `:394`, `src/ddd/gui/api.py:1687`. `KNOWN` by design (`2026-09-24-gui-paste-design.md:166`).
  Trigger (`browser_paste.txt`): a 128 by 128 table of whole counts: `'table_128' has too many values to plan in one request: its counts need 96467 characters of address, and ddd gui reads at most 65521`. The limit is http.server's, the page carries it as a constant, and past about 8,000 to 10,000 whole counts, or 2,500 with long decimals, a reader has no way in the GUI to set a table but cell by cell. Nothing in the domain asks for it.
  *Change:* `POST /api/values-plan` with the counts in the body, gated as any POST is. S; the constant goes.

#### Minor

- **M1. The first vertical became the library.** `gui/src/lib/units.ts:186` (`baseName`), `:161` (`consequence`), `:177`, `:208`; `gui/src/lib/projectUnits.ts:218`; `gui/src/screens/UnitPanel.tsx:35`; `gui/src/components/UnitPanelView.tsx:23`. `lib/units.ts` has the highest fan-in of `lib` (25), for helpers about plans and paths: 12 importers each of `baseName`, `consequence`, `shownChanges`. `planEdit` is `shared.planEdit` -> `projectUnits.planEdit` -> `units.editOf`, and `findings.fixEdit` writes `editOf` again; `nonEmpty` and `owner` twice. `VariablePanelView` types its removal from a unit's panel. Read off the graph. *Change:* `lib/plans.ts`, `baseName` to `lib/paths.ts`, the wrappers gone. S.
- **M2. Two cycles between folders, one edge the wrong way, and nothing guards the direction.** `gui/src/api/client.ts:1` (into `state/edits`) with `gui/src/state/revisions.ts:1`; 28 imports from `screens` into `app`, which imports every screen; `gui/src/ui/Table.tsx:12` takes `ROW_HEIGHT` from `lib/findingsWindow`. `state/` is an in-memory store, `localStorage` for the canvas and the long poll: three things. `graph.txt`. No test or lint looks at imports in `gui/src`. *Change:* `revisions.ts` to `api/`; `app/` split into the root and `hooks/`; `postEdit` not noting into a store (a caller does, or a listener); `ROW_HEIGHT` in a leaf; a thirty line vitest walking imports. S.
- **M3. The Files tab's hold re-derives what the plan did, from its operations.** `gui/src/lib/filesHold.ts:49` (the pointer's regex), `:53`, `:103` (a path join), `:82`. Trigger (`probe_rest.txt`): `extra\x3.ddd.json` and `EXTRA/X1.DDD.JSON` on Windows: the held row's key is not the server's, and it reads "not read by the last analysis" until the list answers. The plan notes links, not these. *Change:* `FilesPlanReply` carries the row it adds and the key it removes; `INSERTED`, `ABSOLUTE`, `joined` go. S.
- **M4. Small divergences in the page's arithmetic.** `gui/src/lib/objectValues.ts:41` against `models/conversion.py:353` ("as `round_physical` takes it off"): exact ties differ, 2,321 of 60,000 random values (`probe_numbers.txt`), `1234567890.125` reads `...13` and `...12`; display only. `:37`: `Math.round` makes `2.5` 3 and `-2.5` -2, and `0.6` typed into a boolean in Physical stores `1` where Raw refuses it (`probe_misc.txt`). `1,5` is refused typed (`:104`) and read as 1.5 pasted (`:165`). All go with C1's move, but for the paste's own reading of a comma, which is the page's.
- **M5. A label cut through a surrogate pair refuses the edit.** `gui/src/lib/undo.ts:143`. Trigger (`probe_rest.txt`): a rename of a unit spelled with emoji past the limit: `POST /api/edit` answers 400, `lone leading surrogate`. It contradicts "no edit is ever refused for the length of a name". Rare. *Change:* cut by code point. S.
- **M6. Small tables and sentences held twice, agreeing today, pinned by nothing across the line.** `lib/shared.ts:201`, `:237`, `lib/projectUnits.ts:12`, `lib/undo.ts:16`, `lib/findings.ts:324`; `lib/objectValues.ts:94`, `:139`, `:292`, `screens/ValuesPage.tsx:283`, `components/ValuesGridView.tsx:173` with `object_values.py:312,314,317,325,348,421`. And twice on the page itself, "kept here too": `KIND_WORDS` (`lib/projectTypes.ts:5`, `components/TypePanelView.tsx:52`), the scope words (`lib/declarations.ts:7`, `components/DeclarePanelView.tsx:43`). Drift is loud or only wording. *Change:* `ValuesReply` says why a grid is read-only, in a field; the file name adopted, in `UnitsReply`; the rest stay. S.
- **M7. Words and code about the contract that nothing holds.** `gui/src/api/types.ts:1-4` says a model without a page type "fails the build": 43 generated names are not re-exported and nothing fails, and 18 of the 90 hand-listed are imported by nothing (`probe_contract.txt`). *Change:* `export type * from "../generated/api"`. `gui/src/screens/FindingsPage.tsx:205` invalidates a key no query has. After an undo one predicate says what is asked again (`lib/undo.ts:209`), after an Apply each screen lists its own: one policy would do. `GET /api/checks` and `GET /api/dictionary` have no client in the page. S.
- **M8. A raster cannot be made acyclic from its panel.** `gui/src/lib/shared.ts:243`. Emptying Cycle sends `""`, refused (`browser_paste.txt`); the plan route takes the key away with `raw` left out, and no field asks that. `KNOWN` (`2026-09-28-gui-rasters.md`, "How a reader clears an optional string wants a design answer"). *Change:* an empty field on an optional key sends no `raw`. S.
- **M9. The panel and the checker disagree about limits past 2^53.** `src/ddd/value_identity.py:63` (`float(bound)`). `ddd check` reports `definition-mismatch` on `...992` against `...993` (`same_value/`), while `same_value` makes them one value (`probe_rest.txt`), so the panel shows no disagreement and settling says nothing to change: read off `variable_keys.py:235`. Against `value_identity.py:41-43` ("a caller has to group values the way the checker does"). *Change:* compare the exact numbers. S.
- **M10. 145 citations of planning artefacts in 51 files of the page, 184 of spec sections, and 40 % of `lib` is prose.** Beside pass 2 M9. Essays on column widths "measured in Chrome (fix round 3)" in 8 views, `useDebounced.ts` 52 lines of prose on 19 of code. Several no longer hold: `lib/shared.ts:9` and `SectionPanel.tsx:115` say no gate executes a `.tsx`, where CI's journeys do. *Change:* what a reader needs stays, with the history in the plans. S.

### Status of the 2026-09-15 findings in this area

None. That review predates `gui/` (the web GUI's design is of 2026-09-17): `SCRATCH/review-2026-09-15.md` has no finding on the page or on `ddd gui`.

### Open questions

1. **Must a 64 bit integer be exact in the GUI?** Yes, as I would answer and as the models say: C1's move, M. No: a refusal past 2^53, in hours, and the grid says it cannot show such a value.
2. **Does `settle` get a judge, against spec 4.2?** Yes: I1's change, and a batch tool inherits the guard. No: the page stays the only guard, a hole like C1's is a corrupt file each time, and a second client should be told.
3. **When nobody states `limits`, whom does a settlement write to?** The producer alone keeps "a consumer defers"; every declaration matches what the panel says of every other key. I2 wants one of them.
4. **One panel per vocabulary, or one panel?** The plans keep each table's facts concrete on purpose. One panel driven by `Vocabulary` makes a fourth vocabulary a data change and costs that concreteness; `useOffers` (I6) is worth doing either way.
5. **Is "no decision in a `.tsx`" still the rule?** As stated it asks for what no React screen can give. "No domain decision, and nothing a test should reach" is keepable, and a lint can hold part of it.
6. **Is a table past about 10,000 counts one the GUI should take?** If not, I8 is a sentence in the guide and nothing else.

### Test gaps

- No value past 2^53 anywhere: not in `test_object_values.py`, `test_gui_api.py`, `objectValues.test.ts`, `values.spec.ts`. The contract's `float` fields have no test of exactness.
- No differential between the page's rule and Python's, for any row of the table below. Each side pins its own literal: `segments`, `rounded`, `LIMIT`, `SECTION_STRINGS`, the codes. A pytest reading a table the server publishes, or a vitest run against a captured reply, would hold them.
- No journey on a `value_block` naming a scalar type, on a type's unit in the component's table, or on limits added to a variable with none (I2, I3). The journeys use the examples' shapes.
- A new `FindingRoute.kind`, a new `editor`, a new `FindingsQuery` parameter, a conversion kind: nothing fails (I5).
- `client.test.ts`'s list of paths is compared with nothing on the server, and `ROUTES`' reply with nothing at all.
- Nothing guards the direction of imports in `gui/src`.

### Assessment

The maintainer's question, for this boundary: **yes, for the most part, with three leaks worth closing before 1.0.** The server owns plans, diffs and the vocabularies' judgement, the wire's shapes are generated and no refusal text is matched: that is the hard part, and it is right. Where the page goes through a number instead of passing text, or reads a file instead of asking, or is trusted because the server does not check, it is wrong on a plausible project (C1, I1, I2, I3), and 959 unit tests at 100 % see none of it, because each side tests its own copy. None of the moves is large, and most remove page code. Inside the page the layering is sound and the views are clean; the screens carry too much, three of them are one, and the helpers that everything uses still live where the first feature put them. I would close C1 first, then I1 and I2, and treat I3 as the move that also ends the file-format generation.

#### The measured graph

Folder to folder, production files, value imports / type-only imports (`graph.txt`). Files and lines, code and prose: `app` 9, 704 (30 % prose); `screens` 19, 5,042 (27 %); `components` 29, 4,451 (23 %); `ui` 8, 351 (29 %); `lib` 33, 5,106 (40 %); `state` 3, 177 (30 %); `api` 4, 706 (23 %); `generated` 9, 6,560.

```
from\to       app   screens components   ui      lib     state    api    generated
main          2/0     .         .         .       .        .      1/0       .
app           4/0   12/0       1/0       4/0    10/3      2/0     3/3       .
screens      28/0   17/0      21/1      39/0    70/9      3/0    18/12      .
components     .      .       23/1      68/0    47/7       .      0/22      .
ui             .      .         .        1/0     1/0       .       .        .
lib            .      .         .         .     20/5       .      2/25     0/2
state          .      .         .         .       .        .      1/1       .
api            .      .         .         .       .       1/0     3/2      0/1
```

Going the wrong way: `screens` -> `app` (the hooks), `api` -> `state` (`client.ts`, `ownEdits`), `ui` -> `lib` (`ROW_HEIGHT`); and worth a look, `lib` -> `api/client` by value, twice, for `ApiError`. `api` <-> `state` is a cycle of folders, not of files. Highest fan-in: `api/types` 61, `api/client` 28, `lib/units` 25, `ui/Button`, `ui/Banner` 22, `lib/route` 18, `lib/findings` 17. `screens/UnitPanel` has 8, for `refusalOf`.

**What the folders mean.** `ui`: what it says, widgets over React Aria. `components`: the views, plus a few widgets of the domain; what it says. `screens`: queries, state and, against the rule, decisions. `lib`: pure and framework-free but for `canvas.ts` (`@xyflow/react`) and `layout.ts` (`dagre`); the name hides three kinds of thing (wording, the page's state machines, copies of domain rules, the last of which should shrink). `api`: what it says, but for noting edits into a store. `app`: the root and the hooks, two things. `state`: three things. **Files of several hundred lines:** `variableKeys.ts` (494) is four jobs (the table's rows, wording a value, the chooser's sections, a range's fields), and four modules import `shortValue` from it, three of them for that alone; `shared.ts` (409) is three families copied per vocabulary, 40 % prose; `ComponentPage.tsx` (429) is a format reader and a table; `SharedPage.tsx` (396) a page and a form. `canvas.ts`, `files.ts`, `findings.ts`, `client.ts`, `FileActionsView.tsx`, `GraphPage.tsx` are long and cohesive: leave them.

**Justified by the job:** the long poll and revision keys; dagre in a worker (measured by them at 475 to 1,164 ms for 3,333 components); virtual tables and the findings window (25,000 findings); `useKept` and the holds as display, given an edit is answered before its analysis (a 500 ms budget at 100,000 declarations). **Simpler with no loss:** I6; `api/types.ts`; `client.ts`'s 40 functions, once a table is generated; the page's half of the holds that re-derives a plan (M3); invalidation lists (M7).

#### Every domain rule the page holds

"Diverged" means I made them disagree on a real `ddd gui`. "Judged" means the server has the last word, so drift costs a refusal rather than a wrong file.

| rule | page | python | state |
| --- | --- | --- | --- |
| what a typed number is | `objectValues.ts:104` | `gui/api.py:2386` | **diverged**, C1 |
| physical to raw, and rounding | `objectValues.ts:32` | `conversion.py:129`, no rounding anywhere | **diverged**, C1, M4; the rounding exists on the page alone |
| raw to physical | `objectValues.ts:23,41` | `conversion.py:126,353` | **diverged** at ties, M4; any new kind reads as identity, I5 |
| a range | `variableKeys.ts:446-494` | `objects.py:167`, `common.py:201` | **diverged**, I1; not judged |
| which declarations have a grid | `ComponentPage.tsx:46,166` | `object_values.py:116` | **diverged**, I3 |
| the unit a declaration has | `ComponentPage.tsx:150` | the type's `fixed` | **diverged**, I3 |
| the file format | `ComponentPage.tsx:129-151` | `models/component.py`, `objects.py` | can drift unseen, I4 |
| which limits can be added | field drawn, `KeyChooser.tsx:81` | `edits.py:549` | **diverged**, I2 |
| where an appended entry goes, its key | `filesHold.ts:49,53,103` | `lsp/units.py:104`, `resolve_path` | **diverged**, transient, M3 |
| the storage a kind asks; identity beside a datatype | `declarations.ts:41,75` | `objects.py:384,400,415` | agrees, 24 of 24; judged |
| a dimension | `declarations.ts:82` | `objects.py:87` | agrees on 11 spellings; judged |
| a size typed | `variableKeys.ts:422` | `objects.py:87` | agrees; not judged, I1 |
| a section's, a raster's json strings | `shared.ts:201,237` | `project_shared.py:775,970` | agrees; judged; unpinned, M6 |
| what `add` requires | `shared.ts:269-321` | `project_shared.py:703,780,975` | agrees, 3 of 3; judged |
| a section's access | `shared.ts:59` | `models/sections.py`, by the generated type | one definition |
| may this go | `ConstantPanel.tsx:142`, `SectionPanel.tsx:132`, `shared.ts:344` | `shared_plans.py` | agrees, 7 of 7; judged |
| what a unit offers | `projectUnits.ts:93` | `lsp/units.py:261,288,312` | agrees, 12 of 12; judged |
| which check a unit's findings are | `projectUnits.ts:54` | `finding_routes.py:26` | agrees by reasoning; not run on a project of several images |
| a component needs a name | `files.ts:185` | `file_plans.py` | agrees, 6 of 6; judged |
| what a cell write does to `stated` | `valuesHold.ts:45` | `object_values.py:331` | agrees; display only |
| why a grid is read-only; two more sentences; `table`; `elementLabel` | `objectValues.ts:94,139,292`, `ValuesPage.tsx:283`, `ValuesGridView.tsx:173` | `object_values.py:312-325,348,421` | agrees; wording, M6 |
| the pointer grammar | `pointer.ts`, `findingsByRow.ts:49`, `findings.ts:344`, `ConstantPanelView.tsx:76`, `variableKeys.ts:223`, `objectValues.ts:286`, `filesHold.ts:49` | `lsp/ranges.py` and pass 2 M8's regexes | `segments` agrees, 13 of 13; nine sites; unowned |
| which file kinds have a screen; why a finding leads nowhere | `findings.ts:324,337` | `finding_routes.py:232` | agrees on the probes; wording |
| route kind to screen | `findings.ts:223` | `finding_routes.py:205`, `contract.py:274` | not exhaustive, I5 |
| the vocabularies | `route.ts:19`, `shared.ts:19,49` | `project_shared.py:993` | agrees; KNOWN four chains |
| kinds of type; scopes | `projectTypes.ts:5,28`, `declarations.ts:7` | `models/types.py`, `component.py:16` | agrees; each twice on the page, M6 |
| a conversion's kind left out | `variableKeys.ts:252` | `conversion.py:274` | agrees on 8 of 9, the ninth a block the models refuse |
| refusal codes | `refusals.ts:30,67`, 13 sites | `editing.py:60`, `gui/api.py` | agrees; journeys pin, I5 |
| a label's length; the adopted file | `undo.ts:16`, `projectUnits.ts:12` | `contract.py:1662`, `lsp/units.py:43` | agrees; M5, M6 |
| the request line | `client.ts:381` | http.server | agrees to the byte; I8 |
| which reads follow the analysis | `undo.ts:190` | each route of `gui/api.py` | unpinned, cannot be measured from outside |
| units in play | `units.ts:224` | `variable_keys.py:217` | agrees; the reply already says it |

Rules the page holds alone, rightly: what a paste means (rows, tabs, a decimal comma), debouncing, selection, labels, the sentences of a consequence. Wrongly alone: rounding a physical value to a count.

#### What is generated, and what is mirrored

| crossing | how it is defined | what a change does (`mutate.txt`) |
| --- | --- | --- |
| a reply's or a query's shape | generated, 133 names | a field renamed: **tsc fails, 58 errors** |
| a query's parameters | `queryOf<Q>`, but `findingsQuery` lists its own | a new one: passes, dropped |
| path and method | literals in `client.ts` | wrong path: tsc passes, vitest fails on the page's own list; a server rename fails only journeys |
| which reply a route gives | `request<T>`, `body as T`, 35 sites; no reply on `Route` | unchecked |
| error body, codes | by hand | page's spelling changed: vitest fails on its own literal; a server rename fails only journeys |
| `FindingRoute.kind`, `editor` | generated `Literal`, used non-exhaustively | a new word: **passes everything** |
| `Conversion` | `dict[str, Any]` by decision, computed with on the page | a new kind: **passes everything** |
| `FileContent.data` | `Any`, read by string pointers | a key renamed: **passes everything** |
| `SharedEntry.kind`, `ProjectType.kind`, `SourceFile.kind` | `str` by decision | falls through a chain |
| `stated`, `fixed` | `dict[str, str]` of json text | parsed where read |
| names the screens import | hand list of 90 in `api/types.ts` | nothing, M7 |
| refusal sentences | shown, never matched | nothing to drift |

#### The boundary I would draw

**The page holds what a person sees and does: words, layout, selection, focus, drafts, debouncing, what is drawn while an analysis catches up. The server holds what a project is and what a value means: reading a value, converting it, rounding it, whether a file could hold it, what a declaration resolves to. Text crosses the line; numbers do not, but for drawing.** The page should never compute a value that ends up in a file, and never read a description file.

| # | move | what crosses | removes | size |
| --- | --- | --- | --- | --- |
| 0 | Guards first: exhaustive `routeOf`, `findingsQuery` through `queryOf`, codes as a `Literal`, `export type *`, an import walk as a ratchet | nothing | half of I5, M2's silence, M7 | S |
| 1 | Cells as exact text: `ValuesReply` answers `rows` and readings as text, axes likewise; `value-plan` and `values-plan` take what was typed and `physical` or `raw`; the server parses, converts, rounds, judges, and says what it stored | `typedNumber`, `rawOf`, `physicalOf`, `rounded` to the server; the plot parses text to draw | C1, M4 | M |
| 2 | One judge in `settle` and `type-plan`; Min and Max as text; the limits of a variable that has none | `limitsRaw` to a template; the rule to the models | I1, I2, M9 | S to M |
| 3 | `POST /api/values-plan` | `ADDRESS_LIMIT` goes | I8 | S, with 1 |
| 4 | `GET /api/component` | `SHAPED_BY_KIND`, `offered`, `shapeOf`, the raw reads to the server; then the file-format half of `schemas.mjs` goes | I3, I4 | M |
| 5 | Plans carry what the page now derives: `FilesPlanReply`'s row and key; `ValuesReply`'s read-only sentence; the adopted file's name | `INSERTED`, `joined`, `readOnlyNote`, `ADOPTED` | M3, M6 | S |
| 6 | Inside the page: `lib/plans.ts`; `refusalOf` in `lib`; one `useOffers`, one `Outcome`; the decisions of I7 into `lib`; `revisions.ts` to `api/`, `hooks/` out of `app/` | none | I6, I7, M1, M2 | M |
| 7 | A generated route table: `reply` on `Route`, one `ask(route, query)` | the 35 pairings become one | the rest of I5 | M |
| 8 | One vocabulary panel, if question 4 says so | the panels' key lists to `Vocabulary` | about 400 more lines | M |

About two weeks in all; 0 to 3 are three or four days and stand on their own, and 1 and 2 are the ones that change what a user can lose. **Across the line the other way:** nothing that needs doing now. `Route.kind` and `EDITORS` could name what a finding or a key is about rather than a screen and a field, as pass 2's move 7 will do anyway.

**What I would leave exactly as it is:** the plan, preview and apply round trip, with operations posted back as data; refusals as the server's sentences; `contract.py` and `queries.py` as the wire (pass 2 agrees); the views as pictures of their props, with stories and screenshots on them; `ui/` over React Aria; `useDebounced`, `planShown`, `useKept`, `panelShows`, the findings window, the layout worker: each answers a measured problem, and each is the page's; the paste parser; six production dependencies.

```candidates
3|C1|gui/src/lib/objectValues.ts:104|The grid holds 64 bit integers as doubles: past 2^53 it shows wrong and writes another number without a word (a typed mask loses bit 0)
3|I1|src/ddd/gui/api.py:1219|settle and type-plan take any value, so the page is the only guard, and opening a uint64's limits row offers a write the loader refuses (KNOWN as design)
3|I2|src/ddd/lsp/edits.py:549|A variable stating no limits cannot be given any: Min and Max end in Nothing to change, against spec 5.2 and declarations.ts:36
3|I3|gui/src/screens/ComponentPage.tsx:150|The component's table reads the raw file in a tsx: a type's unit reads none, a block naming a scalar type has no grid button, a curve of a structure has one
3|I4|gui/scripts/schemas.mjs:1|A file-format change fails the build is false: renaming kind or interface in the generated types passes tsc and vitest; six of eight modules unused
3|I5|src/ddd/gui/routes.py:41|Shapes are one definition; routes, replies, refusal codes and kinds are not: a new route kind, query parameter or conversion kind passes every gate
3|I6|gui/src/screens/SectionPanel.tsx:60|Three panels are one panel copied (0.84 to 0.86 alike), Outcome four times, the stale block 13 times; they already differ on a refusal (KNOWN in part)
3|I7|gui/src/app/useDebounced.ts:24|No decision in a tsx is restated in eight plans and not kept: about 600 conditionals in screens with no unit test; mutations pass tsc and vitest (KNOWN)
3|I8|gui/src/api/client.ts:381|A plan is a GET, so the request line bounds a paste: a 128 by 128 table is refused, the page carrying http.server's constant (KNOWN)
3|M1|gui/src/lib/units.ts:186|The first vertical became the library: baseName and consequence in lib/units, planEdit three ways, refusalOf imported from UnitPanel by eight screens
3|M2|gui/src/api/client.ts:1|Folder cycles api and state, screens and app; ui imports lib; state is three things; nothing guards the direction of imports in gui/src
3|M3|gui/src/lib/filesHold.ts:49|The Files tab's hold re-derives a plan's entry by regex and path join; differs from the server on a backslash or another case, until the list answers
3|M4|gui/src/lib/objectValues.ts:41|rounded differs from round_physical at ties; Math.round is asymmetric at half; 0.6 in a boolean stores 1; a decimal comma refused typed and read pasted
3|M5|gui/src/lib/undo.ts:143|fitted cuts a label through a surrogate pair and the edit is refused 400, against no edit is ever refused for the length of a name
3|M6|gui/src/lib/shared.ts:201|Small tables and sentences held twice across the line, and KIND_WORDS and the scope words twice on the page; agree today, unpinned
3|M7|gui/src/api/types.ts:1|The header's fails the build is false, 18 of 90 re-exports unused; a dead invalidation; two policies for what is asked again; two routes with no client
3|M8|gui/src/lib/shared.ts:243|A raster cannot be made acyclic from its panel (KNOWN)
3|M9|src/ddd/value_identity.py:63|same_value reads limits through float: ddd check reports a mismatch past 2^53 and the panel shows one value with nothing to settle
3|M10|gui/src/lib/shared.ts:9|145 citations of planning artefacts in 51 files, 40 % of lib is prose, width essays in 8 views, some no longer true
```

## Pass 4: what does the documentation miss?

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-4/`. Line numbers are on the review tree.

**The answer, plainly.** As a reference, the documentation misses almost nothing: of 72 checks, 15 ELF findings, 21 commands,
26 options, 153 schema keys, 18 CMake keywords, 7 targets and every plugin field, one schema key is left to the generated
reference and nothing else is absent. Few tools can say that, and most of it is held there by tests. What it misses is everything
that is not a reference. `ddd gui`, which is over half the code, has no guide: its only account is one cell of a table on the command line
page, 3,960 words long. No page says how a project with existing C adopts DDD, and the first step a real adopter takes fails at the
link. No page says how to get from the generated a2l to a connected calibration tool. A contributor is not told how to set up a checkout or where
a new endpoint goes. The tutorial's `ddd id --assign` step fails on Windows. The changelog files features under a release that does not have
them and omits a format change altogether. And at 141,627 words the documents are long because the same facts are told up to eight
times, with history and self-defence woven into the reference, so a correction has many places to miss, and several already missed.

### Scope covered

**Built:** `sphinx-build -W --keep-going -b html docs SCRATCH/pass-4/html`, with the system python's sphinx (the review venv has no
`docs` extra), `dot` 15.1.1 and plantuml through `JAVA` and `PLANTUML_JAR`. It **passes under `-W`** (`sphinx-build.txt`), 28 pages. Graphviz was
present, so nothing was left undrawn.

**Read in full, with line numbers:** `README.md`; every page `docs/index.rst` reaches: `getting_started`, `concept`, all nine of
`file_formats/`, `consistency_checks`, `comparing_deliveries`, `plugins`, `generated_artefacts`, `templates`, `command_line_interface`, `toolbox`,
`build_integration`, `editor_integration`, `gui_security`, `data_contracts`, `data_dictionary` (their prose; the generated model reference only by
headings), `developer_documentation`, `faq`, `acronyms`; `docs/conf.py`; `SECURITY.md`; `editors/vscode/README.md`; `CHANGELOG.md:1-240` and
the `## 0.11.0` section by its diff against the tag; `SPEC.md`'s structure, sections 1, 3.6 and 7 to 7.3; `gui/src/app/App.tsx`, `gui/src/lib/route.ts`, and of
`gui/src/screens/`: `GraphPage`, `StartPage`, `ProjectPage`, `UndoStrip`, `FindingsPage`, `ComparePage`, `ComponentPage`.

**Read by their user-visible strings only (pass 3 read them whole):** the other twelve screens and their views (`gui_strings.py`, `inv/gui_strings.txt`).
**Read in part:** `src/ddd/plugins.py:1-240`, `src/ddd/gui/server.py` (header, `run`), `cmake/Ddd.cmake:395-474` and its keywords, the headings of
`tests/test_documentation.py`, `docs/superpowers/specs/2026-09-17-web-gui-design.md` 60-160 and 498-537, the "Left open" of every plan (searched for documentation items).
**Not covered:** the older sections of `CHANGELOG.md`; whether each sentence is right, except where a gap and a wrong sentence are one thing (passes 5 to 20); `docs/superpowers/` beyond the above.

**Run:** the inventories (`inventory_cli.py`, `inventory_checks.py`, `inventory_schema.py`, `shape.py`, `linkcheck.py`, results in `inv/`); `ddd gui` on a scratch copy of
`examples/demo`, walked headless in Edge (`walk.cjs`, `shots/walk.txt`, 17 screenshots in `shots/`; no edit applied); the tutorial's commands under
PowerShell 5.1 and cmd (`inv/windows-tutorial.txt`); a half migrated project through gcc (`inv/half-migrated.txt`); `git` and `gh api` for the changelog and the tracker (`inv/evidence.txt`). The tree is untouched.

### Strengths

- **Tool against documents, the reference is complete and mostly held by tests.** See the inventory below: 72 of 72 checks have a table row at the registry's severity (`inv/checks.txt`),
  `tests/test_documentation.py:192-301` keeps them there; 15 of 15 `elf-*` findings (`docs/toolbox.rst:198-258`); the CLI reference is generated from the parser and every option also has prose;
  the file format pages are generated in part from the models.
- **The commands shown really run.** `tests/test_transcripts.py` re-runs 122 of the 173 commands shown and says out loud how many it does not (`:424-441`, 51). That is unusual honesty, and the tutorial is the better for it.
- **The site builds clean and links clean,** one link apart (M1). `-W` is meant and kept.
- **Good pages exist, and they show what the others could be.** `docs/toolbox.rst` (1,388 words): what it does, an example, a table of where each key comes from, a table of findings. `docs/file_formats/conversions.rst`, `units.rst`, `sections.rst`;
  `docs/comparing_deliveries.rst`'s worked example over shipped deliveries; `docs/getting_started.rst` as a narrative. `docs/faq.rst` asks real questions and answers them.
- **The rationale a future maintainer needs is written down.** `docs/developer_documentation.rst:255-283` records what was tested against CANape; `:765-867` is a precise account of the release and of what guards it.
- **Trust is stated where it counts for the editor:** `docs/editor_integration.rst:212-225`, `editors/vscode/README.md:50-56`, `docs/plugins.rst:245-257`, `docs/templates.rst:73-85` (for the rest see pass 1 I15).

### Issues

#### Critical

None. No gap here produces wrong output by itself. The nearest, nothing warning that `ddd gui` over a collected project loses work, is pass 1 C4's; its documentation half is in I1.

#### Important

- **I1. `ddd gui` has no guide; its one account is a single table cell of the command line page (KNOWN: "part 20").** `docs/command_line_interface.rst:294-567`, `docs/index.rst:25`. KNOWN: `docs/superpowers/specs/2026-09-17-web-gui-design.md:147,509`, `2026-09-30-gui-large-projects-design.md:20` ("the user guide: every screen, with its screenshots"), `2026-10-21-gui-journeys-remaining-design.md:230`. Graded as I would grade it myself.
  *Trigger:* somebody is asked to use `ddd gui` and opens the site. The sidebar's only entry with "GUI" in it is *GUI security* (`index.html`, by script). `concept.rst`, `getting_started.rst`, `faq.rst` and `index.rst`'s prose never name it. The account they eventually reach is row 11 of a `list-table`: 3,960 words of the page's 7,771 (51 %), 274 source lines, no heading, no anchor (`#ddd-gui` lands on the argparse help), no screenshot. It runs from "The project opens on a graph" to refusal sentences quoted verbatim and benchmark figures (`:533-544`, "Measured on a developer's desktop over a generated project of 100,000 declarations").
  *Evidence of what it does not give:* its words follow the order of the plans, not of a reader's questions: Files tab 93 lines, Shared files 57, large projects 35, Units half a sentence, Types 3, Graph 7. Twenty things a reader meets on screen are missing or get one clause, the table below; "Tidy", "Search modules", "Adopt" and "Add to the vocabulary" appear in no document at all (`inv/evidence.txt`, `inv/gui_strings.txt`). A person who wants to know whether a project's units can be adopted finds the answer only in `CHANGELOG.md`'s `## 0.11.0`, whose first bullet (2,139 words) is the other half of the de facto guide.
  *Who:* everybody asked to use the GUI, which is its purpose: "developers who would rather not edit JSON" (`CHANGELOG.md:247`), the readers least able to reverse-engineer a table cell. *Where:* a new `docs/gui.rst`, "The browser interface", under *Using DDD* ahead of the security page: what it is and when to use it, starting it, a tour by task (settle a disagreement, edit a curve, adopt a vocabulary, undo, compare), one short section per tab, what it writes and when, working beside an editor and a build, what it cannot do. The CLI row shrinks to four lines. The refusal sentences go (they are the page's to say, and a test's to pin), the timings go to the developer page. *Size:* M, two to three days, about 2,500 words and ten screenshots, which the Ladle stories or the journeys already produce. I would not wait for the last screens: the row is already written and growing.

- **I2. No page tells a project with existing code how to adopt DDD, and the natural first step fails at the link.** `docs/toolbox.rst:11` ("A project that adopts DDD rarely starts from nothing"), `docs/consistency_checks.rst:119-120`, `docs/concept.rst:317-320`; compare pass 1 I13.
  *Trigger:* one component is described, as `consistency_checks.rst:120` allows ("a project being migrated onto DDD"), and reads a global the old code still defines. `ddd generate c` stops on `missing-producer`; with `-W missing-producer=ignore` DDD writes a definition of that global too, under `<unresolved>`, and the image fails: `multiple definition of 'LegacySpeed'` (reproduced, `inv/half-migrated.txt`). `concept.rst:318-320` says the opposite: "such a project would link only if some hand written translation unit happened to define the symbol". Nothing says that a template can skip that group, and pass 1 I13 is the deeper point: the model cannot state "defined elsewhere".
  *What exists:* `ddd tool from-elf` to get first declarations, `-W file-extension=warning` to rename gradually, a sentence on `unknown-unit` (`units.rst:49-50`). *What does not:* an order of work; what happens to hand-written `extern`s and definitions; whether components can move one at a time, and how; what a hand-maintained a2l and the datasets keyed on it become; how to take the first baseline. A search for `migrat`, `existing project`, `existing code` and `adopt` finds only sentences like those.
  *Who:* every real integrator, since greenfield is the exception. *How badly:* they must discover the path, and hit a link error on the way. *Where:* new how-to, `docs/adopting.rst`, after Getting started. *Size:* M. It needs an answer to pass 1 I13 first, or at least the template workaround stated and an example project.

- **I3. Nothing tells an integrator how to get from the generated a2l to a connected tool (KNOWN: P10-M13, "documented as a reader obligation", which did not happen; see pass 1 I8).** `docs/file_formats/rasters.rst:126-133`, `docs/faq.rst:612-618`, `docs/acronyms.rst:147-151`, `docs/file_formats/sections.rst:98-103`.
  *Trigger:* an integrator generates the a2l and loads it to measure over XCP. The pages say three times that the module's `DAQ` block, `PROTOCOL_LAYER` and transport "come from whatever configures the XCP stack", and stop. **`A2ML` and `EPK` appear in no document** (`inv/evidence.txt`), `MEMORY_SEGMENT` only as "planned". The file says `DO NOT EDIT`, a rerun overwrites a patched copy, and no page says what to add, where, or how a build merges it. `concept.rst:236` goes further ("There is nothing for a project to decide there").
  *Who:* everyone who calibrates, which is what the a2l is for. *How badly:* stuck at the last step, with no pointer. *Where:* a section "Taking the a2l to a calibration tool" on `generated_artefacts.rst`: what a tool needs, what DDD writes, what the project adds, a build step that assembles them, what was tested with which tool and what was not. *Size:* S to state what is absent, M with a recipe proved on a tool (pass 1 open question 7).

- **I4. The tutorial's `ddd id --assign` step fails on Windows, and no page says its transcripts are a POSIX shell.** `docs/getting_started.rst:262`, `docs/comparing_deliveries.rst:156`; against `README.md:68` ("on Windows and Linux") and `docs/getting_started.rst:15-16` ("needs nothing but python").
  *Trigger:* `ddd id --assign components/*.ddd.json` in PowerShell or cmd, neither of which expands the pattern. *Observed:* `components\*.ddd.json: not readable as json, skipped`, `wrote 0 ids`, exit 1 (reproduced, `inv/windows-tutorial.txt`), where the page shows `wrote 2 ids`. The message sends the reader to the wrong problem. `getting_started.rst:61` and `README.md:79` (`PYTHONPATH=src python -m ddd`) are bash too. The suite cannot see it: `tests/test_transcripts.py:333` runs every transcript through `bash`, on the Windows cells as well.
  *Who:* every Windows newcomer, on one of the two supported platforms, in the first ten minutes. *Change:* have `ddd id` expand a pattern the shell left unexpanded (as `includes` already does) and say that the transcripts are bash, with the one PowerShell spelling that differs. *Size:* S.

- **I5. There is no account of how the GUI is put together; a contributor cannot find where a new endpoint or screen goes.** `docs/developer_documentation.rst:899-1201`, extending pass 2 I5 and pass 3 I7.
  *Evidence:* the section is 3,747 words under one heading, in the order the features were added ("The edit engine learnt one thing for adoption", `:1173`; "`ddd.variables.narrowed` is gone", `:1133-1134`). `contract.py`, `queries.py` and `routes.py`, the wire's three definitions, appear **zero** times; so do `gui/src/app`, `screens`, `components` and `generated` (`src/api`, `src/lib`, `src/state` once, as a coverage list, `:939`). The long poll: one passing mention, in a paragraph on a test helper (`:1008-1009`). Revisions: three passing mentions. The page's own rules, "no decision in a tsx", `*View` as a picture of its props, TanStack Query, `useKept`, never `waitForResponse`, are on the page zero times and on 13 to 213 lines of the plans each (`inv/evidence.txt`). What it has instead: a 556-word paragraph on e2e helpers (`:976-1011`), and three shells' spelling of a variable for a mapped drive journey (`:956-974`).
  *Consequence:* the code a contributor is likeliest to touch, 29,645 of 55,423 lines counting four groups (page 21,065 and server 8,580, against edit layer with language server 11,185 and core 14,593), has its only overview in a record of milestone 1 (`specs/2026-09-17-web-gui-design.md:68-99`) and is otherwise learned by failing tests.
  *Where:* the section split: The pieces (that diagram, brought up to date); A request's life (server, session and revisions, api, plan, preview, apply); Adding a route; Adding a plan; Adding a screen (`lib`, `screens`, `*View`, stories, journeys); the page's rules. The helpers move into `gui/e2e/` beside what they describe; the layer table takes pass 2's target. *Size:* M.

- **I6. A contributor is not told how to set up, nor what a change has to touch.** `README.md:995-1003`, `docs/developer_documentation.rst:392-402`.
  *Evidence:* both start at `python -m pytest`. `pip install -e ".[dev]"` appears once, as a fact about ci (`:535`). There is no `CONTRIBUTING`, no pull request template. `CHANGELOG` is named on the developer page **zero** times; `SPEC.md` once, as what a test reads (`:322`), although `README.md:1055` calls it binding and every feature so far changed it. "Anyone adding a check" (`:246-253`) names the registry and the code, and not the README row, the SPEC row and the reference row the suite will then demand (`tests/test_documentation.py:194-198,295`). There is a walk for an output format (`:195-233`) and none for a key, a file kind, an option or a route.
  On Windows, two things stop the first run and neither is stated: `bash` must be Git Bash (under PowerShell it resolves to WSL and the transcripts fail) and `tests/test_lsp.py:6526` needs the symlink privilege. The page says "Nothing in the suite skips" (`:416`), so the reader takes the failure for a real one.
  *Who:* every new contributor. *Where:* "Working on DDD" at the top of the developer page, or a `CONTRIBUTING.md` pointing at it: clone, venv, install, first green run per platform, then a table of what each kind of change touches. *Size:* S, half a day.

- **I7. The changelog files features under a release that does not have them.** `CHANGELOG.md:345,356,371,389`, inside `## 0.11.0` (`:235-458`); against `README.md:40-41` ("says what changed in it").
  *Trigger:* a reader on 0.11.0, the site's `stable` (`versions.json`, fetched), reads "A sixth tab, Compare" (`:371`), pasting a table (`:345`), the plot (`:356`), the mismatch button (`:389`). `git ls-tree v0.11.0 gui/src/screens/` holds no `ComparePage.tsx`, and `git show v0.11.0:CHANGELOG.md` holds none of the four (`inv/evidence.txt`): PRs #61, #63, #64 and #65 were merged after the tag and their entries written into the released section (`git diff v0.11.0 2b4bae6c -- CHANGELOG.md`, hunks at 342 and 410). A reader of `## Unreleased` learns none of them is new. *Change:* move them. *Size:* S.

- **I8. Two whole tabs and a format change have no changelog entry at all, and `## Unreleased` says nothing of what a user must do.** `CHANGELOG.md:7-15`, `:17-234`, `:467`.
  *Evidence:* the file's own rule is that a release changing a check identifier or a file format "says here what the migration costs" (`:7-11`), and that an entry costing anything "ends with **Migration:**" (`:467`). `empty-vocabulary` is a new check identifier and a format change, by `39f77bab`, PR #72: `minItems` left all five vocabulary schemas, a file that was refused now loads, and a units file listing nothing now opts a project into `unknown-unit`. **`empty-vocabulary` occurs nowhere in the changelog** (`grep`, `inv/evidence.txt`). The Shared files tab (PRs #67, #69, #71) and the Files tab (#73), with everything they write (`constants.ddd.json`, New file, Add a file, Remove), have no entry: "Files tab" occurs only in two later fixes (`:34,52`).
  `## Unreleased` holds 28 bullets, 25 of them about the preview GUI (`net::ERR_NO_BUFFER_SPACE` among them), and 0 `Migration:` lines, though `pyelftools` is a new runtime dependency that an air-gapped install has to bring (M3) and the bullet says only "No file format changes". *To the pass's question:* no. It does not tell a user what they must do, and does not say "nothing" either; they read 218 lines to find out. *Change:* add the entries, a one-line *What to do* at the top of the section, the preview's fixes under one sub-bullet. A test that every registered check is named in the changelog would have caught `empty-vocabulary`. *Size:* S.

- **I9. The SPEC calls itself the authoritative contract and gives the largest part of the tool two clauses.** `SPEC.md:785,2134-2137`; `README.md:1055-1058`, `README.md:13`.
  *Evidence:* the SPEC covers everything else to the last key (table below). `ddd gui` is "editing a project's description files in a browser ... a preview whose options are not yet part of this interface", and one mention in 3.6. The decision recorded (`specs/2026-09-17-web-gui-design.md:505`) was about *options*. There is no sentence on what it writes, when, in what layout, what a refusal is, what undo guarantees, what the server defends, or the edit engine. So there is nothing for "does it work" to be held to: passes 12 to 16 measure against a table cell, a security page and the plans.
  *Consequence:* the 29,645 lines of I5 are outside the contract, and the README's sentence "states ... the command line and the generated artefacts this implementation is measured against" reads as if not. *Change:* the maintainer's call (open question 1): a section 7.4 with what a project may rely on (at the least: only `Apply` writes, what is written and where, what is refused, the trust model), or a plain sentence that the preview stands outside the contract until `preview` is removed. *Size:* S for the sentence, M for the section.

- **I10. The same facts are written in up to eight places, the README is not the short version it says it is, and the suite forbids it from being one.** `README.md:38` ("This README is the short version"), `tests/test_documentation.py:194,385,590`.
  *Evidence:* the README is 1,058 lines, 9,762 words, with the full check table, comparison table, command table and key tables, and the suite requires every check, command and common key to be there, so it cannot shrink. The `volatile` essay is told at `README.md:411-447`, `getting_started.rst:225-235`, `concept.rst:338-349`, `variable_definition.rst:71-89,457-461,566-577`, `generated_artefacts.rst:412-510`, `component.rst:231-237,353-363`, `consistency_checks.rst:846-855`, `comparing_deliveries.rst:287-296`, about 230 lines. The eight fixed checks are listed on six pages, `--const-inputs`' constraint violation on five, `NO_PROPAGATE_HEADERS` on three, the docker `gui` service on three.
  *Consequence, already measured:* the copies have parted. `--image` did not reach five pages (M2); the language server's newer renames did not reach the SPEC and two READMEs (M11); `pyelftools` reached the README and not the tutorial (M3); pass 1's I7 (the `.rodata` claim, false on gcc 13+) and C1 (`--const-inputs`) now each need the same correction on five or six pages. Tests hold counts and names together, not meaning.
  *Change:* one home per fact, everything else a link. A README of about 150 lines (what it is, install, quick start, where everything is); the name tests move from the README to the reference pages, which already have them. *Size:* M, mostly deletion, plus the maintainer's yes (open question 3).

#### Minor

- **M1. The home page's "Module Index" is a 404.** `docs/index.rst:41`. The site documents no python module, so `py-modindex.html` is not built, and `-W` does not notice (reproduced, `inv/linkcheck.txt`: the one broken internal link of 30 pages). Delete the line. S.
- **M2. `--image` did not reach five pages.** `docs/acronyms.rst:66-70` ("DWARF ... DDD does not read it"), `:233-236` ("until an address map supplies"), `docs/faq.rst:553-565` (zero is what a run gets with no `--address-map`, and "keeps address zero silently", against the warning shown at `:517` and `:527`), `docs/getting_started.rst:532-535`, `docs/file_formats/types.rst:333-336`. Read off the lines. S.
- **M3. The tutorial's dependency list is wrong and an air-gapped install has no recipe.** `docs/getting_started.rst:21-24,31-33` ("its only runtime dependencies are pydantic ... and jinja2", "apart from pydantic and jinja2"), `docs/developer_documentation.rst:631`; `requirements.txt` has three, `README.md:52-53` says so. `README.md:57`'s "from a delivered wheel, no network" fails on the dependencies, and no page gives `pip download` plus `--no-index --find-links`. Who: the firewalled builds the sentence is addressed to. Read off the lines. S.
- **M4. The component page teaches what another page calls a mistake.** `docs/file_formats/component.rst:450-491` checks a component with `-W missing-producer=ignore` and never names `--standalone`; `docs/consistency_checks.rst:220` says "Naming the overrides by hand instead is the mistake the flag exists to end". A component author reads this page first. Read off the lines. S.
- **M5. "The exit code is the same everywhere" has two exceptions no page gives.** `docs/command_line_interface.rst:150,182-187` (130 for Ctrl-C). `ddd gui`, whose normal end is Ctrl-C, returns 0 (`src/ddd/gui/server.py:1051-1057`); `ddd lsp`'s 0 or 1 by whether `shutdown` came first is in `SPEC.md:2460-2463` alone. Read off the lines. S.
- **M6. How to bind a file to its schema is in the README and not on the site.** `README.md:119-138,258-272`; `docs/file_formats/index.rst:118-124` says an editor "can offer completion" and not how, `docs/editor_integration.rst` has no `$schema`, `docs/plugins.rst:276` assumes it, and the commit-or-generate choice is README-only. The README's "full documentation" is missing what its short version has. Who: every component author, lightly. Where: a section "Validation while typing" on the editor page. S.
- **M7. No recipe for a build that is not CMake.** `docs/build_integration.rst:8` ("Two integrations are shipped"), against `docs/concept.rst:402` and `command_line_interface.rst:717`. The pieces are scattered: `ddd sources`, the two runs, `ddd build-info` for the editor (`command_line_interface.rst:568-572`), compile the definitions as objects not a static library (`build_integration.rst:398-402`), the include rule. Who: Make, IDE-managed and older-CMake builds, of which embedded has many. Where: "Without CMake" on that page, a tested Makefile of about 40 lines. S.
- **M8. The tutorial stops before a compiler, and does not say the rest exists.** `docs/getting_started.rst:597-619`, `docs/index.rst:4-7`. It ends at generated files. No page shows hand-written C using them: `examples/cmake/components/controller.c` is named by no page, and "reads a curve, a structure member, an enum" has no snippet. "Where to go next" names neither the build integration, the editor nor the GUI, and `index.rst` offers no path by role. Where: a page "From description to linked image" over the thermostat (two `.c`, a `CMakeLists.txt`, a linked a2l); three lines in *next*; role paths in the index. S to M.
- **M9. No "upgrading DDD" how-to.** Scattered: re-run `ddd schema all` (`README.md:263`), reinstall the `.vsix` (`editor_integration.rst:258`), the module refuses another release (`build_integration.rst:37`). The copied templates have nothing: `docs/templates.rst:476` ("Nothing refers back"), though a copy taken before sections existed silently places nothing, the attribute being the template's (`examples/templates/ddd_globals.c.jinja2:4`). Add "diff your copy against `ddd templates-dir`". Where: FAQ or Getting started. S.
- **M10. The editor page has no trouble-shooting, and no recipe for the editors it names.** `docs/editor_integration.rst:34-36`, `README.md:151`, `editors/vscode/README.md:10`: Neovim, Helix and Emacs "need only the command", with no filetype pattern or snippet. "Announced as log messages" (`:179`) does not say where; no page answers "no squiggles appear" (not trusted, not on the `PATH`, no record found). S.
- **M11. SPEC 7.2 and both READMEs stop at variables, types and constants.** `SPEC.md:2353-2362`, `README.md:212-224`, `editors/vscode/README.md:91-95`, against `docs/editor_integration.rst:91-122,154-158`: renaming a unit, a section and a raster, and `unknown-unit`'s two quick fixes, are in the "authoritative contract" nowhere. The server does them (`src/ddd/lsp/server.py:727-791`). S.
- **M12. `SPEC.md:2215` says the dictionary format is "today `8`"; it is 9 (KNOWN: `SCRATCH/pass-1-2026-09-24.md:65`).** `src/ddd/ir.py:645`, `docs/data_dictionary.rst:228`. Left to pass 5. S.
- **M13. Whether the plugin api is public is not stated.** `README.md:42-46` and `CHANGELOG.md:7-11` list the public interface without it, though `docs/plugins.rst:120-121` promises "without breaking a plugin written against the previous version" and a plugin imports `ddd.plugins`, `ddd.diagnostics`, `ddd.backends`. A plugin author cannot tell what may change. Open question 4. S.
- **M14. `examples/` and `gui/` have no README.** Ten example directories, and no page or file says which shows what; the mentions are spread over the README and the pages. A table in `examples/README.md`; a pointer in `gui/README.md`. S.
- **M15. The glossary has holes.** `docs/acronyms.rst`: no LSP, A2ML or EPK; `concept.rst`'s vocabulary has none of the words the GUI and its refusals use (plan, revision, stale, Apply). S.
- **M16. Three environment variables are documented only in code.** `docs/conf.py:102-103` (`PLANTUML_JAR`, `JAVA`; `developer_documentation.rst:674-681` says only that both programs are apt packages, which leaves a Windows contributor at a warning per diagram), `gui/scripts/schemas.mjs:13` (`DDD`). `BROWSER`, read through `webbrowser` (`src/ddd/gui/server.py:1048`), is named only as a test fixture (`developer_documentation.rst:1015`), though `gui_security.rst:237` tells the reader to use "a browser profile of its own" without saying how: `--no-browser` and paste, or `BROWSER`. S.
- **M17. The security page does not say what the reader should do.** `docs/gui_security.rst`. It is a threat model and a list of limits; one bullet (`:47-106`) is 933 words on byte counts and refusal codes. The instructions a user needs are spread over it: paste rather than click (`:136-138`), open pages from the printed address (`:182-183`), publish on loopback (`:188`), a browser profile of its own (`:237`), the terminal's reused-code line means restart (`:217-223`), plugins run (`:126-127`). Add "What you should do", six lines, on top; move the limits to the end, or a reference. S.
- **M18. Reference is mixed with history and with defence of itself.** Examples in *Page shape* below. An editing pass, S to M, no decisions needed.
- **M19. Pages whose order or size stops a reader.** `docs/templates.rst` argues to `:86` (Why the templates belong to the project, The a2l file is not templated, Why jinja2, A template directory is code) and its *Getting started* is at `:449` of 507. `docs/generated_artefacts.rst` is two pages (c, a2l) of 1,374 lines, with a 100-line essay. `docs/developer_documentation.rst` has no working-on-it section and 410 lines on ci and publishing (`:485-897`). `docs/data_contracts.rst` renders to 2.4 MB, 49 % of the site, and its prose restates `file_formats/index.rst`. S to M.
- **M20. The design records' status lines have regrown wrong, and the documents depend on the records (KNOWN: 2026-09-15 pass 7 Minor 5).** `docs/superpowers/specs/*.md`: of 32, 14 have no status and 12 say "to be planned" or "not implemented" of merged work (`2026-09-24-gui-paste-design.md:4`, `2026-09-30-toolbox-from-elf-design.md:4`). `docs/developer_documentation.rst:1055,1091` send a reader there for what "findings-heavy" means and for the figures; `src/ddd/toolbox/from_elf.py:4`, `src/ddd/gui/queries.py:7`, `tools/*.py`, `gui/src/styles/*.css` cite them too, and the sdist excludes them (`pyproject.toml:105`), so for its reader they dangle. `gui/src/stories/fixtures.ts:1577` cites `.superpowers/sdd/...`, in no repository. See pass 2 M9, pass 3 M10. S.

### Status of the 2026-09-15 findings in this area

The rest of that review's pass 7 is plainly fixed on this tree: the issue tracker (`gh api`: `has_issues: true`), the FAQ's array bound (`docs/faq.rst:620-667`), "nothing skips" (`developer_documentation.rst:416`), the README's stale transcript and relative links, the interface sentence, the environments paragraph (`:847-858`).

| finding | one line | status | where |
| --- | --- | --- | --- |
| P7 Minor 5 | design records carry a stale status line | STILL OPEN: the four named are fixed, 26 new | M20 |
| P7 Minor 2 | the developer page's layers omit a whole subsystem | REGRESSED in kind: `lsp` was added, `gui` and 20 root modules are absent | pass 2 I5; I5 here |
| P7 Minor 10 | acronyms the pages use and the page lacks | fixed as listed; drift since: LSP, A2ML, a stale DWARF row | M2, M15 |
| plan 2026-09-16, Left open | README in-page anchors resolve on GitHub alone | KNOWN, still open: `README.md:69,266,294,364,1045`; not reachable from here to test PyPI | Minor, unfiled |
| plan 2026-09-17, Left open | SPEC 3.6's "(`ddd gui`, section 7)" is plain text | KNOWN, still open: `SPEC.md:785` | trivial, unfiled |

### Open questions

1. **Is `ddd gui` inside the SPEC?** Yes: a section 7.4, and passes like 12 to 16 get a contract, at M. No: one sentence saying so, and `README.md:1055-1058` is true again, at S. I would write the small section now, on what a project may rely on, and let screens stay out.
2. **Where do the design records live?** Off the site in any case. On master, as they are; on master with an index and without the binaries (my choice, below); or on an orphan branch, which is cleanest for readers and needs the citations of M20 gone first.
3. **Does the README stay exhaustive?** The suite makes it so (`tests/test_documentation.py:194,385,590`). If it may become short, I10 is mostly deletion, and PyPI's page, which shows the README, gets shorter too. If it must stay, take "the short version" out of its sentence.
4. **Is the plugin api public?** If yes, add it to `README.md:42-46` and `CHANGELOG.md:7-11`, and a change to a context becomes a migration line. If not, say so on `docs/plugins.rst`.
5. **When is the GUI guide written?** The plans have it at part 20, after journeys it no longer depends on. I would write it now without the screenshots: its absence is what the row's growth is compensating for, and a pilot's readers need it first.
6. **The a2l recipe needs a tool (I3).** Somebody with CANape or INCA has to prove one; the same hour as pass 1 open question 7.

### Test gaps

- Nothing holds `CHANGELOG.md` to the public interface: a check added to the registry with no entry passes (`empty-vocabulary`). `TestTheReleaseNote` (`tests/test_documentation.py:1517`) checks counts in an entry, not presence. Registry against changelog is ten lines.
- Nothing notices an edit to a released section: a test comparing the section under each tag with `git show <tag>:CHANGELOG.md` would have caught I7, or a rule in the release walk.
- `tests/test_transcripts.py:333` runs everything through `bash`, so no page's command is ever tried under the shells of a supported platform (I4).
- `-W` does not check generated links: the 404 of M1 passes. `sphinx-build -b linkcheck` restricted to internal links, or `SCRATCH/pass-4/linkcheck.py`'s 40 lines, would.
- 51 of 173 commands shown are not run (`tests/test_transcripts.py:424`, disclosed), 14 of them in `faq.rst`, where the staleness of M2 sits; the prose around a run command is not compared at all.
- Nothing ties the GUI's tabs (`gui/src/app/App.tsx:29-38`) or routes-as-screens to a page. `tests/test_gui_docs.py` holds the route table to the server (good, 36 of 36); once a guide exists, the same for its tabs.
- `tests/test_documentation.py` holds names, not meaning: all of I10's parted copies pass.

### Assessment

The documentation answers "what exactly does this key, check or option do?" better than almost any tool of this size: the inventories are close to complete and the tests keep them so. It does not answer "how do I do this?", and for the largest part of the tool it does not answer "what is this?". Its readers are served in the order the documents were written: a component author very well, an integrator on CMake well until the a2l leaves the build, a newcomer on Linux well for ten minutes, a contributor on the release machinery in depth and on the GUI not at all, and somebody asked to use `ddd gui` with one table cell. Most of the twenty minor findings, and I4, I6, I7 and I8, are half a day's work or less. The one structural step is to give each fact one home and to accept a short README, because the length is not padding but repetition, and the repetition has started to contradict itself. What would change most for the least: the GUI guide from text that already exists (I1), a Windows line and the contributor's first section (I4, I6), the changelog put right before the next release (I7, I8).

#### What is missing, ranked by how many people it stops and how badly

| # | What is missing | Who | How badly | Where it should go | Size | Finding |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | A guide to `ddd gui` | everyone asked to use it | cannot find what exists; no picture; no limits | new `docs/gui.rst` | M | I1 |
| 2 | How to adopt DDD in a project with code | nearly every real project | no path, and a link error on the first step | new `docs/adopting.rst` | M | I2 |
| 3 | From generated a2l to connected tool | everyone who calibrates | stuck at the last step | section on `generated_artefacts.rst` | S-M | I3 |
| 4 | Windows in the tutorial | every Windows newcomer | fails at the id step, wrong message | `ddd id`, `getting_started.rst` | S | I4 |
| 5 | How the GUI is put together | every GUI contributor, over half the code | learned from plans and failures | `developer_documentation.rst` | M | I5 |
| 6 | Set-up and definition of done | every new contributor | stalls, then finds out by failing tests | top of the developer page | S | I6 |
| 7 | Honest release notes | every upgrader | misled on 0.11.0; `empty-vocabulary` unannounced | `CHANGELOG.md` | S | I7, I8 |
| 8 | What a project may rely on from the GUI | maintainers, reviewers, then users | nothing to test it against | `SPEC.md` 7.4, or one sentence | S-M | I9 |
| 9 | One home per fact | all, indirectly | contradictions spreading | README, all pages | M | I10 |
| 10 | Schema binding on the site | every component author, lightly | a detour to the README | editor page | S | M6 |
| 11 | A first linked image, and C using the headers | newcomers, component authors | stops at generated files | new short page | S-M | M8 |
| 12 | A build without CMake | Make and IDE builds | assembles it from six places | `build_integration.rst` | S | M7 |
| 13 | Upgrading DDD | every project, once a release | steps scattered; copied templates unmentioned | FAQ or tutorial | S | M9 |
| 14 | Air-gapped install | firewalled builds | wrong list, no recipe | `getting_started.rst` | S | M3 |
| 15 | Rules for a GUI user on security | GUI users | buried in a threat model | top of `gui_security.rst` | S | M17 |
| 16 | Editors other than VS Code; trouble-shooting | a minority | works it out | editor page | S | M10 |

#### Tool against documents

Documented rows are summarised. Every row marked missing is listed.

| Inventory | The tool has | Documented | Where |
| --- | --- | --- | --- |
| commands | 21, nested ones included (`inv/cli.txt`) | 21 | CLI table, generated reference, README, SPEC 7 |
| options | 26 distinct, 90 argument rows | all | generated reference; each also in prose (`-b`, `-o` by their short form) |
| checks | 72: 8 fixed, 9 project, 13 comparison | 72, severities equal | `consistency_checks.rst`, README, SPEC 4 |
| toolbox | 1 tool, 15 findings | all | `toolbox.rst`, SPEC 7.3 |
| CMake | 18 keywords, 7 targets, `DDD_A2L`, `DDD_DICTIONARY`, `DDD_JSON`, `DDD_EXECUTABLE` | all | `build_integration.rst`, SPEC 7.1. Internal properties rightly not |
| file kinds and keys | 8 schemas, 153 key rows (`inv/schema.txt`) | 152 in prose; `cycle_ns` in the generated reference only | `file_formats/*`, `data_dictionary.rst`, SPEC 3 |
| other files | `ddd-build.json`, `.ddd-manifest.json`, `renames.json`, address map | all | build, artefacts and compare pages, SPEC |
| exit codes | 0, 1, 2, 130 | yes, but for M5 | `command_line_interface.rst:150-187`, `consistency_checks.rst:959-986` |
| LSP | sync, diagnostics, definition, references, hover, rename with prepare, quick fixes, watched files, log messages; 2 settings, 1 command | all | `editor_integration.rst`; SPEC and READMEs lag (M11) |
| plugin api | `Plugin` 7 fields, 3 contexts, `bag`, `locate`, `GeneratedFile` | all | `plugins.rst`, SPEC 3.11 |
| gui routes | 36 | 36, test-held | `gui_security.rst:269` |
| environment | 18 variables read | 14 | build page, README, developer page. Missing below |

| Environment variable | Read by | Status |
| --- | --- | --- |
| `PLANTUML_JAR`, `JAVA` | `docs/conf.py:102-103` | **missing**: a comment in `conf.py` only |
| `DDD` | `gui/scripts/schemas.mjs:13` | **missing**: the script's comment only |
| `BROWSER` | python's `webbrowser`, `src/ddd/gui/server.py:1048` | **missing for a user**: named only as a test fixture |

**`ddd gui`.** Documented, 20 items: address, one-time code, token and gate (`gui_security`); the graph's arrows, the Table, Findings as a list, a settlement button, the variable's panel, adding and removing a declaration, values grid, paste, plot, a scalar type's change and rename, undo, Compare, Shared files, Files, what is served (bounds), large-project behaviour, options (all `command_line_interface.rst:294-567`). Missing:

| Screen, action or state | Source | Status |
| --- | --- | --- |
| Start page: `Open a project`, `Found under`, "built as", `Build records not used`, none found | `screens/StartPage.tsx` | `--help` one clause; the rest **missing** |
| Masthead: `Projects`, switching project, what happens to undo | `app/App.tsx:292-298` | **missing** (`developer_documentation.rst:1192` in passing) |
| Graph: `Search modules` (fades the rest, Enter centres) | `screens/GraphPage.tsx:327-336` | **missing**, no document names it |
| Graph: `Tidy`, `Fit`, zoom | `:337-338,383` | **missing**, no document names them |
| Graph: dragging, positions kept per browser | `state/positions.ts` | **missing** |
| Graph: what an arrow's number and colour mean, and a click: one object opens it, several ask which, agreeing opens nothing | `:285-304` | colour one clause; the rest **missing** |
| Graph: `no dictionary, so its modules are drawn without arrows` | `:96-100` | **missing** |
| Units: `Adopt N units`, `Show changes`, `units.ddd.json` | `components/AdoptBannerView.tsx` | **missing**; changelog only |
| Unit panel: places, rename and merge, description, add, remove | `components/UnitPanelView.tsx` | "maintaining its vocabulary"; changelog only |
| Types: structures, externals, members table, description; that nothing can be created there | `components/TypePanelView.tsx` | scalar change and rename only; the rest **missing** |
| Findings: `missing-id` fix from the panel, its link and notes, "no longer reported" | `components/FindingPanelView.tsx` | **missing** for a user; `developer_documentation.rst:1127` |
| Component page: Unit cell opens the picker, chips, `Findings in this component`, "no longer declared" | `screens/ComponentPage.tsx` | **missing** |
| The one pattern everywhere: plan, `Show changes`, `Apply`, a refusal held until the next revision | every panel | case by case; no statement |
| Working beside an editor: the page follows files on disk, about once a second; a half-saved file reads `did not load` | `gui/session.py` | **missing** for a user |
| What it writes and when: only on Apply, no git, what the browser keeps (token, positions) | | "in their own layout"; the rest **missing** |
| A project CMake collected: which file opens, where New file writes | pass 1 C4 | **missing**: no warning anywhere |
| What it cannot do: create a type, edit members, change scope or kind, `condition`, the `a2l` block, `extensions`, the raw text of a file that does not parse | `lsp/edits.py:64` | **missing** |
| Which browsers it is tried on (Chromium, Edge) | `ci.yml` | security page by header only; `developer_documentation.rst:496` |
| What `preview` means, and what is planned | `app/App.tsx:290` | "options not stable"; plans only |
| Stopping it: Ctrl-C, exit 0 | `gui/server.py:1051` | "until interrupted" (M5) |

**For a contributor.**

| Question | Developer page | Instead |
| --- | --- | --- |
| Set up a checkout | **missing** | a sentence about ci, `:535` |
| What a change has to touch (SPEC, changelog, README, schemas) | **missing**, but for two walks | failing tests |
| GUI server, session, api, contract, queries, routes | **missing** | milestone 1's spec, 4.1 and 6.3-6.5 |
| Where a new endpoint goes | **missing** | failing tests (`test_gui_docs`, the contract) |
| Where a new screen goes, the page's rules | **missing** | plans |
| A plan module's job, the edit engine, undo | present, as narrative | `:1094-1200` |
| Build and test the page, stories, journeys | present | `:902-975` |
| Windows: Git Bash, symlink privilege | **missing** | this review's brief |
| Release, ci, development builds, publishing | present, in depth | `:485-867` |

#### The five readers

- **The newcomer.** Reaches generated files in ten minutes on a POSIX shell, with every transcript true, and has understood why after `concept.rst`, whose three failure modes are the best page of argument here. Stops at: Windows (I4); no compiled image and no C using the headers (M8); never told an editor server or a GUI exists (`getting_started.rst:597-619`; pass 1 M1).
- **The component author.** Best served. Every key has a row, examples compile, findings explain themselves, and the schema hovers while typing. Stops at: `$schema` not on the site (M6), and the stale way to check alone (M4).
- **The integrator.** On CMake the reference is complete to the last keyword, and the module's refusals are explained. Stops at: adopting at all (I2), the a2l leaving the build (I3), not being on CMake (M7), running `ddd gui` over the collected project (pass 1 C4, no warning), tool-only objects under `--gc-sections` (pass 1 I11, no page says `KEEP`).
- **Somebody asked to use `ddd gui`.** Starts it and the screens carry them a long way; they are clear, and their sentences are good. The documents add little. They cannot find what `Tidy` does, how to adopt a vocabulary, what it will not do, or what to take care of (I1, M17).
- **The contributor.** Finds a treatise on publishing and on what guards it, the reasons for the a2l's shape, and 100 % coverage's rationale. Does not find how to get a green first run (I6) or where anything in the GUI goes (I5).

#### The SPEC's coverage of what the tool does

| What the tool does | SPEC | Coverage |
| --- | --- | --- |
| File formats, plugins, build record | 3.1-3.11 | full, to the key |
| Consistency checks, comparison | 4, 4.1 | full, 72 of 72 |
| C, a2l, dictionary, addresses | 5.1-5.3, 6 | full; format number stale (M12) |
| Command line | 7 | full, as one paragraph of 1,218 words |
| CMake | 7.1 | full |
| Language server | 7.2 | partial: unit, section and raster rename, `unknown-unit` fixes absent (M11) |
| Toolbox | 7.3 | full |
| Pre-commit hook | 7, one clause | enough |
| **`ddd gui`: screens, plans, undo, session, server, security** | 7, 3.6: two clauses | **none** (I9) |
| **The edit engine** (`ddd.editing`, what "in their own layout" promises) | none | **none** (I9) |
| Docker services, release machinery | none | rightly |

Shape: `SPEC.md:2064-2156` is a single paragraph, and its section 4's check list is 1,863 words of one list; pass 5 reads it in full.

#### `docs/superpowers/`: what only it holds, and whether it belongs

**The site.** It is not built: `docs/conf.py:35` does not exclude it, it stays out only because it holds no `.rst` (the built site has no page of it, checked). Make that a line of `exclude_patterns`. It should stay out: a record of what was decided at a date, 26 of 32 specs with no status or a wrong one, some superseded by design (`docs/superpowers/plans/2026-09-18-gui-units.md`, "the web GUI spec's section 6.7 still describes milestone 1's unit editor"). Published, it would be read as documentation.

**Needed by a user or contributor, and only there:**

| Held only in `docs/superpowers/` | Who needs it | Should go to |
| --- | --- | --- |
| The GUI's pieces, session and revisions, the api's conventions, refusal codes (`specs/2026-09-17-web-gui-design.md` 4, 6.3-6.6) | contributor | developer page (I5) |
| The page's rules and the journeys' conventions (several plans) | contributor | developer page (I5) |
| What "findings-heavy" means, the large-project figures (`plans/2026-09-30-gui-large-projects.md`) | contributor | developer page, cited at `:1055,1091` |
| What is planned: guide, pilot, removing preview | user, integrator | one paragraph in the guide |
| Known limits, in 27 "Left open" lists (no filter on Findings, no address for the blank form) | user, contributor | a "Known limits" list in the guide; the rest to issues |
| The decisions taken on reviews (`plans/2026-09-16-review-fixes.md`) | maintainer | where they are; a record is the right home |

**On master.** I would keep the text and change three things: an index, `docs/superpowers/README.md`, one line per record with its status and "records, not documentation; may be wrong"; the 53 mockups and screenshots (47 PNG, 6 HTML; 4.4 MB of 9.6 MB on master) out, to a release asset or the record's PR; and no citation of them from code or a page. It is already kept apart from everything else: excluded from the sdist (`pyproject.toml:105`), from ruff (`:146`), from the doc tests (`tests/test_documentation.py:60`, `tests/test_transcripts.py:64`). Those four exclusions are what a separate branch would make unnecessary, so an orphan `design-records` branch is the other honest answer; its cost is losing the search beside the code. The maintainer's call (open question 2).

#### Page shape

Words of prose, a crude count (`shape.py`, `inv/shape.txt`). Total 141,627; SPEC 29,115; developer page 12,510; README 9,762; artefacts 8,825; checks 8,306; CLI 7,384; build 6,979.

| Page | Verdict | Why |
| --- | --- | --- |
| `getting_started`, `toolbox`, `comparing_deliveries`, `faq`, `conversions`, `units`, `sections` | right | each is what it says it is |
| `command_line_interface` | wrong shape | 51 % is one cell (I1); the row carries benchmarks and refusal text |
| `README` | wrong size | "the short version" at 9,762 words (I10) |
| `developer_documentation` | wrong order | 17 sections; a third publishing, none on starting; GUI unsectioned (I5, I6) |
| `gui_security` | mixed | threat model, limits, instructions and a route table; a 933-word bullet (M17) |
| `templates` | wrong order | argues to `:86`, gets started at `:449` (M19) |
| `generated_artefacts` | too long | c and a2l are two pages; the essay on `volatile` (`:412-510`) is a third (M19) |
| `consistency_checks` | good, with lapses | reference table, wise severities page, then history (below) |
| `editor_integration` | one wall | the Rename paragraph is 628 words (`:82-122`), half of it about section and raster names |
| `data_contracts` | duplicates | prose restates `file_formats/index`; 2.4 MB rendered (M19) |

**History in the reference** (M18). A reference says what is; these say what was:

- `consistency_checks.rst:839`: "Two other properties used to be settled this way, and left in opposite directions." `:854`: "a project adopting this version of DDD adds the key everywhere in one go".
- `generated_artefacts.rst:610-612`: "Its header used to stay where the last run had put it". `:491-498`: a note on files "written before it existed", on a page about what is generated. `:866`: "exactly as before rasters existed"; `rasters.rst:97-98` again.
- `build_integration.rst:548-554`: "so it used to be dropped in silence ... `PROJECT` without a value fell into the collected mode".
- `command_line_interface.rst:189-191`: "where the broken pipe used to be reported as a usage error".
- `file_formats/component.rst:323-324`: "turned the declaration below it into part of the condition, and the compiler stopped there".
- `developer_documentation.rst:419-427` ("Two places used to do it"), `:513-516`, `:715-717`, `:880-886`, `:1131-1134`. The changelog is where these belong, and the page's reader needs the rule.

**Defence in the reference** (M18). The page argues where it could state, and a reader wades:

- `consistency_checks.rst:519-521,526-528,534-535`, in three table rows: "Kept a separate identifier from `consumer-storage`, whose published description says storage, which a raster is not." Nobody asks this while reading what the check does.
- `file_formats/index.rst:4-12`: nine lines on why the double extension before the rule, and `README.md:106-110`, `getting_started.rst:124-128`, `faq.rst:16-22` say it again.
- `file_formats/rasters.rst:22-31`: why eight characters, including that "No file DDD writes carries an event name today". Justifying wording is 10.3 per 1,000 words here against 2.1 on `conversions.rst`.
- `templates.rst:15-64`: three argued sections before the first rule.
- `comparing_deliveries.rst:476-477`: why the last line names files rather than projects. `build_integration.rst:313-314`: why the record is not named `*.ddd.json`. `developer_documentation.rst:12-14`: "That is not a style preference".
- Roadmap inside the reference: `sections.rst:98-100` ("is planned"), `rasters.rst:30-31`.

The reasons are worth keeping, and many are the best writing in the set. The change is where they go: state the rule first, in one line; keep the reason in a "Why" paragraph at the end of the section or in `concept.rst`; send the past to the changelog.

```candidates
4|I1|docs/command_line_interface.rst:294|ddd gui has no guide: its one account is a 3,960 word table cell, and twenty things on screen are missing or get one clause (KNOWN part 20)
4|I2|docs/toolbox.rst:11|No page says how a project with existing code adopts DDD; relaxing missing-producer for a global old code defines fails at the link, against concept.rst:318
4|I3|docs/file_formats/rasters.rst:126|Nothing says how to get from the generated a2l to a connected tool: A2ML and EPK appear in no document (KNOWN P10-M13, see pass 1 I8)
4|I4|docs/getting_started.rst:262|The tutorial's ddd id --assign components/*.ddd.json fails on Windows (wrote 0 ids, exit 1), and no page says the transcripts are bash
4|I5|docs/developer_documentation.rst:899|No account of how the GUI is put together: contract, queries, routes, screens named nowhere; where a new endpoint or screen goes is unanswered
4|I6|docs/developer_documentation.rst:392|No set-up and no definition of done for a contributor: CHANGELOG named zero times, pip install -e only as a fact about ci, Windows stoppers unstated
4|I7|CHANGELOG.md:371|The 0.11.0 section lists the Compare tab, paste, plots and the mismatch button, none of them in the v0.11.0 tag
4|I8|CHANGELOG.md:17|empty-vocabulary, a new check and format change, is nowhere in the changelog, nor are the Shared files and Files tabs; Unreleased has no Migration line
4|I9|SPEC.md:2134|The authoritative contract gives ddd gui two clauses: nothing on what it writes, refuses, undoes or defends, for over half the code
4|I10|README.md:38|The same facts are written in up to eight places, the short README is 9,762 words, and tests force it; copies have already parted
4|M1|docs/index.rst:41|The home page's Module Index link is a 404, and -W does not notice
4|M2|docs/acronyms.rst:66|--image did not reach five pages: DWARF DDD does not read it, FAQ's keeps address zero silently
4|M3|docs/getting_started.rst:21|The tutorial's dependency list omits pyelftools, and an air-gapped install has no recipe
4|M4|docs/file_formats/component.rst:450|The component page teaches -W missing-producer=ignore, which consistency_checks.rst:220 calls the mistake --standalone ends
4|M5|docs/command_line_interface.rst:150|The exit code is the same everywhere has exceptions: ddd gui exits 0 on Ctrl-C, ddd lsp's codes are in the SPEC alone
4|M6|docs/file_formats/index.rst:122|How to bind a file to its schema is in the README and not on the site
4|M7|docs/build_integration.rst:8|No recipe for a build that is not CMake; the pieces are on six pages
4|M8|docs/getting_started.rst:597|The tutorial stops before a compiler, no page shows C using the headers, and where next omits build, editor and GUI
4|M9|docs/templates.rst:476|No upgrading how-to, and nothing says a project's copied templates lack what later releases add
4|M10|docs/editor_integration.rst:34|No recipe for the editors it names and no trouble-shooting
4|M11|SPEC.md:2353|SPEC 7.2 and both READMEs omit renaming a unit, section or raster and the unknown-unit fixes
4|M12|SPEC.md:2215|SPEC says dictionary format today 8; it is 9 (KNOWN, 2026-09-24)
4|M13|README.md:42|Whether the plugin api is public is stated nowhere
4|M14|examples:1|examples/ and gui/ have no README and no index of what shows what
4|M15|docs/acronyms.rst:17|The glossary lacks LSP, A2ML, EPK, and the words the GUI uses
4|M16|docs/conf.py:102|PLANTUML_JAR, JAVA, DDD and a user's BROWSER are documented only in code or as a fixture
4|M17|docs/gui_security.rst:47|The security page never says what the reader should do; its instructions are spread through a threat model
4|M18|docs/consistency_checks.rst:839|Reference is mixed with history and with defence of itself
4|M19|docs/templates.rst:449|Pages whose order or size stops a reader: templates, generated_artefacts, developer page, data_contracts at 2.4 MB
4|M20|docs/developer_documentation.rst:1055|Design records' status lines have regrown wrong (26 of 32), and pages and code depend on records the sdist excludes (KNOWN)
```

## Pass 5: SPEC.md on its own

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-5/`. Line numbers are on the review tree.

### Scope covered

- `SPEC.md`, all 2550 lines, read in order with line numbers (1-300, 300-619, 619-948, 946-1275, 1275-1534, 1534-1813,
  1814-2073, 2062-2311, 2307-2550).
- `git diff 6e9e99f HEAD -- SPEC.md` (saved as `spec.diff`): the 48 commits by title and every removed line; the added lines
  were read as part of the present text, not hunk by hunk.
- Mechanical checks (`mech.py`, `mech2.py`, `mech3.py`, output beside them): table of contents against headings; every
  `[section N](#anchor)` against anchor and number; section 4 and 4.1's bullets against `ddd checks --format json`, with
  severities; bold and plain requirement words; terminology counts; every property of `ddd schema all` for a description.
- Probes with the review tree's `ddd.exe` 0.11.0, several hundred runs: `p1`-`p23`, `lsp.py` (a small stdio client), `old.sh` (real
  dictionaries written by v0.5.0 to v0.10.0, from `git archive` into `old/`, read by this tree). The largest project is `rich/`, whose
  `out/Rich.a2l` and `out/ddd_globals.c` were read in full against 5.1 and 5.2; `cnt/` is the counted one.
- `SCRATCH/review-2026-09-15.md` pass 1 with its verification, `SCRATCH/pass-1-2026-09-24.md` in full, the candidates blocks of
  passes 1 to 4, the "Left open" of every plan that mentions the spec (`leftopen.txt`), and the ASAP2 1.6.1 text pass 1 extracted, for
  the sentences that cite it. Code read only to settle a sentence: `cli.py` (`_analyze`, `_command_check/compare/dump`),
  `deliveries.py`, `plugins.py`, `backends/base.py` (`write`), `compare.py` (`_stored_init`, `_compare_instances`), `ir.py:645-658, 765-775`,
  `analysis.py:115-150`, `cmake/Ddd.cmake:395-655`.
- Not covered, left to their passes: a real CMake build (7.1 was checked against the module's text only), rename and quick fixes of 7.2,
  from-elf beyond its refusals and exit codes, A2L validity beyond the sentences that cite the standard. The interrupt's exit 130 was
  read off `cli.py:131`, not run.
- Met again and cited rather than re-filed: `SPEC.md:500-505` `const volatile` (pass 1 I7; on gcc 15.2 `nm` shows `R`, `p19.txt`),
  `:1742` (pass 1 C1), `:1555-1562` (pass 1 C3), `:1668` (pass 1 I3), `:1923` (I5), `:2267-2270` (I6), `:1393` (I10, M3), `:1783` (I11),
  `:2015` (I12), `:462` (M4), `:1883` (M6), `:2105` (M10), `:2134` (pass 4 I9), `:2353` (pass 4 M11, pass 2 M6).

### Strengths

- **The mechanical skeleton is exact.** 39 headings are the table of contents in order; all 295 internal links resolve and their
  numbers match (`mech.txt`). The 72 checks are the 59 bullets of section 4 plus the 13 of 4.1, every severity equal to the registry's;
  the nine `(project)`, eight fixed and thirteen comparison sets are exact; the spec names no check the tool lacks (`mech2.txt`).
- **The file format rules are what the tool does, to the check name and the location.** Of the sentences of 3 to 3.11 probed
  (`p1`-`p4`, `p9`, `p10`, `p14`, `p17`: includes and the 64 levels, conditions, ids, limits, formats, 64 bit integers, the 128 character cap
  on all nine subjects, shapes and the 10 000 000 cap, `init` and strings, every name in `reserved-identifier` and `name-collision`,
  rasters and periods, sections, units, types, plugin loading, blocks and hooks) the only departures are in the Minor list below.
- **5.2 and 5.3 describe the output exactly.** Record order, method names and suffixes, `COEFFS`, formats, `IF_DATA`, `GROUP` contents, the
  mark and the header all match `rich/out/Rich.a2l`, with one exception (M9). The top level, object, instance and leaf key lists of 5.3 are
  exactly a format 9 dump's (`p7.txt`); the dump and the artefacts are byte identical from two directories (`p15.txt`).
- **The examples follow the text.** All eight JSON blocks load together; `Inlet.latest`/`Inlet.raw`, `7.65`, `1500us`/`1234ms`, `unit16`,
  the `--renames` spellings, the note's wording and `-W layout/duplicate-key` all reproduce (`p17.txt`, `p8.txt`, `p18.txt`).
- **What it cites holds.** ASAP2 1.6.1 section 1.5 does say BOM, else ISO-8859-1, and `MATRIX_DIM` does take three (`pass-1/pdf/asap2-1.6.1.txt:877-890, 6575`);
  gcc 15.2 does fold a `const` at `-O0` inside one translation unit (`p20.txt`).
- **Reading an older dictionary is real.** Dumps written by the actual v0.5.0 to v0.10.0 (formats 4, 5, 7, 8) of their own examples all read,
  compare clean against themselves and against today's reading of those projects (`old.txt`). No test does this; the promise held anyway.
- **The session rules of 7.2 hold as written** (`lsp.txt`): before `initialize`, second `initialize`, after `shutdown`, exit 0 and 1, a bad `Content-Length`,
  no length, a foreign scheme, a record of a newer format or naming an unknown check.
- The published schemas keep "every authored field ... shall carry its documentation": 341 properties, none without one (`p17.txt`).

### Issues

#### Critical

None.

#### Important

- **I1. Section 7 still says the dictionary is format 8 (KNOWN: 2026-09-24 I1; see pass 4 M12, which left it here).** `SPEC.md:2215` "`format`, today `8`"
  against `SPEC.md:1953` "`9`" and `src/ddd/ir.py:645`. Trigger: any `ddd dump` -> `"format": 9`. A reader written from section 7 implements 8 and, by the
  rule both sections state (`:1954-1955`, `:2217-2218`), refuses every dictionary 0.11.0 writes. Still the same line as on 2026-09-24; nothing pins it:
  `tests/test_documentation.py:1548-1557` reads the changelog's `Unreleased` only. Read off the lines; dump reproduced (`p7.txt`).
  Say the number once, in 5.3, and link it from 7.

- **I2. What `point_counts: "leading"` does to the C is stated nowhere in the spec, and four sentences say otherwise (KNOWN: 2026-09-24 I2).** The kind table
  (`SPEC.md:434-436`: `[size]`, `[size of the axis]`, `[size of y][size of x]`), `:1830` ("the C declaration is `[y][x]`"), `:356` ("`null` means implicit
  zero initialisation") and `:453-456` (`init` matches the shape) against `cnt/out/ddd_globals.c`: `const uint8_t M[2 + (2) * (NX)] = { NX, 2U, 1U, 2U, 3U, 4U, 5U, 6U };`,
  `const uint8_t Ay[1 + (2)] = { 2U };`, `Cu2[1 + (NX)] = { NX, 7U, 7U, 7U }`; `init` `[3,1,2,3]` on a 3 point axis is `init-invalid` (`p6.txt`). The clause at `:1833-1834`
  ("matching the C declaration that puts the counts first") assumes a statement that does not exist; 5.1 (`:1737-1760`) does not mention it; 5.3 calls the dictionary the contract with "a
  project's" backend, and its `shape` is `[2, 3]`. `docs/data_dictionary.rst:200` says "declared flat, counts first, in its own datatype": the authoritative contract is the one
  document without it. Reproduced. One paragraph in 3.3 and a clause in the table, S.

- **I3. "Findings do not hold the dictionary back ... whatever was reported" and "unless `--force` asks for the outputs anyway" are false for every error of the loading stage.**
  `SPEC.md:2104-2108`, `:2204-2206`; `src/ddd/cli.py:1912-1913`, `:1349-1352`. Trigger: a readable root including a component with a `schema` error. `ddd dump`: exit 1, 0 bytes on stdout;
  `ddd dump -o d.json`: no file; `ddd generate all --force`: nothing written (`p12.txt`). The same for 14 checks tried: `schema`, `json-syntax`, `file-kind`, `file-not-found`, `file-extension`,
  `include-empty`, `plugin-not-found`, `unknown-extension`, `duplicate-component`, `-unit`, `-type`, `-constant`, `-section`, `-raster`; only `init-invalid`, `unknown-type`,
  `duplicate-event`, `reserved-identifier` go through (`p13.txt`), and so does the `schema` the analysis itself raises for an array over the cap (`tests/test_cli.py:592-611`), so one identifier sits in both stages. The spec's sentence says the only exception is that "the root itself could not be read". The same stage also hides every analysis finding: a
  `schema` error in one file, an `init-invalid` in another -> only the first is reported (`p13.txt`). `docs/faq.rst:46-53` explains the two phases as intended; in the spec they exist only as a parenthesis of the toolbox
  (`:2527-2528`). The document is wrong, not the code (`cli.py:1898-1913`); this sentence is the 2026-09-15 fix of P1-I2, which overshot, and `tests/test_cli.py:2715` pins only its analysis half. Add to section 4: reading and checking are two stages, an error of
  the first stops the second, so there is no analysis, no dictionary and nothing for `--force` to write; and name what belongs to the first stage. S. See the open questions.

- **I4. A plugin's `print` at import, or in a validator of its model, lands inside the document on stdout.** `SPEC.md:1191-1200` ("and never inside a document"; "A plugin's own models are held to the same rule"),
  `:2175` ("given `-o`, stdout stays empty"). Only hooks are redirected: `src/ddd/plugins.py:514`, against `:207`, `:233`, `:314-338`, reached from `src/ddd/loading.py:1063`. Trigger: `print("BANNER")` at the top
  of the module -> `ddd dump` stdout starts `BANNER\n{`; `ddd check`, `list`, `generate`, `compare`, `artefacts`, `checks --plugin` with `--format json` start `BANNER`; `ddd dump -o` leaves `BANNER` on stdout; `ddd sources`' first line is
  `BANNER`. `ddd dump p.ddd.json > base.json` then `ddd compare base.json ...` -> `base.json:1:1: error[json-syntax]: in the baseline`. A `field_validator` printing does the same (`p15.txt`, `p22.txt`). Expected: on
  stderr, as for a hook (reproduced). `ddd lsp` is safe (`src/ddd/lsp/server.py:926`). A module-level print, or an imported library's banner, is an ordinary thing for a plugin to have. The code is wrong. Bind stdout to stderr around the
  import and the model validation, as `_call` does; S. `tests/test_plugins.py:2305-2320` prints only in hooks.

- **I5. "Nothing DDD writes is ever a file it read" is false: `--dictionary` and the artefacts overwrite an image, a map, a template or a description, exit 0.** `SPEC.md:2084` ("a path ... is refused, as is one the run read"), `:2191-2193`;
  `src/ddd/cli.py:1258` hands the guard `resolved.sources` alone, which is the description files and plugins. Triggers, all exit 0 (`p21.txt`, `p22.txt`):
  `generate a2l --image fw.elf --dictionary fw.elf` -> `wrote fw.elf (updated)`, 17848 bytes of ELF become 1164 of JSON; `--address-map m.json --dictionary m.json`; `generate c -t tpl --dictionary tpl/a.c.jinja2`;
  `generate a2l -o . --address-map P.a2l`; `generate c -o . -t tpl` with a template `p.ddd.json.jinja2` or `{component}.ddd.json.jinja2` -> the root or a component becomes `{}`, and `--dry-run` even says `would write a.ddd.json (updated)`.
  `ddd build-info p.ddd.json -o p.ddd.json` and `ddd schema component -o a.ddd.json` overwrite a description too, though neither read it. The triggers are rare; graded Important because the result is a destroyed input with a clean exit and the spec says the opposite twice.
  The code is wrong: add the image, the map and the templates to the guard, and hold every rendered path to the sources, S.

- **I6. A delivery that removes, renames or reuses a structured object with no leaf reports nothing, even under `--strict`.** `SPEC.md:161` ("every rule this specification states about a data object states it about an instance too"), `:1543`, `:1586`, `:1657`;
  `src/ddd/ir.py:774` (`comparable` is objects and leaves), `src/ddd/compare.py:1053-1061` (drops `_removed` and `_added`, "an instance that went is every one of its leaves removed"). Trigger: `I` of a structure whose members are all external types, produced by A and read by B, consumers `['B']`;
  the candidate drops both declarations -> `compare --strict`: "can replace", exit 0; same between two dumps; renamed to `K`: no finding, `--renames` writes `[]`; another `id` under the name: no `reused-name` (`p19.txt`, `p18.txt`). Expected: `removed-object` as an error, `renamed-object`, `reused-name`. `ddd check` is no help: the consumer went with it.
  Only the all-opaque shape falls through (any value or `bits` member is a leaf), hence not Critical; see pass 7. The code is wrong. Report removal, addition and rename at the instance when it has no leaf; S.

#### Minor

- **M1. A second project file stating `point_counts` is a fixed `schema` error, and a sub-project's value silently covers its siblings; 3.1 says neither (KNOWN: 2026-09-24 M1).** `SPEC.md:261-263`. `p2.txt`: `q.ddd.json#project.point_counts: error[schema]: point_counts is already stated as 'leading'`.
  New: a sub-project alone stating `leading` makes a component outside it `leading` too (`p21.txt`). The parallel rule for `extensions` is written (`:1161-1162`).
- **M2. "Reads a lower one with the defaults of that format" names no default for format 8 (KNOWN: 2026-09-24 M2).** `SPEC.md:1675-1677`, `:1955`; `src/ddd/ir.py:657-658` has the sentence. A format 8 baseline against a counted candidate -> `changed-interface` `point_counts: leading != none` (`p18.txt`). Right behaviour, unpredictable from the spec.
- **M3. "Every rule ... about a data object states it about an instance too" is broader than the tool and the spec (KNOWN: 2026-09-24 M3).** `SPEC.md:161`. `ddd list` has no row for an instance (`:2085`), `ok:` "counting the objects" says 5 for one object and one instance of two members times two (`:2166`, `p7.txt`) and 0 for an instance with no leaf, `--renames` lists only members (`:1528`), 5.2's "for every measurement" has exceptions. I6 is where it costs.
- **M4. A broken baseline stops a description candidate being analysed; 4.1 says it is analysed and all its findings reported (KNOWN: 2026-09-24 M4).** `SPEC.md:1514-1515`, `:1533-1535` against `src/ddd/deliveries.py:137, 179-182`. `p8.txt`: `compare` shows only the carried error and withholds the candidate's warnings; `check --baseline` on the same files shows all of them; no `--renames` file, though no side "could not be read"; a dumped candidate does get the comparison, the verdict and the file (`p23.txt`). `:1519-1520` covers the verdict only.
- **M5. "The number in its shortest spelling" is not what the C carries at the ends of 64 bits (KNOWN: 2026-09-24 M5, wider).** `SPEC.md:1014-1017`: `#define UMAX 18446744073709551615ULL`, `#define SMIN (-9223372036854775807LL - 1)` (`rich/out/ddd_types.h`, `backends/c/model.py:232-244`). And `:1016`'s `1e3` -> `SYSTEM_CONSTANT "BIG" "1000.0"` is against `:1912` "an integral value without a decimal point" unless a `SYSTEM_CONSTANT` is excepted, which the text does not say.
- **M6. Terminology residue (KNOWN: 2026-09-15 P1-M9, 2026-09-24 M6).** "structured variable" (`SPEC.md:1111`, `1211`, `1545-1546`, `1563`) beside the defined instance; "a2l" in prose (`:1019`, `1061`, `1077`, `1094`, `1101`, `1359`, `1368`, `2291`); `:900` "one value member" where `value` names a member shape, though a `bits` member is a leaf and counts toward the 100 000 (`p17.txt`: 100 001 of one `bits` member is refused); `:617` "in a types file" against 3.2; `:785` the one unlinked reference. New: "table" (`:1379-1381`, `:1545`) is never defined and means curve, map or axis; "the reference" means a reference declaration at `:1269` and an axis or input reference at `:476-483`; "variable" on 39 lines against "data object" on 25.
- **M7. Requirement words, against 1.1 (regressed: 2026-09-15 P1-M1).** Plain permissions that bind: `SPEC.md:723`, `822`, `966`, `994`, `1073` (all added for `empty-vocabulary`), `2046`. `:2032` "A symbol **shall** be stated once" binds data, so it is a **must**, as its neighbour `:2036` has. `:2040` sets bold on a phrase that is no requirement word. `*planned*` (6 places) is a status 1.1 does not define: a reader cannot tell it from a commitment. Read off (`mech.txt`, `mech3.txt`).
- **M8. `name-collision` says two uncompared pairs share the types header's namespace; there is a third, and it stops the compile.** `SPEC.md:1412-1414`. An enum and an enumerator of one name, in one enum or two: `ddd check` ok, `generate` ok, gcc: `'V' redeclared as different kind of symbol` (`p18.txt`, `p10.txt`). Name it, or compare it.
- **M9. The display format of an enum is stated as `%8.3` and written as `%8.0`.** `SPEC.md:1904-1906` ("under an identity or under a linear conversion ... and to `%8.3` otherwise") against `src/ddd/backends/a2l/model.py:630` and `rich/out/Rich.a2l:88`. The document is wrong.
- **M10. `null` against explicit zeros contradicts "compared as the storage it produces".** `SPEC.md:1600-1604`, `:356` against `src/ddd/compare.py:250-252`. Adding `"init": 0`, `[0, 0]` or `""` to an object with none -> `warning[changed-storage]: 's': init: 0 != none`; under `--strict` "cannot replace" (`p8.txt`, `p18.txt`), though no byte moves; `0` against `""` is silent. Conservative direction. Which is meant is the maintainer's (open questions).
- **M11. The address map's two scopes and "exactly".** `SPEC.md:2036` "a symbol the project carries **must** fit" against `:2040`: an `export: false` object at `4294967296` passes (`p23.txt`), so `:2040` is right and `:2036` is stale. `:2034-2035` "those two spellings exactly": `"0X10"` is accepted (`p15.txt`). Document.
- **M12. Section 5's "a run that fails writes, removes and records nothing" is overstated.** `SPEC.md:1694-1696` against its own `:2209-2210` and `src/ddd/backends/base.py:304-308, 372-376`: a failure while renaming or removing leaves updated targets new. Read off the lines.
- **M13. Two sentences of 5.1 narrower than the tool.** `SPEC.md:1719` `{component}<rest>.jinja2`: `x_{component}.h.jinja2` renders per component (`p15.txt`), as `--help` and `cmake/Ddd.cmake:605` say. `:1810` "no byte order mark": a template saved with one by a Windows editor hands it to the output, `b'\xef\xbb\xbfint x;\n'` (`p22.txt`); the loader tolerates exactly this on descriptions (`:192-193`). Strip it, or say so.
- **M14. "Compared without regard to case" holds in the loader alone.** `SPEC.md:193-194` against `cmake/Ddd.cmake:280` (configure error for `X.DDD.JSON`, `:2231-2232` not qualifying), `.pre-commit-hooks.yaml:21` (hook does not run), the GUI (pass 2 M4). Read off the lines.
- **M15. `ddd compare` cannot judge two component files with an `input`.** `SPEC.md:1506-1507` "project or component description", `:1513` "What does reach it is `--standalone`". `compare` has no such option (`:2151`, `p18.txt`), `-W` does not reach the baseline, so a baseline's `missing-producer` is always carried: exit 1, no verdict (`p19.txt`). `check --baseline --standalone` works and is the only route; `:1513` does not say so, sitting in a paragraph about `compare`.
- **M16. The shape limits stop at a declaration; 3.3 says "a shape" and "an array".** `SPEC.md:442-448`. A member with 65 or 600 dimensions, or 10 000 001 elements, passes, and 3000 instances of a 9 000 000 element member pass (`p20.txt`). Dimension count KNOWN (`plans/2026-09-16-review-fixes.md`, S-M1). `:443`'s reason ("the A2L ... carry every element") also contradicts `:901-902` ("a single `MATRIX_DIM`"); `analysis.py:147-149` has the true distinction.
- **M17. `init` spellings the text does not allow.** `SPEC.md:405-406`, `:455`. `"init": true` on `uint8` or `float32` is accepted, reaches C as `1U`, `1.0F` and the dictionary as `true` (`p20.txt`), where `1.0` on `uint8` is refused. `1.0` on `boolean` likewise (KNOWN, same plan, P9-M9).
- **M18. "`notes` of the same shape" is not the shape.** `SPEC.md:2159-2160`. A note carries `message` and `location` only (`p7.txt`), no `check` or `severity`. The sentence reads as a finding.
- **M19. Small sentences that are not so.** `SPEC.md:1757-1758` "so the angle forms come first": `../up.h` and `1wire.h` sort before `<os.h>` (`p20.txt`). `:459-461` "a literal a compiler refuses": gcc 15.2 warns and zeroes, exit 0 (`p20.txt`). `:409-410` "under the identity they are the raw ends themselves", with `:399`'s `3.4028234663852886e38`, against `:544`: a float's derived end is rounded, to `3.40282346639e+38`, just above `FLT_MAX` in the dump and the A2L (`p22.txt`; a float32 rounds it back, so harmless). `:1992` rasters "the declared entries": each also carries a derived `cycle_ns`.
- **M20. Section 7's list of what the tool offers is one sentence of 1106 words, 85 lines and 29 semicolons, three parentheses deep.** `SPEC.md:2064-2148`. `dump -o`'s promise (I3), `--dictionary`'s refusal (I5) and `ddd id`'s rules hide inside it, and none can be cited but by line. A table of commands, one short paragraph each, S. Pass 4 left the shape here.

### Status of the 2026-09-15 findings in this area

Those not plainly fixed. Fixed and re-probed: P1-I1 (`SPEC.md:1529-1533`, `p8.txt`), I3 (`:169`), I4 (`:276-280`, `p2.txt`), I5 (`:1546-1553`, `p8.txt`), M2 (`:81-89`), M3 (`:669-671`), M5 (`:1036-1039`, `:1485`), M6 (`:1600-1604`, `p8.txt`), M7 (`:1216-1217`, `:2193-2195`, `p14.txt`), M8 (`:2313-2314`), M10 (`:2087-2097`, `:2140-2142`, `:2169-2172`, `:1978-1981`, `:799`, `:2249-2251`, `p7.txt`, `p12.txt`), M11 (`:168-169`, `:173`, `:181`); its four open questions are settled in the text.

| id | finding | status | where |
| --- | --- | --- | --- |
| P1-I2 | `dump -o` under an error | rewritten, and now overclaims | I3 |
| P1-I4 | same bytes on any machine | fixed for wildcards; `ddd sources` still sorts as the platform does (`alpha, p, Zeta` here, `p2.txt`), KNOWN `plans/2026-09-16-review-fixes.md`, feeds a dependency set only, unfiled | `:2124` |
| P1-M1 | binding `may` set plain | REGRESSED, six new | M7 |
| P1-M4 | constant literal as written | residue | M5 |
| P1-M9 | terms | partly: instance, storage category, vocabulary file, standalone settled; the rest open | M6 |
| P1-M12 | small inconsistencies | fixed but one: `:1385-1386` and `:1926-1927` say "value-holding" and take the exceptions back at `:1940-1944`, unfiled | |

The stopped review of 2026-09-24, each finding against the present text:

| id | finding | status | where |
| --- | --- | --- | --- |
| I1 | section 7 says format 8 | STILL OPEN, same line | I1 |
| I2 | counted C storage unspecified | STILL OPEN | I2 |
| M1 | second file stating `point_counts` | STILL OPEN, wider | M1 |
| M2 | defaults of format 8 | STILL OPEN | M2 |
| M3 | every rule about an instance | STILL OPEN; it costs now | M3, I6 |
| M4 | broken baseline, description candidate | STILL OPEN | M4 |
| M5 | constant's shortest spelling | STILL OPEN, wider | M5 |
| M6 | terminology | STILL OPEN, more | M6 |

### Open questions

1. **Should `dump` and `generate --force` get past a loading error (I3)?** No, which is what the code and the FAQ say: only the sentences change. Yes, on the files that did load: a dictionary that silently lacks a component, which is what the gate exists to prevent. I would keep the code.
2. **Should a broken baseline stop a description candidate's analysis (M4)?** Yes keeps `compare` and adds a sentence saying the two commands part. No aligns it with `check --baseline` and makes 4.1 true as written. Same question for `--renames` there.
3. **Is an instance a row of `ddd list`, a count in `ok:`, an entry of `--renames` (M3)?** Yes is a tool change and a new rename entry a migration script sees. No narrows the concept row at `:161`. I6 should be fixed either way.
4. **May a sub-project state its own `point_counts` for what it includes (M1)?** Yes changes resolution to the nearest project. No keeps the refusal, and 3.1 says "stated by one project file, and it covers the whole tree".
5. **Does `init` compare `null` against zeros as storage or as spelled (M10)?** As storage makes `:1600-1604` true and a `.bss` to `.data` move silent. As spelled, the sentence gains an exception and `:356` should say an explicit zero is a different statement.
6. **Should `ddd compare` take `--standalone` (M15)?** Yes makes `:1513` true of it. No: one sentence naming `check --baseline --standalone` as the route for a component file.

### Test gaps

- `SPEC.md`'s stated dictionary format against `DICTIONARY_FORMAT`: `tests/test_documentation.py:1548-1557` reads the changelog only. How I1 survived two reviews.
- 5.2's `[y][x]`, the kind table and `:356` against a counted declaration: no guard names `point_counts` in 3.3 or 5.1.
- A plugin printing at import or in a validator: `TestAPluginThatPrints` (`tests/test_plugins.py:2305-2320`) covers hooks and backends, and its docstring says "Whatever a plugin prints".
- `--dictionary` onto an image, a map or a template, and a rendered path onto a description: `tests/test_cli.py:3243-3279` pins descriptions and dumps only.
- Compare of an instance with no leaf: no test in `tests/test_compare.py` names an external member (judged by grep).
- `dump` and `generate --force` under a loading error: `tests/test_cli.py:586-611` and `:2715` pin the analysis stage, `:1894` an unreadable root; nothing pins an included file's refusal (judged by grep).
- Older dictionaries: every test edits a current dump's `format` (`test_compare.py:535`, `test_constants.py:1105`, `test_plugins.py:965`, `test_point_counts.py:265`, `test_rasters.py:260`). A real dump per released format, as `old.sh` makes, would pin what is now only true.
- `name-collision`'s stated pairs: nothing compiles the uncompared ones (M8).

### Assessment

As a statement of what the tool does, SPEC.md is unusually exact, and I expected to find it worse: the links, the check sets, the requirement grammar, the file format rules and the whole of 5.2 and 5.3 survive contact with the tool, its citations check out, and dictionaries from the real old releases still read. The defects are of three kinds. Universal sentences written to close a past finding that say more than the code does: "whatever was reported", "never inside a document", "nothing DDD writes is ever a file it read", "every rule about a data object"; each of the last three hides a real hole in a guard, and that is where the spec is most useful as a test of the code. New material that reached one section and not the ones it changes: `point_counts` and the format number are still as the stopped review left them six weeks ago; that report was never acted on, and all eight of its findings stand. And the slow drift a 29,000 word document collects: terms, plain `may`, one 1,106 word sentence. Nothing here is a redesign; the text fixes are hours, I4, I5 and I6 are small code fixes. Fix I1, I2 and I3 before the next release, because they are the sentences an implementer relies on.

```candidates
5|I1|SPEC.md:2215|Section 7 says the dictionary format is 8; 5.3 and the tool write 9, so a reader built from it refuses every dictionary (KNOWN 2026-09-24 I1, see pass 4 M12)
5|I2|SPEC.md:434|point_counts leading: C storage stated nowhere; kind table, [y][x], null init and init shape contradict the flat counted declaration (KNOWN 2026-09-24 I2)
5|I3|SPEC.md:2104|dump and generate --force promise output under any error; every loading-stage error yields no dictionary and no file, and hides analysis findings
5|I4|src/ddd/plugins.py:207|A plugin's print at import or in a model validator lands inside dump, --format json and sources on stdout, against never inside a document
5|I5|src/ddd/cli.py:1258|--dictionary and artefacts overwrite the image, map, template or description the run read, exit 0, against nothing DDD writes is ever a file it read
5|I6|src/ddd/compare.py:1061|Removing, renaming or reusing a consumed instance with no leaf reports nothing, even under --strict; can replace, renames []
5|M1|SPEC.md:261|A second project file stating point_counts is schema and a sub-project's value covers its siblings; 3.1 says neither (KNOWN 2026-09-24 M1)
5|M2|SPEC.md:1675|Defaults of older dictionary formats omit format 8's point_counts none (KNOWN 2026-09-24 M2)
5|M3|SPEC.md:161|Every rule about a data object states it about an instance is contradicted by ddd list, the ok count and --renames (KNOWN 2026-09-24 M3)
5|M4|SPEC.md:1514|compare with a broken baseline withholds a description candidate's findings and the renames file, unlike 4.1's text and check --baseline (KNOWN 2026-09-24 M4)
5|M5|SPEC.md:1014|Constant shortest spelling is not what C carries at the ends of 64 bits; 1000.0 against an integral value without a point (KNOWN 2026-09-24 M5)
5|M6|SPEC.md:900|Terminology residue: structured variable, prose a2l, value member, table and reference undefined, variable against data object (KNOWN)
5|M7|SPEC.md:723|Requirement words: six plain binding may, shall on data at 2032, planned undefined (regressed P1-M1)
5|M8|SPEC.md:1412|name-collision names two uncompared pairs; an enum and an enumerator of one name is a third, clean check then a compile error
5|M9|SPEC.md:1904|Enum default display format stated %8.3 by the letter, written %8.0
5|M10|SPEC.md:1600|init compared as the storage it produces, yet null against explicit zeros is changed-storage and cannot replace under --strict
5|M11|SPEC.md:2036|Address map: a symbol the project carries against one the A2L states; those two spellings exactly accepts 0X10
5|M12|SPEC.md:1694|A run that fails writes, removes and records nothing is overstated against 2209 and base.py
5|M13|SPEC.md:1719|5.1 narrower than the tool: {component} anywhere in a name renders per component; a template's BOM reaches the output against no byte order mark
5|M14|SPEC.md:193|Extension compared without regard to case holds in the loader alone: cmake module, pre-commit hook and GUI are case sensitive
5|M15|SPEC.md:1513|ddd compare has no --standalone, so two component files with an input never get a verdict; 4.1 reads as if it had
5|M16|SPEC.md:442|64 dimensions and 10 000 000 elements stop at a declaration: a member passes with 600 dimensions or 10 000 001 elements (KNOWN in part, S-M1)
5|M17|SPEC.md:405|init true on uint8 or float32 is accepted and reaches the dictionary as true; 1.0 on boolean likewise (KNOWN in part, P9-M9)
5|M18|SPEC.md:2160|notes of the same shape: a note carries message and location only
5|M19|SPEC.md:1757|Small untrue sentences: angle forms first, a compiler refuses a tiny literal, identity limits the raw ends, rasters the declared entries
5|M20|SPEC.md:2064|Section 7's offer is one sentence of 1106 words and 85 lines, burying promises that cannot be cited
```

## Pass 6: file formats (SPEC 3.1 to 3.10)

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-6/`. Line numbers are on the review tree.

### Scope covered

- Read in full, with line numbers: `SPEC.md` 1-1221 and 1950-1993 (3.11 only as far as `extensions` and `plugins` touch the formats); every file of `src/ddd/models/`;
  `src/ddd/loading.py`; `src/ddd/ir.py`; `src/ddd/build_info.py`; `src/ddd/lsp/discovery.py:1-122`, `src/ddd/cli.py:1632-1655` (the record's writer and reader); all ten pages of
  `docs/file_formats/`, `docs/data_contracts.rst`, `docs/data_dictionary.rst`, `docs/build_integration.rst:272-312`; `gui/scripts/schemas.mjs`, `gui/src/lib/formats.ts`, the head of `gui/src/generated/component.ts`;
  `schemas/ddd_{project,constants,rasters,sections,units,types}.schema.json`; pass 2 of `SCRATCH/review-2026-09-15.md`, `SCRATCH/reports/pass-5.md` in full, the candidates of passes 1 to 4.
  `analysis.py` only at its format rules (85-160, 394-415, 1025-1050, 1368-1380, 1485-1505, 1600-1620, 1655-1685, 1725-1745, 2118-2160, 2190-2205, 2305-2325, 3262-3345, 3564-3610).
- `schemas/ddd_component.schema.json` and `ddd_dictionary.schema.json` were not read line by line: their structure was listed, their texts are the docstrings read above, and all eight regenerate byte for byte (`schemas_all/`), and both were exercised by the differential.
- Ran (`e1`-`e15`, each `.py` beside its `.txt`): about a thousand runs of the real cli over throwaway files, every key of every format with valid and invalid spellings, each error read for text and location (`e1.txt` reading, roots, project; `e2.txt` component, declaration, definition; `e3.txt` conversions, enums, strings; `e4.txt` types, units, sections, constants, rasters; `e5.txt` interface, storage, presentation, `point_counts`; `e6.txt` free text into C and A2L, with gcc under the CI flags; `e7.txt` build record, dictionary files, name lengths; `e10.txt`-`e14.txt` the rest); a differential of the published schemas against the models over 8013 documents (`differential.txt`); the format pages' unshipped transcripts rebuilt (`doc_transcripts.txt`, 59 cases) and their generated fragments looked up in real output (`e9.txt`, 50); `keys.txt`, 182 keys against SPEC 3 and their pages; `tests/test_models`, `test_loading`, `test_point_counts`, `test_rasters`, `test_constants`, `test_units`, `test_sections`, `test_types`, `test_structures` (green).
- Not covered: whether a real calibration tool reads what I2 describes; the GUI's and the language server's own reading of these files (pass 2 M4, passes 10 and 13); `gui/src/generated` was not regenerated, because the script writes into the tree.
- Met again and cited rather than re-filed, with what this angle adds:
  - pass 5 I2: the format pages are silent too. `docs/file_formats/variable_definition.rst` never names `point_counts`, its table (`:463-494`) states `[size]`, and `project.rst:67`, `component.rst:65` link nowhere; the one account is `docs/data_dictionary.rst:182-221`, which does not say that `init` excludes the counts.
  - pass 5 M1: `docs/data_dictionary.rst:192` "may be stated once" against `src/ddd/loading.py:1099-1112`, which takes a second file of the same value.
  - pass 5 M16, M17, M19: reproduced (`e2.txt`, `e3.txt`). Beside M19, `3.4028235e38`, the usual spelling of `FLT_MAX`, is `init-invalid` (`e10.txt`).
  - pass 5 M8 and `SPEC.md:1413-1414` *(planned)*: enum or enumerator against a declared type, clean check (`e10.txt`).
  - pass 1 M12: the partial identifier; I2 adds the whole identifier and the strings.
  - pass 1 I4: a section's `access`, `alignment` and `description` reach neither the dictionary nor any output (`e11.txt`), so a comparison cannot see them.
  - pass 3 I4 stands for the GUI's copy. It adds nothing else here: `gui/src/lib/formats.ts:1` is the whole use of `generated/component.ts`, and no list of datatypes or kinds is restated in `gui/src` outside tests.
  - pass 4 M6: `$schema` is the one key of 182 on no project or component page (`keys.txt`); `docs/file_formats/index.rst:72` says every object is closed and names no exception.
  - pass 5 I5: `ddd build-info p.ddd.json -o named.ddd.json` writes what the record's own rule says it must not be named (`e7.txt`).

### Strengths

- **Key by key, the five sources agree.** All 182 keys are in SPEC 3 and on their page, `$schema` aside (`keys.txt`). Every default in the tables is the model's. About a thousand probes found the check the spec names, at the location it names, in every rule of 3.1 to 3.10 that states one, with the exceptions below.
- **The published schemas are generated, current and honest.** Byte identical to `ddd schema all` (`schemas_all/`). Across 8013 mutated documents the schema and the model part only in the classes the documents already state (`differential.txt`, M9, M10). All 34 description files under `examples/` and the dumps of all nine example projects validate on both sides (`e8.txt`, `e15.txt`); every JSON block of the format pages loads.
- **The pages show what the tool prints.** Of 59 rebuilt transcripts 31 match to the byte, 24 differ only by `info[missing-id]` (M13), 2 only by my key order, 2 are stale (M13). 44 of 50 generated fragments are verbatim in real output, the other 6 shortened or hypothetical on purpose. The dictionary page's two blocks equal the real schema and the demo's dump.
- **Free text cannot hurt the outputs, with one exception (M6).** `*/`, `/*`, `/*/`, newlines, CR, NUL, BEL, quotes, a trailing backslash and jinja markers in `description`, `unit` and the project, component, type, member, enumerator and constant texts all compile under `-std=c11 -Wall -Wextra -Wpedantic -Werror ...` and give a balanced A2L string (`e6.txt`). A string `init` escapes `"`, `\` and `??`. A generated A2L identifier is clipped to 128 and kept unique (`e7.txt`).
- **Reading holds at the edges.** BOM, UTF-16, latin-1, two kinds at once, a dump as a root or an include, a NUL in a path, a UNC path, `CON`, `NUL`, a directory, 64 and 65 levels, nesting to 100 000: each a located finding and no traceback (`e1.txt`, `e12.txt`). A junction and its target are one file (`e10.txt`).
- **The vocabularies are exact.** Periods sort as the decade rule says; event bounds, duplicates within and across files, `raster-kind` with `consumer-raster`, alignment by datatype through nested structures, `dimension-value` on `2.0` and `1e1`, a 128 character name on every key, `empty-vocabulary` on all five kinds at the list's own pointer (`e4.txt`). `point_counts` resolves as documented, a reader's own value never reaches an object, and `point-counts-unrepresentable` fires at exactly 256 and 128 (`e5.txt`).
- **The build record does what 3.6 says** (`e7.txt`): shape, `""` for no image, an unwritten project recorded, an unknown severity refused at configure, a newer or unknown record declined with its reason.

### Issues

#### Critical

None.

#### Important

- **I1. A member's `a2l` block is accepted and ignored where the member names a structure: `export: false` keeps nothing out.** `src/ddd/analysis.py:3325` recurses into the nested structure without the member's block, and only the innermost member's reaches a leaf (`:3318`). `SPEC.md:931-933` "each member's own `export` for the member"; `docs/file_formats/types.rst:264-266` "keeping one member out of the a2l ... is a decision about that member alone"; `src/ddd/models/types.py:208-214`. Trigger: `O_t` with `{"name": "j", "member": "value", "typename": "I_t", "a2l": {"export": false}}` and `V` of `O_t[2]` -> `ddd check --strict` clean, `V[0].j.a`, `V[0].j.b`, `V[1].j.a`, `V[1].j.b` all in the A2L and `export: true` in the dump. `format` and `display_identifier` on such a member vanish the same way. Expected: the sub-structure kept out, or a refusal, which is what the same block on an external member gets for the same reason, "no record for the block to shape" (`analysis.py:1729-1738`). The check and the a2l both say nothing, so the author believes it worked. Reproduced, `e10.txt`. Fold `export` down the walk and refuse the other two as on an external member, or refuse all three; one sentence in 3.7; S.

- **I2. Nothing holds an A2L string to the 255 characters of the standard, or an access path to its 1024.** `src/ddd/backends/a2l/model.py:740` (`a2l_string`) passes any length; `SPEC.md:1910-1912` states escaping only; `SPEC.md:1444-1448` limits `a2l-unrepresentable` to four dimensions. ASAP2 1.6.1 table 5, the row after the one `SPEC.md:422-423` enforces: `string` "maximum MAX_STRING (at present = 255)", and `ident` at most `MAX_IDENT` 1024 (`SCRATCH/pass-1/pdf/asap2-1.6.1.txt:1386-1395`, `:1444-1446`); `LongIdentifier` is a `string` (`:2420`). Triggers, `ddd generate a2l --strict`, exit 0, no finding: a `description` of 300 characters written whole on the record and the group; a `unit` of 300; a project `description` of 300 on `PROJECT`, `HEADER` and `MODULE`; eight levels of members of 32 characters -> `SYMBOL_LINK` of 265; 64 levels -> a record name of 2113. A description of more than three lines is ordinary in a grown project, and `docs/file_formats/variable_definition.rst:92-96` invites the sentence. The tool holds a raster to eight bytes for a field it does not even write yet, and identifiers to the same table, for the stated reason that a name that cannot be put in the a2l is of no use (`docs/data_contracts.rst:115-117`). What a given tool does with the excess I could not test (open question 3). Reproduced, `e13.txt`, `e6.txt`. `a2l-unrepresentable` on each, carrying the text whole; S.

#### Minor

- **M1. A curve with no `axis` is told `Field required` at the definition, with no key: `axis` is also the name of a union tag.** `src/ddd/loading.py:93`, `:1537`. A segment the document lacks is judged by its spelling, and a missing key is by definition one it lacks. Trigger: `{"kind": "curve", ...}` with no `axis` -> `...definition: error[schema]: Field required`, where a map says `...definition.x_axis`, an axis `...definition.size`. `docs/file_formats/index.rst:77-78` "names the offending key and points at it". In a plugin's block it collapses further: required fields named `axis`, `string`, `map` and `int` arrive as one finding at the block, `...extensions.pl: Field required`, through `_one_per_place`, against `loading.py:1512-1522`. Reproduced, `e2.txt`, `e7.txt`. A `missing` error's last segment is always a key; S.

- **M2. The reader is handed pydantic's and python's words.** `src/ddd/loading.py:1328-1330`, `:151`. `"kind": "signal"` -> `Input tag 'signal' found using 'kind' does not match any of the expected tags: <ObjectKind.MEASUREMENT: 'measurement'>, ...`, at `definition` rather than at `definition.kind`; no `kind` -> `Unable to extract tag using discriminator 'kind'`; `"dimensions": 4` -> `Input should be a valid tuple (got: 4)`; `[]` -> `Tuple should have at least 1 item after validation, not 0`; `"project": []` -> `Input should be a valid dictionary or instance of Project`; a list at the top -> `found list`, `null` -> `found NoneType`; a JSON `null` is quoted as `None`, `true` as `True`. The first union arm wins, so a non-number limit is told to be `a valid integer` though limits may be fractional, and `["a b"]` as a dimension the same with no word of a constant. Each names the key, so nobody is stuck, and `docs/file_formats/types.rst:111` even transcribes one. Reproduced, `e1.txt`, `e2.txt`. A small table at the one call site; S.

- **M3. Four messages about a number or a nesting a user cannot act on.** (a) `"value": 1e400` -> `Input should be a valid integer (got: inf)`, and on an `init` as well, where a limit says `finite number` (`src/ddd/loading.py:1351-1358` keeps the first arm; `SPEC.md:213-214`). (b) Two byte order marks -> `Unexpected UTF-8 BOM (decode using utf-8-sig)`. (c) New: a whole number of over 4300 digits -> `json-syntax`, unlocated, `use sys.set_int_max_str_digits() to increase the limit`, against `SPEC.md:418-420` "`schema` where it is written" and against `src/ddd/models/rasters.py:36-38`, which calls this very sentence "python's advice to a programmer". (d) An `init` nested past 100 levels -> `Recursion error - cyclic reference detected`, one finding but no cycle, at a pointer of a hundred `[0]`, against `SPEC.md:211-212` `json-syntax`. (a), (b), (d) are P2-M7 and P2-M9. Reproduced, `e1.txt`, `e3.txt`, `e10.txt`.

- **M4. The refusal of a duplicate key does not say where, and its reason is that such a thing is costly to locate.** `SPEC.md:208-210`; `src/ddd/loading.py:144-146`, `:170-186`. Trigger: `"name"` twice in one of a thousand objects -> `c.ddd.json: error[json-syntax]: key 'name' appears twice in one object`, no line, no pointer, and every object of the file has a `name`. `NaN` and `Infinity` the same. `_read_text`'s promise is "a located finding" (`:1264`). Reproduced, `e1.txt`. On that refusal parse a second time with a hook that records rather than raises, and walk to the pointer; S.

- **M5. A clean check hands the writers a value they cannot carry, or changes it.** (a) A lone surrogate, `"description": "\ud83d"` or `"unit"`: JSON can spell it and `str` keeps it (`src/ddd/models/objects.py:503`, `:506`; `src/ddd/loading.py:108-128`). `ddd check` exit 0; `ddd list`, `dump`, `dump -o`, `generate c`, `generate a2l` exit 2, `ddd: 'utf-8' codec can't encode character '\ud83d' in position 459`, no location, usage error's exit code. `SPEC.md:192` "encoded UTF-8". A key with a pattern refuses it (`e6.txt`). (b) `1e400` in an `extensions` block is `inf`, and the dump writes `null`, with a clean check and no finding, against `docs/data_contracts.rst:132` "every number", `SPEC.md:213-214` and `docs/data_dictionary.rst:262` "it round-trips". (c) A block nested 100 levels: `check` clean, `dump` exit 2, `Circular reference detected (depth exceeded)`. (d) `"offset": 18446744073709551617` reads as `1.8446744073709552e+19`, against `SPEC.md:418-420` "every integer a description states"; `Real` (`src/ddd/models/common.py:169`) lacks the guard `common.py:179-198` explains. All rare. Reproduced, `real_surrogate.txt`, `e6.txt`, `e14.txt`, `e15.txt`. In `parse_json_text`, refuse a lone surrogate and an infinity as `json-syntax`; S.

- **M6. The guard on a condition's trailing backslash misses its trigraph.** `src/ddd/models/component.py:82`; `SPEC.md:327-331`. Trigger: `"condition": "defined(A) ??/"` -> check clean, `#if defined(A) ??/`, and under the repository's own flags (`docker/compile.sh`, `-std=c11`) the next line is spliced in: `error: missing binary operator before token 'extern'`, the failure `docs/file_formats/component.rst:322-324` describes for `\`. `src/ddd/backends/c/literals.py:73` knows about trigraphs for a string literal. Reproduced, `e6.txt`. Refuse `??/` as well; S.

- **M7. The depth rule still depends on the order of two entries.** `src/ddd/loading.py:1195-1200`, against `:1232-1243` ("the ordering this holding back is here to make invisible") and `SPEC.md:250-253`. Trigger: root includes `deep1` (a chain reaching `shared` at level 64) and `shared` (which includes `leaf`). Long route first: `shared` is read at 64, its entry crosses, the shallow route finds `shared` already seen and does not walk it again, `error[include-depth]`, which cannot be relaxed. The entries swapped: clean. Needs a tree 64 deep. Reproduced, `e10.txt`. Revisit a project reached at a shallower level; S.

- **M8. The `description` of a scalar or external type reaches nothing, and is published as "offered to the c templates".** `src/ddd/models/types.py:376`, `:484`, so hover text in both schemas; `docs/file_formats/types.rst:174`. Trigger: `SCALARTYPEDESC`, `EXTERNALTYPEDESC` in a full `generate all --dictionary`: in no file, the dictionary included. `types.rst:218-222` says why a scalar type has no typedef; nobody followed that through to its text. Reproduced, `e11.txt`. Say "documentation for the reader of this file"; S.

- **M9. "Can never disagree" is untrue, and "cannot be expressed" is true of fewer rules than it says.** `docs/data_contracts.rst:16-19` "Two parts of DDD can therefore never disagree about a file format"; `src/ddd/models/schema.py:153-157`; against `docs/file_formats/index.rst:171-172`, which has it right, and `differential.txt`: 17 keys one way (M10), 43 the other. `index.rst:169` says such rules "cannot be expressed as a constraint", yet `datatype` or `typename` (`oneOf`), `conversion` beside `datatype` (`dependentRequired`), a non-zero `factor`, the spelling of `cycle`, `header` and `condition`, and an `extensions` key all can, and they are the mistakes an editor would most usefully underline. The last contradicts the spec: `SPEC.md:258-260` says a bad key is `schema`, and `schemas/ddd_project.schema.json:54-64` has `patternProperties` and nothing closing it, so `{"extensions": {"Bad-Name": 1}}` validates (`src/ddd/models/project.py:45`, `objects.py:474`). Reproduced, `differential.txt`, `e15.txt`. Correct the sentences; publish `propertyNames` at least; S.

- **M10. The strict-mode residue is exactly as it was (KNOWN, `plans/2026-09-16-review-fixes.md`, decision 10, P2-I2).** The model reads what the schema refuses on `volatile` and `a2l.export` (`0`, `1`, `0.0`, `"1"`, `"no"`, `"true"`), `factor`, `offset`, `limits.min` and `.max` (`true`, `"1"`, `"1.5"`, `"1_000"`), `bits` (`true`, `"1"`). `"bits": true` is a one bit field. The direction is safe, the schema being stricter; nothing outside the list leaks (`differential.txt`). See open question 1.

- **M11. An external type cannot be called `size_t`, for a reason that does not apply to it.** `src/ddd/analysis.py:1372-1377`; `SPEC.md:880-881`; documented at `docs/file_formats/types.rst:357-359`. `{"type": "external", "name": "size_t", "header": "<stddef.h>"}` -> `reserved-identifier: type name 'size_t' is reserved by the c language`. The rule exists because a variable of that name would produce `size_t size_t;` (`src/ddd/models/reserved.py:12-16`), and an external type declares nothing. With `-W reserved-identifier=ignore` it generates and compiles clean. `size_t`, `ptrdiff_t`, `wchar_t` and a vendor's `__x_t` are what such an entry is for, and DDD offers no other way to hold a `size_t` member. Reproduced, `e14.txt`. Hold an external name to the keywords only; S.

- **M12. A BOM is accepted "since it is what ... PowerShell redirection put there", and Windows PowerShell's redirection puts UTF-16 there.** `docs/file_formats/index.rst:115-116`, `src/ddd/loading.py:1268-1270`, `docs/data_dictionary.rst:30`, `:54`. Trigger: `powershell.exe -NoProfile`, `ddd dump p.ddd.json > d.json` -> first bytes `FF FE 7B 00`; `ddd compare d.json ...` -> `is not valid utf-8 (byte 0): DDD description files are utf-8`, exit 1, a sentence about the wrong kind of file. A profile setting UTF-8 hides it. `-o` works and is documented for scripts; the redirection is what the page shows first, and this is the default shell of a Windows machine. Reproduced, `ps/transcript.txt`. Say so on both pages; S.

- **M13. Small sentences that have drifted.** All reproduced or read off.
  - `docs/file_formats/variable_definition.rst:439` and `docs/data_contracts.rst:121`: `^%\d*\.\d+$`; the message has said `^%[0-9]*\.[0-9]+$` since `src/ddd/models/common.py:153`. The transcript carries a trailing comment, so nothing runs it.
  - `docs/data_contracts.rst:124`: what a condition may not hold omits the trailing `\`; `:25-28` the diagram shows two of the seven kinds; `:206` a comment quotes a raster pattern long gone.
  - 24 of the 59 unshipped transcripts omit `info[missing-id]`: `variable_definition.rst:329-332` shows `2 errors, 1 warning`, and a reader copying the page's JSON, which has no `id`, gets three more lines and `2 errors, 1 warning, 3 infos`; `project.rst:203` shows `ok:` where the reader gets `1 info`.
  - `docs/file_formats/types.rst:601` "each nesting the next" over `types[64] ... 'T65_t'`: that output is each nesting the previous; as written it is `types[0] ... 'T1_t'` (`e14.txt`).
  - `src/ddd/ir.py:178`, `:545` "or the identity when none was given", published in the dictionary schema, predates the required conversion; `:318` "`null` when it names a declared type": a member naming a scalar type has its `datatype` (`Sample_t.value`).
  - `SPEC.md:723`, `:823`, `:994`, `:1073` say an empty file loads; only `docs/file_formats/units.rst:48` of the five pages does (the changelog: pass 4 I8).
  - `src/ddd/build_info.py:54`: `format` is lax where the dictionary's is strict (`src/ddd/ir.py:672`); `0`, `-1`, `"1"`, `true` are read as records, against `SPEC.md:809-810` "declines rather than misreads". Nobody writes one (`e7.txt`).

### Status of the 2026-09-15 findings in this area

Fixed and re-probed: P2-I1 (`src/ddd/models/objects.py:35-39`, `e2.txt`), P2-I3 (`src/ddd/loading.py:1361-1391`, `e2.txt`), P2-M1 (`README.md:486`), P2-M2 (`docs/file_formats/project.rst:180`), P2-M3 (`docs/data_contracts.rst:309`), P2-M4 (`docs/file_formats/constants.rst:29-33`), P2-M5 (`src/ddd/models/types.py:486-495`, `rasters.py:94-102`, `conversion.py:190-196`, `objects.py:512-513`, `:573-574`), P2-M8 (`src/ddd/models/common.py:140-143`, `SPEC.md:1091-1093`, `e2.txt`).

| id | finding | status | where |
| --- | --- | --- | --- |
| P2-I2 | keys read what the schema refuses | STILL OPEN, KNOWN, deferred by decision 10 | M10 |
| P2-M6 | `4.0` in an editor, refused by the loader | STILL OPEN, KNOWN; now said in each of the five descriptions, and a guard holds the sentence | `differential.txt` |
| P2-M7 | `1e400` on a constant, two BOMs | STILL OPEN, both; the first on `init` too | M3 |
| P2-M9 | deep `init` | reduced from a hundred findings to one; the words and the identifier are still wrong; the boundary is now 100 levels | M3 |

### Open questions

1. **Strict mode (P2-I2).** Strict on the six keys makes the loader refuse what the schema refuses and `"volatile": "no"` a finding, at the cost of a migration note for any project spelling them; left, the differential's class A stays and M9's sentences should say so. The list has not moved in two reviews.
2. **A member's `a2l` on a nested structure (I1).** Honoured: `export: false` keeps the subtree out of every instance of the type, which fits "per member". Refused: simpler, and it matches an external member. Either ends the silence; the first is what the docs promise.
3. **Over-long strings (I2).** Only the calibration tools you target can answer. If they read the excess, a warning is enough; if they truncate or refuse, it should be an error, and a project of long descriptions needs a way out, such as truncating with a finding.
4. **Float point counts.** `SPEC.md:1380` "a float holds any count", `docs/superpowers/specs/2026-09-23-record-layouts-design.md:40-42` "nothing in the format refuses a float count", and C writes `2.0F` (`e5`). No tool has been asked to read `NO_AXIS_PTS_X 1 FLOAT32_IEEE`. If one reads a count as an integer, `point-counts-unrepresentable` should refuse floats.
5. **How much of the rules to publish (M9).** More in the schema gives editors the common mistakes, and makes pydantic's output less plainly "derived" (`json_schema_extra` on `DataObject` and `Member`).

### Test gaps

- `tests/test_structures.py:1240-1247` pins `export: false` on a value member; nothing on a member naming a structure (I1).
- `tests/test_transcripts.py:13-14`: a transcript with a trailing comment is shown, not run, which is how `variable_definition.rst:439` went stale and why the `missing-id` lines were never noticed. `doc_transcripts.py` shows they can run: 59 cases, the files inline.
- No generic differential between the published schemas and the models; `tests/test_documentation.py` holds sentences. `differential.py` is 120 lines and takes seconds.
- No test of a location for a missing key per key (M1): `tests/test_types.py:54` and its like match `Field required` on the model, where the pointer has not been made yet (judged by grep).
- `tests/test_hardening.py:1165` asserts the text of a duplicate key and not where it is (M4).
- No test feeds a lone surrogate through a file: `tests/test_gui_hostile.py:38-39` is about request bodies.
- `tests/test_generation.py:612` pins trigraphs in a string literal and nothing in a condition (M6).
- No test states the length of an A2L string (`MAX_STRING` appears nowhere in the repository).
- Nothing asserts where each `description` goes: M8 would have shown at once.

### Assessment

This is the soundest area of the tool I can point to. Five sources (spec, schema, model, loader, page) describe about two hundred keys and agree; the spec's rules are what the tool does, down to the check name and the pointer, over a thousand probes; the published schemas are generated and current, the examples and the pages' fragments are real, and the free text an author can type cannot break the generated C or the A2L's quoting, with one exotic exception. The review's earlier Important findings here are fixed. What remains is at the edges, and it is of three kinds. A key that is accepted and silently means nothing, of which the nested member's `a2l` is the one a user will hit (I1) and a scalar type's description the harmless one (M8). A limit of the target format applied to its identifiers and not to the strings in the next row of the same table (I2). And wording: python's vocabulary in the messages, one pointer that loses its key by a name collision, a couple of sentences claiming more than the code does. The one structural remark is that the "shown, not run" convention for transcripts is where these pages rot, and they have started to.

```candidates
6|I1|src/ddd/analysis.py:3325|A member's a2l block on a member naming a structure is accepted and ignored: export false keeps nothing out, format and display_identifier vanish
6|I2|src/ddd/backends/a2l/model.py:740|Nothing holds an A2L string to MAX_STRING 255 or an access path to MAX_IDENT 1024: description, unit, SYMBOL_LINK over the limit under --strict
6|M1|src/ddd/loading.py:1537|A curve with no axis is told Field required at the definition with no key, because axis is a union tag; required plugin fields so named collapse into one finding
6|M2|src/ddd/loading.py:1330|Python and pydantic words reach the reader: tuple, instance of Project, NoneType, <ObjectKind.MEASUREMENT>, discriminator, at definition rather than kind
6|M3|src/ddd/loading.py:1357|1e400 and an init say valid integer, two BOMs and a 5000 digit number give python's advice, init past 100 levels says cyclic reference (P2-M7, P2-M9 open)
6|M4|src/ddd/loading.py:145|A duplicate key is refused with no line or pointer, the spec's reason being that it is costly to locate
6|M5|src/ddd/loading.py:120|A clean check hands writers what they cannot carry: lone surrogate exit 2 on list, dump, generate; 1e400 in a block dumps as null; deep block; offset past 64 bits rounds
6|M6|src/ddd/models/component.py:82|A condition ending in the trigraph ??/ passes the trailing backslash guard and splices the next line under the CI's -std=c11
6|M7|src/ddd/loading.py:1195|include-depth depends on the order of two entries: a project first read at level 64 is not walked again from a shallow route
6|M8|src/ddd/models/types.py:376|The description of a scalar or external type reaches nothing, published as offered to the c templates
6|M9|docs/data_contracts.rst:16|Can never disagree is untrue, cannot be expressed overstated; a bad extensions key validates against the published schema, against SPEC 3.1
6|M10|src/ddd/models/objects.py:584|Strict-mode residue unchanged: volatile, export, factor, offset, limits, bits read what the schema refuses (KNOWN, decision 10, P2-I2)
6|M11|src/ddd/analysis.py:1372|An external type cannot be named size_t or wchar_t: reserved-identifier fires though it declares nothing; relaxed it compiles clean
6|M12|docs/file_formats/index.rst:115|BOM justified by PowerShell redirection, which writes UTF-16 on Windows PowerShell; the documented ddd dump > file is then refused
6|M13|docs/file_formats/variable_definition.rst:439|Drifted sentences: stale format pattern on two pages, 24 transcripts omit missing-id, chain comment reversed, stale ir docstrings, empty vocabulary on one page of five, lax record format
```

## Pass 7: consistency checks and comparison (SPEC 4, 4.1)

Transcripts and probe scripts are in `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad/pass-7/`; a bare `name.txt` below is a file of that folder.

### Scope covered

**Read in full, with line numbers:** `SPEC.md` 1222-1680 (sections 4, 4.1), 1114-1221 (3.11), and the sentences the checks lean on (325-332, 362-378, 455-521, 572-600, 926-940, 2148-2158); `src/ddd/analysis.py` 1-3692; `src/ddd/compare.py` 1-1126; `src/ddd/identity.py` 1-209; `src/ddd/diagnostics.py` 1-590; `src/ddd/loading.py` 1-1608; `src/ddd/ir.py` 1-817; `src/ddd/deliveries.py` 1-231; `src/ddd/plugins.py` 1-530; `src/ddd/addresses.py` 1-259; `src/ddd/models/objects.py`, `conversion.py`, `types.py`, `reserved.py`, `sections.py` in full, `component.py` 1-95, `constants.py` 30-115; `src/ddd/cli.py` 736-1022, 1129-1296, 1828-2006; `src/ddd/lsp/diagnostics.py` 125-160; `docs/consistency_checks.rst` and `docs/comparing_deliveries.rst` in full; `README.md` 518-650; `tests/test_comparison_tables.py` 1-200; pass 3 of the previous review; the left-open items of `2026-09-16-review-fixes.md`, and a grep of the left-open sections of all 51 plans; the candidates blocks of passes 1-6.

**Ran:**
- The registry against SPEC, both doc pages, README and the code (`registry_crosscheck.py`).
- Every identifier fired on a throwaway project (`fire1.txt`, `fire2.txt`, `cmp2.txt`, `doc_edits.txt`).
- All 27 transcripts of the two doc pages that can run, on a copy of `examples/`, 6 of them after the edit the page names (`doc_transcripts.txt`, `doc_edits.txt`). Three name a file the repository does not hold and were not run.
- About 60 comparison scenarios, each as descriptions and as dumps (`cmp1.txt`, `cmp2.txt`, `cmp3.txt`, `misc1.txt`, `misc4.txt`).
- A mutation run: every value of a rich project edited, 984 edits, one by one and mirrored onto its readers. Each edit went through the check, the comparison and the C and a2l renderers (`mutate.py`, `mutate.txt`, `mutate2.txt`, `accepted.txt`).
- gcc under the CI flag set on `ddd_globals.c` of all 387 accepted mirrored edits, with and without the condition's macro (`compile_all.txt`), and on `ddd_globals.c` and every header of a 405 pair namespace matrix (`collide.txt`).
- 1,968 runs with every relaxable check at `ignore` or at `warning`, 1,210 of which loaded and went on through render and compare, looking for a traceback (`relax.txt`).
- A consumer built against the baseline and linked with the candidate (`abi.txt`, `cond_link.txt`).
- Older dictionary formats 8 to 1, emulated by stripping the keys each predates, and the field history of `ir.py` across all tags (`cmp3.txt`, `ir_history.txt`).
- `tests/test_compare.py`, `test_comparison_tables.py`, `test_analysis.py`: all pass.

**Not covered:**
- `src/ddd/gui/compare.py` beyond a grep, and the finding routes (GUI passes).
- A real calibration tool: M13 stops at the a2l text.
- `weigh_addresses` and the image reader (pass 8).
- Plans' left-open sections were grepped for this area, not read whole.

### Strengths

- **The registry and its documents agree.** 72 identifiers, 8 fixed, 9 project, 13 comparison: each one in SPEC, the reference tables and the README at its default severity, zero differences (`registry_crosscheck.py`). All 72 fire at the default the documents state. The `-W` grammar gives the documented usage errors, and `--strict` applies after the overrides.
- **Documented transcripts are true.** All 27 runnable transcripts of the two pages hold: 13 byte-identical by script, 7 partial ones whose `...` shows lines that are present, and 7 compared by eye, the 6 that need an edit plus one that differs only in the absolute path of the run's directory. `ddd compare` on `examples/pressure` included (`doc_transcripts.txt`, `doc_edits.txt`).
- **Agreement inside a project is tight.** Of all single edits to a reader's file, nine pass `check`, and those are the component's own name, an order, a dropped input, a reversed one-element list, and a condition (reported as `condition-mismatch`) (`accepted.txt`).
- **What `check` accepts compiles.** gcc under the CI flags accepts `ddd_globals.c` for 385 of the 387 accepted edits; the two left are pass 1 M8's section conflict and an external header that does not exist (`compile_all.txt`).
- **The name matrix matches SPEC.** Of 405 pairs, compile errors appear only at the two pairs SPEC marks *planned*, pass 5 M8, library names (pass 1 M3) and the template's own include guard (`collide.txt`).
- **The comparison's field coverage is good.** Of the edits that change generated code and report nothing, every one is pass 1 I3, I4 or C3, a description, an order, or a reader-only edit (`mutate2.txt`). Nothing outside those families. The only new holes found are in layout (C1) and init (I1).
- **Pairing holds:** rename, rename with interface change, swap, reuse with or without an id, half-migrated, referents across a rename. The dump and the description gave one comparison on every pair.
- **Old archives stay readable.** No key has left the dictionary since v0.5.0, dictionaries stripped to formats 8 to 1 compare clean (emulated, no real old dump was at hand), and `format` spelled `"9"`, `9.0`, `0`, `true` or `null` is refused (`ir_history.txt`, `cmp3.txt`).
- **The analysis does not crash.** No traceback in the 1,210 relaxed runs that loaded and went on through render and compare (`relax.txt`).
- **Pass 3 of the last review** is fixed, reproduced one by one (`misc2.txt`).

### Issues

#### Critical

- **C1. `compare` passes a moved layout with an `info`, or with nothing at all: an appended member, a grown nested structure or array, a renamed and swapped nested type; the fix pass 1 C3 proposes misses the first two outright.** `src/ddd/compare.py:682-692`, `:651-657`. Cited from pass 1 C3, whose triggers were an inserted member and an external member; these are others of the same root.

  *Trigger*, each `compare --strict`, exit 0, "can replace" (`abi.txt`, built and run):

  | candidate | findings | delivered consumer, built against the baseline |
  | --- | --- | --- |
  | `Rec[2]` of `{a, b}` gains `c` at the end | two `info[added-object]` | producer wrote 1234 to `Rec[1].a`, consumer reads 0 |
  | nested `In_t {v}` gains `w`, `Rec_t {inner, tail}` unchanged | one `info` | wrote `Rec.tail`, reads 0 |
  | nested `cell[2]` becomes `cell[3]` ahead of `tail` | one `info` | wrote `Rec.tail`, reads 0 |
  | nested `In_t {v, w}` becomes `In2_t {w, v}` | **none** | wrote `Rec.inner.v`, reads 0 |

  A consumer rebuilt against the candidate reads 1234 in all four.

  *Why:*
  - `_compare_layouts` lines up "the members both sides declare" of the types both sides name.
  - Its reasoning, that "a member that arrived or left is already an addition or a removal" (`compare.py:682-685`, `SPEC.md:1561-1562`), ignores that a size change moves what follows.
  - The fourth row shows a rename hides a reorder outright: the control without the rename is `changed-interface` (`misc4.txt`).

  *Contradicts:*
  - `docs/comparing_deliveries.rst:716-721`: "what a clean comparison guarantees is that everything built, calibrated and measured against the previous delivery still addresses the same objects, with the same layout".
  - `SPEC.md:1555-1559`, where widening a bitfield is an error because it "moves every member after it".
  - `docs/comparing_deliveries.rst:471-473`.
  - The tool itself: an array of structures growing is an error at the variable (`cmp2.txt`, `i_shape`), where these are not.

  *Scope:* the grade rests on open question 1, as pass 1 C3's does. If every consumer is always rebuilt, this drops to Minor.

  *Change (S-M):* derive one layout signature per instance from the dictionary's `types` (ordered members, nested types expanded, external members by name and shape, dimensions by value) and compare it, leaving only an append to a scalar top-level instance as `added-object`. Pass 1's "any difference ahead of a shared member" misses rows 1 and 2, nothing being ahead of a shared member there, and reaches rows 3 and 4 only if its "type and shape" is taken to cover nested members and not just external ones.

#### Important

- **I1. Two different tables compare as one init: `_uniform` is not injective, so a transposed square map is no finding even under `--strict`, and the index it reports can be wrong.** `src/ddd/compare.py:260-271`, `:197-220`, `SPEC.md:1600-1607`, `docs/comparing_deliveries.rst:273-279`.

  *Trigger* (`cmp1.txt`):
  - `Blk` `uint8[2][2]`, init `[[10,10],[20,20]]` to `[[10,20],[10,20]]`: no finding, `--strict` exit 0.
  - Likewise a 3x3 map, `[[1,1,1],[2,2,2],[3,3,3]]` to `[[1,2,3],[1,2,3],[1,2,3]]`.

  *Why:* the collapse works per level, so rows that are each uniform collapse to `(1,2,3)`, and identical rows collapse to `(1,2,3)` as well. This needs a square table, which is what a map usually is, and it is exactly the transposition a swapped pair of axes produces.

  *Second symptom:* where the collapse does not collide it still misaligns the report. `[[1,2,3],[1,2,3],[1,2,3]]` to `[[1,2,3],[1,2,3],[1,2,4]]` prints "first differs at [0][1]: 2 != 1", and both sides hold 2 there. The real difference is `[2][2]: 4 != 3`. SPEC promises "the first index at which they part".

  The docstring's "the long spelling of exactly that scalar" holds only when all leaves are equal. This came in with the fix of P3-I2.

  *Change (S):* collapse only when every leaf of the whole init is one value, else keep the nested tuple; walk the difference over the broadcast shape.

- **I2. An object wrapped in a condition is a warning although its readers stop linking; the message says so, and the docstring says so, and the verdict is "can replace".** `src/ddd/compare.py:1021-1027`, `:1087-1093`, `SPEC.md:1584`, `:1615-1617`, `docs/comparing_deliveries.rst:186`, `:298-300`.

  *Trigger* (`cond_link.txt`): `Speed`, read by `B`, gains `"condition": "defined(FEATURE_X)"` on both declarations.
  - `compare`: `warning[changed-condition] ... so it is now absent from every build where that condition is false`, exit 0, "can replace".
  - In a build without the macro, the delivered consumer: `undefined reference to 'Speed'`.
  - The rebuilt consumer: `error: 'Speed' undeclared`.

  *Contradicts:* warnings are for changes where "no consumer becomes wrong" (`SPEC.md:1584`). The same page calls the same outcome an error for a removal: "the software which was built against it no longer builds, and that is an error" (`:298-300`). `compare.py:1087-1090` writes "its consumers stop linking" and grades it a warning.

  *Change (S):* grade by direction and readers. Narrowing an object somebody reads (none to a condition, one condition to another) is an error, under a new identifier so that `changed-condition` keeps its meaning. A condition going away stays a warning. `tests/test_compare.py:358-361` pins the warning, on a `local` object.

- **I3. The supplier's gate grades removal backwards: an output gone is a warning with a false sentence, an input dropped is an error.** `src/ddd/compare.py:845-859`, `src/ddd/deliveries.py:191-192`, `src/ddd/cli.py:840`, `docs/command_line_interface.rst:591-592` ("lets a supplier verify a component long before an integrator ever sees it"), `SPEC.md:1513-1514`.

  *Trigger*, both from a description baseline and from a `dump --standalone` archive, component `Sensor` with output `Pressure` and input `Clock` (`misc1.txt`, `cmp3.txt`):
  - Delete the output, `ddd check s.ddd.json --standalone --baseline base`: `warning[removed-unused-object]: 'Pressure' is gone; no component read it`, exit 0.
  - Delete the input instead: `error[removed-object]: 'Clock' is gone, but was read by Sensor`, exit 1.

  *Why:* the consumers of a component read alone are, by construction, itself. "No component read it" is what the run was not shown, the very mistake `--standalone` exists to avoid (`diagnostics.py:55-62`). The same edit in the whole project is `removed-object` on the output (`misc1.txt`, a2), and an input a reader stops reading harms nobody. Neither `compare()` nor a dumped dictionary knows the run was partial.

  *Change (S; M with the mark in a dump):* tell `compare` the side is partial. Then grade by scope: an `output` gone is `removed-object` with a sentence that does not claim to know the readers, and an `input` gone is at most an `info`. A `dump --standalone` has to record that it is one, or a later comparison cannot know.

#### Minor

- **M1. The `kind` of a structured variable is reported per member, and not at all when it has no leaf.** `src/ddd/compare.py:357`, `:407-413`, `tests/test_comparison_tables.py:148`, `SPEC.md:1657-1666`. Measurement to parameter is one line of one declaration, and it gives one `changed-interface` per member, three for three members (`cmp1.txt`, S4). A structure of external members only gets no finding, `--strict` exit 0, while every reader's header goes from `extern Rec_t Rec` to `extern const Rec_t Rec` (`misc3.txt`). Adds to pass 5 I6, which covers the same blind spot for removal, rename and reuse. `_NOT_COMPARED_INSTANCE` records "compared on every leaf" as the decision and does not consider no leaves.

- **M2. Layout is compared by type name only: a nested type renamed or a nested array respelled is nothing, a type no variable uses is an error.** `src/ddd/compare.py:687-700`, `:407-408`, `SPEC.md:1563-1564`, `docs/comparing_deliveries.rst:250-254`.
  - `In_t` to `In2_t` with the members untouched: no finding, where the same rename at the top is `changed-interface` (`cmp1.txt`, S3).
  - A member `cell[N]` to `cell[M]`, values equal: no finding, where a value member respelled the same way is `changed-interface` (`misc4.txt`).
  - A structure nothing instantiates, reordered: error "every variable of it holds its members somewhere else"; the same structure removed: nothing (`misc1.txt`, b).
  - The signature C1 proposes settles all three.

- **M3. `point-counts-mismatch` is one more check that needs the whole project, and `--standalone` reports it falsely.** `src/ddd/diagnostics.py:208-209`, `:55-62`, `src/ddd/analysis.py:403-406`, `:3589-3600`, `SPEC.md:1238-1240` ("Exactly these"). `A` and `B` both state `point_counts: leading`, `B` has a curve over `A`'s axis. The whole project is clean; `ddd check b.ddd.json --standalone` gives `warning[point-counts-mismatch]: 'Cv' stores its point counts 'leading', but its axis 'Ax' stores them 'none'`, exit 1 under `--strict` (`chk1.txt`). The axis has no producer here, so it resolves to the default. Skip the comparison when the axis has no producer (S).

- **M4. `--standalone` on a project root loses the trace of a real drop.** `src/ddd/diagnostics.py:449-457`, `src/ddd/analysis.py:2040-2055`, `SPEC.md:2155-2156`, `src/ddd/lsp/diagnostics.py:139-152`. SPEC calls holding the checks back "rarely wanted". It does not say a variable of a type no file declares then vanishes: `check p.ddd.json --standalone` gives `ok: 1 variable in 1 component are consistent`, exit 0, one object gone with no `incomplete-project`, because the run counts as "handed one component" (`misc2.txt`). The language server refuses that reading for a project file. `standalone` should be false for a project root, keeping the floor (S).

- **M5. Relaxing a duplicate drops a file's content with no trace, and the include order then picks the layout.** `src/ddd/loading.py:778-786`, `:874-882`, `SPEC.md:1475-1482`, `docs/consistency_checks.rst:700-701`, `:359-361`.
  - `-W duplicate-component=ignore`: `Y` and `Z` of the second file gone, exit 0, no `incomplete-project`, against "a dictionary short of a variable is never a surprise".
  - `-W duplicate-type=warning` with `uint8` and `uint32` copies: `X` is `uint8` or `uint32` by the order of two includes (`silence.txt`), which is what `docs/consistency_checks.rst:359-361` says must not decide. The previous review fixed the same fault for producers (P3-M5).
  - Either report the dropped declarations and pick a stable winner, or see open question 3.

- **M6. A plugin's fixed check is not fixed by a usage error, and a malformed severity is a traceback.** `src/ddd/diagnostics.py:471-476`, `:503-512`, `src/ddd/plugins.py:119-132`, `SPEC.md:1235-1236`, `docs/consistency_checks.rst:264-266`.
  - `CheckInfo(..., overridable=False)` with `-W pl/fixed=ignore`: accepted, silently ignored, the finding stands (`silence.txt`), against "a usage error rather than a silently ignored request".
  - `CheckInfo("pl/x", "warning", ...)`: `AttributeError: 'str' object has no attribute 'rank'`, traceback, exit 1, the findings' own code, on `check` and on `checks --plugin` (`misc2.txt`). `Plugin.__post_init__` validates the identifier only. SPEC's "Malformed means" should include it (S).

- **M7. `{"name": "P"}` is a delivery.** `src/ddd/ir.py:672`, `src/ddd/loading.py:596`, `src/ddd/deliveries.py:76-78`, `:220-231`. `format` has a default, so a file with neither `format` nor `objects` validates as an empty dictionary: as a baseline every object is an `added-object`, "can replace"; as a candidate it is `removed-unused-object`, "almost.json can replace p.ddd.json", exit 0 (`cmp1.txt`, S9). `holds_a_dictionary` calls `format` "the one key every dump stamps". Require it (S; every tag since v0.5.0 stamps it).

- **M8. The tolerance on `narrowed-limits` hides narrowing anybody stated on purpose.** `src/ddd/models/conversion.py:370-374`, `src/ddd/compare.py:978`, `SPEC.md:1608-1613`. `uint32` limit 4294967295 to 4294967291, `float64` 1000000 to 999999.9995, `uint64` tighter by 13.7e9: all silent (`cmp1.txt`, S8), against "narrow enough that a limit anybody stated on purpose is still a different number". Rounding at 12 significant digits needs about 1e-11, not 1e-9.

- **M9. "Compared as the bytes" and "rounds to zero" each miss one spelling.** `src/ddd/compare.py:267-271`, `SPEC.md:1600-1604`, `:457-461`, `src/ddd/loading.py:120-124`. `init` 0.0 to -0.0 on a `float32` moves a byte and is no finding (`cmp1.txt`, S2). `init` `1e-400` reads as 0 before anything looks at it, so `check` is clean and `list` shows 0 (`misc1.txt`, d).

- **M10. `reserved-identifier` states C11 7.1.3 wrongly, both ways.** `src/ddd/models/reserved.py:73-77`, `SPEC.md:1395-1400`, `docs/consistency_checks.rst:486-488`, `README.md:561`.
  - C11 reserves identifiers that *begin* with a double underscore. A double underscore anywhere is C++'s rule. `Speed__raw` is refused "reserved by the c language", and compiles clean under the CI flags when relaxed (`misc3.txt`).
  - The family C11 does reserve at file scope, a leading underscore and a lower case letter, passes: `_speed` is `ok`, and every object, enum and typedef DDD generates is at file scope.
  - Reword, or follow the standard (S).

- **M11. SPEC's `local-conflict` sentence is wider than the code.** `SPEC.md:1282-1286`, `docs/consistency_checks.rst:550-553`, `src/ddd/analysis.py:2937-2946`. "Referred to ... by a curve, map or axis another component declares": `B` reading `A`'s curve over `A`'s local axis declares that curve and has to name the axis or get `definition-mismatch`, and nothing fires (`fire2.txt`). The code's answer is the workable one, since otherwise such a curve could have no reader. Say "by a curve, map or axis another component produces" (S).

- **M12. A project that relaxes an error cannot use the documented branch-against-trunk comparison.** `src/ddd/deliveries.py:191-192`, `docs/comparing_deliveries.rst:141-143`, `:681-683`, `docs/consistency_checks.rst:160-163`. A project building with `-W missing-producer=ignore`: `check` clean, and `ddd compare base/p.ddd.json cand/p.ddd.json` under the same `-W` gives `error[missing-producer]: in the baseline: ...`, no verdict, exit 1. Through a dump it works (`doc_edits.txt`). 4.1 states this rule, while the page offers comparing two working trees without the condition, and "the policy belongs to the project". See open question 4.

- **M13. An axis may be indexed by an array or by text.** `src/ddd/analysis.py:3026-3045`, `SPEC.md:484-486`. `input` naming a `uint16[4]` or a string measurement passes `--strict`, and the a2l writes `COM_AXIS Sp` over a record with `MATRIX_DIM 4` (`chk1.txt`, k22, k23; `cases/k22/gen/P.a2l`, `cases/k23/gen/P.a2l`). ASAP2 1.6.1 only says the reference is to a measurement. What a tool does with it was not established. Refuse with `reference-kind` as for a structure, or say SPEC allows it.

- **M14. A condition a preprocessor refuses passes `--strict`.** `src/ddd/models/component.py:60-88`, `SPEC.md:325-332`. `defined(`, `A &&`, `(A`, `1 +`, `defined(A) defined(B)` all pass (`misc3.txt`). For the first, gcc then stops in `ddd_globals.h`, "operator 'defined' requires an identifier" (`chk1.txt`, k32), the message about a generated file the checks exist to prevent. A balanced-parentheses and trailing-operator test would catch most.

- **M15. Small untrue sentences.**
  - `name-collision` on an object and a scalar type says "the types header makes that a typedef name" (`src/ddd/analysis.py:1827-1829`); the shipped header emits none, and relaxed it compiles (`misc1.txt`, c).
  - The registry's `changed-interface` omits bit width, member order and type (`src/ddd/diagnostics.py:232-235`), though SPEC calls `ddd checks` authoritative.
  - The registry and `README.md:629` say of `missing-plugin` "this run has not loaded", against `SPEC.md:1624-1633`, where it also fires for a plugin the run did load for the baseline (`doc_edits.txt`).
  - The example object at `docs/comparing_deliveries.rst:52-87` lacks `point_counts`, which every dump has (`misc3.txt`).

### Status of the 2026-09-15 findings in this area

All of pass 3 (I1-I3, M1-M9 and its four questions) is fixed or settled, reproduced in `misc2.txt`, `cmp3.txt` and `doc_edits.txt`, the doc sentences of P3-M8 read off the page. Only these are not plain:

| id | finding | status |
| --- | --- | --- |
| P3-I2 | `init` compared as spelled | FIXED at `compare.py:223-257`, and the fix brought I1 |
| P3-M8 (c) | an in-file `duplicate-type` is located at the whole file | the page now says so (`docs/consistency_checks.rst:361-365`); the message is still `Value error, type 'T_t' is already declared in this file (got: {'types': ...`, see pass 6 M2 |

### Open questions

1. **Pass 1's question 1, with more riding on it: which consumer does `compare` protect, one rebuilt or one not?** *Not rebuilt:* C1 stands as Critical, I2's first symptom stands, `volatile` from false to true is an error, and `renamed-object` on an object somebody reads should be an error too, since `mutate2.txt` shows it warns while a delivered reader stops linking. *Rebuilt:* C1 and pass 1 C3 drop to Minor and the sentence at `docs/comparing_deliveries.rst:716-721` has to go. I2 stands either way, because a rebuilt reader does not compile. I would answer "not rebuilt".
2. **What does a run know about readers when it was handed a component?** Answering "nothing" changes `compare`'s signature, and I3 needs a mark in a `dump --standalone` (a format change). Answering "`--standalone` and `--baseline` do not go together" removes a documented flow.
3. **Should relaxing a duplicate exist at all?** Making `duplicate-component`, `duplicate-type` and `duplicate-constant` fixed turns eight fixed checks into eleven, ends M5 and costs the second-wave trick at `docs/consistency_checks.rst:286-288`. Keeping them relaxable needs a trace and a stable winner.
4. **Does a description baseline take the project's `-W`?** 4.1 says no, deliberately. *Yes* would bring back the case the previous review refused (P3 question 2), so a middle answer is relaxation only, never promotion. That ends M12 and changes 4.1.

### Test gaps

- `tests/test_compare.py:918-956`: no init of a square table with uniform rows or identical rows, no index test on them, and no test names `_uniform` (I1). A property test over random tables, that distinct tables stay distinct, would have found it.
- `tests/test_compare.py:358-361` pins `changed-condition` between two conditions on a local; nothing covers a condition appearing on an object somebody reads (I2).
- `tests/test_cli.py:2105-2122` is the only standalone baseline test, and it pins the floor; nothing grades a removal there (I3).
- No test grows a structure at its end, in an array or nested, or renames a nested type (C1, M2). `test_two_members_swapped_are_reported_once_at_the_structure` (`:638`) keeps the name.
- `tests/test_point_counts.py` never runs `--standalone` (M3).
- `tests/test_plugins.py` has no fixed plugin check and no non-`Severity` default (M6).
- `tests/test_comparison_tables.py` is a sound guard that a field was decided about. It does not ask whether the decision holds for an object with no leaves (M1).
- No test hands a file with `name` alone as either side (M7).
- `tests/test_file_plans.py:741-755` covers `duplicate-component` relaxed for the Files tab; nothing asks for a trace (M5).

### Assessment

The checks are the strongest part of the tool: the registry, the documents and the behaviour agree on all 72 identifiers, a reader cannot disagree with a producer on anything that matters, and what `check` accepts nearly always compiles (385 of 387 mutated projects). Of the false negatives I hunted in `check`, none reaches a shipped wrong value at the default severities. What remains there is guards around relaxation and small sentences. The comparison's pairing and field coverage are good too, and most of what it misses is the known I3 and I4 of pass 1. Its real weakness is the structure: it reasons about leaves, so a layout that moved while its leaves stayed passes as an `info` or as nothing, and the sentence promising "the same layout" is false for any consumer that is not rebuilt. Beside that, one fix introduced a real blind spot (a transposed square table compares equal), and two grades contradict the stated rule, condition wrapping and the standalone gate, the second of them backwards. None of these needs a redesign; each is a small change once open question 1 is answered, and that question is now the one thing that most changes this area's verdict.

```candidates
7|C1|src/ddd/compare.py:682|compare passes a moved layout as info or nothing: appended member, grown nested structure or array, renamed and swapped nested type; pass 1 C3's fix misses the first two outright
7|I1|src/ddd/compare.py:260|_uniform is not injective: a transposed square map is no finding under --strict, and first differs names the wrong index
7|I2|src/ddd/compare.py:1021|An object wrapped in a condition is a warning and can replace, while its readers stop linking and compiling
7|I3|src/ddd/compare.py:845|The supplier's gate grades removal backwards: output gone warns no component read it, input dropped is an error
7|M1|src/ddd/compare.py:407|The kind of a structured variable is one finding per member, and none at all when it has no leaf (adds to pass 5 I6)
7|M2|src/ddd/compare.py:687|Layout compared by type name: nested type renamed or nested array respelled is nothing, an unused type reordered is an error
7|M3|src/ddd/diagnostics.py:208|point-counts-mismatch needs the whole project and fires falsely under --standalone
7|M4|src/ddd/analysis.py:2040|--standalone on a project root loses incomplete-project for a real drop
7|M5|src/ddd/loading.py:778|Relaxing a duplicate drops a file's content with no trace, and the include order picks the layout
7|M6|src/ddd/diagnostics.py:503|A plugin's fixed check accepts -W silently, and a non-Severity default is a traceback with exit 1
7|M7|src/ddd/ir.py:672|A json of name alone is a delivery: format defaults, so it compares as an empty dictionary and can replace
7|M8|src/ddd/models/conversion.py:370|The narrowed-limits tolerance hides narrowing stated on purpose: 4 counts of a uint32, 999999.9995 from 1000000
7|M9|src/ddd/compare.py:267|Bytes and rounds to zero miss a spelling each: -0.0 is no change, 1e-400 reads as 0 and passes
7|M10|src/ddd/models/reserved.py:73|reserved-identifier states C11 7.1.3 wrongly: refuses Speed__raw, passes _speed at file scope
7|M11|SPEC.md:1282|SPEC's local-conflict sentence is wider than the code: a reader of a curve over a local axis does not fire
7|M12|src/ddd/deliveries.py:191|A project relaxing an error cannot compare two working trees: baseline's error, no verdict, against the documented flow
7|M13|src/ddd/analysis.py:3026|An axis may be indexed by an array or a string measurement, under --strict
7|M14|src/ddd/models/component.py:60|A condition a preprocessor refuses passes --strict, then gcc stops in a generated file
7|M15|src/ddd/analysis.py:1827|Small untrue sentences: typedef of a scalar, the registry on changed-interface and missing-plugin, the dump example lacks point_counts
```

## Pass 8: generated artefacts and addresses (SPEC 5, 6)

### Scope covered

**Read in full, with line numbers:** `SPEC.md:336-643` (the definition and its keys, as the artefacts depend on them), `:704-811`, `:1681-2061`; `src/ddd/ir.py` (817), `src/ddd/addresses.py` (259), `src/ddd/build_info.py` (88); `src/ddd/backends/base.py` (549), `backends/a2l/{backend,model,options,types}.py`, `a2l/templates/project.a2l.jinja` (162), `backends/c/{backend,literals,model,options,types}.py`; the five `examples/templates/*.jinja2`; `docs/generated_artefacts.rst` (1374), `docs/data_dictionary.rst` (446), `docs/templates.rst` (507); `src/ddd/models/common.py:150-419`, `objects.py:130-170, 480-993`, `conversion.py:30-444`, `types.py` whole; `src/ddd/cli.py:950-1296, 1632-1656`; `src/ddd/analysis.py:905-936, 1790-1940, 2381-2404, 3020-3050, 3225-3410, 3564-3600`. ASAP2 1.6.1 (`SCRATCH/pass-1/pdf/asap2-1.6.1.txt`): Table 5, 3.5.5-3.5.10 (alignment), 3.5.17 AXIS_DESCR, 3.5.18 AXIS_PTS, 3.5.20 AXIS_PTS_X, 3.5.29 CHARACTERISTIC, 3.5.30 COEFFS, 3.5.33 COMPU_METHOD, 3.5.36 COMPU_VTAB, 3.5.47 DEPOSIT, 3.5.61, 3.5.62 FNC_VALUES, 3.5.77 LAYOUT, 3.5.81 MATRIX_DIM, 3.5.84 MEASUREMENT, 3.5.87 MOD_COMMON, 3.5.91 NO_AXIS_PTS, 3.5.103 RECORD_LAYOUT, 3.5.123 SYMBOL_LINK. 1.51: 6.3.83. `SCRATCH/review-2026-09-15.md:1414-1782` and its later mentions of the backends; `plans/2026-09-16-review-fixes.md:426-500`; `plans/2026-10-02-addresses-from-image.md:5602-5634`; `specs/2026-09-23-record-layouts-design.md`.

**Ran** (all under `SCRATCH/pass-8/`; every path below is relative to it):

- `gen_matrix.py`: one project of 1,679 variables, 1,664 A2L records: all 11 datatypes under 6 conversions (identity, identity with unit, whole linear, fractional linear with offset, negative factor, enum), every kind and shape (scalar, 1-D, 2-D, 3-D, broadcast, no init), both `point_counts`, strings on both datatypes in measurement, value block and member, nested structures, arrays and grids of structures, bitfields, external members, scalar types, constants as dimensions, sections, rasters, conditions, `export: false`, the closure. Generated, compiled under the CI flag set on MinGW gcc 15.2 (`-std=c99, gnu99, c11, gnu11, c17, c23, gnu23`, and with `-Wsign-conversion -Wfloat-conversion -Wdouble-promotion -Wundef -Wredundant-decls -Wmissing-variable-declarations`) and on gcc 13.3 (`c99, c11, c17, c2x`, `wsl_ci.sh`), every header alone and twice, as `docker/compile.sh` does (`cc_ci.sh`), with and without `-DFEATURE_X` and with `--const-inputs`.
- An independent reader and oracle, written from the standard's prototypes and importing nothing of ddd (`a2lread.py`, `oracle.py`, `verify2.py`, `dictcheck.py`, `elfread.py`): every record's fixed fields, optional keywords, references and block balance; for an image, `&path` and `sizeof path` from a program that links the generated C, and the record's bytes decoded the way a tool would (RECORD_LAYOUT positions, counts, MATRIX_DIM, datatype, byte order) against the description's `init`; COMPU_METHOD against the factor and offset; limits against exact-fraction arithmetic; formats, events, groups, sort orders; every C type by redeclaration (`types_oracle.c`); the dictionary against the description files.
- 26 image variants (`variants.txt`): `-O0 -Og -O2 -Os -O3`, DWARF 2, 3, 4, 5, strict, `-g1 -g3`, `-gz`, `-fpack-struct`, `-fshort-enums`, `-fdata-sections --gc-sections`, static, PIE, `-fcommon`, `-gsplit-dwarf`, `-fdebug-types-section`, `-flto`, no `-g`, stripped of everything, stripped of debug information, relocatable. An ELF32 i386 link with a link-time address table (`i386.txt`). The five committed cross images, big-endian included, decoded from the ELF file (`elfread.py`).
- `fuzz.py`: 485 random projects: check, generate, compile under the CI flags, parse, map back from the run, decode, hold the dictionary to the descriptions (`fuzz1.txt` to `fuzz4.txt`).
- 80-odd small cases (`cases/`, transcripts `e1.txt` to `e16.txt`, `addr_map.txt`), the manifest scenarios (`mf/`), every documented excerpt of `docs/generated_artefacts.rst` against real output (`doc/doc_blocks.py`, `doc/doc_blocks.txt`), 39 mutations of the generating code against the suites that cover it (`mutate.py`, `mutate.txt`, on a copy).

**Not covered:** no calibration tool exists here, so nothing was loaded in CANape or INCA (see I3 and the open questions). No clang and no big-endian compiler: the matrix was built for x86-64 and i386 only; big-endian rests on the committed fixtures. `src/ddd/elf.py` was exercised, not read (pass 11). The CMake flows are pass 9.

**Met again and cited, not re-filed, with what this pass adds:**

- pass 1 C1 (`--const-inputs`): the matrix with `--const-inputs` compiles clean under the CI flags, which is exactly why nothing catches it.
- pass 1 I5 (compiled-out object at address 0): reason text verified; see M6 for the references to one.
- pass 1 I8, I9, I10, M6, M12; pass 6 I2: the records are otherwise valid; nothing more to add, except that the limits of Table 5 reach numbers as well as strings (M2).
- pass 1 I11: `Discarded` under `--gc-sections` is reported, "the linker discarded its storage" (`addr_map.txt`).
- pass 1 I12 (KNOWN): `uint32_t WrongType[9]` for a `uint16[2]` is placed with no finding (`addr_map.txt`).
- pass 1 M2: `analysis.py:915-936` `_a2l_closure` is the second answer to which objects reach the file that `backends/a2l/model.py:221-224` says should not exist. The two agree where I compared them (`e15.txt`).
- pass 1 M8: a measurement and a parameter in one section is the one class of compile failure the random projects found: 29 of the first 175, all `section type conflict` (`fuzz1.txt`).
- pass 5 I2: the flat counted declaration remains stated nowhere in the SPEC; the output itself is right.
- pass 5 M8 and `SPEC.md:1412-1414` *(planned)*: an enum named as a structure or an external type, and an enumerator named as a structure: clean check, gcc `conflicting types` in `ddd_types.h` (`e7.txt`).
- pass 5 M11, M13, M19; pass 6 I1, M6; pass 7 M13, M14: as filed. M13 below extends pass 6 M6.

### Strengths

- **Every value in the A2L and the C agrees with what the compiler and the linker did.** Over the matrix: 1,664 of 1,664 addresses, sizes and decoded values, 342 of 342 stored counts, zero parser problems, C types all agree with the dictionary (`gen*/`, `verify2.txt`). The result is unchanged across `-O0` to `-O3`, DWARF 2 to 5, `-gz`, `-fpack-struct`, `-fdata-sections`, static and `-fcommon` (`variants.txt`); on i386, where `uint64` members sit on 4 byte borders, 1,664 of 1,664 addresses; on the five committed images, armv7m, powerpc, x86_64, aarch64_be and i686, all 46 records decode correctly under the byte order the a2l states.
- **The random differential found nothing in the generator.** 456 of 485 random projects, with hostile units and descriptions, nested structures, constants as dimensions, counted tables, conditions, sections, rasters and consumers, generated, compiled under the CI flags, parsed, and read back 13,956 of 13,956 records through the a2l's layouts as the values the descriptions state, with the dictionary agreeing with the descriptions throughout. The other 29 were all pass 1 M8's `section type conflict`; with measurements and parameters kept in separate sections, 310 of 310 pass.
- **The guards hold.** Strings on any kind other than the two allowed, `boolean` counts, a count one past the type, a fractional `init`, a section name that would break the string literal, a dimension constant that is fractional, zero or negative, an axis `input` on a structure, an address past 32 bits, all refused with a located finding or a usage error that writes nothing (`e2.txt`, `e5.txt`, `e6.txt`, `e8.txt`, `e9.txt`, `addr_map.txt`).
- **Section 6 does what it says, reason by reason.** Each sentence of `SPEC.md:2017-2027` was provoked and answers as written: no variable, a `static`, thread-local, discarded by the linker, no such member, not a structure, not an array, out of range, a bitfield (`addr_map.txt`). LTO, type units, no DWARF, a stripped image, a relocatable object and a PE image are each refused in a sentence of their own, nearly all naming the fix (`variants.txt`, `addr_map.txt`). `--image` and a complete `--address-map` give the same a2l, and the post-link run changes only the 1,664 address fields.
- **The documents are accurate.** All the records `docs/generated_artefacts.rst` quotes from the demo and the vocabulary example are verbatim in the output; the illustrated ones (`Fuel`, `Cube`, the address map) reproduce when their projects are written (`doc/`, `e10.txt`, `docchk/`). `22 of 23` and `23 of 23` hold. "Five record layouts, eight compu methods" holds. The manifest scenarios of SPEC 5 hold: dropped component, `generate a2l` leaving the C, `--dry-run`, unknown format, unchanged reruns keeping mtimes (`mf/`).
- **The dictionary is a real contract.** Every dump validates against `ddd schema dictionary`, round-trips byte for byte, and the backends fed the reloaded document write the same bytes as the original run (`dict1.py`, `dict1.txt`). Held to the description files, owner, consumers, declarations, shape, spelling, references, raster, `point_counts` and `export` all agree (`dictcheck.py`). `dump -o`, `--dictionary` and stdout are the same bytes. Output is identical under three hash seeds.
- **Free text cannot break the outputs,** with the one exotic exception of M13: quotes, backslashes, comment markers in both orders, line breaks, NUL, `%`, `{{`, non-ASCII all reach comments and A2L strings safely across the random projects.

### Issues

#### Critical

None found. I looked hardest here: a wrong address, value, count, shape, conversion or qualifier in a clean run. None exists in anything I could build.

#### Important

- **I1. An axis and the measurement indexing it may mean different things, under `--strict`, and the a2l then contradicts itself.** `src/ddd/analysis.py:3020-3050` (kind and structure only), `SPEC.md:484-486`, `docs/generated_artefacts.rst:1070-1073`. *Trigger* (`cases/axisinput`, `e4.txt`): a measurement `Speed`, `uint8`, factor 100, unit `rpm`; an axis `SpeedAxis`, `float32`, identity, unit `Hz`, `"input": "Speed"`; a curve over it. `ddd check --strict` exit 0, generate exit 0. The file states `COM_AXIS Speed CM_IDENT_HZ` beside `MEASUREMENT Speed ... CM_LIN_RPM`. *Contradicts:* ASAP2 1.6.1 3.5.17: "It is expected that both conversions are equivalent, i.e. they must lead to the same result." *Consequence:* the tool places the operating point from a value in rpm on an axis in Hz, the engineer calibrates the wrong cell, and a routine interpolating over the two compares different scales. DDD compares units between declarations of one object to the letter and not between the two objects whose units must match by definition. Pass 7 M13 is the shape half of this (an array or a string as input); this is the meaning half. *Change (S):* a warning, `input-mismatch`, when the units differ, and a note when the conversions do: a different datatype on one unit is legitimate, and a project can relax it.

- **I2. A component named after a header takes that header's place on every include path, and `ddd check` says nothing.** `src/ddd/analysis.py:1792-1812` (case only), `cmake/Ddd.cmake:689`, `SPEC.md:1721-1723`, `docs/generated_artefacts.rst:327-330`. A component's header is `<name>.h` in a directory every component compiles with as `-I`, which precedes the system directories. *Triggers* (`cases/h_*`, `e7.txt`), `ddd check` clean each time:
  - component `stdint`, `stdbool` or `stddef`: `gen/stdint.h:21:8: error: unknown type name 'bool'`, the types header including the component's header in place of the C library's;
  - component `driver` with an external type whose header is `driver.h`: `#include "driver.h"` in `ddd_types.h` finds the generated header beside it before anything on the include path, `unknown type name 'Dr_t'`;
  - components `Signal` and `Math`, ordinary names, on this disk: the generated code compiles, and a hand-written `#include <signal.h>`, `#include <math.h>` under `-Igen` gets the components' headers: `unknown type name 'sig_atomic_t'`, `implicit declaration of function 'floor'`. MinGW resolves the name without regard to case, as macOS does by default. The same `hand.c` compiles on ext4 under gcc 13.3 and fails under that gcc on this disk, so the project builds in a Linux CI and not on the developer's machine. `Time`, `String`, `Limits`, `Assert` and `Errno` are the same mechanism, and so is a component named after any vendor header, AUTOSAR's `Com` for one.
  *Change:* (S) `name-collision` against the C library's header names without regard to case, and against the external headers in use; or (M) generate per-component headers into a subdirectory, `#include "ddd/Signal.h"`, which ends the class.

- **I3. "ASAP2 lists the fastest running index first" is stated as the standard's rule; the standard does not state it, its one general formula reads the other way, and no tool has been asked.** `src/ddd/backends/a2l/model.py:523-538`, `SPEC.md:449-452`, `docs/generated_artefacts.rst:1009-1034`, `docs/faq.rst:608-609`, `docs/acronyms.rst:230`. Established by reading, not reproduced: there is no tool here. Extends pass 1 Strengths and its question 7, which read the agreeing half.
  *For DDD's reading:* 3.5.62 says rows and columns "relate to the XY coordinate system" and that a cuboid is an array of XY planes with Z slowest, so x is fastest in a table with axes.
  *Against:* 3.5.81 says only `xDim yDim zDim`, and ties them to no storage order. The one statement of the order for a matrix, 3.5.62, is "A 2 x 3 matrix ... would be stored as follows: a11, a12, a13, a21, a22, a23. More generally, a matrix a i x j x k would be listed as a111, ... a11k, a121, ... a1jk, a211, ... aijk", which 3.5.77 makes the definition of `ROW_DIR` for a measurement: the *last* stated dimension runs fastest. A reader taking `MATRIX_DIM i j k` as that matrix takes `uint8_t T[2][3]`, the standard's own example, as `MATRIX_DIM 2 3 1`. DDD writes `3 2 1`, which that reader takes as three rows of two.
  *Consequence if the other reading is what tools implement:* every multi-dimensional measurement and value block is transposed, and the page describes the symptom itself: "the file parses, the tool connects, the display fills with plausible numbers". Maps and curves are unaffected, their shape coming from `AXIS_DESCR`. From memory Vector's XCPlite passes the inner extent as `xDim`, which would support DDD; I could not check that here, and it is not in the repository.
  *Change (S):* load one `T[2][3]` with distinct values in CANape, record the result where `docs/developer_documentation.rst:264-283` records the structure measurements, and have the pages say "as CANape reads it" or correct the table. Until then the sentence should not be stated as the standard's. See the open questions.

#### Minor

- **M1. Rounding derived limits fixed short decimals and moved the original defect to everything longer than twelve digits.** `src/ddd/models/conversion.py:353-367, 415-416`, `SPEC.md:544-547` ("the number its own largest raw count reads as"). *Evidence* (`e1.txt`, `e14.txt`, `verify2.txt`, exact-fraction arithmetic): `uint64` under `{"factor": 1}` states `1.84467440737e+19`, about 9.6e6 below the raw maximum; `sint64` under the same `-9.22337203685e+18 .. 9.22337203685e+18`; `uint32` under 2^-10 states `4194303.99902`, below its top count's `4194303.9990234375`; `sint32` under 2^-16, Q16.16 and as ordinary as fixed point gets, states `32767.9999847`, below `32767.99998474121` (`e14.txt`). In each at least the top raw count reads as out of limits. A `float64` under the identity states `1.79769313486e+308`, below `DBL_MAX`, against `SPEC.md:409-410` "the raw ends themselves" (pass 5 M19 has the `float32` half). 231 records of the matrix are in this state. This is P4-I3's symptom: a tool that enforces limits refuses the description's own largest value. *Change (S):* round outward, or keep the exact end where the factor is a dyadic rational; spell a whole product exactly.

- **M2. Sizes past what `uint` holds reach `MATRIX_DIM`, `NUMBER` and `MaxAxisPoints`, under `--strict`.** `src/ddd/backends/a2l/model.py:394, 441, 464, 482, 523-538`, `SPEC.md:1444-1449`, `:442-443`. ASAP2 1.6.1 Table 5: `uint` is a 2 byte unsigned integer; 3.5.81, 3.5.18 and 3.5.17 type these fields `uint`. *Trigger* (`e11.txt`): `uint8 Trace[70000]`, an axis of 70000: `ddd generate --strict` exit 0, `MATRIX_DIM 70000 1 1`, `AXIS_PTS ... 70000`. The tool allows 10,000,000 elements and exports by default, and it caps the raster's `event` at 65535 for this very field type (`models/rasters.py:84`). What a tool does with 70000 I could not test; truncated to 16 bits it reads 4464 elements. Adds the numbers to pass 6 I2's strings. *Change (S):* `a2l-unrepresentable`, carrying the number whole.

- **M3. One file, two orders: the records list `SA[2]` before `SA[10]`, the `GROUP` lists `SA[10]` before `SA[2]`, and SPEC 5.1 states the second as the rule.** `src/ddd/backends/a2l/model.py:502-509`, `src/ddd/ir.py:729-739`, `src/ddd/analysis.py:903`, `SPEC.md:1803-1805`, `:1859`, `:1864`. *Trigger* (`e1.txt`): an array of 12 structures: `MEASUREMENT` order `SA[0] SA[1] ... SA[11]`, `REF_MEASUREMENT` order `SA[0] SA[10] SA[11] SA[1] ...`. The comment at `model.py:502-504` says the sort restores "the order the dictionary carries them in", which it does not: it sorts by plain text where the dictionary sorts by `index_order`. `SPEC.md:1804` "`cell[10]` before `cell[2]`" is false of the records, the dictionary and `ddd list`. Deterministic, so cosmetic in a tool; the docstring is wrong and the SPEC is stale. *Change (S):* `key=lambda leaf: index_order(leaf.path)`, and correct the sentence.

- **M4. `MOD_COMMON` states fixed alignments the image can contradict, and `--image` takes the byte order from the image but not this.** `src/ddd/backends/a2l/templates/project.a2l.jinja:15-20`, `SPEC.md:1878-1879`, `docs/generated_artefacts.rst:705-707`. ASAP2 3.5.8: "its memory address must be dividable by the value AlignmentBorder", for complex objects. *Evidence* (`i386.py`, `i386.txt`): on i386, `SP.a_uint64` (a `VAL_BLK`) at `0x080513BC`, `SM.inner.m_uint64` at `0x08055714`, 8 such records, in a file stating `ALIGNMENT_INT64 8` and `ALIGNMENT_FLOAT64_IEEE 8`. Harmless for a one-type layout if a tool pads only between elements, wrong if it rounds up the start; untested in a tool. The same for a project's own template packing a structure. A project cannot amend it (pass 1 I8). *Change (S):* derive the borders from the image's DWARF where it has one, or state the assumption and how to change it.

- **M5. `--image` on an `ET_DYN` image writes load-relative offsets as absolute `ECU_ADDRESS`es, with no finding and no sentence saying so.** `SPEC.md:2005`, `src/ddd/elf.py:442`, `docs/generated_artefacts.rst:1220-1226`. *Trigger* (`variants.txt`, `pie`): gcc's default on Ubuntu: 1,664 of 1,664 records differ from `&obj` at run time, `0x000219B0` against `0x626f928e89b0`. Right for a project that adds the base itself, and invisible to one that does not, for instance a hosted test build of the same components. *Change (S):* one sentence in section 6, and a note on the run.

- **M6. An unconditional object may refer to a conditional axis, or an axis to a conditional input, under `--strict`.** Adds to pass 1 I5. `SPEC.md:1923-1924`, no check. *Trigger* (`cases/condref`, `e4.txt`): `Cu` over `Ax` where only `Ax` carries `defined(F)`: `ddd check --strict` exit 0. In a build without `F` the curve is in the image and its `AXIS_PTS_REF` names a record at address 0, the tool reading axis points from there. *Change (S):* `condition-mismatch` across a reference.

- **M7. A map the reader cannot decode is reported without naming it, and a deep one as a traceback with the findings exit code.** `src/ddd/addresses.py:62-75`, against its docstring ("Every complaint spells the path") and `SPEC.md:2045-2047` ("written by a build step, and on Windows that is exactly where one comes from"). *Trigger* (`addr_map.txt`): a map in UTF-16, which is what Windows PowerShell's `>` writes: `ddd: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`, exit 2, no file named; `[[[...` 200,000 deep: `RecursionError` traceback, exit 1; a 5,000 digit address: python's advice about `sys.set_int_max_str_digits()`. *Change (S):* catch `UnicodeDecodeError`, `RecursionError` and the digit limit with the sentence the others have.

- **M8. A `float64` under any factor above 1 is refused even with stated limits, for a reason that is not so.** `src/ddd/analysis.py:2381-2404`, `SPEC.md:411-414` ("no finite stated limits could repair a conversion that overflows by itself"). *Trigger* (`cases/f64factor`, `e14.txt`): `float64`, `{"factor": 1.8, "offset": 32}`, `"limits": {"min": -100, "max": 500}`: `error[schema]: the limits derived from 'float64' and this conversion are not finite`. Stated limits are what `physical_limits` returns first (`models/objects.py:707-708`), so nothing infinite reaches any output: they do repair it. A `float64` in degF cannot be stated at all. *Change (S):* run the check only when no declaration states limits.

- **M9. `.const` says a `const` was added when none was, so a template that builds the line as the page offers writes `const const`.** `docs/templates.rst:371-374`, `src/ddd/backends/c/model.py:114, 624`. *Trigger* (`tc/`): `--const-inputs`, a calibration object as an input: `const=True constant=True`; `{{ "const " if e.const }}{{ e.variable.qualifier }}...` gives `const const volatile uint16_t ConstMap`, which `-Wduplicate-decl-specifier` stops under the CI flags. The surrounding reasons are untrue too: `docs/templates.rst:288-289` "the `const const` that no compiler accepts", `docs/generated_artefacts.rst:359` "a second `const` does not compile" and `model.py:113` "c refuses a repeated qualifier": C99 6.7.3p4 (C11 p5) allows it and gcc -std=c11 compiles it with a warning. *Change (S):* `const` true only where it adds one; correct the three sentences.

- **M10. "The two differ only at the ends of the 64 bit range" is untrue of `.value` and `.literal`.** `docs/templates.rst:202-210`, `src/ddd/backends/c/literals.py:48-66`. *Evidence* (`docchk/gk/a.c`): `5000000000` becomes `5000000000LL`, `4294967295` becomes `4294967295LL`, everything past `int`. "The narrowest type that holds it" is untrue of the second, which `unsigned int` holds, and of `-2147483648`, which is not an `int` expression in C. The literals themselves compile. *Change (S):* correct the sentences.

- **M11. `Sensor` and `Sensor_` get one include guard (previous review, still open).** `src/ddd/backends/c/literals.py:226-233`, `docs/templates.rst:252-254`, `SPEC.md:1412-1414`. *Trigger* (`e9.txt`): both headers `DDD_COMPONENT_SENSOR_H`; a file including both: `'B' undeclared`. `compile.sh` compiles each header alone, so it does not notice. *Change (S):* stop stripping, or extend `name-collision`.

- **M12. The standard says a linear function uses `LINEAR`; DDD writes `RAT_FUNC`, and no document says this is a choice.** `src/ddd/backends/a2l/model.py:634-652`, `SPEC.md:1899`, `docs/generated_artefacts.rst:898-924`. ASAP2 1.6.1, COMPU_METHOD: "Note: For linear functions, use the ConversionType LINEAR". `COEFFS_LINEAR a b` states `PHYS = a*INT + b`, the description's own direction, and would retire the page's section on why the coefficients look inverted. `RAT_FUNC` reads correctly (every record checked, `oracle.py`) and older tools know it, which may be the reason. *Change (S):* say so, or switch.

- **M13. A component description ending in `??/` stops the CI flag set.** Extends pass 6 M6, and qualifies "already defused". `src/ddd/backends/c/literals.py:205-223`, `examples/templates/{component}.h.jinja2:7`, `ddd_globals.c.jinja2:17`, where the text ends the line. *Trigger* (`e12.txt`, `cases/tri_comp`): `gen/C.h:12:8: error: trigraph '??/' converted to '\' [-Werror=trigraphs]`. *Change (S):* `sanitize_comment` writes `? ?`.

- **M14. "The unsuffixed name goes to the object that reaches the file first, the plain objects in name order" is not what happens.** `SPEC.md:1894-1897`, `src/ddd/backends/a2l/model.py:439`. *Trigger* (`e1.txt`, `cases/cmname`): measurement `C_meas` (factor 0.5, V), axis `Z_axis` (0.25, V), curve `B_curve` over it with no method of its own: `CM_LIN_V` goes to `Z_axis`'s, reached through the curve, and `C_meas` gets `CM_LIN_V_2`. Stable and harmless. Say "first met, the axes of a curve when the curve is".

- **M15. Two compiler options earn a misleading reason.** `src/ddd/addresses.py:133-135, 200-203`, for pass 11. `-g -gsplit-dwarf`: "the unit defining it was built without debug information (-g)"; it was, and the fix offered is what it already did (`variants.txt`, `split`). `-g1`: "'SA' is not an array, so it has no element [0]", where the image's debug level simply holds no types. Both safe: address 0 and `address-missing`.

- **M16. `ddd build-info P -o P` overwrites the description it names.** `src/ddd/cli.py:1650-1651`. Adds a verb to pass 5 I5: `_refuse_a_source` is not called here. *Trigger* (`addr_map.txt`): exit 0, the project file is now a build record.

- **M17. Small untrue sentences.** `docs/generated_artefacts.rst:1235-1239`: the example map puts `AxisA` and `ParameterA` at one address, `0x08004000` and `134234112` being the same number. `docs/data_dictionary.rst:74`: `LOWER_LIMIT` and `UPPER_LIMIT` are no keywords of the format. `docs/data_dictionary.rst:15-16`: `shape` and `MATRIX_DIM` "read from one field, so they cannot drift apart": C reads `dimensions` under a project's constant, A2L reads `shape`; true of the shipped templates, as pass 1 I12 says. `docs/templates.rst:228-233`: "Objects without a section are not here - they stay in their component's group" reads as if a placed object leaves its group; it is in both (`e16.txt`), so a template walking `model.groups` and `model.sections` defines it twice.

### Status of the 2026-09-15 findings in this area

Verified fixed, by running the scenario or, for the sentences, reading the line: P4-I1 (`e9.txt`), P4-I2 (`P.a2l` opens `EF BB BF`), P4-I4 (`reference-kind`, and `model.py:456-457`), P4-M1, M2, M3, M4, M5, M6, M7, M8 (`e14.txt`), M9, M10 (the plugin's header compiles), M12.

| id | finding | status | where |
| --- | --- | --- | --- |
| P4-I3 | derived limits below the raw maximum | FIXED for short decimals (`7.65`, `3276.7`), STILL OPEN past twelve digits | M1 |
| P4-M11 | Windows file names | path length FIXED (`backends/base.py:418-426`); device names STILL OPEN, unreproducible here: `Aux`, `Con`, `Nul`, `Prn`, `Com1`, `Lpt1` write and compile on this Windows 11 (`e9.txt`) | KNOWN, plan self-review |
| previous pass 8 M4, carried at `review-2026-09-15.md:4133` | `Sensor` and `Sensor_` share a guard | STILL OPEN | M11 |
| P4 test gaps | `MOD_COMMON`, `HEADER`, the `_2` suffix | STILL OPEN | Test gaps |

### Open questions

1. **Which way does a tool read `MATRIX_DIM`?** (I3.) An hour with CANape. If it is the other way, every array of two or three dimensions in every a2l written so far is transposed: `_matrix_dim` loses its `reversed`, and it is a release note. The same session settles question 2, and whether a tool takes an axis's number of points from `MaxAxisPoints` when its layout states no count: the default `RL_AXIS_*` relies on it, and every example in the standard states one.
2. **Does a tool accept a floating point count?** KNOWN, `specs/2026-09-23-record-layouts-design.md:40-42`: `NO_AXIS_PTS_X 1 FLOAT32_IEEE` is legal by 3.5.91's `datatype` and was shipped on that. If a tool refuses it, `point-counts-unrepresentable` should refuse floats.
3. **Should a derived limit round outward?** (M1.) Outward means no raw count is ever out of limits at the price of a limit one digit longer; it changes every archived baseline's limits again, by less than the tolerance of `is_above`.
4. **Is `RAT_FUNC` a decision?** (M12.) If older tools are the reason, write it down; if not, `LINEAR` removes a page section.

### Test gaps

- **Ten of 38 mutations of the generating code pass every suite that covers it.** On a copy of the tree, each mutation against the twenty suites about generation (`mutate.py`, `mutate.txt`, 28 killed), then the ten survivors applied together against `test_documentation`, `test_transcripts`, `test_cmake`, `test_plugins`, `test_example_plugin`, `test_generate_project` and `test_lsp`: no new failure (`mutate2.py`, `mutate2.txt`). An eleventh survivor, the map read by `int(text, 0)`, differs only on a leading zero and I do not count it. The ten:
  - `A2L_TYPE`: `uint64` written `A_INT64`, `float64` written `FLOAT32_IEEE`, `sint32` written `ULONG`, `boolean` written `SBYTE`. The table at `SPEC.md:388-400` is pinned for `UBYTE`, `SBYTE`, `UWORD`, `SWORD` and, in a counted layout, `ULONG`: `A_UINT64`, `A_INT64`, `SLONG` and `FLOAT64_IEEE` appear in no test at all, `FLOAT32_IEEE` in one counted axis. Each of these is a tool misreading every such value, with the coverage gate green.
  - `MOD_COMMON`: `ALIGNMENT_INT64 4`, `ALIGNMENT_WORD 1`; `HEADER` without `PROJECT_NO` (P4's list, still open).
  - `GROUP`: a parameter's member filed under `REF_MEASUREMENT`, the dangling reference `backends/a2l/model.py:493-495` says a tool "drops ... without a word"; the leaves ahead of the plain objects, against `SPEC.md:1851-1853`.
  - C: a `uint32` literal without its `U`.
  What did kill the rest: the order and fields of the three record kinds, `MATRIX_DIM`, `COEFFS`, the counted layouts, `ROW_DIR`, the byte order mark, the image's arithmetic and the 32 bit bound are all properly pinned.

- No test reads an A2L record back. `tests/test_a2l.py` and `tests/test_point_counts.py` match strings; `tests/test_address_fixtures.py` holds offsets to an oracle but never a value through a `RECORD_LAYOUT`. `a2lread.py` and `oracle.py` here are about 700 lines of what that test would be, and they read 1,664 records in seconds. (M)
- Nothing compiles the full range. The container targets compile the demo (`docker-compose.yml:49, 58`); `tests/test_cmake.py:690-735` compiles one counted project with one `uint32` map under the CI flags. The matrix here is small enough for the suite under `gcc` where present. (S)
- Not one test has an axis against its input's unit (I1), a component named after a header (I2), a size past 65535 (M2), or a group past ten elements (M3). `REF_CHARACTERISTIC` appears in one test, `tests/test_calibration.py`, and `REF_MEASUREMENT` is asserted only for one plain object at a time.
- `tests/test_generation.py` does not compile anything, although the review kit names it; its `/*` test holds a string, and `tests/test_cmake.py:512` is what compiles it.

### Assessment

This is the part of DDD I would trust most. I tried for wrong output and did not get any: every address, size, count, value, conversion, datatype, qualifier and reference agrees with what gcc and the linker did, across every datatype, shape, kind, conversion and structure form, both `point_counts`, 26 image variants, a 32 bit ABI, big-endian images and 456 random projects, and the documents describe what the tool does nearly to the character. Section 6's image reader is better than its specification asks. What is left is at the edges of what a project may legally say: two objects whose meanings must match and are not compared (I1), a file name that takes a header's place (I2), numbers and sizes that outgrow a field or twelve digits (M1, M2). The one thing I cannot call sound is what no one can call sound from here: the reversed `MATRIX_DIM` is an inference from the standard stated as its rule, the standard's own formula reads the other way, and the tool that would settle it has not been opened (I3). The weakness is not in the code but around it: the tests pin the shape of the file much less than the code deserves, ten of 38 mutations of the generating code pass the suites, among them `uint64` written `A_INT64` and `float64` written `FLOAT32_IEEE`, so the correctness measured here today is held by nothing tomorrow.

```candidates
8|I1|src/ddd/analysis.py:3020|An axis and its input measurement may differ in unit and conversion under --strict; the a2l then contradicts 3.5.17
8|I2|src/ddd/analysis.py:1792|A component named after a header takes its place on every include path: stdint, driver, and Signal or Math on a case-insensitive disk, clean check
8|I3|src/ddd/backends/a2l/model.py:536|The reversed MATRIX_DIM is an inference stated as the standard's rule; 3.5.62's own formula reads the other way and no tool has read one
8|M1|src/ddd/models/conversion.py:367|Rounding moved P4-I3 past twelve digits: uint64 under factor 1, uint32 under 2^-10, a derived limit below the raw maximum
8|M2|src/ddd/backends/a2l/model.py:536|Sizes past the 16 bit uint reach MATRIX_DIM, NUMBER and MaxAxisPoints under --strict, where event is capped
8|M3|src/ddd/backends/a2l/model.py:508|Records list SA[2] before SA[10], the GROUP the reverse; the comment and SPEC 5.1's cell[10] sentence are wrong
8|M4|src/ddd/backends/a2l/templates/project.a2l.jinja:18|MOD_COMMON's fixed alignments contradict the image on i386; --image takes the byte order and not this
8|M5|SPEC.md:2005|--image on ET_DYN writes load-relative offsets as absolute addresses with no finding or sentence
8|M6|SPEC.md:1923|An unconditional curve over a conditional axis passes --strict; the a2l points at address 0
8|M7|src/ddd/addresses.py:64|A UTF-16 map names no file, a deep one is a traceback with exit 1, a huge number gives python's advice
8|M8|src/ddd/analysis.py:2393|float64 under a factor above 1 is refused even with stated limits, for a reason that is not so
8|M9|docs/templates.rst:371|.const is true where no const was added, so a template written from the page gets const const; no compiler accepts is untrue
8|M10|docs/templates.rst:204|.value and .literal differ past int, not only at the ends of 64 bits; narrowest type is untrue
8|M11|src/ddd/backends/c/literals.py:230|Sensor and Sensor_ share one include guard (previous review, still open)
8|M12|src/ddd/backends/a2l/model.py:641|The standard says use LINEAR for a linear function; RAT_FUNC is written and no document says it is a choice
8|M13|src/ddd/backends/c/literals.py:223|A component description ending in ??/ stops the CI flag set
8|M14|SPEC.md:1894|The unsuffixed compu method name does not go to the object reaching the file first
8|M15|src/ddd/addresses.py:133|-gsplit-dwarf is told to build with -g, -g1 that a variable is not an array
8|M16|src/ddd/cli.py:1651|ddd build-info P -o P overwrites the description it names (adds to pass 5 I5)
8|M17|docs/generated_artefacts.rst:1235|Small untrue sentences: the example map's one address, LOWER_LIMIT, cannot drift apart, a placed object in both lists
```

## Pass 9: tool interface and build integration (SPEC 3.11, 7, 7.1)

### Scope covered

**Read in full, with line numbers:** `SPEC.md:1114-1221` (3.11), `:2062-2340` (7, 7.1), `:775-811` (3.6), `:129-150` (1.6); `src/ddd/cli.py` (2076), `src/ddd/plugins.py` (530), `cmake/Ddd.cmake` (794), `.pre-commit-hooks.yaml`; `docs/command_line_interface.rst` (739), `docs/build_integration.rst` (856), `docs/plugins.rst` (287); `examples/cmake/CMakeLists.txt` and its sources, `examples/plugins/ddd_layout.py`; what the command line reaches: `src/ddd/backends/base.py` (549), `src/ddd/deliveries.py` (231), `src/ddd/build_info.py`, `src/ddd/names.py`, `src/ddd/identity.py:130-209`, `src/ddd/diagnostics.py:255-590`, `src/ddd/loading.py:492-498, 1040-1105`, `src/ddd/gui/server.py:239-262, 325-500, 905-1057`, `src/ddd/lsp/discovery.py:55-121`, `src/ddd/lsp/server.py:917-927`; the outline of `tests/test_cmake.py` and its `:1-145, 737-810, 1050-1262, 1382-1458, 1500-1640, 1844-1921`, `tests/test_cli.py:3010-3060`; the previous review's pass 5 and the "Left open" of `plans/2026-09-16-review-fixes.md`.

**Ran** (under `SCRATCH/pass-9/`; every path below is relative to it; CMake 4.4.3, Ninja 1.13.2, gcc 15.2 on Windows):

- `tests/test_cmake.py`: 57 passed (`test_cmake.txt`). On this host the `ADDRESSES_FROM_IMAGE` tests take their non-ELF branch (`tests/test_cmake.py:1090-1103`).
- `examples/cmake` for real, from a copy (`cm/`): configure, build, second configure, build, touch a description, build twice (`cm/run1.txt`); a change on one side (`cm/run2.txt`); a change on both sides, build twice, disassembling the image each time (`cm/run3.txt`). The same story on a small project under Ninja in both modes and under MinGW Makefiles, running the image (`c1/`, `c1b/`).
- Every command and option, about 230 command lines over copies of the examples, each with its exit code, stdout, stderr and `--format json` parse (`cli/m1.txt` to `m5.txt`); closed pipes with a reader gone, on Windows and, for the commands that need no pydantic, on Linux (`cli/pipe*.txt`, `wsl/pipe.txt`); line endings (`cli/crlf.txt`); `ddd id --assign` on 15 odd files (`idp/run.txt`); `ddd tool from-elf` on a fixture (`elf/run.txt`).
- `ddd gui`'s surface, every option, a taken port, reachability of the printed address (`gui/g.txt`, `gui/host.txt`).
- 25 plugin modules: printing and child processes under every command and on the wire of `ddd lsp`, interrupts, undeclared and flagged checks, odd backends, ordering across sub-projects, the settings rules (`plug/`, `plug2/`, `plug3/`).
- About 70 small CMake projects: awkward directory names in both modes (`s4/`, `s4b/`), quoted empty keywords (`s2/`), the handshake after an in-place upgrade (`s3/`), wildcards added and removed (`s1/`), a late or broken `PROJECT`, a banner, a registered sub-project, a deleted output directory (`s6/`), vocabulary recipes, C++, a bare `DDD_EXECUTABLE`, a component root, a shared output directory (`s13/`), subdirectories (`s20/`), a plugin that stops importing (`s33/`), the 20 refusals (`s40/run.txt`), templates added and removed (`s41/`, `s32/`), a vocabulary generated later (`s42/`).
- Two mutation probes of `ddd.cli.main`, in process: 3,506 random mutations of the demo's files by 9 commands (`fuzz/fuzz1.txt`), and 2,636 schema-respecting ones over the demo, structures and vocabulary examples by 10 commands, 1,447 of them past the loader (`fuzz/fuzz2.txt`).

**Not covered:** `ADDRESSES_FROM_IMAGE` end to end: MinGW links PE, and WSL has gcc but no CMake or pydantic here, so the step was read and left to the suite's Linux cells. The 3.20 and 3.30 floors: only CMake 4.4.3 is at hand. The hook through `pre-commit` itself, which is not installed: the yaml was read and `ddd id --assign` probed directly. A real console Ctrl-C: `KeyboardInterrupt` was raised from plugins instead. macOS. `ddd lsp` beyond the wire question (pass 10).

**Met again and cited, not re-filed, with what this pass adds:**

- pass 1 C2, I6: not re-run; C1 below means that in the map flow the first build after an edit is stale in its code as well as in its a2l.
- pass 1 I5, I14, I15, pass 2 M1, pass 4 M5, pass 5 I3, I5, M14, pass 8 M5, M16: read again, stand as filed. For pass 4 M5: `ddd gui` stopped by Ctrl-Break instead of Ctrl-C ends with the system's `0xC000013A` (`gui/g.txt`).
- pass 4 I4: a directory or a pattern is told the same `not readable as json, skipped` (`cli/m1.txt`).
- pass 4 M7: a build without CMake inherits I1 and M13 below.
- pass 5 I4: **adds a consequence.** In `PROJECT` mode a plugin that prints at import has its banner read as a file name by the module: `ninja: error: 'hello from a plugin banner', needed by 'ddd/fw/ddd_globals.c', missing and no known rule to make it` (`s6/run.txt`, S8). M2 below is the same promise's other holes.

### Strengths

- **The command line is a real contract, and it holds.** About 230 command lines: exit 0, 1, 2 exactly as `SPEC.md:2179-2211` says; stdout and stderr split as documented; every `--format json` document parses and carries the documented keys, but for M3; a usage error after the analysis reports the findings first in the requested format; `--stand`, `--dict` and `--no-browse` are refused; `sources` and `artefacts` are tolerant in both formats; `--without` subtracts with its options and refuses a run left with nothing.
- **Nothing escaped `main` in 57,914 runs over mutated projects.** No traceback and no document that does not parse on the stream the page names, `generate --force` included; the second probe, which counted them, saw no exit 2 in 26,360 runs (`fuzz/fuzz1.txt`, `fuzz/fuzz2.txt`). The documents' numbers are right: 72 checks, 8 fixed, 9 `(project)`.
- **Interrupts are clean.** `KeyboardInterrupt` at import, in a validator and in a hook, under `check`, `sources` and `checks --plugin`: `ddd: interrupted`, exit 130, no traceback (`plug/run.txt`).
- **The plugin api does what 3.11 says.** Order across root and sub-projects, a module named twice keeping its first place, settings stated twice, a required setting omitted, a block with no model, a key outside the grammar, `unknown-extension` relaxed and carried, a clash with a built-in file refused before anything is written, a bad return from `generate` (`plug/run.txt`, `plug2/run*.txt`).
- **The second configure and a touch are clean.** A second configure rewrites `ddd-build.json` and the schemas and nothing else, and `ninja: no work to do` follows. A touched description reruns the generation, every file `unchanged`, nothing compiled, then `no work to do` (`cm/run1.txt`). A change on one side stops the build at `definition-mismatch` and writes nothing (`cm/run2.txt`).
- **The module refuses well and quotes well.** 19 of 19 misuses are refused naming what is wrong (`s40/run.txt`). Spaces, parentheses, commas, `&`, `'`, `+`, `=`, `^`, `!` in the paths build in both modes, `#` and `$` in the collected one (`s4/`, `s4b/`); a byte order mark, a component root, components in subdirectories, the vocabulary recipes and a bare `-DDDD_EXECUTABLE=ddd` work (`s13/`, `s20/`, `s30/`).
- **The previous review's Important findings in this area are fixed where they were found.** The output directory is owned, the address map recipe settles on a 64 bit host (it passes here), abbreviations are gone, `id --assign` stamps past an unwritable file (`cli/m5.txt`).

### Issues

#### Critical

- **C1. Under Ninja, the build after a description change recompiles the definitions and relinks, but not the components reading the changed header: exit 0, and the image's code disagrees with its globals until a second `ninja`.** `cmake/Ddd.cmake:646-656` (`OUTPUT` holds the shared files alone), `:436-439`, `:596-600`, `:684-690`. Against `docs/build_integration.rst:4-6, 420-425`, `docs/generated_artefacts.rst:552-572` ("only what genuinely changed is touched", "a correct build"), `README.md:900-903`.
  *Trigger* (`c1/run.txt`): `Sensor` produces `Speed`, `Logger` reads it. Widen it from `uint8` to `uint16` in both descriptions; `sensor.c` now writes 1000; `logger.c` needs no edit. `ninja`: exit 0, no finding, compiles `sensor.c` and `ddd_globals.c`, relinks. `Logger.h` already says `extern uint16_t Speed`, and the image prints **`the logger reads 232`**. A second `ninja`, nothing touched: `output logger.c.obj older than most recent input Logger.h`, compile, relink, `the logger reads 1000`. The shipped example does the same: `ValueJ` to `uint32` in `examples/demo`, and after one build `event_logger_step` still stores `mov %dl,(%rax)` into a 4 byte variable, after a second `mov %edx,(%rax)` (`cm/run3.txt`). `PROJECT` mode the same (`c1b/run.txt`).
  *Why:* Ninja decides what is dirty before it runs anything. A `{component}` header is no edge's output, so it is stat'ed once, before the generation rewrites it; the object's only tie to the generation is order-only; and `restat` then cleans the compile edges against the stale stamp. Under Makefiles each target is checked after the generation ran, and the same edit builds right (`c1/run_make.txt`). A plugin's files, "not declared as outputs" by the same design (`docs/build_integration.rst:104-106`), sit on the same edge (read off).
  *Consequence:* any change of a datatype, array size or qualifier whose consumers' C is not edited gives a wrong image from a green incremental build, and an `ADDRESS_MAP` or `--image` a2l then describes that image. The next build heals it, so it reads as a flake; whoever builds once and flashes has shipped it. Ninja is the generator the module and the pages name. A clean build is right, which is why the suite never saw it: nothing compiles a component after a header change, `tests/test_cmake.py:1622` asks about `ddd_globals.c.obj` alone.
  *Change (S-M):* declare the per-component headers as `BYPRODUCTS`. A copy of the module with the two names written in builds right and keeps the granularity the pages promise: a description edit that leaves `Logger.h` alone recompiles `sensor.c` and not `logger.c` (`c1fix/run.txt`). The names: `ddd_add_component` reads `component.name` at configure and carries a second transitive property; `PROJECT` asks the tool. See open question 1.

#### Important

- **I1. In `PROJECT` mode a plugin that stops importing leaves the dependencies, and the build goes green with the old artefacts.** `src/ddd/loading.py:1050-1055, 1063-1069`, `src/ddd/cli.py:1821-1825`, `cmake/Ddd.cmake:124-141`. Against `SPEC.md:2127-2129` ("an edited plugin re-runs the generation"), `docs/plugins.rst:36-37`, `docs/build_integration.rst:266-268`, `docs/command_line_interface.rst:723-725` ("so a configure step hears about it").
  *Trigger* (`s33/run.txt`): `ddd_generate(fw PROJECT p.ddd.json ...)`, the project naming `stamp.py`, whose backend writes `stamp.h`. An edit is noticed. A typo in the plugin: `Re-running CMake...`, `ninja: no work to do.`, nothing printed, `stamp.h` the old one. The typo fixed: `no work to do`. Every later edit of the plugin: `no work to do`, `stamp.h` still old, until something else re-runs configure. Deleting the plugin is the same (`s33/run2.txt`); only `fw_ddd_check` says anything.
  *Why:* `ddd sources` lists loaded plugins alone and exits 0, so the next configure drops the file from `DEPENDS`; and the module captures stderr and prints it only on a non-zero exit, so `plugin-invalid`, a fixed error, reaches nobody. A missing include shows the second half too: configure exit 0, silent, then ninja's `missing and no known rule` rather than `file-not-found` (`s6/run.txt`, S7b).
  *Change (S):* list a `.py` spelling whether or not it imported, as a missing include already is, and print `ddd sources`' stderr as a `message(WARNING)`.

- **I2. A file a wildcard include starts or stops matching changes nothing: `ninja: no work to do`, against the page that promises the opposite.** `cmake/Ddd.cmake:116-120, 139`. Against `docs/build_integration.rst:268-270` ("adding a file matching an `includes` wildcard re-runs configure and picks the new component up"), and the harm `docs/command_line_interface.rst:697-699` says `ddd sources` closes.
  *Trigger* (`s1/run.txt`): `"includes": ["components/*.ddd.json"]`. Add `components/beta.ddd.json`: `no work to do`, twice; `BetaVar` in no artefact. `CMAKE_CONFIGURE_DEPENDS` watches the files that were listed, and a new file touches none of them. Remove a matched file: configure re-runs, the generation does not, its command line being the same and its inputs only fewer, so `BetaVar` stays in `ddd_globals.c` and the a2l: `no work to do`. A new component whose C is linked fails on its missing header, which is loud; a vocabulary file, or a component of tool-only objects, is silent.
  *Change (S):* glob the patterns with `file(GLOB ... CONFIGURE_DEPENDS)`, and write the source list to a file in the build tree only when it differs, as a dependency of the generation, so that a shorter list regenerates too.

- **I3. A registered sub-project is collected but only its own file is watched: edits to what it includes do not regenerate.** `cmake/Ddd.cmake:284, 543, 650`, `:229-246`. Against `docs/build_integration.rst:376-380`; `SPEC.md:2223-2227` does not say a project file may not be registered, and nothing refuses one.
  *Trigger* (`s6/run_s9.txt`): `ddd_add_component(a JSON sub.ddd.json)`, `sub.ddd.json` including `inner.ddd.json`: configures and builds, the collected project includes it. `inner.ddd.json` from `uint8` to `uint32`: `ninja: no work to do.`, `ddd_globals.c` still `uint8_t InnerVar`, while `ddd list` on the same collected project says `uint32`. A plugin that sub-project names is no dependency either (read off). A supplier handing over a sub-project is the method's own case (`examples/demo/subsystems/logging/`), and registering it is the natural call.
  *Change (S):* refuse a file whose top level key is `project` in `ddd_add_component`, or ask `ddd sources` for it at configure. Open question 2.

- **I4. The guard against a keyword given no value misses the form every example uses: `ADDRESS_MAP "${DDD_MAP}"` with the variable unset builds, with every address 0, and `PROJECT "${X}"` falls into the collected mode.** `cmake/Ddd.cmake:88-102, 441-448`. Against `SPEC.md:2232-2234`, `docs/build_integration.rst:548-554`, whose own recipes quote (`:629-631`).
  *Trigger* (`s2/run.txt`, `s2/run31.txt`): under `cmake_minimum_required(VERSION 3.31)`, no output at all, configure exit 0, build exit 0, `ECU_ADDRESS 0x00000000`, no map seeded, none a dependency; `PROJECT "${DDD_PROJECT}"` generates out of the link graph. Under 3.30 on this CMake an author warning about policy CMP0174 is all there is, and a CMake older than 3.31 has no such policy to warn about. The bare `${DDD_MAP}` is refused. With `PARSE_ARGV` a quoted empty string is a value, so `KEYWORDS_MISSING_VALUES` does not name it, and every check below is `if(arg_X)`. `OUTPUT_DIRECTORY`, `SCHEMA_DIRECTORY`, `BYTE_ORDER`, `NAME`, `PLUGINS` and `SEVERITY` are dropped the same way. `tests/test_cmake.py:1415-1438` tries the bare form alone.
  *Change (S):* walk `ARGV<n>`, refusing a keyword followed by an empty argument, which works from 3.20 on.

- **I5. On Windows a `PROJECT` build under a non-ASCII path cannot build: the module decodes the UTF-8 of `ddd sources` in the console's code page.** `cmake/Ddd.cmake:125-129`, with `src/ddd/cli.py:123`, which forces UTF-8 on the pipe.
  *Trigger* (`s4b/run.txt`, `s4/run.txt`): a checkout under `Müller-project`: configure exit 0, then `ninja: error: '.../M├╝ller-project/components/alpha.ddd.json', needed by ..., missing and no known rule to make it`. `Müller-collected` builds. `execute_process` defaults to `ENCODING AUTO` on Windows. `C:\Users\André\...` is an ordinary place for a checkout, and nothing tells the reader what happened. No test has a non-ASCII path.
  *Change (S, one line):* `ENCODING UTF-8`, and a test.

#### Minor

- **M1. "Ends the run at 0 and in silence" holds only for a pipe that breaks during a handler's write.** `src/ddd/cli.py:137-146`; `SPEC.md:2183-2185`, `docs/command_line_interface.rst:189-191`. The documented `| head -1` passes. A reader already gone does not: on Windows `ddd schema component | true` and `ddd dump p | true` give `ddd: [Errno 22] Invalid argument`, exit 2, the usage error the page says is gone; `ddd --version | true`, `cmake-dir`, `checks`, `check --format json`: `Exception ignored on flushing sys.stdout`, exit 120 (`cli/pipe.txt`, `cli/pipe2.txt`). On Linux `ddd --version`, `cmake-dir`, `--help`: `Exception ignored ... BrokenPipeError`, exit 120 (`wsl/pipe.txt`). Two holes: what stays buffered is flushed at interpreter shutdown, past `main`'s `try`; and Windows reports a write to a pipe with no reader as `EINVAL`, a plain `OSError`. `tests/test_cli.py:3014-3050` mocks a stream raising `BrokenPipeError`, on no real pipe. *Change (S):* flush inside the `try`, and read `EINVAL` on stdout as closed on win32.

- **M2. "Never inside a document" has two more holes after pass 5 I4.** `src/ddd/plugins.py:514`, `src/ddd/lsp/server.py:926-927`; `SPEC.md:1191-1197`, `docs/plugins.rst:209-216`. `redirect_stdout` rebinds `sys.stdout` and no more: a hook running `subprocess.run([...])` without capture, `os.write(1, ...)` or `print(file=sys.__stdout__)` lands in `ddd check --format json` and in `ddd dump` (`plug/run.txt`), and on the wire of `ddd lsp`, `...}}CHILD SAYS HI\r\nContent-Length: 43` (`plug/lspwire.txt`). And under `ddd dump --format json` a hook's `print` goes where the findings document goes: stderr is `HOOK SAYS HI\n{...`, not json. *Change (S):* `os.dup2` around hooks and at the server's start; say in the page that `dump`'s stderr is shared.

- **M3. `ddd list --format json` loses `project`, `components` and `variables` when a file fails to load, and `generate` loses `generated`; `sources` and `artefacts` keep theirs, empty.** `src/ddd/cli.py:1301-1303, 1151-1153, 1211-1213`; `SPEC.md:2087-2088`, `:2169`. `ddd list nosuch.ddd.json --format json` has `diagnostics` and `summary` alone (`cli/m1.txt`); a script reading `doc["variables"]` meets a `KeyError` on an ordinary exit 1. *Change (S):* empty values.

- **M4. The release handshake is skipped after an in-place upgrade of the tool, the case it exists for.** `cmake/Ddd.cmake:78-86`; `SPEC.md:2323-2327`, `docs/build_integration.rst:37-41`; the comment says "upgrading either side asks again". The cache key is the tool's path and the module's version. A project with a copied `Ddd.cmake` and a `pip install -U` in its venv: reconfigure exit 0, not asked; a fresh build tree refuses (`s3/run.txt`). *Change (S):* key on the tool's mtime and size as well, or ask every configure; `ddd --version` needs no pydantic.

- **M5. The documented fallback for a project that cannot be resolved yet is dead: the module says it falls back, then stops.** `cmake/Ddd.cmake:122-123, 203-213, 250-258, 375-376, 532-536`; `docs/build_integration.rst:270-272`. A `PROJECT` in the build tree, generated later, which `_ddd_absolute_input` accepts as something that "may well be generated later": status line `the generation will depend on that file alone`, then CMake's raw `file failed to open for reading`. A syntax error: the same line, then fatal (`s6/run.txt`, S6, S7a). *Change (S):* say that the file has to exist and parse at configure, and remove the sentence, the status line and the tolerance.

- **M6. Under Makefile generators a generation that changed nothing runs again at every build, for good.** `cmake/Ddd.cmake:646`; `SPEC.md:2280-2281` and `docs/build_integration.rst:512, 589` state this of the a2l step alone. Touch one description: `Generating the data dictionary` on every later build, where Ninja says `no work to do` (`c1/run_make.txt`). Nothing recompiles, and each build pays for the whole analysis and every plugin's import. No test runs a Makefile generator although the pages make claims about Make. See open question 3.

- **M7. Six edges of the module, each with a misleading message or none.** (a) A checkout under `pr[1]`: `file(GLOB)` reads the bracket, and the refusal is `no *.jinja2 template in ".../pr[1]/templates"` (`:588`, `s4/run.txt`). (b) The output directory deleted: `ninja: error: 'ddd/fw/fw.ddd.json' ... missing and no known rule`; a reconfigure mends it, and nothing says so (`:650`, `s6/run.txt`, S10). (c) `project(x LANGUAGES CXX)`: `CMake can not determine linker language for target: fw_ddd_globals` (`:723`, `s13/run.txt`), the confusing failure the page's three refusals exist to spare a reader (`docs/build_integration.rst:225-229`). (d) A helper in a subdirectory of the templates, which jinja finds, is no dependency: its text changed, `no work to do`, the old text stays in the output (`:588`, `cli/m5.txt`). (e) A template removed: re-configure runs, `no work to do`, and its output stays in the directory on the include path, against `docs/build_integration.rst:209-211` (`s41/run.txt`). (f) A vocabulary file generated during the build is checked as a component: `alpha.ddd` fails `file-kind` until a second configure (`:229-233`, whose "the only kind worth generating" a generated constants file refutes, `s42/run.txt`).

- **M8. `ddd gui --host` with any specific address serves nobody and says nothing.** `src/ddd/cli.py:399-403`, `src/ddd/gui/server.py:488-498, 630`, `:976`. `--host 127.0.0.2` or a LAN address: starts, prints `http://127.0.0.1:N/...`, which is refused; the address it does listen on answers `421 misdirected request` (`gui/host.txt`). The docstring of `address` knows this half; `--help` says "IPv4 address to listen on". Beside it: `-b nosuchdir` and `-b afile.txt` are accepted without a word, the project then analysed under default severities, and a mistyped project is `nosuch.ddd.json is not a project description`, a component with OS separators (`gui/g.txt`). Preview options, so Minor. *Change (S):* refuse a host that is neither loopback's `127.0.0.1` nor a wildcard.

- **M9. `--renames` alone creates no directory and is not staged.** `src/ddd/cli.py:914-923`. `compare a b --renames nosub/r.json`: the comparison runs, then exit 2, `No such file or directory`; `dump -o`, `--dictionary`, `schema -o` and `build-info -o` all create the parents (`cli/m2.txt`). It writes in place, where `dump -o` and `--dictionary` stage.

- **M10. `check --baseline` blames the command line for a file it could not open.** `src/ddd/cli.py:844`, against the comment at `:1898-1900`. `ddd check nosuch.ddd.json -W layout/x=ignore`: exit 1. The same with `--baseline b`: the finding, then `unknown check 'layout/x': no loaded plugin registers it`, exit 2 (`cli/m3.txt`).

- **M11. A backend's `name` is not held to its plugin's: one named `c` takes back the c sources.** `src/ddd/plugins.py:446-454`, `src/ddd/cli.py:1255`. `ddd generate bname -o d`, into a directory `generate all` filled: `removed d/ddd_globals.c`, `ddd_globals.h`, `ddd_types.h`, `Comp.h`, and the manifest files `b.txt` under `c` (`plug/run.txt`). KNOWN in part: `plans/2026-09-16-review-fixes.md` says the manifest keys on the backend's own name. *Change (S):* stamp a plugin's files with the plugin's name.

- **M12. `CheckInfo`'s flags are undocumented, and `needs_every_component` does nothing for a plugin.** `docs/plugins.rst:97, 108-115`, `src/ddd/diagnostics.py:270-274`. The example sets `comparison=True`, and no page says what it or the others do. A plugin check with `needs_every_component=True` is marked `(project)` by `ddd checks`, whose docstring says that is what `--standalone` holds back; `ddd check p.ddd.json --standalone` reports it, exit 1 (`plug3/run.txt`). See pass 7 M6 for `overridable`.

- **M13. On Windows stdout is CRLF, so `ddd sources p | while read -r f` gets a `\r` on every path.** `src/ddd/cli.py:107-118`; `docs/command_line_interface.rst:716-718` ("without being translated first"). All six paths `NOT FOUND` in Git Bash, the shell the pages' transcripts assume (`cli/crlf.txt`). CMake and `$(...)` strip it. *Change (S):* `reconfigure(newline="\n")`; `ddd dump >` then gives what `dump -o` gives.

- **M14. Small untrue or missing sentences.** `docs/command_line_interface.rst:10-12` "the one file the tool leaves behind for its own use" is `ddd-build.json`; `generate` leaves `.ddd-manifest.json`. `:624` "how both directories are used from a `CMakeLists.txt`" is a comment beside a literal path (`docs/build_integration.rst:29-32`): no page shows the `execute_process` the argument for the command needs. `docs/build_integration.rst:255-272` never says that without `ddd_add_component` a component links `<stem>_ddd_headers` itself. `SPEC.md:2320` "an upgraded DDD regenerates" is not so for the wrapper script `docs/build_integration.rst:36-37` recommends. `--dictionary out/.ddd-manifest.json` is told about path lengths, where `src/ddd/backends/base.py:240` refuses a backend that name (`cli/m4.txt`). `src/ddd/cli.py:864-866` prints `ok: 1 variable in 1 component are consistent`.

### Status of the 2026-09-15 findings in this area

Those not plainly fixed. Checked and fixed, by a run, by a passing test or read off the line: P5-I3, I4, M1, M4, M5, M7, M9, M10, M11, M12, M13, M14, M15, M16.

| id | finding | status | where |
| --- | --- | --- | --- |
| P5-I1 | a plugin's print inside a document | FIXED for `print` in a hook; open for import and validators (pass 5 I4) and for the rest (M2) | `src/ddd/plugins.py:514` |
| P5-I2 | an output path that is an input | FIXED against descriptions; open for images, maps, templates, `build-info` (pass 5 I5, pass 8 M16) | `src/ddd/cli.py:1933` |
| P5-I5 | a record naming an unknown check ends the server | pass 10's | `src/ddd/lsp/discovery.py:108-112` |
| P5-M2 | no last-resort handler in `main` | STILL OPEN as code: anything but `OSError` and `ValueError` is a traceback and exit 1, the findings code. Reached only through plugin misuse (pass 7 M6); 57,914 runs over mutated projects raised none, so unfiled | `src/ddd/cli.py:128-154` |
| P5-M3 | a hook can rewrite the dictionary | documented rather than changed; read off | `docs/plugins.rst:147-154` |
| P5-M6 | a closed pipe is a usage error | PARTLY: M1 | `src/ddd/cli.py:137` |
| P5-M8 | a dump handed to `check` | FIXED in the words; a dump not named `*.ddd.json` is still first told it "is a DDD description file", unfiled | `cli/m2.txt` |
| earlier P5 minor 1 | `SPEC` lists `--plugin` and `--renames` in the clause of `check --baseline` | STILL OPEN; `check --baseline --renames` is `unrecognized arguments` (`cli/m5.txt`) | `SPEC.md:2066-2068` |
| earlier P8 minor 2 | a lone surrogate ends `list` and `dump` | STILL OPEN (pass 6 M5) | |
| earlier P8 minor 8 | `PROJECT` re-runs configure on every component edit | STILL OPEN, by design, and imports the plugins each time | `cmake/Ddd.cmake:139`, `c1b/run.txt` |
| "still unstated" | `build-info` accepts a plugin override it cannot verify | STILL UNSTATED; `docs/build_integration.rst:309` overclaims for one | `src/ddd/cli.py:1639`, `cli/m1.txt` |

### Open questions

1. **How should the build learn the per-component headers (C1)?** `BYPRODUCTS` from names read at configure keeps the per-component rebuild the pages advertise, and a renamed component needs a reconfigure. A single declared header every component depends on is smaller, and rebuilds every component on any header change, which rewrites `docs/generated_artefacts.rst:552-572`. Both are right; leaving it is not.
2. **May a project file be registered with `ddd_add_component` (I3)?** Yes means the collected mode asks `ddd sources` for it at configure, and it gets a `<target>.ddd`. No means a configure error and a sentence for suppliers saying how to register a delivered sub-project.
3. **Is a Makefile generator supported (M6)?** Yes needs a stamp output and a test cell. No means the pages say Ninja, and their sentences about Make go.
4. **Should `ddd sources` list what the project names or what loaded (I1)?** Named keeps a build watching a broken plugin. It changes the docstring of `Workspace.sources` and the sentence "the file it was imported from" at `SPEC.md:2127-2128`.
5. **LF on stdout everywhere (M13)?** Yes makes `ddd dump >` and `dump -o` the same bytes and changes what a redirection gives on Windows.

### Test gaps

- Nothing compiles a component after a generated header changed (C1): `tests/test_cmake.py:1622` asks about the definition file alone.
- `PROJECT` mode with a wildcard: adding and removing a match (I2); a plugin that stops importing (I1); a registered sub-project (I3). `tests/test_cmake.py:737-810` edits a plugin that keeps importing.
- `test_it_is_refused_and_named` tries bare `${VAR}` alone, never the quoted form the pages use (`:1415-1438`).
- No non-ASCII path in any CMake test (I5). `test_the_include_refuses_it_naming_both_versions` configures once, so the cached handshake is never met (`:1880`).
- No test runs a Makefile generator, though `SPEC.md:2281` and the page state what Make does.
- The closed pipe tests mock `sys.stdout`: no real pipe, no `EINVAL`, no flush at exit (`tests/test_cli.py:3014-3050`).
- Hooks' stdout is tested through `print` alone: no child process, no `sys.__stdout__`, nothing on `dump`'s stderr document (`tests/test_plugins.py:2362, 2455`).
- `--host` with a specific address, `-b` naming nothing (`tests/test_gui_server.py`).

### Assessment

The command line deserves its claim to be a contract: about 230 hand-written command lines and 57,914 runs over mutated projects found no crash, no wrong exit code on a project's fault and no broken document, and what is wrong with it is at the rim, closed pipes and small inconsistencies. The CMake module refuses misuse better than most and quotes paths correctly in places many modules do not, and `tests/test_cmake.py` passes, but it is the weak half of this pass, because its reasoning about what a build system knows does not match what Ninja does. It decided that a consumer depends on "the generation step, not on an individual header path", and under Ninja that dependency orders the build without invalidating anything: the first build after a real change of a description ships objects compiled against the old header, with exit 0, which is the failure the whole tool exists to prevent, and the most serious thing I found. The neighbouring findings have the same shape: what the module watches is less than what the tool reads, so a wildcard match, an included file of a registered sub-project and a plugin that stopped importing all end in `ninja: no work to do` over stale artefacts, and the tool's findings at configure time are captured and thrown away. All of it is fixable in the module in days, with `BYPRODUCTS` already prototyped, but none of it is caught by the kind of test the suite has, which asks whether files exist and what they say after one build. One story test that makes a real edit of each kind, builds, asserts that the objects and the artefacts changed, and asserts that a second build has nothing to do would have found C1, I1, I2 and I3.

```candidates
9|C1|cmake/Ddd.cmake:646|Under Ninja the build after a description change recompiles the definitions and relinks but not the components reading the changed header: exit 0, the logger reads 232, a second ninja corrects it
9|I1|src/ddd/loading.py:1050|In PROJECT mode a plugin that stops importing leaves the dependencies: no work to do, exit 0, old artefacts, plugin-invalid captured and dropped at configure
9|I2|cmake/Ddd.cmake:139|A file a wildcard include starts or stops matching changes nothing, against the page's re-runs configure and picks the new component up
9|I3|cmake/Ddd.cmake:650|A registered sub-project is collected but only its own file is watched: an edit to what it includes leaves stale artefacts, no work to do
9|I4|cmake/Ddd.cmake:94|The empty keyword guard misses the quoted form every example uses: ADDRESS_MAP "${DDD_MAP}" unset builds with address 0, PROJECT "${X}" falls into the collected mode
9|I5|cmake/Ddd.cmake:125|On Windows a PROJECT build under a non-ASCII path cannot build: execute_process decodes the UTF-8 of ddd sources in the console's code page
9|M1|src/ddd/cli.py:137|Ends at 0 and in silence holds only for a pipe breaking during a write: a reader gone gives exit 120, on Windows exit 2 with Errno 22
9|M2|src/ddd/plugins.py:514|Never inside a document has more holes: a hook's child process, os.write and sys.__stdout__ reach stdout and the lsp wire; a hook's print enters dump's findings document on stderr
9|M3|src/ddd/cli.py:1301|list --format json loses project, components, variables on a load failure and generate loses generated; sources and artefacts keep theirs
9|M4|cmake/Ddd.cmake:84|The release handshake is cached on path and module version, so an in-place upgrade of the tool is not asked
9|M5|cmake/Ddd.cmake:122|The documented fallback for a project not resolvable yet is dead: the module says it falls back, then stops on file(READ) or string(JSON)
9|M6|cmake/Ddd.cmake:646|Under Makefile generators a generation that changed nothing runs again at every build; the pages state this of the a2l step alone
9|M7|cmake/Ddd.cmake:588|Six module edges: brackets in a path, a deleted output directory, a C++ project, a helper in a subdirectory, a removed template's output, a vocabulary generated later
9|M8|src/ddd/gui/server.py:488|ddd gui --host with a specific address serves nobody and says nothing; -b naming nothing is accepted in silence; a missing project is not a project description
9|M9|src/ddd/cli.py:914|--renames alone creates no directory and is not staged
9|M10|src/ddd/cli.py:844|check --baseline blames the command line for a root it could not open: exit 2 where the same run without a baseline exits 1
9|M11|src/ddd/plugins.py:446|A backend's name is not held to its plugin's: one named c takes back the c sources (KNOWN in part)
9|M12|docs/plugins.rst:97|CheckInfo's flags are undocumented, and needs_every_component is marked (project) but not held back by --standalone for a plugin
9|M13|src/ddd/cli.py:107|On Windows stdout is CRLF, so ddd sources piped into while read gets a carriage return on every path
9|M14|docs/command_line_interface.rst:10|Small untrue or missing sentences: the one file left behind, no recipe for cmake-dir, PROJECT's header wiring, upgraded DDD regenerates, the manifest as --dictionary, 1 variable are
```
