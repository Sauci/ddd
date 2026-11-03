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
