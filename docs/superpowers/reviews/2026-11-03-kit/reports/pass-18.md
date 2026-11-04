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
