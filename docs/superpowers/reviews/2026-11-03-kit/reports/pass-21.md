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
