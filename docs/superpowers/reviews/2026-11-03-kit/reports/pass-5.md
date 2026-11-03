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
