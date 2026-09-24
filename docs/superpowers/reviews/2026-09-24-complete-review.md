# Complete review of DDD, 2026-09-24

A full review of the whole project after release 0.11.0, run as a sequence of independent passes,
each by one reviewer reading the material fresh, followed by a verification of every finding by a
second reviewer and two sweeps for what the passes missed. It follows the review of 2026-09-15
(branch `review/complete-review-2026-09-15`), whose findings were fixed on 2026-09-16; each pass
records the status of that review's findings in its area. What it finds is to be fixed in 0.11.1.

Since 2026-09-15 the project gained the local web GUI (`ddd gui`, milestones 1 to 7 of its plan),
record layouts with point counts, dictionary format 9 and release 0.11.0: 393 commits on master.
The GUI is reviewed in two passes of its own, server side (7) and front end (8).

Line numbers refer to master at `faee81e` unless a pass says otherwise. Work in progress: passes are
added as they finish, and the summary is written last.

## Baseline

On master at `faee81e`, Windows 11, Python 3.13, the worktree's own venv, from Git Bash:

- `python -m pytest`: all passed but one, coverage 100.00 % of lines and branches (10543
  statements, 2848 branches), in 5 min 23 s. The failure is the known
  `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`
  (Windows symlink privilege); it passes in CI.
- `ruff check .`, `ruff format --check .` (122 files), `mypy` (strict, 68 source files): clean.
- `gui/`: `npm run schemas`, `lint` (biome, 133 files, one info), `typecheck`, `test` (Vitest, 19
  files, 358 tests, 100 % statements/branches/functions/lines), `build`: clean. Without
  `npm run schemas` first, `typecheck` fails on three implicit `any` in `src/stories/fixtures.ts`
  (the generated types are absent); CI runs `schemas` first, so this is only a local trap.

## Pass 1: SPEC.md on its own

### Scope covered

- `SPEC.md` at `faee81e`, all 2411 lines, read in order with line numbers (1-300, 300-599,
  599-898, 898-1197, 1197-1496, 1496-1795, 1795-2114, 2114-2411).
- `git diff 6e9e99f faee81e -- SPEC.md` (514 insertions, 178 deletions), hunk by hunk, with
  extra attention on `point_counts` (3.1, 3.2, 4, 4.1, 5.2, 5.3), format 9, the constants and
  string sentences, the `ddd gui` mentions (3.6, 7) and the sentences the 2026-09-16 fixes added.
- Mechanical checks (python, in `SCRATCH/pass-1/`): every `[section N](#anchor)` against the 37
  heading anchors and against the number in its link text (all resolve and match); every
  hyphenated backticked identifier against `ddd checks --format json` (all 69 registry checks are
  named; the spec names no check the tool lacks); the nine `(project)` checks, the eight fixed
  ones and the thirteen `(comparison)` ones against the registry (exact); plain and bold
  `shall`/`must`/`should`/`may` (no plain binding use left).
- Probes with the review tree's `.venv/Scripts/ddd.exe` (0.11.0), projects under
  `SCRATCH/pass-1/`: `pc` (project `point_counts` + component override, counted axis/curve,
  boolean curve, array-of-structures instance; dump, list JSON, generate all, a format-8 copy of
  the dump compared against it), `pc2` (sub-project stating `point_counts`, a constant-sized
  counted axis, map, scalar and list `init` on counted tables), `pc3`/`pc4` (broken baseline
  against a description candidate; `--renames` of a renamed instance), `un` (unowned counted
  table), `k` (constant literals in C and A2L), `ii` (relaxed `init-invalid` beside a relaxed
  `point-counts-unrepresentable`), `si` (string `init` respelled between deliveries). Key output
  is in `SCRATCH/pass-1/transcript.txt`.
- Read to settle a sentence only: `src/ddd/ir.py:645`, `src/ddd/loading.py:1372-1384`,
  `cmake/Ddd.cmake:12-33,106`, `src/ddd/cli.py:1765-1800`, `docs/comparing_deliveries.rst:660-681`,
  `src/ddd/analysis.py:1537-1567`, the dictionary schema's `format` and `source`, the record
  layouts design and plan (`docs/superpowers/specs/2026-09-23-record-layouts-design.md`, plan task
  9), the "Left open" of `docs/superpowers/plans/2026-09-16-review-fixes.md`,
  `tests/test_documentation.py:1492-1502`.
- Not covered: whether each section agrees with its own code and docs in depth (passes 2-8);
  the GUI beyond the two sentences SPEC gives it.

### Strengths

