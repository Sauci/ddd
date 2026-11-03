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
