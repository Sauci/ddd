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

### An accident during the review

Pass 19 ran one probe as root in the WSL instance `Ubuntu-24.04`, to show what the writer does to a
device (its M9), and the probe also replaced that instance's real `/dev/null` with a regular file. Nobody
had asked for root. The pass restored the device at once with `mknod`; a later sweep of `/tmp` as root
was refused and not retried. The coordinator checked on 2026-11-04, after the instance had restarted:
`/dev/null`, `/dev/zero` and `/dev/full` are character devices of mode 666 (1,3, 1,5 and 1,7), and
`/dev/null` takes a write from the ordinary user and reads empty. Neither the repository nor Windows was
touched. From pass 20 on, the brief forbids root and system paths as targets.

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

## Pass 10: editor integration (SPEC 7.2)

Paths are on the review tree. `t/x.txt` means `SCRATCH/pass-10/transcripts/x.txt`; the probes are `SCRATCH/pass-10/*.py`, driven by `SCRATCH/pass-10/lspc.py` (the real `ddd.exe lsp` on pipes, a client that holds buffers, sends the `file:///c%3A/...` spelling, applies a workspace edit as an editor does: refuses an overlap and a stale version, opens a file it does not hold, keys what it draws on the normalised uri).

### Scope covered

Read in full, line by line: `src/ddd/lsp/__init__.py`, `protocol.py`, `server.py`, `discovery.py`, `diagnostics.py`, `navigation.py`, `ranges.py`, `edits.py`, `hover.py`, `units.py` (4952 lines); `editors/vscode/package.json`, `src/extension.ts`, `src/config.ts`, `src/config.test.ts`, `src/launch.test.ts`, `README.md`, `.vscodeignore`; `docs/editor_integration.rst` (all); `SPEC.md:2341-2476`; `README.md:140-244`; `src/ddd/editing.py:1-790`, `src/ddd/identity.py`, `src/ddd/value_identity.py`, `src/ddd/cli.py:333-357, 1600-1606`, `src/ddd/models/objects.py` (the keys and rules a fix relies on), `src/ddd/analysis.py:1745-1930`; `docs/superpowers/plans/2026-09-16-review-fixes.md:426-479`, `2026-09-25-gui-mismatch-fix.md:1360-1474`; the previous review's pass 6 in full and its other sections by grep. Of `tests/test_lsp.py` (7395 lines): the class list, `:1-200, 2795-2870, 4920-4980, 7315-7396` and greps for what is pinned; pass 22 owns the rest.

Ran:
- `s01`-`s06`, `s12`-`s14`, `s17`, `s19`, `s22`: edit sequences, multi-file renames, unsaved buffers, files changing under the server, broken files, sub-projects, two images, junctions, odd uris.
- `s07`: all five requests at every token of six examples, 29,990 requests. `s09`: each file of three examples broken six ways, 84 variants, six request kinds, 67,368 requests. `s08`, `s21`: malformed messages, odd buffers and files, 1,500 init and shape variants under a hover.
- `s11`: 87 renames of five kinds onto tricky names with `ddd check` as oracle. `s16`: every quick fix between 338 pairs of declarations, 1,688 actions applied, oracle the loader and the analysis. `s18`: 330 unit plans rendered as text edits against `edit_text`.
- `s15`, `s20`: costs on generated projects up to 36,000 declarations.
- `tests/test_lsp.py tests/test_lsp_decisions.py`: one failure, the known symlink one. The extension's seven tests (`config.test.ts`, `launch.test.ts`), compiled in scratch with `gui/node_modules/.bin/tsc`: pass.

What the client does was read, not run, from local copies: `vscode-languageclient` 9.x as bundled in `llvm-vs-code-extensions.vscode-clangd-0.6.0/out/bundle.js` (the lock pins 9.0.1, the bundle declares `^9.0.1`), and `Microsoft VS Code/261c84cb1e/.../workbench.desktop.main.js`.

Not covered: `extension.ts` was neither compiled nor run (no `node_modules` in `editors/vscode`, and no download), so no session in a real VS Code. No other editor. Nothing on Linux or macOS; a `subst` drive was not re-run, its path is the junction's.

### Strengths

- **An edit lands where it should.** Positions and edits come from the buffer: emoji, tabs, CRLF, a BOM, lines typed above, two fixes in a row unsaved (`t/s17_more.txt`, `t/s02_rename_buffers.txt` W); versions are right; no client refusal for an overlap in 1,688 actions.
- **The unit plans are what they claim.** 330 random plans over random layouts, CRLF included, escapes in the spelling: `text_edits` and `edit_text` gave the same bytes every time (`t/s18_unit_diff.txt`). "An editor and `ddd gui` write the same bytes" holds there.
- **The server survives what a project throws at it, nearly.** 97,358 requests over intact and broken projects, zero deaths in `s07` and `s09`; files nested 200,000 levels deep, NaN, 5,000 digits, invalid utf-8, a directory named like a description: all findings or nothing (`t/s08_robust.txt`). What does kill it is I13 and M1.
- **The refusals it has are right.** A moved declaration refuses a rename; a file that did not load refuses a variable's and a unit's rename; duplicated vocabulary entries are refused (`t/s17_more.txt`). `rename_problem` agreed with the next `ddd check` on every name of `s11` but the raster alphabet (I9) and a constant named as a member (pass 2 M6, seen again).
- **P6-C1 is gone in the shape it was filed.** A project file opened alone shows the whole `ddd check` set, opened before or after a component (`t/s12_previous_critical.txt` 1-2).
- The extension is the launcher it says it is, plus one watcher (M8), and its trust gate is as documented.

### Issues

#### Critical

None. I1 is the same class as last review's Critical, but `ddd check` and the build still fail, so nothing ships. I9 is literally a corrupted file, but on unusual input and it shows at once. I10 is wrong C with every gate green, on a rare trigger. Each is graded Important below with that said; verification may disagree.

#### Important

- **I1. Findings of every other project are withdrawn at each refresh: a file with a real error reads clean until it is saved again.**
  `src/ddd/lsp/server.py:553-555`, `:436-437`. `refresh` publishes `current | self._published` and treats a file absent from this run's report as fixed, while `collect` (`diagnostics.py:254-277`) only looks at the build records and the one document. With no record covering it, a file outside the document's project gets an empty list.
  Triggers and what is on screen:
  - Two projects, no record: open `a` (`missing-producer`), open `b`: `a`'s finding is gone; save `a`: `b`'s is gone. Both errors are in `ddd check` throughout (`t/s01_withdrawn.txt` 1-5).
  - Two loose components: `duplicate-declaration` on `one` vanishes when `two` is opened (`s01` 6-7).
  - Project file not above its components (`project/p.ddd.json`, `components/*.ddd.json`): project open shows 6 findings; opening a component it lists empties the screen, and the hover says "*No component produces this.*" (`t/s12_previous_critical.txt` 3).
  - A watch event with several documents open: each refresh erases the last, so only the last in sort order keeps its findings (`s01` 5).
  - Nothing open, a pull that changes a file and deletes another: all real findings withdrawn and a phantom `file-not-found` published on the deleted file; `ddd check` says `definition-mismatch` (`t/s03_projects.txt` K, K2).
  Contradicts `docs/editor_integration.rst:8-10` "the editor never disagrees with the build" and `SPEC.md:2345-2346`. This is the surviving half of P6-C1's "opening it withdraws them". Change (S): withdraw only files this run reported on, `self._published & set(reports)`, and do not `refresh` a deleted path.

- **I2. The nearest project answers for the whole project: in the repository's own demo a clean tree shows false errors, and a rename breaks it.**
  `src/ddd/lsp/navigation.py:546-549`, whose comment has it backwards: "one further up as well is a sub-project of it" - the nearer one is the sub-project. Stated by `SPEC.md:2391-2394` and `README.md:239`, against `SPEC.md:2345-2346`.
  Trigger: a copy of `examples/demo`, no record, open `subsystems/logging/event_logger.ddd.json`. `ddd check demo.ddd.json` is exit 0; published: three `missing-producer` errors and an `unused-output`. Hover on `ValueE`: "*No component produces this.*". Definition: `[]`. Rename: touches `event_logger.ddd.json` alone, after which `ddd check demo.ddd.json` is exit 1 (`t/s04_demo_subproject.txt`). The sub-project file itself is checked under the top project, its component under the sub-project, in one session (`t/s03_projects.txt` H, H3).
  Change (S-M): walk to the root and answer from the outermost description that includes the document, which also drops a sub-project found first. Cost: the candidates above are already loaded on a miss. The SPEC sentence changes with it.

- **I3. In a two-image project a rename's reach depends on the file it starts from, and started from a reader it half-renames the other image.**
  `src/ddd/lsp/server.py:743`, `:783`: only projects containing the document are visited.
  Trigger: `writer` in images `one` and `two`, `reader_one` and `reader_two`, two records. F2 on `Speed` in `reader_one`: edits `writer` and `reader_one`. `ddd check two` goes from exit 0 to `missing-producer` on `reader_two`. The same rename from `writer` reaches all three (`t/s03_projects.txt` I, I2).
  Read off the same lines: a section's, a raster's and a unit's rename, and "Apply this unit", have this reach. Contradicts `editors/vscode/README.md:94` "rather than half applied" and `README.md:220-224`; this setup is SPEC 7.2's own example of a shared component.
  Change (M): after computing the edits, take every project containing a touched file, repeat until no new one appears, then rename across them or refuse naming the image.

- **I4. A rename sees the disk: what a buffer added is invisible, so it half-renames, merges, or quietly does nothing.**
  `src/ddd/lsp/server.py:740-763`, `navigation.py:885-900`, `units.py:547-566`. The drift check asks only whether each disk site still holds the name.
  - An unsaved new mention keeps the old name: an axis with `"input": "Speed"` typed and unsaved, F2 to `Velocity`, accepted; after the save `unknown-reference` (`t/s02_rename_buffers.txt` D). A new unsaved stating of a unit likewise (`t/s06_units.txt` "unsaved extra stating").
  - F2 on a name only the buffer holds: `prepareRename` opens the box, `rename` answers `{"documentChanges": []}`. This is the second of two renames in a row whenever the first stayed unsaved, and VS Code auto-saves a refactoring only past one file (`u.length>1` in its bulk edit), so every local variable. An empty edit is applied silently (`t.length===0` returns `isApplied:false`). `server.py:720-721` calls this exactly what a refusal exists to prevent (`s02` E). With no subject under the caret and no prepare, the same empty answer (`s02` Y).
  - F2 onto a name only a buffer declares passes `rename_problem`; the result is a `duplicate-declaration`, and with an input in another file it is the silent merge `SPEC.md:2357-2358` refuses (`s02` F).
  `docs/editor_integration.rst:124-128` promises the refusal only for moved declarations, so this is a hole in the guard rather than a broken sentence, except for the empty edit.
  Change (S): refuse while any open document of the project parses to something other than its file on disk, naming it, and turn an empty answer into a refusal.

- **I5. With no project known, F2 on a shared variable rewrites one file and says nothing.**
  `src/ddd/lsp/navigation.py:459-462`, `server.py:743-763`.
  Trigger: `writer` and `reader` in one folder with no project file, or a fresh clone of a collected CMake project before its first configure, or a build directory not named `build`, `out` or `cmake-build-*`. F2 on an `output`: one edit in `writer` (`t/s02_rename_buffers.txt` Q). The only trace is the log line "no ddd-build.json found", which does not mention edits.
  Contradicts `docs/editor_integration.rst:82-83` "across as many files as that takes". Change (S): in the alone case refuse any rename but a `local`'s, saying no project is known.

- **I6. While a file of the project does not load, every caret move in every description raises an error toast, and the reason never reaches it.**
  `src/ddd/lsp/server.py:854-855` answers `textDocument/codeAction` with `REQUEST_FAILED`, and the comment at `:847-849` knows a client asks at every move of the caret. Reproduced: error at every position, in the broken file and the others (`t/s05_quickfix.txt` last block); `examples/layout` with its plugin not importable answers 228 of 228 that way (`t/s07_sweep.txt`), though "stopped the project reading it" is untrue of those files.
  Read off the client: `handleFailedRequest(ui.CodeActionRequest.type,h,w,null)` takes `showNotification` by default, unlike rename's `!1`, and `error()` calls `showErrorMessage("Request textDocument/codeAction failed.", "Go to output")` because `revealOutputChannelOn` defaults to `Error` and `extension.ts:48-55` does not set it. So the user fixing a schema error gets a toast per caret move, naming no file; the sentence the docs promise (`docs/editor_integration.rst:124-128` "naming the file") is in the output channel only.
  `tests/test_lsp.py:4967` pins the error. Change (S): answer `[]` and say it once with `window/logMessage`, or `window/showMessage` when a finding was sent.

- **I7. A quick fix can write a file the loader refuses, often the preferred one, and then the project stops being analysed and every further fix is refused.**
  `src/ddd/lsp/edits.py:541-560` (`settled_at` knows storage and kind, and no rule between keys).
  Reproduced by applying every action: 143 of 1,688 (8.5 %) leave a `schema` error (`t/s16_fix_matrix.txt`). Example: writer `float32`/identity, reader `uint8`/enum: the preferred "Use the datatype declared in w" gives "enum conversion 'Mode_t' requires an integer datatype"; step 1 is then "code action refused" (`t/s05_quickfix.txt` s05b). Likewise "Apply this conversion" onto a float writer, string conversions against a unit, limits, non-byte datatype or missing dimensions, and "Remove this dimensions" on a string.
  Contradicts `src/ddd/models/objects.py:953-955` "what stops it offering an edit that produces a file the loader then refuses". The plan's ruling (`2026-09-25-gui-mismatch-fix.md:1466-1473`) closed only the storage half. `settled_at` is shared with `ddd gui`'s fix; `variables.py:304` guards storage alone, for pass 14 to try there.
  Change (S-M): validate the definition with the key applied before answering `Settled`; withhold otherwise.

- **I8. A named type is read as silence: the preferred fix removes a key, settles nothing, and its title is untrue.**
  `src/ddd/lsp/edits.py:752-754`, `:805-815`, `:845-848`. Raw text is read where the resolved value is meant.
  - Writer `typename: Speed_t` (type states `rpm`), reader `unit: krpm`: only offer is "Remove this unit, which w does not declare", `isPreferred`, carrying the finding; after it `unit: '' != 'rpm'` (`t/s05_quickfix.txt` s05e).
  - Writer `unit: rpm`, reader `typename` stating `krpm`: "Remove the unit from 1 other declaration", preferred, strips the producer; after it `'krpm' != ''` (`t/s13_misc.txt` b). `_remove_elsewhere`'s docstring says this was fixed; the code checks `changes` and not `unsettled`.
  Change (S): read the producer's key through its type, and offer no removal when `settlement.unsettled` holds a type.

- **I9. A raster rename writes the new name raw between the quotes, so a quote or backslash corrupts every file it touches.**
  `src/ddd/lsp/navigation.py:900` `{"range": span, "newText": name}`; `_raster_problem` admits `RASTER_NAME_PATTERN` (`models/common.py:131`, printable ASCII, stated at `docs/editor_integration.rst:107-108`).
  Reproduced: `a"b`: accepted, `json-syntax` in the rasters file and the components, whole project unanalysed. `a\b`: writes a backspace, `schema`. `a\nb`: a line feed, `schema` (`t/s11_rename_oracle.txt`). A stray quote typed in the box is enough. The unit path escapes (`units.py:507`); this one has no read-back. Tests stop at `rename_problem` (`tests/test_lsp.py:2859-2866`). Change (S): `json.dumps(name, ensure_ascii=False)[1:-1]`.

- **I10. Renaming a constant leaves a `condition` spelling it: the object is compiled out with every gate green.**
  `src/ddd/lsp/navigation.py:744-748`; `SPEC.md:2354` "everywhere the project writes it".
  Trigger: `"condition": "CELLS > 2"`, F2 on `CELLS` to `SLOTS`: two edits, the condition untouched (`t/s13_misc.txt` d). `ddd check` exit 0; `gcc -std=c11 -Wall -Wextra -Werror` passes (`docker/compile.sh` has no `-Wundef`); `#if CELLS > 2` is false, so `Big` is gone from the C while the a2l still names it. Reproduced: `SCRATCH/pass-10/p/s13d/gen/ddd_globals.c:21`. The examples' conditions are only `defined(...)`, so the trigger is rare, and the page's Shared files rename uses the same `rename_sites`.
  Change (S): refuse, or rewrite, when a condition holds the identifier as a word.

- **I11. "VS Code shows the multi-file edit in a preview first, so nothing changes without being seen" is false: it is applied and saved at once.**
  `editors/vscode/README.md:87-88`, and the design reason at `src/ddd/lsp/edits.py:8-10`.
  Read off VS Code's workbench: applying a code action passes `showPreview:t?.preview`, set only for the explicit preview gesture; the bulk edit previews only on that or `needsConfirmation`, which the server never sends; and past one file `files.refactoring.autoSave` (default true) saves them all. So "Apply this unit to 2 other declarations" rewrites and saves two other components unseen.
  Change (S): send `changeAnnotations` with `needsConfirmation` on a multi-file fix, which makes the sentence true, or correct both places.

- **I12. A save costs one analysis plus one per open document, every hover a full analysis, and a rename across N files about 2N.**
  `src/ddd/lsp/server.py:436-437`, `:333`, `:338-339`; `src/ddd/lsp/hover.py:99`. The extension's watcher fires on the editor's own saves, so every save is a `didSave` and a watch event.
  Measured (`t/s15_perf.txt`, `t/s20_perf2.txt`):
  - 6,000 declarations, ten tabs: `didSave` 0.58 s, its watch event 5.91 s.
  - 36,000 declarations, five tabs: `didSave` 3.98 s, watch event 20.13 s; every hover 1.91 s, the first 4.02 s.
  - Rename as VS Code applies it, 61 files: 60 `didOpen` 11.06 s, 61 `didSave` 14.26 s. 201 files: 411 s with the watch batch arriving while the models are open.
  The loop is single threaded, so hovers and renames queue behind it. These are the sizes `tools/bench_gui.py` holds the page to; nothing holds the server.
  Change (S): analyse once per distinct project in a refresh, coalesce queued `didOpen`/`didSave`, keep the resolved dictionary until `_forget`.

- **I13. A hover or a hand-made record ends the session, because there is no net by decision.**
  `src/ddd/lsp/server.py:8-12` ("a thing the design already prevents"), `:265-277`; `hover.py:81-82`, `:60-63`; `server.py:380`.
  - A parameter with `"init": []`: `ddd check` gives one `init-invalid`, a hover gives exit 2 `ddd: range() arg 3 must not be zero` (`t/s21b_init_empty.txt`, 27 cases in `t/s21_hover_inits.txt`).
  - A valid project (`ddd check` exit 0), float64 block with init `[-1.7e308, 1.7e308, 0]`: a hover gives exit 2 `ddd: cannot convert float NaN to integer` (`t/s10_hover_truth.txt`).
  - A record with a relative `project` and an unknown plugin check: exit 2 on the first `didOpen`, `relative path can't be expressed as a file URI` (`t/s13_misc.txt` g); `_uri` calls `as_uri()` even when the client's spelling exists, and a relative record is otherwise accepted.
  The client restarts the server and gives up after five crashes in three minutes, taking every finding with it, and the hover is what kills it again.
  Change (S): wrap each request, answer `-32603`, write the trace to stderr, keep the session. That hides nothing the docstring fears; fix the three triggers besides. Also see the open question.

#### Minor

- **M1. The server dies on malformed params that `_field` says it refuses.** `src/ddd/lsp/server.py:147` "Every field a handler reads goes through here", against `:846-850` (`diagnostics: null`, `3`, `[1]`), `:325` and `:866-879` (`params: [1]`, `rootUri: 3`, `workspaceFolders: 3`), `ranges.py:165-166` (`line: -1000`, `IndexError`), and `%00` in a uri (`ddd: embedded null character`). All exit with a traceback or exit 2 (`t/s08_robust.txt`). Against `SPEC.md:2450-2452`. VS Code sends none of them; P6-M1 and P6-M2's neighbours.
- **M2. A quick fix under a moved buffer is performed in part, where the SPEC says refused whole.** `SPEC.md:2364-2367`, `README.md:220-222`, `docs/editor_integration.rst:124-127`; `src/ddd/lsp/edits.py:877-898` leaves it out. Trigger: V moved in `r2`'s buffer; at the writer "Apply this unit to 1 other declaration" touching `r1` alone, while the rename beside it is refused (`t/s13_misc.txt` a). The count in the title is honest; the documents or the code should change.
- **M3. In two images every action is offered twice.** `src/ddd/lsp/server.py:852-859`, no `_gather` here. `["Use the unit declared in writer", "Apply this unit...", "Use the unit declared in writer", "Apply this unit..."]`, both preferred (`t/s03_projects.txt` I3).
- **M4. The hover says things the project does not.** `src/ddd/lsp/hover.py:97-103`, `:315-320`. Writer in two images: "read by **ReaderOne**" while references lists `reader_two` too. Reader's file did not load: "read by *nobody*". Writer's file did not load: "*No component produces this.*", definition `[]`. Two writers: "Written by **W1**" (`t/s19_small.txt`, `t/s10_hover_truth.txt`). The remainder of P6-I3; one line naming what did not load would do.
- **M5. Two leftovers of the client's spelling.** `src/ddd/lsp/server.py:378-380`, `:553-555`: through a junction, a file published under its resolved uri and later opened under the junction keeps the old set on screen for good: fixed and saved, `real/r.ddd.json` still holds 2 findings (`t/s14_spelling.txt`). `src/ddd/lsp/edits.py:339` with `server.py:840`: `here` keeps the unresolved path, so it equals no index site: "Remove this unit" is lost at the producer, and the order is computed as a consumer's (`s14` "w's Only"). `path.resolve()` there, and withdraw under the old spelling.
- **M6. A squiggle lands on the wrong key of a dirty buffer.** `src/ddd/lsp/diagnostics.py:251`, `:362`: ranges are the disk's. Five lines typed above, unsaved, then another file saved: `r`'s finding at line 7, which in the buffer is `"name": "R"` (`t/s13_misc.txt` e). Also a restored dirty buffer at `didOpen`. `SPEC.md:2423` says the findings are the disk's, not that they may be drawn elsewhere.
- **M7. `onLanguage:json` starts the server for any json file.** `editors/vscode/package.json:35`: `ddd lsp` runs in every workspace where a json file opens, and with `ddd` missing the error popup appears there. P6-M8's second half, still open.
- **M8. The watcher is the extension's, so other editors go stale, and the record is not watched.** `editors/vscode/src/extension.ts:54`; the server never sends `client/registerCapability`. `README.md:153-154` "works the same either way" and `SPEC.md:2470-2472` "shall do no more than launch": Neovim, Helix and Emacs get no branch-switch refresh and a stale index under a rename (`t/s02_rename_buffers.txt` F2). `**/*.ddd.json` also misses `ddd-build.json`: a configure that writes only the record leaves the old severities until the next save (`t/s19_small.txt`). Register the watcher from the server, including the record. A change of `ddd.buildDirectories` needs a restart, which nothing says.
- **M9. An external type can be renamed.** `src/ddd/lsp/navigation.py:706-707`. `DriverStatus_t` in `examples/structures`: accepted, `ddd check` exit 0, the vendor's header still defines the old name (`t/s13_misc.txt` c). The name is not DDD's to choose; the compiler stops the build.
- **M10. Folders added later are not followed.** `src/ddd/lsp/server.py:885-900` announces no `workspaceFolders`; a document in a folder added after `initialize` gets `missing-id` only, against `missing-producer` and `unused-output`, with no new log line (`t/s03_projects.txt` M). A relative `-b` is read in the first folder alone (the client's `_mainGetRootPath`), where `docs/editor_integration.rst:172-173` says "the workspace folder".
- **M11. Rendering a unit plan is quadratic, and it runs on a caret move.** `src/ddd/lsp/units.py:569-583` rescans per operation, and commit `3ddc8115` fixed the engine's path, not this one. Rename, one file: 500 statings 5.34 s, 2,000 103.57 s, 8,000 no answer in 300 s (`t/s15_perf.txt`). `edits.py:445-446` renders every candidate eagerly: 16.87 s per code action on an unknown unit stated 500 times (`t/s20_perf2.txt`). `codeAction/resolve` would defer it.
- **M12. Small untrue sentences.** "r.ddd.json has unsaved changes that moved a declaration" for a closed file changed on disk before the watch event (`server.py:830`, `t/s22_stale.txt`). Every action of a declaration carries all its mismatch findings, though one key settles one (`edits.py:265-269`, against the docstring at `:112-116`; `t/s05_quickfix.txt` s05d). "the full range of the datatype" on a `uint8` enum reading `0 .. 1` (`hover.py:328-332`). `docs/editor_integration.rst:119` "only while a file ... does not load" omits the moved unit's refusal, and `:124` omits a raster. A fix into a closed CRLF file carries `\n` (`ranges.py:276` reads through universal newlines, `editing.py:126`); VS Code normalises, another client mixes (`t/s17_more.txt`).

Seen again, not re-filed: pass 2 M6 (`t/s11_rename_oracle.txt`, constant to `field`, then `name-collision`), I1, I2, M10; pass 3 I2; pass 4 M10, M11; pass 9 M2.

### Status of the 2026-09-15 findings in this area

Only those not plainly fixed. Fixed and checked: P6-I2 (`navigation.py:541`), I4 (`discovery.py:108-112`), I5 (`navigation.py:60-62`), I6 (`diagnostics.py:304-316`), M3, M4, M5, M6, M7, M9, M10, M11, M12, M14, M15, M16; P8-I1 (`ranges.py:108`).

| id | finding | status | where |
| --- | --- | --- | --- |
| P6-C1 | project file opened with no record: checks silenced, and withdrawn from the components | FIXED as filed (`diagnostics.py:149-151`, `t/s12_previous_critical.txt` 1-2); the withdrawal STILL OPEN in other shapes | I1, I2 |
| P6-I1 | published under the resolved path | FIXED for what is open (`server.py:378-384`); a leftover | M5 |
| P6-I3 | rename and fix computed around a file that did not load | FIXED for rename and fix (`server.py:744`, `:854`), though the refusal reaches a user as I6; the hover's half STILL OPEN | I6, M4 |
| P6-M1 | `codeAction` with `context: null` ends the server | FIXED for `context`; `diagnostics: null` on the next line STILL ends it | M1 |
| P6-M2 | a folder entry without `uri` ends the server | FIXED for that; `rootUri: 3`, `workspaceFolders: 3` STILL end it | M1 |
| P6-M8 | watcher dropped; `onLanguage:json` | watcher FIXED (`server.py:340`); `onLanguage:json` STILL OPEN | M7 |
| P6-M13 | work repeated per save and first request | the double read FIXED (`diagnostics.py:161-177`); a new repetition, per open document | I12 |

### Open questions

1. **A net or no net?** `server.py:8-12` rejects a catch-all because it "would hide" a defect. A guard that answers `-32603` and writes the trace to stderr hides nothing and keeps the reader's findings; three project-side triggers show the premise does not hold. If the answer stays no, the document should say a defect ends the session, and the extension's error handler should say which.
2. **What does a rename mean across images?** Extend to every project holding a touched file, or refuse naming the image? Extending writes files of an image nobody asked about; refusing makes a rename in a shared component impossible from a reader. Decides I3.
3. **Nearest or outermost project?** SPEC says nearest (`SPEC.md:2393`). Outermost fixes I2 but answers with the widest project where a sub-project is sometimes built alone. A record still wins either way.
4. **Should a dirty project refuse edits outright?** "Any open document differing from disk" (I4) is simple and sound, but refuses a rename whenever any tab has an unsaved typo. Indexing from buffers avoids that and is a larger change, since the loader reads files (L).
5. **Should a multi-file quick fix ask?** `needsConfirmation` makes the README true at one extra click on every fix; correcting the README keeps the one press. Decides I11.
6. **Is the watcher a launcher's job?** If the server registers it, SPEC's "shall do no more" holds and other editors gain it, at the cost of a capability the client must support (M8).

### Test gaps

- A second project, a loose file, a project not above its components: what is withdrawn. `tests/test_lsp.py:4363` has only the project-file order; all of I1's triggers are untested. So is `_watched` with two open documents of two projects, and with a deleted path.
- A nested project with no record (I2): nothing runs `examples/demo`'s sub-project through the server, though the sweep over it would have shown the false errors.
- A rename from a non-shared file in two images (I3): `tests/test_lsp.py:5075` pins only that two images do not send one edit twice.
- An unsaved addition, a second rename, a rename onto a buffer's name (I4). A rename with no project (I5).
- `test_a_quick_fix_is_refused_while_a_file_of_the_project_did_not_load` asserts the error the client turns into a toast (I6): the test pins the defect.
- Fixes are tested for titles and single cases; no test applies the whole offer over varied declarations and loads the result. `s16` is under 200 lines and found 143 file-breaking actions (I7, I8); something of that shape in the suite would hold `settled_at`.
- Raster names are tested through `rename_problem` only (`tests/test_lsp.py:2795-2866`); no test applies an edit carrying a character json must escape (I9).
- Hover over `init: []` and over ±1e308 (I13); 100 % coverage of `rows` and `sparkline` did not reach either.
- Nothing bounds the server's cost (I12, M11): no count of analyses per save, no budget like the page's.
- `extension.ts` has no test, `launch.test.ts` still opens no document (carried), and nothing tests the client's reaction to an error answer.

### Assessment

The mechanics are good and getting them right was real work: an edit lands exactly where it should, in every encoding and line ending tried, the unit plans match the engine byte for byte, the server survived nearly 100,000 requests over broken projects, and last review's Critical is gone as filed. What is wrong is one level up, in what the server believes it knows. It assumes one project at a time, so opening a file elsewhere withdraws true findings. It trusts the nearest description, so the repository's own demo shows false errors in the editor, and a rename there breaks a clean project. It computes a rename from the disk and the document's own project, so the result depends on where you pressed F2 and on what you have not saved. And its quick fixes check two rules of the loader where the loader has more, so one in twelve in a deliberately hard matrix breaks the file and shuts off the very fixes that would repair it. Several of these are stated as design in the SPEC, which is why the tests and the documents agree with them; the sentence they contradict is the SPEC's own first paragraph about an editor that disagrees with the build. Most fixes are small, and I would start with I1, I6 and I9, which are a few lines each, then I2 and I13. I would not yet call F2 safe outside a single-image project with everything saved.

```candidates
10|I1|src/ddd/lsp/server.py:553|Findings of every other project are withdrawn at each refresh: open or save elsewhere and a real error reads clean; a deleted file gets a phantom file-not-found
10|I2|src/ddd/lsp/navigation.py:547|The nearest project answers for the whole: examples/demo's event_logger shows 3 false missing-producer, hover says no producer, a rename breaks a clean project
10|I3|src/ddd/lsp/server.py:743|In two images a rename from a reader rewrites the shared writer and leaves the other image's reader; the reach depends on where F2 was pressed
10|I4|src/ddd/lsp/server.py:740|A rename sees the disk: an unsaved mention keeps the old name, a name only a buffer holds gets an empty edit, a name only a buffer declares is merged onto
10|I5|src/ddd/lsp/navigation.py:459|With no project known, F2 on a shared variable rewrites one file and says nothing
10|I6|src/ddd/lsp/server.py:854|While a file does not load every caret move answers an error, which vscode-languageclient shows as a toast naming no file; the reason is only in the output channel
10|I7|src/ddd/lsp/edits.py:541|143 of 1,688 quick fixes write a file the loader refuses, preferred ones included, and then every further fix is refused
10|I8|src/ddd/lsp/edits.py:752|A named type reads as silence: the preferred fix removes a unit, settles nothing, and says the writer does not declare it
10|I9|src/ddd/lsp/navigation.py:900|A raster rename writes the name raw: a quote or backslash the alphabet admits corrupts every file it touches
10|I10|src/ddd/lsp/navigation.py:744|Renaming a constant leaves a condition spelling it: the object is compiled out with check and gcc -Werror green
10|I11|editors/vscode/README.md:87|VS Code shows the multi-file edit in a preview first is false: it is applied and auto-saved at once, and edits.py rests its design on it
10|I12|src/ddd/lsp/server.py:436|A save costs 1+N analyses, every hover one, a rename across N files about 2N: 24 s per save with five tabs at 36,000 declarations, 25 s for a 61 file rename
10|I13|src/ddd/lsp/hover.py:81|A hover on init [] or on float64 at 1e308 ends the session, as does a relative record, because the server has no net by decision
10|M1|src/ddd/lsp/server.py:850|Malformed params the _field docstring says are refused end the server: diagnostics null, rootUri 3, negative line, %00 in a uri
10|M2|src/ddd/lsp/edits.py:877|A quick fix under a moved buffer is performed in part where SPEC says refused whole
10|M3|src/ddd/lsp/server.py:852|In two images every quick fix is offered twice, both preferred
10|M4|src/ddd/lsp/hover.py:97|The hover answers from the first project and from what loaded: read by nobody, no component produces this, one writer of two (remainder of P6-I3)
10|M5|src/ddd/lsp/server.py:380|Through a junction a file published resolved and then opened keeps stale findings for good; here keeps the unresolved path and loses an action
10|M6|src/ddd/lsp/diagnostics.py:362|Ranges are the disk's, so a squiggle lands on the wrong key of a dirty buffer when another file is saved
10|M7|editors/vscode/package.json:35|onLanguage:json starts the server for any json file and pops the error where ddd is missing (P6-M8)
10|M8|editors/vscode/src/extension.ts:54|The watcher is the extension's, so other editors go stale against works the same either way; ddd-build.json is unwatched; a settings change needs an unstated restart
10|M9|src/ddd/lsp/navigation.py:706|An external type can be renamed though a header defines the name
10|M10|src/ddd/lsp/server.py:885|Workspace folders added later are not followed and get the thin answer in silence; a relative -b reads the first folder alone
10|M11|src/ddd/lsp/units.py:569|Rendering a unit plan is quadratic and runs on a caret move: 104 s at 2,000 statings, 17 s per code action at 500
10|M12|src/ddd/lsp/server.py:830|Small untrue sentences: unsaved changes on a closed file, every action claiming all findings, full range of the datatype on an enum, only while in the docs, LF into a closed CRLF file
```

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

## Pass 12: the web GUI, security of the local server

**The threat model, first.** It is stated, in one place, and plainly: `docs/gui_security.rst` has *What it defends against* (`:9-121`: another page in the same browser, another server on another port, any local process or user without the token, malformed input, `localhost`), *What it trusts* (`:123-150`: the project and its plugins, a baseline and its plugins, the start directory, whoever holds the token, the page's own origin) and *What it does not defend against* (`:195-248`: a local denial of service, the moment of launch, a server earlier on the same port, beyond loopback, transport). `SECURITY.md` points at it, and specs `2026-10-05 §1, §10` and `2026-10-07 §1, §3` are where it was decided.

**Is it the right one?** Its adversaries are the right ones, and against them the server holds up unusually well (*Strengths*). Four things are wrong with the model as written, and they matter more than any single bug below:

1. **It never says what the token is worth.** Spec `2026-10-07 §1` says it in one sentence, "The token is code execution as the reader", and the page never does. I proved it (I2). Everything the page says about losing the token reads differently once you know.
2. **"Trusted" is wider than a reader will take it.** *The project the reader opens* suggests a decision. A file merely present under the start directory acts on the start page's first request, before anything is opened (I4). A baseline is, by the tool's own concept, something handed over by somebody; the page trusts its python if it is a description, and the Compare form does not say so (M6, adding to pass 1 I15). For build verbs this is the bargain `make` strikes. For a viewer with a one-click project list it is a choice nobody has yet been asked to make.
3. **A same-user process is outside the model, and the page does not say so.** "Any other local process or user that reaches the port without the token" reads as if it covered malware of the same user, which can read the terminal or the browser's profile. That is the only sensible scope. It should be stated.
4. **The confinement machinery has no adversary in the model.** The token holder is trusted and so is the project, so `Serving`, `_under`, `_served` and the device rules on request paths defend against nobody the page names. They are robustness against a page's own mistake, and docstrings claim more (M2). Spec `2026-10-05 §10` also puts the page's own code out of scope while *What it trusts* rests on it: I reviewed it here and it holds, but nothing pins that (*Test gaps*).

### Scope covered

**Read in full:** `src/ddd/gui/server.py`, `routes.py`, `queries.py`, `depth.py`, `session.py`, `compare.py`; `SECURITY.md`; `docs/gui_security.rst`; specs `2026-10-05-gui-security-design.md`, `2026-10-07-gui-token-out-of-cookie-design.md`; plans `2026-10-05-gui-security.md:1340-1511` and `2026-10-07-gui-token-out-of-cookie.md:1440-1548` (figures, *What was left open*, rulings), `2026-10-07-gui-journeys-every-platform.md:1231-1307` (`2026-10-21-gui-journeys-remaining.md`'s left-open section searched for security items: none); `tests/test_gui_hostile.py`; `src/ddd/file_names.py:1-80`, `src/ddd/lsp/discovery.py`, `src/ddd/build_info.py:1-110`, `src/ddd/plugins.py:150-300`; on the page `gui/src/api/signIn.ts`, `token.ts`, `client.ts:1-180`, `main.tsx`, `app/App.tsx`, `app/useRoute.ts`, `lib/route.ts`, `gui/index.html`, `gui/e2e/localhost.spec.ts`, `hostile.spec.ts:1-50`.
**In part:** `src/ddd/gui/api.py:1-800, 1240-1300, 1455-1500, 2150-2486` (every path-taking route and the route table; passes 13 and 14 own the rest); `contract.py` request models; `tests/test_gui_server.py`: every test name, and `:766-830, 979-1058, 2200-2449, 2920-2968, 3215-3342`; `tests/test_gui_api.py:1905-2004`.

**Run (all against a real `ddd gui` I started on loopback, on my own probe copies; transcripts under `SCRATCH/pass-12/transcripts/`, scripts one level up):**
- `p01_gate`: tokens, 15 hostile `Host` forms, `Sec-Fetch-Site` and `Origin` combinations, `POST /open`, methods, headers on every kind of answer.
- `p02_confinement`, `p03_reach`, `p14_paths_and_holds`, `p18_short`: 62 path spellings (`..`, junction, drive-relative, UNC in six spellings, `\\?\`, `\\.\`, `\??\`, trailing dots and spaces, alternate streams, device names, case) against `file`, `findings`, `declarable`, `fix`, `declaration-plan`, `files-plan` add and remove, `open` and `edit`; 25 against `compare`, on a project that resolves; 8.3 names apart; 73 on page paths.
- `p04_limits`, `p10*`: the cap, idle and slow connections, sizes, chunked, abandoned long polls, reload loops in Edge.
- `p05_ports`, `p06_dual`, `p15_more`, `p19_first`: strangers on the port, the IPv6 hold, `--port 80`, `--host`.
- `p07_*`: six hostile projects through a real Edge: 492 route visits and 522 presses, recording script runs, injected elements, CSP violations, off-site requests, crashes; screenshots in `SCRATCH/pass-12/shots/`.
- `p08_hostile_server`: 23 hostile file sets against every no-argument and file route. `p16_records`: hostile build records.
- `p09_browser`: a signed-in Edge attacked from a page on another port. `p11_launch`: a stub browser, the code, its race and expiry. `p17_csp`: the policy tried by hand.
- `p12_fuzz`: 8,800 GETs and 2,500 edit bodies over HTTP. `p13_routes`: the page's route table against a plugin noting every call, and the tree hashed around each route.
- `tests/test_gui_hostile.py` (passes here). `npm audit`. `gh api repos/Sauci/ddd/private-vulnerability-reporting`.

**Not covered:** Linux and macOS (so the `/proc` half of the launch race and the Linux hold are not measured); Chrome, Firefox, Safari (Edge only; no old browser); WSL 2, a mapped drive; a file symlink (no privilege here; junctions yes). **I did not bind beyond loopback**: my instructions are a loopback server, and a real `0.0.0.0` on this enterprise machine exposes it and may raise a firewall dialog (the suite's own comment, `tests/test_gui_server.py:2930`). `run` was driven with the socket on loopback (`p11`), and since nothing reads a client's address, the forged `Host` and `Origin` probes stand in for a remote client. I named no SMB host but `127.0.0.1`, so the network reach in I4 is shown on loopback only. `pip-audit` is not installed and I did not add it. `eval` under the policy could not be judged: CDP's evaluate exempts itself.

### Strengths

- **Nothing about the project is reachable without the token.** Every API request without it answers `401`, token as cookie, in the query or as Basic included; the scheme is case-insensitive, one space, compared in constant time (`p01`). `POST /open` takes a code or the token and nothing else; duplicates, lists, a surrogate, `NaN` and 1,025 bytes are all refused.
- **DNS rebinding:** 15 hostile `Host` forms answer `421`, and a real Edge at `http://foo.localhost:<port>/` reads "misdirected request" (`p01`, `p09`).
- **The gate, in a real browser.** From a page on another port of `127.0.0.1`, in the signed-in Edge: `fetch` rejected or opaque, `Authorization` dies in its preflight, image, script and sheet fail, both iframes blocked, a form post and a websocket refused, the opened window's `location` and `localStorage` are `SecurityError`, and navigating it lands on the sign-in page. The baseline plugin's marker never appeared, the project was untouched, the hostile server received no token, the browser holds no cookie (`p09`).
- **Arriving asks nothing (P18b-10 is closed).** A typed address, and a typed address of another site that redirects, land signed in on a Files row with only `/api/session`, `/api/state`, `/api/files` asked, no `files-plan`; a link pressed on the hostile page lands on the sign-in page (`p09`).
- **The launch.** The opener is handed a code alone; a `GET` spends nothing; a wrong code leaves it; code and token are not interchangeable; second presentation `403` with the terminal line; expiry at 60 s silent (`p11`).
- **The policy is a real second layer.** The inline script's hash is right: the module aborted once is asked again and the page draws, with no violation in 492 visits. Injected by hand, inline handlers, `javascript:`, inline, `data:`, `blob:` and foreign scripts, inline styles, foreign `fetch`, sheet and worker are all refused (`p17`).
- **A hostile file reaches the page as text.** `gui/src` has no raw-HTML sink and every `href` starts with `/` by construction (`lib/route.ts:93-131`). Payloads as description, unit, component and object names, finding text and note (through a plugin), file names, an undo label, a hostile dictionary compared, and the address itself: no script ran, no element was made, no request left the origin, nothing crashed, in any of the six projects (`p07_*`, `shots/clean/090.png`). Wrong-shaped json (`"interface": "x"`, `{"component": []}`, `5`) and names `constructor`, `toString`, `__proto__` draw normally. The one off-site address on any page is React Flow's attribution link.
- **Path confinement holds for what a request names.** Nothing outside what is served was read or written by any spelling on any route; the network and device spellings are refused before anything resolves them; `\??\` is normalised by python and touches no network; inside spellings land on the one file (`p02`, `p03`, `p14`, `p18`). Page paths serve nothing outside the pages (`p14`).
- **Malformed input.** 11,300 hostile requests: two `500`s (M1), no hang, no file written by a GET, no edit that left a file unparseable, raw `ESC` never on the terminal (`p12`). 23 hostile file sets (surrogates, `1e400`, `NaN`, a million open brackets, a 40 MB string, 200,000 keys, binary, UTF-16, device names and a pipe as includes) answered no `500` and printed nothing on the terminal (`p08`).
- **The cap protects the machine.** 64 connections held: 72 threads, the 65th `503`; no slot leak after 500 connect-and-closes or abandoned long polls; idle connections closed at 30 s (`p04`, `p10b`).
- **The route table is true.** It names all 36 routes, and measured against a noting plugin only `compare` and `files-plan` ran hooks (`p13`).
- **Reporting works:** private vulnerability reporting is on (`{"enabled":true}`), as `SECURITY.md` says. Shipped dependencies audit clean (`npm audit --omit=dev`: 0).
- **Left-open items now measured and fine:** a fixed `--port` restarted at once on Windows with a client still connected works (P19a-31, `p05`); 400 parallel connects past the backlog of 5 all connected (`p04`).

### Issues

#### Critical

None. I1 is the nearest: read literally, "a security hole in the local server" would make it Critical. I grade it Important because it needs a second local principal **and** a reader who opens `localhost` rather than the printed address. If you read the definition strictly, promote it.

#### Important

- **I1. On Windows the IPv6 hold does not keep a dual-stack listener off `localhost`: a program on `[::]` with `IPV6_V6ONLY=0` binds beside it and receives `localhost:<port>/open?token=...`.** `src/ddd/gui/server.py:27-31, 128-138, 331-374`; contradicts `docs/gui_security.rst:112-117` ("So no other program can listen on `localhost` at that port ... rather than reaching a stranger there") and `:118-121` (a held port is refused before `ddd gui` starts).
  *Trigger:* `ddd gui` running on port P; a stranger does `socket(AF_INET6)`, `IPV6_V6ONLY=0`, `bind(("::", P))`, `listen()`. Expected: refused. Observed: **bound**, with or without `SO_REUSEADDR`; the other 16 of 18 combinations are refused. `[::1]:P` then reaches the stranger, `127.0.0.1:P` still reaches `ddd gui`. Edge opening `http://localhost:P/open?token=PROBE-TOKEN-FROM-EDGE` is answered the stranger's page, and the stranger logs the token. No socket options are needed: a plain Node `http.createServer().listen(P)` binds `::` dual-stack by default and does it. Stranger first, on a fixed port: `ddd gui --port Q` starts without a word.
  *Evidence:* reproduced, `p06_dual.txt`, `p15_more.txt`.
  *Why the suite missed it:* its stranger always sets `V6ONLY=1` (`tests/test_gui_server.py:3225, 3256`) and the journey only tries `listen(port, "::1")` (`gui/e2e/localhost.spec.ts:5-11, 23`). The runs the docstrings cite are of that stranger.
  *Consequence:* the token, which is code execution (I2), to any program listening on the port, for a reader who rewrote the address. The printed `127.0.0.1` address stays safe.
  *Change (S-M):* listen on the hold and serve it. Measured (`p14`, `p19_first.txt`): with `[::1]` or `[::]` exclusive **and listening**, `[::1]` reaches the hold, stranger first or second; a dual-stack hold is refused beside our own IPv4. `localhost` is then `ddd gui` itself, signed out until the address is opened, and the page's section gets shorter. Not measured on Linux.

- **I2. The token is code execution as the reader, and neither the security page nor the terminal says so.** `docs/gui_security.rst:135-138` ("It is the key"), `:214-215` (the race's winner "is signed in with the token"), `src/ddd/gui/server.py:1034-1040` ("what keeps others out"); `src/ddd/plugins.py:172-174`; spec `2026-10-07 §1` has the sentence the page lacks.
  *Trigger:* with the token, `POST /api/edit` setting `project.plugins` to `["<outside>/evil_plugin.py"]`, label "harmless" -> `200`, and the next analysis imports it from outside what is served: the marker reads "ran from outside what is served" (`p03_reach.txt`). `GET /api/file` of that plugin stays `404`. The same token can create a file of any name beside the project, `fresh.py`, `fresh.bat` (`p02_confinement.txt`), against `src/ddd/gui/session.py:478-480` "only the kind of file adopting a vocabulary writes".
  *Consequence:* a reader cannot weigh screen-sharing the terminal, pasting the address in a ticket, publishing a container's port, or ignoring the terminal's one line, because the page calls the loss "signed in". Nor does it say that a same-user process is out of scope.
  *Change (S):* two sentences at `:135`, one in the `--host` warning. Open question 2 is how to make it less true.

- **I3. KNOWN (plans `2026-10-05` P18-8/P18-9, `2026-10-07` *What was left open*): the launch-code race hands whoever wins code execution for the whole run.** `src/ddd/gui/server.py:446-475, 935-949`, documented at `docs/gui_security.rst:208-224`.
  *Trigger:* a local process reads the code from the opener's command line and posts it first -> `200` with the token; the reader's own post `403`; the terminal prints one line. *Evidence:* the server's half reproduced with a stub browser, the racer's bearer working (`p11_launch.txt`); reading another user's command line not run (Windows here; `/proc` on Linux and `ps` on macOS by reading).
  Documented and accepted as a residual, but its weight rests on I2, the sign is one line after the fact, and the innocent cause prints the same line (P19a-9). On a shared Linux box this is a colleague's shell. Open question 3.

- **I4. A file merely present under the start directory acts on the start page's first request, before anything is opened: a network path is read, the console is opened, the page hangs or answers `500`.** `src/ddd/gui/session.py:249, 256, 971-975`, reached by `GET /api/projects` and by `POST /api/open` (`src/ddd/gui/api.py:352`); `src/ddd/build_info.py:58-63` says the path is absolute and nothing holds it to that.
  *Trigger:* `build/ddd-build.json` holding `{"format":1,"project":<X>}`, `ddd gui` with no project, the page's first ask:
  - `\\127.0.0.1\C$\...\far.ddd.json` -> `200`, offered as `//127.0.0.1/C$/...` **with its name `FarAway` read over SMB**; pressing it is then `400 open takes a project's path`.
  - `CON` or `CONIN$` -> no answer in 40 s, against `gui_security.rst:49` "no request this server reads in full is left hanging". Every open from the page goes through the same function.
  - `a\u0000b` -> `500`, a traceback on the terminal.
  - `C:/Windows/win.ini`, `C:/Windows`, `""` -> read and offered as projects.
  *Evidence:* reproduced, `p16_records.txt`. Only loopback's SMB named; on Windows a path to another host asks the system to authenticate there with the reader's credentials, which I did not try.
  *Contradiction:* `src/ddd/gui/queries.py:69-72` and `gui_security.rst:60-63` refuse these very spellings in a request "before anything resolves it", because Windows would open them. A file gets them unasked.
  *Why it matters:* the start page is the natural way to look at a clone before trusting it, and it is the one step `gui_security.rst:126` ("the project the reader opens") does not cover. `:132` trusts the directory, so this is inside the model as written, which is why it is not graded higher; open question 1.
  *Change (S):* read a record's `project` by `file_path`'s rule, `_read_json` catching `ValueError` as `_described` does, and read nothing not named `*.ddd.json`.

#### Minor

- **M1. `GET /api/compare?baseline=%00` answers `500` on Windows.** `src/ddd/gui/compare.py:383-389`, which catches `OSError` while `open` raises `ValueError: embedded null character`; `resolve()` no longer raises there. Contradicts `docs/gui_security.rst:47-56` (a NUL refused `400`, `404` or `409`) and `src/ddd/gui/queries.py:20-21`. Reproduced, `p12_fuzz.txt` (both `\x00` and `a\x00b`, the only `500`s in 11,300). The hostile walk passes because it runs with the working directory elsewhere (*Test gaps*): `p15_more.txt` shows the same call `400` with cwd elsewhere and raising with cwd the root, as `run` always has it. S.

- **M2. `served` is no boundary, and docstrings say it is.** `src/ddd/gui/session.py:154-166, 579-581`, `src/ddd/gui/compare.py:333-336`, `tests/test_gui_api.py:1935`. With an outside file added to the includes by `POST /api/edit`, `GET /api/file` is `404`, but `/api/dictionary`, `/api/types`, `/api/type`, `/api/units`, `/api/unit`, `/api/variable`, `/api/values`, `/api/graph` answer its descriptions, units and init, and a json that is no description has its **values** quoted by findings: `OUTSIDE-PASSWORD-VALUE` (`p14_paths_and_holds.txt`). A build record naming a project elsewhere widens `served` to its directory, and an edit then writes there (`p03_reach.txt`). Against "These cannot be widened that way", "its contents are neither read, written, nor shown", "`POST /api/edit` writes description files of the open project and nothing else". No power beyond I2, hence Minor; `docs/gui_security.rst:132` is accurate. Say what the guard is for (S), or open question 2.

- **M3. A long poll whose client has gone keeps its slot for its 25 s, so one tab reloading reaches the cap.** `src/ddd/gui/api.py:378`, `src/ddd/gui/session.py:379-384`; contradicts `docs/gui_security.rst:204-206` ("A browser never comes near that limit by itself"), `src/ddd/gui/server.py:109-110`, spec `2026-10-05 §6, §8`. 64 long polls with every client gone: 70 threads (`p10b_slots.txt`), `503` for the next 23.4 s (`p10c_slots.txt`). Edge, one tab, reloading twice a second: the page reads "answering as many connections" after 31 reloads in 17.5 s; as fast as it can, 34 reloads in 1.7 s; once a second, not in 29 reloads (`p10d_reload.txt`). The page then shows that banner and asks nothing again until reloaded. The `503` itself is sometimes lost to a reset (`ConnectionAbortedError` in `p04_limits.txt`, `p10c`; `_refuse`'s docstring knows the race), and the page then says "not answering". Wait in slices and notice a closed client, or correct the sentence. S.

- **M4. `ddd gui --port 80` prints an address no browser can use.** `src/ddd/gui/server.py:630, 739`. A browser sends `Host: 127.0.0.1` for port 80, answered `421`; only `Host: 127.0.0.1:80`, which no browser sends, is `200` (`p05_ports.txt`, by that `Host`, not in a browser). S.

- **M5. An empty `--host` is not loopback.** `src/ddd/gui/server.py:973`. `getaddrinfo("", ...)` answers this computer's first network address, here `10.27.230.65`; `--host "$UNSET"` is refused only for want of a port, and with `--port` would bind that interface (`p05_ports.txt`; refused path run, bind not run). Adds to pass 9 M8. S.

- **M6. The two clicks that run a project's python say nothing (adds to pass 1 I15).** `gui/src/screens/StartPage.tsx:18-19`, `gui/src/components/CompareView.tsx:83`. Opening from the list imports its plugin; `GET /api/compare?baseline=base/base.ddd.json` imports the *baseline's* plugin; `ddd gui PROJECT` imports before any browser connects (`p15_more.txt`, `p13_routes.txt`). The form says "Accepts a dumped dictionary, or a project or component description" and no more, though only one of those runs code. One sentence on each. S.

- **M7. KNOWN (plan `2026-10-05`): the standard library's answers carry none of the security headers.** `src/ddd/gui/server.py:265-271`. `400`, `414`, `431`, `501`, `505`: no policy, no `nosniff`, no referrer rule; `421` and the `403` page no `no-store` (`p01_gate.txt`). They hold only escaped text, so no effect found; but "no page of `ddd gui` can be shown inside another" (`gui_security.rst:28`) is untrue of them. Override `send_error`. S.

- **M8. KNOWN (plans `2026-10-05`, `2026-10-07`): anyone can hold the 64 connections.** `docs/gui_security.rst:198-206`. Reproduced: 32 connections written to every 20 s stayed held past the 30 s that closed 32 idle ones (`p04_limits.txt`); the 65th of 64 is `503`. Documented, correctly.

- **M9. KNOWN (plan `2026-10-07`, P18b-11/13): a server earlier on the same port can leave a service worker or cached script in this origin.** `docs/gui_security.rst:226-238`. Not re-measured. Its advice, a browser profile of its own, is one few will take; the plan's structural answer, a fresh origin each run, is open question 5.

- **M10. KNOWN (spec `2026-10-05 §10`): the audit was run once, and is already out of date.** `npm audit` today: 0 in what ships, 5 in development (2 high: `vite` through `launch-editor`, `decode-uri-component`; 3 moderate: `vitest`, `@vitest/mocker`, `@vitest/coverage-v8`), none of them the plan's list (`transcripts/npm_audit.json`). A developer's dev server, not the product. A CI job or a dated release step. S.

- **M11. `Sec-Fetch-Site: none` survives a redirect, which the page's sentence does not cover.** `docs/gui_security.rst:177-183` ("a navigation it begins itself - an address typed, or chosen from a bookmark"). A typed address of another site that redirects to `/project?view=files&path=...` lands signed in (`p09_browser.txt`). Arrival asks no plan, so no effect beyond the page's own warning; widen the sentence. S.

### Status of the 2026-09-15 findings in this area

That review had no such pass, so there is nothing to check against.

### Open questions

1. **Is `ddd gui` meant to be safe to point at a tree you have not decided to trust?** Spec `2026-10-05 §10` left it "if the pilot asks"; pass 1 I15 asks for `--no-plugins`. *Yes:* no network or device from a build record (I4), a gate before the first analysis, a baseline's plugins off, and a project's `includes` held to the request rules too. *No:* one sentence at the top of the page: "treat `ddd gui` like `make`: it runs what the project names". Either answer is fine; today's silence is the defect.
2. **Must the token buy code execution?** Nothing on the page writes `plugins` (no writer in `gui/src` or the plan modules). If `POST /api/edit` refused any edit changing a `plugins` list, a created file's document included, a stolen token could no longer run code of its choosing, and I2, I3 and `served` would all weigh less (M, plus closing M2's read-around if that boundary is then wanted). *If not:* drop the confinement claims and call it robustness.
3. **The launch race:** keep the one-click browser on every system, or default to printing only where other users can read command lines? Either changes how much I3 matters.
4. **`localhost`:** serve `[::1]` (I1's measured fix, two origins, one server) or stop promising it and say so? Serving also simplifies the page's longest bullet but one.
5. **A fresh origin each run** (`<random>.localhost`): closes M9 at the cost of a `Host` rule per run and a browser's support for the name. The plan measured the idea and left it to you.

### Test gaps

- **The IPv6 stranger is always `V6ONLY=1`** (`tests/test_gui_server.py:3225, 3256`; `gui/e2e/localhost.spec.ts:23`). Add a dual-stack one and Node's default `listen(port)`. This is I1.
- **The hostile walk never runs where the server runs.** `tests/test_gui_hostile.py:152-158` builds its session on a temporary root with the working directory elsewhere, so every relative path is judged against the wrong directory, and it calls `Api.handle`, not HTTP. It claims `\x00` on every key is "never answered 500"; on `/api/compare` that holds only because the baseline lands "outside the session root" first (M1). `monkeypatch.chdir(root)` would have caught it.
- **No test of a hostile string reaching the page, and no lint rule.** The page's safety rests on React and on nobody adding a sink: Biome's `recommended` set, as configured (`gui/biome.json`), does **not** flag `dangerouslySetInnerHTML` (tried on a scratch file; it flags only `target="_blank"`). `security/noDangerouslySetInnerHtml` is one line, and my `p07_page.cjs` probe is about 60 lines of journey. No journey asserts zero policy violations in general (`units.spec.ts:268` listens in one).
- **The cap is tested with handlers holding their clients** (`Held`, `tests/test_gui_server.py:2060`), never a long poll whose client has gone (M3).
- **Build records have one hostile case, a newer format** (`tests/test_gui_api.py:1321`); no NUL, device or network `project` (I4).
- **`test_a_file_outside_them_is_not_read` pins one route** (`tests/test_gui_api.py:1935`); its neighbours pin an edit and settle. `/api/dictionary`, `/api/variable`, `/api/types` and `/api/findings` read it back (M2).
- **`Host` is pinned by one foreign name** (`evil.example`); the other forms I tried are refused because the comparison is exact, which is sound, and worth one parametrised test.

### Assessment

As a local server this is careful work that survives being attacked: in a real Edge, a hostile page on another port got nothing; a hostile project reached the page only as text in 492 visits; no request-named path left what is served; 11,300 malformed requests produced two `500`s and no hang. That is better than most tools of this kind, and the threat model is written down honestly. What is wrong is at the edges of the model rather than in its middle: one measured defence, the IPv6 hold, does not hold against the most ordinary way a program listens on Windows; the page never says that the token is code execution, which is what makes every residual it lists matter; "trusted" covers a tree the reader has not opened yet, including a network path read by the first thing the start page does; and a good deal of confinement code defends against nobody the model names while its docstrings claim otherwise. Fix I1 and the two sentences of I2 before calling the server reviewed, and decide open questions 1 and 2, because those two answers decide what the rest of the security page should say.

```candidates
12|I1|src/ddd/gui/server.py:128|On Windows a dual-stack listener on [::] binds beside the IPv6 hold and receives localhost:<port>/open?token=, against no other program can listen on localhost
12|I2|docs/gui_security.rst:135|The token is code execution as the reader (an edit names a plugin outside what is served) and neither the security page nor the terminal says so
12|I3|src/ddd/gui/server.py:446|The launch-code race hands its winner code execution for the whole run; the sign is one line after the fact (KNOWN)
12|I4|src/ddd/gui/session.py:249|A build record under the start directory acts on the start page's first request: a network path read, the console opened and a hang, a 500, before anything is opened
12|M1|src/ddd/gui/compare.py:384|GET /api/compare?baseline=%00 answers 500 on Windows with the server's own working directory; the hostile walk passes only because its cwd is elsewhere
12|M2|src/ddd/gui/session.py:154|served is no boundary: an outside file is read back through the dictionary and quoted by findings, and a build record widens it, against its docstrings
12|M3|src/ddd/gui/session.py:379|A long poll whose client has gone keeps its slot 25 s, so one tab reloading reaches the cap, against a browser never comes near that limit; the 503 is sometimes lost to a reset
12|M4|src/ddd/gui/server.py:630|ddd gui --port 80 prints an address no browser can use: Host carries no port, 421
12|M5|src/ddd/gui/server.py:973|An empty --host resolves to the computer's first network address rather than loopback
12|M6|gui/src/components/CompareView.tsx:83|The start page and the Compare form run a project's or a baseline's python without a word (adds to pass 1 I15)
12|M7|src/ddd/gui/server.py:265|The standard library's 400, 414, 431, 501, 505 carry no security headers, so can be framed; no effect found (KNOWN)
12|M8|docs/gui_security.rst:198|Anyone reaching the port can hold the 64 connections by writing every 30 s (KNOWN)
12|M9|docs/gui_security.rst:226|A server earlier on the same port can leave a service worker or cached script in this origin (KNOWN)
12|M10|docs/superpowers/specs/2026-10-05-gui-security-design.md:305|The dependency audit ran once and is out of date: 0 in what ships, 5 in development, 2 high (KNOWN)
12|M11|docs/gui_security.rst:177|Sec-Fetch-Site none survives a redirect, wider than a navigation the browser begins itself; no effect beyond landing signed in
```

## Pass 13: the web GUI, the edit engine and the plans

### Scope covered

Read in full, with line numbers: `src/ddd/editing.py` 1-982, `src/ddd/gui/session.py` 1-1039, `src/ddd/declaration_plans.py` 1-322, `src/ddd/type_plans.py` 1-117, `src/ddd/shared_plans.py` 1-612, `src/ddd/file_plans.py` 1-640, `src/ddd/lsp/units.py` 1-624, `src/ddd/lsp/edits.py` 1-954, `src/ddd/object_values.py` 1-507, `src/ddd/identity.py` 1-209, `src/ddd/file_names.py` 1-111, `src/ddd/pointers.py` 1-29. Read because the scope stands on them: `src/ddd/lsp/ranges.py` 1-395, `src/ddd/lsp/navigation.py` 1-930, `src/ddd/variables.py` 1-357, `src/ddd/finding_fixes.py`, `src/ddd/variable_keys.py`, `src/ddd/gui/derived.py`, `src/ddd/gui/queries.py`, `src/ddd/gui/api.py` 1-2486 (the plan and edit routes; its answers are pass 14's), `src/ddd/project_shared.py` 1-400, the "left open" sections of the GUI plans (`SCRATCH/pass-13/left-open.txt`), the spec's writing and verification sections (`2026-09-17-web-gui-design.md:360-394`).

Ran, all under `SCRATCH/pass-13/`, each transcript beside its script:

- `fuzz_engine.py`: random documents and batches against an oracle of its own (its own json reader keeping every literal and key as spelled, its own pointer grammar and application). Seeds 2, 3, 4: 180,000 documents, 127,263 batches, 122,179 written (`fuzz_engine_{2,3,4}.txt`).
- `plan_fuzz.py`: generated projects (CRLF, BOM, tabs, one-line containers, `\u` keys, non-ASCII, sub-projects, explicit nulls, repeated declarations) and every plan route through `Api.handle`, the outcome compared with the oracle's parse-modify of the same files, then the loader asked, then the undo compared byte for byte. Seeds 11-13: 18,000 actions asked, 7,612 applied (`plan_fuzz_{11,12,13}.txt`). `plan_fuzz_examples.py` over every example, as it is and CRLF: 515 applied.
- Real concurrency: `p03_stale_index.py` (Session threads), `p13_stale_http.py`, `p09_tabs.py`, `p08_killed.py` (a real `ddd gui` over real connections), `p04_lost_save.py`, `p05_two_writers.py`, `p06_same_instant.py`, `p07_two_guis.py`, `p16_id_and_gui.py` (separate processes), `p17_stress.py` (everything at once on one session).
- Files as they are met: `p01_readonly.py` (Windows), `p02_linux_files.py`, `p02b_id_link.py` (Linux through WSL; there is no pydantic in WSL, so these run the tree's own `editing`, `identity`, `ranges`, `pointers` and `file_names` with the models stubbed, `wsl_stub.py`), `p10_fix_matrix.py`, `p11_cases.py`, `p12_unloaded.py`, `p14_sizes.py`, `p15_more.py`, `p18_last.py`.

Not covered: a file symlink on Windows (no privilege here; junctions were); a real `ddd gui` on Linux (engine and `ddd id` only, as above); a power cut (M1 is read off the line); projects with several build records (one run per probe); what the page does with these answers (passes 15, 16); `test_gui_api.py` beyond grep (pass 22).

### Strengths

- **The text engine does what it says.** 122,179 random edits read back as the independent oracle's tree, every untouched literal and key as spelled: 0 wrong, 0 written where the oracle says the operation names nothing, and for a single set no byte changed outside the value it replaces (`fuzz_engine_*.txt`). Depth: answers up to 490 levels, refuses cleanly past it, to 100,000 levels on a request's thread (`p14_sizes_ladder_long.txt`). Duplicate keys, `NaN`: `409 unreadable`, file untouched (`p18_last.txt`).
- **The plans reach what they should.** 7,612 applied plans and 515 on the examples: the oracle's reach, spelling and values hold for every unit, type, constant, section, raster, declaration and file plan, a `\u` key and an escaped unit included. No plan's edit was refused after a 200, no 500, no BOM or final newline lost. The three classes of difference are M2, pass 2 M5 and pass 3 I2.
- **Undo is byte exact.** Every undo of every run restored every byte, created files removed; 66 undone at the end of the concurrent run compared equal (`p09_tabs.txt`).
- **One server serialises its writers.** Four tabs posting one plan: `[200, 409, 409, 409]`, 8 of 8; four files at once: all 200; three undos of one edit: `[200, 409, 409]`, 40 of 40. A minute of saves, half-saved files, plans, edits, undos and re-opens: 581 revisions, no thread stuck, settled at once, every fingerprint the disk's, findings equal a fresh session's (`p17_stress.txt`).
- **Rollback is real.** An edit whose second file is held open, a create whose description is held open, an undo with one file held: all refused after a second, the others back or forward, the undo entry kept and working once released (`p15_more.txt`). Ctrl-C during an edit lets it finish: `Session.stop` needs the lock the edit holds, 300 of 300 written (`p15_more.txt` 6).
- **Links and confinement in the GUI.** A file reached through a junction is written at its target and the junction stays (`p11_cases.txt` J); a rename reaching a file outside what is served is refused whole, nothing written (`p11_cases.txt` I).

### Issues

#### Critical

- **C1. A save during an analysis makes a revision that fingerprints the new bytes and points by the old ones, so a plan passes the stale check and lands on the wrong entry.** `src/ddd/gui/session.py:914`, `:926`, read at `:582`, after the analysis at `:572`.
  `_described` reads each file again once the analysis is over, and that hash becomes `SourceFile.fingerprint`. The index comes from what the loader read earlier. The claims it breaks: `session.py:4` "the files it read with a fingerprint of each", `src/ddd/variables.py:73` "What the analysis read the file at", `src/ddd/gui/derived.py:56`, `src/ddd/gui/api.py:1516`, `src/ddd/type_plans.py:11-13` "a file that changed since is refused by the fingerprint the edit carries", spec `2026-09-18-gui-units-design.md:197-199`. `session.py:699-707` records this same hazard for the stamps, and fixed it there alone.
  Trigger: a person's editor saves a component with a declaration added at its top, while an analysis runs; a plan is asked when the revision lands. No patching.
  - Real server, `GET /api/value-plan?name=Injection&at=[1]&raw=999`: plan `set component.interface[0].definition.init[1]`, `POST /api/edit` 200, afterwards `{'Ignition': [1, 999, 3], 'Injection': [100, 200, 300]}`; 6 of 6. The state at that moment says `analysing: false`; findings after it: 0 errors (`p13_stale_http.txt`).
  - Real server, removing section `.unused` while `.new` was saved above it: the person's just-saved `.new` is what goes; 6 of 6.
  - Session threads, a unit rename: `Gamma` goes `kg` to `krpm`, `Alpha` keeps `rpm`; 12 of 12 (`p03_stale_index.txt`).
  Window: the save lands anywhere from the loader's read of that file to the end of the analysis, then the plan any time up to the next revision: a poll (1 s) plus an analysis (3.8 to 6.0 s at 100,000 declarations, by `docs/command_line_interface.rst`'s own measure; about 1 s in these probes). A person saving twice inside one analysis is enough. The preview shows the true lines of the wrong declaration, without its name.
  Exposed (index pointer, no check of what sits there): `rename_unit`, `describe_unit`, `remove_unit`, `rename_type`, `set_entry`, `rename_entry`, `remove_entry`, `set_cell`, `set_values`, `read_object`. Safe: `settle` and its fixes (`lsp/edits.py:540`, `_at_site`), `set_key` (`project_types.py:233`), `remove_declaration`. `unit_drift` (`lsp/units.py:547`) exists and only the language server asks it; the read routes ask `type_in_place`, `entry_in_place`, `listed_in_place`.
  Change (S): fingerprint the bytes the analysis read, recorded by the loader or taken with the stamps before it reads (then a save in between refuses, the safe way); and have the plans ask the in-place question the read routes ask. `tests/test_gui_session.py`'s `saving_while_analysing` already makes the trigger.

- **C2. Every writer stages under one fixed name beside the file, so two writers can delete the file: on Windows the description is gone, nothing left beside it.** `src/ddd/editing.py:922`, the unlink at `:928-931`; `src/ddd/identity.py:198-208`; `src/ddd/file_names.py:16-18`; the reasoning at `identity.py:69-73` ("a leftover of a run that died is ours by construction").
  Trigger: two processes applying one change each to one file at one instant, once a round: two `ddd gui` over one project, or one and a `ddd id --assign` hook. Reproduced on Windows, the tree's own code:
  - 128 KB: THE FILE IS GONE 12 of 1,500, 11 of 2,000; 2 MB: 2 of 300; 16 KB: 0 of 1,500. One told written, the other `Permission denied` on the stage, the directory empty (`p06_same_instant_windows.txt`, `p06_again.txt`).
  - With the real `identity.assign` against an edit: 1 of 2,000; `assign` answered 1, the edit `unwritable`, directory empty (`p16_id_and_gui.txt`).
  - The cause named by mutation in a process of its own: the failure path's `staging.unlink()` taken out, 0 of 2,000; a stage name per process, 0 of 2,000 and no false refusal (`p06b_no_unlink.txt`, `p06b_unique.txt`).
  On Linux the file survives and the answers are false: the writer whose bytes are there was told it failed, 1,067 of 1,500 at 16 KB (`p06_same_instant_linux.txt`); 1,013 of 515,190 reads of the file were not json, the first of them empty, and the other engine answered `unreadable` on 497 of its reads (`p05_two_writers_linux.txt`, both writers hammering).
  Rare: two writers in one millisecond. Graded for what it costs: a person's uncommitted description, no trace, and an undo that answers the file can no longer be read.
  Change (S): a stage name of its own per write (`tempfile.mkstemp` beside the file); `CREATED_NAME_MAX` and the test pinning the suffix follow.

#### Important

- **I1. The fingerprint is checked once, before anything is written, so a save landing during an edit is overwritten, the edit answering written.** `src/ddd/editing.py:803`, written at `:811`; spec `2026-09-17-web-gui-design.md:383-386`; the docstring at `editing.py:793-794`.
  Trigger: another process saves a file at a random moment of `apply_changes`. Given a save inside the edit: 273 of 300 lost at 50 declarations (the edit takes 8 ms), 198 of 200 at 500 (43 ms), 27 of 40 for the first of 100 files (578 ms) (`p04_lost_save.txt`). The window of the first file is the whole in-memory phase of the batch: 1,200 files, 3.07 s, whole edit 6.33 s (`p14b_window.txt`). Two `ddd gui`: both 200, one change gone, 1,179 of 1,200 (`p07_two_guis.txt`). `assign` answered 1 and the id is gone, 1,993 of 2,000 (`p16_id_and_gui.txt`). `Written.before` holds the bytes from before the save, so the undo cannot bring it back either.
  Graded below C1 only because the common window is milliseconds; a pull or a branch switch during a large rename has seconds. It is the same class of loss.
  Change (S): compare the file's bytes with `original` again immediately before each rename, refusing `stale` and putting back. Tried at run time: 273 of 300 becomes 35 (the stage's own write is still inside; check after staging), 27 of 40 becomes 0 (`p04b_recheck.txt`).

- **I2. A rename or removal of a type, constant, section or raster, and a settle, are half performed while one file of the project did not load; only a unit's rename refuses.** `src/ddd/type_plans.py:93`, `src/ddd/shared_plans.py:212`, `:326`, `src/ddd/lsp/edits.py:577`, `src/ddd/gui/api.py:1219`; the guard at `src/ddd/lsp/units.py:235-240` has no sibling; `api.py:1193-1198` hands `unread` to `SharedProject` and only `add_entry` reads it.
  Against `lsp/units.py:13-15` "a rename that cannot see it leaves the old spelling there, in a project the rename said it had rewritten", `lsp/navigation.py:373-377` "An ordinary mid-edit state has to refuse the rename, not half-perform it", `lsp/edits.py:570-572` "a change that reaches only some of its declarations is not the one they chose".
  Trigger (`p12_unloaded.txt`): `b.ddd.json` truncated by a save, or holding one mistyped value, as an editor saves a file being typed in. Unit rename: `409 unreadable`. Type, constant, section, raster rename: plan 200 over the other files, edit 200, `b` untouched; once `b` is repaired, `unknown-type`, `unknown-constant`, `unknown-section`, `unknown-raster`. Settle: `definition-mismatch` once repaired. Removing a constant only `b` names: allowed, `unknown-constant` once repaired; a section or a raster likewise, the panel reading 0 uses.
  Change (S): the refusal `rename_unit` makes, in `_type_plan`, `_shared_plan` for rename and remove, and `_settle`. Which reach a repair would need is question 3.

- **I3. No plan asks the loader what it would leave: the engine verifies json, never the format, so a button or a panel value writes a file that stops loading, against a page promising otherwise.** `src/ddd/variables.py:232`, `src/ddd/editing.py:19-20`; the promises at `docs/command_line_interface.rst:315-316` "unless it would leave the file unable to load", `src/ddd/models/objects.py:953-955`.
  The root of three findings filed from other sides: pass 10 I7, pass 3 I1, pass 2 M5. What this angle adds is the reach in the page. Pass 10's matrix through `GET /api/fix` and the panel's values in play (`p10_fix_matrix.txt`): **84 of 1,002 buttons** and **58 of 882 in-play values** leave a file the loader refuses: `Use the datatype declared in w` on an enum (`requires an integer datatype`), `Remove this dimensions` on a string, `Use the unit declared in w` on a string. Each is previewed as an ordinary change and offered as the fix; undo puts it back.
  Change (S-M): `planned` validates the text it computed with the model of that file's kind, and the answer refuses or says so; which is question 5. What is wrong only in context stays reported, as the spec rules.

- **I4. A read-only file: on Windows the refused edit leaves a read-only stage that blocks every later edit, even once the file is writable again; on Linux it is written through.** `src/ddd/editing.py:926`, `:928-931`, `:949-959`.
  Windows (`p01_readonly.txt`): `_keep_access` makes the stage read-only, the rename is refused after 1.17 s, and `staging.unlink()` is refused too, in a `suppress`: `u.ddd.json.ddd-staging` stays, read-only. The reader clears the flag and asks again: `Permission denied` on the stage, at once, for as long as nobody deletes it. Likewise a read-only stage left by a kill. A created file takes the description's read-only mode, so its rollback fails: `these could not be put back: ...constants.ddd.json`, and the stage stays beside them (`p11_cases.txt` M).
  Linux (`p02_linux_files.txt` 1): a file kept 444 is rewritten and stays 444, no refusal, where `identity.py:59` calls a read-only file one that "could not be written". A read-only checkout's protection is silently passed; nothing says which system does what.
  `tests/test_editing.py:706` pins no leftover with a monkeypatched `Path.replace`, whose stage is not read-only.
  Change (S): refuse a target this process may not write before staging, on every system (question 1); make the stage writable before unlinking it.

- **I5. `ddd id --assign` through a symlink replaces the link with a copy and leaves the file it names unstamped.** `src/ddd/identity.py:198-201`, where `gui/session.py:823` resolves first. Adds to pass 2 I6.
  Reproduced on Linux (`p02b_id_link.txt`): `proj/common.ddd.json -> ../shared/common.ddd.json`, `assign` answers 1; the link is now a regular file holding the id, `shared/common.ddd.json` has none. A description shared between projects by a link is forked in silence, `wrote 1 id`, each project then minting its own identity for one object.
  Change (S): resolve the path first, or take the engine's writer, which closes pass 2 I6 too.

- **I6. Reading another component's local is offered, and writes `local-conflict` into a clean project.** `src/ddd/declaration_plans.py:83-98`, `:101-111`.
  Trigger (`p11_cases.txt` A): `W` holds `Loc` local. `GET /api/declarable` for `R`: `('Loc', ['input'])`; plan 200, edit 200, two errors `'Loc' is local to component 'W' but is also declared as input by component 'R'`. `scopes_for`'s docstring holds `local` back "because `local-conflict` is exactly a local beside another declaration", which an `input` is. Locals are ordinary (every declaration of `examples/vocabulary` is one), the name field lists them with the rest, and for such a name this is the only scope offered.
  Change (S): `declarable` leaves out a name only locals hold, or `scopes_for` answers none and the plan refuses.

#### Minor

- **M1. All-or-nothing holds against a refusal, not against a stop: a killed server leaves half an edit and nothing says so.** `src/ddd/editing.py:806`, `src/ddd/gui/contract.py:1657`, `:1660` "made all at once, or not at all", `src/ddd/gui/server.py:380`. A rename across 400 files, the server killed while writing, as a closed terminal or `kill` does: 6, 49 and 59 files renamed, once a stage left beside them; started over: `error: 0`, nothing to undo (`p08_killed.txt`). Ctrl-C is safe (Strengths). No `fsync` before the rename either (`editing.py:924`), so a power cut can leave an empty file on a file system that reorders (read off the line). Question 4.
- **M2. `at` without brackets plans a key of its own: `init1`.** `src/ddd/object_values.py:472`, `src/ddd/gui/queries.py:1094`. `GET /api/value-plan?name=A&at=1&raw=9`: `_element` strips brackets it never required, the pointer is `...definition.init1`, 200, the edit makes `schema: Extra inputs are not permitted` (`p11_cases.txt` E; 85 load failures with pass 2 M5 in `plan_fuzz_1[123].txt`). The page always sends brackets; a second client meets this.
- **M3. Reading a conditional object drops its condition.** `src/ddd/declaration_plans.py:320`, against `:163-164` "agree with its producer by construction". Producer under `defined(FEATURE)`: `condition-mismatch` on both sides after the plan (`p15_more.txt` 1).
- **M4. A short init's cell past its end is refused in the engine's words.** `src/ddd/object_values.py:332`, against `:197-199` "setting a cell or pasting a table ... is how the page repairs it". `init` of 2 in a shape of 4, `at=[3]`: `409 nothing is written at component.interface[2].definition.init[3]` (`p11_cases.txt` E). Only the paste repairs it.
- **M5. A change the poll cannot see is stale for good.** `src/ddd/gui/session.py:424`, `:1034-1038`. Same size, same modification time (a one-second file system, a tool restoring times): poll false; the plan 200 with the old fingerprint, its edit `409 stale`, every retry the same, until something else changes (`p11_cases.txt` K). A stale refusal asks for no analysis (`p18_last.txt`). `KNOWN` in part: `2026-09-19-gui-units-project.md`, Task 8, "an immediate retry is refused again". Change: a stale refusal asks for an analysis, which closes that too.
- **M6. An edit does not always follow the file's line ending.** `src/ddd/editing.py:134-138`, `:625`, `src/ddd/lsp/units.py:151`. No line break after the place: LF into a CRLF file, `{\r\n ...2,\n    3],\n    "c": 3}` (`p15_more.txt` 7; 6 in `plan_fuzz_1[23].txt`). Bare CR reads as one line, so an addition joins it (`p11_cases.txt` N). A created file is LF and two spaces whatever the project writes (`p11_cases.txt` O). The remainder of P8-M6.
- **M7. The Files tab writes a backslash or an absolute path into `includes`.** `src/ddd/file_plans.py:569`, `src/ddd/lsp/units.py:124`. `sub\x.ddd.json` and `C:/Users/.../y.ddd.json` are written as typed, clean here (`p11_cases.txt` L), a `file-not-found` on any other machine; against `src/ddd/file_names.py:5` "A project is checked out on more than one system".
- **M8. A member added to a file written on one line is quadratic, under the session's lock at Apply.** `src/ddd/editing.py:149`, `:282`, `:634-646`. Whole component on one line: 0.45 s at 1,000 declarations, 39.3 s at 10,000 (1.5 MB); the rename batch 0.88 s, a removal 0.69 s (`p14_sizes_ladder_long.txt`). `_unit_below` walks every entry looking for a line of its own, `indent_of_line_at` copies the rest of the text for each.
- **M9. Keys holding the pointer grammar crash the engine rather than refuse.** `src/ddd/editing.py:643`, `:699-702`. A file with a key `""`, `.`, `[` or `a.` anywhere: member additions raise `AssertionError` or `RecursionError` (942 and 306 in `fuzz_engine_{2,3,4}.txt`), answered 500, nothing written. Only reachable in a plugin's block or by a direct post. `KNOWN` (`2026-09-17-web-gui-skeleton.md`, `2026-09-30-gui-large-projects.md`).

Seen again, not re-filed, with what this angle adds:

| Earlier | In the GUI |
|---|---|
| pass 1 C4 | Reaches every plan that edits the description: `create_plan`, `add_plan`, `remove_plan`, `adopt_units`, `add_entry`'s creating arm (`file_plans.py:420, 569`, `shared_plans.py:584`, `lsp/units.py:385`). A rename or a set does not. |
| pass 2 I6 | Confirmed; I5 and C2 add to it. |
| pass 2 M3, M7 | Confirmed: `"unit": "\u00b0C"`, `-40.0` from `-4.0e1`; the id last, where `ddd id` puts it after `name` (`p11_cases.txt` F). |
| pass 2 M5 | Confirmed: `18446744073709551616` in a float32 cell, `schema` (`p11_cases.txt` E). See I3. |
| pass 3 I1 | Confirmed: `settle` and `type-plan`, six of six values stop the file loading (`p11_cases.txt` H). See I3. |
| pass 3 I2 | Confirmed: `settle` of limits on a variable stating none answers 200 and no change (`p11_cases.txt` G). |
| pass 3 M5 | Refused 400 before anything is touched: no file risk (`p18_last.txt`). |
| pass 10 I7 | Reaches the page: 84 of 1,002, 58 of 882. See I3. |
| pass 10 I8 | Does not reach the page as a wrong press: `_reconciled` drops it, so the finding has no button (`p11_cases.txt` B; 124 of the matrix's 680 findings have none, these among them; `KNOWN`, `2026-09-25-gui-mismatch-fix.md`). |
| pass 10 I9 | Does not reach the page: `shared_plans._raw` escapes; `a"b`, `a\b` load (`p11_cases.txt` D). |
| pass 10 I10 | Reaches the page, and further: a rename leaves `CELLS > 2`, and **removing** `CELLS` is allowed with 0 uses and no finding, the object compiled out (`p11_cases.txt` C). |
| pass 10 M2 | No buffers in the GUI; C1 is the disk's own form of it. |

### Status of the 2026-09-15 findings in this area

Only those not plainly fixed. P8-I1 (`ranges.py:94-115`), P8-M5 (`ranges.py:297`), P5-M4 (`identity.py:199-208`), P6-M14 (the engine counts `\n` alone) are fixed.

| Finding | Status | Note |
|---|---|---|
| P8-M6 | STILL OPEN in part | `editing.py:134-138` fixed the bare CR it was filed on; an LF still enters a CRLF file where no line break follows. M6. |
| P8-M18 | FIXED, with new defects | `identity.py:198-201` stages now; the stage is what C2 and I5 are about, and pass 2 I6 lists what it lost beside the engine. |

### Open questions

1. **May a read-only file be edited?** Today: refused on Windows, written on Linux. If not, a check before staging on every system (I4). If so, Windows has to clear and restore the flag, and the docstrings change. I would refuse.
2. **May two servers serve one project?** A unique stage (C2) stops the deletion, but both still answer written and one change goes (I1). A lock file beside the description refuses the second server, and costs a stale lock after a crash.
3. **A rename while a file does not load: refuse, or reach it by text?** Refusing is what `rename_unit` and the editor do, and it blocks every rename while somebody's file is half saved. Writing into a file nobody can read is not on offer. I would refuse (I2).
4. **Is all-or-nothing meant to survive a kill?** If so a journal beside the project and a recovery at start (M). If not, `contract.py:1657` says refusals, and the page's sentence with it (M1).
5. **Plan that would stop a file loading: refused, or written and reported?** Spec `2026-09-20-gui-other-keys-design.md` 4.2 rules written and reported; `docs/command_line_interface.rst:315-316` and `objects.py:953-955` say otherwise. Refusing loses a path through a bad state; I would refuse a button and warn on a panel's value (I3).

### Test gaps

- No test holds a fingerprint to the bytes the analysis read: `tests/test_gui_session.py:279` compares after the fact, nobody saving; `saving_while_analysing` (`:380`) checks the poll, not the plan. A plan and an edit after that helper's save pins C1.
- No plan test moves a file between the analysis and the plan: the drift tests are the read routes' and the language server's.
- No test has two writers on one file, or a real read-only file: `tests/test_editing.py:706` and `_patiently`'s test monkeypatch `Path.replace`, which is why I4 and C2 stayed green at 100 %.
- `tests/test_unit_plans.py` covers the unread refusal; nothing asks the same of `rename_type`, `rename_entry`, `remove_entry` or `settle` (I2).
- `tests/test_editing_at_once.py:44`'s `oracle` is the engine's own helpers, so it pins at-once against in-turn, not against an independent reading. The independent one here found no difference; `fuzz_engine.py` is a ready start.
- No test asks the loader of what a plan's result is, across kinds of conversion (I3).

### Assessment

Can an edit lose or corrupt a person's file? Yes, three ways, each from one small decision, all reproduced: a fingerprint read after the analysis it is said to describe (C1: the wrong declaration rewritten, a just-saved entry removed, a value in the wrong object, with every gate green), one fixed stage name (C2: the file deleted), and a check made once before all the writing (I1: a save overwritten). Each fix is hours. What surrounds them is better than this makes it sound: the text engine is the strongest thing I have read in this project, 122,179 random edits and 7,612 plans read back exactly by an oracle that shares nothing with it, undo is byte exact everywhere, one server serialises its writers, and rollback works when something refuses. The weakness is the seam between the plans and the disk: the design trusts the fingerprint so completely that the plans dropped the in-place question the read routes and the editor ask, so when the fingerprint lies nothing else stands. Does a plan always produce a file the loader accepts and the change it announced? The change, nearly always; the file, no: about one button in twelve in a matrix of disagreeing declarations stops a file loading, and nothing between the plan and the write asks the loader (I3). Rename also needs the guard the unit rename has (I2). Fix C1, C2, I1 and I2 before anyone edits a real project with this and a text editor side by side.

```candidates
13|C1|src/ddd/gui/session.py:914|A save during an analysis gives a revision fingerprinting the new bytes and pointing by the old: a plan passes stale and rewrites the wrong declaration, value or entry, 12 of 12
13|C2|src/ddd/editing.py:922|One fixed stage name: two writers delete the description on Windows (11 of 2000, also with ddd id --assign), on Linux the answers are false and readers meet an empty file
13|I1|src/ddd/editing.py:803|The fingerprint is checked once before anything is written: a save during an edit is overwritten, answered written, and undo cannot bring it back; seconds on a large rename
13|I2|src/ddd/shared_plans.py:212|Rename or removal of a type, constant, section or raster and settle are half performed while one file did not load; only a unit's rename refuses
13|I3|src/ddd/variables.py:232|No plan asks the loader what it leaves: 84 of 1002 buttons and 58 of 882 in-play values stop a file loading, against unless it would leave the file unable to load
13|I4|src/ddd/editing.py:926|A read-only file: on Windows a read-only stage stays and blocks every later edit, rollback of a create fails; on Linux it is written through
13|I5|src/ddd/identity.py:198|ddd id --assign through a symlink replaces the link with a copy and leaves the file it names unstamped
13|I6|src/ddd/declaration_plans.py:111|Reading another component's local is offered and writes local-conflict into a clean project
13|M1|src/ddd/editing.py:806|A killed server leaves half an edit, error 0 at restart, against made all at once or not at all; no fsync before the rename
13|M2|src/ddd/object_values.py:472|at without brackets plans a key init1 and the file stops loading
13|M3|src/ddd/declaration_plans.py:320|Reading a conditional object drops its condition: condition-mismatch, against agree by construction
13|M4|src/ddd/object_values.py:332|A short init's cell past its end is refused in the engine's words, against setting a cell repairs it
13|M5|src/ddd/gui/session.py:424|A change of the same size and time is stale for good: a stale refusal asks for no analysis (KNOWN in part)
13|M6|src/ddd/editing.py:138|LF into a CRLF file where no line break follows; bare CR reads as one line; a created file ignores the project's layout (remainder of P8-M6)
13|M7|src/ddd/file_plans.py:569|The Files tab writes a backslash or an absolute path into includes, against checked out on more than one system
13|M8|src/ddd/editing.py:149|A member added to a one-line file is quadratic: 39 s at 1.5 MB, under the session lock at Apply
13|M9|src/ddd/editing.py:643|Keys holding the pointer grammar crash the engine rather than refuse: 500, nothing written (KNOWN)
```

## Pass 14: the web GUI, the API and its answers

### Scope covered

**Read in full, with line numbers:** `src/ddd/gui/api.py` 1-2486, `contract.py` 1-1798, `compare.py` 1-432, `derived.py` 1-188; `src/ddd/project_units.py` 1-273, `project_types.py` 1-299, `project_shared.py` 1-1004, `variables.py` 1-357, `variable_keys.py` 1-271, `value_identity.py` 1-80, `graph.py` 1-191, `finding_routes.py` 1-365, `finding_fixes.py` 1-125, `findings_by_file.py` 1-88, `deliveries.py` 1-231. Also, because every answer runs through them: `gui/session.py` 1-1039, `gui/queries.py` 1-1114, `gui/depth.py` 1-385, `gui/routes.py` 1-73, `lsp/diagnostics.py` 1-403, `object_values.py` 1-420, `plugins.py` 60-357, `cli.py` 780-936 and 1878-1917, `tools/bench_gui.py`, `tools/generate_project.py`.

**Specs and plans.** In full: `2026-09-17-web-gui-design.md`, `2026-09-22-gui-findings-design.md`, `2026-09-26-gui-compare-design.md`, `2026-09-30-gui-large-projects-design.md`, `2026-09-18-module-graph-design.md` sections 1-4.5, `2026-09-23-gui-values-design.md` 4.2-4.3. The other `*gui*` specs I read only for what each says of its endpoints (grep of `/api/`, `404`, `409`). "Left open" read whole for large-projects, findings, other-keys, values, files, compare, mismatch-fix, module-graph; the rest searched for this pass's subjects.

**Ran**, everything in-process through `Api.handle` unless said, each transcript beside its script under `SCRATCH/pass-14/`:

- `p02`: all 57 requests of `rich.py` (a project with every feature, clean under `--strict`) on a valid project.
- `p04`: the same 57 on 24 broken projects. `p05`: on 26 kinds of change landed under a revision. `p19`: on 48 saves that still parse, values of the wrong type. `p06`, `p30`: on 40 kinds of value the loader takes or refuses. `p07`: half way through an analysis, held on an event: the first, one after a save, one after an edit.
- Against the tool: `p03`, `p25` (`/api/findings` against `ddd check --format json`, finding by finding: 5 examples, then 57 broken cases each under the defaults and under a strict build with overrides); `p03` (`/api/dictionary` against `ddd dump`, `/api/checks` against `ddd checks`); `p01`, `p14`, `p17` (`/api/compare` against `ddd compare` and `ddd check --baseline`: 25 changes, builds); `p23` (18 odd baselines); `p08`, `p09`, `p27` (a panel's `disagrees` against `definition-mismatch`: 62 pairs); `p11`, `p12`, `p31` (the graph); `p13` (where each of 47 kinds of finding leads, and whether it is listed there); `p22` (rows against panels against the dictionary, 7 projects); `p26` (adopting and adding a file, then `ddd check`); `p18`, `p29` (values and numbers); `p10` (what the poll notices, real `Session.poll`); `p16`, `p20`, `p28`.
- Measured: `tools/bench_gui.py` on three generated projects (`bench.txt`), and what it does not measure (`p15_perf_*.txt`, `p21_perf2.txt`, `p24_vocab_large.txt`).

**The four states, as the endpoints answered them** (no exception escaped `handle` anywhere but M5):

| Routes | Valid | Broken | Half way through an analysis | Changed under it |
|---|---|---|---|---|
| `session`, `projects`, `checks` | 200 | 200; a root that does not parse has `name: null` and leaves `projects` | 200, also before the first revision | 200 |
| `state`, `findings`, `graph`, `dictionary` | 200 | 200; `dictionary: null` where the read reported an error | `state` revision 0 then the last revision with `analysing: true`; the rest 409 `analysing` before the first, then the last revision | the last revision, until the poll; routes read the disk for the names they carry |
| panels: `variable`, `unit`, `type`, `constant`, `section`, `raster` | 200 | 409 `unreadable` naming the file, 404 only where every file loaded | last revision's index, the disk's text | 409 "changed since", or a row left out; `type` of a structure 500 (M5) |
| rows: `units`, `types`, `shared`, `files` | 200 | 200, empty where no index | as panels | a row's fields empty once its place moved; `files` follows the disk |
| `values`, `compare` | 200 | 409 where nothing resolved; otherwise from what resolved (I1, M3) | last revision | last revision; a baseline read now (a project against itself reads as a change, until the next revision) |
| plans | 200 | 409, or 404 (M4) | 409 `analysing` for a file an edit wrote, otherwise computed | 409 in engine words, or passes (pass 13 C1); judged plans `stale` |

**Measured** on this Windows 11 PC (16 logical processors, Python 3.13.17), one run each; the documents' figures are the Linux development PC's and its analysis is about three times faster (3.8-4.5 s).

| ms | heavy100k (`mixed`, ids 1, unread 0.5; 125,000 findings) | clean100k (`mixed`) | heavy35k (`many`) |
|---|---|---|---|
| open / analysis | 15,595 / 16,717 | 10,523 / 10,923 | 4,524 / 7,100 |
| state, graph, units, files | 427, 331, 42, 444 | 40, 218, 63, 505 | 118, 452, 15, 328 |
| findings page, of a file | 123, 359 | 0, 0 | 13, 3 |
| variable, unit | 85, 1,625 | 186, 529 | 28, 221 |
| remove judged, rename plan | 16,644, 10,052 | 13,475, 9,679 | 5,729, 3,700 |
| edit answered, edit analysed | 6, 16,113 | 267, 14,596 | 5, 6,033 |
| while analysing: state, plan, edit | 608, 256, 297 | 68, **24,908**, 720 | 292, 194, 301 |

Beyond the bench (heavy100k / clean100k): idle poll round 26-28 ms; `POST /api/open` 957 / 1,035 ms; `GET /api/declarable` 5.2 / 4.5 s; `GET /api/settle` in the largest component, idle, **22 / 38 s**; `GET /api/compare` of a dump 4.7 / 4.1 s then 1.4 / 1.0 s; `GET /api/dictionary` 9.3 / 6.9 s. Resident memory at clean100k: 697 MB with one revision, about 1 GB after three more, peak 1.37 GB; with two baselines held, 1.58 GB and 2.4 GB (heavy100k 2.2 and 3.2 GB), where `compare.py:136` sizes an entry by "the 45 MB one".

**Not covered:** the page's use of these answers beyond reading what it does with a few (passes 15, 16); a real browser, or real HTTP (`Api.handle` was driven; the server's own path is pass 12's); the journeys; several build records beyond `p17`; Linux; `tests/test_gui_api.py` beyond grep (pass 22); the page half of the benchmark.

### Strengths

- **The findings are the tool's.** 119 runs of `/api/findings` against `ddd check --format json`, compared by check, severity, words, file and pointer, under the defaults and under a strict build record with overrides: not one differs, mirrors aside (`p03`, `p25`). "The same engine" holds for findings, and it holds because `session._runs` really is the same `_run`.
- **`/api/dictionary` equals `ddd dump` byte for byte as json, `/api/checks` equals `ddd checks --format json`** (`p03`).
- **The comparison's own findings and renames equal `ddd compare`'s** in all 24 of 25 changes that resolve (`p14`); only the verdict differs, I1. Strictest-of-builds does what `_policy_of` says (`p17` b2). Eighteen odd baselines get a reason, none a 500 (`p23`).
- **Nothing falls over.** 57 requests over 24 broken projects, 26 changes under a revision, 48 wrong-typed saves and 40 hostile values raised exactly one kind of exception, on one route (M5). Numbers an answer could not carry (`NaN`, `1e999`, a derived infinity) are refused before they reach it (`p29`, `p30`).
- **Half way through an analysis is coherent**: `analysing`, `edits` and `undoable` move as documented, a plan on an edited file is refused in a true sentence, and a state request answered in 68-608 ms beside a 10-17 s analysis (`p07`, `bench.txt`).
- **Rows agree with panels** on all seven projects: every type, unit, constant, section and raster, uses and findings, and each variable's roles with the dictionary's owner and consumers (`p22`; the two `sections` lines in its transcript are the probe's own: a dictionary has no such key). **An add's `brings` was right in all nine cases held against `ddd check` after applying it** (`p26`). `adoptable` agrees with the plan it is answered by in all nine cases.
- **Routes lead somewhere true**: 47 kinds of finding; the exceptions are M8 and the known ones.

### Issues

#### Critical

None. The nearest is I1, and it stays Important because the build still refuses the project and the tab is one tab away from the errors.

#### Important

- **I1. The Compare tab says "This project can replace the baseline" of a project `ddd compare` says cannot.** `src/ddd/gui/compare.py:262`, drawn at `gui/src/components/CompareView.tsx:97-99`. Against `SPEC.md:1516-1518` ("exactly when no finding of the run is reported as an error - the candidate's own, the baseline's carried ones and the comparison's alike"), spec `2026-09-26-gui-compare-design.md:93-94` ("by the rule the command's exit code already uses"), `:88-89`, and the function's own `compare.py:180-182` ("under every rule the command's own exit code answers by"); `contract.py:1493-1494` is vague. One document says the opposite: `docs/command_line_interface.rst:362-364`, "the project's own findings ... take no part in it".
  *Trigger:* dump a clean project, change one reader's unit. `ddd check` 1 error; `ddd compare`: exit 1, `project.ddd.json cannot replace baseline.dictionary.json`; `ddd check --baseline` exit 1; `GET /api/compare`: `{"verdict": true, "findings": []}` (`p01_verdict.txt`). Of 25 changes the verdict differs in four, every one `ddd compare` exit 1: a reader disagreeing, a reader of nothing, a short init, a section the access forbids (`p14_compare.txt`). Worse with two builds: one relaxing `duplicate-constant`, one not. `analysed: false`, two errors on the state, `verdict: true` from the first build's dictionary (`session.py:594`), while `ddd check --baseline` under the other exits 1 (`p17_builds.txt` b), against `_policy_of`'s "a delivery any one of the project's builds would refuse is not one to call acceptable". Only a candidate whose read reported an error is refused (409); an error of the analysis passes.
  No test pins it either way. *Change (S):* the verdict takes `not revision has errors`, `Compared` says which, the panel says "the project has N errors of its own". Or, if the carve-out stands (open question 1), the tab stops using the command's words and the SPEC says so.

- **I2. `GET /api/graph` knows nothing of structured variables: `examples/structures` draws two modules and no arrow, and a disagreement about one paints none.** `src/ddd/graph.py:83`, `:101-129` walk `dictionary.objects`; `dictionary.instances` holds the structured ones, with the same `owner` and `consumers`. Against spec `2026-09-18-module-graph-design.md:96-97`, `contract.py:476` ("Everything one module produces for another"), `:519` ("Every flow").
  *Trigger:* `examples/structures`: `ddd check` clean, `Inlet` owned by Sensing, read by Monitoring; `flows: []`, `dictionary: true`, which spec 4.5 tells the page to read as modules that share nothing. Make the reader's `volatile` differ: `ddd check` 1 error, both modules count it, still no arrow (`p12_graph_structures.txt`). In `rich.py` `Inlet` flows beside three scalars: `objects` leaves it out, and with a mismatch on it the flow is `severity: null`, an arrow drawn as agreeing between two modules with an error each (`p11_graph.txt`). So on a project whose interface is structures, the first screen shows an architecture with nothing connected.
  Reproduced on the repository's own example; `tests/test_graph.py` (22 tests) has no structure in it. *Change (S):* walk `(*objects, *instances)`; `_declared_object` already answers an instance's name.

- **I3. A variable's panel says the declarations disagree where `ddd check` says they do not, and neither settlement can be made.** `src/ddd/variable_keys.py:178-179`, against `value_identity.py:41-43` ("or a row reads as a disagreement the checker files no finding about"), plan `2026-09-20-gui-other-keys.md:3000` ("a row the checker does not report must not read as a disagreement here").
  *Trigger:* the producer spells `datatype`, `unit`, `conversion`; a reader names a type fixing the same (or the other way round). `ddd check`: `ok`. `/api/variable`: `typename` `disagrees: true`, one value beside silence. The panel opens on that row (`gui/src/screens/VariablePanel.tsx:167`). `GET /api/settle` with that value: 409 "would not load ... storage is named exactly once"; with none: the same, naming the other file (`p09_typename.txt`). So a tinted row no action clears, on a project the tool calls consistent. Held against `definition-mismatch` over 62 pairs, the panel differs in these: one side naming a type and the other spelling it (7, a reader, a producer, one of three readers, with no producer at all), two types of one meaning (1), `unit: ""` beside no unit (2), an external type beside a scalar, where the check files `type-kind` instead (1); the other way round, `kind`, which the reference page says no edit carries, and limits past 2^53, pass 3 M9 (`p08_disagrees.txt`, `p27_disagrees2.txt`).
  *Change (S):* `typename` disagrees only where two declarations name different types; `datatype` and the rest are already read through the type. A test holding `disagrees` against the check over a table of pairs stops it returning.

- **I4. A plugin edited while `ddd gui` runs makes a new revision with the old code, for as long as the server lives.** `src/ddd/plugins.py:196-198`, noticed at `src/ddd/gui/session.py:424`. Against spec `2026-09-17-web-gui-design.md:40-42` ("so the GUI cannot disagree with the build"). Written down for whoever writes a plugin: `docs/plugins.rst:230-233` ("editing the plugin file only takes effect the next time a process starts"), `SPEC.md:1141-1142` ("in the editor after the server is restarted"). Nothing says it to a reader of `ddd gui`: its reference page does not, and the session stamps the plugin, so the page says updating and then shows a new revision as though it had run what is on disk. Hence Important rather than Minor; a verifier weighing the documented limit may grade it down.
  *Trigger:* `plug.py` files `plug/say: OLD WORDS`. Edit it to say `NEW WORDS`: the poll answers changed, the page says updating, revision 3 lands with `OLD WORDS`; `ddd check` says `NEW WORDS`. Take the check out: revision 4 still reports it, `ddd check` is clean. A module the plugin imports is neither noticed nor reloaded (`p10_watched.txt` 4, 5). The comparison's hooks are the same stale objects. A `git pull` updating a project's plugin during a day-long session reproduces it for someone who never touched Python.
  *Change (S to M):* where a plugin's stamp moved, drop its module and load it again (a failed reload is `plugin-invalid`, as it is at start), or, smaller, a finding saying the plugin changed and the server has to be restarted. Open question 2.

- **I5. A change the poll cannot see leaves the page saying what `ddd check` no longer says, `analysing: false`, until something else changes.** `src/ddd/gui/session.py:722-724` (the stamps are `revision.files`), `:420`. `KNOWN` in part: `session.py:18-19` ("a limit of the preview"), plan `2026-09-29-gui-files.md:954-956` for a new file on a pattern, filed as its own task and still open. The rest is not written down (`p10_watched.txt`):
  - a new component on `comps/*.ddd.json` writing a variable another writes: page 0 errors, `ddd check` `multiple-producers`, exit 1, indefinitely; `/api/files` lists the file meanwhile;
  - a plugin named but missing, then created: `plugin-not-found` stays, `ddd check` exit 0;
  - a plugin raising at import, then fixed: `plugin-invalid` stays, `ddd check` exit 0 (neither is in `revision.files`, because `workspace.sources()` lists only what loaded);
  - a build record rewritten, `-W` or `--strict` changed by a reconfigure: the old severities stand and `/api/session` names them (the GUI's twin of pass 10 M8).
  Saving a new file from an editor is an ordinary thing to do, and the page's "0 errors" is the reading a reader acts on. *Change (S):* stamp besides the files the directory each pattern expands in (creating or removing an entry moves its time, and it costs one stat where expanding cost seconds), every path `plugins` spells whether or not it loaded, and every build record found.

- **I6. A plan in a large file takes tens of seconds, idle, and holds up every other plan.** `src/ddd/variables.py:253-254`; `:283` is why the fast path never applies (the new line is held elsewhere in any file where the unit is used twice); `src/ddd/difflib_lock.py:40`. `KNOWN`: plan `2026-09-30-gui-large-projects.md:2441`, ruling F9 `:2577`, with two ways out. Against `docs/command_line_interface.rst:529` ("Large projects stay responsive") and `:535` ("a variable's plan ... within a tenth of a second"), whose caveat at `:541` gives 35,000 declarations only.
  *Measured here:* `GET /api/settle` of one variable's unit in the largest component, with nothing else running: 4.6-4.8 s at 35,000 (16,943 lines, the document says 0.8 s), 22-23 s at heavy100k (46,683 lines), 38 s at clean100k (48,350 lines); `declaration-plan` remove 22-23 s; 12.7 of 13.4 s profiled in `SequenceMatcher` (`p15_*`, `p21_perf2.txt`). Beside one such plan, a plan of a small component waits 2.3 s on the lock at 35,000. `plan while analysing` read 24,908 ms on clean100k and 256 ms on heavy100k only because the bench's chosen variable fell in a large component on one and a small one on the other. No budget of spec §3 covers a plan, so "met on all eighteen" does not speak to this: Apply is withheld until the plan answers.
  *Change (S):* the operations know the spans they replace, so a hunk needs the lines around them, not a diff of the file; or difflib over the trimmed middle, accepting another numbering where runs of lines are alike, which ruling T11b-1 declined.

#### Minor

- **M1. The page counts a disagreement once per file, so its totals are not `ddd check`'s.** `src/ddd/gui/derived.py:172-175`, `gui/src/lib/findings.ts:106-114`. `examples/inconsistent`: `ddd check` "4 errors, 1 warning", the Findings tab "8 findings · 7 errors, 1 warning" (`p03_against_cli.txt`); a producer with three readers disagreeing, 3 against 6 (`p20_names.txt`). The panel already says each statement once (`distinctFindings`); no document says the totals differ. Reproduced. Open question 3.

- **M2. A disagreement can name the wrong variable.** `src/ddd/graph.py:177-178` indexes `ResolvedComponent.declarations` by the file's interface index, and the analysis leaves out what it drops. A declaration of an unknown type above a mismatching `Speed`: `{"object": "Temp", "message": "'Speed' is declared differently ..."}` (`p12_graph_structures.txt`); the page opens `Temp`'s panel (`gui/src/lib/canvas.ts:344`). Where the wrong name does not flow, the disagreement is dropped and the arrow reads as agreeing. Reproduced. Read the name from the index's site, not by position.

- **M3. `GET /api/values` says the project declares no `X` of what it declares.** `src/ddd/object_values.py:122-124`. `the project declares no 'Curve'` where `Curve` names an axis nothing declares, `'Map'` where its axis dropped out, `'Inlet'` for a structured variable, `'StructCurve'` for a curve of a structure; `/api/variable` answers 200 for each, and the Shape column offers the button (`gui/src/screens/ComponentPage.tsx:166-169`, adds to pass 3 I3) (`p18_values.txt`, `p04_broken.txt`). Reproduced. Say why: not in the dictionary, with the finding's reason.

- **M4. Where a file did not load or moved, a plan's refusal says something false that the read route beside it does not.** `src/ddd/shared_plans.py:388`, `type_plans.py:116`, `lsp/units.py:270, 299, 333`, `gui/api.py:1288`. A constants file that does not parse: `/api/constant` 409 "'SAMPLES' is not declared in any file that loaded, and constants.ddd.json did not load"; `/api/constant-plan` 404 "no file of this project declares a constant called 'SAMPLES'". The same for sections, rasters, types and units; "project.ddd.json includes no units file" beside one that does not parse; `/api/declarable` "control.ddd.json is not a component" (`p20_names.txt`, `p04_broken.txt`). `_undeclared`'s docstring (`api.py:1763-1770`) is the rule the plan routes skip. In the window after a save: "a type of this kind has no 'unit' to set" of a scalar, "types[2].members[0] is not an object", "... can no longer be read as utf-8" of a deleted file (`p05_changed.txt`). Reproduced. Plans ask `_undeclared` before refusing `not-found`.

- **M5. `GET /api/type` answers 500 for a save that still parses.** `src/ddd/gui/api.py:904-915`, `:886`, `project_types.py:280-287`: every other read route reads drifted text tolerantly (`p19_drift_types.txt`: 48 saves over 57 requests). A member losing its `name` or `member`: `KeyError`; `bits: "a"`, `typename: 5`, `member: "other"`, `dimensions: 5`, `header: 5`: `ValidationError`. All in the window before the next revision, which is seconds at size. Reproduced. `_member` reads each key by what the contract wants, as `_string` does.

- **M6. A baseline is stamped after it is read, so a save in between serves a stale verdict until the next change.** `src/ddd/gui/compare.py:408`, the mistake `session.py:699-700` explains at length for the session ("Before, never after"). A file of the baseline saved during the read: first answer and cached answer `verdict: true`, a fresh session `false`, `ddd compare` exit 1 (`p16_misc.txt` a, the save put in the window by a patched reader). The window is the read: 10-16 s for a description at 100,000 declarations, and the open project as its own baseline is "the very first thing anyone compares against". Reproduced. Take the time before the read, and keep no entry any of whose files is newer than it.

- **M7. An analysis that raises is invisible to the page.** `src/ddd/gui/session.py:686-689`, `:717-718`; `contract.State` has no field for it. `KNOWN` in part (plan `2026-09-30-gui-large-projects.md:2437`), against its own spec `2026-09-30-gui-large-projects-design.md:146-148` ("The revision it makes carries the failure"). A plugin filing a check whose severity is a string (pass 7 M6): `ddd check` a traceback, exit 1; before the first revision `Analysing the project…` for good, `analysing` flipping at every poll; later, the last revision stands as current, `analysing: false`, the reason only in the terminal (`p17_builds.txt` c, c2, reproduced); and, read off `session.py:717-729`, no revision publishing means every plan on an edited file stays refused "has not been analysed yet". `State.failed: str | None`.

- **M8. A finding can lead to a panel that does not list it.** `src/ddd/finding_routes.py:191`, `:352-357`; `project_shared.py:342-352`. `consumer-storage` on a reader's `init` opens the values grid of the producer: another file, the producer's numbers, `findings: []`, and for a scalar no cell at all (`p28_small.txt`), where `finding_routes.py:161-162` says it "opens the values grid - the variable's own screen". A `duplicate-constant`, `-section` or `-raster` at the second entry leads to the first's panel, which lists only its own; the row says `findings: 1` of two (`p13_routes.txt`, `p28_small.txt`). `duplicate-unit` lists both. Reproduced.

- **M9. A missing include reads as the wrong file not loading.** `src/ddd/gui/session.py:925`, `contract.py:249`, `api.py:1772-1779`. `gone.ddd.json` in `includes`: its row `kind: unknown, loaded: true`; `project.ddd.json`, which parsed and matches its shape, `loaded: false`, so every route on it goes and `_undeclared` says "project.ddd.json did not load" (`p28_small.txt`, `p04_broken.txt` file_missing). `KNOWN` for the route (`2026-09-29-gui-files.md:957-958`); the sentence and the two rows are not.

- **M10. A component that does not parse is no module.** `src/ddd/gui/api.py:543`, with `session.py:933-945`. Graph: `[('Sensing', True)]`, the broken one absent; a schema error: `[('control', False), ('Sensing', True)]` (`p31_graph_unparsed.txt`). Against spec `2026-09-18-module-graph-design.md:24-25, 92`. `KNOWN`: plan `2026-09-18-module-graph.md:679-682`; adds to pass 2 M4.

- **M11. A refused build record is told only on the start page, which `ddd gui PROJECT` never draws.** `src/ddd/gui/session.py:566`. A record naming `--strict` and a check this DDD lacks, or a newer format: `builds: []`, a warning shown as a warning, nothing on the state or in the terminal (`p17_builds.txt` e), where `ddd lsp` logs it. Spec `2026-09-17-web-gui-design.md:462-463`. Reproduced.

- **M12. `GET /api/declarable` reads every producer's file to name it.** `src/ddd/declaration_plans.py:91`, where `built.components` already has it (`project_units.py:158` uses it). 4.5-5.2 s at 100,000 declarations, 1.7 s at 36,000, each time the panel opens, against the spec's 1 s for a panel; not in the bench (`p15_*`, `p24_vocab_large.txt`). Reproduced.

- **M13. A constant only a condition spells reads as unused, and goes.** `src/ddd/project_shared.py:502-548`, `docs/command_line_interface.rst:418-419` ("a shape"). `"condition": "UNUSED > 3"`: `/api/constant` `uses: []`, row `uses: 0`, the remove plan 200, applied, `ddd check` clean: and `#if` of an undefined name compiles the object out from then on, which pass 10 I10 measured for the rename (`p20_names.txt` for everything up to `ddd check`; no compile here).

- **M14. `POST /api/open` and the start page parse every description under the root.** `src/ddd/gui/api.py:352`, `session.py:958`. 552-608 ms of the 957-1,035 ms `POST /api/open` took at 100,000 declarations, against the 1 s of spec `2026-09-30-gui-large-projects-design.md:79`; the bench's `open` (`tools/bench_gui.py:370-375`) calls `session.open` and never sees it. Ask `wanted == self.project` first, and keep what `/api/projects` last found for the rest.

- **M15. Untrue sentences in the contract, which `gui/src/generated/api.ts` publishes.** `contract.py:1498` "Always carries `route: null`": a plugin's finding has `{'kind': 'variable', 'name': 'EngineHours'}` (`p28_small.txt`), as spec `2026-09-26-gui-compare-design.md:100-103` knows. `:317` "has no screen yet": types, constants, sections, rasters have had screens since. `:249`, `:453` "parsed and matched the shape": M9. `:476`, `:519`: I2. `:509` "a plugin that raised or a file that did not parse": any error of the read, `dup_const` here. `:850`: seven routes answer it. `api.py:11-12` "never a hand-assembled `dict`... cannot drift apart": every refusal is one (`:1695`, adds to pass 3 I5).

- **Met again, not re-filed.**
  - Pass 3 C1 starts on the server: `contract.py:1447`, `:1411`, `:1437` are `float`, so `init: [9007199254740993, 18446744073709551615]` is answered `[[9007199254740992.0, 1.8446744073709552e+19]]`, against spec `2026-09-23-gui-values-design.md:107` ("its values as the file holds them"), and a fix in the page alone cannot reach it. Planning `sint64`'s maximum from the row as answered is refused "written as a fractional number" (`p18_values.txt`).
  - Pass 3 M9: `p08`. Pass 2 I9: `constant-plan`, `section-plan`, `raster-plan` 1.5-2.7 s at 36,000 in `project_of` (`p24_vocab_large.txt`). Pass 13 C1 and I2: the plans of the "changed" and "broken" columns above. Pass 7 M7: a json of `name` alone is `verdict: true` here too (`p23_baselines.txt`). Pass 1 I4: a raster's event changing, no finding on either side (`p14_compare.txt`).

### Status of the 2026-09-15 findings in this area

None: that review had no such pass.

### Open questions

1. **Does the Compare tab's verdict include the project's own errors?** SPEC 4.1 and the tab's spec say yes, the reference page says no, the code says no. Yes: the tab always agrees with the command, and a broken project cannot read as replaceable (I1, S). No: the words "can replace" have to go, since they are the command's, and SPEC 4.1 gains a sentence.
2. **A changed plugin in a long-lived server: reload it, or say so?** Reloading makes the page true and runs new code from a `git pull` unasked, which the next run of anything would do anyway. Saying so keeps "imported once per process" and adds a finding. Which also decides the language server's sentence at `SPEC.md:1142`.
3. **Is the headline a count of statements or of rows?** Statements match `ddd check` and the CI log a reader holds beside the page; rows match the table under it. Today the number matches only the table (M1).
4. **Is a type on one side and the same thing spelled on the other a disagreement?** `ddd check` says no, the panel yes. No: I3's fix. Yes: `definition-mismatch` changes, and a settling way has to exist, since neither direction can be written today.
5. **Do the budgets bind a plan, and on which machine?** No budget covers the wait before Apply is offered (I6), and every figure of spec §3 is the Linux PC's, where the people named in the design's first paragraph are on Windows and analyse three times slower here. Answering yes moves I6 from known to due.

### Test gaps

- `tests/test_graph.py` and `tests/test_gui_api.py:2242-2310` hold no structured variable (I2). A flow test over `examples/structures` would have caught it.
- `tests/test_gui_compare.py` (32 tests) has none with a candidate carrying an error of its own, so neither answer to open question 1 is pinned; none saves between the read and the stamp (M6).
- `tests/test_variable_keys.py` pins `disagrees` case by case and never against the check, though its comments cite it; a table of pairs asked of both would close I3 for good.
- Nothing edits a plugin during a session, or changes what the poll does not stamp (I4, I5).
- `tests/test_gui_api.py:5119` asks `/api/type` of a structure only as it loaded (M5); the drift tests are for the panels that were found out.
- No test holds `State.counts` to `ddd check` (M1). The parity `p25` runs in a few minutes would be worth keeping: 57 broken cases, two policies.
- **The bench's blind spots:** the generator states no type, constant, section or raster, so `types` and `shared` measure 0 ms over 28 bytes (with them, `p24`: 49 and 33 ms, panels 0.1-0.9 s, plans 1.2-2.7 s); `open` skips `POST /api/open` (M14); `plan while analysing` lands in a large or a small component by the middle name's luck (I6); `declarable`, `compare` and `undo` are not measured; no figure is from Windows.

### Assessment

The core of what I was asked holds: for findings, the page is told what `ddd check` says, finding for finding over 119 runs, and for a comparison's differences and renames what `ddd compare` says, and the dictionary and the check list are the tool's own to the byte. The API does not fall over in any of the four states, its refusals name causes in most routes, and half way through an analysis is handled with more care than the problem usually gets. Where the page is told something the tool would not say, it is not a broken engine but the answers built around it: a verdict that leaves the project's own errors out under the command's own words, a graph that walks one of the dictionary's two lists and so draws the repository's own structured example with nothing connected, a panel rule of its own for silence that the check does not share, and a long-lived process meeting a tool designed around short runs, which shows as plugins never reloading and as a poll blind to what its last analysis did not read. All of these are small to fix; none is structural. "The GUI cannot disagree with the build" is true of the findings and untrue of the sentence people read first. Performance at size is good for what was measured and has one known cliff, a plan in a large component, which no budget covers and which costs 22-38 s here.

```candidates
14|I1|src/ddd/gui/compare.py:262|The Compare tab says can replace of a project ddd compare says cannot: the candidate's own errors take no part, against SPEC 4.1; two builds, one stopping at its read, read as can replace too
14|I2|src/ddd/graph.py:83|GET /api/graph walks dictionary.objects alone: examples/structures draws no arrow, and a mismatch on a structured variable paints none or a plain one
14|I3|src/ddd/variable_keys.py:178|The panel says typename disagrees where ddd check is clean, one side naming a type and the other spelling it, and both settlements are refused
14|I4|src/ddd/plugins.py:196|A plugin edited while ddd gui runs makes a new revision with the old code until restart; a module it imports is not even noticed
14|I5|src/ddd/gui/session.py:722|A change the poll cannot see leaves the page contradicting ddd check: a new file on a pattern (KNOWN), a plugin created or fixed, a build record rewritten
14|I6|src/ddd/variables.py:253|A plan in a large file takes 22-38 s idle at 100,000 declarations, 4.6 s at 35,000 where the page says 0.8, and holds other plans on the difflib lock (KNOWN)
14|M1|src/ddd/gui/derived.py:172|The page's totals count a disagreement once per file: 7 errors where ddd check says 4
14|M2|src/ddd/graph.py:177|A disagreement names the wrong variable where the analysis dropped a declaration above it, or vanishes from the arrow
14|M3|src/ddd/object_values.py:122|GET /api/values says the project declares no X of a structured variable, an object the analysis dropped and a curve of a structure, offered a button
14|M4|src/ddd/shared_plans.py:388|Plan refusals say no such entry where the file did not load, and engine words after a save, where the read route beside them says the truth
14|M5|src/ddd/gui/api.py:904|GET /api/type answers 500 for a save that still parses: KeyError and ValidationError, the one read route not tolerant of drift
14|M6|src/ddd/gui/compare.py:408|A baseline is stamped after it is read: a save in the window serves a stale verdict until the next change
14|M7|src/ddd/gui/session.py:686|An analysis that raises is invisible to the page: Analysing for good, or the last revision as current; against its spec (KNOWN in part)
14|M8|src/ddd/finding_routes.py:191|A finding leads to a panel that does not list it: a reader's init to the producer's grid, a duplicate's second entry to the first's panel, counted one of two
14|M9|src/ddd/gui/session.py:925|A missing include reads as the description not loading and the missing file loaded, in the state and in sentences (KNOWN for the route)
14|M10|src/ddd/gui/api.py:543|A component that does not parse is no module on the graph, against the module graph's spec (KNOWN)
14|M11|src/ddd/gui/session.py:566|A refused build record is told only on the start page, which ddd gui PROJECT never draws: defaults applied in silence
14|M12|src/ddd/declaration_plans.py:91|GET /api/declarable reads every producer's file to name it: 4.5-5.2 s at 100,000 declarations, not in the bench
14|M13|src/ddd/project_shared.py:502|A constant only a condition spells reads as used by nothing, and removing it compiles the object out with check clean (adds to pass 10 I10)
14|M14|src/ddd/gui/api.py:352|POST /api/open parses every description under the root before answering, about 1 s at 100,000 declarations; the bench's open goes round it
14|M15|src/ddd/gui/contract.py:1498|Untrue sentences in the contract the page's types publish: Always route null, has no screen yet, parsed and matched, every flow, never a hand-assembled dict
```

## Pass 15: the web GUI, the logic of the page

### Scope covered

Transcripts are under `SCRATCH/pass-15/`; line numbers are on the review tree (code at master `2b4bae6c`).

**Read in full, with line numbers:** `gui/src/api/` (`client.ts` 435, `signIn.ts` 87, `token.ts` 88, `types.ts` 96), `gui/src/state/` (`edits.ts`, `positions.ts`, `revisions.ts`), `gui/src/app/` (`App.tsx` 315, `useProjectState.ts`, `useRoute.ts`, `useDebounced.ts`, `useKept.ts`, `useLayout.ts`, `layoutWorker.ts`, `sheets.ts`, `updating.ts`), `gui/src/main.tsx`, and every non-test module of `gui/src/lib/` (33 files, including `objectValues`, `valuesHold`, `filesHold`, `undo`, `typing`, `refusals`, `kept`, `variableKeys`, `units`, `shared`, `projectUnits`, `projectTypes`, `declarations`, `findings`, `findingsWindow`, `files`, `route`, `pointer`, `canvas`, `layout`, `layoutAnswers`, `valuePlot`).

**Read because the logic lives there:** `screens/` `ValuesPage`, `UndoStrip`, `StartPage`, `VariablePanel`, `UnitPanel`, `TypePanel`, `UnitsPage`, `TypesPage`, `ConstantPanel`, `SharedPage`, `FilesPage`, `FindingsPage`, `ComponentPage`, `DeclarePanel`, `GraphPage`, `ComparePage`, `ProjectPage`; `components/` `ValuesGridView`, `ValuesPlotView`, `KeyChooser`, `VariablePanelView`, `UnitPanelView`, `DeclarePanelView`, `DimensionsField`, `FindingPanelView`, `UndoStripView`, parts of `ConstantPanelView` and `SharedAddView`; `ui/ComboBox`, `UnitPicker`. Server side: `session.py:260-735`, `object_values.py`, the plan, state, edit and undo handlers of `api.py`. Specs and "Left open" sections: `2026-09-24-gui-paste-design`, `2026-09-25-gui-plots`, `2026-09-23-gui-values`, `2026-09-22-gui-undo`, `2026-09-20-gui-other-keys`, `2026-09-22-gui-findings`, `2026-09-27-gui-constants`, `2026-09-28-gui-rasters`, `2026-09-29-gui-files`, `2026-09-30-gui-large-projects`, `2026-10-07-gui-token-out-of-cookie`, `2026-10-08-gui-journeys-every-action`, `2026-10-21-gui-journeys-remaining`.

**Tests:** the test names of `state/`, `api/` and most of `lib/` (not `canvas`, `findingsByRow`, `layout`, `neighbours`, `paths`, `pointer`, `projectTypes`, `shape`, `shared`, `sheets`, `start`, `units`, `updating`, `values`); the bodies of `state/revisions.test.ts` in part, `lib/refusals.test.ts`, the `rawOf` and `typedNumber` blocks of `lib/objectValues.test.ts`.

**Ran:** throwaway Vitest over the real modules (`numbers.txt`, `logic.txt`, `hold.txt`: a random walk of `valuesHold` against a model of file, analysis and answers). Python probes of a real `ddd gui` with what the page sends (`probe_server.txt`, `probe_noop.txt`, `probe_lag.txt`, `probe_spaces.txt`, `probe_body.txt`). Real pages, Edge driven by Playwright against a real server: `s1*`, `s2*`, `s3`, `s4*`, `s5*`, `s6`, `s7*`, `s8*`, `s9`, `s10`, `s11`, `s12`, `s13`, `s14`, `s15`, `s16`.

**Not covered:** `SectionPanel`, `RasterPanel` (grep only, pass 3 I6 has them as copies), `TypePanelView`, `CompareView`, `FileActionsView`, `VariableKeysTable`, the stories, `generated/`; test bodies beyond those named (pass 23). The project's own `vitest` and `e2e` were not run (passes 23, 16). Firefox and Safari not tried. I2's `offline` event was dispatched on the window, not produced by really losing a network. I tried the classic "one long poll per tab, six connections per host" stall: 8 tabs, then 70 long polls from one page, never delayed a plain ask (`s5b`, `s5c`, `s5d`), with 6 connections on the machine; identical poll addresses look serialised by the browser's HTTP cache lock (inferred, not established). No finding.

### Strengths

- **No non-idempotent request is sent twice.** `sentAgain` (`client.ts:92`) resends only a GET, only on a rejected fetch; `retry: false` for queries (`main.tsx:16`), none for mutations; the one resent POST, `/open`, is documented with its cost. A double press of Apply sent at most two POSTs, and the second was refused by its spent fingerprints: `200,409`, file right (`s11_misc.txt`, first run).
- **Every wrong request I could build ended in a refusal, not a write.** Infinity, NaN, `1e400`, `0x10` as raw text, fractional counts, a bad alignment, a bad event, a name with spaces, a dimension of `0`: all refused by the server, with nothing planned (`probe_server.txt`, `probe_spaces.txt`). Limits with `Infinity` are refused 400, so `limitsRaw`'s bad text never reaches a file. The fingerprint is why a stale page is safe: a plan over moved bytes is refused.
- **The values grid's hold holds.** 4,000 random walks, 56,000 steps of Apply, undo, landing and answer: the grid never showed other than the file outside the lag `valuesHold.ts:96-100` documents (`hold.txt`). Reads between an Apply and its analysis come from the file as it stands (`probe_lag.txt`), so a panel's text does not go back through the old value.
- **Plans cannot cross keystrokes.** Keys are by content and revision, `planShown` drops an answer for a request the fields have left, `gated` closes on the very render a revision lands. An answer of another revision is never drawn in the Findings window (`arrivedPages`).
- **Route parsing round-trips.** 27 hostile spellings (`%`, `&`, `+`, `#`, `/`, emoji, spaces, tab, newline) through 8 route shapes: 0 differences; half-written addresses fall back to the bare tab (`logic.txt`).
- **The token logic is sound for what it claims.** Read per request, `credentials: "omit"`, secret removed from the address before it is sent, a 401 clears only the token it carried. What is left is in its plan's "What was left open".
- **`1.0` against `1` in limits does not offer a change:** `same_value` holds on the settle path (`probe_server.txt`).

### Issues

#### Critical

- **C1. A value picked for one key is carried to the next key that disagrees, where the panel plans it and Apply writes it.**
  `gui/src/screens/VariablePanel.tsx:162-167` (`selected` moves by itself while `picked` is `undefined`), `:184` (`settledRaw(chosen, startingRaw(reply, selected))`: `chosen` belongs to no key), `:251-254` (kept on purpose after an Apply), `:211-219` (cleared only by `select`), `gui/src/lib/variableKeys.ts:333`.
  `KNOWN` in part: `2026-09-20-gui-other-keys.md`, "Left open", has "an outside edit that makes another key disagree can re-open a chooser on what was typed for the last one". It needs no outside edit, and it is a live plan and an Apply, not only a field.
  Trigger, on a real page: a variable disagreeing on two keys, its panel open by itself on the first (`VariablePanel.tsx:158-161`, "a reader could settle it from there in one press"). The reader picks a value and applies. When the analysis lands the panel moves itself to the next row, on the last pick.
  (a) `unit` and `volatile` disagree, pick `rpm2`: the next row previews `"volatile": "rpm2"` in both files, `Apply to 2 files`. Pressed, both files stop loading: `schema: Input should be a valid boolean` (`s2_chosen_leaks.txt`).
  (b) `datatype` and `unit` disagree, no units file, pick `uint32`: the field then reads `Unit of Disagree = uint32`, the preview `"unit": "uint32"`. Pressed, both declarations state that unit, the project has 0 errors, the `definition-mismatch` is gone, and no finding speaks of the unit (`s2b_chosen_leaks_silent.txt`).
  Expected: the next row on the producer's value, as a row opened by itself starts everywhere else. Not unseen: the field and Show changes say it, Undo puts it back. But the line above Apply names files only, and pressing Apply again to take the next disagreement is what the panel teaches, so the wrong unit in (b) leaves by the same press as the right one. `e2e/keys.spec.ts:123` stops at one disagreeing key, and I found no journey with two.
  *Change:* `chosen`, `typed` and `edited` held as `{key, value}` and ignored while `key !== selected`, as `stale` is already (`:149`). S.

#### Important

- **I1. Text typed into a chooser and left there is not what Apply writes: the earlier value is written, and no word says so.**
  `gui/src/ui/ComboBox.tsx:45-50` ("text typed and left is never a choice"), `gui/src/screens/VariablePanel.tsx:193-194` (the request is made from `target`, never `typed`), `:403`; `UnitPanel.tsx:256`, `TypePanel.tsx:336`. It contradicts `gui/src/lib/typing.ts:13-14` ("never one for text the reader has since typed past"): the field's text is simply not part of the request, so `planShown` cannot see it.
  Trigger (`s1b_typed_then_apply.txt`, Show changes open so that the list does not cover the button): field reads `rpm`, type `km/h`, press Apply. The field goes back to `rpm` on the press and `rpm` is written. By keyboard the same: Tab, Tab, Enter. In the Units tab's rename: `Volt` chosen, `Kilovolt` typed, Apply renames to `Volt` (`s14_more.txt`). With Show changes closed the open list happens to cover Apply, and a press there takes the As typed entry (`s1_typed.png`): the wrong result depends on the panel's height. While the text is typed, the table above still says `RPM will change`, and the consequence names files, not the value.
  *Change:* while `typed` is not the settled value's label, withhold Apply as `planShown` withholds a plan (a pending state), or commit on blur (open question 3). S. The neighbouring `KNOWN` half: a resting pointer's entry taken by Enter or Tab in place of typed text (P19c-12, `2026-10-21-gui-journeys-remaining.md`).

- **I2. A browser's `offline` event stops every read and every write of a page whose server is on loopback, with no word, and a pressed Apply goes out when the network returns.**
  `gui/src/main.tsx:15-17`: the `QueryClient` leaves TanStack's default `networkMode: "online"` (`query-core/src/retryer.ts:53`, `onlineManager.ts`). Nothing in `gui/src` or `e2e/` mentions it.
  Trigger (`s16_offline.txt`, the window's `offline` event dispatched on a real page, the server answering throughout): Apply pressed. No POST leaves, the file is unchanged, the cells and Apply are disabled, no alert. Back to the component: `Reading the file…` for as long as it lasts. Ten seconds later the `online` event: `POST /api/edit` goes out on its own and the value is written. The raw long poll goes on meanwhile, so the state moves and nothing says why the screens do not.
  Likely on a laptop whose Wi-Fi drops, or a bench PC unplugged from the network; a machine with a virtual adapter may never fire it. In effect a press deferred without limit: the fingerprint stops a stale one, a fresh one lands long after the reader gave up on it.
  *Change:* `networkMode: "always"` for queries and mutations, one line each, with a journey dispatching the event. S.

- **I3. Open a second project in one tab: every other tab keeps naming the first, over the second's contents, and writes into the second.**
  `gui/src/app/App.tsx:68-70` (`session` asked once, invalidated only by the tab that opened), `:169`, `:189`, `:297`; `gui/src/app/useProjectState.ts:26-38` (follows the one server state, whichever project). `State.project` is on the wire (`src/ddd/gui/api.py:423`) and the page never reads it.
  Trigger (`s3_two_tabs.txt`, `s3_tab_b.png`): tab B on `ProjectOne`; tab A opens `ProjectTwo`. Tab B's heading and masthead still read `ProjectOne`; its Table lists `AlphaTwo` from `two/a.ddd.json`; a press leads to that component under the masthead `ProjectOne`, and what its panels plan and apply is the open project's, the second (read off: the server holds one). `project={opened.path}` also files the canvas's positions under the wrong project. The session is one project at a time, so this is any two tabs, not a corner: the spec treats a second window as ordinary (`2026-09-30-gui-large-projects-design.md`).
  *Change:* name the page from the state; ask `["session"]` again when `state.project` differs from `opened.path`. S.

- **I4. A rename the page plans cannot be applied past about 55,000 declarations, and the reader is told the server has stopped answering.**
  `gui/src/api/client.ts:331` (the whole plan goes back as the body), `src/ddd/gui/server.py:84` (`MAX_BODY`, 1 MiB), `tools/bench_gui.py:311` (the bench measures `rename plan` and never applies it).
  Trigger (`probe_body.txt`, generated `many` projects, unit `rpm`): 35,000 declarations, 696,483 bytes, applied. 60,000: plan answered in 5.9 s, 1,193,873 bytes, `413`. 100,000: 1,992,781 bytes, connection aborted. In a real Edge a POST of that size rejects with `Failed to fetch` (`s10_big_post.txt`), so the panel reads `The change was refused: ddd gui is not answering`, while the server is fine and a POST is rightly not resent. Against the budgets "at every size up to 100,000 declarations" (`2026-09-30-gui-large-projects-design.md` §3). Bytes count paths, so the exact threshold moves with the directory.
  *Change:* a body limit for `/api/edit` that fits what its own plans make, or an edit that names the plan rather than repeating it (the second also serves pass 3 I8). S to M.

- **I5. There is no error boundary: any throw while drawing empties `#root`, the whole page, with no message.**
  `gui/src/main.tsx:26-32`. `KNOWN`: `2026-09-17-web-gui-skeleton.md:6148`, parked for "milestone 8" and not taken up there; `2026-09-25-gui-plots.md`, "A spread `Math.min(...values)` throws above about 125 000 arguments ... *Costs:* nothing this tool can reach", which is untrue.
  Reproduced twice. An object of 130,000 elements, by its address: `RangeError` in `gui/src/lib/valuePlot.ts:80`, `#root` has 0 children, within 170 s (`s7_large_grid_130000.txt`); SPEC allows 10,000,000 elements. A unit `"\ud800x"` in a file (`ddd check` loads it): `URIError` from `hrefOf` (`lib/route.ts:106`) reached through `routeHref` on `ComponentPage`: that component's page blank, every time (`s9_surrogate.txt`). Rare triggers both; the structure is the finding, and it has bitten before: `client.ts:145-146` records one more instance ("React unmounted the whole page"), patched at the site. Typed state goes with it, and since no `.tsx` runs under a unit gate, the next throw is found by a reader.
  *Change:* one boundary inside the masthead, keeping `stopped` and the address, saying what failed and offering a reload. S.

#### Minor

- **M1. One answer of the long poll that is not 200 ends the follow for good, under a sentence that says to ask again.** `gui/src/state/revisions.ts:50`, `gui/src/app/useProjectState.ts:34-36`, `App.tsx:307`, `api/client.ts:128`, `:147`. Trigger (`s12_follow_ends.txt`): one `503` carrying the server's own `BUSY` sentence ("ask again in a moment"; the spec has `Retry-After: 1`): 0 asks afterwards in 32 s; the page stays on `3 errors, 1 warning · updating` where the server says 5 errors; Apply stays enabled, so its stale plans meet refusals. The real cap reached at load does the same to `/api/session`, one ask and a dead page (`s4b_cap_at_load.txt`). A body cut half way reads as `not-json` and ends it too (`logic.txt`). An open tab keeping its connection is not touched by the cap (`s4_cap_ends_follow.txt`), so this is rare: pass 12 M3 is the likeliest trigger. Pinned as design by `revisions.test.ts:154` with a `409`, `start.spec.ts:133` for the banner. *Change:* a 5xx is treated as an unanswered ask, the banner lifting at the next answer. S.
- **M2. A stale refusal is stamped with the revision on screen when its answer arrives, which can be the revision that noticed the change: the panel then holds it for a revision that never comes.** `screens/VariablePanel.tsx:265`, `:311`, `ValuesPage.tsx:235`, `UnitPanel.tsx:172`, `ConstantPanel.tsx:196`, `SectionPanel.tsx:189`, `RasterPanel.tsx:184`, `TypePanel.tsx:245`, `UnitsPage.tsx:82`, `FilesPage.tsx:229`, `FindingsPage.tsx:196`, `UndoStrip.tsx:56`: `revision` read in `onError`, from the latest render. Trigger (`s15_stale_stamp.txt`, the POST's answer held 3 s to open the window): revision 1 to 2, the refusal arrives at 2 and stays: `A file changed on disk ...`, no Apply, 8 s later the same, while a plan would answer. Clears only with an outside change or a reload. The natural window is one round trip. *Change:* note the revision in `onMutate`, or the plan's own. S.
- **M3. After one stale refusal, that action's later plan refusals are not shown at all.** `screens/UnitPanel.tsx:204`, `ConstantPanel.tsx:228`, `SectionPanel.tsx:222`, `RasterPanel.tsx:217`, `VariablePanel.tsx:342`. `KNOWN` for `UnitPanel` (`2026-09-22-gui-findings.md`, "Left open"). Trigger (`s6_stale_then_silent.txt`): Value `abc` reads its refusal; after one stale Save and its landing, Value `abc` reads nothing: no sentence, no Save. `lib/refusals.ts:47` `refusalShown` has the right precedence and `refusals.test.ts:37` pins it, but only `FilesPage` calls it. *Change:* the other five call it. S.
- **M4. A cell retyped to its own value offers an Apply that changes nothing and leaves an entry on the undo stack.** `lib/units.ts:161-165`, `components/ValuesGridView.tsx:293`, `lib/undo.ts:162`, the server's plan answering a change with no hunk (`object_values.py:332`). `KNOWN` for a type's key (P19b-13, `2026-10-08-gui-journeys-every-action.md`), not for the grid. Trigger (`s8b_own_value.txt`, `probe_noop.txt`): `Sets element 1 of BlockI to 1. Changes 1 file`, an empty diff; Apply: the file byte for byte as it was, an analysis, `Undo element 1 of BlockI`, whose strip says `Puts back 1 file`. *Change:* a change with no hunk is no change, on the server. S.
- **M5. A physical value typed into a float object writes the arithmetic's tail, and what is typed never reaches the server.** `lib/objectValues.ts:33-37`, `api/client.ts:366`. Adds to pass 3 M4 and C1. Trigger (`s8b_own_value.txt`): `BlockF` (`float32`, factor 0.1, file `3`, reads `0.3`): typing `0.3` plans `3` to `2.9999999999999996`; `0.7` plans `7` to `6.999999999999999`, under `Sets element 1 of BlockF to 0.3`. Each cell of a physical paste likewise, which is why `client.ts:388-393` counts "about 2 500 that carry decimals". Typing `1.0` over a file's `1.0` plans it to `1` (`s8_grid_states.txt`). `objectValues.test.ts:230` pins it as "keeps the exact raw count". *Change:* with pass 3 C1's move to text; until then round to the datatype's digits. S.
- **M6. In Physical, the grid's default, a value of more than 12 significant digits under a linear conversion is shown as another number.** `lib/objectValues.ts:25`, `:41-43`, `components/ValuesGridView.tsx:211`. Trigger (`s8_grid_states.txt`, `numbers.txt`): raw `1234567890123`, factor 1, reads `1234567890120`; `1.23456789012345` reads `1.23456789012`. Well below 2^53, so past pass 3 C1's reach. No sign in the cell; Raw shows the truth. Copying what is read loses it. *Change:* the digits the value needs, or say it. S.
- **M7. The grid's columns follow the axis's breakpoints, not the object's shape, and a missing cell reads `0`.** `lib/objectValues.ts:265-271`, `:276-283`, `components/ValuesGridView.tsx:207`; against `src/ddd/object_values.py:197` ("drawn as written"). Trigger (`s8_grid_states.txt`): a curve of 6 over an axis of `size` 6 stating 3 points draws 3 cells, values 4 to 6 unreachable, while the hint says `Paste 1 row of 6`, and no finding on that grid says why. A curve of 2 over an axis stating 4 draws 4, the last two `0`. A short `init` `[1, 2]` of 4 reads `1 2 0 0`, cells the file does not hold. *Change:* columns from `shape`, a breakpoint only labelling; a hollow cell for what is not stated. S.
- **M8. A keystroke in a large grid stalls: the whole table and the plot are drawn again, the plot quadratically.** `lib/valuePlot.ts:103-104` (`Math.min(...xs)` and `Math.max(...xs)` per point), `components/ValuesGridView.tsx:248`. Key press to the next frame (`s7b_grid_keystroke.txt`, `s14_more.txt`): 16×16 33 ms, 256 cells 90 ms, block 1024 about 350 ms, 64×64 about 300 ms, block 4096 about 1.7 s, block 10,000 about 4.7 s; against "Typing or scrolling stalling: never over 100 ms" (`2026-09-30-gui-large-projects-design.md` §3). `plotted` alone: 875 ms at 10,000, 16.8 s at 40,000 (`logic.txt`). Typical maps are fine. The bench does not type into a grid. *Change:* the two extremes once; a memo on the plot; a table of cells that does not rebuild on every keystroke. S to M.
- **M9. A spreadsheet in a comma locale cannot paste a block holding one value of three decimals, and the advice given does not help.** `lib/objectValues.ts:155`, `:226`; `lib/variableKeys.ts:486`. By design in part (`2026-09-24-gui-paste-design.md` §4.2). Trigger (`numbers.txt`): `0,125 0,250 0,500` refused, though no grouping starts at `0`; `0,5 1,250 2` refused; "paste the column unformatted" leaves a French spreadsheet writing the same comma, and a typed cell refuses the comma too. Min `1,5` says `A range needs a minimum and a maximum`, of a field that holds one. *Change:* a leading `0` is no grouping; a one-press choice of what the comma means. S.
- **M10. A stray space typed into a variable's or a type's unit is written, where the Units tab refuses the very spelling.** `lib/units.ts:142`, adds to pass 3 I1. Trigger (`s14_more.txt`, `probe_server.txt`): `V ` and Enter writes `"unit": "V "`; `unit-plan` refuses `'rpm ' has spaces around it`. Without a units file no finding says so, and the project holds two spellings of one unit. *Change:* trim on the page, judge in `settle`. S.
- **M11. Pressing the open project on the start page empties the undo stack and analyses it again.** `screens/StartPage.tsx:29`, `src/ddd/gui/session.py:360`. Trigger (`s11_misc.txt`): `Undo element 1 of BlockI` shown; Projects, the same project: no Undo, in every tab, nothing said. The list does not mark which one is open, and at 100,000 declarations this costs 45 s here. *Change:* opening what is open goes to it. S.
- **M12. A finding whose pointer moved closes its panel saying it is no longer reported.** `lib/findings.ts:139-141`, `src/ddd/gui/derived.py:149` (the key holds the pointer). Trigger (`s11_misc.txt`): a declaration above it removed elsewhere: `This finding is no longer reported.`, while the server reports it at `interface[1]`. *Change:* key by the object's name where there is one, or do not say so where the same words remain. S.
- **M13. `typedNumber`'s grammar is JavaScript's.** `lib/objectValues.ts:104-106`, `lib/variableKeys.ts:491-494`, `lib/typing.ts:15-17`. `0x10`, `0b101`, `0o17`, `Infinity` pass (`numbers.txt`), where Constant's Value refuses hex in the json parser's words: no field agrees with another on what a number is. `Infinity` passes the page's guard and is refused in Python's word, `inf`; `sameRequest` makes `Infinity`, `-Infinity` and `NaN` one request, so `-Infinity` reads `inf`'s refusal. Nothing wrong is written (pass 3 C1 has the hex mask). *Change:* one grammar, with C1's text. S.
- **M14. Stale sentences.** `lib/undo.ts:131` and `screens/FindingsPage.tsx:57` say the one fix the tab offers is `missing-id`; `src/ddd/finding_fixes.py:71-74` also offers reconciliations on `definition-mismatch`.
- **M15. Still open, in this area, already recorded.** `KNOWN`, each read off the code as still so, graded Minor: a kept answer not dropped by a refusal (P19c-15, `lib/kept.ts:16-25`); Apply drawn beside a plan's own refusal where a refetch fails (P19b-24 and its siblings, `components/ValuesGridView.tsx:270-305`, `UnitPanelView.tsx:242-258`: a press meets `stale`, harmless); "the start page's list can stay held"; "a panel whose read of the units fails says it is reading, for good"; the stale decision inline in thirteen places (`lib/refusals.ts:29` unused but for one).

### Status of the 2026-09-15 findings in this area

None: that review had no pass on the page's logic.

### Open questions

1. **A block one row and one column larger than the object is read as having a header, and its first row and column are dropped unread.** Spec §3 of `2026-09-24-gui-paste-design.md` accepts the cost ("the preview is what catches it"). Trigger (`numbers.txt`): `10 20 30 40 / 50 60 70 80` into a curve of 3 stores `60 70 80` under "Replaces every value", Show changes closed. Keep it, or say in the sentence that a header was dropped, or compare it with the breakpoints.
2. **Ctrl-V into a focused cell replaces every value by design (spec §2), so one number pasted is refused and what the cell held typed is lost** (`s8_grid_states.txt`). A single value setting the cell it lands in would add one rule. Yes or no changes `pasted` and the hint.
3. **What does text left in a chooser mean (I1)?** Withheld Apply keeps "text typed and left is never a choice"; commit on blur drops that rule and changes `ComboBox` for every field.
4. **What should the page do with a 5xx on its long poll or its session (M1)?** Ask again with a delay, or stay as it is: the journeys pin the banner, and the answer changes them.

### Test gaps

- `VariablePanel`'s reader state: no journey settles two disagreeing keys (`e2e/keys.spec.ts:73-130` has one), so nothing reaches C1: `chosen` carried across keys is what the screen does today, and no gate looks.
- No journey leaves text in a chooser and presses Apply (I1).
- No journey opens a second project with another tab on the first (I3); `start.spec.ts:322` is the only `newPage`, for a stranger.
- Nothing dispatches `offline` (I2).
- The benchmark plans a rename and never applies it (I4).
- No render-throw journey, and no boundary to test (I5).
- `revisions.test.ts:154` proves the follow ends on a `409` that cannot occur on an open project; nothing asks what follows a `503` (M1).
- `refusals.test.ts:37` pins a fall-through only one screen has (M3).
- `valuePlot.test.ts` holds small tables only: no size, no cost, no limit (M8, I5).
- `objectValues.test.ts:349-371` never types hex, `Infinity` or an exponent; `typing.test.ts:17-50` never compares non-finite requests (M13).

### Assessment

The page's central design holds up better than its prose suggests it needs to: fingerprints and plans keyed by content make most races end in a refusal, nothing non-idempotent is resent, and the values hold survived a random walk unmarked. What fails is the state that lives in `.tsx` and in library defaults, where no unit gate reaches: a pick that outlives its key and primes a wrong write, a field's text that is not part of the request, a heading that never re-reads which project is open, and TanStack's "online" mode silently suspending a loopback tool. These are short fixes. The pattern is the finding: careful reasoning concentrated in `lib/`, which is sound, and the defects one layer up, in state such as `VariablePanel`'s eleven `useState`s, whose relations nothing tests; the "no decision in a `.tsx`" rule (pass 3 I7) is not a style point but where the page's only Critical sits.

```candidates
15|C1|gui/src/screens/VariablePanel.tsx:184|A value picked for one key is carried to the next that disagrees: "volatile": "rpm2" stops two files loading, "unit": "uint32" loads with no finding (KNOWN in part)
15|I1|gui/src/ui/ComboBox.tsx:50|Text typed in a chooser and left is not what Apply writes: km/h typed, rpm written, no word, against planShown's never for text typed past
15|I2|gui/src/main.tsx:16|TanStack's online mode: an offline event stops every read and write of a loopback page in silence, and a pressed Apply goes out when the network returns
15|I3|gui/src/app/App.tsx:68|A second project opened in one tab: other tabs keep the first's heading over the second's contents and write into it
15|I4|gui/src/api/client.ts:331|A rename the page plans cannot be applied past about 55,000 declarations: body over 1 MiB, told ddd gui is not answering; the bench never applies it
15|I5|gui/src/main.tsx:26|No error boundary: 130,000 elements or a lone surrogate empties #root, against Costs nothing this tool can reach (KNOWN)
15|M1|gui/src/state/revisions.ts:50|One non-200 on the long poll ends the follow for good under a sentence saying ask again; the session's one ask the same
15|M2|gui/src/screens/VariablePanel.tsx:265|A stale refusal is stamped with the revision on screen when it arrives, and is then held for a revision that never comes
15|M3|gui/src/screens/UnitPanel.tsx:204|After one stale refusal, that action's plan refusals are not shown at all, in five panels; refusalShown has it right and one screen calls it (KNOWN for one)
15|M4|gui/src/lib/units.ts:161|A cell retyped to its own value offers an Apply that changes nothing and leaves an undo entry (KNOWN for a type's key)
15|M5|gui/src/lib/objectValues.ts:37|A physical value typed into a float object writes the arithmetic's tail: 0.3 plans 3 to 2.9999999999999996; typed text never reaches the server
15|M6|gui/src/lib/objectValues.ts:42|In Physical a value past 12 significant digits under a linear conversion reads as another number: 1234567890123 reads 1234567890120
15|M7|gui/src/lib/objectValues.ts:268|Grid columns follow the axis's breakpoints, not the shape, and a missing cell reads 0: three of six values unreachable, four cells for two
15|M8|gui/src/lib/valuePlot.ts:104|A keystroke in a large grid stalls, the plot quadratic: 350 ms at 1024, 1.7 s at 4096, against never over 100 ms
15|M9|gui/src/lib/objectValues.ts:155|A comma locale cannot paste a block with one three decimal value, 0,125 included; the advice does not help
15|M10|gui/src/lib/units.ts:142|A stray space typed into a unit is written where the Units tab refuses the spelling
15|M11|gui/src/screens/StartPage.tsx:29|Pressing the open project on the start page empties the undo stack and analyses it again, in silence
15|M12|gui/src/lib/findings.ts:140|A finding whose pointer moved closes its panel saying it is no longer reported
15|M13|gui/src/lib/objectValues.ts:105|typedNumber's grammar is JavaScript's: hex, binary, octal, Infinity pass; no two fields agree; sameRequest makes the non-finite one request
15|M14|gui/src/lib/undo.ts:131|Stale sentences: the one fix the tab offers is missing-id, where definition-mismatch has fixes too
15|M15|gui/src/lib/kept.ts:16|Still open and recorded: P19c-15, Apply beside a refetch's refusal, the held start list, a panel reading for good, the stale decision inline (KNOWN)
```

## Pass 16: the web GUI, the screens as a user meets them

### Scope covered

Transcripts and pictures are under `SCRATCH/pass-16/`: `logs/` (one per script), `shots/` (285 pictures), `s*.mjs` (the scripts), `tmp/` (the probe projects). Line numbers are on the review tree (code at master `2b4bae6c`).

**Read in full, with line numbers:** `gui/src/screens/` (all 19), `gui/src/components/` (every view, not the stories), `gui/src/ui/` (8), `gui/src/styles/` (3), `gui/index.html`, `gui/public/pressable.css`, `gui/src/app/App.tsx`; line by line, as asked, `SectionPanel`, `SectionPanelView`, `RasterPanel`, `RasterPanelView`, `TypePanel`, `TypePanelView`, `ComparePage`, `CompareView`, `CompareTableView`, `FilesPage`, `FileActionsView`. From `lib/`: `declarations.ts`, the chooser half of `variableKeys.ts`, `consequence` in `units.ts`, `noRouteReason`. React Aria's `useTypeSelect`, `GridKeyboardDelegate`, `useGrid`, its `Table`. The "Left open" sections of the undo, types, declarations, compare, sections, rasters, files, large-projects and both journeys plans.

**Ran:** `ddd gui` on copies of `examples/demo`, `vocabulary`, `inconsistent`, `structures`, on generated projects of 2,000, 10,000 and 35,000 declarations and on small probe projects, driven with real key and mouse events by 46 Playwright scripts in headless Edge at 1280×800, and also 1920×1080 down to 320 wide, forced colours and reduced motion. Of the 285 pictures, 107 read at full size and 178 on contact sheets (`SCRATCH/pass-16/sheets/`, nine to a sheet). No `pageerror` in any run; the console holds only expected 4xx answers and, after a stop, refused connections. The Playwright journeys were not run again: the coordinator's baseline (`SCRATCH/baseline/e2e.txt`, 294 passed) stands.

**Not covered:** Firefox, Safari, a real screen reader (the accessibility tree was read instead, `logs/s30.txt`; React Flow nests arrow buttons in `role="img"`, whose effect I could not hear), touch, the stories.

**Each job, as somebody who has not read the code meets it:**

| Job | Where | What happens |
|---|---|---|
| Fix a finding that has a fix | demo with a drifted unit | Easy and good. Findings, a row, `Apply this unit to 1 other declaration of 'ValueE'`, the real diff, `Apply to 1 file`, the row goes, Undo appears (`212_fix_row_1`, `214`, `215`). |
| Fix a finding that has none | `inconsistent` | `Open SharedValue`, then only "Remove from ComponentA". Doable (remove, then Add a declaration), nothing suggests it, a writer cannot be turned into a reader (`16`, `25`, `341`). |
| Fix a file that does not parse | demo, half-saved component | Not from here, and the page does not say where the error is: I8, I9. |
| Rename a unit | vocabulary | Easy. Row, type a spelling, an `As typed` entry or Enter, a diff of every file, Apply, the panel follows, Undo appears (`34`, `36`, `38`). At 35,000 declarations it works, slowly and silently: M17. |
| Change a value | demo | A curve: yes, and well worded (`75`, `76`). A map: typing fails: C1. Its Apply is off-screen: I2. A scalar: there is no way: I4. A paste: works. |
| Add a declaration | demo | A name the project has: easy. A new one: stuck until you guess that "Volatile" wants an answer: I6. At 35,000: five seconds a key: I7. |
| Undo | demo | Easy and clear: it names the edit, shows the lines, says `Put back 1 file`; refused, it says which file changed (`217`, `219`). |
| Compare against a delivery | demo | You must already know what a "dumped dictionary" is and that `ddd dump` makes one; the page does not say (pass 4 I1), and has no file picker. A relative path works. The verdict and the renames read very well (`80`, `90`, `91`). Leave the tab and it is gone: M2. |
| Empty project | no includes | Graph an empty grid, Table one line, Files two buttons: M13. |
| Project with errors | `inconsistent` | Good: red arrow, badges, worst first (`10`, `13`, `14`). |
| A file that does not parse | demo | Graph loses every arrow under a sentence about a "dictionary"; Table names no broken file: I9. A panel elsewhere then says something false: I10. |
| Lost server | demo | Banner in 0.5 s, controls disabled, the right instruction (`150`). Graph alone gives wrong advice: M12. |

### Strengths

- **The plan, preview and undo model is the best thing on the page, and a newcomer gets it at once.** Every write names its files, shows the real lines on request (`36`, `214`, `146`), is applied by one button, and shows up as an Undo button that says what it would undo. The refused cases read well too: `user_interface.ddd.json changed on disk since it was written. Nothing was put back; the page shows the files as they are.` (`219`).
- **Refusals are in plain, specific sentences.** `event 1 is already claimed by raster '10ms'`, `3 is not an alignment a section may state ... a power of two, written as a whole number`, `components/controller.ddd.json is part of this project already: the pattern 'components/*.ddd.json' brings it in`, `'measuremint' is not a kind: measurement, parameter, ...` (`logs/s22.txt`, `s27.txt`, `s11b.txt`). Add a file informs of the errors a file brings rather than refusing (`304`).
- **A disagreement jumps out of the Graph.** A red arrow, a tooltip naming check and values, one press to the panel already on the disagreeing key, one more to settle it (`210`, `220`, `222`).
- **The chooser wording is thought through.** `produces / reads / keeps to itself`, `not one of this project's units`, `will change` beside the cell that would, `Nothing to change`.
- **Lost server, sign-out and first analysis are handled.** Banner 533 ms after the stop, every write control disabled (`logs/s13.txt`); an old tab after a restart says `Open the address ddd gui printed in its terminal.` (`156`); `Analysing the project…` in 0.7 s where the graph takes 17 s at 35,000 declarations (`180`, `logs/s16.txt`).
- **The long tables hold up.** 1,166 components: 21 rows in the document. 43,750 findings: 36 rows. A unit stated in 4,376 places: panel in 517 ms. A rename across 1,167 files applied, Undo in 6.5 s, `Updating the findings…` until 24 s, right throughout (`logs/s16.txt`, `s28.txt`).
- **Semantics and text contrast are sound.** Landmarks, `aria-current`, labelled fields, `aria-pressed`, `role="status"` on refusals, `aria-label` on every grid cell, arrows reachable by Tab with their text as a tooltip (`logs/s30.txt`, `173`). Every text colour pair is AA, the lowest 4.92:1 (`logs/contrast.txt`). Fix and Undo can be done by keyboard alone, 20 and about 7 presses (`logs/s37.txt`). A dead-looking screen was never met: no render error in 46 scripts.
- **The five panels pass 15 left to me hold no logic error beyond what is listed.** Their copies (pass 3 I6) behave alike; the differences I met are M4, M5, M6.

### Issues

#### Critical

- **C1. A number typed into a cell of a map or a two-dimensional block loses digits: the table's type-to-find takes them, the focus jumps to a row, and what is left is planned and written.** `gui/src/components/ValuesGridView.tsx:196` (React Aria's `Table`), `:214-232` (the cell's `onKeyDown` takes Enter alone); `gui/node_modules/react-aria/dist/private/selection/useTypeSelect.mjs:49-70`, `grid/GridKeyboardDelegate.mjs:233-255`; `react-aria-components/dist/private/Table.mjs:376` drops `disallowTypeAhead` before `useTable`, so no prop turns it off.
  A printable key in a cell bubbles to the grid, whose type-to-find looks for a row label starting with that character; found, it moves the focus there and calls `preventDefault`, so the digit never reaches the cell. Row labels of a map are its y axis's breakpoints, of a block its indices: digits.
  Real key events, `logs/s21d.txt`, `s21b.txt`, `s21c.txt`, with `examples/demo`'s own `MapA` (rows 0, 30, 70, 100, Physical): double-click a cell, type `20`: cell reads `2`, focus on the row header `0`, sentence `Sets element 1, 2 of MapA to 2 %. Changes 1 file` with Apply (`shots/247_mapa_typed_20_full.png`). Pressed, the file holds raw `4`. Likewise `5.1` plans 5, `6.03` plans 6, `40` plans 4, `50` plans 5, `27` plans 2, `2.75` plans 2, `9.7` plans 9. `1`, `12`, `13`, `13.5`, `3`, `7`, `70`, `0`: nothing enters, and the focus is on another row (`246`). Raw the same. A 16×16 map over 0, 10, ..., 150: every digit `0` to `9` jumps; only `-` and `.` enter. A 4×4 block: digits `0` to `3` jump, `4` and `5` enter. A curve or a single-row block has one row, named after the object, so digits work and a letter jumps.
  Cause confirmed: with printable keys kept from the grid, `13` types and plans correctly (`logs/s36.txt`).
  Against `docs/command_line_interface.rst:330-331` ("One cell is changed at a time, previewed") and the job this tab exists for. Not seen by any gate: `e2e/values.spec.ts` sets cells with `.fill()`, 13 times, and no journey in `gui/e2e` ever types into a field key by key.
  *Grade:* the cell and the sentence do show the short number and Undo restores it, as with pass 15 C1, which is graded the same way; the wrong number is one Apply away, on the tool's own demo map, and that Apply is off-screen (I2). If verification weighs the preview more, it is the first Important; either way it is the first thing to fix.
  *Change:* `event.stopPropagation()` for one-character keys in the cell's `onKeyDown`, or a plain `<table>` for the grid, with a journey that types with `pressSequentially`. S.

#### Important

- **I1. A cell shows six characters, cut from the right with no sign, so a larger number reads as a smaller one.** `gui/src/styles/ui.css:763-773` (`width: 5em`), `gui/src/components/ValuesGridView.tsx:214-219`. Trigger, `uint32` block `[123456789, 4000000000, 42, 1000000]`: the cells read `123456`, `400000`, `42`, `100000` (`233`; `clientWidth` 66 against `scrollWidth` 91, 99, 66, 75, `logs/s20.txt`). `float64` `[0.1234567890123, 1234567.125, -0.000001]`: `0.1234`, `123456`, `-0.000` (`234`). A map of `0.125` steps: `10.375` reads `10.37` and half a glyph (`231b`). Right-aligned, so the eye takes it as whole, in a column several times wider than the field. Not pass 15 M6, which is a rounding of the value; here the value is right and the field hides it. *Change:* size the field to its text (`ch` of the longest cell), or an ellipsis and a title. S.

- **I2. After a cell is typed in a map, nothing changes where the reader is looking: the sentence and Apply appear under the plot, off-screen, and Enter does nothing.** `gui/src/components/ValuesGridView.tsx:248` (the plot), `:262-307` (the offer), `:229-231` (Enter). `MapA` at 1280×800: Apply at y 877 to 914 (`logs/s35.txt`); `241`. 16×16 at 1280×800: y 1463 in a page of 1516, scrollY 0 (`logs/s20.txt`, `232`). A curve fits: 712 to 749. Nothing scrolls, nothing says so; the cell looks typed and the page looks finished, and leaving it drops the value without a word (I3). *Change:* the offer above the plot, or held in view while a cell is open. S.

- **I3. A second cell typed throws the first away in silence.** `gui/src/screens/ValuesPage.tsx:102`, `:301-306`. `CurveA`, type `13`, `14`, `15` into three cells in turn: `[13, 9, 8]`, then `[12, 14, 8]`, then `[12, 9, 15]` (`logs/s35.txt`, `350`): each cell silently goes back when the next is touched, and one change is offered. The same on leaving by `Back to Controller`. Retuning three points of a curve means Apply and wait, three times, which no screen says: "One cell is changed at a time" stands only in `docs/command_line_interface.rst:330`. Also, inside a cell the arrow keys, Home and End move between cells (`End` jumps to the row's last cell; `logs/s21b.txt`), so a digit in the middle of a number cannot be reached by keyboard; Tab leaves the grid. *Change:* hold several typed cells as one plan (`getValuesPlan` already takes a whole table), M; or at least say it on the cell's sentence, S. Open question 2.

- **I4. The value of a scalar can be neither read nor changed, nor can any variable's description, name or scope.** `src/ddd/variable_keys.py:29-42` (`KEY_ORDER`), `gui/src/screens/ComponentPage.tsx:62-65`, `:166-169`, `gui/src/screens/ValuesPage.tsx:283`. Trigger: `examples/demo`'s `ParameterA`, "Single calibratable constant", `init: 3200`, a plain calibration parameter. Its row has no Shape button; its panel lists kind, datatype, unit, conversion, limits, volatile, typename; the page holds neither `3200` nor `800` nor its description (`71`, `logs/s08.txt`; `ScalarParam` likewise, `logs/s20.txt`). By address: `'ScalarParam' has no cell for a value to sit in` (`235_values_ScalarParam`). Nor shown: `section`, `raster`, `id`, `condition`, a string's text. There is no rename of a variable, though units, types, constants, sections and rasters each have one and the language server renames variables. There is no change of scope: a writer becomes a reader by Remove then Add, which loses what the file stated (`25`, `26`). A `conversion` or `dimensions` row offers only what is already in play; text typed there vanishes on Enter with `Nothing to change` and no reason (`logs/s26.txt`, `286`, `287`; the reason is in a docstring, `variable_keys.py:68-73`). `KNOWN` for types: nothing added or removed, members read only (`2026-09-22-gui-types.md:2483`, `:2486`). The docs state what the panel does and are silent on all this. For a person sent here to "change a value", the commonest value there is has no control and no sentence. *Change:* a scalar's `init` as a one-cell grid and the description as a field on the panel, S each; rename by the existing `navigation.rename_edits`, M; and a line on the panel saying what is edited elsewhere. Open question 1.

- **I5. Once the Shared files tab lists anything, nothing can be declared there.** `gui/src/components/SharedTableView.tsx:69-73`: the Declare button is drawn only where there are no rows (plan `2026-09-27-gui-constants.md:2211`). `examples/vocabulary`: 0 Declare controls on a tab of seven entries (`logs/s22.txt`, `250`). The form itself works, reached by a typed address: `/project?view=shared&kind=raster&name=2ms` (`251`). A finding can lead to it for a constant, but no GUI action can name an undeclared section or raster, so a second one of those has no way in at all. Against `docs/command_line_interface.rst:398-399`, "One of the three is declared there too". `e2e/shared.spec.ts:250` pins the empty case only. *Change:* the button always, above the table. S.

- **I6. Add a declaration: a required key reads `state nothing`, and nothing says why Apply does not come.** `gui/src/components/DeclarePanelView.tsx:58`, `:64-66`, `:177`; `gui/src/lib/declarations.ts:41-49`, `:63-67`, `:105-107`. Trigger, demo, Controller: name `BrandNewSignal`, Kind `measurement`, Datatype `uint16`: `Declares BrandNewSignal, a measurement this component produces.` and no Apply, indefinitely (`105`, `logs/s11b.txt`). The field holding it up is `Volatile of BrandNewSignal`, reading `state nothing`, a value its own list does not offer (`110`). Pick `false` and Apply appears (`111`). The same field text means "fine" on Datatype and Typename, of which exactly one is needed, also unsaid; a curve wants Axis the same way (`114`). No field is marked required, no line says what is missing, and the sentence above reads as if it were complete. *Change:* one line naming what the form still needs, computed where `definitionOf` returns `null`, and a required key's field empty rather than `state nothing`; or default `volatile`. S.

- **I7. The Name list of Add a declaration is not narrowed by typing and is drawn whole: at 35,000 declarations each key takes five seconds.** `gui/src/components/DeclarePanelView.tsx:96-106`, against `gui/src/ui/ComboBox.tsx:70-71` ("The caller narrows the sections itself"), and the unit picker's `lib/units.ts`, which does. `KNOWN` that it is not narrowed (P19c-12, `2026-10-21-gui-journeys-remaining.md:1986`); the cost is not. Measured (`logs/s16.txt`, `s30.txt`, `194`): 2,000 declarations: 968 options, 258 to 275 ms a key. 10,000: 4,968 options, about 1.0 s a key. 35,000: 26,218 options, first key 4.8 s, seven more 36.9 s, the list still starting at `C00000_O0000` under a field reading `C00500_O`. So a new name cannot be typed in a large project without waiting for each letter. Against the budget "Typing or scrolling stalling: never over 100 ms" at every size up to 100,000 (`2026-09-30-gui-large-projects-design.md` §3) and `docs/command_line_interface.rst:529`. The bench types only into a unit picker (`gui/bench/page.bench.ts:592-598`). *Change:* narrow as the unit picker does, cap what is drawn. S.

- **I8. A finding with nowhere to lead names no place: the page drops what `ddd check` prints.** `src/ddd/gui/api.py:1712-1717` and `contract.py:293-318` carry a pointer and no line or column; `gui/src/components/FindingPanelView.tsx:58-62` does not draw even the pointer. Half-saved file: `ddd check` says `.../controller.ddd.json:15:56: error[json-syntax]: Expecting ',' delimiter`; the panel says `Expecting ',' delimiter`, `controller.ddd.json did not load`, and offers nothing to press (`122`). Schema: `...#component.interface[0].definition.volatile: error[schema]: Input should be a valid boolean ... (got: 'maybe')` against the same words with no place (`129`, `logs/s12.txt`), though `finding.pointer` is in the reply. In a file of hundreds of lines the reader goes back to a terminal. This is the state the page itself calls the commonest ("an editor saving it half-written", `SharedTableView.tsx:60-61`). *Change:* carry `line` and `column`, draw `file:line:column` or the pointer, and the file's path. S.

- **I9. While a file does not load, the screens a reader lands on do not say so.** `gui/src/screens/GraphPage.tsx:96-99`, `gui/src/screens/ProjectPage.tsx:20`, `gui/src/screens/UnitsPage.tsx:111`; adds to pass 14 M9, M10. A component half-saved, demo (`logs/s12.txt`): Graph: every arrow gone, the module gone, under `This project has no dictionary, so its modules are drawn without arrows.` (`121_broken_graph`), which names neither file nor cause. Table: `1 error, 0 warnings` over rows of 0 and 0, the broken file in no row, `kind` being `unknown` (`120`). Units: `4 units`, `% 2 variables` where it was `5 units`, `% 5 variables`, no banner, the adoption offer gone (`121_broken_units`), though Types and Shared files do warn. The description itself broken or failing its schema: an empty canvas under the same sentence, Table one line, Files two buttons (`131_*`, `331`); only the Findings tab knows, and no tab carries a count. A person opening such a project sees "no dictionary" and an empty grid. *Change:* one banner in the project heading, from `state.files`, naming what did not load and linking to the finding. S.

- **I10. While a file does not load, a variable's panel states what is false, and offers the removal that breaks the project.** `gui/src/lib/declarations.ts:118-120`, `gui/src/components/VariablePanelView.tsx:143`; adds to pass 13 I2. Controller half-saved, SensorHub's `ValueA`: `produced by SensorHub · 1 declaration · all agreed`, `Removes ValueA, which no other component declares.`, `Remove from SensorHub` enabled (`126`). Pressed: applied. File restored: `missing-producer 'ValueA' is read by component 'Controller' but no component declares it as output` (`271`, `272`, `logs/s23.txt`). The server knows: right after, the panel says `'ValueA' is not declared in any file that loaded, and controller.ddd.json did not load`. Undo does recover it. *Change:* with I9's banner; the sentence reads "no file that loaded", and a removal is refused or says so while a file is unread, as a unit's rename already refuses. S.

- **I11. An arrow that agrees is almost invisible, on the screen every project opens on.** `gui/src/lib/canvas.ts:83-87` (`agreed: var(--rule)`), `gui/src/styles/tokens.css:8-9`, `gui/src/components/FlowEdge.tsx:43`. `--rule` on `--canvas` is 1.17:1 (`logs/contrast.txt`), against 3:1 for a graphic that carries meaning (WCAG 1.4.11). In a clean project that is every arrow, heads included: `02`, and `282`, where fourteen arrows are a pale smear. In forced colours the same graph reads at once (`301`), which shows what is lost. A backward arrow leaves its module's right side and passes behind the modules, so even at close range its end cannot be followed (`173`, the stub right of EventLogger). The numbers on arrows are unexplained, and pressing an agreeing arrow does nothing, with no way but hovering to learn what it carries. Against `docs/command_line_interface.rst:298-299`, "an arrow per pair". *Change:* a stroke of at least `--ink-quiet` (4.92:1). S.

- **I12. The focus ring of every Button is 1.27:1, and in forced colours there is none.** `gui/src/styles/tokens.css:12` (`--focus`, 16 % accent), `gui/src/styles/ui.css:20-25`, `:64-66`. `.button:focus-visible` removes the outline and `[data-focus-visible]` draws a 3 px shadow in that token: `#d8e7ea` on white, 1.27:1 (`logs/contrast.txt`; close-ups `172`, `170`, `175`, `176`). That is every Apply, Close, Show changes, Undo, Remove, Save and link-styled button. Beside it the tabs (browser's ring, `171`) and fields (2 px accent) are plain to see, so a keyboard user's place vanishes at the controls that matter. In forced colours (`Windows High Contrast`) a `box-shadow` is not drawn: `Open ValueE` focused shows nothing (`303`), and a selected row has no mark either, its tint being its only sign (`302`; 1.16:1 in normal colours). Field borders are `--rule` on white, 1.32:1. Against WCAG 2.4.7, 1.4.11. *Change:* the outline the file's own `app.css:84-88` already sets, unsuppressed; S.

- **I13. Focus is dropped and nothing is announced: after Close, Apply, Put back or any change of page the keyboard is back at the top, and the page's title never changes.** `gui/src/ui/Panel.tsx:17`, `gui/src/screens/VariablePanel.tsx:442`, `gui/src/app/App.tsx:66`, `gui/index.html:6`. Reproduced (`logs/s19.txt`, `s14.txt`, `s37.txt`): focus after Close by keyboard: `BODY`. 150 ms after Apply by keyboard: `BODY`, and after the analysis. Enter on a Table row: new page, `BODY`, next Tab `Projects`. `document.title` is `ddd gui` on every screen, so several tabs and any screen reader's page list read alike; no document code sets it. Success has no status line beyond `Updating the findings…`, which on a small project flashes. `KNOWN` for Compare (`2026-10-21-gui-journeys-remaining.md:1976`). The code knows the problem: `FileActionsView.tsx:239-241` holds focus for one button, "focus left on it would fall to the page's body, a keyboard's place lost". *Change:* focus the page's heading on a route change; the row on Close; the panel's heading after Apply; a title per page; a status line saying what was written. S to M.

- **I14. Nothing finds a variable.** `gui/src/screens/ProjectPage.tsx:24`, `gui/src/screens/ComponentPage.tsx:238`, `gui/src/components/FindingsTableView.tsx:63`, `gui/src/components/UnitPanelView.tsx:137`; the one search box is the Graph's, for modules (`GraphPage.tsx:327`). 1,166 components, a component's thousands of declarations, 43,750 findings, 4,376 places: no filter, no search, and the browser's find does not help because the rows are not in the document: `window.find("C00020")` false on the Table tab (`logs/s24.txt`). "Where is this signal?" has no answer but scrolling. `KNOWN` for Findings alone (`2026-09-30-gui-large-projects.md:2446`: "no filter of its own", though `GET /api/findings` has one). Not a problem on the demo; on the projects the large-projects part exists for, it stops the job before it starts. *Change:* a filter box on each long table, and a go-to-variable in the masthead over the index the server has. M.

#### Minor

- **M1. Compare's table is drawn whole: at 4,375 findings a key in its field takes 5.4 s and selecting a row 6.7 s.** `gui/src/components/CompareTableView.tsx:17`. Rename `degC` at 35,000 declarations, compare with the delivery: 4,376 rows in the document (`logs/s28.txt`, `315`). Against the same budget as I7; the docs' list of windowed tables does not name it. *Change:* the Findings tab's window, or `LongTable`. S.
- **M2. Compare forgets its baseline when you leave the tab, and a verdict names no baseline.** `gui/src/screens/ComparePage.tsx:33`, `:37`, `gui/src/app/App.tsx:229-230`. Ask, go to Units, come back: field `""`, no verdict (`logs/s33.txt`, `342`). `ComparePage.tsx:22-25` and spec §4 promise that fixing what the verdict complained about turns it "while the tab is open", but every fix is on another tab. Typed and not asked, the old verdict stands under another path (`92`). *Change:* hold `asked` above the tab, in memory (not the address: pass 12 M6). S.
- **M3. Compare's refusals are in Python's words.** `gui/src/screens/ComparePage.tsx:66`, `src/ddd/gui/compare.py:360`. `the baseline '...nothing.json' is unreadable: [Errno 2] No such file or directory: 'C:\\Users\\...'`, doubled backslashes included (`84`). A directory: `[Errno 13] Permission denied` (`85`). `is outside the session root` (`86`): the page's own sentence says "the directory ddd gui was started in". Windows' Copy as path, with its quotes, is taken as relative and refused with the path twice over (`logs/s25.txt`, `82`). *Change:* the sentence without `{error}`'s tail, strip the quotes. S.
- **M4. Text typed in a panel is dropped without a word when another part of it is used.** `gui/src/screens/TypePanel.tsx:306-309`, `:352-360`, `:368-376`. A type's Description typed, then a row of What it fixes selected: the field goes back, the words are gone (`53`, `54`, `logs/s07b.txt`), where the sibling panels keep each draft. Those lose theirs on a rename instead, the panel remounting on the new name (`SharedPage.tsx:171`; `logs/s22.txt`). Undo cannot help: nothing was written. *Change:* keep drafts, or hold the move while one is open. S.
- **M5. A range that is no range, on a type's panel, says nothing.** `gui/src/components/TypePanelView.tsx:133` (`note={undefined}`), `gui/src/screens/TypePanel.tsx:142-146`, whose comment says the chooser "has no field of its own to show the sentence in", though `KeyChooser` has the same `note` the variable's panel uses. Min `abc`: the sentence and Apply vanish and the chooser goes blank (`66`). *Change:* pass `broken` as the note. S.
- **M6. A key row of a type's panel opens its list by keyboard and not by mouse, covering the panel.** `gui/src/components/TypePanelView.tsx:135-136`, against `gui/src/ui/ComboBox.tsx:61-63`: `"focus"` is what "only a story wants", since the list "covers what is below the field". Enter on a row: list open over Rename and the sentence (`300`, `logs/s27.txt`). A mouse press: focus stays in the row, no list (`logs/s07b.txt`), so `TypePanelView.tsx:117-119` ("always takes the focus") does not hold. See also pass 15 M4 for the same panel: a row merely selected offers `Changes 1 file` and an Apply that writes nothing and leaves an undo entry (P19b-13; `60`, `61`, file identical, `logs/s07c.txt`). *Change:* drop the two props. S.
- **M7. The declare form says "Reads" while it writes an output.** `gui/src/lib/declarations.ts:100-103`. `MissingValue`, no producer, Scope `produces`: `Reads MissingValue as this project declares it.`, diff `"scope": "output"`, written so (`343`, `logs/s34.txt`). *Change:* the sentence follows the scope. S.
- **M8. The page never uses more than 1,100 px, so columns stay cut on any screen.** `gui/src/styles/app.css:11`. At 1920×1080, panel open: `uint...`, `S...` for Shape, `axis...`, chips cut, with 800 px empty (`201`). The same as at 1280 (`71`), and the `.tsx` comments measure against that. A 16×16 map overflows the page sideways instead of scrolling in a box (`231b`). The Graph of 1,166 modules gets 1,068 px. *Change:* let the data pages take the window. S.
- **M9. Below 900 px a panel opens off-screen with nothing to show it did; below about 600 px the page scrolls sideways.** `gui/src/styles/ui.css:137-141`. 800×600: a component's row selected, panel top at y 608 of 600, scrollY 0, only the row's tint changes (`281`, `logs/s25.txt`); a browser beside an editor on a laptop is that wide. 600 wide with a panel: `scrollWidth` 784; 375: the tabs alone reach 432 (`logs/s17.txt`): WCAG 1.4.10, and 200 % zoom. *Change:* scroll the panel into view; let the tabs wrap. S.
- **M10. The Graph's search says nothing, and a large project opens on a corner of itself.** `gui/src/screens/GraphPage.tsx:271-283`, `:306-309`. At 35,000 declarations, `C00500` typed: everything in view fades to almost nothing, the match being elsewhere, until Enter (`182`, `183`). No match: all faded, no word (`184`). Only the first match is ever flown to. The opening view and `Fit` show 6 of 1,166 modules, tiny, in the right half of an empty canvas, with no count (`181`, `185`): by design (`app.css:147-149`), but nothing tells the reader. *Change:* a line under the box: `3 of 1,166 modules`, `no module matches`. S.
- **M11. An arrow's tooltip scales with the canvas and is cut by its edge.** `gui/src/components/FlowEdge.tsx:65-85`, `gui/src/styles/app.css:176-179`, `:252-264`. On a small project at zoom 2 its first line, the one naming the variables, is hidden above the canvas and its text is twice the size (`11`); `pointer-events: none`, so it cannot be scrolled. *Change:* a tooltip outside the zoomed layer. S.
- **M12. After a stop the Graph tab gives wrong advice.** `gui/src/lib/layoutAnswers.ts:53`. `ddd gui is not answering` and `The layout worker stopped; reload the page to try again.` under `ddd gui has stopped. Start it again and open the address it prints.` (`152`); reloading then gives the browser's refused-connection page and loses the tab (`155`). Units says `ddd gui is not answering` twice (`154`). *Change:* no worker message while `stopped`. S.
- **M13. An empty project gives no next step, and a description that does not parse is not on the start page.** `gui/src/screens/ProjectPage.tsx:23-24`, `gui/src/screens/GraphPage.tsx:340`, `gui/src/screens/StartPage.tsx:20-21`. No includes: an empty grid, `0 errors, 0 warnings` and white (`141`, `142_empty_table`); Types `This project declares no types` and no way to add one. `KNOWN` for Files (`2026-09-29-gui-files.md:970`). `brokenone/broken.ddd.json` is left off the list with no word, beside `Found under ...` (`logs/s31.txt`). *Change:* a line on the Graph and the Table pointing at New file; list what could not be read. S.
- **M14. A note reads as a warning everywhere but two tables, and severity is colour alone.** `gui/src/screens/ComponentPage.tsx:345`, `gui/src/components/VariablePanelView.tsx:74`, `UnitPanelView.tsx:105`, `TypePanelView.tsx:257`, `ConstantPanelView.tsx:168`, `SectionPanelView.tsx:196`, `RasterPanelView.tsx:226`, `ValuesGridView.tsx:256`, against `FindingsTableView.tsx:111-113`. `missing-id` amber on a component (`192`), grey on Findings (`214`). A Findings row's accessible name holds no severity (`logs/s30.txt`), nor its text; WCAG 1.4.1. The tab says `notes`, `ddd check` says `infos`. *Change:* one `toneOf`; a word or icon in the row. S.
- **M15. Files are named by base name alone.** `gui/src/lib/findingsWindow.ts:89`, `gui/src/lib/units.ts:163`, `gui/src/components/Changes.tsx:15`. `left/signals.ddd.json` and `right/signals.ddd.json`: two rows `signals.ddd.json`, `Changes 1 file: signals.ddd.json`, `signals.ddd.json, line 11`, no path, no title (`273`, `275`, `logs/s24.txt`). The Table tab has `shownPath`. *Change:* use it. S.
- **M16. Leaving the Findings tab loses your place, and a component's page has no way back to it.** `gui/src/screens/FindingsPage.tsx:69`, `:126`, `gui/src/app/App.tsx:296`. Scrolled to 20,000 px, a finding followed, Back: scrollTop 0, panel closed (`logs/s24.txt`, `278`), so working down a list means finding your place each time. A component's page has no tabs; the masthead's project link always goes to the Graph. *Change:* the tab's state above the tab, or in the address. S.
- **M17. A wide change shows a wall of file names, and a slow plan shows nothing.** `gui/src/lib/units.ts:161-165`, `gui/src/components/UnitPanelView.tsx:238-247`. Rename a unit stated in every component at 35,000: `Changes 1167 files: c00000.ddd.json, c00001.ddd.json, ...`, Apply at y 6,281 of 6,534 (`320`, `312`, `logs/s29.txt`); Show changes 4,376 hunks, page 399,280 px. For the 3.4 s before it, the panel looks as it did before Enter (`310`, `logs/s28.txt`). *Change:* count past a few names; a `Planning…` line while `pending`. S.
- **M18. A long name pushes Close out of the panel and the page.** `gui/src/styles/ui.css:105-115`. 86 characters: `Close` past the panel's edge, page 1292 wide in 1280 (`284`). SPEC allows 128. A long project name makes the masthead wrap (`331`). *Change:* `overflow-wrap: anywhere`. S.
- **M19. The reduced-motion preference is not honoured.** `gui/src/screens/GraphPage.tsx:48`, `:269`, `:279`. Nothing in `gui/src` reads it; under `prefers-reduced-motion: reduce` a search's Enter still animates, 5 distinct frames in 400 ms (`logs/s25.txt`). The only motion on the page: a small cost. *Change:* duration 0. S.
- **M20. Selecting a row of the Files tab offers only its removal.** `gui/src/screens/FilesPage.tsx:111-123`. `Remove from the includes`, or, for a file a pattern brings, a refusal as the panel's whole content, also for one marked `did not load` (`148`, `270`). No way from a row to its component, its findings or why it did not load; the Findings count is not a link. New file leaves you on the tab, not on the new component. *Change:* a link in the panel. S.
- **M21. Text in a table cannot be selected.** `gui/src/screens/ProjectPage.tsx:27-31` documents it. Dragging over a path in the Table tab selects nothing and opens the component; a message or a unit likewise (`logs/s38.txt`). A panel's text can be. So a path can be copied from nowhere. *Change:* leave cells' text selectable or add a copy control. S.
- **M22. Small words and layout.** `Undo Apply this unit to 1 other declaration of 'ValueE'`, `Undo 'my_part.ddd.json' created` (`lib/undo.ts`). `it is about the whole delivery being compared, ...` opens a line in lower case (`lib/compare.ts:32`). A screen reader hears `kHzwill change` and `Show the choices for Unit of ValueE Unit of ValueE` (`VariableKeysTable.tsx:165`, `ComboBox.tsx:139`, `logs/s30.txt`). An Undo button appearing pushes Add a declaration to a second line and the table down (`25`). The panel's top border sits on the masthead's rule (`71`). A unit panel's Where rows are plain text, where the other four panels link theirs (`UnitPanelView.tsx:150`). A plot's end labels are padded numbers no cell holds (`12.275` for 12), overlap a marker on a wide range and collide at 16 rows (`72`, `233`, `231b`). A panel over a canvas leaves the far modules cut until `Fit` (`222`).
- **M23. Still open in this area, already recorded, and met here.** `KNOWN`, Minor as they stand: a refused undo stays on top for the session with the entries under it (`2026-09-22-gui-undo.md:2514`, `219`); a raster cannot be made acyclic, pass 3 M8 (`259`); the Findings window's keys act on the drawn rows (`2026-09-30-gui-large-projects.md:2458`).

Cited, not re-filed: pass 3 I3, I6, I7; pass 4 I1 (no guide, and the page links none); pass 14 M7 to M10; pass 15 C1, I1, I3, I5, M4, M6 to M8.

### Status of the 2026-09-15 findings in this area

None: that review had no such pass.

### Open questions

1. **Is the GUI meant to change a scalar's value, a variable's description, its name and its scope (I4)?** Yes: one-cell grid, a Description field, the language server's rename, a scope chooser. No: the panel should say what is edited elsewhere, and the concept page should say the GUI edits a subset. Either answer changes I4 from a defect to a task or a sentence.
2. **One typed cell per edit, or several (I3)?** Several makes a row of retuning one Apply and fits the existing table plan; one means saying so on screen and keeping today's journeys.
3. **What is the accessibility target (I11, I12, I13, M9, M14, M19)?** If WCAG AA is meant, these are defects, and a check belongs in the journeys; if keyboard use by sighted developers is the aim, I12 and I13 still stand, and the rest is lower.
4. **Should the page keep its 1,100 px measure (M8)?** Every table's widths are argued against it in comments; the Graph and the maps would gain most from dropping it.

### Test gaps

- **No journey presses keys in a field.** 151 `.fill()` in `gui/e2e`, none of `pressSequentially` or `keyboard.type`; the one typed text in the repository is the bench's, into a unit picker (`gui/bench/page.bench.ts:598`). `.fill()` skips `keydown`, which is exactly why C1 is invisible to 294 passing journeys. One journey typing into a map's cell would have caught it.
- Nothing asks whether Apply is in view (I2), or whether a value is readable in its cell (I1); no story holds a value past six characters.
- No picture among `gui/screenshots/references` draws the canvas or a focus ring, so nothing looks at the arrows or the rings (I11, I12).
- No check of contrast, focus position after an action, or document title.
- The bench's `typing` measure covers one field; Name and Baseline are not measured (I7, M1). `apply`-side costs: see pass 15 I4.
- `e2e/shared.spec.ts` drives Declare on an empty tab only, and never asks where the button goes once there are rows (I5).
- No journey leaves a file broken and reads the Table, the Graph's sentence or a neighbouring variable's panel for what they say (I9, I10).

### Assessment

As a person who has not read the code, I found a calm, legible tool whose core loop (see a finding, see the exact lines, apply, undo) works and is pleasant to use, with sentences that are honest and specific; somebody can fix a disagreement or rename a unit in a minute with no guide, and read a comparison's verdict at a glance. But the screens have not been used the way people use them. The worst finding is the plainest: on the tool's own demo map you cannot type a number, because no journey has ever pressed a key, and when part of it gets through, `5.1` is planned as `5`. Around it stand gaps a first hour meets at once: the commonest value, a scalar parameter, has no control; a second raster has no way to be declared; a new declaration waits on a field that reads `state nothing`; a file that does not parse is named nowhere useful, and on the landing tab is a sentence about a "dictionary". The care spent on measuring column widths in comments has no counterpart in anyone having tried the job at a keyboard; the pale arrows and pale focus ring are the same story, correct by token and invisible by eye. None of this is deep: nearly every fix is hours, the structure under the page is sound, and the honest verdict is a good design at preview stage that needs a week of somebody watching real use, with journeys that type.

```candidates
16|C1|gui/src/components/ValuesGridView.tsx:214|A number typed into a map's cell loses digits to the table's type-to-find: 20 plans 2, 5.1 plans 5, focus jumps to a row; 16x16 takes no digit at all
16|I1|gui/src/styles/ui.css:764|A value cell shows six characters cut from the right with no sign: 1000000 reads 100000, 4000000000 reads 400000
16|I2|gui/src/components/ValuesGridView.tsx:262|After a cell is typed in a map the sentence and Apply appear under the plot off-screen, y 877 to 1463 at 800 high, Enter does nothing
16|I3|gui/src/screens/ValuesPage.tsx:301|A second cell typed throws the first away in silence, and leaving drops it; three cells typed leave one change offered
16|I4|src/ddd/variable_keys.py:29|A scalar's value cannot be read or changed, nor a variable's description, name or scope; ParameterA's panel holds neither 3200 nor its description
16|I5|gui/src/components/SharedTableView.tsx:69|Once Shared files lists one entry nothing can be declared there; a second section or raster has no way in but a typed address
16|I6|gui/src/lib/declarations.ts:66|Add a declaration: required Volatile reads state nothing, the sentence reads complete, and nothing says why Apply does not come
16|I7|gui/src/components/DeclarePanelView.tsx:96|Name list neither narrowed nor windowed: 26,218 options and five seconds a key at 35,000, one second at 10,000 (KNOWN in part)
16|I8|src/ddd/gui/api.py:1717|A finding with no route names no place: ddd check prints controller.ddd.json:15:56 or the pointer, the panel only Expecting ',' delimiter
16|I9|gui/src/screens/GraphPage.tsx:96|While a file does not load the landing tabs do not say so: no dictionary, no arrows, Table 1 error over rows of 0, Units silently short
16|I10|gui/src/lib/declarations.ts:119|While a file does not load a variable's panel says no other component declares it and offers the Remove that leaves missing-producer
16|I11|gui/src/lib/canvas.ts:86|An agreeing arrow is 1.17:1 on the canvas, on the screen every project opens on; numbers on arrows unexplained, a press does nothing
16|I12|gui/src/styles/tokens.css:12|Every Button's focus ring is 1.27:1, and in forced colours there is none; a selected row has no mark there either
16|I13|gui/src/ui/Panel.tsx:17|Focus falls to the body after Close, Apply, Put back and every change of page; document title never changes; success is not announced (KNOWN for Compare)
16|I14|gui/src/screens/ComponentPage.tsx:238|Nothing finds a variable: no filter on any long table, the browser's find sees drawn rows only (KNOWN for Findings)
16|M1|gui/src/components/CompareTableView.tsx:17|Compare's table is drawn whole: at 4,375 findings a key in its field takes 5.4 s, selecting a row 6.7 s
16|M2|gui/src/screens/ComparePage.tsx:33|Compare forgets its baseline on leaving the tab, though every fix is on another tab; a verdict names no baseline
16|M3|src/ddd/gui/compare.py:360|Compare's refusals in Python's words: Errno, doubled backslashes, session root, Permission denied for a directory, Copy as path refused
16|M4|gui/src/screens/TypePanel.tsx:306|Typed text dropped without a word: a type's description on selecting a key row, siblings' drafts on a rename
16|M5|gui/src/components/TypePanelView.tsx:133|A broken range on a type's panel says nothing: Apply vanishes, the chooser goes blank, the note is withheld
16|M6|gui/src/components/TypePanelView.tsx:135|A type's key row opens its list by keyboard and not by mouse, covering the panel, against ComboBox's only a story wants
16|M7|gui/src/lib/declarations.ts:103|The declare form says Reads MissingValue while its scope is produces and it writes an output
16|M8|gui/src/styles/app.css:11|The page never uses more than 1,100 px: uint..., S..., chips cut at 1920 with 800 px empty; a 16x16 map overflows the page
16|M9|gui/src/styles/ui.css:137|Below 900 px a panel opens off-screen with nothing to show it; below 600 px the page scrolls sideways
16|M10|gui/src/screens/GraphPage.tsx:271|The Graph's search says nothing: typed, everything fades with the match elsewhere; no match, no word; large project opens on 6 of 1,166 with no count
16|M11|gui/src/components/FlowEdge.tsx:65|An arrow's tooltip scales with the zoom and is cut by the canvas: the line naming the variables hidden, no way to scroll
16|M12|gui/src/lib/layoutAnswers.ts:53|After a stop the Graph says the layout worker stopped, reload; reloading loses the page to a refused connection
16|M13|gui/src/screens/ProjectPage.tsx:23|An empty project gives no next step; a description that does not parse is left off the start page with no word
16|M14|gui/src/screens/ComponentPage.tsx:345|A note reads as a warning in eight places and grey in two; severity is colour alone in a Findings row; notes against infos
16|M15|gui/src/lib/findingsWindow.ts:89|Files named by base name alone: two signals.ddd.json indistinguishable in rows, previews and diffs
16|M16|gui/src/screens/FindingsPage.tsx:69|Back from a finding's page loses the place in the list; a component's page has no tabs and the masthead goes to the Graph
16|M17|gui/src/lib/units.ts:164|A wide rename lists 1,167 file names, Apply at y 6,281, Show changes 399,280 px; a 3.4 s plan shows nothing while it waits
16|M18|gui/src/styles/ui.css:111|An 86 character name pushes Close out of the panel and the page
16|M19|gui/src/screens/GraphPage.tsx:48|prefers-reduced-motion is not honoured: a search still flies, 5 frames in 400 ms
16|M20|gui/src/screens/FilesPage.tsx:111|Selecting a Files row offers only its removal or a refusal, also for one that did not load; no way to its component or findings
16|M21|gui/src/screens/ProjectPage.tsx:27|Text in a table cannot be selected; dragging over a path opens the component instead
16|M22|gui/src/lib/compare.ts:32|Small words and layout: Undo Apply this unit, doubled accessible names, Undo shifting the table, a plot's padded end labels
16|M23|docs/superpowers/plans/2026-09-22-gui-undo.md:2514|Still open and recorded, met here: a refused undo blocks the stack, acyclic raster, the Findings window's keys (KNOWN)
```

## Pass 17: code review of the core, part A

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-17/`. Line numbers are on the review tree.

### Scope covered

- **Read in full, with line numbers:** `src/ddd/models/__init__.py` 1-164, `common.py` 1-419, `component.py` 1-167, `constants.py` 1-115, `conversion.py` 1-444, `objects.py` 1-993, `project.py` 1-78, `rasters.py` 1-151, `reserved.py` 1-77, `schema.py` 1-250, `sections.py` 1-95, `types.py` 1-561, `units.py` 1-95; `src/ddd/loading.py` 1-1608; `src/ddd/diagnostics.py` 1-590; `src/ddd/names.py` 1-58; `src/ddd/pointers.py` 1-29; `src/ddd/file_names.py` 1-111.
- **Read for how the scope is used:** `src/ddd/analysis.py` 205-235, 960-1030, 2620-2700, 3325-3400, 3675-3692; `src/ddd/plugins.py` 105-130, 180-337; `src/ddd/deliveries.py` 120-175; `src/ddd/cli.py` 100-170, 1190-1300, 1950-2000; `src/ddd/backends/base.py` 340-372; `src/ddd/elf.py` 55-80; `src/ddd/variable_keys.py` 176-262; `src/ddd/declaration_plans.py` 108-128, 230-296; `SPEC.md` 186-290; the previous review's pass 8; `docs/superpowers/plans/2026-09-16-review-fixes.md` "Left open"; the open items of all 31 plans, by keyword; pass 6 in full and the candidates of passes 1 to 16.
- **Ran:**
  - `fuzz_core.py`, random schema-valid projects with odd combinations (unknown types, constants of every value, wrong reference kinds, enums past `int`, every conversion on every datatype) under random `-W`, through `check`, `dump`, `list`, `generate a2l`, `generate c --force`, `compare`, `check --standalone`: 5,400 projects, about 43,000 runs in process (`fuzz_core_2.txt`, `fuzz_core_3.txt`).
  - `pointer_fuzz.py`, 30,000 mutated descriptions from `examples/`, each finding's pointer walked through the document (`pointer_fuzz.txt`).
  - `fuzz_dump.py`, 3,000 mutated dumps through `compare` (`fuzz_dump.txt`).
  - `order_dep.py`, every example project with its includes expanded and permuted, dumps and a2l compared (`order_dep.txt`).
  - `time_load.py`, `time_load2.py`, the loader and the analysis on the four generated shapes at 100,000 declarations (`profile_large.txt`, `profile_chain.txt`); `bigarrays.py`, arrays at the documented cap (`bigarrays.txt`); `meaningful.py`, `mapping_key.py`, broken large files (`meaningful.txt`, `mapping_key.txt`).
  - `suspects1.py` to `suspects4.py`, `lsp_digits.py`, `lsp_deep2.py`, `status0915.py`, `last_checks.py`, `small_facts.py`, `devices.py`; `plug/p17plugin.py`, a pytest plugin recording every hash of a data object and every ordering of a `Location` over `test_loading`, `test_compare`, `test_models`, `test_edge_cases`, `test_hardening`, `test_analysis`, `test_cli`, `test_plugins`, `test_gui_session` (all green). `mypy --strict` and `ruff` over the scope: clean.
- **Not covered:** python 3.12 and 3.14, which this machine does not have (M5 rests on python's documentation for 3.12); a real out-of-memory run; another operating system. Whether a CI log parser acts on a forged line (M4) was not tried. No mutation testing: pass 21.
- **Met again and cited rather than re-filed, with what the inside adds:**
  - pass 6 M1, M2, M3, M4, M7, M10: confirmed at the lines the pass names; nothing to add.
  - pass 6 M5: its surrogate half has a cause and a further effect, my M3.
  - pass 8 M8 (`float64` under a factor above 1): every position answers with the `not finite` finding, producer, consumer, consumers alone, member, scalar type, `float32`, `uint64` at `1e308` and an offset overflowing the sum. `Limits(min=inf)` at `objects.py:711` and `types.py:228` would be a pydantic error out of the analysis, and no path reaches it (`suspects2.txt`). The guard holds.
  - pass 8 M1, pass 7 M8, pass 5 M16, M17, pass 7 M10: read at the lines; nothing to add.
  - pass 10 I13, pass 14 M7: my M2 is one more trigger of each.
  - pass 8 I2: my M9 is its other half.
- **Met on the way, for pass 19, not filed:** one `generate` in about 10,000 here failed with `cannot write '.../.ddd-manifest.json': Access is denied`, a file written a few milliseconds earlier and re-replaced with no retry (`backends/base.py:370`; `fuzz_core_3.txt`, `cases/fuzz_kept/000/argv.txt`). `plugins.py:113`, `:124` use `.match` on a pattern ending in `$`, so a plugin named `"layout\n"` passes (`small_facts.txt`). The text report prints each finding to unbuffered stderr: at 125,000 findings `ddd check` took 54 s against 16 s with `--format json`, measured while a fuzz was running, and the rendering itself 4.4 s.

### Strengths

- **No traceback from any input the schema admits.** About 43,000 CLI runs over 5,400 odd projects under random relaxations: zero tracebacks, and the one exit 2 is the manifest above. 3,000 mutated dumps: zero. Every `assert` in the scope (`objects.py:374`, `:655`, `:709`, `types.py:220-221`, `:300`, `rasters.py:113`) held. This is the result I most expected to break.
- **The pointer machinery is right.** Of 39,483 findings on 30,000 mutated descriptions, 27,916 resolve exactly and 8,517 end one key short at a key that is missing. Of the remaining 3,050, 3,048 are keys I injected with `.` or `[n]` in them and 2 are `units[i].unit`, both M7. Zero exceptions in the reporting path. `_place` (`loading.py:1509-1546`) fixed the two Important findings it was written for (`status0915.txt`).
- **On a valid project the loader is linear and small.** 100,000 declarations: 3.3 s in 3,333 files, 2.3 s in 30 files, 2.6 s mixed, against 6 to 8 s of analysis. 50,000 files: 27 s (31 s under the profiler, 11.5 s of it Windows' `realpath`, about 230 µs a file), and nothing grows with the square. `_locations` is the largest step of the loader's own code, about a fifth of the load at 30 files, and harmless. Arrays are about 2 µs per element to the 10,000,000 cap.
- **Meaning does not depend on include order.** Permuted includes of all example projects: the dump's meaning is identical every time, and the a2l differs only in the order of its lines (`order_dep.txt`).
- **The hash machinery hides no cliff.** Nothing but an explicit test hashes a model or a workspace (`plug/p17plugin.py.out`).
- **Patterns are matched carefully.** Every use of a `$` pattern against unvalidated text is `fullmatch` (`rasters.py:48`, `cli.py:168`, `:1385`, `lsp/navigation.py:780`, `:826`, `:849`), `plugins.py:113` above apart, and pydantic's engine reads `$` as the end of the text.
- **The last review's findings here are fixed,** down to the small ones: 16 of 21 plainly, 5 with the remainders below.

### Issues

#### Critical

None.

#### Important

None. The earlier passes found the formats sound from the outside; from the inside I find the same.

#### Minor

- **M1. A file whose definitions all fail one of the models' own rules takes quadratic time in the filter that tidies the findings.** `src/ddd/loading.py:1383`. `explained_by_a_deeper_finding` walks every place for every error whose input holds something (`:1388`), and an `after` validator's error has the whole object as its input. Trigger: one component of N definitions stating `"datatype": "uint8"` and no `conversion`, so N `schema` findings: whole `ddd check` 1.7 s at 4,000, 6.0 s at 8,000, 22.5 s at 16,000 (`meaningful.txt`). In process at 16,000: validation 0.13 s, `_place` 0.04 s, `_meaningful` 17.95 s; the same count of missing `volatile`, whose type returns early at `:1386`, 0.016 s (`last_checks.txt`). At the square, about twelve minutes at 100,000 in one file. It needs a generated component broken whole at once, which is what a release tightening a rule does, and how `conversion` became required (`622561a0`). The language server and `ddd gui` pay it on each analysis until the file is fixed. Reproduced. Build the set of every proper prefix of every place once, and ask it; S.

- **M2. An unknown key holding a long bracketed number ends `ddd check` in python's advice, with no finding, and ends `ddd lsp`.** `src/ddd/diagnostics.py:310` `int(p)`, `src/ddd/pointers.py:21` `int(index)`: both read `\d+` unbounded, and `int()` refuses past 4300 digits. Trigger: `{"component": {"name": "A", "interface": [], "x[1...1]": 1}}` at 4301 digits -> `ddd: Exceeds the limit (4300 digits) for integer string conversion ... use sys.set_int_max_str_digits()`, exit 2, and nothing on stdout under `--format json`; at 4300 digits an ordinary located `schema` finding, exit 1 (`last_checks.txt`, `suspects1.txt`). `textDocument/didOpen` on the file: `ddd lsp` exits 2 (`lsp_digits.txt`). `src/ddd/graph.py:170` reads the same pointer (read off). Against `loading.py:1264` "Every failure has to come back as a located finding"; `rasters.py:36-38` calls this very sentence "python's advice to a programmer". The edit engine guards itself (`editing.py:91` `_LONG_INDEX`), so the rule exists once, in a client. Reproduced. `\d{1,18}` in both patterns, a longer run being text; S.

- **M3. `_write_utf8` throws away stderr's `backslashreplace`, so a finding quoting a lone surrogate ends `ddd check` with exit 2 and no findings (adds to pass 6 M5).** `src/ddd/cli.py:118`. `reconfigure(encoding="utf-8")` resets `errors` to `strict`: stderr `backslashreplace` before, `strict` after; stdout `surrogateescape` before, `strict` after (`reconfigure.txt`). Python's own default would have printed `\ud800`. Pass 6 M5 has `ddd check` clean on such a file; that holds only until a finding quotes the text. Triggers: `"unit": "\ud800"` in a project with a units file (`unknown-unit`); a duplicated key spelled `"\ud800"`; an include naming one, the most ordinary finding there is -> `ddd: 'utf-8' codec can't encode character '\ud800' ...`, exit 2, where `--format json` gives the finding and exit 1 (`suspects3.txt` q2, q8; `suspects4.txt`). `tests/test_gui_queries.py:489` pins this escape for the GUI's sentence. Reproduced. `errors="backslashreplace"` on stderr; pass 6 M5's refusal at the parser ends it as well (open question 3); S.

- **M4. Free text reaches the text report raw, so one finding can print as two and escape codes reach the terminal.** `src/ddd/diagnostics.py:335`, `:405`; `src/ddd/loading.py:181`, `:1331`. `(got: ...)` goes through `repr`; the pointer, a quoted unit and a quoted include do not. Against `docs/consistency_checks.rst:69` "Every finding is one line, in a shape an editor or a log parser can pick apart" and `docs/command_line_interface.rst:15`. Triggers: an unknown key `"a\nb: error[fake]: forged"` -> a line ending `#component.a`, and a second reading `b: error[fake]: forged: error[schema]: ...`; a unit holding `\n` and `\u001b[31m`, and an include holding the same (`suspects3.txt` q3, q4, q9; `suspects4.txt`). The ELF reader takes care of exactly this (`src/ddd/elf.py:61`, pinned by `tests/test_cli.py:4216`, whose subject is `.c\x1b[2K`), so the decision exists for one source of text. Cosmetic under the stated trust, a description being able to run a plugin anyway; a log parser would read the forged line. Reproduced. Escape control characters once, at render, leaving the json as it is; S.

- **M5. An include ending in `**` means two things, by python version.** `src/ddd/loading.py:1432`; `SPEC.md:273` "`**` matches directories recursively"; `docs/file_formats/project.rst:100`; `pyproject.toml:14` `>=3.12`; `.github/workflows/ci.yml:46` runs 3.12, 3.13, 3.14. Trigger: `"includes": ["components/**"]` -> on 3.13.17 both files under it, exit 0, against the spec's sentence (`starstar.txt`). On 3.12 `Path.glob` yields directories alone, by python's own note ("Changed in version 3.13: Globbing with a pattern that ends with "**" returns both files and directories. In previous versions, only directories were returned"), so `match.is_file()` at `:1442` leaves nothing and the same project is `include-empty`, an error. `components/**.ddd.json` reads as `*.ddd.json` on 3.13; 3.12's pathlib, as I remember it, refuses a partial `**` (not run). No test uses such a pattern. 3.13 half reproduced; 3.12 half from the documentation, since this machine has no 3.12. See open question 1; S.

- **M6. An interface nothing calls, a field nothing reads, and an ordering that would raise.** `src/ddd/models/conversion.py:39`, `:98`, `:128`, `:239`, `:267` `to_raw`; `:32` `ConversionRule`; `:295` `IDENTITY`; `src/ddd/loading.py:195`, `:218` `parents`, threaded through `:769`, `:995`, `:1016`, `:1188`; `src/ddd/diagnostics.py:313` `order=True`. No caller in `src/ddd` for any of them; tests alone read them (`tests/test_models.py:155`, `:427`, `tests/test_edge_cases.py:193-196`, `tests/test_loading.py:59`) (`dead.txt`), and that is how a 100 % gate keeps them. The module's opening sentence, `conversion.py:3-4`, says each variant answers the same three questions; nobody asks the second. `Location`'s generated ordering is never used over nine test modules (`plug/p17plugin.py.out`) and raises where it would be: `sorted([Location(p, "x", 3, 1), Location(p, "x")])` -> `TypeError`, `None` against `int` (`small_facts.txt`): a `json-syntax` location carries a line and every other location none. Reproduced. Remove them, or state them as plugin api (open question 2); S.

- **M7. Two kinds of finding still point at a place the file does not have (remainder of P8-M14).** `src/ddd/loading.py:1531`, `src/ddd/models/units.py:53`, `src/ddd/models/common.py:64-69`; `docs/file_formats/index.rst:77-78`. (a) `"units": [""]` -> `units[0].unit`: the shorthand is rewritten to `{"unit": ""}` before validation, as an enumerator mapping is, and `_mapping_key` handles that one alone; the file holds a string there (`pointer_fuzz.txt`). (b) A refused block key: `"extensions": {"c[1]": {}, "a.b": {}}` -> `...extensions.c[1]`, `...extensions.a.b`, which `pointers.segments` reads as an index and as two keys, where `common.py:64-69` says the pattern keeps such a key out of the pointer (`status0915.txt`, m14). Any unknown key so spelled does the same. Editors fall back to the parent, so the cost is a wider underline. Reproduced. Stop the walk at a scalar where the model read an object, and correct the sentence; S.

- **M8. Small untrue sentences.** Each reproduced or read off.
  - `src/ddd/loading.py:62-64`: a tree too deep is "most often a project that includes a sibling which includes it back under a second spelling of one path". Identity is the resolved path, so that is `include-cycle` at once (`spelling.txt`); only a real chain reaches the cap.
  - `src/ddd/models/objects.py:69-73`: the integer arm is listed first "so that an out of range whole number is reported against that bound". `within_64_bits` (`:62`) answers before any arm: `Value error, does not fit 64 bits` (`initbound.txt`).
  - `src/ddd/loading.py:613-615`: "every other problem is reported through `bag`". A plugin's model raising leaves as `PluginError` through `:1163`, by design at `plugins.py:325-327` (read off).

- **M9. The names no file can be created under are not asked of the files DDD generates (adds to pass 8 I2).** `src/ddd/file_names.py:1-7`, `:32-36`; `SPEC.md` 3.2 "it becomes the name of a generated header". A component or a project named `NUL`, `CON`, `AUX`, `COM1` or `LPT1` passes `ddd check --strict`, and `ddd generate all` reports `wrote out/NUL.h`, `wrote out/CON.a2l` (`devices.txt`). On this Windows 11 those are plain files, so the module's "opening it opens the device" is untrue here, and "on any system" with it. On a Windows that still reads them as the module says, the header is lost with exit 0 and `#include "NUL.h"` reads nothing; not reproducible here. Its docstring's reason, "a project is checked out on more than one system", is as good for a header as for a description. Rare. First half reproduced, second read off. Ask `device_named` of a component's and a project's name beside `name-collision`, and soften the sentence; S.

- **M10. `ddd sources` lists in the order the platform compares paths (KNOWN, `plans/2026-09-16-review-fixes.md`, "Left open").** `src/ddd/loading.py:498`; `SPEC.md:2124`. On Windows `_under, alpha, Beta, p, Zeta`, where the same files load `Beta, Zeta, under, alpha` (`last_checks.txt`). Nothing generated depends on it. Still open; one line, `key=Path.as_posix`.

### Status of the 2026-09-15 findings in this area

Checked against the tree, by run or at the line. Plainly fixed: P8-I2, P8-I3 (`loading.py:1509-1546`), P8-M2 (`reserved.py:39`), P8-M3 (`common.py:153`), P8-M4 (`loading.py:1502`), P8-M5, P8-M6, P8-M7, P8-M8 (`deliveries.py:134`, `:150`), P8-M9 (`--version` 0.146 s against 0.048 s for python alone), P8-M10 (`rasters.py:41`), P8-M11 (`loading.py:1549`), P8-M12 (`conversion.py:146-164`), P8-M13, P8-M15 (`loading.py:1466`), P8-M16 (`common.py:131`). All in `status0915.txt`, `last_checks.txt`.

| id | finding | status | where |
| --- | --- | --- | --- |
| P8-I1 | a file 500 levels deep ends `ddd id --assign` and the server | FIXED as a crash. The server stays up, its finding at 0:0 from about 500 levels (`lsp_deep2.txt`). `ddd id --assign` at 520 says `not readable as json, skipped`, exit 1, of a file `ddd check` reads clean (`status0915.txt`): untrue, and rare | `identity.py`, pass 18 |
| P8-M1 | a condition ending in a backslash | FIXED (`component.py:82`); its trigraph is pass 6 M6 | |
| P8-M14 | an extension key with `.` or `[n]` | PARTLY: refused now, and the refusal itself still carries that pointer | M7 |
| P8-M17 | `MemoryError` on a read | FIXED for the read (`loading.py:1300`); the parse at `:119-128` has no such clause. Read off, not provoked, and a file that is not json fails at its first byte | |
| P8-M18 | `assign` rewrites in place | FIXED; the staging that replaced it has its own findings | pass 13 C2, I5 |
| P7 design note 3 | strict by default | STILL OPEN, KNOWN, decision 10 | pass 6 M10 |

### Open questions

1. **What does a trailing `**` mean (M5)?** "Directories", as SPEC says: `x/**` then reaches no file on any python, and 3.13's reading must be filtered out. "Everything under", as 3.13 does: normalise `x/**` to `x/**/*` on every python and change the sentence, at the price of sweeping non-DDD files into `file-extension`. Either way one branch in `expand_include` and a test on the matrix.
2. **Is the conversion interface public (M6)?** Whether a plugin may call `to_raw` or lean on `ConversionRule` is pass 4 M13's open point. If yes, document it. If no, five methods, a Protocol and a constant go, with the tests that read them.
3. **Is a lone surrogate refused at the parser (pass 6 M5's proposal)?** If yes, M3's stream handler is a belt and the check gains a finding, with a migration for nobody. If no, the handler is the fix, and `ddd list`, `dump` and `generate` still need their own answer.

### Test gaps

- Nothing holds `_meaningful` to linear (M1): a bound on 20,000 errors would have caught it.
- `tests/test_hardening.py:1316-1324` and `tests/test_pointers.py:20` pin ordinary indices and superscripts; no run of digits past python's limit (M2).
- Nothing tests `_write_utf8`, or a lone surrogate in a finding through `ddd check`; `tests/test_gui_queries.py:489` is the GUI's sentence (M3).
- Control characters in the text report are pinned for the ELF reader alone, `tests/test_cli.py:4216` (M4). The sentence "one line per finding" has no test.
- No test uses an include ending in `**` or holding a partial one, on a matrix of three pythons that differ on both (M5).
- `tests/test_models.py:155`, `:427`, `tests/test_edge_cases.py:193-196`, `tests/test_loading.py:59` pin code nothing runs (M6).
- Across the suite, `units[0].unit` appears as a pointer only for a file spelling that key (`tests/test_lsp.py:2178`); the shorthand's location is not pinned (M7).
- No test asks what happens to a component named after a device (M9).

### Assessment

This is careful code, and from the inside I find what pass 6 found from the outside: the models, the loader and the diagnostics are sound. I went looking for a branch that does the wrong thing, an unguarded impossible input and a cliff, with three fuzzers and about 76,000 hostile documents and runs, and the result is no traceback from a description and no wrong pointer beyond two small classes. The loader is linear and cheap on valid input, the assertions hold, the numeric guards reach every position, and the last review's three Important findings here are fixed. What is left is real and small: one quadratic filter on a file broken whole, one unbounded `int()`, one stream handler reset by accident, control characters in a report promised to be one line per finding, and a wildcard that means two things on two supported pythons. The code's prose is the weakest part: it states absolutes ("every", "never", "on any system") that are nearly true, and M6 shows a 100 % gate keeping alive what nothing calls. I would fix M1 to M5 in an afternoon and leave the structure of these modules as it is.

```candidates
17|M1|src/ddd/loading.py:1383|A file whose definitions all fail a model's rule is quadratic in the findings filter: 22.5 s at 16,000, 18 s of it in _meaningful, about twelve minutes at 100,000
17|M2|src/ddd/diagnostics.py:310|An unknown key holding a bracketed run past 4300 digits: ddd check exit 2 with python's advice and no finding, ddd lsp exits on didOpen; pointers.py:21 the same
17|M3|src/ddd/cli.py:118|_write_utf8 resets stderr's backslashreplace to strict: a finding quoting a lone surrogate ends ddd check with exit 2 and no findings (adds to pass 6 M5)
17|M4|src/ddd/diagnostics.py:405|Free text reaches the text report raw: a newline in a key or unit forges a finding line, escape codes reach the terminal, against one line per finding; the ELF reader escapes them
17|M5|src/ddd/loading.py:1432|An include ending in ** reads every file on 3.13 and nothing on 3.12, include-empty, against SPEC's matches directories; no test on a matrix of three pythons
17|M6|src/ddd/models/conversion.py:39|Nothing calls to_raw, ConversionRule, IDENTITY or parents, tests alone keep them; Location order=True is unused and raises on a None line
17|M7|src/ddd/loading.py:1531|Findings pointing at what the file lacks: units[0].unit on a bare string, extensions.c[1] on a refused key, against common.py:64 (remainder of P8-M14)
17|M8|src/ddd/loading.py:62|Small untrue sentences: a second spelling reaching the depth cap, the arm order of init, every other problem reported through bag
17|M9|src/ddd/file_names.py:32|A component or project named NUL, CON, AUX passes --strict and writes NUL.h; plain files on Windows 11 against the docstring, lost on a Windows reading them as devices (adds to pass 8 I2)
17|M10|src/ddd/loading.py:498|ddd sources lists in the platform's path order, case insensitive on Windows, where components load by code point (KNOWN, 2026-09-16 left open)
```

## Pass 18: code review of the core, part B (`analysis.py`, `ir.py`, `compare.py`, `identity.py`)

Transcripts and probe scripts are in `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad/pass-18/`; a bare `name.txt` below is a file of that folder.

### Scope covered

**Read in full, with line numbers:** `src/ddd/analysis.py` 1-3692, `src/ddd/ir.py` 1-817, `src/ddd/compare.py` 1-1126, `src/ddd/identity.py` 1-209. To hold them against what they call: `src/ddd/models/objects.py`, `conversion.py`, `common.py`, `types.py`, `component.py`, `constants.py` in full, `sections.py` 20-79; `src/ddd/diagnostics.py` 1-590; `src/ddd/loading.py` 185-505, 533-606, 640-815; `src/ddd/plugins.py` 260-297, 340-367; `src/ddd/cli.py` 1472-1495, 1878-1917; `src/ddd/difflib_lock.py`; `src/ddd/backends/a2l/model.py` 236-300 (its closure against `_a2l_closure`). `SPEC.md` 436-450, 470-612, 892-905, 925-937, 1222-1446, 1500-1680; `docs/faq.rst` 622-660; `docs/file_formats/types.rst` 605-615; `CHANGELOG.md` 1428-1442; `tests/test_structures.py` 640-730; `tests/test_backends.py` 665-740. Pass 9 of the previous review; "Left open by the implementers" of `2026-09-16-review-fixes.md`; pass 7 whole; the candidates blocks of passes 1-17.

**Ran:**
- `fuzz.py`: random projects through the real loader, `analyze` and `compare`, 4,500 of them (1,500 with random `-W`, 1,500 with random `-W` and every name drawn from a small pool, 1,500 with that pool alone). Invariants: no exception; every declaration a component lists is in the dictionary; no dangling reference; leaves under their instance; lists sorted; types in dependency order; a comparison with itself and with its own dump clean; the dump round trips; two shuffles of the includes compared field by field (`fuzz_relax.txt`, `fuzz_hard_relax.txt`, `fuzz_hard.txt`). `p12.py` held the include order against ownership over 2,597 more.
- `fuzz_clean.py`: mostly consistent random projects, `ddd generate all`, gcc under the CI flag set on `ddd_globals.c` and every component header (`fuzzc_plain.txt`, `fuzzc_pool.txt`).
- Performance: `perf_base.py` (the generator's 35,000 and 100,000 declarations, profiled), `perf_shapes.py`, `perf_shapes2.py`, `perf_shapes3.py`, `p6.py`, `p8.py` (shapes the generator never makes: types, constants, vocabularies, leaves, long cycles, large inits), `p11.py` (attribution by patching one method in the probe's process), `p9.py` (a rename sweep), `p4.py`, `p4b.py` (`ddd id --assign`).
- `p1.py`, `p2.py`, `p3.py` (21 spellings through `ddd id --assign`), `p5.py`, `p7.py`, `p10.py`: single hypotheses from the reading.
- `tests/test_analysis.py`, `test_compare.py`, `test_comparison_tables.py`, `test_structures.py`: all pass.

**Not covered:**
- `ddd.lsp.ranges.Document` beyond what `ddd id` shows of it (pass 10, pass 13).
- A member dimensioned near 2^64 over a structure with no leaf: read off, not run, because it allocates until the machine fails (M1).
- The cost of I1 and M2 inside `ddd gui` and `ddd lsp`: inferred from pass 10 I12 and pass 14 M7, not measured.
- No real calibration tool reads the limits of M4 and M5.

### Strengths

- **The logic of the analysis holds where I could attack it.** 4,500 random projects, many of them full of mistakes and relaxed at random: no exception, no `AssertionError`, no IR `ValidationError`, every invariant above true on every run. Coverage says each line ran; this says the states they assume are the states that occur.
- **The graph walks are what they claim.** `_nesting_depths` is a plain depth-first walk whose mark propagates on pop; `settled` in `_nesting_cycle` really means "reaches no cycle", because a name joins it only once every name it nests has; the memo of `_reaches_external` cannot store a false "no", because `any` stops at the first true and a `seen` cut only meets a name already answered no. I tried to break each on diamonds and cycles and could not.
- **The absence machinery is sound.** Both fixpoints of `_absent` are monotone and their depth is bounded by the reference kinds. Every drop is recorded, and `incomplete-project` says what a `-W` hid.
- **What `check` calls clean compiles.** 391 random clean projects went through gcc under the CI flag set: 387 compile, and the other 4 are exactly the pairs SPEC marks *planned* and pass 5 M8 (`fuzzc_plain.txt`, `fuzzc_pool.txt`).
- **Include order.** An object with a producer does not depend on it: over 2,597 projects and two shuffles each, 208 objects moved and every one had no producer (`p12.txt`). What does move with it is documented: the fallback for an object nobody produces (`SPEC.md:522-526`), the order of `components` (`SPEC.md:1798`), and which copy of a conflicting enum the dictionary keeps, under an `enum-conflict` error. The dump and the findings of `examples/demo` are identical under three hash seeds (`p10.txt`).
- **Linear on large plain and structured projects.** `analyze` takes 4.4 s at 35,000 and 13.2 s at 100,000 declarations, profiled (`perf_base.txt`); 3.3 s and 16.9 s at 10,000 and 40,000 declarations over 8,750 and 35,000 types (`p8.txt`); 3.9 s and 40 s at 100,000 and 1,000,000 leaves (`perf_shapes3.txt`). The fix of P9-I4 holds: a rename sweep with no ids over 17,500 objects compares in 2.5 s, against 2.1 s for the dump against itself (`p9.txt`).
- **`ddd id --assign` respects the bytes.** CRLF, a BOM, tabs, one line, `null`, escaped keys, a name spread over three lines: one line changed each time and the file still loads (`p3.txt`). Pass 2 I6 and pass 13 C2, I5 stand, and are about the write, not the text.

### Issues

#### Critical

None found.

#### Important

- **I1. The name-collision check of constants against members is constants times members on every analysis of a clean project: 45.7 s against 1.6 s at 4,000 constants and 40,000 members.** `src/ddd/analysis.py:1918`, `:1929-1946`.

  *Why:* `_check_constant_collisions` calls `_members_named` once per constant, and each call sorts every type name and walks every member of every structure.

  *Trigger,* `ddd check` through the real command, one variable and no finding at all (`p6.txt`):

  | constants | structures | members | `ddd check` |
  | --- | --- | --- | --- |
  | 0 | 4,000 | 40,000 | 1.6 s |
  | 1,000 | 3,000 | 24,000 | 8.0 s |
  | 4,000 | 4,000 | 40,000 | 45.7 s |

  *Attribution:* the same `analyze`, with this one method answered from a dict built once, drops from 36.24 s to 0.48 s (`p11.txt`). On a type-heavy project with only 100 constants it already costs as much as all of `_flatten`: 4.1 s of 14.1 s, profiled, at 17,500 types (`p8.txt`).

  *Consequence:* no finding is needed to pay for it. Every build, every save and every GUI revision runs the analysis, and pass 10 I12 multiplies that by 1+N per save.
  - `src/ddd/models/constants.py:6` ("a gain, an offset or a base address") and `docs/file_formats/constants.rst:7` invite any number of the project, so a constants file taken from a legacy header reaches these counts.
  - `tools/generate_project.py` writes plain declarations only, with no type and no constant, so `tools/bench_gui.py` cannot see it. Everything the suite measures at 100,000 declarations misses this cost.

  *Graded* Important for the clean project and for each re-analysis paying it. If you say a project never declares more than a few hundred constants, it is Minor.

  *Change (S):* a `{member name: [(holder, position)]}` index built once, and types and constants options on the generator.

#### Minor

- **M1. The caps have a hole below a declaration: a structure with no leaf is walked with no bound, so a 12 kB types file never returns; a member of 300 dimensions ends in python's advice.** `src/ddd/analysis.py:1574-1577`, `:3324-3325`, `:1608`, `src/ddd/models/types.py:163-174`, `docs/faq.rst:622-625`, `CHANGELOG.md:1428-1441`. KNOWN in part: `S-M1` in `2026-09-16-review-fixes.md`, "Left open", and pass 5 M16. The hang and the crash are not recorded there.

  *Why:* `_leaves_of` multiplies by the leaves of the nested type, so a structure whose members are all external counts 0 however it is nested or dimensioned. `_refuse_wide_types` and `_shape_fits` therefore see nothing, and `_flatten` walks every element of every level regardless.

  *Trigger 1, the ladder the changelog says is fixed, over an external type* (`p5.txt`):

  | levels | size of the types file | `ddd check` |
  | --- | --- | --- |
  | 22 | 6.9 kB | 5.9 s |
  | 24 | 7.5 kB | 26.5 s |
  | 40 | 12.4 kB | killed at 120 s, no output |

  `TestADiamondOfStructures` (`tests/test_backends.py:673`) knows this shape and fixed the c model's walk alone. `_flatten` doubles per level on the same input.

  *Trigger 2, arrays:* `Top_t.o[3000]` of `Outer_t.m[3000]` of `Mid_t.i[3000]` of `Inner_t {Ext_t e}`: killed at 60 s, no output (`p1.txt`). `_element_paths` builds a list of that many strings per level, so a member dimensioned in the billions allocates until the machine fails (read off, not run). `_shape_fits`'s "what still bounds the element paths" (`analysis.py:2100-2103`) holds for the variable's own dimensions only.

  *Trigger 3:* a member with 300 dimensions of `2**64-1` over a structure with one leaf: `ddd: Exceeds the limit (4300 digits) for integer string conversion; use sys.set_int_max_str_digits() ...`, exit 2, no finding, raised by the message at `:1608` (`p1.txt`). `S-M1`'s "produces no traceback, only an unbounded shape" misses this.

  *Who meets it:* contrived; it takes a very large array or a ladder of 30 levels, hence Minor. In `ddd gui` the page would then read Analysing for good (pass 14 M7; inferred, not run).

  *Change (S):* `_flatten` skips a member whose structure counts zero leaves. Then decide open question 1.

- **M2. Every "did you mean" is a fresh sweep of the vocabulary, with no memo per spelling, so a broken large project takes minutes to say so.** `src/ddd/analysis.py:1152`, `:1991-1992`, `:2001`.

  *Trigger,* the same mistake named 35,000 times, `ddd check` (`p6.txt`, `perf_shapes.txt`, `perf_shapes2.txt`):

  | project of 35,000 declarations | clean | every 10th wrong | every one wrong |
  | --- | --- | --- | --- |
  | 3,000 types, typename nobody declares | 19.2 s | 46.4 s | 266 s |
  | 300 units, unit not in the file | 19.6 s | 40.6 s | 150 s (`analyze` alone) |

  3,000 constants against 5,000 uses of a removed constant: 20.5 s of `analyze`. A finding costs 4 to 8 ms, with the difflib lock taken and released per comparison for units. `sorted(self._types)` and `sorted(vocabulary)` are rebuilt per finding as well.

  *Who meets it:* one project-wide mistake, such as a types file lost in a merge, a unit file adopted with part of its vocabulary, or a removed type. A broken project is when somebody is waiting on the tool, and the language server does this per save.

  *Also:* one cycle of 2,000 structures is 5.8 s and of 8,000 is 90.9 s of `_check_types`, because every start walks it again and `frozenset(cycle)` rebuilds it (`perf_shapes2.txt`). `_nesting_cycle`'s docstring presents the walk as having left the square of the chain behind. Rare.

  *Change (S):* a dict per spelling for the run, in each of the three.

- **M3. `ddd id --assign` is quadratic in the size of one file: 8 s at 5,000 declarations, 118 s at 20,000.** `src/ddd/identity.py:191-192`, `src/ddd/editing.py:149` (the line of pass 13 M8, met here on an ordinary multi-line file). Every insertion rebuilds the whole text, and `indent_of_line_at` slices the rest of the document per id. At 10,000 declarations, 17.8 s of 27.2 s is `assign` itself and 7.9 s is `indent_of_line_at` (`p4.txt`, `p4b.txt`; the 20,000 and 10,000 figures are under the profiler). 60,000 declarations did not finish in the 500 s the probe allowed. This is the migration command, run once, and the generator's "large" shape is 3,333 declarations a file, hence Minor. *Change (S):* join the pieces once; `indent_of_line_at` scans forward from `start`.

- **M4. Every `float32` without stated limits states limits past what a `float32` holds.** `src/ddd/models/conversion.py:367`, `:415-416`. Adds to pass 8 M1, which names the other direction for `float64`.

  *Trigger:* `F32` `float32` under the identity: the dump's `limits` are `+-3.40282346639e+38` and the a2l writes `FLOAT32_IEEE NO_COMPU_METHOD 0 0 -3.40282346639e+38 3.40282346639e+38` (`p2.txt`). `FLT_MAX` is `3.4028234663852886e38` (`SPEC.md:399`), and twelve digits round it up.

  *Contradicts:* `SPEC.md:409-410`, "under the identity they are the raw ends themselves", and the purpose of `limits-out-of-range` ("a range the calibration tool offers and the storage cannot take", `analysis.py:2678`). The same number as an `init` is refused with `does not fit into float32`.

  *Effect:* small. A value at that limit rounds to `FLT_MAX` under IEEE. What a tool or a checker says about it was not established. *Change (S):* do not round the identity, whose ends need no rounding.

- **M5. The tolerance of `limits-out-of-range` covers integer storage under the identity, so a limit past it passes `--strict` and reaches the a2l.** `src/ddd/analysis.py:2682`, `src/ddd/models/conversion.py:393-395`, `SPEC.md:1438-1441`. Adds to pass 7 M8, the same constant on the other check.

  *Trigger* (`p10.txt`): `uint32` with `max: 4294967299` and `sint64` with `max` 5e9 past its top: `ok`, exit 0 under `--strict`; the a2l writes `ULONG NO_COMPU_METHOD 0 0 0 4294967299` and `A_INT64 NO_COMPU_METHOD 0 0 0 9223372041854775807`.

  SPEC gives the tolerance as being "at the edge of a floating point range", and an identity on an integer computes nothing. *Change (S):* compare exactly when the derived end is an `int`.

- **M6. A member past `MATRIX_DIM` is one `a2l-unrepresentable` per element and per variable, at a file that cannot fix it.** `src/ddd/analysis.py:3253-3262`. `Cell_t {m4[2][2][2][2], raw}`, two variables `[1000]`: 2,000 warnings, each at the variable's `definition` in `w.ddd.json`, while the member is in `t.ddd.json` (`p7.txt`). `_check_scalar_type` (`:984-990`) and `_check_init` (`:2554-2559`) state the principle this breaks: "What a type fixes is the type's to answer", and "The ways are counted, not the elements". *Change (S):* once per member, at the type, whichever variable reaches the file.

- **M7. The comparison reports one edit of a member once per element, and in text order.** `src/ddd/compare.py:369-371`, `:545-547`.
  - `Cell_t.raw`'s unit changes, two variables `[1000]`: 2,000 `changed-interface` (`p7.txt`). `SPEC.md:1662-1664` gives this as the reason the variable's own fields were moved to the variable, and `_compare_layouts` as the reason for reporting a reorder once.
  - They are listed `A[0].raw`, `A[10].raw`, `A[11].raw`, `A[1].raw` (`p10.txt`), where `ddd list` now reads `[0], [1], ... [11]`. That is the remainder of P9-M7, fixed in `ir.py` and `analysis.py` but not in `_pair`'s two sorts.
  - See open question 4.

- **M8. Small untrue sentences and one loose validator.**
  - `src/ddd/ir.py:368-376`: "Exactly one of `datatype`, `type` and `external`", and `ResolvedMember(name="x", datatype="uint8", type="T")` validates (`p2.txt`). The fix of P9-M2 refuses none and refuses external beside either, not the third pair.
  - `src/ddd/analysis.py:3072-3074`: "so that which file the project lists first cannot decide whether the reference is reported". With two locals of one name it decides: `a` then `b` no finding, `b` then `a` `local-conflict` at the same reference (`p10.txt`). Asked of `locals_[0]` where any of them is the answer. An already erroneous project.
  - `src/ddd/analysis.py:275-277`: "a declaration that leaves one unstated is leaving it to whoever states it" against `SPEC.md:576-578`, "a consumer's statement never replaces a producer's silence". The SPEC is what the code does (`p1.txt`, C): `format` and `display_identifier` on a reader under a silent producer reach nothing, with no finding. See open question 3.
  - `src/ddd/ir.py:699-700`: `enums` "used by the objects". An enum of a scalar type nothing names, or of a dropped declaration, is there too (`p10.txt`); the types header emits it.
  - `src/ddd/analysis.py:2350`: "Three of the keys" introduces two. `src/ddd/analysis.py:3271`: `_flatten`'s `reference` is only passed on. `src/ddd/ir.py:594`: "The member's own a2l options" against `analysis.py:3311-3320`, both answers resolved.
  - `src/ddd/identity.py:48-54`, `src/ddd/cli.py:1487`: "not readable as json" of a file `ddd check` reads clean, past about 500 levels in an `extensions` block (`p3.txt`, P8-I1's remainder, handed on by pass 17), and of a file that does not exist.

### Status of the 2026-09-15 findings in this area

Plainly fixed and read at the line or re-run: P9-I3 (`analysis.py:2638-2662`), P9-I4 (`compare.py:716-782`, `p9.txt`), P9-M1 (`analysis.py:516-521`), P9-M3 (`:171-183`), P9-M4 (`objects.py:889-903`), P9-M5 (`compare.py:153-178`), P9-M6 (`analysis.py:2727`), P9-M8 (`:2709`), P9-M10.

| id | finding | status |
| --- | --- | --- |
| P9-I1 | `narrowed-limits` compared exactly | FIXED (`compare.py:978`), and the tolerance is now too wide: pass 7 M8, M5 here |
| P9-I2 | reordered structure, bitfield width | FIXED for those two; layout beyond them is pass 1 C3, pass 7 C1 |
| P9-M2 | member with no storage | FIXED; two storages still pass, M8 |
| P9-M7 | leaves in text order | FIXED in the dictionary and `ddd list`; STILL OPEN in the comparison's report, M7 |
| P9-M9 | `1.0` on a boolean | STILL OPEN, KNOWN (2026-09-16 left open), pass 5 M17 |
| P9-M11 | layer table against the analysis's knowledge of a2l and c | STILL OPEN, pass 1 M2 |
| P7 design note 4 | implicit phase order of `run` | STILL OPEN, no defect: 4,500 runs met none; the order lives in comments |
| P7 design note 5 | the IR is the a2l's shape | STILL OPEN, by decision; `leaves` per element is what M6, M7 and I6 of pass 5 sit on |
| 2026-09-16 left open | an instance's `a2l` not compared | KNOWN, stated in `SPEC.md:933-937`; no effect found |
| 2026-09-16 left open, S-M1 | a member's dimension count uncapped | STILL OPEN, KNOWN; worse than recorded, M1 |
| P8-I1 | deep file ends `ddd id --assign` | FIXED as a crash; the reason it gives is untrue, M8 |

### Open questions

1. **Are a member's shape and a structure with no leaf capped at all (`S-M1`)?**
   - *Yes:* hold a member to `_MAX_DIMENSIONS` and `_MAX_ELEMENTS` in `_check_member_dimensions`. M1's crash and pass 5 M16 end, the FAQ's "five places" becomes true, and a project with a large opaque member array needs a migration line.
   - *No:* only the `_flatten` skip of M1 is needed, and the FAQ has to say declarations only.

2. **Is a reference a use?** SPEC says yes for `local-conflict` and no for `unused-output` (`SPEC.md:478-483`). A component holding an axis and a curve, with a reader of the curve alone, can never be `--strict` clean, and is told the axis, and the measurement that indexes it, are "read by nobody" (`p1.txt`, D).
   - *Yes:* `_consumers` counts referrers.
   - *No:* the message should say "declared as input by nobody".

3. **Is a reader's `a2l.format` under a silent producer to be told?** SPEC says silence (`SPEC.md:576-578`), while the page says "What DDD refuses to do is decide silently" (`docs/file_formats/component.rst:350`). An `info` costs one branch in `_compare`; leaving it needs only the comment fixed.

4. **One finding per path, or per member, for a member's change in a comparison (M7)?** Per path is what a dataset is keyed by; per member is what the edit was. `--renames` already gives a tool the paths for a rename, and nothing does for a change. Folding needs a list in the JSON form.

### Test gaps

- `tests/test_structures.py:690-708` caps a no-leaf structure at the variable's own dimensions only. Nothing puts one under a member or a ladder (M1).
- `tests/test_backends.py:728-733` asserts the c model's walk count at depths 8 and 16 and runs the analysis's exponential walk at both without noticing.
- `tools/generate_project.py`, and so `tools/bench_gui.py`: no types, no constants, no sections, 8 units, no mistakes of the kinds in M2. No performance guard reads `_check_constant_collisions` or a suggestion (I1, M2).
- No test holds `ddd id --assign` at a large file (M3).
- No test pins the derived limits of a `float32`, or a whole limit past an integer datatype (M4, M5).
- `tests/test_analysis.py`: no two-locals reference in both include orders (M8).
- Nothing constructs a `ResolvedMember` with two storages (M8).
- A property test over random projects would be cheap: `fuzz.py` here is about 460 lines and has found no defect yet, which is why it is worth keeping. Today nothing in the suite would notice an invariant it holds being broken by a new combination.

### Assessment

`analysis.py` is sound, and this pass could not make it give a wrong answer of its own. Read line by line, the phases do what they say, the walks are correct, every branch I could reach does the right thing, and the seam to `ir.py` is clean: 4,500 hostile random projects raised nothing and broke no invariant, and 387 of 391 clean ones compile, the other four being already-recorded pairs. The verdicts that are wrong in this area remain the comparison's and the concept's, and passes 1 and 7 have them. What reading added is cost and small holes. One clean-project quadratic is invisible to the benchmark, which generates no types and no constants. The did-you-mean sweeps have no memo. `ddd id --assign` is quadratic. A hole in the caps hangs on a contrived input, and the changelog says that hole's own shape is fixed. Limits slightly past their storage reach the a2l in two ways. All of these are small changes. The module's size is mostly not logic: of 3,692 lines, 2,193 are code and 1,269 are docstrings and comments, in one class of 85 methods and 17 state fields whose order lives in comments. I found no defect that hides in that, and the docstrings are more accurate here than elsewhere in the tree, but its next reader pays for it.

```candidates
18|I1|src/ddd/analysis.py:1929|name-collision of constants against members is constants times members on every analysis of a clean project: 45.7 s against 1.6 s at 4,000 x 40,000, invisible to the bench
18|M1|src/ddd/analysis.py:3324|The caps have a hole: a structure with no leaf is walked unbounded, a 12 kB types file never returns; a member of 300 dimensions ends in python's advice (KNOWN in part, S-M1)
18|M2|src/ddd/analysis.py:1992|Every did you mean sweeps the vocabulary with no memo per spelling: 266 s at 35,000 uses of a removed type among 3,000; a cycle of 8,000 is 91 s
18|M3|src/ddd/identity.py:191|ddd id --assign is quadratic in one file: 8 s at 5,000 declarations, 118 s at 20,000
18|M4|src/ddd/models/conversion.py:415|Every float32 without stated limits states limits past what a float32 holds: 3.40282346639e+38 above FLT_MAX (adds to pass 8 M1)
18|M5|src/ddd/analysis.py:2682|The limits-out-of-range tolerance covers integer storage: uint32 max 4294967299 passes --strict and reaches the a2l (adds to pass 7 M8)
18|M6|src/ddd/analysis.py:3253|A member past MATRIX_DIM is one a2l-unrepresentable per element and per variable, at a file that cannot fix it: 2,000 warnings for one member
18|M7|src/ddd/compare.py:545|The comparison reports one edit of a member once per element and in text order: A[0], A[10], A[11], A[1] (remainder of P9-M7)
18|M8|src/ddd/ir.py:368|Small untrue sentences: exactly one storage lets two through, include order does decide a reference under two locals, enums used by the objects, not readable as json of a readable file
```

## Pass 19: code review of the periphery

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-19/`. Line numbers are on the review tree.

### Scope covered

- **Read in full, with line numbers:** `src/ddd/cli.py` 1-2076; `src/ddd/plugins.py` 1-530; `src/ddd/backends/__init__.py`, `base.py` 1-549, `a2l/__init__.py`, `a2l/backend.py`, `a2l/model.py` 1-750, `a2l/options.py`, `a2l/types.py`, `a2l/templates/project.a2l.jinja` 1-162, `c/__init__.py`, `c/backend.py`, `c/literals.py` 1-233, `c/model.py` 1-637, `c/options.py`, `c/types.py`; `src/ddd/build_info.py`, `addresses.py` 1-259, `__init__.py`, `__main__.py`, `difflib_lock.py`; `cmake/Ddd.cmake` 1-794.
- **Read for how the scope is used:** `src/ddd/diagnostics.py` 293-590, `deliveries.py` whole, `loading.py` 516-665, 1040-1190, 1394-1503, `names.py`, `editing.py` 55-100, 880-950, `identity.py` 175-210, `gui/compare.py` 380-410, `models/component.py` 40-90, `models/common.py` 405-419; `SPEC.md` 1114-1221, 1681-1702, 2179-2211; `docs/plugins.rst` whole, `docs/command_line_interface.rst` 150-195, `docs/generated_artefacts.rst` 612-660, `docs/build_integration.rst` 262-272; commit `a497da33`; `examples/plugins/ddd_layout.py` by grep; `tests/test_cli.py` 3010-3055, `tests/test_plugins.py` 1370-1410, 1455-1470, and greps over the tests of this area; the previous review's pass 10; the left-open items of `plans/2026-09-16-review-fixes.md`; the candidates of passes 1 to 18, passes 8, 9, 17 in full.
- **Ran:**
  - `tests/test_plugins`, `test_backends`, `test_generation`, `test_a2l`, `test_example_plugin`, `test_addresses`, `test_cli`: 694 passed (`tests.txt`).
  - `cli/silent.py`: 12 commands over 18 broken and healthy roots under three policies, in process, looking for a run that ends in silence or raises out of `main`: 648 runs (`cli/silent.txt`).
  - `plug/run.py`: 37 misbehaving plugins, each under `check` and `check --format json` and the verbs its fault concerns (`plug/run.txt`); `plug2/roundtrip.py`, `plug2/obj/`, `plug2/race.py`, `plug2/pk/`.
  - `cli/run1.py` to `run5.py`: `--force` into the backends, template errors, an empty `-o`, a raising model, 13 hand-broken manifests, closed pipes and unprintable usage errors in process.
  - `pipe/`: real pipes with 4,000 findings. `cm/`: one CMake and Ninja story (CMake 4.4.3, Ninja 1.13.2).
  - `mf/stress_os.py`, `stress_delay.py`, `stress_write.py`: the refusal pass 17 handed on, about 70,000 renames, with no ddd and with the real writer. `mf/pair_writer.py`, `pair_cli.py`: two runs at once. `mf/interrupt.py`.
  - `wsl/writer.py`: the real `backends/base.py` on Linux, python 3.12, `ddd.ir` stubbed since WSL has no pydantic: links, fifos, modes, devices, a case-insensitive directory.
  - `perf/phases.py`, `unique.py`, `e2e.py`: the backends on pass 17's three projects of 100,000 declarations, and on 16,000 conversions and a 1,000,000 element array. `status/s.py`: the previous review's findings.
- **Not covered:** macOS itself (M10 is reproduced on the same condition under WSL). The full command line on Linux: no pydantic in WSL, so a Linux claim about `main` rests on the mock `tests/test_cli.py` uses, and the writer's on the real module. `ADDRESSES_FROM_IMAGE` end to end (MinGW links PE). No mutation testing: pass 22. M7 was not driven through a running `ddd gui`.
- **An accident of this pass.** `wsl/writer.py`, run once as root to exercise M9 on a device of its own, also replaced the real `/dev/null` of the WSL instance with a regular file. I restored it at once with `mknod -m 666 /dev/null c 1 3` and checked it from root and from the user (character device 1,3, mode 666, writable); checked again at the end of the pass, it is still so. The repository and Windows were not touched, and the probe's two directories in WSL's `/tmp` are gone. The script no longer does this as root.
- **Met again and cited rather than re-filed, with what the inside adds:**
  - pass 1 M5: its sharp form: a manifest naming the run's own `b.ddd.json` under `c`: `removed .../b.ddd.json`, exit 0, the description the run had just read is gone. `_refuse_a_source` is asked of writes and not of removals (`cli/run3.txt`, `source_in_dir`).
  - pass 5 I4, pass 9 M2: one more hole, and the likeliest: `logging.basicConfig(stream=sys.stdout)` at import binds the real stdout, so `logging.info` from a hook lands at the head of `ddd dump` and of `check --format json`, which then does not parse (`cli/run5.txt`).
  - pass 5 M12: the failure M1 measures shows it: a refused manifest rename leaves `ddd_globals.c` updated, the stale header removed and the new header taken back, neither of the two on disk, exit 2 (`mf/stress_write.txt`, `left`).
  - pass 6 M5, pass 17 M3: see M12 and M16.
  - pass 9 M1: real pipes here give 120 and 2; I3 adds the 0 and why it matters.
  - pass 9 M5: corrected by I2: the fallback is not dead.
  - pass 9 M14: the cause of `--dictionary out/.ddd-manifest.json`'s advice about path lengths: both payloads stage onto one `.ddd-manifest.json.ddd-staging`, the first rename spends it, the second meets `ENOENT`.
  - pass 13 C2: `write()` has the same fixed stage name; M11 is what it costs there.
  - pass 2 I6, pass 13 I4, I5: M1 and M9 are the same writer's other copies.
  - pass 1 C2, I6, pass 5 I3, I5, pass 7 M6, pass 8 I3, M2-M5, M7, M11, M13, M15, M16, pass 9 C1, I1-I5, M3-M13: read at the lines, stand as filed.

### Strengths

- **No path ends in silence on a project's fault.** 648 runs, every command over missing, empty, non-json, wrong-kind, future-format and broken roots, under no policy, every overridable check ignored, and `--strict`: none raised out of `main`, none ended with nothing said (`cli/silent.txt`). The eight fixed checks are exactly what makes that hold: a root that cannot be read cannot be relaxed away.
- **The "cannot miss" comments hold.** `c/model.py:342-343`, `:617-619`, `a2l/model.py:347-348`: a placed instance of a structure with an unknown member, a curve over a missing axis, a measurement, an instance, under `--force` and under relaxation: the analysis drops the object first, no `KeyError`, one sentence saying so (`cli/run2.txt`).
- **The manifest fails safe.** 13 hand-broken records (a NUL, a colon, a device name, a wildcard, 5,000 characters, `..`, an absolute path, a list, a byte order mark, an unknown format): nothing raises, nothing outside the directory is touched, the next record is right (`cli/run3.txt`). The rollback is what its docstring says it is, and it says what it does not do (`base.py:301-308`).
- **A template's mistake is one sentence.** Missing import, undefined name, recursion, division by zero, a bad argument to a helper, undecodable bytes: seven of seven name the template, the line and the reason, findings first (`cli/run1.txt`).
- **The backends are linear and cheap.** 50,000 objects: c model 0.7 s, a2l model 0.4 s, render 3 s, a rerun of 3,337 unchanged files 3.5 s, nearly all of it `realpath` (`perf/phases.txt`). The previous review's quadratic and exponential walks are gone. 1,000,000 elements render in 1 s (`perf/e2e.txt`). The one exception is M14. The 28 s I first saw for a rerun was this machine reading cold files, not the code.
- **The guards around a plugin's hooks hold where they stand.** A hook or validator that raises, exits or is interrupted, a non-`Plugin`, a bad return from `backend` or `generate`, a path outside the directory: each as documented (`plug/run.txt`), findings first for a hook.
- **`difflib_lock` does what its first line says.** All three calls into `difflib` in the tree hold it, each for one call, and it nests with nothing. Whether it is the right cure is unknowable, and its docstring says so.
- **`Ddd.cmake` has nothing new beyond pass 9**, read line by line, but for I2.

### Issues

#### Critical

None.

#### Important

- **I1. A plugin's model is read back from its own dump, so an alias, a computed field or `strict` makes every run with a hook exit 2 over a block the loader has just accepted.** `src/ddd/plugins.py:284`, `:289-291`, `:351`, docstring `:344-345`; `docs/plugins.rst:130-132` ("the project block validated against `project_model`"), `:104-106` (which recommends `extra="forbid"`), `:262-263`; `examples/plugins/ddd_layout.py:59`.
  *Trigger* (`plug2/roundtrip.txt`): a plugin with a `check` hook and any of these models, the project stating a valid block, `"extensions": {"set": {"max-key": 5}}`: `Field(alias="max-key")`, the only way to key a field `class` or `max-key`; a `@computed_field` under `extra="forbid"`; `strict=True` with an enum or a date; a `field_serializer`; `Field(exclude=True)`; a validator that is not idempotent. `ddd check` and `ddd list`: exit 2, `ddd: the settings of plugin 'set' are invalid: 2 validation errors for S ... Field required ... Extra inputs are not permitted ... For further information visit https://errors.pydantic.dev/2.13/v/missing`. The control, a plain model: exit 0. Eight of eight fail. `ddd sources` passes, no hook running there.
  *Why:* `resolve_blocks` dumps the validated block with `model_dump(mode="json")`, by field name and with computed values, and `settings_of` validates that dump as if it were the description. The docstring says a failure here "comes from a dump"; it comes from any run. On a definition the same dump goes into the dictionary (`plug2/object_alias.txt`): the file and the published schema say `"key-no": 3`, `ddd dump` says `"key_no": 3`, the c templates receive that, and a hook reading the block the way the worked example does, `Entry.model_validate(block)`, fails: `plugin 'tag' failed in its check hook: 2 validation errors`.
  *Consequence:* ordinary pydantic features break a plugin outright, with a message blaming a block that validated, and nothing in the page or the SPEC says a block model must read its own dump. No test has an alias or a computed field. Reproduced.
  *Change (S-M):* dump with `by_alias=True, round_trip=True`; hand a hook the instance validated from the stated block and validate again only what really came from an archive; state the rule on the page. See open question 2.

- **I2. A plugin model that raises escapes every guard around the load: the findings are lost, `ddd sources` and `ddd artefacts` exit 2, and the CMake fallback then leaves a green build that no longer watches anything.** `src/ddd/cli.py:1896` (before the block at `:1902`), `:1808`, `:1740`; `src/ddd/loading.py:1163`; `cmake/Ddd.cmake:130-135`. Against `docs/plugins.rst:201-202`, `:222-223` ("reported the way a hook's is"), `SPEC.md:1200`, `:2202-2204` ("exit 0 whatever the findings ... they exit 1 only when the root cannot be read"), `cli.py:1798-1803`, `:1991-1994`. Corrects pass 9 M5: the fallback it calls dead is reached here. Same end as pass 9 I1, through another door.
  *Trigger* (`cli/run3.txt`): component `a` has a `schema` error, component `b` a block whose validator raises `RuntimeError`. `ddd check`: only `ddd: plugin 'bad' failed validating an 'extensions' block: validator defect`, exit 2; the `schema` finding is gone. `--format json`: stdout empty, no document. A hook raising in the same place reports its findings first, as the pages promise. `ddd sources`, in both formats, and `ddd artefacts`: exit 2, no listing.
  *The build* (`cm/run.txt`): `ddd_generate(fw PROJECT p.ddd.json ...)`, the validator raising at configure: exit 0, one status line, `the generation will depend on that file alone`. Build: exit 2, loud. Fix the validator: build green. Then `uint8` to `uint16` in `alpha.ddd.json`: `ninja: no work to do`, twice, `volatile uint8_t AlphaVar` in the output, `ddd check` clean. A hand re-configure mends it, and nothing asks for one, because the fallback returns before `CMAKE_CONFIGURE_DEPENDS` is set, not even the project file. One `KeyError` in a validator during a re-configure is enough, which is what a plugin under development does.
  *Change (S):* move `load_workspace` inside the block in `_analyze`; in `sources` and `artefacts` report the defect as `plugin-invalid` beside the listing; in the fallback keep the project file as a configure dependency and print a `WARNING`.

- **I3. A closed pipe turns a failing check into exit 0.** `src/ddd/cli.py:137-146`. Against `SPEC.md:2179-2180`, `docs/command_line_interface.rst:160-161`; `SPEC.md:2183-2185` and `docs/command_line_interface.rst:189-191` speak of a reader of standard output and of `ddd schema`, which has no verdict to lose.
  *Trigger* (`pipe/run.txt`, a real pipe on this Windows): a project of 4,000 errors, plain: exit 1. `set -o pipefail; ddd check big.ddd.json --format json | head -1`: `PIPESTATUS` 0. In process, with a stream raising `BrokenPipeError` as `tests/test_cli.py:3018` does (`cli/run4.txt`): `examples/inconsistent`, 4 errors, exit 1 when left alone: 0 for `check` with its text report cut on *stderr*, for `check --format json`, `list` and `dump`. The same pipes here also give 120 for the text report and 2 for `list` (pass 9 M1), so one project's verdict reads 0, 1, 2 or 120 by stream and platform.
  *Consequence:* it takes output past what the pipe holds, or a reader gone before the last line, so the more broken the project, the likelier the green: under `shell: bash` in a GitHub workflow, which sets `pipefail`, `ddd check p 2>&1 | head -50` passes a project with hundreds of errors and fails one with three (reasoned for Linux from the handler and the mock; the full tool cannot run there here). The trigger is narrow; the exit code is the contract. The comment at `:138-142` weighs a pager and not a verdict. The handler cannot tell stdout from stderr, nor a run that found errors from one that did not.
  *Change (S):* keep the verdict where the run has one: return `EXIT_FINDINGS` if the bag holds errors, 0 only where there is none. See open question 1.

#### Minor

- **M1. The refusal the edit engine retries stops `ddd generate`: a target written milliseconds ago refuses the rename (pass 17's `.ddd-manifest.json`).** `src/ddd/backends/base.py:370`, `:374`, `:378`; `src/ddd/identity.py:201`; against `src/ddd/editing.py:66-76`, `:934-946`. **Real, and not the manifest's doing.** With no ddd at all, write a file and replace a target with it in a loop: 484 of 20,000 refused, all `WinError 5`, all 484 cured by one immediate retry (`mf/stress_os.txt`). The age of the target decides it (`mf/stress_delay.txt`): a new target each round 0 of 10,000; same target at once 2.02 %, 1 ms old 1.04 %, 10 ms 0.23 %, 100 ms 1 of 1,500, 500 ms 0 of 300. The real writer: 7 of 5,000, five on `.ddd-manifest.json`, two on `ddd_globals.c`: `cannot write ...: Access is denied`, exit 2 (`mf/stress_write.txt`). The cause is not established; no reader of ours is involved, so it looks like a scanner or indexer on this managed machine. Commit `a497da33` met this on CI's windows runners and fixed the edit engine alone, reasoning from a reader in `ddd gui`. Rare between processes, and a retry build passes: a flake with an unhelpful sentence. `ddd id --assign` calls it `cannot be written, skipped`. In-process repeats, a test suite's above all, are where it bites. *Structural:* stage-and-rename exists three times, with one retry, one `_keep_access` and one fixed stage name in common. *Change (S-M):* one `stage_and_replace` both call.

- **M2. `Plugin(name="bad\n")` passes: `.match` on a pattern ending in `$` (pass 17's `plugins.py:113`).** `src/ddd/plugins.py:113`, `:124`. **Real.** Against `SPEC.md:1145`, `:1149`, and `plugins.py:44-47` "cannot drift apart". Reproduced (`plug/run.txt` `imp_name_nl`, `imp_check_nl`; `plug/name_nl.txt`): no `plugin-invalid`, exit 0. One finding prints as two lines, `<project>: warning[bad\n/x]: said`; `ddd artefacts`' note and `compare`'s `missing-plugin` split; the dictionary records `"bad\n"`; a block keyed so is `schema`; `ddd generate` refuses the name. So a half-usable plugin. The same on a check, `bad/x\n`. `addresses.py:117` has the form too and strips first; `models/reserved.py:71` and the pointer patterns see validated or generated text. `fullmatch`, twice; S.

- **M3. A finding that is no finding, and unguarded reads of a plugin's objects, end in a traceback under the findings code with every finding lost (P5-M2).** `src/ddd/diagnostics.py:563`, `:392-396`; `src/ddd/cli.py:128-154`, `:1958`, `:1972-1973`; `src/ddd/plugins.py:151`, `:220-227`, `:245`, `:446`. Reproduced (`plug/run.txt`): `context.bag.add("bad/x", "m", Path("file.json"))`, the natural slip, or a `str`, or `Location("file.json")`, or `severity="warning"`: `AttributeError`, exit 1, stdout empty under `--format json`. A `Path` as message: a `TypeError` under `--format json` alone. `notes=["see here"]`: `ddd: too many values to unpack (expected 2)`, exit 2, naming no plugin. A custom `BaseException` or `asyncio.CancelledError` at import: traceback, exit 1, under `check`, `sources`, `checks`, against `SPEC.md:1143-1145`; `tests/test_plugins.py:1372-1405` pins the hook and the model and not the import. A module `__getattr__` that raises; `backend.name` a raising property. Exit 1 reads as "the project has errors" (`docs/command_line_interface.rst:160-161`). Pass 9 left P5-M2 unfiled as reached only through plugin misuse; this is the misuse of a plugin's first day. *Change (S):* validate in `DiagnosticBag.add`, so the failure raises inside `_call` and names the plugin; a last-resort clause in `main`, exit 2.

- **M4. A hook that fails says nothing about how, and nothing can make it.** `src/ddd/plugins.py:528`, `:218`, `:256`, `:335`; `src/ddd/cli.py:152-154`. Reproduced (`plug/run.txt`): `assert`, `raise RuntimeError()`, `next(iter(()))`: `ddd: plugin 'bad' failed in its check hook:`, and nothing after the colon. At import: `error[plugin-invalid]: plugin 'plug.py' failed to import: `. `{}["k"]`: `failed in its check hook: 'k'`. The type and the line are dropped, the `from error` is never printed, and no option or variable shows the traceback, so a plugin's author has to wrap the hook in a `try` to learn what happened. Of all the ways `cli.py` ends this is the one that does not say why. *Change (S):* `f"{type(error).__name__}: {error}"` and the plugin file's last frame. See open question 5.

- **M5. A check hook that returns its findings, is a generator or is `async` runs nothing, and `ddd check` passes.** `src/ddd/plugins.py:367`, `:515`. Reproduced (`plug/run.txt`, `hook_returns`, `hook_generator`, `hook_async`): exit 0, the plugin's finding absent; the last adds a `RuntimeWarning` at exit. `backend_of`'s docstring knows "python does not enforce a return type at runtime" (`:429-436`) and holds `backend` and `generate` to theirs, not `check` and `compare`. A rule that never ran reads as a rule that passed, which is what `missing-plugin` exists to prevent. *Change (S):* a return other than `None` is a `PluginError`.

- **M6. A plugin's `os.chdir` moves where the run writes.** `src/ddd/backends/base.py:228`, `src/ddd/backends/c/backend.py:144`. Reproduced (`plug/run.txt`, `imp_chdir`, `hook_chdir`): `ddd generate c p.ddd.json -o out -t t`: `no template directory at 't'`, which is there. With an absolute `-t`: exit 0, `wrote out/a.c (created)`, the file at `elsewhere/out/a.c`. `_call` restores stdout and not the directory. *Change (S):* resolve the command line's paths before the load.

- **M7. Two threads meeting a path plugin for the first time: the second gets the half-run module and `plugin-invalid`.** `src/ddd/plugins.py:196-198`, `:205`. Reproduced at the function (`plug2/race.txt`): `exposes no PLUGIN that is a ddd.plugins.Plugin`, while the first thread loads it. `importlib.import_module` holds a lock per module; this path holds none. In `ddd gui`, `gui/compare.py:393` reads on a request thread beside the analysis thread's `lsp/diagnostics.py:201`, so a baseline naming a plugin the first analysis is still importing is refused for it (not driven through the server). Rare. A lock; S.

- **M8. Of a plugin that is a package, a build watches `__init__.py` alone.** `src/ddd/plugins.py:168-169`; against `docs/plugins.rst:36-37`, while `:238-239` sends shared code into exactly such a package. `ddd sources` lists `mypkg/__init__.py` and not `mypkg/impl.py` (`plug2/package.txt`); an edit of the second is then `no work to do` (read off, the machinery of pass 9 I1). The build's half of pass 14 I4. List the package's directory, or say so; S.

- **M9. The writer replaces whatever stands at a target named on the command line: a link, a fifo, a mode a person set, and as root `/dev/null`.** `src/ddd/backends/base.py:327`, `:370`; `src/ddd/cli.py:1126`, `:1458`. Reproduced with the real module on Linux (`wsl/writer.txt`, `wsl/writer_root.txt`): `-o link.json`: `updated`, the link now a regular file, `real.json` still old, the twin of pass 13 I5; `generate`'s own artefacts are resolved and follow a link, so `-o` and `--dictionary` are the odd ones. A fifo: `created`, now a regular file, its reader told nothing. Mode 640 becomes 644, 444 becomes 644. As root, `-o /dev/null`: `created`, a regular file of mode 644, the system's device gone; `docker/Dockerfile` has no `USER`, so that is who the project's own image runs as. `-o /dev/fd/4`, a shell's `>(...)`: `the path itself that was refused: 9 characters`. On Windows `-o NUL` is refused harmlessly, in misleading words (`pipe/run.txt`). `base.py:288-296` weighs open handles and hard links, not these. *Change (S):* a target that is neither regular nor absent is written through or refused; resolve a link first; `_keep_access`. See open question 3.

- **M10. A component renamed in case alone, on a case-insensitive disk under posix paths: the run deletes the header it has just written.** `src/ddd/backends/base.py:184`, `:372-376`. Reproduced with the real writer under WSL in a directory of NTFS (`wsl/writer.txt`, g): `[('SENSOR.h', 'updated'), ('Sensor.h', 'removed')]`, exit 0, only the manifest left; the next run recreates it. `path in written` compares spelling where the disk does not; `WindowsPath` equality saves Windows; macOS's default disk has the condition and is not in CI's matrix (`ci.yml:45`), which is why this was never seen. The header being no declared output (`Ddd.cmake:646`), ninja has no reason to regenerate, so compiles fail until a description changes (read off). `os.path.samefile` before taking back; S.

- **M11. `generate c` and `generate a2l` at once into one directory lose the record, and sometimes the run.** `src/ddd/backends/base.py:338-344`, `:365`, `:378`; `:280-281` "race on it exactly as they always raced on the real targets" is untrue: two artefacts never shared a target, only this file and its stage. `SPEC.md:1691` and `docs/generated_artefacts.rst:655-659` bless the pair in sequence and warn only about shared artefacts. Reproduced (`mf/pair_cli.txt`), 40 pairs on a clean directory, what `make -j` does with two rules: 38 clean, 2 failing with `Access is denied`, `Permission denied`, or `... it is the path itself that was refused: 149 characters`. The manifest afterwards names both artefacts in 32 and one or none in 8, mostly under exit 0; a component then dropped leaves its header for good, which is the one thing the manifest is for. The CMake module orders its two runs and is not affected. See open question 4.

- **M12. `main`'s last word can raise: a usage error holding a lone surrogate escapes with a traceback, exit 1.** `src/ddd/cli.py:150`, `:153`, cause at `:118`. Reproduced in process (`cli/run4.txt`): `-W '\udcff=ignore'`, `--component '\udcff'`, `dump -o 'nosuch\udcff/x/../..'`; on Linux a non-utf-8 byte in `argv` is exactly that. Adds to pass 17 M3, whose `errors="backslashreplace"` ends this too.

- **M13. `-o` given nothing, or a directory.** `src/ddd/cli.py:644-647`, `:1920-1930`. Reproduced (`cli/run5.txt`, `cli/run1.txt`): `ddd generate c p -o "$UNSET" -t t`: `Path("")` is the working directory: `wrote a.c (created)`, a manifest beside it, exit 0, where `dump -o ""` is refused: pass 9 I4's shape on the command line. `dump -o sub`, `-o ..`: `cannot write 'sub': Access is denied` on Windows, of a directory with nothing wrong with its access; the docstring at `:1923` names `-o ..` among what it refuses. S.

- **M14. The a2l's method names are quadratic in the conversions sharing a unit.** `src/ddd/backends/a2l/model.py:680-686`. Each new method counts up from `_2` again. `build_a2l_model`, N objects each with a factor of its own in one unit: 0.53 s at 2,000, 2.19 s at 4,000, 10.9 s at 8,000, 41.6 s at 16,000 (`perf/e2e.txt`, `perf/unique.txt`), against 0.4 s for 50,000 objects otherwise. An imported project with many scalings pays it at every generation. A counter per base; S.

- **M15. An interrupted write takes nothing back, and what it leaves no later run removes.** `src/ddd/backends/base.py:379`, `:36-42`; `SPEC.md:2207-2211`. Ctrl-C between two renames (`mf/interrupt.txt`): `a.h` created, `b.h.ddd-staging`, `c.h.ddd-staging` and `.ddd-manifest.json.ddd-staging` left, the old record standing. A next run no longer asking for `b.h` and `c.h` leaves their stage files for good: no record names a staging file, and "overwriting that one is right" reaches only a name written again. Harmless bytes in a directory nothing else cleans. Clean up on `BaseException`; S.

- **M16. Small untrue sentences.** Each read off, the first reproduced.
  - `src/ddd/plugins.py:308-309`: `PluginError` is "one line naming the plugin and the hook". A settings failure is four to eight lines ending in pydantic's url (`cli/run5.txt`, `plug2/roundtrip.txt`).
  - `src/ddd/cli.py:1995-1997`: "`list`, `artefacts`, `sources` and a `dump` to stdout have nothing fallible after their analysis". `dump`'s `print` raises on a lone surrogate (pass 6 M5) before `_report` at `:1359`, and the findings are gone.
  - `src/ddd/cli.py:1177-1179`: "must not be killed by one it was never going to read" reasons about a case `_selected` has refused at `:1048`; `args.render_a2l and` is dead.

### Status of the 2026-09-15 findings in this area

Plainly fixed, each run or read at the line (`status/s.txt`): P10-I1 (`loading.py:1422`), P10-M1 (`c/model.py:385`), P10-M2 (`a2l/model.py:267`), P10-M3 (`a2l/model.py:218`), P10-M4 (`c/model.py:339`), P10-M5 (`addresses.py:64`), P10-M6 (`addresses.py:28`, `:96`), P10-M7 (`cli.py:1920`), P10-M8 (`cli.py:1334`, `:1358`), P10-M9 (`cli.py:2034`), P10-M10 (`cli.py:777`); the forwarded `docker/compile.sh` item (rewritten).

| id | finding | status | where |
| --- | --- | --- | --- |
| P10-I2 | a keyword given no value | FIXED for the bare form, open for the quoted one | `Ddd.cmake:448`, pass 9 I4 |
| P10-M11 | templates run unsandboxed | DOCUMENTED by decision of 2026-09-16; whether to sandbox stays the maintainer's (KNOWN) | `docs/plugins.rst:253-257`, `docs/templates.rst` |
| P10-M12 | module and tool one release | FIXED; the handshake's cache remains | `Ddd.cmake:57`, pass 9 M4 |
| P10-M13 | `IF_DATA XCP` without A2ML | OPEN, left to the maintainer, documented as a reader's obligation (KNOWN) | pass 1 I8, pass 4 I3 |
| P5 minor 2, the P10 "residue" | no last-resort handler in `main` | STILL OPEN, and reachable by an ordinary slip | M3 |
| P10 design note "report before you write" | the class of exception the block does not list | STILL OPEN; and the load itself stands outside the block | M3, I2 |
| P5 minor 3 | hooks receive mutable dicts | documented; what they receive is also not what was validated | `docs/plugins.rst:147-154`, I1 |
| earlier P8 minor 2 | `reconfigure` without `errors=` | STILL OPEN | pass 17 M3, M12 |
| earlier P8 minor 4 | `Sensor` and `Sensor_` share a guard | STILL OPEN | pass 8 M11 |

### Open questions

1. **What does a closed pipe do to a verdict (I3)?** Keeping 1 means `ddd check | head` under `pipefail` fails on a broken project, where a pager over `list` or `dump` of a project with errors fails too: the case the comment at `cli.py:138-142` set out to spare. Keeping 0 means saying in SPEC 7 that a cut report loses the verdict. A closed stderr should not be 0 in either answer.
2. **What does the dictionary carry of a block (I1): what the file says, or the model's field names?** The first (`by_alias=True`) keeps file, schema, dump and templates in one spelling and changes what an archive holds for any plugin with an alias, which today cannot work with hooks anyway. The second keeps the shape and needs hooks handed an instance. Either way the page must state that a model reads back its dump.
3. **An output path that is not a regular file (M9): written through, or refused?** Through keeps `-o /dev/null` and a link working and gives up staging for them. Refused is simpler and makes `-o /dev/null` a usage error.
4. **Is `generate` of two artefacts at once into one directory supported (M11)?** Yes needs a lock, or a stage name per process and a record per artefact. No needs a sentence in SPEC 5 and on the page, and `base.py:280-281` corrected.
5. **Should a plugin's author be able to see a traceback (M4)?** A `DDD_TRACEBACK` variable costs no option on the contract; a `--debug` costs one. Without either, the type and the last frame in the one line are the most the tool can say.

### Test gaps

- No plugin model in the suite has an alias, a computed field, `strict`, a serializer or an `exclude`; `tests/test_plugins.py:977` round-trips the dictionary, never a block through its model (I1).
- `tests/test_plugins.py:1455-1465` asserts the raising validator's sentence and not that the findings came first, nor anything of `--format json`, `sources` or `artefacts`. `tests/test_cmake.py` has no plugin that raises at configure (I2).
- `tests/test_cli.py:3014-3050` closes a pipe only on `ddd schema`, which has no verdict: no failing project, no stderr, no real pipe (I3, pass 9 M1).
- No test retries a refused rename in `backends/base.py` or `identity.py`; `tests/test_generation.py:402`, `:537` assert a refusal stands. `tests/test_editing.py:735-773` pins the retry where it exists.
- `tests/test_plugins.py:161`, `:166` try malformed spellings without a trailing newline (M2).
- `DiagnosticBag.add` with a wrong location, severity, message or notes: none. A `BaseException` at import, a raising `__getattr__`: none, where the hook and the model have theirs (M3).
- A hook that returns, yields or is `async`: none (M5). An `assert` or an empty exception in a hook: none (M4).
- `write()` over a link, a fifo, a device, a mode: none (M9). A case-only rename: none (M10). Two runs at once: none (M11). An interrupt during the write: none (M15).
- An empty `-o` on `generate`: none (M13). A bound on `_unique`: none; `tests/test_a2l.py` pins `_2` alone (M14).

### Assessment

The periphery is careful and mostly earns its prose. The command line does not end in silence on anything a project can do to it, the backends' internal assumptions held under everything `--force` could send them, the manifest refuses to be fooled by a broken record, and the previous review's performance findings are gone. What I found sits where the code meets something it does not own. A plugin is guarded against raising and not against being a normal pydantic model: dumping a block and validating the dump is not a round trip, so an alias or a computed field breaks every run (I1), the load stands outside the block that is meant to protect the findings (I2), and what a hook leaves in the bag is judged by nobody until the report falls over (M3). The operating system is treated as if a rename were atomic and free: the transient refusal commit `a497da33` fixed in one writer is real, measured, and unfixed in the two others (M1), and whatever stands at a target gets replaced, which I demonstrated on this machine's own `/dev/null` by accident (M9). The closed pipe's 0 was decided for a pager and forgets that `ddd check` has a verdict (I3). Both things pass 17 handed on are real and both are one small fix. None of this is wrong output on a clean project, and I would fix I1 to I3 and M1 to M4 in a day or two; the structural point worth a decision is that stage-and-rename exists three times with different protections.

```candidates
19|I1|src/ddd/plugins.py:351|A plugin's model is read back from its own dump: an alias, a computed field or strict makes every run with a hook exit 2 over a block the loader accepted; the dictionary carries key_no where the file says key-no
19|I2|src/ddd/cli.py:1896|A plugin model that raises escapes every guard around the load: findings lost, no json document, sources and artefacts exit 2 against SPEC, and the CMake fallback leaves a green build watching nothing (corrects pass 9 M5)
19|I3|src/ddd/cli.py:137|A closed pipe turns a failing check into exit 0: 4,000 errors, head -1 under pipefail, PIPESTATUS 0; one verdict reads 0, 1, 2 or 120 by stream and platform
19|M1|src/ddd/backends/base.py:370|A target written milliseconds ago refuses the rename and generate stops with Access is denied (pass 17's manifest, real, no ddd needed): 2 % at once, cured by one retry; editing.py retries, base.py and identity.py do not
19|M2|src/ddd/plugins.py:113|Plugin(name="bad\n") passes through .match with $ (real): a finding on two lines, the name in the dictionary, against SPEC's grammar and cannot drift apart
19|M3|src/ddd/diagnostics.py:563|A hook's bad finding, a BaseException at import, a raising __getattr__: traceback under the findings code, every finding lost; no last-resort handler (P5-M2)
19|M4|src/ddd/plugins.py:528|A hook that fails says nothing about how: assert leaves failed in its check hook: and nothing after, KeyError reads 'k', no switch shows a traceback
19|M5|src/ddd/plugins.py:515|A check hook that returns its findings, is a generator or is async runs nothing, and ddd check passes
19|M6|src/ddd/backends/base.py:228|A plugin's os.chdir moves where the run writes: wrote out/a.c, the file at elsewhere/out/a.c; a template directory that is there is told missing
19|M7|src/ddd/plugins.py:205|Two threads meeting a path plugin first: the second gets the half-run module and plugin-invalid; reachable from ddd gui's compare beside an analysis
19|M8|src/ddd/plugins.py:168|Of a plugin that is a package, a build watches __init__.py alone, against a build re-runs when a plugin changes
19|M9|src/ddd/backends/base.py:370|The writer replaces whatever stands at a named target: a link, a fifo, a mode, and as root /dev/null
19|M10|src/ddd/backends/base.py:184|A component renamed in case alone on a case-insensitive disk under posix paths: the run deletes the header it just wrote, exit 0
19|M11|src/ddd/backends/base.py:338|generate c and generate a2l at once into one directory lose the record in 8 of 40 and the run in 2; base.py's race sentence is untrue
19|M12|src/ddd/cli.py:153|main's last word can raise: a usage error holding a lone surrogate escapes as a traceback, exit 1 (adds to pass 17 M3)
19|M13|src/ddd/cli.py:1920|generate -o "" writes into the working directory where dump -o "" is refused; -o a directory reads Access is denied; the docstring names -o ..
19|M14|src/ddd/backends/a2l/model.py:682|The a2l's method names are quadratic in the conversions sharing a unit: 41.6 s at 16,000
19|M15|src/ddd/backends/base.py:379|An interrupted write takes nothing back, and its stage files are left for good once not written again
19|M16|src/ddd/plugins.py:308|Small untrue sentences: one line of PluginError, nothing fallible after a dump to stdout, a dead guard on the address map
```

## Pass 20: the repository and the remaining documents

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-20/`. Line numbers are on the review tree, `master` being `2b4bae6c`.

**The answer to the question asked.** What a person gets who installs the wheel is complete and works. The wheel holds the GUI's pages, both licence files, the CMake module, the templates and the a2l backend's own template, built twice by two routes to the same hash. The tutorial reproduces to the byte from outside the repository, `ddd gui` serves all eight tabs, an edit and its undo round trip exactly, and all 294 journeys pass with the wheel as the server. The sdist is self-contained: its suite, its documentation under `-W`, and its pages recompiled byte for byte. The holes are around it: the licence list leaves out one bundled package and its gate has a matching hole, Dependabot has never opened a pull request, and the documentation site crowns a release that Publish refused. What stands between master and a release is not packaging: it is the Critical list of the earlier passes and a changelog that does not yet tell the truth (pass 4 I7, I8).

### Scope covered

**Read in full, with line numbers:** `README.md` 1-1058; `CHANGELOG.md` 1-2046 (pass 4 read to 240); `SECURITY.md`; `docs/getting_started.rst` 1-619, `concept.rst` 1-588, `faq.rst` 1-769, `data_contracts.rst` 1-352, `developer_documentation.rst` 1-1201, `index.rst`, `acronyms.rst` 1-262, `conf.py`, `_static/js/versions.js`, the head of `_templates/versions.html`; `pyproject.toml`; `requirements.txt`, `requirements-dev.txt`, `requirements-docs.txt`; `.gitignore`, `.gitattributes`, `.dockerignore`, `.pre-commit-hooks.yaml`; `.github/workflows/ci.yml`, `docs.yml`, `publish.yml`, `.github/dependabot.yml`; `docker/Dockerfile`, `elf-fixtures.Dockerfile`, `compile.sh`, `verify_symbols.py`, `build_elf_fixtures.py`, `build_address_fixtures.py`, `docker-compose.yml`; `tools/dev_version.py`, `site_versions.py`, `generate_project.py`, `bench_gui.py`; `gui/scripts/licenses.mjs` and the head of `schemas.mjs`, `gui/package.json`, `gui/vite.config.ts`; `editors/vscode/package.json`, `.vscodeignore`; `examples/cmake/CMakeLists.txt`, the head of `examples/plugins/ddd_layout.py`, and the rest of `examples/` by running it. Pass 7 of the 2026-09-15 review (`review-2026-09-15.md:2685-3099`) and the candidates of passes 1 to 19, pass 4 in full.

**Ran, all outside the tree (`status-before.txt` against the last status: unchanged):**

| What | Result | Transcript |
| --- | --- | --- |
| `python -m build --outdir` from the tree, `twine check --strict` | wheel 106 files, sdist 730 files; both PASSED | `build.log`, `wheel.txt`, `sdist.txt` |
| the wheel into a fresh venv; the whole tutorial from outside the repository, in Git Bash | every command and exit code as the page shows | `tutorial.sh`, `tutorial.log` |
| `ddd gui` of the wheel, driven in headless Edge: all eight tabs; Adopt, Undo, Put back; start page; the demo | no failed request but one harmless 409 after Adopt; the project comes back exactly | `walk_wheel.log`, `edit_wheel.log`, `shots-wheel/` |
| **every journey from the unpacked sdist, `DDD_PYTHON` being the venv holding the wheel** | 294 passed in 11.9 minutes, in Edge | `e2e_wheel.log`, `e2e.log` |
| Vitest from the sdist | 959 passed, 100 % on all four counters | `e2e_wheel.log`, `vitest.log` |
| README's commands over the sdist's examples from the wheel; `ddd schema all` against the committed schemas; `ddd lsp` handshake; `from-elf`; `--image`; a plugin's artefact | all as documented; the schemas identical byte for byte | `run_examples.sh`, `examples.log` |
| `docker/compile.sh` with MinGW gcc on a copy whose only edits are `verify_symbols.py`'s path and `python3`: demo with `-DFEATURE_X`, structures, vocabulary, pressure, layout | compiled, linked and verified; "22 of 23", "23 of 23" as `README.md:975` shows | `examples.log`, `last.log` |
| README's CMake recipe with the module and the templates of the wheel | configures, builds, links, the image runs | `more.log`, `last.log` |
| the sdist's own suite, in a fresh venv, gcc on the path | 7039 passed, 3 failed, coverage 100.00 % of 14,908 statements and 4,184 branches, 11 m 19 s | `sdist_suite.log` |
| pages recompiled from the sdist: `npm ci`, `schemas`, `typecheck`, `lint`, `build` | byte for byte what the sdist holds | `pages_nouuid.log` (and `sdist_pages.log`, M3) |
| `pip install` of the sdist, of a fresh clone with no pages, and a wheel built directly from the tree | pages present; none, and `ddd gui` says why; same hash as through the sdist | `more.log`, `last.log` |
| `sphinx-build -W --keep-going -b html` from the sdist and from the tree, `pip install -e ".[docs]"` first; `-b linkcheck` | both pass; three "broken" links are this machine's certificate chain, as last time | `docs_build.log`, `linkcheck/output.txt` |
| the published pre-commit hook through `pre-commit try-repo` | fails the commit with `wrote 1 id`, passes once staged, fails on a file that does not parse | `more.log` |
| the transcripts `tests/test_transcripts.py` does not run: twelve FAQ and data contract scenarios | hold, the only extra lines being `missing-id` infos (pass 6 M13) | `faq_probe.py`, `faq.log` |
| a rehearsal of the release commit, the ten files walked to 0.12.0 on a copy; the development stamp after it | closes: see the checklist | `run_bump.sh`, `bump.log`, `bump2.log` |
| the dependency floors, the licence gate with a package relabelled, `npm audit`, `npm outdated`, `pip-audit`, a source map of the bundle | I2, I1, M1, M9 | `floor.log`, `min.log`, `min2.log`, `licence_trace.log`, `gate.log`, `last.log`, `npm-*.json` |
| GitHub, read only: `gh release list`, `gh api` on the repository, environments, Pages, rulesets, pull requests, actions, private reporting; the two indexes' json; the site's `versions.json` | below | `github-state.txt`, `github-state2.txt`, `github-state3.txt`, `repo-misc.txt`, `unreleased-interface.txt` |

**Not covered.** Docker cannot run here, so `docker/Dockerfile`, compose and the two fixture images are read off the lines (CI's `container` job builds the first and last ran green on `2b4bae6c`). WSL was left alone under the brief's rule, so the wheel was installed on Windows and Python 3.13 only; Linux and Python 3.12 and 3.14 are what CI says of them, and CI does not install the wheel (Test gaps). `mapped.spec.ts` needs a mapped drive and is left out of the journeys here as everywhere but one CI leg. I did not download the wheels on the indexes: their contents are compared by size and metadata only. No workflow was dispatched and nothing on GitHub was written.

### Strengths

- **The wheel is complete and reproducible.** `ddd/gui/static/` (`index.html`, three hashed assets, `pressable.css`, `third-party-licenses.txt`), `dist-info/licenses/LICENSE`, `ddd/cmake/Ddd.cmake`, `ddd/templates/` (five), `ddd/backends/a2l/templates/project.a2l.jinja`, `py.typed`; beyond those, exactly the tracked files of `src/ddd` (`wheel.txt`). There is no vendored third-party code in `src/ddd`, `gui/src` or `docs/_static` but the compiled pages themselves (searched, and `difflib_lock.py` is a lock around the standard library, not a copy of it). Built through the sdist and built directly, the wheels hash alike (`0671d3b7a4b80c44`).
- **A build without pages says so.** A checkout with none builds a wheel of 100 files, exit 0, and its `ddd gui` says which installations carry the pages and how a checkout builds them, exit 2; every other command works. All three builds in CI check that the wheel holds `index.html`.
- **The sdist does what `pyproject.toml:70-75` says it is for.** Suite, documentation, type checks, lint, Vitest, pages and `.vsix` all come out of it with no other input, and `ruff` and `mypy` pass there. Its three failures are environmental (Test gaps).
- **The release machinery rehearses clean.** The ten-file walk (`developer_documentation.rst:827-845`) is complete: at 0.12.0 only `getting_started.rst` fails until the other five are walked, then 1,328 tests over documentation, transcripts, address fixtures, command line and CMake pass, `twine --strict` passes and `dev_version.py` stamps `0.12.1.dev999` into its three places.
- **The promises about the past hold.** No check identifier has left the registry across seven tags (`CHANGELOG.md:13`, by script). Six of seven released changelog sections are identical to what their tag wrote; the seventh is pass 4 I7. The dictionary format at each tag is what the changelog says (4, 4, 5, 7, 7, 8, 9).
- **The GitHub side is in the state the pages describe.** Issues on, private vulnerability reporting on (`SECURITY.md`'s button exists), Pages `legacy` from `gh-pages`, `versions.json` `stable: v0.11.0` and the root redirect, `.vsix` on the last releases, CI and Documentation green on `2b4bae6c`, `0.11.1.dev305` on TestPyPI from that run. `publish.yml` and `docs.yml` have not changed since they published 0.11.0 successfully.
- **The documents in this pass's scope are honest about the tool.** Every transcript tried holds, including the ones no test runs; the tutorial's prose matches; no external link is dead; the FAQ's caps and the environment paragraph, wrong last time, are right.

### Issues

#### Critical

None. Nothing in this area writes wrong output or loses a file, and the wheel carries what it should.

#### Important

- **I1. Dependabot has never opened a pull request, though the repository rests on it.** `.github/dependabot.yml:3-8`, `requirements-dev.txt:3-7`, `docs/developer_documentation.rst:547-556`.
  *Claim:* "Nothing in the toolchain moves on its own ... What proposes the moves instead is `.github/dependabot.yml`, weekly". *Observed:* the file reached the default branch on 2026-09-16 (`f0d1756b`, seven weeks ago). `gh pr list --state all --author app/dependabot`: 0; the same search through the api: 0; no `dependabot/*` branch among the remote's; no Dependabot workflow among the repository's. `gh api .../dependabot/alerts`: "Dependabot alerts are disabled for this repository"; `security_and_analysis.dependabot_security_updates`: disabled; `dependency-graph/sbom`: 404 (`github-state3.txt`, `github-state2.txt`). Why it does not run is not readable with this token; the settings page will say.
  *What it would have proposed by now (`repo-misc.txt`, `npm-outdated.json`, `gate.log`):* `ruff` 0.17.3 and `mypy` 2.4.1, both past the caps the file exists to move; `actions/setup-node` v7 where the workflows pin `@v5`; 13 of the 18 direct packages of `gui/`, including `vite` 8.3.5 and `vitest` 5.1.0, the non-major fixes `npm audit` names for pass 12 M10; `brace-expansion` in the `.vsix` (M9).
  *Consequence:* the file's own sentence, "nothing moves at all until a release is blocked by a tool nobody upgraded or an action whose major tag was retired". *Change:* switch it on in the repository's settings and read the first batch before the release branch; or take the file and three paragraphs out and say bumps are by hand. S.

- **I2. The licence list leaves out `scheduler`, which the pages bundle, and the licence gate cannot see it.** `gui/scripts/licenses.mjs:20-24`, against its own `:1-3` and `docs/developer_documentation.rst:1034`.
  *Trigger:* `npm run build`. `npm ls --long --json` prints `react-dom` under `@xyflow/react` with a path and no `dependencies`; that entry is met first, the key is recorded, and the later top-level entry that does hold `scheduler` is skipped by `if (!packages.has(key))`. *Observed:* `scheduler@0.28.0` is the one production package of `gui/package-lock.json` not listed, and a source map of the build shows it is bundled, the one of the 25 packages with code in the pages that is unlisted; `unstable_scheduleCallback` is in `assets/index-*.js` (`licence_trace.log`, `last.log`).
  *The gate has the same hole, reproduced:* with `node_modules/scheduler/package.json` relabelled `GPL-3.0-only`, `licenses.mjs` writes its file and exits 0; the same edit to `classcat`, listed, exits 1 naming it (`gate.log`). So a package reached only below a deduplicated entry can bring in any licence, and the wheel ships it.
  *Reach:* `@xyflow/react` joined on 2026-09-18 (`0abf0374`), so every release carrying pages, 0.11.0 on PyPI included, ships React's scheduler with its MIT notice missing. *Change:* visit every entry's `dependencies` whether or not its key is known, keeping the visited set for the output alone; a test that every non-`dev` package of the lock file is listed. S, and do it before the next wheel.

- **I3. The site publishes and crowns a release that Publish refused or failed.** `.github/workflows/docs.yml:27-28,100-116`, `publish.yml:71-80`, `tools/site_versions.py:57-76`, `docs/developer_documentation.rst:704-706`.
  *Trigger:* a release tagged `v0.12.0` over a `pyproject.toml` saying `0.11.0`, or any failure of Publish's `test` or `build`. The two workflows run on the same event and neither waits for the other. Publish stops and says "Delete the release and its tag, then re-create it as v0.11.0; nothing has been uploaded yet". Documentation has by then pushed `v0.12.0/` to `gh-pages`; `tools/site_versions.py` reads the directories on disk, so `versions.json` says `"stable": "v0.12.0"` and the root redirects there (`last.log`, run on a scratch site). Deleting the release removes nothing from the site, and the page's table says a version directory is rewritten "never"; no page says how to take one out.
  *Who:* the reader of the site, sent to documentation of something `pip` will not install, for as long as nobody edits `gh-pages` by hand. Publish has failed on 4 of its 9 release runs so far (`gh run list`), and `publish.yml:66-70` records a tag of the wrong form having really reached the site. *Change:* the `build` job, which has the tree, compares the tag with `pyproject.toml`'s version on a release and refuses, as Publish does (three lines, and it covers the mismatch); for a failed test, trigger the deploy on `workflow_run` of Publish, or accept it and say on the page how to remove a directory. S.

- **I4. The release everyone installs still has what master's changelog names as holes, four weeks on, and nothing tells its users.** `SECURITY.md:5` ("Only the latest release is supported"), `CHANGELOG.md:189-192,197-200,220-226`.
  *Trigger:* `pip install ddd-tool` answers 0.11.0, and master's security work landed from 2026-10-05 on. *Evidence at the tag (`v0.11.0-security.txt`):* `v0.11.0:src/ddd/gui/server.py:243` sets the token as a cookie, which the changelog itself says "a browser sends ... to every port of `127.0.0.1`"; `:390` opens the browser on the long-lived token, "on a command line any local user could read"; `Sec-Fetch` occurs 0 times, `issue_code` 0 times, no connection cap. `v0.11.0:docs/index.rst` has no security page, and the site's root is that version. Pass 12 I2 grades what the token is worth.
  *Consequence:* those sentences are public, on `master` and in the site's `latest`, and the version users run has no advisory, no note and no date. The preview label limits who is affected; it does not change the arithmetic. *Change:* decide (open question 1). Either the next release goes out soon with the GUI's Criticals fixed, or a GitHub security advisory says what 0.11.0 lacks and what to do. S for the advisory.

#### Minor

- **M1. The dependency floor is not a floor: pydantic 2.8 and 2.9 satisfy `requirements.txt` and end every command in a traceback.** `requirements.txt:1` (`pydantic>=2.7,<3`). *Trigger:* `pip install "pydantic==2.9.2" ddd_tool-0.11.0-py3-none-any.whl`, or a constraints file doing the same. pip takes the current `typing_extensions`, `pip check` says "No broken requirements found", `ddd --version` answers, and `ddd check` ends in `PydanticSchemaGenerationError: Unable to generate pydantic-core schema for InitValue`, exit 1 (`floor.log`). 2.8.2 the same; 2.10.0 and later run, and so do 2.8 and 2.9 beside `typing_extensions` 4.12.2, so it is `type InitValue = ...` (`models/objects.py:61`) meeting a newer `typing_extensions` (`min.log`, `min2.log`). Python 3.13 only: 2.7 has no wheel for it, and 3.12 was not tried. At 2.10.0 with jinja2 3.1.0 and pyelftools 0.32, 2,496 of 2,499 core tests pass (schema text twice, one ELF test: `min_suite2.log`). A fresh venv takes the newest and is untouched. *Change:* `pydantic>=2.10`, and one CI cell at the floors. S.
- **M2. "Runs without being installed at all" stops at `--help`.** `README.md:73-80`, `docs/getting_started.rst:55-66`. In a venv holding nothing, `PYTHONPATH=src python -m ddd --version` and `--help` answer, and `check` is `ModuleNotFoundError: No module named 'pydantic'`, a traceback, exit 1 (`last.log`), against "every command shown below works with either". A line naming `pip install -r requirements.txt` is the fix. S.
- **M3. `npm run build` fails under a directory whose path holds a uuid.** `gui/scripts/licenses.mjs:12,34`. npm redacts what looks like a token in what it prints, so `entry.path` reads `...\C--git-ac11-ddd\***\scratchpad\...` and `readFileSync` raises ENOENT, after Vite has already emptied `static/` and written the pages without the licence file (`sdist_pages.log`; the same steps under a plain temporary folder pass, `pages_nouuid.log`). Loud, and rare: this review's scratch folder is such a path, and so are other tools' temporary directories. Reading the tree from `node_modules/.package-lock.json` would close it and I2 together. S.
- **M4. Publish re-runs half of what `ci.yml` says it re-runs, and never installs what it uploads.** `.github/workflows/ci.yml:7-9`, `publish.yml:21-30,51-61`, `docs/developer_documentation.rst:543-545`. "A release can be cut from a commit ... this workflow never saw" is the stated reason, and on such a commit Publish runs pytest on one cell, the type check and the build: no `npm test`, no `npm run lint`, no journey and no Windows, for a `gui/` where 28,073 lines were inserted since the tag against 13,512 in `src/ddd`. The one check of the artefact is a zip listing for `index.html`. Nothing stops the release being cut before CI is green: the ruleset holds deletion and force-push only. *Change:* at the least, a fresh venv in Publish's `build` job that installs the wheel, compares `ddd --version` with the tag and answers `templates-dir`, `cmake-dir` and a served `index.html`: the smoke this pass did by hand. S.
- **M5. A release's documentation run can be cancelled by a later push.** `.github/workflows/docs.yml:34-39`. All deploying runs share one concurrency group with `cancel-in-progress` false, read as "queues behind the last one"; GitHub keeps one running and one pending in a group, and cancels the pending one when a third arrives. Merge the release, publish it, merge a fix within the first run's minutes (read-back alone can take five), and the release's run reads *cancelled*, nothing red, no `vX/` on the site. Read off the line and GitHub's documented behaviour; not reproduced, since it needs writes. Re-running heals it, so a sentence on the page is enough. S.
- **M6. The sdist lacks `SECURITY.md`, `.dockerignore` and `.gitattributes`.** `pyproject.toml:76-99`. It is "what an evaluator is sent", and carries `docker/` and the compose file: without `.dockerignore`, `docker/Dockerfile:94-96`'s "the build context has none of its own to mix in" is false there, the sdist holding pages. Without `SECURITY.md` the reader of the archive has no way to report privately. Read off the lines; the suite does not notice. Note also that 5.3 MB of its 7.2 MB are reference screenshots no python test reads and only the Linux image can use: harmless, and worth a thought with `docs/superpowers`' reasoning at `:100-103`. S.
- **M7. The page a released version gets on PyPI sends its reader to master's documentation.** `README.md:35-38` ("so that they describe the tree this README sits in"). The README is the index's description, where there is no tree: 0.11.0's page has 12 links into `sauci.github.io/ddd/latest/` and none into `v0.11.0` (`pypi.json`), so a user of 0.11.0 lands on pages for `ddd tool`, `--image` and tabs they have not got. Two in-page anchors, `#cmake-integration` and `#plugins`, are the KNOWN remainder of the plan of 2026-09-16. Rewriting `latest/` to the tag in the release commit is one more file to walk; a sentence saying which version the links follow is less. S.
- **M8. Three places disagree about what a release is.** All seven GitHub releases are flagged Pre-release with empty bodies (`gh release list`; `gh release view` with no tag answers "release not found", so `/releases/latest` is a 404); the site's menu calls v0.11.0 "(stable)" and redirects to it; PyPI serves it as final; the classifier says `4 - Beta` (`pyproject.toml:19`). Last review's open question, unanswered. Nothing automated reads the flag. Open question 2. S.
- **M9. What ships in the `.vsix` has audit findings, which pass 12 M10's "0 in what ships" did not reach.** `editors/vscode/package.json:78`, its lock file. `npm audit --omit=dev` there: 1 high, 2 moderate, `brace-expansion` 2.1.4 and `minimatch` 5.1.9 below `vscode-languageclient` 9.0.1 (now 11.0.0), all denial of service over a glob pattern (`gate.log`, `vsix-audit.json`). The patterns come from the extension and its own server, so the exposure is small. The python lists are clean at runtime and in development; `requirements-docs.txt` resolves to one `certifi` advisory (`last.log`). The audit step pass 12 asks for should name both lock files. S.
- **M10. The a2l keyword table stopped growing.** `docs/acronyms.rst:156-159`: "the keywords that appear in the files DDD generates ... can be read as a description of one file". The file now also says `SYSTEM_CONSTANT`, `MOD_PAR`, `ANNOTATION`, `NUMBER`, `FNC_VALUES`, `AXIS_PTS_X`, `NO_AXIS_PTS_X`, `NO_AXIS_PTS_Y`, `NO_INPUT_QUANTITY`, `DISPLAY_IDENTIFIER`, `FORMAT` and `BYTE_ORDER`, some of them shown on `faq.rst:479`, none on the page (`gate.log`). Pass 4 M15 is the other table. S.
- **M11. The developer page, three sentences.** `docs/developer_documentation.rst:488-490` counts "two jobs, and five more", and the section never describes `gui-screenshots`, the eighth; `:573-574` lists what `dev-build` waits for and omits it (`ci.yml:308`). `:406` "a couple of minutes in a warm checkout": 11 m 19 s in a fresh one here, and 4 to 10 minutes per CI cell. `:1036` "both MIT like every other bundled package": of the 40 listed, 8 are Apache-2.0, 8 ISC, 1 BSD-3-Clause and 1 0BSD (`licence_trace.log`). S.
- **M12. Small untrue sentences elsewhere.** `CHANGELOG.md:26` "every other command runs without importing it", against the same section's `--image` at `:37`. `requirements.txt:3` "`ddd tool from-elf` today". `.github/workflows/docs.yml:181-183` "the artifact this workflow currently uploads ... is what lets the Pages source move to it": it moved, and the file is now required. `.github/workflows/ci.yml:39-41` and `pyproject.toml:22` "os independent ... tested claims": no macOS cell, `README.md:68` says Windows and Linux, `CHANGELOG.md:64` "never on macOS". `docs/faq.rst:185-186` "the component's own pipeline ignores `missing-producer`" adds to pass 4 M4. S.
- **M13. What a release day still takes unpinned (P7-M7's remainder).** `publish.yml:40` `pip install --upgrade pip build twine`; `pyproject.toml:4` the build backend; `publish.yml:145,173`, `ci.yml:466` `pypa/gh-action-pypi-publish@release/v1`, a moving branch in the jobs holding the OIDC token; `editors/vscode/package.json:74` `npx --yes @vscode/vsce`, whatever is current; `requirements-docs.txt` lower bounds alone under a `-W` build; `docker/Dockerfile:20,32,63` floating tags its own header says to pin "before relying on the result for a release". Dependabot's list has no `docker` entry either. A Publish run on a bad day fails after the suite, or uploads through an action nobody reviewed. Pin the action by sha and the tools in a requirements file. S.
- **M14. `pypi` has no protection, as the page says (KNOWN: the page itself, the remainder of P7-I1 and P7-M4).** `docs/developer_documentation.rst:847-867`: "What stands between a pushed branch and pypi.org is the `pypi` environment's protection, and today there is none". `gh api .../environments`: unchanged, `deployment_branch_policy: null`, `protection_rules: []`, for `pypi`, `testpypi` and `testpypi-dev`; the leftover `github-pages` environment still stands. One collaborator today, so one stolen token. A settings click, before the release rather than after: a required reviewer stops a branch and a tag alike.
- **M15. The steps of a release are nowhere as steps.** `docs/developer_documentation.rst:761-867` is an account of the machinery and "Bumping the version means walking all ten"; nothing says in what order to merge, wait, tag, write the notes, verify, or what to do when a job fails. The steps are in last review's report and below. S: move the checklist here to that page.
- **M16. A wheel built from master says it is the release.** `pyproject.toml:11`, `src/ddd/__init__.py:20`. Between releases the version stays the last one's, so the wheel `ci.yml:237-257` uploads as `ddd-tool-<commit>`, and any local build, is `ddd_tool-0.11.0-py3-none-any.whl` holding 609 more commits: `ddd --version` and the banner of every generated file say 0.11.0, the module's handshake passes, and pip calls it satisfied. Only `dev-build` stamps its own. The report of a defect, or an archive of what generated a delivery, cannot tell them apart. Stamping the `gui` job's build as `dev-build` stamps its own would do for CI. S.

### Status of the 2026-09-15 findings in this area

Plainly fixed on this tree: P7-I1 (`publish.yml:159-161`), P7-I2 (`tools/site_versions.py:54,76`), P7-I3 (`has_issues: true`), P7-I4 (`faq.rst:620-667`), P7-I5 (`developer_documentation.rst:416`), P7-M1 (`README.md:975`, reproduced), P7-M3 (`tests/test_documentation.py:822`), P7-M6, P7-M9 (`conf.py:97-101`, `compile.sh:53-54`, `.dockerignore`, the `docs` service, `ci.yml:83-117`).

| id | finding | status | where |
| --- | --- | --- | --- |
| P7-M2 | developer page sentences | partly: extension and language server fixed; `gui-screenshots` and the suite's time are the same lapse again | M11; pass 2 I5 for the layers |
| P7-M4 | environment paragraph | text FIXED; the settings unchanged, `github-pages` leftover | M14 |
| P7-M5 | stale status lines | STILL OPEN | pass 4 M20 |
| P7-M7 | supply chain | partly: caps and one action version FIXED; Dependabot's file there and not running; the rest open | I1, M13 |
| P7-M8 | Node 20 | FIXED in every job; `@types/node ^20.11.0` left at `editors/vscode/package.json:81`, and a `sed` of the version would hit it | checklist |
| P7-M11 | README's relative links | FIXED for files; two anchors KNOWN | M7 |
| P7 open question | pre-release flag, development status | STILL OPEN | M8 |
| P7 test gaps | wheel names and banners unpinned; compile transcript | STILL OPEN by design, stated at `developer_documentation.rst:839-845`; the walk rehearsed clean | checklist |

### Open questions

1. **What does the next release wait for?** If for the whole Critical list, 0.11.0's holes stay out in the world for longer, and I would publish an advisory now (I4). If a release goes first, then at least pass 13 C2 (a file deleted) and pass 1 C4 (edits lost) should be fixed, since the preview label does not cover losing a file. The answer sets phase B below.
2. **What is a release?** Full GitHub release or Pre-release, `4 - Beta` or `5`, and is `preview` still the GUI's word? Today GitHub, the site and PyPI answer three ways (M8). One line each in the release commit.
3. **Should this review's reports sit on a public branch while their findings are open?** `review/complete-review-2026-11-03` is on the public repository and its 19 reports are readable through the api, pass 12's among them, while `SECURITY.md` asks a reporter to keep such things private. Keeping the kit local until the fixes land changes nothing else. The same is true of the earlier review branches, whose findings are fixed.
4. **Dependabot: on, or off and said so?** On gives I1's first batch to read, and a Playwright bump needs its image bumped by hand (`tests/test_documentation.py:2060` holds them together). Off means the three paragraphs go.
5. **`pypi`'s protection (M14).** Which, and when; I would add the required reviewer before the release.
6. **macOS (M12).** Claimed or not: the classifier and a comment say one thing, the README another. No cell is the cheap answer, and then `Operating System` lists two.

### Test gaps

- **No job installs the built wheel and runs it.** `tests/test_documentation.py:927,1897` read `pyproject.toml`'s `force-include`; `ci.yml:248,368`, `publish.yml:58` read one name out of the zip; the `container` job's `python -I` asks the same of the image, whose other services run the working tree. Every positive above was by hand (M4).
- **`gui/scripts/licenses.mjs` has no test.** I2 and M3 pass everything. Lock file against output is ten lines.
- **Nothing tests the floors of `requirements.txt`** (M1), and the published schema's text depends on the pydantic version (two failures at 2.10.0).
- **Two tests fail on a default Windows.** `tests/test_gui_api.py:2645,8514` create a 243-byte name; with `LongPathsEnabled` 0, this machine's value and Windows' default, they answer 500 `unwritable` under any temporary directory longer than about 16 characters (`sdist_suite.log`, `longest.log`). CI's Windows cells pass them, so its runners evidently have long paths on. So the brief's one known failure is three here, as the baseline's `gate.txt` already shows, and pass 4 I6's list of Windows stoppers has a third entry. The product's half belongs to pass 13: the plan is offered and Apply answers 500.
- **Nothing relates the two release workflows** (I3, M5), and `site_versions.py`'s tests pin orderings, not whether a directory's release exists.
- **Nothing checks a release's own record:** the empty bodies and flags of M8, or that the version on PyPI, the `.vsix` and `versions.json` agree after a release. The "verify from outside" of the checklist is by hand.

### Assessment

The packaging is the best-kept part of this repository, and everything that can be tested from outside passed: a person who runs `pip install` on this wheel gets a tool that does what its first page says, in a browser too, with no Node.js anywhere, and an evaluator handed the sdist can rebuild and re-verify all of it. The release machinery has learned from every release it broke, and its guards, unusually, are themselves under test. Its weakness is that those guards stop at the repository's edge. Dependabot is a file and not a process; the documentation run and the publishing run do not know about each other; the licence gate trusts a tree it reads wrongly; no job ever installs what is uploaded; and settings the pages rely on, or say are unset, are still unset. All of it is small, a day's work in total. The real distance to a release lies elsewhere: twelve Critical findings by earlier passes, a changelog that files features under a release that lacks them and omits a format change (pass 4 I7, I8), a SPEC with the wrong dictionary format (pass 5 I1) and 609 unreleased commits, while the version users actually install has security holes master describes in public. I would stop adding, fix what can lose a file or ship a wrong a2l, correct the changelog, and release.

### Release checklist

For the next release, which I number 0.12.0: a new check, a changed file format and a new runtime dependency make it a minor. Phase A and step 8 are the maintainer's alone.

**A. Decide**

1. What the release waits for (open question 1), and what it is called (open question 2). If a stop is more than days away, publish the advisory of I4 first.

**B. Land first, in this order, so that the release commit is a version bump only**

2. What can lose a file or an edit: pass 13 C2, C1; pass 1 C4; pass 16 C1, pass 15 C1, pass 3 C1.
3. What ships a wrong artefact or a wrong verdict: pass 11 C1; pass 1 C2, C3 with pass 7 C1; pass 9 C1. Pass 1 C1: at the least the warning on the five pages saying so.
4. The contract: `SPEC.md:2215` 8 to 9 (pass 5 I1), then whichever of pass 4 I9 was decided.
5. The changelog (pass 4 I7, I8): move the Compare, paste, plot and mismatch entries out of `## 0.11.0` to `## Unreleased`; add `empty-vocabulary` with its **Migration:** line, the Shared files and Files tabs; a *What to do* at the top, naming `pyelftools` for an air-gapped install; `CHANGELOG.md:26` (M12).
6. The pages a newcomer meets: the Windows step (pass 4 I4), the dependency lists (pass 4 M3), M2, and a decision on the GUI guide (pass 4 I1, KNOWN: part 20).
7. This pass: I2 (one line and a test), I3 (three lines in `docs.yml`), M1 (one character), M4's smoke, M5's sentence, M6's three includes, M11, M12; M13's action pin if wanted.
8. The settings, by hand: Dependabot on, and its first batch read (I1); `pypi` protected (M14); the `github-pages` environment removed.

**C. Rehearse on the candidate.** CI's pull request runs the suite, lint, the page's gates, the journeys and the documentation on both systems. What it does not do, and this pass did by hand:

9. `npm audit` in both `gui/` and `editors/vscode/` (pass 12 M10, M9), and a read of `npm outdated` if Dependabot's batch has not been.
10. `python -m build` and `twine check --strict`; a fresh venv outside the repository with the wheel alone: the tutorial, `ddd gui` with one Apply and one Undo, `ddd cmake-dir`, `ddd templates-dir`, `ddd tool from-elf`, `ddd lsp`. `SCRATCH/pass-20/tutorial.sh`, `walk_wheel.cjs`, `edit_wheel.cjs` and `run_examples.sh` do this, and M4 would put the core of it in Publish.

**D. The release commit, on `release/0.12.0`** (rehearsed: `bump.log`)

11. `src/ddd/__init__.py:20`; `pyproject.toml:11`; `cmake/Ddd.cmake:44`; `editors/vscode/package.json:5`; `editors/vscode/package-lock.json:3,9`. A test holds these five to each other.
12. `README.md:57` and `docs/getting_started.rst:29` (wheel name); `docs/getting_started.rst:39,62` (`ddd --version`; only the first is run); `docs/getting_started.rst:407,441,474`, `docs/generated_artefacts.rst:137,526,671,678`, `docs/faq.rst:590`, `docs/templates.rst:194` (banners). Nothing holds these. **Leave alone:** `editors/vscode/package.json:81` and lock `:15` (`@types/node ^20.11.0`, which a blind replacement of `0.11.0` corrupts), `gui/src/api/signIn.test.ts:7`, `tests/fixtures/addresses/symbols.json:2` and `generated/*` (read as naming what the committed files record, `developer_documentation.rst:388-390`), `tools/dev_version.py:54-55`, `tests/test_documentation.py:2767`.
13. `CHANGELOG.md:17` `## Unreleased` to `## 0.12.0`, no date, as the older headings. Reword anything saying "unreleased" inside it. `grep` the older tag's number once more.
14. If decided: `pyproject.toml:19`.
15. `python -m pytest`; `PYTHONPATH=src python -m ddd --version` answers `ddd 0.12.0`; `python -m build` names `ddd_tool-0.12.0`.

**E. Publish**

16. Optional dry run, on the release branch before merging: Actions, Publish, `target: testpypi`. It spends `0.12.0` on TestPyPI, which a second try then cannot reuse.
17. Pull request; merge; wait for **every** job of CI (`test` six cells, `lint`, `container`, `extension`, `gui` three legs, `gui-screenshots`, `dev-build`, `dev-publish`) and Documentation to be green on the merge commit. Nothing enforces this: the ruleset holds deletion and force-push only. And no further push until phase F is done (M5).
18. Create the GitHub release on the merge commit, tag exactly `v0.12.0`, its notes the changelog section (the last seven have none, M8), the pre-release flag as decided. That starts Publish (`test`, `build`, tag check, `twine`, then `publish-pypi` and `extension`) and Documentation (`site/v0.12.0`, `versions.json`, root redirect, read-back) side by side.

**F. Verify from outside**

19. `pip index versions ddd-tool` lists 0.12.0; a fresh venv's `pip install ddd-tool==0.12.0` answers `ddd 0.12.0`, and `ddd gui` serves; the release carries `ddd-0.12.0.vsix`; `https://sauci.github.io/ddd/versions.json` says `"stable": "v0.12.0"`, and `/v0.12.0/` answers 200; both runs green.

**G. If something goes wrong, and afterwards**

20. A tag check failure: delete the release and the tag and re-create it, **and remove `v<wrong>/` from `gh-pages` by hand and re-run Documentation**, or the site goes on calling it stable (I3). A job failing after the upload: re-run failed jobs; the `.vsix` clobbers and the docs directory is rewritten. A wrong artefact on PyPI cannot be redone: yank it, and the next is 0.12.1. A cancelled Documentation run: re-run it (M5).
21. Afterwards: `## Unreleased` again with the first change; the next run of `ci.yml` publishes `0.12.1.dev<run>` by itself; move this list to the developer page (M15); if the fixes are in, the review branches and the advisory can be dealt with (open question 3).

```candidates
20|I1|.github/dependabot.yml:3|Dependabot has never opened a pull request in seven weeks: 0 ever, alerts disabled; ruff, mypy, setup-node and 13 of 18 page packages are past what it would propose, against what proposes the moves
20|I2|gui/scripts/licenses.mjs:20|The licence list omits scheduler, bundled in every wheel with pages, and a GPL relabel of it passes the gate: a deduplicated entry met first stops the walk
20|I3|.github/workflows/docs.yml:27|The site publishes and crowns a release Publish refused or failed: stable v0.12.0, root redirect, and no way back on any page; Publish says nothing has been uploaded
20|I4|SECURITY.md:5|The release everyone installs has the holes master's changelog names, four weeks on with no advisory: token cookie to every port, token on a command line, no Sec-Fetch at v0.11.0
20|M1|requirements.txt:1|pydantic 2.8 and 2.9 satisfy the floor and end every command in a traceback beside a current typing_extensions; the real floor is 2.10
20|M2|README.md:73|Runs without being installed at all stops at --help: check is ModuleNotFoundError, a traceback, against every command works with either
20|M3|gui/scripts/licenses.mjs:34|npm run build fails under a path holding a uuid: npm redacts entry.path to ***, after Vite has emptied static/
20|M4|.github/workflows/publish.yml:21|Publish re-runs half of what ci.yml says: no npm test, lint or journey on a commit ci never saw, and it never installs what it uploads
20|M5|.github/workflows/docs.yml:37|A release's documentation run can be cancelled by a later push: one pending per concurrency group, nothing red, no directory on the site
20|M6|pyproject.toml:76|The sdist lacks SECURITY.md, .dockerignore and .gitattributes; Dockerfile's the build context has no pages is false there
20|M7|README.md:35|PyPI's page for a release sends its reader to latest 12 times and to its own version never; two anchors remain (KNOWN)
20|M8|pyproject.toml:19|GitHub says Pre-release with empty notes and no latest, the site says stable, PyPI final, the classifier Beta (still open from last review)
20|M9|editors/vscode/package.json:78|The .vsix ships brace-expansion and minimatch with 1 high and 2 moderate advisories, which 0 in what ships did not reach (adds to pass 12 M10)
20|M10|docs/acronyms.rst:156|The a2l keyword table stopped growing: SYSTEM_CONSTANT, MOD_PAR, ANNOTATION, NUMBER, FNC_VALUES, NO_AXIS_PTS_X and others are in the file and not on the page
20|M11|docs/developer_documentation.rst:488|Developer page: five more jobs omits gui-screenshots twice, a couple of minutes is 11, both MIT like every other bundled package is 22 of 40
20|M12|CHANGELOG.md:26|Small untrue sentences: every other command, from-elf today, the artifact docs.yml uploads, os independent as a tested claim, the component's pipeline ignores missing-producer
20|M13|.github/workflows/publish.yml:40|A release day still takes build, twine, hatchling, vsce, sphinx and the publish action unpinned, and the image tags its own header says to pin (P7-M7 remainder)
20|M14|docs/developer_documentation.rst:858|pypi has no protection, as the page says; settings unchanged, github-pages leftover (KNOWN)
20|M15|docs/developer_documentation.rst:761|The steps of a release are nowhere as steps: an account of the machinery, no order, nothing on a failed job
20|M16|pyproject.toml:11|A wheel built from master says it is the release: ddd_tool-0.11.0 with 609 more commits, the banner and handshake agreeing, in ci's own ddd-tool-<commit> artifact
```

## Pass 21: the test suite, core and formats

> **Read this first.** A survivor is first a survivor of the 22 in-scope test files (1,385 of the
> suite's 7,042 tests). 171 of the 664 survivors read as real were then asked of the rest of the suite
> (every other test file, less `test_cmake`, `test_bench_gui` and `test_editing_at_once`, and for a
> mutant the import reaches also less `test_gui_server`, `test_gui_api`, `test_generate_project` and
> `test_gui_hostile`): 48 died there, 123 survived. Each finding below says which of its survivors
> outlive the whole suite so asked; the details are under "Asked of the rest of the suite".

### Scope covered

Read in full, with line numbers: `tests/conftest.py` (355 lines) and the 22 files of the scope -
`test_models` (1057), `test_loading` (864), `test_analysis` (2400), `test_structures` (2190),
`test_constants` (1434), `test_rasters` (512), `test_point_counts` (535), `test_types` (497),
`test_units` (230), `test_sections` (515), `test_calibration` (566), `test_compare` (2152),
`test_comparison_tables` (572), `test_edge_cases` (523), `test_hardening` (1369), `test_embedded`
(458), `test_pointers` (38), `test_settle` (258), `test_backends` (734), `test_a2l` (574),
`test_generation` (626), `test_external` (654): 19,113 lines. The code was read around every survivor
cited (one line each for all 716 survivors, in context for the ones below), plus `compare.py:285-460`,
`src/ddd/backends/a2l/templates/project.a2l.jinja` and the five example templates in full.

What ran, all in `SCRATCH/pass-21/` on copies of the tree (`base/`, twelve workers `w/0..11`):

- **Baseline** of the copy, every test file in its own process with per-test line contexts
  (`baseline.py`, `cov/summary.txt`): 7,042 tests, the same three failures as the tree's own gate
  (two path-length tests of `test_gui_api`, the symlink test). 5,763 tests reach a line of `ddd`
  in-process; the rest only through a subprocess or not at all (`linemap.pkl`).
- **Population**: 7,078 mutation sites over 41 files of the core and the writers (`genmut.py`,
  `population.jsonl`), in eight strata (models; loading with diagnostics, names, pointers,
  file_names; analysis; ir with identity and value_identity; compare; c; a2l; backends/base) and 21
  operators (comparison, boolean, negated test, number, boolean constant, string token, message text,
  arithmetic, returned value, deleted statement / finding / raise / flow / validator, enum member,
  index, swapped function, dropped keyword argument, swapped arguments, table entry swapped or dropped).
  327 template mutants of the a2l template and the example c templates (`gentpl.py`).
- **Planned sample** of 4,375 (`sample.py`): every site of the logic operators, half of the returns and
  boolean constants, a quarter of the strings, a third of the dropped arguments, a sixth of the swaps,
  in round-robin order over (stratum, operator), so that any prefix of it is itself stratified.
- **Ran with a real outcome: 2,473 of the sample and 278 template mutants** against the scope
  (`runmut.py`, `results-scope.jsonl`, `results-tpl.jsonl`), each with `-x` against the in-scope tests
  that reach its line, and against all 1,385 when the import reaches the line. Follow-ups: the 12
  survivors on an import-reached line asked again of every in-scope test (6 then killed:
  `results-import.jsonl`); the 53 `str-token` survivors asked again with the token replaced whole, since
  a prefix passes a substring assertion (8 then killed: `results-token2.jsonl`). 24 null mutants, twice:
  no false kill either time (`results-null.jsonl`).
- **Effects**: nine survivors applied to a copy of the sources (`x/`) and the real `ddd generate all`
  run on a small project each, diffed against the pristine tool (`probe_effects.py`,
  `probes/effects.txt`).
- **Determinism**: an oracle over a corpus of 300 description trees from the examples and earlier
  passes' probes (`oracle.py`, `corpus/roots.txt`), asking the load, the analysis, the dump, both
  renders and 7,050 comparisons against doctored copies: 9,157 answers, identical under three hash
  seeds (`seeds.py`).
- **Static survey** of what the assertions look at (`survey.py`, `survey2.py`, `survey2.txt`).
- **Second stage** (2026-11-06, after two reboots, every worker first compared with `base/` byte for
  byte: no difference, so no rebuild and no new null run was needed): the 171 highest-ranked
  survivors asked of the rest of the suite (`results-rest.jsonl`), 213 asked of the corpus oracle
  (`results-oracle.jsonl`).

**Two crashes, and what was done about them.** The campaign was cut on 2026-11-04 at 10:09 when the
session ended. `results-scope.jsonl` then held 2,729 rows; from row 1,732 on, 940 were
`exit-3221225794` (0xC0000142, no process could start). The file is kept as
`results-scope.poisoned-2729.jsonl`. Removed and re-asked: the 940, the 8 kills and 1 survival after
row 1,732 (5 of those kills were `test_the_module_entry_point_runs_as_documented` failing because its
subprocess could not start), and all 10 timeouts. Kept from after row 1,732: 47 `no-scope-test` rows
and 1 `invalid`, which are decided before any process starts. On resuming, `base/` equalled the tree
byte for byte (`diff -rq`), but **every worker differed**: two still held a mutant of `analysis.py`
(the restore never ran), and ten **lacked 12 to 16 source files** each, their directories stamped
2026-11-05 01:25:15. All twelve were rebuilt from `base/`, the runner now scrubs every worker against
`base/` before and after a run, counts only real outcomes as done, stops when processes cannot start,
and checks each restore; the null mutants were rerun on the rebuilt workers with no false kill. The
session ended again after the first chain (07:28 on 2026-11-05); on 2026-11-06 all twelve workers
equalled `base/` byte for byte again. **What removed the files, I believe, was something outside the
run**: it happened fifteen hours after the last mutant ran, when no process of the campaign was alive;
it struck ten workers in the same second and took the whole `pyc/` cache too (gone again after the
reboots of 2026-11-05), which no test or mutant writes to; the files that went are the ones the
harness had rewritten, which points at a `%TEMP%` cleaner. `base/`, the results, `cov/` and the corpus
were untouched and the workers are verified before every run, so the evidence stands - but the scratch
folder lives under `%TEMP%`, and anything cited from it should be copied out first.

**Not covered**: 1,902 of the planned sample (the 25 minute budget cut the round robin there; what is
left is mostly `negate` and `cmp` of `analysis.py`, `loading.py` and `models`, and the numbers of
`models`), 49 template mutants (all `tpl-del-line` of the a2l template's tail), 36 planned mutants
(`extra.jsonl`: the extractors of the comparison tables, seven semantic edits), a sweep of every
check's severity, and a kill matrix without `-x`. `cli.py`, `plugins.py`, `addresses.py`, `elf.py`, the
toolbox, `gui/` and `lsp/` were not mutated (pass 22). Of the 664 survivors read as real, the 493
below the first 171 in priority (most of the "other" class, the template survivors, the dropped
sorts and the 170 unreached mutants) were not asked of the rest of the suite, and the broadcast and
other index survivors were left out of that step by the class filter.

### Strengths

- **A deleted rule is almost always noticed.** Of the Python mutants that ran: deleted findings 60 of
  67 killed (the 7 others are reached by no in-scope test), deleted raises 44 of 50, deleted
  validators 29 of 29, returns 147 of 165, negated tests 176 of 208, comparisons 170 of 200, swapped
  arguments 87 of 100. The weakness is in what the tests *read*, not in whether they run the rule.
- **Where a finding is drawn is now pinned**: `DRAWN_AT` (`tests/test_analysis.py:2150-2400`) holds the
  anchor of 27 checks, and an AST walk (`:942-965`) holds every identifier the code files to the
  registry - the previous review's two largest location gaps.
- **The comparison-table guard works**: after the import-reached follow-up, every table entry dropped
  from `compare.py` (`:314`, `:319`, `:348`, `:412`, twice) and the a2l entries of `analysis.py:285`
  were killed by `tests/test_comparison_tables.py:245-306` and `:470-480`.
- **The strong tests**, by how often each was the first to fail: `test_generation.py::test_scalar_definition`
  (52), `test_loading.py::test_project_with_components` (32), the manifest's
  `test_a_header_of_a_component_that_is_gone_is_removed` (28),
  `test_analysis.py::test_consistent_project_has_no_findings` (27),
  `test_signed_negative_and_float_literals` (26); by file, `test_analysis` (208 first kills),
  `test_generation` (204), `test_compare` (189), `test_a2l` (148), `test_loading` (113). Exact whole-line
  pins kill: `test_generation.py:87,93`, `test_point_counts.py:381,469-489`, `test_compare.py:892-904`.
- **The code is deterministic** although no test says so: 9,157 answers over 300 trees were identical
  under `PYTHONHASHSEED` unset, 1 and 2.
- Order independence and hygiene hold: no false kill from 48 null mutants under full load; the
  previous review's assertion-free tests and dead `or` alternative are gone.

### Issues

#### Critical

None. No survivor is a defect of today's code; each is a wrong program the suite would let through.

#### Important

- **I1. The writers' datatype tables are pinned for a minority of the eleven datatypes.** Survivors in
  the scope: `backends/c/types.py:23` `uint32` spelled `int32_t`, `:24` `sint32` spelled `uint64_t`,
  `:38` `uint32` literal without `U`; `backends/a2l/types.py:13` `boolean` as `SBYTE`, `:19` `SLONG`,
  `:20` `A_UINT64`, `:21` `sint64` as `FLOAT32_IEEE`, `:23` `float64` as `UBYTE`;
  `src/ddd/models/common.py:331,336,340` the `DatatypeInfo` of `boolean` (maximum 255), `uint32`
  (signed, float) and `float32`. Reproduced (`probes/effects.txt`): `uint64_t S = -5;`, `int32_t U = 5U;`
  and `UBYTE NO_COMPU_METHOD 0 0 -1.79769313486e+308 ...` with exit 0. `tests/test_backends.py:107-109`
  checks only that each table has every key. **Asked of the rest of the suite**: all five a2l type
  swaps, the `U` suffix, and the `boolean` and `float32` entries of `DatatypeInfo` survive it; the
  `uint32` and `sint32` c spellings and the `uint32` flags die only in
  `tests/test_address_fixtures.py::test_the_committed_c_is_what_ddd_generates_for_t...`, a fixture's
  committed c rather than a test of the rule. This confirms pass 8's a2l list for the whole suite and
  adds the `U` suffix and `DatatypeInfo`. Fix: one test parametrised over the eleven datatypes reading
  the c declaration and literal, the a2l datatype, record layout and limits (S).
- **I2. The a2l is asserted by substring and by `count("/begin") == count("/end")`, so a mangled
  keyword, a mis-named `/end`, an extra number and a dropped escape pass.** Of 214 template mutants of
  `src/ddd/backends/a2l/templates/project.a2l.jinja`, 84 survive: every `/end` renamed (13: `/end
  MEASUREMENT`, `/end CHARACTERISTIC`, ... `:93`, `:137`, `:157`, `:160`), all of `MOD_COMMON` (`:13-20`,
  19 mutants), `HEADER`, `PROJECT_NO`, `VERSION` (`:6-9`), 11 of the 12 `| a2l` escapes (`:4`, `:40`,
  `:48`, `:100`, `:116`, `:141`, ...), and `FORMAT`/`DISPLAY_IDENTIFIER` of axes and characteristics.
  `MATRIX_DIM 4 1 1 1` (reproduced) passes `"MATRIX_DIM 4 1 1" in content` (`tests/test_a2l.py:68`, and
  `tests/test_hardening.py:64`, `tests/test_calibration.py:498`), `XXSYMBOL_LINK "X" 0` passes
  `'SYMBOL_LINK "X" 0' in content` (`tests/test_a2l.py:54`). Only `tests/test_hardening.py:849-862` pins
  an escape, on one record. Fix: assert records whole through a small a2l reader (pass 8's `a2lread.py`
  is one), or at the least anchor each expected line to its start and end (M).
- **I3. Nothing checks that the a2l's names are unique and its references defined.** Deleting
  `self._names.add(candidate)` (`backends/a2l/model.py:686`) gives two `COMPU_METHOD CM_IDENT_V`
  (reproduced) and passes `tests/test_a2l.py:302-313`, a test named for the very case; stopping the
  closure after one hop (`:353`) leaves `AXIS_PTS Ax` indexed by `M` with no `MEASUREMENT M`
  (reproduced), because `tests/test_hardening.py:83-98` and `tests/test_calibration.py:538-545` pull
  one hop only. A calibration tool refuses either file. Both survive the rest of the suite, as do
  `backends/a2l/model.py:511` (a parameter's members filed under `REF_MEASUREMENT`, pass 8) and the
  four-number `MATRIX_DIM` of I2 (`:51`, `:537`). Fix: an invariant over every rendered a2l of the
  suite - each record name defined once, each reference to a defined record (S).
- **I4. A check's severity is pinned for few checks, so an error can become a warning in silence.**
  20 severity survivors in the scope, `ERROR` to `WARNING` among them for `removed-object`
  (`src/ddd/diagnostics.py:229`), `missing-producer` (`:173`), `include-depth` (`:104`),
  `duplicate-section` (`:118`), `unknown-constant` (`:137`), `raster-kind` (`:150`), `name-collision`
  (`:159`), `consumer-identity` (`:167`), `enum-conflict` (`:180`), `plugin-invalid` (`:109`).
  `tests/test_compare.py:182-195`, `test_a_removed_object_with_consumers_is_an_error`, asserts the
  identifier and a phrase, not that it is an error; `tests/test_analysis.py:77-81` counts
  `missing-producer`. The grade decides the exit code and "cannot replace". **Asked of the rest of the
  suite**, 10 of the 20 die there (in `test_transcripts`, `test_cli`, `test_gui_compare`,
  `test_gui_session`, `test_file_plans`); **10 survive the whole suite**: `duplicate-event`
  (`src/ddd/diagnostics.py:126`), `raster-kind` (`:150`), `type-cycle` (`:154`), `consumer-storage`
  (`:163`), `consumer-identity` (`:167`) and `enum-conflict` (`:180`) as warnings, and
  `section-alignment` (`:200`), `a2l-unrepresentable` (`:206`), `changed-owner` (`:249`),
  `changed-condition` (`:252`) as infos. A cyclic structure as a warning lets `generate` go on. Fix:
  one parametrised test over the triggers `DRAWN_AT` already has, asserting the severity of each (S).
- **I5. Seven tests pass with the rule they name deleted.**
  `tests/test_structures.py:1621-1628` (the stdint include "counts the members": the example template
  includes `<stdint.h>` unconditionally, `examples/templates/ddd_types.h.jinja2:10`, so `ir.py:785` and
  `backends/c/types.py:48` survive and nothing reads `needs_stdint`); `tests/test_generation.py:169-181`
  (its docstring claims `model.needs_stdint` answers; nothing asserts it);
  `tests/test_hardening.py:766-779` (a line break in a condition: the payload also holds `#`, so deleting
  the line-break refusal, `models/component.py:77`, passes, and `/*` likewise, `:78`, because the payload
  also holds `*/`); `tests/test_analysis.py:102-123` ("the local declaration owns": the local is `A`,
  first by name too, so `analysis.py:2876` preferring nothing survives); `tests/test_sections.py:435-485`
  (`Pack` and `Tiny` tie, so the structure's alignment, `backends/c/model.py:351,353`, is not read);
  `tests/test_external.py:481-487` ("byte deterministic": one in-memory dictionary rendered twice in one
  process; 31 survivors drop a `sorted`); `tests/test_compare.py:182` (I4). Fix: one input each that
  only the named rule refuses (S). Asked of the rest of the suite, the survivors behind the first
  five (`ir.py:785`, `backends/c/types.py:48`, `models/component.py:77`, `:78`, `analysis.py:2876`,
  `backends/c/model.py:351`, `:353`) all survive it.
- **I6. The fixtures make the cases that tell two implementations apart rare.** Arrays are square
  (`[2, 2]` in `tests/test_models.py:225`, `tests/test_analysis.py:484`, ...): `range(shape[0])` read as
  `range(shape[-1])` in `models/objects.py:943` fills `uint8_t T[2][3] = 7` with three rows
  (reproduced), and 33 first-or-last index survivors pass. Files are included in name order
  (`a.ddd.json`, `b.ddd.json`), so load order and name order coincide in nearly every test: 31 `sorted`
  survivors. `declare` defaults to a non-volatile `uint8` measurement (`tests/conftest.py:47-70`):
  `uint32` and `sint32` are almost never written. Fix: non-square shapes, a reversed include order and a
  datatype matrix in the shared builders (S).
- **I7. Boundaries go untested: 65 boundary and threshold survivors, several of which refuse a valid
  project or accept an invalid one.** Reproduced: narrowing the c `int` bound to 61
  (`analysis.py:152`) refuses an enumerator of 100 on `uint16`, exit 1, and no in-scope test notices.
  Also in the scope: a constant of value 1 as a dimension (`analysis.py:112`), a boolean init of 0
  (`:2588`), the alignment estimate's floor (`:1310`), the lowest enumerator (`models/conversion.py:48`,
  `-(2*63)` passes), an enum with no enumerator (`:188`, `min_length` dropped), the 128 character
  identifier (`models/common.py:57`, `max_length` dropped), a reserved `_X` of two characters
  (`models/reserved.py:77`), addresses 0 and `0xFFFFFFFF` (`backends/a2l/options.py:59`). **Asked of the
  rest of the suite** (65 of them): 26 die, among them the address bounds (`tests/test_addresses.py`),
  while the 128 character cap and the enumerator bounds (`models/conversion.py:48,49,188`) die only in
  `tests/test_documentation.py`'s comparison with the committed schemas, which pins a published text
  rather than the refusal; 39 survive, among them `analysis.py:112`, four of the five edits of
  `analysis.py:152`, `:1310`, `:2588` and the literal bounds of `backends/c/literals.py:62,64`. Fix:
  one edge test per bound, both sides of it (S).

#### Minor

- **M1. The reserved-word table is pinned entry by entry for six words.** Dropping `while`, `short`,
  `signed`, `void`, `long`, `goto`, `inline`, `restrict`, `typeof`, `nullptr`, `_Atomic`,
  `_Static_assert` or `_Thread_local` from `src/ddd/models/reserved.py:29-35` survives (22 mutants;
  the 18 asked of the rest of the suite all survive it too); `tests/test_models.py:75-77` names six. A variable called `short` would check clean and not compile.
  Fix: parametrise over the C23 keyword list (S).
- **M2. The example c templates' conditions and comments are pinned in one place.** 30 of 64 example
  template mutants survive: negating or deleting the `#if`/`#endif` of calibration data
  (`examples/templates/ddd_globals.c.jinja2:40-48`), of `ddd_globals.h` (`:19-26`) and of outputs and
  locals in `{component}.h.jinja2:21-28,53-60`; the guard and include of `ddd_globals.h` (`:3-6`); the
  typedef of an empty project (`ddd_globals.c.jinja2:52-60`). An `#if` without its `#endif` compiles in
  no test of the scope, which compiles nothing (`ddd templates-dir` hands these templates out). Fix:
  compile one rich project's output under the CI flags where `gcc` is present (S).
- **M3. Older dictionary formats read with defaults no reading test pins.** `ir.py:224` (`volatile`
  defaulting to `True`), `:454`, `:474`, `:590` (`local`), `:106` and `:137` (`source`, `description`)
  survive the scope: a dump of an older format lacking the key would read otherwise and compare
  differently. Of these only `:224` was asked of the rest of the suite, and it dies in
  `tests/test_documentation.py`'s committed-schema comparison, not in a test that reads an old dump.
  Adds to pass 5's test gap on older dictionaries (S).
- **M4. Where descriptions and comments go is not asserted.** `backends/c/model.py:499,507,561`
  (structure, member and enum comments dropped), `backends/c/literals.py:193-199` (axis and map
  comments), `backends/a2l/model.py:316,473` (project and characteristic description), six template
  comment lines survive. Pass 6 said as much; it still holds (S).
- **M5. Absence is rarely asserted.** `backends/c/model.py:199` makes every header say "This component
  declares no global variable", `backends/c/backend.py:66` renders every file of the template directory,
  `backends/base.py:478` doubles the final newline, `backends/base.py:432,436` drops `lstrip_blocks`
  (documented at `docs/templates.rst:68`): all survive the scope; asked of the rest of the suite, the
  doubled newline dies in `tests/test_address_fixtures.py` and the other three survive it (S).
- **M6. Message texts and a few places are unpinned.** 29 message survivors (`compare.py:292`, `:607`,
  `:655`, `:935`, ...), and the place of five findings survives a whole replacement
  (`analysis.py:1830`, `:2317`, `:2507`, `:3513`, `:3586`) (S).
- **M7. Two performance tests still bound nothing, and 14 mutants hang the suite instead of failing
  it.** `tests/test_structures.py:589-614` and `tests/test_sections.py:355-381` (previous review M10,
  open). Under this harness 14 mutants ran past 300 s (`analysis.py:541-677`, `:1530-1541`, `:2955-2970`,
  `backends/a2l/model.py:682`): a ci job would hang (S).
- **M8. A core test still imports from the language server's tests**: `tests/test_constants.py:1296,1341`
  (`from test_lsp import ...`), although `tests/conftest.py:255-295` now holds the helpers (previous
  review M6, open) (S).
- **M9. A collection-only run still reports a coverage failure and exits 0**: `pytest --co` prints
  `FAIL Required test coverage of 100% not reached. Total coverage: 15.80%` (reproduced on the copy),
  because `pyproject.toml:118` keeps `--cov-fail-under=100` in `addopts` (previous review M9, half fixed:
  the pragma is gone) (S).

### Status of the 2026-09-15 findings in this area

Pass 11a's thirteen; only those not plainly fixed:

| id | finding | status | where |
| --- | --- | --- | --- |
| P11A-M6 | a core test imports helpers from the LSP test module | STILL OPEN | `tests/test_constants.py:1296,1341` (M8) |
| P11A-M8 | order pins depending on the schedule | FIXED in substance; one left | `tests/test_analysis.py:1944` |
| P11A-M9 | redundant pragma; `--co` reports a coverage failure | half: pragma gone, `--co` still FAIL | `pyproject.toml:118` (M9) |
| P11A-M10 | two performance tests bound nothing | STILL OPEN | `tests/test_structures.py:589`, `tests/test_sections.py:355` (M7) |
| P11A-M11 | `DERIVED_AS` claimed, one entry executed | FIXED for the analysis tables; the delivery tables execute `shape` only | `tests/test_comparison_tables.py:308-363` |

Fixed: I1 (`tests/test_hardening.py:576-598`), I2 (`tests/test_comparison_tables.py:259-282`), M1
(`tests/test_sections.py:182-190`), M2 (`tests/test_edge_cases.py:497-514`), M3
(`tests/test_models.py:966`, `tests/test_edge_cases.py:481-495`, `tests/test_sections.py:507`), M4
(`tests/test_analysis.py:942-965`), M5, M7 (`tests/conftest.py:81-117`). Of pass 11a's 53 consolidated
gaps, still open by grep and by survivor: the 128/129 identifier, `dimensions: []`, `raw_reading`, the
include-cycle chain, three producers, a byte order mark on an included file, a `..` include, a
directory named by an include, the `added-object` and `project-mismatch` texts.

### Open questions

1. Are the example templates held to the tool's standard? `ddd templates-dir` hands them out. If yes,
   M2's survivors are gaps and the suite should compile their output; if not, the pages should say they
   are illustrations.
2. Is a valid a2l (unique names, defined references, matching `/end`) an invariant DDD tests, or left to
   the calibration tool? I2 and I3 depend on it; a reader in the suite is about a day.
3. Is each check's default severity part of the contract the suite pins (I4), or does the
   documentation's table stand for it?
4. A wall-clock bound on the walks of M7, or a durations check in ci (the previous review's question 3,
   unanswered)?

### Test gaps

**Mutation, against the 22 in-scope files.** Python mutants with a real outcome: 2,473 of the 4,375
planned (7,078 sites): 1,731 killed, 14 hung past 300 s, 492 survived, 65 survived as a dataclass flag,
170 reached by no in-scope test, 1 invalid. Score, killed or hung over what is not a flag:
**72.5 %**; over what an in-scope test reaches, **78.0 %**. Templates: 278 of 327 ran, 164 killed, 114
survived (a2l template 130/214, example c templates 34/64).

| stratum | ran | killed | hung | survived | flag | unreached | score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| a2l | 296 | 215 | 2 | 61 | 18 | 0 | 77.3 % |
| analysis | 437 | 334 | 12 | 82 | 9 | 0 | 78.0 % |
| backends/base | 168 | 113 | 0 | 38 | 7 | 10 | 70.2 % |
| c | 304 | 235 | 0 | 43 | 19 | 7 | 82.5 % |
| compare | 261 | 217 | 0 | 41 | 3 | 0 | 84.1 % |
| ir, identity, value_identity | 152 | 75 | 0 | 28 | 1 | 48 | 49.7 % |
| loading, diagnostics, names, pointers, file_names | 418 | 242 | 0 | 110 | 8 | 58 | 59.0 % |
| models | 437 | 300 | 0 | 89 | 0 | 47 | 68.8 % |

By operator, killed share: deleted validator 100 %, deleted finding 90 %, return 89 %, deleted raise
88 %, swapped arguments 87 %, negated test 85 %, comparison 85 %, deleted statement 79 %, enum member
79 %, arithmetic 76 %, boolean 75 %, dropped argument 74 %, table entry 67 %, message 64 %, token 59 %,
number 50 %, swapped function 50 %, boolean constant 37 %, index 27 %. Lowest files: `identity.py` 2/57
and `models/schema.py` 1/48 (reached by other files' tests only), `diagnostics.py` 46/128, `names.py`
1/10, `models/reserved.py` 13/31, `file_names.py` 0/19.

**The 716 survivors read, by class**: 82 dataclass or config flags and 19 `__all__` entries (no
behaviour a run shows); 33 first-or-last index on one-dimensional shapes and 9 `zip(strict=)`, mostly
equivalent; 31 `sorted` dropped (order, I6); 65 boundaries and thresholds (I7); 26 datatype table
entries (I1); 22 reserved words (M1); 20 severities (I4); 29 message texts (M6); 114 template mutants
(I2, M2: 27 keyword prefixes a substring assertion accepts, 19 `MOD_COMMON`, 16 condition guards, 13
`/end` names, 11 escapes, 6 comments, 22 other); 266 others, read one by one, among them the closure,
the names, the broadcast and the condition rules above. The classes of wrong code the scope lets
through: **a wrong entry of a per-datatype table; a keyword, number or escape inside an a2l line; a
duplicate or dangling a2l name; a changed severity; a rule shadowed by another rule the same fixture
trips; an index or order confusion on a square or name-ordered fixture; an edge of a bound; text,
comments and absences.**

**Effects reproduced** (`probes/effects.txt`), each exit 0 unless said: closure after one hop; two
methods of one name; `MATRIX_DIM 4 1 1 1`; three rows for `T[2][3]`; `int32_t U`; `uint64_t S = -5`;
`U = 5` without its suffix; `float64` as `UBYTE`; an enumerator of 100 refused, exit 1.

**Harness caveats** (so the numbers are read right): a survivor whose line the import runs was first
asked only of the tests reaching that line, which misses a test reading a table the line defines; the
12 such survivors were re-asked of every in-scope test and 6 died. A prefix on a token passes a
substring assertion; the 53 token survivors were re-asked with the whole token replaced and 8 died.
Timeouts are counted as kills here, but would be hangs in ci.

**Not run** (see Scope covered): 1,902 of the sample, 49 template mutants, the 36 planned and extractor
mutants, the severity sweep and the kill matrix.

**Asked of the rest of the suite** (`results-rest.jsonl`, 2026-11-06, 20 minute budget): the 664
survivors read as real were ranked - first the 78 the findings rest on, then 70 boundaries and reserved
words, 201 others, 114 template survivors, 31 dropped sorts, 170 unreached - and the first 171 were
asked of every test outside the scope that reaches the line, or of every such test for a line the
import reaches (less the files named in the note at the top). 48 died, 123 survived (21 of them reached by no test outside the scope at all):

| class | asked | died elsewhere | survived the suite |
| --- | --- | --- | --- |
| datatype table | 22 | 5 (`test_address_fixtures` 3, `test_cli` 1, ...) | 17 |
| check severity | 20 | 10 | 10 |
| boundary or threshold | 65 | 26 (`test_documentation` 12 through the committed schemas, `test_addresses` 4, `test_cli` ...) | 39 |
| reserved word | 18 | 0 | 18 |
| other (the closure, the names, the conditions, the rules of I5) | 46 | 7 | 39 |

The first killers outside the scope were `test_cli` (14), `test_documentation` (12, mostly the
committed-schema comparison), `test_address_fixtures` (7, the committed c), `test_addresses`,
`test_transcripts`, `test_gui_*` and `test_file_plans`: the periphery guards a handful of the core's
rules through published texts and committed outputs, not through tests of the rules. The 493 survivors
below rank 171 were not asked; the template survivors, which only a compiler or an a2l reader would
catch, are among them, so M2 and I2's template part stand on the scope alone.

**The corpus oracle on the same survivors** (`results-oracle.jsonl`, `oracle2.py`, 10 minute budget, 213
asked): each survivor applied, then the load, analysis, dump, both renders and the doctored
comparisons of the 300 trees compared with the pristine tool's, less a noise floor measured on an
unmutated worker (one tree, `p1/repro/t/bb/DemoDevice.ddd.json`, answers by the working directory: 4
to 55 answers). Of the 128 whole-suite survivors asked, **38 change what DDD says or writes about at
least one of the 300 realistic trees** - the a2l type swaps, the four-number `MATRIX_DIM`, the group
filing, the duplicate method names, the closure, the `U` suffix, every header declaring nothing,
`ir.py:785`, `DatatypeInfo` of `boolean`, two thresholds of `compare.py` - and 90 do not: they need an
edge input the corpus lacks (the bounds of I7, the severities of checks the corpus never fires, the
rules of I5) or are equivalent (`backends/c/types.py:33`, a boolean suffix nothing reads;
`backends/a2l/model.py:464,482,574`). One oracle run timed out.

**Skipped**, with the reason: the severity sweep over the 66 severities not yet asked and the kill
matrix without `-x` (neither can change a verdict above, and the sessions kept ending), the 36
planned and extractor mutants of `extra.jsonl`, and the rest of the suite for the 493 lower-ranked
survivors.

### Assessment

The core suite is large, careful and honest about what it runs: a deleted finding, validator or raise
is caught nine times in ten, where a finding is drawn is now pinned, and the comparison guard does its
job. What it does not do is read the outputs closely. About one mutant in four that the scope reaches
survives it, and the survivors are not noise: a `uint32` declared `int32_t`, a `float64` written `UBYTE`,
two compu methods of one name, an axis indexed by a measurement the file does not hold, `MATRIX_DIM` with
four numbers, a type cycle downgraded to a warning - each passes all 1,385 tests of the scope with
the coverage gate green, and each was then asked of the rest of the suite and passes that too. The cause is structural and cheap to fix: assertions match fragments of the a2l
rather than its records, fixtures are square, name-ordered and `uint8`, a check's severity is asserted
for a handful of checks, and nothing compiles or parses what the writers emit. Seven tests pass with the
rule they name deleted. 100 % coverage here means every line ran; about 72 % of the mutations that ran
were noticed by the tests that own the code.

```candidates
21|I1|src/ddd/backends/a2l/types.py:23|Writers' datatype tables pinned for few datatypes: float64 as UBYTE, sint64 as FLOAT32_IEEE, no U suffix pass the whole suite
21|I2|tests/test_a2l.py:68|A2L asserted by substring and begin/end counts: renamed /end, MOD_COMMON, 11 of 12 escapes, MATRIX_DIM with four numbers pass
21|I3|src/ddd/backends/a2l/model.py:686|No test checks a2l names unique or references defined: two CM_IDENT_V and a dangling axis input pass the whole suite
21|I4|src/ddd/diagnostics.py:154|Severities pinned for few checks: type-cycle, enum-conflict, consumer-storage and seven more downgraded pass the whole suite
21|I5|tests/test_structures.py:1621|Seven tests pass with the rule they name deleted: stdint, line break in a condition, local owner, alignment tie, determinism
21|I6|tests/conftest.py:47|Square, name-ordered, uint8 fixtures hide index and order confusions: broadcast fills T[2][3] with three rows unseen
21|I7|src/ddd/analysis.py:152|Boundaries untested: 65 survivors, c int bound 61 refuses an enumerator of 100, address 0, 128-char names, -126
21|M1|src/ddd/models/reserved.py:29|Reserved-word table pinned for six words: dropping while, short, signed, void, _Atomic and others passes the whole suite
21|M2|examples/templates/ddd_globals.c.jinja2:40|Example templates' #if/#endif and guards unpinned: 30 of 64 template mutants survive, nothing compiles output
21|M3|src/ddd/ir.py:224|Older-format defaults unpinned: volatile and local defaulting to true pass, an old dump reads otherwise
21|M4|src/ddd/backends/c/model.py:499|Where descriptions and comments go is not asserted: struct, member, enum, axis comments and a2l descriptions drop unseen
21|M5|src/ddd/backends/c/model.py:199|Absence rarely asserted: every header saying it declares nothing, extra rendered files, a doubled newline pass
21|M6|src/ddd/compare.py:292|29 message texts and five finding places survive whole replacement
21|M7|tests/test_structures.py:589|Two performance tests bound nothing; 14 mutants hang the suite past 300 s instead of failing it (P11A-M10 open)
21|M8|tests/test_constants.py:1296|Core test still imports helpers from test_lsp though conftest holds them (P11A-M6 open)
21|M9|pyproject.toml:118|pytest --co prints a coverage FAIL and exits 0 (P11A-M9 half open)
```

## Pass 22: the test suite, periphery and GUI server

> **Read this first.** The suite is strong where a guard exists and blind where none does. Every
> guard earlier passes leaned on fires a test when it is removed (81 of 88 guard mutants killed),
> and the stratified campaign kills 83.9 % of 2,520 mutants (the core's, pass 21: 72.5 %). But not
> one of the ten failures passes 10, 13 and 19 found by hand has a test that fails on it, and each
> such test is 10 to 30 lines with the suite's own helpers (I1, probes ready in
> `SCRATCH/pass-22/probe-tree/tests/test_p22_probes.py`). Everything cited lives in
> `SCRATCH/pass-22/`; `notes.md` there is the working log, including one harness defect of mine and
> its repair.

### Scope covered

**Read in full, with line numbers**: `tests/conftest.py` (355), `tests/test_gui_hostile.py` (438),
`tests/test_gui_docs.py` (45). **Read in part**: `tests/test_editing.py:555-835`,
`tests/test_editing_at_once.py:1-140`, `tests/test_gui_session.py:1-460, 596-647`,
`tests/test_gui_server.py:296-535, 1031-1080, 2037-2060`, `tests/test_lsp.py:1-102, 196-235,
4293-4422, 4840-4969`, `tests/test_lsp_decisions.py:1-60`, `tests/test_cli.py:3000-3056`,
`tests/test_gui_api.py:1-40, 488-500, 2636-2652, 3192-3301, 6767-6886`,
`tests/test_type_plans.py:55-100`, `tests/test_variables.py:263-430`,
`tests/test_toolbox_from_elf.py:86-108`, `tests/test_documentation.py:3327-3346`,
`tests/test_transcripts.py:530-545`, `tests/test_plugins.py:2233-2242`; every class and test name of
`test_gui_server`, `test_lsp`'s `TestServer`, `test_gui_api`, `test_cli`, `test_plugins`,
`test_documentation`, `test_cmake`, `test_gui_depth`, `test_gui_derived`, `test_gui_contract`,
`test_elf`, `test_toolbox_from_elf`, `test_addresses`. Code read where a probe or a survivor needed
it: `src/ddd/editing.py:760-981`, `src/ddd/gui/server.py:160-935`, `src/ddd/gui/queries.py:60-274`,
`src/ddd/gui/session.py:440-589, 800-930`, `src/ddd/lsp/server.py:425-445, 540-560, 715-790`,
`src/ddd/cli.py:115-160, 322-331, 872-890, 1180-1228, 1471-1485`, the line of each of the 405
survivors and the context of about sixty of them.

**Not read**: the other 54,000 or so of the 57,194 lines of the 38 files (5,487 tests). They were
measured instead, by the guard mutants, the probes and the campaign, which asks every in-scope test
that reaches a mutated line. `tests/test_gui_api.py` (10,266 lines, 860 tests) was sampled by
mutating what it tests (`gui/api.py`, `contract.py`, `queries.py`: 308 mutants) and read at five
places only.

**Ran** (all on copies under `SCRATCH/pass-22/`; the suite ran twice in `base/`, and `diff -rq` of the
tree against `base/` afterwards shows no difference, so it writes nothing into its tree):

- The whole suite as a contributor runs it, one process: with the default options (coverage and its
  gate) 674 s wall (`timing/serial.txt`); with `--no-cov` 562 s, per file (`timing/nocov.xml`,
  `timing/per-file.txt`). Both runs had at most two mutation workers beside them.
- 36 null mutants under load: all survived, no false kill (`results-null.jsonl`).
- 88 hand-written guard mutants, one per guard earlier passes leaned on (`mkplanned.py`,
  `results-planned.jsonl`).
- Ten probe tests, one per hand-found defect (`probe-tree/tests/test_p22_probes.py`,
  `probes-run1.txt`); three of them again against crude fixes in a copy (`probe-fix/`).
- **The campaign**: pass 21's generator copied and pointed at 49 files in nine strata (cli with
  build_info and difflib_lock; plugins; lsp; gui-server: server, routes, depth; gui-session: session,
  compare, derived; gui-api: api, contract, queries; editing: editing, the five plan modules,
  object_values, identity; project: project_*, variables, variable_keys, finding_*,
  findings_by_file, graph, deliveries; elf: elf, addresses, toolbox/*): 13,211 sites, pass 21's
  rates and round-robin order (`sample.jsonl`, 7,880 planned, so any prefix is stratified). Each
  mutant asked with `-x` of the in-scope tests reaching its line in pass 21's line map
  (`linemap.pkl`; valid, `base/src` equals pass 21's and the tree's); a line only the import runs is
  asked of every test reaching its file. Twelve workers, stopped at 2,520 mutants with a real outcome
  (`runmut22.py`, `results-scope.jsonl`). Follow-ups: 47 module-level survivors and 12 unreached ones asked of every
  in-scope file naming the module, or a module naming it, whole (`results-importers.jsonl`); 28
  survivors of `cli.py`, `plugins.py` and `build_info.py` asked of `test_transcripts`, whose runs
  reach the tool through a subprocess the line map cannot see (`results-transcripts.jsonl`); 112
  asked of the tests outside the scope that reach their line (`results-rest.jsonl`).
- Effects of four survivors on a copy of the sources (`effect.py`, `eff/*.txt`, `x/pg14.txt`).

**A harness defect of mine, repaired**: from 07:49 to 07:54 a second runner on two spare workers
numbered its threads 0 and 1, so its pytest runs shared base-temp folders and logs with the main
campaign's workers 0 and 1, and a run starting wiped the other's `tmp_path`. That can only make
false kills. Every result of the window (rows 600-900) was asked again in a clean run
(`results-reask.jsonl`): 297 of 301 gave the same outcome, the 4 others were kills that became
survivals (two dataclass flags, `gui/server.py:163`, `type_plans.py:32`), and the new outcomes are
the ones counted. The runner now names every per-worker path by the worker.

**Not covered**: `test_cmake` was asked of no mutant (its 57 tests reach the tool only through
CMake, 228 s a run); 5,360 of the planned sample (the budget, stratified cut); 43 survivors read
but left unclear; a kill matrix without `-x`.

### Strengths

- **Every guard that exists has the test that fires it.** Of the 88 guard mutants, 81 are killed:
  all 11 of the edit engine's (the fingerprint check, the rollback, the stage, its removal, the
  file's access, a created file over an existing one, a file named twice, the retry), all 8 of the
  session's confinement, 9 of the 10 query path rules (network, dot segments, relative, NUL,
  device, sibling prefix, length; case folding survives, M4), 6 of the 7 language-server mutants
  (its refusals and the withdrawal of fixed findings; the cache forget survives, M4), the 3
  closed-pipe and interrupt handlers, and 44 of the 49 server gates - the token,
  the Bearer scheme, the cookie, the launch code spent, expired, compared by prefix, weakened,
  `Sec-Fetch-Site`, `Origin`, the content type, both body limits, `frame-ancestors`, `nosniff`,
  `Referrer-Policy`, the inline hash, every page-path rule, the cap, the lingering close, the IPv6
  hold and both exclusivities.
- **The campaign scores well above the core's**: 83.9 % of 2,520 (84.3 % of those a test reaches);
  every stratum between 77.1 % (cli) and 88.5 % (plugins); negated tests 166 of 167 (the other
  hung), deleted raises
  143 of 144, swapped arguments 141 of 144, comparisons 160 of 166, returns 150 of 157, deleted
  findings 11 of 11.
- **The heavy files earn their time.** `test_gui_api` runs last in every ask, so when it is the first
  to fail no other in-scope file reaching the line failed: it is the only killer of 169 mutants (110
  of the 268 kills in the gui-api stratum). `test_gui_server`, next to last, is the first killer of
  180.
- **Where a rule is written twice, the suite compares the two**, and those comparisons catch what the
  line map cannot select: the route table against the security page (`tests/test_gui_docs.py`, 8
  module-level survivors killed in the follow-up), the toolbox's severities against the guide
  (`tests/test_documentation.py:3341`, 3), `KEY_ORDER` against `PROPAGATED_KEYS`
  (`tests/test_variable_keys.py:92`, 2), every query model published (`tests/test_gui_api.py`, 2).
- **Isolation and hygiene hold**: no false kill among 36 null mutants and 88 guard mutants on twelve
  parallel copies with arbitrary subsets of tests; 297 of 301 re-asked mutants gave the same outcome,
  the four others explained above; one `time.sleep` in the 38 files, inside a deadline loop
  (`tests/test_gui_server.py:2053`); no coverage pragma anywhere in `src/ddd`, so the 100 % branch
  gate is real; the suite writes nothing into its tree.
- **Pass 11b's eighteen findings are fixed but two**, among them both Importants (table below).

### Issues

#### Critical

None. No survivor is a defect of today's code; each is a wrong program the suite would let through.
The defects that are present - passes 10, 13 and 19 - have no test, which is I1.

#### Important

- **I1. The suite pins each guard that exists and none of the hazards a guard misses: every failure
  passes 10, 13 and 19 found by hand fails a test of 10 to 30 lines built from the suite's own
  helpers, and no such test is in the suite.**
  `SCRATCH/pass-22/probe-tree/tests/test_p22_probes.py`, run on a copy of the tree
  (`probes-run1.txt`): 10 failed. Per defect, what the probe observes and the nearest test:

  | defect | probe observes on the tree | nearest test, and what it pins instead |
  | --- | --- | --- |
  | pass 13 C1 | the revision's fingerprint of `b.ddd.json` is that of the bytes saved after the analysis read it; an edit carrying it is not refused (`DID NOT RAISE`) | `tests/test_gui_session.py:368-408` use the same `saving_while_analysing` helper and assert only that the next poll finds the save; `tests/test_gui_api.py:6767-6886` move an entry after the analysis, for the read routes |
  | pass 13 I1 | a save landing between the check and the rename is overwritten: `{"x": 2}` where the other editor wrote `{"x": 9}`, answered written | `tests/test_editing.py:620-630` changes the file before `apply_changes`, the one moment the check covers |
  | pass 13 C2 | with a second writer staging under the one name, the edit answers written with the fingerprint of `{"x": 2}` while the file holds `{"x": 3}` | none has two writers; `tests/test_editing.py:718-719` pins the shared name (M1) |
  | pass 19 I3 | `ddd check examples/inconsistent/project.ddd.json` with both streams closed: exit 0, with and without `--format json` | `tests/test_cli.py:3035-3055` close the pipe on `ddd schema`, which has no verdict |
  | pass 10 I1 | `one/a.ddd.json`'s `missing-producer` is published `[]` once `two/b.ddd.json` is opened | `tests/test_lsp.py:4363-4391`: one project, its project file opened second |
  | pass 10 I2 | the demo's `event_logger.ddd.json` shows three `missing-producer` errors while `ddd check demo.ddd.json` prints `ok: 23 variables` | no server test opens a sub-project's component |
  | pass 10 I3 | F2 from `reader_one` in a two-image project edits `writer` and `reader_one`, not `reader_two` | `test_a_file_in_two_projects_is_edited_once`: two images do not send one edit twice |
  | pass 10 I4 | an open buffer's unsaved `"Speed"` is left out of the rename, answered with two files | the drift tests (`PL02`, `PL05` killed) cover a buffer that moved a declaration, not one that added a mention |

  Three of the probes pass once a crude fix is applied in a copy (`probe-fix/`: a stage name per
  write and the bytes compared again before the rename; withdrawing only the files this run reported
  on), so they test the defect and not something near it.
  Why it is structural: the guards the code has are tested one refusal at a time and every one fires
  (Strengths); what is never built is a second actor - a second writer, a save inside the window, a
  second project, a second image, a buffer that is not the disk, a stream that closes on a run with a
  verdict. Passes 9, 10, 13 and 19 named their own cases in their Test gaps; what this adds is that
  the ten tests are short, need no fixture the suite lacks, run in about a second, and fail today, so
  each fix can land with its test (S, about an hour each).

- **I2. The token exchange and the Host gate are each pinned by one wrong value, so two weakenings of
  the first defence pass the whole scope.**
  `src/ddd/gui/server.py:713` and `:630`; tests `tests/test_gui_server.py:432-434`
  (`{"token": "wrong"}`, the only wrong token `POST /open` is ever sent) and `TestWhoMayAsk` (one
  foreign host, `evil.example`, as pass 12's Test gaps said).
  - Mutant `PG14`, the `/open` token compared as a substring rather than with `compare_digest`:
    survives the 4 tests that reach the line. On a mutated copy (`x/pg14.txt`) an empty or a partial
    token is then accepted while `"wrong"` is still refused. The Bearer header is safe from the same
    weakening because `test_anything_else_is_unauthorised[no-token]` sends an empty one (`PG11`
    killed).
  - Mutant `PG02`, the Host compared by prefix (`127.0.0.1...`, `localhost...`, any port): survives
    all 206 tests that reach the line.
  Consequence: a regression that would hand the token, and with it code execution (pass 12 I2), to
  whatever reaches the port would go out green; the DNS-rebinding layer could weaken in silence.
  Change (S): parametrise the wrong token over the empty string, a prefix, a suffix and the token
  with one character changed; parametrise `Host` over the forms pass 12 tried by hand.

- **I3. What the page is told is pinned on the smallest case, so a first-or-last confusion in it
  passes: an undo offering the bottom of the stack, a doubled per-file warning count, a preview split
  wrongly.**
  - `src/ddd/gui/session.py:555`, the snapshot's undo entry `self._stack[-1]` read as `[0]`:
    survives 161 tests. Effect on a copy (`eff/undo-bottom.txt`): after two edits `GET /api/state`
    offers `{'at': 1, 'label': 'edit first'}`, and pressing it answers `409 stale: edit 1 is not the
    one to undo any more`. The snapshot is tested with an empty stack and with one entry
    (`tests/test_gui_session.py:947`), where first and last are one.
  - `src/ddd/gui/session.py:928`, `warnings=sum(1 ...)` read as `sum(2 ...)`: survives 1,258 tests.
    Effect (`eff/warnings-doubled.txt`): over `examples/inconsistent`, `component_a.ddd.json` is
    answered 2 warnings where `ddd check` has 1, the totals still 1. Only a file's errors are
    asserted (`tests/test_gui_session.py:291-292`); nothing reads its warnings or infos, which the
    Files tab and the module graph show (`src/ddd/gui/api.py:410, 1755`).
  - `src/ddd/variables.py:287-288`, the fast path claimed to answer "what difflib answers ... on every
    pair of texts" (`tests/test_variables.py:263-265`) merging runs on `runs[0]`: survives, because
    the eight hand cases (`:311-359`) never have a run of two lines after another run; no random
    comparison with the difflib oracle the file already holds.
  - The same shape elsewhere, read off the survivors: the first workspace folder answered for all
    (`src/ddd/lsp/server.py:482`, every test has one root; pass 10 M10), the worst of two severities
    on an arrow (`src/ddd/graph.py:59`, `key=` dropped survives 7 tests), a finding's place under an
    array element (`src/ddd/project_shared.py:361`, `src/ddd/project_types.py:226`).
  Pass 21 I6 found square, name-ordered, one-entry fixtures hiding index confusions in the core; this
  is the same on what the reader sees. Change (S): a second edit before the state is read, a file
  with a warning and an info in the state tests, a seeded random comparison against
  `_reference_hunks`.

#### Minor

- **M1. A test pins the shared stage name pass 13 C2 found deletes a description.**
  `tests/test_editing.py:718-719`, `test_edits_stage_under_the_name_every_other_writer_stages_under`:
  `assert STAGING_SUFFIX == ARTEFACT_STAGING_SUFFIX`. The fix pass 13 proposes, a stage name of its
  own per write, has to break this test, which states the hazard as a rule. Change (S): replace it
  with I1's C2 probe.
- **M2. The idle timeout is tested only through tests that replace it.** `src/ddd/gui/server.py:544`
  (`timeout = IDLE_SECONDS`); the three tests that close an idle connection set
  `module._Handler.timeout` to 0.05 or 0.5 first (`tests/test_gui_server.py:1644`, `:2040`, `:2395`)
  and no test reads `IDLE_SECONDS`. `PG35`, `timeout = None`, survives all 293 tests that reach
  `gui/server.py`, and `IDLE_SECONDS = 31` every in-scope file naming the module. The comment at `:2038-2039` says what is asserted
  "is that the socket carries one at all"; the monkeypatch is what gives it one. With the cap at 64
  (`:106`), idle connections would then hold every slot for good (adds to pass 12 M8). Change (S):
  assert `_Handler.timeout == IDLE_SECONDS` once.
- **M3. Several expectations are taken from the code under test.** The suite has a rule for this -
  "Pinned by its literal ... would drift along with any change to it" (`tests/test_gui_server.py:300,
  307, 349, 383, 467`) - applied to the token's strength and the code's lifetime but not to:
  the content security policy (`:1036` checks one substring, `:1053` equals `page_policy(...)`;
  `PG23`, `base-uri 'none'` dropped, survives 293 tests); the JSON-RPC codes
  (`tests/test_lsp.py:56-57, 159-162, 5474` import them; `METHOD_NOT_FOUND = -32600` and
  `REQUEST_FAILED = -32802`, `src/ddd/lsp/protocol.py:122, 141`, survive every in-scope file naming
  the module); `MAX_BODY` (`tests/test_gui_server.py:569`; `1024 * 1025` survives the same); the
  range of a finding on a whole first line (`src/ddd/lsp/diagnostics.py:401-402`: a range without
  its `character` key, or without its `end`, which a client cannot read, survives every importer
  file); the toolbox's
  severities (`tests/test_toolbox_from_elf.py:96-102` is parametrised over the table it tests; only
  the guide's copy, `tests/test_documentation.py:3341`, kills a change). Change (S): literals.
- **M4. Smaller guard survivors.** `PG48` (the 503's drain before closing,
  `src/ddd/gui/server.py:295`; without it the refusal can be lost to a reset, pass 12 M3), `PQ09`
  (`_CASELESS` on Windows, `src/ddd/gui/queries.py:74`: no test spells a served directory in another
  case, 1,177 tests reach it), `PL06` (`self._forget()` after a rename, `src/ddd/lsp/server.py:762`:
  no test asks the server again after a rename without a notification between).
- **M5. Positive paths no test takes, each a refusal or a column the reader would meet.** Setting an
  external type's `header` or a structure's `description` through a type plan
  (`src/ddd/type_plans.py:32-33`: dropping either key from `SETTABLE` survives every in-scope file
  naming the module, and dropping the external kind whole the 33 tests reaching the line;
  `tests/test_type_plans.py:72-84` asserts only the
  refusal's code and that the key is named, which a "not settable" refusal also does); a hover on a
  map's `y_axis` (`src/ddd/lsp/hover.py:43`, likewise); the Types tab's `bits` column
  (`src/ddd/project_types.py:44`, likewise); the Compare reply's renames with an entry
  (`src/ddd/gui/api.py:1501`: `entry["from"]` misspelt survives, since `tests/test_gui_api.py:4054`
  has none, though `tests/test_gui_compare.py:381` has one one level down); a stylesheet served
  (`src/ddd/gui/server.py:163`: `.css` as `text/html`, which under `nosniff` a browser will not
  apply, survives); `file-kind` as a load check (`src/ddd/lsp/navigation.py:113`) and the role words
  of an input (`src/ddd/variables.py:29`), both surviving every importer file; a backend answering a
  list with one stray item (`src/ddd/plugins.py:493`, `all` read as `any`); a dotted plugin whose
  package is missing (`src/ddd/plugins.py:239`); invalid UTF-8 in a DWARF string
  (`src/ddd/elf.py:864`, `errors="replace"` dropped survives 174 tests; adds to pass 11 M2); a
  big-endian DWARF-2 bitfield (`src/ddd/elf.py:787`; adds to pass 11's five). Each S.
- **M6. The command line's own guards.** `ddd id` without `--assign` (`src/ddd/cli.py:325-328`: the
  handler always assigns, `:1471-1485`, so `required=True`, whose help says "so that no run edits a
  file by accident", is the only guard; dropping it survives 426 tests and `test_transcripts`, since
  every `ddd id` test passes `--assign`); `--format` accepting anything (`:748`, choices dropped:
  `ddd check ... --format xml` prints text and exits 1 where the tree refuses it with exit 2,
  reproduced with `effect.py`); the byte order `generate a2l` writes with neither `--byte-order` nor
  `--image` (`:1224`, `BYTE_ORDERS[0]` read as `[-1]` survives 59 tests and `test_transcripts`;
  `tests/test_cli.py:3772-3773` pins the constant, `:4533, 4561` the image's order); port 65535
  (`:1627`).
- **M7. What only a separate process shows is pinned by nothing in the suite.** stdout reconfigured
  to UTF-8 (`src/ddd/cli.py:123`): deleting it survives 420 in-process tests, which replace the
  stream, and `test_transcripts`, which runs every documented command with `PYTHONUTF8=1`
  (`tests/test_transcripts.py:340`) - the one setting that makes the reconfigure redundant. The
  flush of `ddd gui`'s address line (`src/ddd/gui/server.py:1027`, `flush=True` dropped survives 16
  tests): the commits closing part 19c's hang (`a9405e57`, `2b704a7e`) are about this line reaching
  its reader, and only the journeys read it through a pipe. Change (S): one subprocess test per behaviour, without `PYTHONUTF8`.
- **M8. Two tests of `tests/test_gui_api.py` fail on a Windows without long paths, the default, so
  the gate is red out of the box with three failures here.** `tests/test_gui_api.py:2646-2651` and
  `:8515-8521` create a 243-byte name (`:496`), staged as 255 bytes, under `tmp_path`; with
  `LongPathsEnabled` 0 (this machine, `reg query ...\FileSystem`), any `tmp_path` puts the stage past
  260 characters and the edit is answered `500 unwritable` (`timing/serial.txt:100-134`); pytest's
  own default base directory is about 90 characters, so the two cannot pass on such a machine
  wherever they run; pass 21 saw the same three failures. The developer page names no long-path
  requirement (`docs/developer_documentation.rst:392-415`). Change (S): derive the longest name from
  the parent's length on Windows, or state the requirement.
- **M9. "A couple of minutes" is nine to eleven, two files are two thirds of it, and nothing smaller
  than a file can be asked for.** `docs/developer_documentation.rst:406` (pass 20 M11 found the
  sentence). Measured here, one process: 674 s with the default options, 562 s with `--no-cov`, of
  which `test_cmake` is 228 s (41.7 %, 57 tests) and `test_gui_server` 125 s (22.8 %, 346 tests at
  0.36 s each, spread evenly: 13 tests take over a second, 14 s together, so the cost is the
  fixture - a real server over a freshly analysed project per test - not a few slow tests); the
  other 6,639 tests take 195 s. No marker, no documented way to leave the two out, no
  `pytest-xdist` in `requirements-dev.txt`, and the coverage gate fails any partial run unless
  `--no-cov` is given. The isolation evidence above (twelve parallel copies, no false kill) says the
  suite would likely take to `-n auto`, bounded by `test_cmake`'s longest class (35 s,
  `TestAddressesFromTheImage`). Change (S): a `slow` marker on the two files, the developer page's
  numbers, and the file a module's tests live in (see open question 3).

### Status of the 2026-09-15 findings in this area

Pass 11b's eighteen; only those not plainly fixed:

| id | finding | status | where |
| --- | --- | --- | --- |
| P11B-M12 | core tests import helpers from `test_lsp` | half: `test_external` fixed, `test_constants` remains (pass 21 M8); three new imports between test modules: `test_cmake` from `test_cli`, `test_gui_compare` from `test_gui_api`, `test_lsp` from `test_variable_keys` | `tests/test_constants.py:1296`, `tests/test_cmake.py:44`, `tests/test_gui_compare.py:38`, `tests/test_lsp.py:78` |
| P11B-M14 | `test_cmake` configures the same trees again and again | partly: class-scoped fixtures now (`tests/test_cmake.py:238, 313, 822, 1149, 1498, 1656`); still 228 s, 42 % of the suite (M9) | `tests/test_cmake.py` |

Fixed: I1 (`tests/test_lsp.py:86-100`, publications keyed by the uri string), I2
(`tests/test_lsp.py:4587-4626`, `-b` reaching discovery), M1 (`tests/test_cli.py:184-192`), M2, M3
(`tests/test_lsp.py:204`), M4 (`tests/test_documentation.py:469, 549, 1007, 2001, 2308, 2316, 2323`),
M5 (`tests/test_transcripts.py:534-541`), M6 (`tests/test_documentation.py:397`), M7, M8, M9
(`tests/test_plugins.py:1878`), M10 (`tests/test_plugins.py:2240`), M11, M13
(`tests/test_cmake.py:1918`), M15 (`tests/test_example_plugin.py:38-46`), M16
(`editors/vscode/src/launch.test.ts:64-80`).

### Open questions

1. Is a second actor - a second writer, a save inside an analysis, a second project or image, an
   open buffer, a closed stream on a run with a verdict - something the suite must hold, as a rule?
   I1's probes show it can be done without threads or sleeps. The answer decides whether the fixes of
   passes 10, 13 and 19 land with their tests, and whether M1's test is a rule or a defect.
2. Is a stock Windows, without long paths, a supported development machine (M8)? If yes, two tests
   change; if no, the developer page says so.
3. Should a contributor be able to run "what matters" for a module in seconds - a `slow` marker on
   `test_cmake` and `test_gui_server`, `pytest-xdist`, a map from module to test files (the line map
   used here is one) - or is the whole suite before a commit the intended loop? The developer page's
   timing and advice follow the answer.

### Test gaps

**Mutation, against the 38 in-scope files.** 2,520 mutants with a real outcome of the 7,880 planned
(13,211 sites): 2,108 killed, 7 hung past 600 s (a ci job would hang), 393 survived, 12 reached by no
in-scope test, 0 invalid. Score, killed or hung over what ran: **83.9 %**; over what a test reaches,
**84.3 %**.

| stratum | ran | killed | hung | survived | unreached | score |
| --- | --- | --- | --- | --- | --- | --- |
| cli | 262 | 202 | 0 | 50 | 10 | 77.1 % |
| editing | 324 | 269 | 2 | 52 | 1 | 83.6 % |
| elf | 361 | 313 | 1 | 47 | 0 | 87.0 % |
| gui-api | 308 | 268 | 1 | 39 | 0 | 87.3 % |
| gui-server | 276 | 225 | 2 | 49 | 0 | 82.2 % |
| gui-session | 254 | 215 | 1 | 38 | 0 | 85.0 % |
| lsp | 316 | 253 | 0 | 62 | 1 | 80.1 % |
| plugins | 113 | 100 | 0 | 13 | 0 | 88.5 % |
| project | 306 | 263 | 0 | 43 | 0 | 85.9 % |

By operator, killed share: negated test 100 %, deleted raise 99 %, swapped arguments 98 %,
comparison 96 %, return 96 %, deleted statement 94 %, enum member 93 %, boolean 92 %, arithmetic
92 %, deleted flow 89 %, table entry swapped 86 %, string token 85 %, number 82 %, table entry
dropped 78 %, message 78 %, swapped function 75 %, index 62 %, dropped keyword 56 %, boolean
constant 40 % (the last three mostly flags and first-or-last on one element). Lowest files:
`gui/contract.py` 7 of 17, `type_plans.py` 11 of 16, `lsp/hover.py` 23 of 33, `graph.py` 16 of 22,
`lsp/diagnostics.py` 27 of 36, `lsp/navigation.py` 34 of 45, `cli.py` 203 of 260.

**`tests/test_gui_api.py`, sampled by mutation**: of the 308 mutants of what it tests, 268 killed,
39 survived; `gui/api.py` alone 182 of 206. `test_gui_api` is the first and only in-scope killer of
110 of the stratum's kills (169 across all strata), `test_gui_queries` of 90, the hostile walk of 34.
Its survivors are I3's counts, M5's renames, M3's route codes, and statuses of the 500 branch
(`src/ddd/gui/api.py:943, 1239`: 501 survives).

**The 405 survivors and unreached, each read** (`survivors.tsv`, `labels22.tsv`): 99 dataclass or
model flags; 83 equivalent (an index on one element, a code that is equal, a placeholder the
docstring says cannot matter); 55 help texts and messages; 20 cosmetic (an indent, an icon's type);
18 order (`sorted` dropped on name-ordered or set-derived data); 16 killed in a follow-up (8 by
`test_gui_docs`, 3 by `test_documentation`, 2 each by `test_variable_keys` and `test_gui_api`, 1 by
`test_hardening`); 11 unreached, 10 of them artefacts of the line map (tuple elements and keyword
defaults on lines of their own, `src/ddd/cli.py:255-268` among them, carry no line context, so no
test was asked: the six asked again whole all died, in `test_plugins` and `test_finding_fixes`,
the other six were not asked again); 2 performance only; 2 module-level not asked again; **43 unclear** (mostly
`gui/depth.py`'s walk and the session's wake conditions); **56 real gaps** - I3, M2, M3, M4, M5,
M6, M7, the 500 branch's statuses, and three boundaries (port 65535, a carriage return at offset 0,
`src/ddd/editing.py:136`; the escape of non-ASCII values written, `src/ddd/editing.py:718`, adds to
pass 2 M3).

**Effects reproduced**: the undo of the bottom (`eff/undo-bottom.txt`), the doubled warnings
(`eff/warnings-doubled.txt`), `--format xml` accepted (`effect.py` run, exit 1 against 2), the empty
token accepted under `PG14` (`x/pg14.txt`).

**Follow-ups.** Module-level survivors asked of every in-scope file naming the module or a module
naming it, whole: 47 asked, 16 died (above), 31 survive; then the unreached, 6 asked again before
the run was stopped, all 6 died (line-map artefacts: `test_plugins`, `test_finding_fixes`); the
other 6 were not asked. `cli.py`/`plugins.py` survivors asked of
`test_transcripts`: 28 asked, none died. Survivors asked of the tests outside the scope: 112 asked,
91 reached by none of them (this code is the periphery's own), 1 died (`cli.py:883` in
`test_hardening`), 20 survive.

**Harness caveats**, so the numbers are read right: a mutant was asked only of the in-scope tests
reaching its line, so a test reading a table without running a line of its module is missed until
the follow-up (16 such kills found); `test_cmake` and the subprocess half of `test_transcripts` and
`test_documentation` are invisible to the line map; timeouts are counted apart, not as kills; the
first-killer counts depend on the order files are asked in (cheap first, `test_gui_api` last).

**Gaps found, beyond those passes 9-14 and 19 listed**: the ten probes of I1 (each a ready test);
the wrong values of I2; a second edit, a warning count and a multi-line run (I3); the literals of M3;
the positive paths of M5; `ddd id` without `--assign`, an invalid `--format`, the default byte order
(M6); one subprocess run without `PYTHONUTF8` and one read of the address through a pipe (M7).

### Assessment

The periphery's suite is better than the core's by every measure this pass took: every guard the
code has fires a test when removed, 84 % of mutants die against the core's 72 %, the heavy files
are not redundant, and it is isolated enough to run on twelve copies at once without a false kill.
Its failure is of a different kind, and more serious than a score says: it tests what the code
already refuses, one refusal at a time, and never builds the second actor that every hand-found
defect of passes 10, 13 and 19 needs - a second writer, a save in the window, a second project or
image, a buffer unlike the disk, a closed stream on a failing run. Each of those ten defects fails a
short test written from the suite's own helpers, and none is there; one test even pins the shared
stage name behind pass 13's lost description. Around that, the gaps are the ordinary ones of a large
suite with one-entry fixtures and expectations read from the code under test: an undo that offers
the wrong edit, a doubled warning count, an empty token accepted by a weakened compare, all green.
The runtime is honest but undocumented: nine to eleven minutes in one process, two thirds of it in
two files, and no smaller loop offered. 100 % coverage here means every line ran; it does not mean
the hazards the reader of passes 10 and 13 met were ever tried.

```candidates
22|I1|tests/test_gui_session.py:368|Suite pins every guard that exists, no hazard a guard misses: the ten hand-found failures of passes 10, 13, 19 each fail a 10-30 line probe
22|I2|tests/test_gui_server.py:432|Token exchange and Host gate each pinned by one wrong value: a substring token compare and a prefix Host check pass the whole scope
22|I3|src/ddd/gui/session.py:555|What the page is told pinned on the smallest case: an undo of the stack's bottom, doubled per-file warnings, hunks of two runs pass
22|M1|tests/test_editing.py:718|A test pins the shared stage name pass 13 C2 found deletes a description
22|M2|tests/test_gui_server.py:2040|Idle timeout tested only by tests that replace it: timeout None passes 293 tests
22|M3|tests/test_gui_server.py:1036|Expectations taken from the code under test: CSP, JSON-RPC codes, MAX_BODY, the whole-first-line range, the toolbox severities
22|M4|src/ddd/gui/server.py:295|Smaller guard survivors: the 503 drain, Windows case folding of served paths, the LSP cache after a rename
22|M5|src/ddd/type_plans.py:32|Positive paths no test takes: an external's header, y_axis hover, bits column, Compare renames, a stylesheet, invalid UTF-8 in DWARF
22|M6|src/ddd/cli.py:328|Command-line guards unpinned: ddd id without --assign edits, --format accepts anything, the default a2l byte order
22|M7|src/ddd/cli.py:123|What only a separate process shows is pinned by nothing: stdout's UTF-8 (transcripts set PYTHONUTF8), the address line's flush
22|M8|tests/test_gui_api.py:2646|Two longest-name tests fail on any Windows without long paths, so the gate is red out of the box here
22|M9|docs/developer_documentation.rst:406|A couple of minutes is nine to eleven, two files are two thirds of it, no smaller loop offered
```