- The previous pass 1 is closed almost entirely: all five Important and eleven of its twelve
  Minor findings are fixed in the text (table below), and every probe of a fixed sentence
  reproduced what the sentence now says - `--renames` spells `abcdefghjkm6[0].a`
  (`SPEC.md:1516-1519`), a string `init` respelled from `[72,105,0,0]` to `"Hi"` is silent even
  under `--strict` (`SPEC.md:1586-1590`), wildcard matches sort by POSIX code point
  (`SPEC.md:275-279`, `loading.py:1378-1384`), `1e3` reaches C and A2L as `1000.0`
  (`SPEC.md:1011-1014`).
- 1.1 now says whom `shall` binds beyond the tool (`SPEC.md:80-88`), which dissolves the
  carried-over "shall on other actors" finding cleanly rather than by unbolding.
- The public JSON shapes are now stated by key: `ddd list` (`SPEC.md:2040-2044`, a leaf row
  carries `name`, `path`, `instance`, `instance_id` - reproduced), `ddd checks`
  (`SPEC.md:2092-2094`, the six keys the tool emits), `ddd artefacts`, `generated`, 5.3's
  `references` and `owner` (`SPEC.md:1964-1967`); 5.3's top-level keys and the object, instance
  and leaf key lists are exactly those of a format-9 dump of `pc`.
- The check sets are exact: nine `(project)` checks (`SPEC.md:1233-1235`), eight fixed
  (`SPEC.md:1411-1413`), thirteen comparison checks in 4.1; both new point-count checks are listed
  with the registry's severities (`SPEC.md:1374-1376`, `1445-1447`).
- The CMake floors now agree with the module (3.30 collected, 3.20 overall: `SPEC.md:2199-2201`,
  `cmake/Ddd.cmake:32,106`).

### Issues

#### Critical

None.

#### Important

- **I1. Section 7 still says the dictionary is format 8; 5.3 and the tool say 9.**
  `SPEC.md:2165` "The dictionary names its own format (`format`, today `8`)" against
  `SPEC.md:1939` "Its `format` is `9`" and `src/ddd/ir.py:645` `DICTIONARY_FORMAT = 9`. Trigger:
  `ddd dump` of any project -> `"format": 9`. A reader written from section 7 implements format 8
  and, by the rule both sections state ("a reader **shall** refuse a higher one",
  `SPEC.md:1940-1941`; "refuses it (`schema`)", `SPEC.md:2167-2168`), refuses every dictionary
  0.11.0 writes. The record-layouts plan (task 9, step 2) touched 5.3 only; the one test that
  pins the format number reads the CHANGELOG, not SPEC (`tests/test_documentation.py:1492-1502`).
  Established: read off both lines, dump reproduced.

- **I2. What `point_counts: "leading"` does to the C storage is specified nowhere, and three
  sentences say the opposite of what the tool generates.** SPEC gives the key a meaning only in
  the A2L (`SPEC.md:1814-1821`). Against the generated C:
  - the kind table (`SPEC.md:433-435`) says an axis is "array `[size]`", a curve "`[size of the
    axis]`", a map "`[size of y][size of x]`", and 5.2 says "maps are stored row wise, that is the
    C declaration is `[y][x]`" (`SPEC.md:1816`); `pc2` generates
    `const uint8_t M[2 + (2) * (NX)] = { NX, 2U, 1U, 2U, 3U, 4U, 5U, 6U };`,
    `const uint8_t Ax[1 + (NX)] = { NX, 1U, 2U, 3U };`;
  - "`null` means implicit zero initialisation" (`SPEC.md:355`); a counted axis with no `init`
    generates `const uint8_t Ay[1 + (2)] = { 2U };` - always an explicit initialiser, rightly,
    but the spec forbids it;
  - "`init` ... **must** match the shape of the object" (`SPEC.md:452-455`) does not say the
    counts are outside `init` (the tool refuses `[3,1,2,3]` on a 3-point curve as
    `init-invalid` and broadcasts a scalar `7` over the data only: `{ NX, 7U, 7U, 7U }`);
  - 5.1's "the *data* they are given is fixed" (`SPEC.md:1723-1746`) does not mention the
    counts, the flat declaration, or the `dimensions`/`point_counts` fields templates now get.
  The order of the counts (x then y) and their type (the object's own datatype) can only be
  inferred from the A2L bullet. 5.3 calls the dictionary "the contract between the checking front
  end and every backend, DDD's own and a project's" (`SPEC.md:1938-1939`); a project backend or a
  template author reading SPEC declares a counted map `[y][x]` without counts and ships an image
  whose layout disagrees with the A2L DDD writes. The design (`2026-09-23-record-layouts-design.md`
  section 4) states all of it; SPEC received only the key and the dictionary field. Established:
  reproduced (`SCRATCH/pass-1/pc2/out/ddd_globals.c`), sentences read off.

#### Minor

- **M1. A second project file stating `point_counts` is a fixed-severity `schema` error, and 3.1
  does not say so.** `SPEC.md:260-262` gives the key and its default only. Trigger (`pc2`): root
  `"point_counts": "leading"` including a sub-project stating `"none"` ->
  `sub.ddd.json#project.point_counts: error[schema]: point_counts is already stated as 'leading'`,
  exit 1, not relaxable; the same value twice is accepted. The parallel rule for `extensions` is
  written (`SPEC.md:1156-1157` "a second file stating a plugin's settings is `schema`"). A reader
  of 3.1 expects a sub-project's value to apply to its own components, or at least a relaxable
  finding. Reproduced.

- **M2. "Reads a lower one with the defaults of that format" names no defaults for format 8.**
  `SPEC.md:1941` and `SPEC.md:1661-1665` (formats 3 and 6 only). A format-8 dictionary has no
  `point_counts`; the tool reads it as `"none"` (said in the dictionary schema's description, not
  in SPEC). Trigger: `pc/base8.json` (the `pc` dump with `format: 8`, `point_counts` removed)
  against the same project -> three `changed-interface` "point_counts: leading != none" and
  "cannot replace". The behaviour is right; SPEC does not let a reader predict it. Reproduced.

- **M3. "Every rule this specification states about a data object states it about an instance
  too" is broader than the tool and the rest of SPEC.** `SPEC.md:160` (added 2026-09-16). Against
  it: `ddd list` "listing the resolved data objects" (`SPEC.md:2037`) has rows for `Inst[0].a` and
  `Inst[1].a` and none for `Inst`; the `ok:` line "counting the objects" (`SPEC.md:2116`) says
  "6 variables" for four objects, two leaves and one instance (`pc3`); `--renames` "one entry per
  paired object whose name changed" (`SPEC.md:1514-1515`) lists only the members when `Inst`
  becomes `Inst2` (`pc4`: two entries, none with id `abcdefghjkm6` alone); 5.2's "`MEASUREMENT`
  for every measurement" is excepted elsewhere (`SPEC.md:1912-1926`). Either the sentence
  narrows to the rules it means (ownership, scope, `id`, the comparison of 4.1) or the listings
  gain the instance. Reproduced.

- **M4. A description candidate is not analysed at all when the baseline carries an error, which
  4.1 does not say, and `ddd check --baseline` does the opposite.** `SPEC.md:1500-1501` "A
  candidate given as a description is analysed too, and all of its findings are reported";
  `SPEC.md:1505-1506` says only that no verdict is printed. Trigger: `ddd compare pc/proj.ddd.json
  pc3/proj.ddd.json` (baseline with one `point-counts-unrepresentable`) -> only the carried
  baseline error, none of the candidate's three warnings, no comparison, exit 1; `ddd check
  pc3/proj.ddd.json --baseline pc/proj.ddd.json` -> the carried error, `removed-object`, the
  candidate's three warnings, exit 1. `docs/comparing_deliveries.rst:676-681` and
  `cli.py:1776-1778` describe the `compare` behaviour as intended; SPEC 7 presents
  `check --baseline` as "both questions in one exit code" (`SPEC.md:2020-2021`), not as a run
  that answers differently. Reproduced.

- **M5. "What the outputs carry is the number in its shortest spelling" is not what the C
  carries above `LLONG_MAX`.** `SPEC.md:1011-1014`. Trigger (`k`): `"value":
  18446744073709551615` -> `#define UMAX 18446744073709551615ULL`, A2L `"18446744073709551615"`
  (the example templates render `constant.literal`, `backends/c/model.py:232-244`, which adds the
  suffix because no unsuffixed C literal of that value exists). The sentence should say the C
  literal carries the suffix the value needs. Reproduced.

- **M6. Terminology residue (carried from 2026-09-15 P1-M9).** "structured variable"
  (`SPEC.md:1106`, `1206`, `1531`, `1549`) beside the defined "instance" and "structured object";
  "a2l" in prose (`SPEC.md:1016`, `1058`, `1072`, `1089`, `1096`, `1354`, `1363`, `2226-2227`)
  beside "A2L"; 3.7's "A leaf is one value member of one element" (`SPEC.md:899`) where `value`
  is the name of a member shape, while a `bits` member is a leaf too (the dump of
  `examples/structures` lists `Inlet.status.mode` with `bits: 2`; `analysis.py:1560-1562` counts
  it toward the 100 000); 3.3.2's "`typename` names a type the project declares in a types file"
  (`SPEC.md:616-617`) omits the component-declared types 3.2 allows; "(`ddd gui`, section 7)"
  (`SPEC.md:784`) is the one section reference that is not a link. Read off.

### Status of the 2026-09-15 findings in this area

All five Important findings and the open questions are fixed: I1 (`SPEC.md:1516-1519`,
reproduced), I2 (`2054-2061`), I3 (`168`), I4 (`275-279`, `1789-1795`; `loading.py:1378-1384`),
I5 (`1530-1539`); Minors M1 (`1359`), M2 (`80-88`), M3 (`668-670`), M5 (`1032-1036`, `1471`),
M6 (`1586-1590`, `1959-1961`), M7 (`1211-1212`, `2143-2144`), M8 (`2248-2249`), M10
(`2040-2049`, `2092-2094`, `2119`, `1964-1967`, `798`, `2199-2201`), M11 (`167-168`, `172`, `180`),
M12 (`423-424`, `1411-1418`, `1893`, `640`, `933-936`, `1309-1312`) are fixed. Not plainly fixed:

| id | finding | status | where |
| --- | --- | --- | --- |
| P1-M4 | constant literal "as written" | fixed, one residue: the `ULL` suffix | M5 |
| P1-M9 | terms used otherwise or undefined | partly: instance, storage category, vocabulary file, standalone, delivery settled; structured variable, a2l, member path remain | M6 |

### Open questions

1. May a sub-project state its own `point_counts` for the components it includes (M1)? Yes
   changes the loader's resolution to the nearest project and 3.1's sentence; no keeps the
   refusal and 3.1 says "stated by one project file", as for `extensions`.
2. Should `ddd compare` analyse and report a description candidate when the baseline is broken
   (M4)? Yes aligns it with `check --baseline` and makes 4.1 true as written; no needs a
   sentence in 4.1 saying the candidate is not read, and one in 7 saying the two commands part.
3. Is an instance a row of `ddd list`, a count in `ok:`, and an entry of `--renames` (M3)? Yes is
   a tool change (and a new rename entry format a migration script would see); no narrows the
   concept-table sentence.

### Test gaps

- Nothing pins the dictionary format number SPEC states against `DICTIONARY_FORMAT`:
  `tests/test_documentation.py:1492-1502` reads the CHANGELOG only, which is how I1 survived the
  bump (carried over from 2026-09-15; now it has bitten).
- Nothing ties SPEC 3.3's storage column or 5.2's "`[y][x]`" to the counted declaration; a
  documentation guard naming `point_counts` in 3.3 and 5.1 would have caught I2.
- `ddd compare` with a broken baseline and a description candidate: tests assert the carried
  `in the baseline:` line (`tests/test_cli.py:2017`, `2078`), not that the candidate's own
  findings are withheld while `check --baseline` reports them (M4). Judged by grep.
- The second-project-file refusal of `point_counts` is tested (`tests/test_point_counts.py:99-107`)
  but has no SPEC sentence to be tested against (M1).

### Assessment

SPEC.md absorbed the 2026-09-15 pass cleanly - every Important finding is fixed, the JSON
shapes and check sets are exact, and the cross-references and requirement words are clean by
mechanical check. The weak spot is the newest material. The record-layouts change reached SPEC
as a key, two checks, an A2L bullet and a dictionary field. What it does to the C storage, to
`init` and to the kind table's declared shapes is not there, and three older sentences now
contradict the generated code (I2). The format bump reached 5.3 but not the paragraph in
section 7 that states the same number, so a reader built from section 7 refuses every 0.11.0
dictionary (I1). Both are text fixes. The Minors are gaps of the same kind: behaviour the tool
has and the spec does not state (sub-project `point_counts`, format-8 defaults, the broken
baseline run), and one new sentence that says more about instances than the tool does. Before
0.11.1, fix I1 and I2 and add a documentation test pinning SPEC's format number.

```candidates
1|I1|SPEC.md:2165|Section 7 says the dictionary format is 8; 5.3 and the tool write 9
1|I2|SPEC.md:433|point_counts "leading" C storage unspecified; kind table, 5.2 [y][x] and init null contradict the generated flat counted declaration
1|M1|SPEC.md:260|A second project file stating point_counts is a fixed schema error that 3.1 does not state
1|M2|SPEC.md:1941|Defaults of older dictionary formats unstated; format 8's point_counts "none" appears nowhere in SPEC
1|M3|SPEC.md:160|"Every rule about a data object holds for an instance" contradicted by ddd list, the ok: count and --renames
1|M4|SPEC.md:1500|compare with a broken baseline does not analyse a description candidate, unlike 4.1's text and check --baseline
1|M5|SPEC.md:1011|Constant "shortest spelling" is not what C carries above LLONG_MAX (ULL suffix)
1|M6|SPEC.md:899|Terminology residue: structured variable, prose a2l, "value member" leaf, typename "in a types file", unlinked section ref
```
