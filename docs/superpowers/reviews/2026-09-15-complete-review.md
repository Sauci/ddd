# Complete review of DDD, 2026-09-15

A whole-tool review before the official release, run as a sequence of independent passes,
each by one reviewer reading the material fresh, followed by a verification of every finding
by a second reviewer and a sweep for what the passes missed. It follows the review of
2026-09-08 (branch `review/complete-review-2026-09-08`), whose findings were fixed in two
tiers between 2026-09-08 and 2026-09-10; each pass here records the status of that review's
findings in its area, so that what is still open is listed once, here.

The passes, in order:

1. `SPEC.md` on its own: contradictions, gaps, ambiguities, requirement words, undefined
   terms, and the sentences the features since 0.9.0 added.
2. File formats: `SPEC.md` section 3.1 to 3.10 against the published schemas, the pydantic
   models, the loader and the file format documentation.
3. Consistency checks and comparison: `SPEC.md` section 4 against `analysis.py`,
   `compare.py`, `identity.py`, `diagnostics.py` and their documentation.
4. Generated artefacts, address information and the dictionary: `SPEC.md` sections 5 and 6
   against `ir.py`, the backends, `build_info.py`, the shipped templates and their
   documentation; the generated c compiled under the CI flag set.
5. Tool interface: `SPEC.md` sections 3.11, 7 and 7.1 against `cli.py`, `plugins.py`,
   `Ddd.cmake`, the pre-commit hook and their documentation.
6. Editor integration: `SPEC.md` section 7.2 against the language server, the extension and
   their documentation, with the server's code reviewed line by line.
7. The remaining documentation and the repository: getting started, concept, FAQ, data
   contracts, developer documentation, README, CHANGELOG, examples, docker, CI, packaging
   and release readiness.
8. Code review of the core, part A: `models/`, `loading.py`, `diagnostics.py`, `identity.py`.
9. Code review of the core, part B: `analysis.py`, `ir.py`, `compare.py`.
10. Code review of the periphery: `cli.py`, `plugins.py`, the backends, `build_info.py`, the
    cmake module.
11. The test suite: what it pins, what it leaves open, and how it would fail; run as two
    halves, 11a for the fixtures and the core and format tests, 11b for the command line,
    server, plugin, backend, build and documentation-guard tests.

After the passes, every Critical, Important and Minor finding was handed to a verifier that
had not written it, with the verdict CONFIRMED (trigger and outcome reproduced or read off
the line), PLAUSIBLE (the mechanism is real, the trigger uncertain) or REFUTED (the code does
not say that, or a guard elsewhere catches it); refuted candidates are listed at the end of
each pass so that the next review does not raise them again. Two sweeps then read the code
and the documents again with the verified list in hand, looking only for what was missed.

Line numbers refer to master at `6e9e99f` unless a pass says otherwise.

**Status: in progress.** Passes are appended as they complete and pushed; the summary is
written last.

## Baseline

On master at `6e9e99f`, Windows 11, Python 3.13, the project's own venv:

- `python -m pytest`: 2284 passed, 1 failed, coverage 100.00 % of lines and branches, in
  2 min 22 s. The failure is
  `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`,
  which needs a Windows privilege the shell does not hold; the same test passes in CI.
- `ruff check .`, `ruff format --check .` (81 files), `mypy` (strict, 46 source files):
  clean.
- `sphinx-build -W --keep-going -b html docs`: clean, with graphviz and plantuml available.

## Summary

To be written when every pass, the verification and the sweeps are done.

## Pass 1: SPEC.md, internal quality

### Scope covered

- `C:/git/ac11/ddd/SPEC.md`, all 2075 lines, read in order with line numbers in eight chunks
  (1-260, 260-520, 520-780, 780-1040, 1040-1300, 1300-1560, 1560-1820, 1820-2075). Line numbers
  below are those of the current tree (`6e9e99f`).
- Mechanical checks (python, kept under `scratchpad/pass-1/`): the table of contents against the
  38 headings; every `[section N](#anchor)` against the heading anchors, and the section number in
  the link text against the heading it points at; every backticked identifier of the check grammar
  against `ddd checks`; the 83 bold requirement words and every plain `shall`, `must`, `should`,
  `may` and `can`.
- The tool, from the venv: `ddd --help`, `ddd checks` (text and JSON), `ddd artefacts` (text and
  JSON), the `--help` of all 14 subcommands and of `generate c|a2l|all`; `ddd dump` of
  `examples/demo` (top-level and record keys against 5.3) and `ddd list --format json` of
  `examples/structures`; eleven small projects under `scratchpad/pass-1/exp*/`, built to settle
  ambiguities: constant literals through `dump`, the C and the A2L (expA); `dump`, `dump -o` and
  `generate --dictionary` under an error finding (expB); `--renames` on an array-of-structures
  instance (expC); a string `init` as list and as text (expD); a structure member naming a zero
  constant (expE); wildcard order of mixed-case file names (expH); `compare --plugin` beside a
  description baseline (`examples/layout`); a revalued enumerator between deliveries (expK).
- `git diff v0.9.0 HEAD -- SPEC.md` to focus on the material added since the release;
  `CHANGELOG.md` "Unreleased"; the previous review's pass 1 (`previous-review.md:136-694`); the
  plans `docs/superpowers/plans/2026-09-08-spec-catch-up.md` and `2026-09-09-docs-corrections.md`;
  one grep in `cmake/Ddd.cmake` for the dictionary's file name; the test names of
  `tests/test_documentation.py`. No other code was read.

### Strengths

- Every one of the 69 identifiers `ddd checks` registers is named in the spec, and the spec names
  no check the tool lacks; the ten `(project)` checks (`SPEC.md:1159-1162`), the eight fixed ones
  (`SPEC.md:1314-1316`) and the thirteen `(comparison)` ones of 4.1 are exactly the registry's
  sets. `dimension-value` is rightly not among the ten (`SPEC.md:972-973`; the tool marks it so).
- Section 7 names all 14 subcommands of `ddd --help` and every option their `--help` prints, and
  `ddd artefacts` answers as `SPEC.md:1807-1813` says.
- The 38 headings are the table of contents in order; every cross-reference resolves, and its
  section number matches the heading it points at.
- The requirement words are bold wherever they are used: no plain `shall`, `must` or `should`
  occurs anywhere, and every bold `must`/`must not` on description data names its check.
- 5.3's fourteen top-level keys are exactly those of a format-8 dump, and its object, instance,
  leaf and component records list the keys the dump carries.
- All six open questions of the previous review are settled by one sentence each, and its
  Critical finding and seventeen of its eighteen Important findings are fixed (status table).
- The material added since 0.9.0 is consistent with the sections it touches: strings in 3.3
  (`SPEC.md:325-331`, `428-434`), 3.4 (`620-630`), 3.7 (`803-805`, `825-827`), 4 (`1177-1181`,
  `1287-1289`), 5.1 (`1561-1563`) and 5.2 (`1622-1628`, `1713-1716`); `--standalone` on the three
  commands in 4 (`1162-1165`) and 7 (`1848-1854`); `<stem>_ddd_list` (`1970-1971`);
  `--dictionary` in 7 (`1799-1802`) and 7.1 (`1973-1977`); the empty address map in 4
  (`1349-1350`) and 7.1 (`1945-1946`).

### Issues

#### Critical

None.

#### Important

1. **The `--renames` id of a member of an array-of-structures instance is not spelled as 4.1
   says** (`SPEC.md:1410-1411`: "its `id` being the instance's `id` followed by `.` and the member
   path"). Trigger: an instance `Inst` of a structure with `"dimensions": [2]` and id
   `abcdefghjkmn`, renamed `Inst2` -> the file carries `"id": "abcdefghjkmn[0].a"`, `"from":
   "Inst[0].a"` (no `.` before `[`), and `"id": "pqrstvwxyz23.a"` for a member of a scalar
   instance. A migration script written from the spec keys on `abcdefghjkmn.[0].a` and migrates
   nothing. Evidence: `ddd compare base/proj.ddd.json cand/proj.ddd.json --renames r.json` in
   `scratchpad/pass-1/expC/`, `r.json` as quoted. Fix: "followed by the member's path below the
   instance as the access path spells it: `.latest` for a member, `[2].raw` for a member of the
   third element".

2. **"Written the way `generate` writes an artefact" and "when the project does not resolve" give
   `ddd dump -o` under an error finding two readings, and the tool takes the one the words argue
   against** (`SPEC.md:1814-1817`; `generate`: `SPEC.md:1887-1889` "with error findings writes
   nothing"). "Resolve" is said of declarations, shapes, rasters and paths, never of a project, so
   a reader takes "does not resolve" as "has error findings" and expects the file left alone.
   Trigger: a project with one `definition-mismatch`; `ddd dump proj.ddd.json -o d.json` over an
   existing `d.json` -> `wrote d.json (updated)`, exit 1 (and to stdout the full dictionary, exit
   1); `ddd generate c proj.ddd.json -o out -t ... --dictionary out/d.json` on the same project ->
   nothing written, exit 1 (`scratchpad/pass-1/expB/`). Two commands that write "the text `ddd
   dump` prints" behave oppositely on one input and the spec cannot tell a reader which. Fix (the
   behaviour is the maintainer's decision; only the sentence changes): "left as it was only when
   the root cannot be read; findings, errors included, stop neither `dump` nor `dump -o`, unlike
   `generate`, so a build archiving a delivery with `dump -o` gates on the exit code".

3. **The concept table still defines a constant as a named integer** (`SPEC.md:158`: "a named
   integer declared by a constants file") while 3.9 declares "named numbers" (`SPEC.md:927`), "a
   whole number of either sign ... or a finite number written with a fraction"
   (`SPEC.md:953-954`), and 4 says "A constant may hold any number" (`SPEC.md:1276`). Trigger:
   `{"name": "GAIN", "value": 2.5}` - refused by an implementer of section 2, accepted by 3.9 and
   by the tool (`ddd dump` shows `"value": 2.5`, `scratchpad/pass-1/expA/`). Fix: "a named number
   declared by a constants file or inside a component; a shape names one holding a whole number of
   at least 1 where it would state a size".

4. **5.1 promises the same bytes on any machine while 3.1 and 5.1 order wildcard includes as the
   platform compares paths, and that order is in the output** (`SPEC.md:1604-1607` "the same
   project generates the same bytes on any machine"; `SPEC.md:255-258` "ordered again as the
   platform compares them"; `SPEC.md:1612` "only file paths order as the platform compares them";
   `SPEC.md:1605` "components keep the include order of the project"; `SPEC.md:1652-1653` `GROUP`s
   in component order). Trigger: `"includes": ["comps/*.ddd.json"]` matching `Zeta.ddd.json` and
   `alpha.ddd.json`. On this Windows tree `ddd sources` lists `alpha` first and the A2L has `GROUP
   Alpha` before `GROUP Zeta` (`scratchpad/pass-1/expH/`); by the spec's own rule a code-point
   platform orders `Zeta` first (`sorted()` gives `['Zeta.ddd.json', 'alpha.ddd.json']`), so the
   definitions file and the A2L of one project differ between a Windows and a Linux build
   (unconfirmed on Linux - the same project generated there would confirm it). Fix: order
   wildcard matches by code point of the resolved path, as names are ordered, or narrow the
   promise to machines that order paths alike.

5. **Whether a delivery comparison compares an enum's enumerators is unstated, and the in-project
   rule a reader would apply says the opposite of what the tool does** (`SPEC.md:1422-1425`
   `changed-interface`: "kind, datatype, unit, scaling, shape, referenced objects or locality";
   `SPEC.md:1202-1203`: conversions "compared by kind and parameters, an enum by its name -
   `enum-conflict` compares the enumerators"; 4.1 lists no `enum-conflict`). Trigger: baseline
   `{"OFF": 0, "ON": 1}`, candidate `{"OFF": 0, "ON": 2}` under the same `Mode_t` and datatype. A
   reader of section 4 reports nothing and prints "can replace"; the tool prints
   `error[changed-interface]: 'Mode' is not the same object any more (conversion: enum(Mode_t:
   OFF=0, ON=2) != enum(Mode_t: OFF=0, ON=1))` and "cannot replace" (`scratchpad/pass-1/expK/`),
   which the changelog's "A delivery comparison spells an enum change out" describes. Fix: in
   `changed-interface`, "scaling - the conversion by kind and parameters, an enum by its name and
   its ordered enumerators, whose descriptions are not compared (`SPEC.md:1464-1465`)".

#### Minor

1. **A binding `may` set plain in the new `dimension-value` entry** (`SPEC.md:1276`: "A constant
   may hold any number"). It is the permission 3.9 grants, and 1.1 sets the words in bold
   "wherever they bind" (`SPEC.md:77-78`). Fix: `**may**`.

2. **Requirement words bound on actors other than DDD and the data, one of them new** (carried
   over from the previous Minor 1): `SPEC.md:98` (the project's objects "**shall** be defined ...
   by code DDD renders"), `SPEC.md:463` ("**should** be confirmed on the toolchain", advice to the
   user), `SPEC.md:730` ("A build **shall** therefore write a record"), `SPEC.md:1734` (new with
   5.3: "a reader **shall** refuse a higher number" - a project's own backend is a reader too),
   `SPEC.md:2069-2071` (the extension "**shall** do no more"). 1.1 binds **shall** to DDD alone
   (`SPEC.md:69`). Fix: extend 1.1 ("**shall** also binds what DDD ships - the CMake module, the
   extension - and a reader of the dictionary") or unbold and rephrase.

3. **A `must` with no reportable violation** (`SPEC.md:621-622`: "`kind` **must** be stated,
   because the conversion has no key of its own to be inferred from"). A string without `kind` is
   the valid identity `{}` (`SPEC.md:631-634`), so no check can carry the violation 1.1 promises
   (`SPEC.md:70`). Fix: state it as a fact: "a conversion is a string only when `kind` says so;
   `{}` stays the identity".

4. **"The outputs carry the literal as written" is not what reaches them** (`SPEC.md:955-956`).
   Trigger: `"value": 2.50` and `"value": 1e3` -> `#define GAIN 2.5`, `#define BIG 1000.0`,
   `SYSTEM_CONSTANT "GAIN" "2.5"`, `SYSTEM_CONSTANT "BIG" "1000.0"` (`scratchpad/pass-1/expA/`);
   and "written with a fraction" (`SPEC.md:954`) does not classify `1e3`, which the tool treats as
   not whole, so a shape naming a constant `1e1` is `dimension-value`. Fix: "carry the number in
   its shortest round-trip spelling - a whole number without a decimal point, any other with one -
   so `2.50` reaches the C as `2.5` and `1e3`, which counts as written with a fraction, as
   `1000.0`".

5. **A `dimension-value` at a structure member makes the type unusable, which 3.9 does not say and
   `incomplete-project`'s enumeration omits** (`SPEC.md:974-976`: "both findings are then reported
   at the member", nothing about the type; `SPEC.md:1369-1371`: "a variable of a type whose cycle,
   unknown member type or unknown member constant was silenced"). Trigger: member `v` with
   `"dimensions": ["ZERO"]`, `ZERO` = 0, a declaration `Obj` naming the type, `-W
   dimension-value=ignore` -> `Obj` is absent from `ddd list` and `incomplete-project` says "the
   dimension-value that says why the type is unusable is not reported"
   (`scratchpad/pass-1/expE/`). Fix: in 3.9, "at a member either finding makes the type unusable,
   as a member naming an unknown type does, and every declaration naming it is dropped"; add the
   case to `incomplete-project`.

6. **A string `init` in the dictionary and in a comparison is unspecified** (`SPEC.md:1745`: 5.3
   lists `init` with no text form - the dump carries `"init": "Hi"`; `SPEC.md:1451`:
   `changed-storage` "the initial value ... changed", without saying whether `init` compares as
   bytes or as spelled). Trigger: baseline `"init": [72, 105, 0, 0]`, candidate `"init": "Hi"` on
   a `uint8[4]` string -> `warning[changed-storage]: 'Label': init: "Hi" != (72, 105, 0, 0)`, an
   error under `--strict` (`scratchpad/pass-1/expD/`): the same bytes, and the migration the
   feature invites. Fix: say in 5.3 that a string's `init` is its text when stated so, and in 4.1
   which of the two comparisons is meant (open question 1).

7. **Section 7 refuses `--plugin` "beside a description"; 3.11 and the tool refuse it beside a
   project candidate only** (`SPEC.md:1877-1878` against `SPEC.md:1136-1138`). Trigger, on
   `examples/layout`: `ddd compare project.ddd.json layout.json --plugin ddd_layout.py`
   (description baseline, dumped candidate) -> accepted, exit 0, no `missing-plugin`; the sides
   swapped -> "ddd: --plugin names the plugins of an archived dictionary; a project description
   names its own", exit 2. Fix: "a `--plugin` refused beside a project candidate".

8. **`<NAME>.dictionary.json` where `NAME` is ignored** (`SPEC.md:1974` against
   `SPEC.md:1937-1938` "`NAME` is then ignored in favour of the name written inside the file").
   Beside `PROJECT` the module names the dictionary after the project name inside the file, as it
   names the A2L (`cmake/Ddd.cmake:428`, `:445`). Fix: "as `<project name>.dictionary.json`, the
   name the A2L takes".

9. **Terms defined once and used otherwise, or not defined.**
   - "instance" is "a declaration naming a structure type" (`SPEC.md:150`), but the dictionary's
     instance is the resolved object with `owner` and `consumers` (`SPEC.md:1748-1750`), the way
     "data object" is "the subject of a declaration" (`SPEC.md:149`); `missing-id`'s "a producing
     declaration or instance" (`SPEC.md:1377`) is now redundant, and `duplicate-id`'s "two data
     objects" (`SPEC.md:1249`) leaves two instances sharing an id out by the letter of 149-150.
   - "storage category" (`SPEC.md:1629`, `1676`) is still undefined (values against axis points).
   - "vocabulary file" (`SPEC.md:1907`, `1913-1914`): which kinds, and whether a types file is one
     - "registers descriptions, component and vocabulary files alike" leaves a types file in
     neither class.
   - "standalone" means a file outside a component (`SPEC.md:289-291`) and a component checked
     alone (`SPEC.md:1849`).
   - "structured variable" (`SPEC.md:1043`, `1132`) beside "structured object" and "instance".
   - "baseline" and "candidate" are used from `SPEC.md:981` and `1136` on and defined only by
     use at `SPEC.md:1393-1398`; "delivery" (`SPEC.md:164`) is "the archived data dictionary"
     while 4.1 accepts a description on either side (`SPEC.md:1391-1392`).
   - "member path" (`SPEC.md:1411`) beside the defined "access path" (`SPEC.md:159`).
   - Drift carried over: "variable" for data object (15 lines, e.g. `SPEC.md:1804`), "scaling"
     for conversion (`SPEC.md:1422`), "a2l" in prose (`SPEC.md:958`, `998-1033`, `1271-1280`,
     `1952`) beside "A2L".

10. **Public contracts stated by name and not by shape.** `ddd list --format json`
    (`SPEC.md:1803-1806`): an object entry carries `name`, a leaf entry `path`
    (`examples/structures`: seven of nine entries have `"name": null`), and that leaves are rows
    of the table at all is unstated; `ddd checks --format json` (`SPEC.md:1842`) names two of its
    six keys (`check`, `default_severity`, `description`, `overridable` unnamed);
    `ddd artefacts --format json` carries `artefacts` of `name`/`kind` and
    `plugins_without_artefact` where the spec says "in a note" (`SPEC.md:1808-1809`); the JSON key
    under which `generate` and `dump -o` report the files written (`SPEC.md:1867`, `1870-1871`);
    in 5.3 the keys of `references` (`axis`, `x_axis`, `y_axis`, `input`), what "folded into one"
    means for a leaf's `export` (`SPEC.md:1753`), and the `owner` of an object no component owns;
    the build record's `image` "empty when no target is named" (`SPEC.md:747`: `""` or `null`);
    the CMake floor of the collected mode ("its stated floor", `SPEC.md:1927-1928`, is stated
    nowhere - 3.30 is stated for `ddd_add_component` only, `SPEC.md:1911`).

11. **Concept-table rows that predate later sections.** "declared type" and "constant" "declared
    by a types file" / "a constants file" (`SPEC.md:157-158`) omit 3.2's in-component declarations
    (`SPEC.md:281-285`); "finding ... findings reported as errors fail the run" (`SPEC.md:162`)
    against `ddd sources` and `ddd artefacts` exiting 0 (`SPEC.md:1884-1887`); the scope table's
    `input` row, "another component has to produce it" (`SPEC.md:170`), is the one row naming no
    check (`missing-producer`).

12. **Small inconsistencies.** The name-cap subject list (`SPEC.md:396-397`) omits constants,
    which `SPEC.md:948-949` puts under it; `include-depth` is listed twice in section 4
    (`SPEC.md:1314` and `1317`); the parenthetical "(`NO_COMPU_METHOD`: an identity without a
    unit)" (`SPEC.md:1691-1692`) now also covers a string (`SPEC.md:1637`); "one object per
    member" (`SPEC.md:592-593`) against "one object per value-holding member"
    (`SPEC.md:1706-1707`) and a `bits` member that holds a value and reaches no A2L
    (`SPEC.md:1722`); a structured declaration stating `format` or `display_identifier`
    (`SPEC.md:881-882`) is still neither `schema` nor ignored by the text; `duplicate-type` still
    splits the same-file case off as `schema` (`SPEC.md:837-838`) unlike the four parallel
    vocabulary checks.

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| C1 | seeded empty map + `STRICT` blocks the first build | fixed | `SPEC.md:1349-1350`, `SPEC.md:1945-1946` |
| I1 | `--standalone` denied; per-component target missing | fixed | `SPEC.md:1848-1854`, `SPEC.md:1912-1914` |
| I2 | "instance" and "leaf" undefined | fixed (defined); usage drift remains, Minor 9 | `SPEC.md:150-151` |
| I3 | "storage" in three senses | fixed | `SPEC.md:489-490`, `570`, `819-820`, `857` |
| I4 | `boolean` defaults to `%8.3` by the letter | fixed | `SPEC.md:1688-1690` |
| I5 | `COMPU_METHOD` sharing key | fixed | `SPEC.md:1633-1637`, `1678-1683` |
| I6 | verdict criterion unstated | fixed | `SPEC.md:1398-1402` |
| I7 | `--renames` keys unnamed | partly fixed: keys named, member spelling wrong (Important 1) | `SPEC.md:1408-1411` |
| I8 | dictionary described nowhere | fixed | `SPEC.md:1730-1756` |
| I9 | `typename` compared as spelled or resolved | fixed | `SPEC.md:505-509`, `1504-1506` |
| I10 | alignment need undefined | fixed | `SPEC.md:703-707` |
| I11 | dangling references unspecified | fixed | `SPEC.md:1290-1296` |
| I12 | plugin name grammar and reserved names | fixed | `SPEC.md:1077-1082` |
| I13 | project block for an unloaded plugin | fixed | `SPEC.md:1090-1091` |
| I14 | listing orders; `sources`/`artefacts` exit | fixed (JSON shapes remain, Minor 10) | `SPEC.md:1803-1813`, `1829`, `1843-1844`, `1884-1887` |
| I15 | A2L file name and `-o` | fixed | `SPEC.md:1660-1661`, `1951` |
| I16 | `reserved-identifier` subjects | fixed | `SPEC.md:1303-1305` |
| I17 | CMake library names | fixed | `SPEC.md:1916-1919` |
| I18 | baseline's plugins | fixed | `SPEC.md:1471-1474` |
| M1-M21 | minors, checked in bulk | M1 (Minor 2), M3 (Minor 9), M18's structured `format` and M21 (Minor 12), M20's wording (`SPEC.md:1405`, `1443-1444`, `592-593`) still open; the other sixteen fixed | Minor 2, 9, 12 |

The six open questions, each settled by the current text:

1. A reference into another component's `local` object: settled - `SPEC.md:445-447` "It is a use
   of the object all the same, so a reference into another component's `local` object is
   `local-conflict`" (and `SPEC.md:172`, `1197-1201`).
2. A type name compared as spelled: settled the other way - `SPEC.md:505-506` "A `typename`
   compares as what it fixes - the `datatype`, `unit`, `conversion` and `limits` of the scalar
   type"; `SPEC.md:1504-1506` for a delivery comparison.
3. The baseline's own plugins: settled - `SPEC.md:1471-1472` "Each side given as a description
   runs the plugins it names for its own analysis".
4. A project block for an unloaded plugin: settled - `SPEC.md:1090-1091` "A project block keyed
   by a name no loaded plugin has is `unknown-extension`, as on a definition."
5. "Can replace": settled - `SPEC.md:1398-1400` "exactly when no finding of the run is reported
   as an error - the candidate's own, the baseline's carried ones and the comparison's alike".
6. The names `reserved-identifier` polices: settled - `SPEC.md:1303-1305` "the names that reach
   the generated C: projects, components, data objects, declared types, structure members, enums,
   enumerators and constants; not to `display_identifier`".

### Open questions

1. Does `changed-storage` compare a string `init` as bytes or as spelled (Minor 6)? As bytes, a
   list-to-text migration is silent and 4.1 says so; as spelled, 4.1 says the spelling counts, as
   3.9 does for a dimension, and the migration knowingly costs one warning per string.
2. Is the platform order of wildcard matches intended (Important 4)? Code point makes the output
   the same on every machine and changes the loader's sort key; platform order keeps the loader
   and narrows 5.1's promise.
3. Where do enumerator changes belong in 4.1 (Important 5): inside `changed-interface`, as the
   tool reports them, or under a comparison-side identifier of their own? The answer changes
   4.1's list and, in the second case, the registry.
4. Is an exponent spelling such as `1e3` a whole number or a fraction (Minor 4)? Today it is a
   fraction, so a shape naming a constant `1e1` is `dimension-value`; 3.9's rule should say which.

### Test gaps

`tests/test_documentation.py` pins that every check is named in the spec, that the ten
project-wide checks are counted and named as the registry counts them, that the command list is
what section 7 promises, and the cross-references. Judged by the test names, it does not pin:

- that the thirteen checks 4.1 lists are exactly the registry's `comparison` ones and the eight of
  `SPEC.md:1314-1316` exactly its unrelaxable ones (the comparison test at
  `tests/test_documentation.py:208` covers the reference page, not the spec);
- that the format number 5.3 and section 7 state (`SPEC.md:1733`, `1898`) is the code's dictionary
  format constant (`tests/test_documentation.py`);
- the `--renames` `id` of a member of an array-of-structures instance, `<id>[0].a`
  (`tests/test_compare.py`, or wherever `--renames` is tested; Important 1);
- `ddd dump -o` under an error finding writing the file and exiting 1, beside `generate
  --dictionary` writing nothing on the same project (`tests/test_cli.py`; Important 2);
- a wildcard include whose matches differ only in case class, ordered the same way on every
  platform, once open question 2 is decided (`tests/test_loading.py`; Important 4).

The feature test files were not read; a scenario above may already be pinned in one of them.

### Assessment

The specification has absorbed the previous review well: its Critical finding and seventeen of
eighteen Important ones are fixed, all six open questions are settled in the text, and the
material added since 0.9.0 - strings, constants holding any number, `dump -o`, `--dictionary`,
`--standalone` on three commands, the list target - is consistent with the sections it touches
and with what the tool prints. What remains is of two kinds. Four sentences say something the
tool does not do or that another sentence contradicts: the `--renames` spelling for array
members, the "written the way `generate` writes" reading of `dump -o`, the concept table's "named
integer", and the "same bytes on any machine" promise beside platform-ordered includes. And a
handful of decisions taken in code are not yet written down: enumerators in `changed-interface`,
a string `init` in the dictionary and in a comparison, a member's `dimension-value` making its
type unusable, the normalised constant literal. Each is a sentence, not a redesign; Important 4
and open question 1 are the two the maintainer has to decide rather than merely record.

### Verification

Every candidate of this pass was handed to a second reviewer (group A): 17 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P1-I1 | Important | CONFIRMED | Important | ran `ddd compare base/proj.ddd.json cand/proj.ddd.json --renames r.json` (copy of expC): `"id": "abcdefghjkmn[0].a"` for the array member, `"pqrstvwxyz23.a"` for the scalar one; `SPEC.md:1410-1411` "the instance's `id` followed by `.` and the member path" |
| P1-I2 | Important | CONFIRMED | Important | copy of expB, one `definition-mismatch`: `ddd dump proj.ddd.json -o d.json` -> `wrote d.json (updated)`, exit 1; `ddd generate c ... --dictionary outB/d.json` on the same project -> nothing written, exit 1; a missing root leaves the file absent; `SPEC.md:1814-1817` "written the way `generate` writes an artefact ... left as it was when the project does not resolve" |
| P1-I3 | Important | CONFIRMED | Minor | `SPEC.md:158` "a named integer declared by a constants file"; `:927` "named numbers", `:953-954`, `:1276`; `ddd dump` of expA carries `{'name': 'GAIN', 'value': 2.5}` |
| P1-I4 | Important | CONFIRMED | Important | `loading.py:1006-1010` sorts `Path` objects; here `ddd sources`, the dump's `components` (`['Alpha', 'Zeta']`) and the A2L (`GROUP Alpha` at line 35, `GROUP Zeta` at 43) put `alpha` first; `sorted()` of the same names as `PurePosixPath` gives `Zeta, _under, alpha`; `SPEC.md:1607` "the same bytes on any machine" vs `:1612` "only file paths order as the platform compares them" |
| P1-I5 | Important | CONFIRMED | Important | copy of expK: `error[changed-interface]: 'Mode' is not the same object any more (conversion: enum(Mode_t: OFF=0, ON=2) != enum(Mode_t: OFF=0, ON=1))`, "cannot replace", exit 1; `SPEC.md:1202-1203` "an enum by its name - `enum-conflict` compares the enumerators"; 4.1 (`:1422-1425`) names no enumerator rule |
| P1-M1 | Minor | CONFIRMED | Minor | `SPEC.md:1276` "A constant may hold any number" set plain; `:77-78` "set in bold wherever they bind" |
| P1-M2 | Minor | CONFIRMED | Minor | `SPEC.md:98` "**shall** be defined and declared by code DDD renders" (binds the project's objects), `:730` "A build **shall**", `:1734` "a reader **shall** refuse", `:2069` "An editor extension **shall**", `:463` "**should** be confirmed on the toolchain"; `:69` "a binding requirement on DDD" |
| P1-M3 | Minor | CONFIRMED | Minor | `SPEC.md:621-622` "`kind` **must** be stated"; `:631-634` "one stating nothing, `{}`, is the identity"; `:70` a **must** violation "is reported under the named check" - none is named and `{}` is valid |
| P1-M4 | Minor | CONFIRMED | Minor | expA `generate all`: `#define BIG 1000.0`, `#define GAIN 2.5`, `SYSTEM_CONSTANT "BIG" "1000.0"` from `1e3` and `2.50`; `SPEC.md:955-956` "the outputs carry the literal as written"; primary of the pair with P2-M4 |
| P1-M5 | Minor | CONFIRMED | Minor | expE with `-W dimension-value=ignore`: `Obj` absent from `ddd list`, `info[incomplete-project]: ... it names the type 'T_t', and the dimension-value that says why the type is unusable is not reported`; `SPEC.md:1370-1371` lists "cycle, unknown member type or unknown member constant" only, `:974-976` says nothing of the type |
| P1-M6 | Minor | CONFIRMED | Minor | expD: `warning[changed-storage]: 'Label': init: "Hi" != (72, 105, 0, 0)`, "can replace"; under `--strict` an error and "cannot replace"; `SPEC.md:1745` lists `init` with no text form, `:1451` "the initial value ... changed" |
| P1-M7 | Minor | CONFIRMED | Minor | on `examples/layout`: `ddd compare project.ddd.json layout.json --plugin ../plugins/ddd_layout.py` -> "layout.json can replace project.ddd.json", exit 0; sides swapped -> "ddd: --plugin names the plugins of an archived dictionary; a project description names its own", exit 2; `SPEC.md:1877-1878` "a `--plugin` refused beside a description" |
| P1-M8 | Minor | CONFIRMED | Minor | `SPEC.md:1974` "`<NAME>.dictionary.json`" against `:1937-1938`; `Ddd.cmake:428` "NAME is ignored with PROJECT - the a2l and the dictionary are named after the project name inside", `:447` replaces `arg_NAME`, `:547` names the file from it |
| P1-M9 | Minor | CONFIRMED | Minor | "storage category" occurs at `SPEC.md:1629`, `:1676` only; "vocabulary file" at `:1907`, `:1914` only; "member path(s)" at `:1411`, `:1605`, `:1652`, `:1720` beside the defined "access path" (`:159`); "instance" `:150` vs `:1748-1750`; "standalone" `:289-291` vs `:1849`; "delivery" `:164` vs `:1391-1392` |
| P1-M10 | Minor | CONFIRMED | Minor | `ddd list --format json` on `examples/structures`: 7 of 9 `variables` carry `path` and no `name` key; `ddd checks --format json` rows carry 6 keys where `:1842` names 2; `artefacts` JSON carries `plugins_without_artefact`; `generate` reports under `generated`; the build record writes `"image": ""` |
| P1-M11 | Minor | CONFIRMED | Minor | `SPEC.md:157-158` "declared by a types file" / "a constants file" vs `:281-285`; `:162` "findings reported as errors fail the run" vs `:1884-1886` "exit 0 whatever the findings"; `:170` is the one scope row naming no check |
| P1-M12 | Minor | CONFIRMED | Minor | `:396-397` omits constants, `:948-949` applies the cap; `include-depth` at `:1314` and `:1317`; `:1691-1692` vs `:1637`; `:592-593` vs `:1706-1707` and `:1722`; a structured declaration with `a2l.format`/`display_identifier` is accepted silently, the dump's instance record carries both and the A2L writes neither; `:837-838` vs `:1230-1236` |

Notes of the verifier:

- **P1-I3, regraded to Minor.** The row is stale wording contradicted by the normative 3.9
(`:927`, `:953-954`) and by section 4 (`:1276`) in the same document, and the tool follows 3.9. A
reader is told a feature does not exist; nobody is led to a wrong verdict or output, which under
the brief is a small inconsistency. It is the same stale word as P2-M1 in the README: P1-I3 is
primary, P2-M1 its copy, two files and one fix.

## Pass 2: the file formats (SPEC.md section 3.1 to 3.10)

### Scope covered

Read in full, with line numbers, on the review tree (`46a8807`, whose sources are `master` at
`6e9e99f`): `SPEC.md` lines 179-1045 (section 3 intro, 3.1-3.10); the eight published schemas
`schemas/ddd_*.schema.json` (component 2127 lines, dictionary only where it shares definitions
with the others); every file of `src/ddd/models/` (`__init__`, `common`, `component`,
`constants`, `conversion`, `objects`, `project`, `rasters`, `reserved`, `schema`, `sections`,
`types`, `units`); `src/ddd/loading.py` whole; the analysis the format rules delegate to
(`src/ddd/analysis.py` 85-160, 880-1140, 1530-1650, 1850-1910, 2040-2170, 2280-2520,
3090-3240); `src/ddd/ir.py` 160-190 and 560-600; `src/ddd/backends/c/model.py` 180-200; all ten
pages of `docs/file_formats/`; `docs/data_contracts.rst`; `README.md` 97-479; the schema tests
`tests/test_documentation.py` 831-1013 and 1379-1439; the outlines of `tests/test_loading.py`
and `tests/test_constants.py`; `previous-review.md` 695-963; `reports/pass-1.md`.

Ran, from the venv, everything kept under `scratchpad/pass-2/`: `ddd schema <kind>` for all
eight kinds and `ddd schema all`, diffed against `schemas/` (`schemas/`, `schemas_all/`); 252
commands over 190 probe files (`probes.py`, outputs in `results.txt`) and 63 more in a second
round (`probes2.py`, `results2.txt`): `ddd check --standalone` on component probes, `ddd check`
on project probes, `ddd dump`, `ddd list`, `ddd sources` and `ddd generate` where the resolved
form or the output mattered, and `jsonschema` (Draft 2020-12) over the published schemas for
forty documents to settle which side accepts what (`results2.txt`, block `R12`). Probe ids
`Lnn`/`Rnn` below refer to those files.

Pass 1's questions, settled from the code:

- Constants (pass 1 Important 3, Minor 4, open question 4): `src/ddd/models/constants.py:44-49`
  is `ConstantValue = Annotated[int, Field(strict=True, ge=-(2**63), le=2**64 - 1)] |
  Annotated[float, BeforeValidator(_refuse_whole_number), Field(strict=True,
  allow_inf_nan=False)]`, and `_refuse_whole_number` (`:31-41`) keeps an out-of-range `int` off
  the float arm. Nothing in the model classifies the spelling: the JSON parser does
  (`src/ddd/loading.py:575`, `json.loads`), which yields `int` for a literal without `.`, `e`
  or `E` and `float` otherwise, so `2` is whole and `2.0`, `2.50`, `1e3`, `1E3`, `-0.0` are
  fractional. No normalisation happens in the model either; the outputs render the Python
  object with `str()` (`src/ddd/backends/a2l/templates/project.a2l.jinja:26`
  `SYSTEM_CONSTANT "{{ constant.name }}" "{{ constant.value }}"`, and
  `src/ddd/backends/c/model.py:192` `value: int | float` for the C templates), which is why
  `2.50` reaches both as `2.5`, `1e3` as `1000.0`, `1e21` as `1e+21`, `0.10` as `0.1` and `1.0`
  as `1.0` (probe L14c, `ddd_types.h` and `P.a2l`). A constant `1e1` named as a dimension is
  `dimension-value` "whose value is 10.0" (L14c), because `analysis.py:92-99` `_is_length`
  asks `isinstance(value, int)`.
- Wildcard order (pass 1 Important 4, open question 2): `src/ddd/loading.py:1006-1010`
  `matches = sorted(resolved for match in found if match.is_file() and (resolved :=
  _resolve(match)) not in excluded)` sorts `Path` objects. A `WindowsPath` orders by its
  case-folded string, a `PosixPath` by the raw string. The case-mixed set `Zeta.ddd.json`,
  `_under.ddd.json`, `alpha.ddd.json` (L43) loads as `_under, alpha, Zeta` here (`ddd sources`,
  the `PRODUCER` order of `ddd list` and the `components` of the dump all show it); a code-point
  platform sorts the same three `Zeta, _under, alpha` (checked with `PurePosixPath`). So the two
  platforms differ twice, on case and on where `_` (0x5F, between the cases) falls.
- The name cap on constants (pass 1 Minor 12): `constants.py:65` `name: Identifier`, and
  `Identifier` (`common.py:52-55`) carries `max_length=IDENTIFIER_MAX_LENGTH` (128); L22i
  refuses a 129-character constant name and accepts 128. The cap applies; only the spec's list
  at `SPEC.md:394-397` omits constants.
- `duplicate-type` within one file (pass 1 Minor 12): `types.py:500-513`
  `check_distinct_type_names` raises `ValueError`, reported as `schema` "type 'A_t' is already
  declared in this file" (L42a for a types file, L42c for a component's `types`); across files
  or homes it is `duplicate-type` with a note (L42b). Units, sections, rasters and constants go
  through the registry in both cases (`loading.py:713-736` `_register`), so the same file twice
  is `duplicate-unit`/`duplicate-constant` (L38b, L42d, L42e). The asymmetry is real and is
  what `SPEC.md:837-838` says.
- "Vocabulary file" (pass 1 Minor 9): `loading.py:69-85` names all five include-only kinds in
  `_INCLUDE_ONLY_KINDS`, whose docstring reads "Why a vocabulary file is refused as the root,
  by kind", and `_load_vocabulary` (`:685-711`) loads all five, `types` included (`:738-754`).
  In the loader a types file is a vocabulary file.
- A member's `dimension-value` poisons its type (pass 1 Minor 5): `analysis.py:1539-1570`
  `_check_member_dimensions` records `self._poisoned_types.setdefault(entry.name,
  _Cause(check, reported, location))` for `unknown-constant` and `dimension-value` alike (R4
  shows the member finding at `types[0].members[0].dimensions[0]`).
- A string `init` in the dictionary (pass 1 Minor 6): `src/ddd/ir.py:186-188` "Raw initial
  value, nested to match `shape`, or the text of a string object", and the dump carries
  `"init": "abc"` (L34w). The comparison side is pass 3's.

### Strengths

- All eight schemas regenerate byte for byte from the models (`ddd schema <kind>` and
  `ddd schema all`, diffed against `schemas/`), and `tests/test_documentation.py:1389-1398`
  pins it for every kind of `ddd.cli._SCHEMA_MODELS` (`src/ddd/cli.py:1028-1037`), `dictionary`
  included.
- The reading rules of the section 3 intro hold in every case tried: BOM on the root and on an
  included file (L24a-b), UTF-16 and a latin-1 byte as `json-syntax` with the byte offset (L25b,
  R9), a raw NUL (L25c), `NaN`/`Infinity`/`-Infinity` anywhere, an `extensions` block included
  (L16a-d), a duplicate key at the top level, inside a definition, in an enumerator mapping and
  inside an `extensions` block (L17a-d), a top level that is a list, a number, a string, `null`
  or `true` (L27a-f), `$schema` as string, `null`, number, object, nested (L28a-e, L18t),
  unknown keys in every object of every format, `units` and `includes` on a component (L18a-v),
  `1e400` as `schema` "finite" wherever a number is read (L14a, R12_39), 64-bit bounds on every
  integer position (L15, L15b).
- `includes` does what 3.1 says: `..` in a literal and in a pattern, `**`, absolute literal and
  pattern, a directory as literal (`file-not-found`), a pattern matching only a directory or
  nothing or only the project itself (`include-empty`), one file under three spellings of its
  case loaded once, one file through two patterns and a literal loaded once, `[ab]?`, an
  unclosed `[`, a self-include and a mutual cycle (`include-cycle`), an included `.json`
  (`file-extension`, loading continues), `*.ddd.json` matching `A.DDD.JSON` (L29a-q).
- The string rules of 3.4 are enforced in all fifteen shapes tried, with the identifier the
  spec names: 2-D, `uint16`, `boolean`, unit, limits, `a2l.format`, parameter, axis, curve, a
  scalar string type named without dimensions, with a format or by a parameter, a member naming
  it without dimensions, an own 2-D member, a bits member (L34a-r, R3); init exactly the
  dimension, longer, a tab, non-ASCII, text on a non-string object all `init-invalid` (L34e-h,
  L21f, L34t), `""` and a list init accepted (L34s, L34j), and the C literal escapes `"` and
  `\` (L34i: `uint8_t V[8] = "a\"b\\c";`).
- The vocabularies behave as 3.5, 3.8, 3.9 and 3.10 say: nineteen `cycle` spellings sort
  exactly as the decade rule predicts (L36d), events bound 0..65535 and strict (L15b, L36e),
  `duplicate-raster` within and across files (R6), raster names of 8 and 9 characters (L36a),
  `raster-kind` and `consumer-raster` (L36b), sections refused for alignment 0, 3, `true`,
  `"4"`, a quote or a space in the name (L37a), `unknown-section`, `section-access` and
  `section-alignment` (R7), unit entries `""`, `5`, `null`, an object with an extra key,
  `duplicate-unit` in one file, `unknown-unit` on a scalar type and a member with the nearest
  spelling (L19o, L38a-c), constants of 0, negative, fractional and 2**63 accepted at the
  declaration and `dimension-value` where a shape names them, at `dimensions[i]`, `size` and a
  member (L35a, R4).
- Embedded types and constants resolve in a standalone component run and reach the listing
  (R5, R5b); the four consumer keys earn their four identifiers (R8); 128-character names are
  accepted and 129 refused on objects, components, projects, enums, enumerators, types, members,
  `display_identifier`, constants and the `axis`/`input`/`typename` references (L22a-j);
  reserved identifiers are reported on objects, enums, enumerators, components, projects, types,
  members and constants and not on `display_identifier` (L23a, R2).
- The five earlier Important findings on the descriptions and the published type-name pattern
  are fixed (status table); the previous review's twelve "spec gaps proven from code" are all
  written into the spec now except one (below).

### Issues

#### Critical

None found.

#### Important

1. **A quoted number nested in a list `init` is read as the number, which the spec and the
   model's own contract say it is not** (`src/ddd/models/objects.py:36`
   `type InitElement = Annotated[InitScalar | tuple[InitElement, ...],
   BeforeValidator(within_64_bits)]`). Trigger: `"dimensions": [2], "init": ["1", "2"]` on a
   `uint8` measurement -> `ddd check --standalone` reports nothing and `ddd dump` carries
   `"init": [1, 2]` (L02, L02b); `"init": ["a", "b"]` is refused (L34u), so only the
   numeric-looking strings slip through. `SPEC.md:433-434` says "a quoted number is text, not
   the number"; the type's docstring at `objects.py:36-42` says "What a list init holds:
   numbers, or lists of them, never text ... a string nested in a list is refused here, by the
   contract"; `objects.py:58-64` says the quoted-spelling question "is answered"; the published
   schema refuses it (`schemas/ddd_component.schema.json:845-872`, `InitElement` is `integer |
   boolean | number | array`; R12 row "init ['1', '2']": schema REFUSED, loader accepted). Only
   the whole init has a `str` arm (`objects.py:44-46`, `tests/test_models.py:842`); inside a
   list pydantic's lax `int` parses `"1"`. The reader is told one thing by the spec, the
   docstring and the editor, and the file means another - the exact "the file would say
   something its author did not write" that `objects.py:74-76` gives as the reason `Dimension`
   is strict. Fix: `Field(strict=True)` on the `int` and `float` arms of `InitScalar` (the
   `bool` arm already matches by exact type), so `["1"]` fails where `"1"` does, and drop the
   "answered" sentence of `objects.py:58-64`.

2. **Six keys still read what the published schema refuses: string and number spellings of
   booleans, quoted limits and factors, a quoted or boolean bit width** (the residue of the
   deferred strict-mode question, listed so that what remains is exact). Trigger -> outcome,
   each accepted without a finding while an editor bound to the schema underlines the value
   (R12 rows, L03-L05, L09, L39):

   | key | model | reads | spelling | schema |
   | --- | --- | --- | --- | --- |
   | `volatile` | `bool` (`objects.py:484`) | `"true"`, `"no"`, `1` -> true/false/true | `"volatile": "no"` drops the qualifier from the generated C | `type: boolean` (`ddd_component.schema.json:228`) |
   | `a2l.export` | `bool \| None` (`objects.py:147`) | `"no"`, `0` -> false | object left out of the A2L | `:9-16` |
   | `limits.min`/`max` | `Number` (`common.py:144-146`, "Not strict" `:154-156`) | `"0"`, `false` -> 0 | quoted limits pass | `:893-919` |
   | `factor`/`offset` | `Real` (`conversion.py:87-90`) | `"0.5"` -> 0.5 | quoted scaling passes | `:939-950` |
   | `bits` | `PositiveInt` (`types.py:173`) | `"2"` -> 2, `true` -> 1 | `"bits": true` is a one-bit field | `:1445-1453` |

   Already strict on both sides: `dimensions`, `size`, `event`, `alignment`, an enumerator's
   `value`, a constant's `value` (L06-L11, L11b), and the whole `init` (L01). `SPEC.md:322-334`
   types `volatile` as "whether" and `limits` as `min`/`max` numbers;
   `docs/file_formats/index.rst:118-124` promises that the schema lets "a ci job validate the
   files without running DDD at all",
   which these rows break in the direction that matters (the job passes a file `ddd check`
   also passes, but an editor flags a file the build accepts). Fix: `strict=True` on these five
   fields (or `ConfigDict(strict=True)` on the models with `Number`'s union arms marked strict),
   and pin each row in `tests/test_models.py`; if the deferral stands, say so in
   `data_contracts.rst:146-149`, which today describes only the int-before-float order.

3. **A scalar-level mistake inside a nested `init` is reported once per enclosing list, and
   every enclosing report is wrong** (`src/ddd/loading.py:1171-1193` `_meaningful` drops only
   `too_short`; `:1154-1168` `_one_per_place` keeps the first union arm per pointer, the
   scalar one). Trigger: a map `"init": [[1, 2], [3, null]]` on `"dimensions": [2, 2]` ->
   three `schema` errors: `init: Input should be a valid integer (got: [[1, 2], [3, None]])`,
   `init[1]: Input should be a valid integer (got: [3, None])`,
   `init[1][1]: Input should be a valid integer (got: None)` (R1a); the same for text (R1b),
   an object (R1c) and a 65-bit number (R1d: `init: Input should be a valid integer (got: [1,
   18446744073709551616])` before the real `init[1]: does not fit 64 bits`); at 99 levels it is
   100 findings (R10). The first two tell the reader a list should be an integer, the count
   says three mistakes where there is one, and the reading phase then stops the analysis
   (`docs/file_formats/index.rst:30-35`). `_meaningful`'s own docstring names the rule
   ("Reporting both invites the reader to go looking for a second problem that is not there")
   and applies it to one error type. Fix: in `_meaningful`, also drop an item whose `input` is
   a list or an object when a strictly deeper item exists at a location under it, keeping
   `missing` and the `too_short` case as they are.

#### Minor

1. **README still calls a constant an integer** (`README.md:447` "a **constants** file
   declares named integer constants"). Trigger: a reader writing `"value": 2.5` -> told it is
   refused; `SPEC.md:953-954`, `constants.py:44-57` and the tool accept it (L35a). Fix: "named
   numbers".

2. **project.rst contradicts itself about the include depth** (`docs/file_formats/project.rst:166`
   "The nesting has no depth limit and no effect on the result" against `:226-228` "DDD follows
   at most 64 levels of includes" and `SPEC.md:239`, `loading.py:55`). Fix: "The nesting has no
   effect on the result".

3. **The generated reference omits the fourth conversion** (`docs/data_contracts.rst:288-305`
   lists `IdentityConversion`, `LinearConversion`, `EnumConversion`, `Enumerator`; no
   `autopydantic_model:: ddd.models.StringConversion` anywhere under `docs/`, and the paragraph
   at `:291-296` describes three kinds). Trigger: a reader looking up what `{"kind": "string"}`
   is held to on the page that says it is "the generated reference for every model" (`:191`)
   -> nothing. Fix: add the directive and "or a string" to the paragraph.

4. **"The outputs carry the literal as written" is stated three times about constants and is
   not what happens** (`src/ddd/models/constants.py:77-79` "the generated code emits the
   literal as written, so the author picks the type rather than the format", published at
   `schemas/ddd_constants.schema.json:27` and `schemas/ddd_component.schema.json:401`;
   `docs/file_formats/constants.rst:28-30`; `src/ddd/backends/c/model.py:193` "The number as
   the description wrote it"). Trigger: `"value": 2.50`, `1e3`, `1e21`, `0.10` -> `#define C
   2.5`, `#define A 1000.0`, `#define E 1e+21`, `#define F 0.1` and the same strings in
   `SYSTEM_CONSTANT` (L14c). The type survives (a point or an exponent stays a float), the
   spelling does not. Pass 1 reported the spec sentence (`SPEC.md:955-956`); these are the
   three copies it is echoed by. Fix: "the number in its shortest round-trip spelling, a whole
   number without a point and any other with one, so `2.50` reaches the C as `2.5` and `1e3`
   as `1000.0`".

5. **Four rules enforced only in Python are missing from the descriptions the schema page
   promises carry them** (`docs/file_formats/index.rst:169-171` "Some rules cannot be expressed
   as a constraint and are written into the description of the key they hang off instead").
   R12 shows the editor accepting and the loader refusing: `header` `"a b.h"` while
   `types.py:484-488` says only "`my_driver.h` for the quoted form, `<os_types.h>` for the
   angle form" (the whitespace, quote and angle rules of `types.py:410-440` and `SPEC.md:831-832`
   are absent); `cycle` `"1234ms"` while `rasters.py:94-99` says "an integer and a unit ... no
   space and no fractional part" and not the 1..255 times a decade rule of `:56-68`; duplicate
   enumerator names while `conversion.py:148` says "The named values, either as objects or as
   a mapping" (`:163-170` refuses the repeat); `unit`, `limits` and `a2l.format` beside a
   string while `objects.py:416-422`, `:469-475`, `:158-159` say nothing about a string
   (`:252-287` refuses all three). Fix: one sentence each.

6. **Five integer keys published as `type: integer` accept `4.0` in an editor and are refused
   by the loader** (`schemas/ddd_component.schema.json:1350-1352` `dimensions` items, `:239-241`
   `size`, `:773-776` an enumerator's `value`, `schemas/ddd_rasters.schema.json:18-21` `event`,
   `schemas/ddd_sections.schema.json:34-37` `alignment`; models `objects.py:70`, `conversion.py:46`,
   `rasters.py:86`, `sections.py:52`, all `strict=True`). Trigger: `"dimensions": [4.0]`,
   `"event": 1.0`, `"alignment": 4.0`, `{"A": 1.0}` -> `jsonschema` accepts (JSON Schema's
   `integer` admits a zero fractional part), `ddd check` says `Input should be a valid integer
   (got: 4.0)` (L12a-e, R12). The reverse direction of Important 2, and the harmless one. Fix:
   accept a float with a zero fraction on these keys (a `BeforeValidator` turning `4.0` into
   `4` and refusing strings keeps the two spellings of `"8"` apart), or say in the descriptions
   that a whole number is written without a point.

7. **Two pass-through messages a user cannot act on.** (a) `"value": 1e400` on a constant ->
   `k.ddd.json#constants[6].value: error[schema]: Input should be a valid integer (got: -inf)`
   (L14b): `_one_per_place` (`loading.py:1161-1163`) keeps the first arm, the strict `int` of
   `ConstantValue`, so the finding names the wrong arm, where the same literal in `init`,
   `limits` or `factor` says "Input should be a finite number" (L14a). (b) A file with two
   byte order marks -> `c.ddd.json:1:1: error[json-syntax]: Unexpected UTF-8 BOM (decode using
   utf-8-sig)` (L24c), Python's advice to a programmer passed through `loading.py:580-585`.
   Fix: (a) prefer a `finite_number` error over the others in `_one_per_place`, or state the
   finite rule in the `value` message; (b) map that `JSONDecodeError.msg` to "a second byte
   order mark follows the first".

8. **A `raster` reference is held to no rule while a `section` reference is patterned, and
   the spec states neither** (`objects.py:432` and `component.py:96` `raster: str | None =
   None` against `objects.py:424` `section: Annotated[str,
   StringConstraints(pattern=SECTION_NAME_PATTERN)] | None`). Trigger: `"raster": ""` on a
   definition or a component -> `unknown-raster: 'V' is measured in ''` (L19e, L19g), a name no
   rasters file could declare (`rasters.py:76-78` refuses it); `"section": ""` or `"no-dash"`
   -> `schema` before `unknown-section` gets a say (L19d, L37b), which `SPEC.md:691-699` does
   not mention (carried over from the previous review's spec gaps, the one of twelve still
   open). Fix: hold the raster reference to the declaration's `^\S+$` and length, and say in
   3.5 that a definition's `section` obeys the declaration's spelling rule.

9. **An `init` nested 99 levels deep is refused with a hundred wrong findings** (R10: 98
   levels validate, 99 give `Recursion error - cyclic reference detected` at the two deepest
   pointers under the cascade of Minor 3; L26 shows the same at 100, 300, 900 and 1500).
   `SPEC.md:200-201` promises `json-syntax` for "nesting [that] exceeds the depth the parser
   accepts"; the parser accepts these, pydantic-core's recursion guard on the recursive
   `InitElement` (`objects.py:36`) does not, and no document states the cap. Implausible in a
   description, so minor; Important 3's fix reduces it to one finding, and a sentence in 3.3
   or a `json-syntax` finding when a list init nests deeper than 98 would state it.

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| I1 | measurement "only read" by a calibration tool | fixed | `objects.py:89`, `:621-625`; `README.md:334-336`; `variable_definition.rst:444-450`; `ddd_component.schema.json:1165`, `:1340` |
| I2 | identity described as "the default" | fixed | `conversion.py:64-69`; `ddd_component.schema.json:833` |
| I3 | `unit` docstring predates the vocabulary | fixed | `objects.py:416-422`; `ddd_component.schema.json:126`; `variable_definition.rst:97-104`; `README.md:319` |
| I4 | `"dimensions": []` accepted, spec said non-empty | fixed (spec side) | `SPEC.md:410` "`[]` or absent for a scalar"; L20b |
| I5 | type-name pattern refused lowercase only | fixed | `common.py:269-282`; `ddd_component.schema.json:107`; R12 rows `UINT16`/`Uint8` refused on both sides; `tests/test_documentation.py:1096-1106` |
| M1-M9 | minors, checked in bulk | M1, M2, M3, M4, M6, M7, M8, M9 fixed (`project.py:23-29`, `types.py:322-328`, `conversion.py:46-57`, `component.py:23`, `common.py:26`, `build_info.py:21`, `component.rst:356-363`, `project.rst:133-143`, `README.md:327`); M5 (whole-valued float init refused as "fractional") consciously left: the finding still reads `init value 1.0 is written as a fractional number` (L12h) and `SPEC.md:422-427` still states only the range rule | `analysis.py:2348-2357` |

The previous review's twelve "spec gaps proven from code" are in the spec now: `[]` as the
scalar spelling (`SPEC.md:410`), `$schema` string or null (`:207-208`), `export: null`
(`:547-548`), `description` on scalar, struct and member entries (`:804`, `:818`, `:821`),
the header spelling rules (`:831-832`), a member's `dimensions` naming a constant (`:974-976`),
`NaN`/`Infinity`/`1e400` (`:201-203`), a non-object top level (`:204`), a units entry `""`
(`:914`), `file-extension` after reading (`:263-264`), the exported-axis exception (`:543-546`),
and restating beside a `typename` (`:587-588`, though `"unit": ""` is refused by presence,
L32d). Still open: the section-name pattern on a definition's `section` (Minor 8). The
`init: true` on an integer datatype is the deferred JSON-boolean init (L39). Of its eight test
gaps, one is closed (the mixed-case type name against the published schema,
`tests/test_documentation.py:1096-1106`); the character class, the dot-prefixed file, the sorted
order winning over enumeration order (`tests/test_loading.py:53-63` still asserts the natural
order `["A", "B"]`), symlink identity, the 128-character cap outside the LSP rename
(`tests/test_lsp.py:2085-2087` only), a BOM in a loader test (`tests/test_cli.py:2362` is the
`id --assign` path) and `"dimensions": []` in a model test (`tests/test_cli.py:985` shows it in
a dump only) are open.

### Open questions

1. Is a quoted number inside a list `init` meant to be text, as `SPEC.md:433-434` and
   `objects.py:36-42` say, or is the whole strict-mode question (Important 2) to be settled in
   one change? Text alone changes `InitScalar`; the whole question changes five fields, the
   `Number` alias and `data_contracts.rst:146-149`.
2. Pass 1's question 2 (platform order of wildcard matches) has a code shape now: the loader
   sorts `Path` objects (`loading.py:1006-1010`); code-point order means sorting on
   `resolved.as_posix()` (or `str(resolved)`) instead, and `tests/test_loading.py:53-63` would
   need a set whose enumeration order differs from the sort. Platform order keeps the loader
   and narrows `SPEC.md:1604-1607`.
3. Pass 1's question 4 (`1e3` as a fraction): the model cannot see the spelling, only the
   parser's `float`; refusing or reclassifying exponent spellings would need a `parse_float`
   hook in `loading.py:575` that keeps the literal text. Leaving it means writing the rule as
   "a literal with a point or an exponent is fractional" in 3.9 and `constants.py:73`.
4. For the five integer keys of Minor 6, accept `4.0` in the loader (consistent with the
   published schema) or keep them strict and document the disagreement? The first changes
   `Dimension`, `Enumerator.value`, `event` and `alignment`; the second changes five
   descriptions.

### Test gaps

- `tests/test_models.py`: a numeric string nested in a list init (`["1", "2"]`) is refused or
  read as the number, whichever open question 1 decides; `tests/test_models.py:842` pins only
  the whole init. The same file, one case per row of Important 2 (`"volatile": "no"`,
  `"export": 0`, `"limits": {"min": "0", ...}`, `"factor": "0.5"`, `"bits": true`), pinning the
  decision either way.
- `tests/test_loading.py`: a `null` or text inside a 2-D init yields one `schema` finding at
  the innermost pointer (Important 3); today nothing pins the count, and
  `tests/test_hardening.py:852` covers only the `too_short` filter.
- `tests/test_loading.py`: a BOM on the root and on an included file; a literal `..` path; a
  character class `[ab]?`; a dot-prefixed file; two spellings of one file's case on Windows
  loaded once (L29i); a match set created in an order different from its sort; symlink
  identity (all previous gaps, still open).
- `tests/test_models.py`: 128 accepted and 129 refused on an object name, a constant name and
  an `axis`/`input`/`typename` reference; `"dimensions": []` on a measurement read as the
  scalar (`SPEC.md:410`).
- `tests/test_constants.py:81-88` (`test_a_fractional_value_is_carried_as_written`)
  parametrises `1.5, -0.25, 0.0, 2.0`, whose `repr` is their spelling; a `2.50` or `1e3` case
  through `ddd generate` would pin the normalisation Minor 4 documents.
- `tests/test_documentation.py`: that every `BaseModel` exported by `ddd.models` appears in an
  `autopydantic_model` directive of `docs/data_contracts.rst` (Minor 3 would not have shipped).
- `tests/test_rasters.py` or `tests/test_models.py`: a definition or component `raster` of `""`
  or with whitespace, whichever way Minor 8 is settled.

### Assessment

The formats are in good shape: the eight schemas are current and pinned for every kind, the
five Important findings of the previous review are fixed, its spec gaps are written down but
one, and across some three hundred probes every refusal section 3 attaches to an identifier is
reported with that identifier - the reading rules, the includes, the string rules, the four
vocabularies and the name rules all do what the text says. What remains is concentrated in one
place, the `init` union: a numeric string nested in a list is quietly read as a number against
the spec's and the docstring's word, and a scalar mistake deep in a nested init is reported once
per enclosing list with a wrong message each time. Beside those, the residue of the deferred
strict-mode question is exactly five fields, listed above so that the decision can be taken on
the full list rather than case by case; the rest is prose that has drifted from behaviour in
the README, one page that contradicts itself about the include depth, a reference page missing
the fourth conversion, and the "as written" claim about constant literals that the outputs do
not keep.

### Verification

Every candidate of this pass was handed to a second reviewer (group A): 12 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P2-I1 | Important | CONFIRMED | Important | `"init": ["1", "2"]` on `uint8[2]`: `ddd check --standalone` clean, `ddd dump` carries `'V': [1, 2]`; the whole init `"12"` -> `init-invalid` "initialised with text"; `jsonschema` REFUSED at `definition`; `SPEC.md:433-434` "a quoted number is text, not the number"; `objects.py:37` "never text" |
| P2-I2 | Important | CONFIRMED | Minor | `"volatile": "no"` -> `uint8_t V;`, `"export": "no"` -> no `MEASUREMENT X`, `{"min": "0", "max": "10"}` -> `{'min': 0, 'max': 10}`, `"factor": "0.5"` -> 0.5, `"bits": "2"`/`true` -> `f : 2`, `g : 1`; `jsonschema` refuses all five; the deferred strict-mode residue |
| P2-I3 | Important | CONFIRMED | Important | `[[1, 2], [3, null]]`: `init: Input should be a valid integer (got: [[1, 2], [3, None]])`, `init[1]: ... (got: [3, None])`, `init[1][1]: ... (got: None)`, "3 errors"; `[1, 18446744073709551616]`: the `init` line precedes `init[1]: ... does not fit 64 bits`; `loading.py:1192` drops `too_short` only |
| P2-M1 | Minor | CONFIRMED | Minor | `README.md:447` "a **constants** file declares named integer constants"; the tool dumps `2.5` (expA); the README copy of P1-I3 |
| P2-M2 | Minor | CONFIRMED | Minor | `project.rst:166` "The nesting has no depth limit" vs `:227` "DDD follows at most 64 levels of includes"; `loading.py:55` `_MAX_INCLUDE_DEPTH = 64` |
| P2-M3 | Minor | CONFIRMED | Minor | `src/ddd/models/__init__.py:21`, `:122` export `StringConversion`; the `autopydantic_model` directives under `docs/` name Identity, Linear, Enum and Enumerator only (`data_contracts.rst:298-306`); `:291-296` describes three kinds |
| P2-M4 | Minor | CONFIRMED | Minor | `constants.py:78-79` "the generated code emits the literal as written", verbatim at `ddd_constants.schema.json:27`, `ddd_component.schema.json:401`, `constants.rst:28-29`; `c/model.py:193` "as the description wrote it"; outputs as in P1-M4, which is primary |
| P2-M5 | Minor | CONFIRMED | Minor | `types.py:484-488` names the two forms while `:419-439` refuse whitespace, a quote and mixed angles; `rasters.py:94-99` vs `:56-68`; `conversion.py:148` vs `:163-169`; `objects.py:416-422`, `:469-475`, `:158-159` say nothing of a string while `:278-286` refuse all three; `index.rst:169-171` promises the rule in the description |
| P2-M6 | Minor | CONFIRMED | Minor | `"dimensions": [4.0]`, `"event": 1.0`, `"alignment": 4.0`: `jsonschema` accepts all three; `ddd check` -> `Input should be a valid integer (got: 4.0)`, `(got: 1.0)`, `(got: 4.0)`; `objects.py:70`, `rasters.py:86`, `sections.py:52` `strict=True` |
| P2-M7 | Minor | CONFIRMED | Minor | `"value": 1e400` -> `k.ddd.json#constants[0].value: error[schema]: Input should be a valid integer (got: inf)` beside `limits.max: ... Input should be a finite number (got: inf)`; two BOMs -> `bom.ddd.json:1:1: error[json-syntax]: Unexpected UTF-8 BOM (decode using utf-8-sig)`; `loading.py:583` passes `error.msg` through |
| P2-M8 | Minor | CONFIRMED | Minor | `"raster": ""` and `"a b"` on definitions, `""` on the component -> three `unknown-raster` ("measured in ''", "'a b'"); a rasters entry `""` -> `schema` "at least 1 character"; `"section": ""` -> `schema` pattern `^[A-Za-z0-9_.$]+$`; `objects.py:432` `raster: str|None` vs `:424`; `SPEC.md:691-699` states no spelling rule |
| P2-M9 | Minor | CONFIRMED | Minor | 98 nested lists: clean; 99: "100 errors", the deepest two `error[schema]: Recursion error - cyclic reference detected (got: 1)`; `SPEC.md:200-201` promises `json-syntax` for depth and no document states 98 |

Notes of the verifier:

- **P2-I2, regraded to Minor.** This is the residue of the strict-mode question the review brief
lists among the follow-ups the maintainer left open on purpose ("strict-mode pydantic models and
a JSON-boolean init deferred"; `docs/superpowers/plans/2026-09-09-core-robustness.md:29`
"strictness is a separate, deferred change with its own migration note"; the previous review's
Important 6 named these same fields). Every row reproduces, and none yields a value other than
what its spelling says - `"no"` is false, `"0.5"` is 0.5, `"2"` is 2; `"bits": true` -> 1 is the
one odd reading, on input nobody writes. The schema is the stricter side, so a CI job validating
with it passes nothing the loader refuses; the cost is an editor underline on a file the build
accepts. No wrong verdict or output, so not a defect the deferral now causes; the table remains
the exact list the decision needs. P2-I1 is different and stays Important: `SPEC.md:433-434` and
`objects.py:58-64` say the init half of the question was settled, and the nested case escaped
the settlement.

## Pass 3: the consistency checks and the comparison (SPEC.md section 4)

### Scope covered

Read in full, with line numbers, on the review tree (`master` at `6e9e99f`): `SPEC.md` 1143-1507
(sections 4 and 4.1) plus the sentences the checks lean on in 2.1, 3.3 and 3.10 (443-449,
492-524, 1036-1042); `src/ddd/analysis.py` 1-3289; `src/ddd/compare.py` 1-672;
`src/ddd/identity.py` 1-183; `src/ddd/diagnostics.py` 1-523; the check sites of
`src/ddd/loading.py` (440-660, 690-760, 870-1160); `src/ddd/plugins.py` 266-303 and 362-402;
`src/ddd/cli.py` 540-725 and 1350-1500; `src/ddd/ir.py` 100-260 and 560-720;
`src/ddd/models/objects.py` 20-120 and 430-830; `src/ddd/models/conversion.py` 125-300;
`src/ddd/backends/a2l/model.py` 398-430; `docs/consistency_checks.rst` and
`docs/comparing_deliveries.rst` in full; `README.md` 480-607; `CHANGELOG.md` "Unreleased";
`previous-review.md` 964-1123 and 1655-1680; `reports/pass-1.md` and `pass-2.md`; the test names
of `tests/test_analysis.py`, `test_compare.py`, `test_calibration.py`, `test_structures.py`,
`test_constants.py`, `test_rasters.py`, `test_models.py`, `test_cli.py`,
`test_documentation.py`, and the bodies of the tests cited below.

Ran, from the venv, everything kept under `scratchpad/pass-3/`: `ddd checks` in text and json;
five probe scripts (`probes_a.py`, `probes_a2.py`, `probes_b.py`, `probes_b2.py`,
`probes_b3.py`) writing 48 throwaway projects under `cases/` and running about 190 commands -
`check`, `check --standalone`, `check --baseline`, `list`, `dump`, `generate c|a2l`, `compare`
with `--renames`, `--plugin`, `-W`, `--strict`, `--format json` - with the transcripts in
`results_a.txt`, `results_a2.txt`, `results_b.txt`, `results_b2.txt`, `results_b3.txt`. Case
ids `Cnn`, `Mnn`, `Nnn` below refer to those. Every one of the 69 identifiers was lined up
against the registry, the code that adds it, the spec, both doc pages and the README, and all
69 were observed firing. The verdict rule was exercised on ten configurations (`M03`, `N01`,
`N03`), the comparison on a pair carrying all thirteen checks at once (`M02`), on format 7, 3
and 9 dictionaries (`M05`), on the plugin example (`M08`) and on the shipped pressure example
(`N02`). Not covered: the language server's use of `STANDALONE_POLICY` beyond reading
`lsp/diagnostics.py:59`, and the generated artefacts except where a check gap reached them.

### Strengths

- The registry is section 4 exactly: 69 identifiers, every default severity, the eight fixed
  ones, exactly the ten whole-project ones (`diagnostics.py:89-255`), from which
  `STANDALONE_POLICY` (`:257-261`), `ddd check|list|dump --standalone` (`cli.py:1359`) and the
  editor (`lsp/diagnostics.py:59`) are all derived; `ddd checks` marks `(fixed)`, `(project)` and
  `(comparison)` and the json carries the three flags. `dimension-value` is rightly not flagged:
  alone, a component can only name its own constants, and `C14` shows it firing on them under
  `--standalone` at a declaration's `dimensions`, an axis's `size` and a member.
- Ownership is decided over the census, dropped declarations included, in every configuration
  tried: a dropped producer is no `missing-producer` and a dropped consumer no `unused-output`
  (`C03`), the object is built from the producer that resolved whatever the include order
  (`C03b`), and a dropped producer takes its consumers' copies out whole, each with
  `incomplete-project` and a note at the producer when the cause was silenced.
- `incomplete-project` now says every absence the spec lists, and one it does not: a poisoned
  type with the cause and a note at the member (`C29`: nine findings for nine drops through a
  cycle, an unknown member type and a structure nesting either), a member's `dimension-value`
  (`C14`), a refused reference ("its input 'Nobody' does not resolve, and the unknown-reference
  that says why is not reported", `C09`), a transitive absence at the reference that pulled it
  down, and a map explained on one axis only (`C06`).
- A dangling reference drops the referrer (`C09`: four objects gone from `ddd list`), a reference
  into another component's `local` object is `local-conflict` at the reference with a note,
  nothing dropped and the same answer in either include order (`C08`), a scope clash involving a
  `local` is never also `multiple-producers` (`C35`).
- A scalar type is checked once, at its declaration, used or unused (`C13`: `limits-out-of-range`
  at `types[0].limits` on a type nobody names, the enumerator finding at `types[1].conversion`
  once although two components name the type), and a declaration naming a type checks clean
  against an equivalent inline one (`C26` `T`).
- The severity policy is the spec's to the letter (`C23`): last override wins, `--strict` after
  the overrides, a fixed or unknown check, an unknown severity, a missing `=` and a plugin check
  nobody registers are usage errors with exit 2 and the messages the reference page prints.
  Findings sort by index, not text (`C38`), and two runs print the same json (`C01`).
- The comparison does what 4.1 says in every configuration tried: all thirteen checks fire with
  the messages the docs show (`M02`); the verdict is "can replace" exactly when nothing is an
  error - a warning-only run exits 0, `--strict` or `-W x=error` turns it into "cannot" and exit
  1, a candidate's own error refuses, a broken description baseline carries its errors as "in the
  baseline:" and still compares a dumped candidate but analyses no description candidate and
  prints no verdict, an unreadable side exits 1 and writes no renames file, the baseline's
  warnings are dropped, json prints no verdict line (`N03`, `M03`, `N01`). Renames are keyed
  `<id>[0].a` and `<id>.a`, sorted by `to`, `[]` when nothing moved (`M02`, `M06`, `N03`); a
  renamed instance whose type also renamed a member pairs the surviving members and reports the
  rest as removal and addition (`M06`). A format 7 dump reads back, a format 3 one compares shapes
  by value alone, format 9 is refused on either side and under `check --baseline` (`M05`). The
  plugins behave as 4.1 states (`M08`), and the shipped pressure sequence reproduces the docs'
  transcript to the character (`N02`).

### Issues

#### Critical

None.

#### Important

1. **An axis whose `input` names a structured measurement instance passes `reference-kind`, and
   the A2L then binds the axis to a name that has no `MEASUREMENT` record**
   (`src/ddd/analysis.py:2700` `elif found.kind is not _EXPECTED_KIND[key]:` - a structured
   instance's `kind` is `measurement`, so the test passes; `src/ddd/backends/a2l/model.py:412`
   and `:425` write `references.get("input")` verbatim). Trigger (`C09b`): a structure `S_t`
   with a member `a`, an instance `Inst` of it, an axis `Cx` with `"input": "Inst"` and a curve
   over `Cx` -> `ddd check` prints `ok: 3 variables in 2 components are consistent`, and
   `ddd generate a2l` writes `/begin AXIS_PTS Cx ... 0x00000000 Inst RL_AXIS_UWORD ...` and
   `COM_AXIS Inst NO_COMPU_METHOD ...` while the only measurement record is
   `/begin MEASUREMENT Inst.a`. `_EXPECTED_KIND`'s own docstring (`analysis.py:137-140`) and
   `SPEC.md:1292-1293` ("an axis naming an absent measurement would leave a dangling name in the
   A2L") describe exactly the outcome. A curve naming the instance as its `axis` is refused
   (`C09`: "'Inst' is of kind 'measurement'"); only the `input` key, which expects a
   measurement, lets a structured one through. Fix: in `_refuse_reference`, refuse a target whose
   `declared_type` names a structure as `reference-kind` ("'Inst' is a structured object; an
   input quantity is a plain measurement"), which drops the axis as every wrong-kind reference is.

2. **`changed-storage` compares `init` as spelled, so a byte-identical respelling is a warning and,
   under `--strict`, a false "cannot replace"** (`src/ddd/compare.py:182`
   `ComparedField("init", lambda o: o.init, lambda o: _describe_init(o.init)),`; the dictionary
   carries the init as written, `analysis.py:390` `init=definition.init,`, although
   `ir.py:186-187` says "nested to match `shape`"). Trigger (`N01`): a baseline with `"init": 7`
   on `uint8[4]` and `"init": [72, 105, 0, 0]` on a `uint8[4]` string, a candidate spelling them
   `[7, 7, 7, 7]` and `"Hi"` ->
   `warning[changed-storage]: 'Arr': init: (7, 7, 7, 7) != 7` and
   `warning[changed-storage]: 'Str': init: "Hi" != (72, 105, 0, 0)`, "can replace", exit 0; with
   `--strict`, the gate `docs/comparing_deliveries.rst:660-662` recommends, three errors and
   "cannot replace", exit 1. The generated c is the same in both deliveries, and the text
   spelling is the migration the strings feature invites (`CHANGELOG.md` "Strings"). Pass 1
   Minor 6 asked which comparison is meant; from the code it is the spelling. Fix: compare the
   init broadcast over `shape` (`models.objects.broadcast`) and a string as its byte tuple padded
   with zeros to the dimension - or, if the spelling is meant to count, say so in 4.1 beside
   `changed-storage` and in 5.3, so that `--strict` users know the respelling costs a release.

3. **Comparison findings carry the candidate path as it was typed, so `--format json` reports a
   cwd-relative `location.path` where the reference page promises an absolute one**
   (`src/ddd/cli.py:649` `location = Location(args.candidate)`, `:602` and `:609`
   `Location(args.project)` under `check --baseline`, `:712` `Location(path)` for
   `address-missing`; `docs/consistency_checks.rst:975` "``location`` is an absolute,
   forward-slashed path together with the json pointer"). Trigger (`N01`):
   `ddd compare base.json warn/p.ddd.json --format json` -> `"path": "warn/p.ddd.json"` for
   `removed-unused-object`, beside `"path": "C:/.../cases/N01/warn/sensor.ddd.json"` for the
   candidate's own `init-invalid` in the same document; `N02`: `"path":
   "examples/pressure/work/pressure.ddd.json"`. A dashboard or editor following the documented
   contract cannot resolve the path without knowing the run's working directory. A side effect
   in text mode: within one severity the sort key is `path.as_posix()`
   (`diagnostics.py:354`), and `C:/...` sorts before `cand/...`, so every comparison finding
   lands after every finding of the candidate's own analysis (`M02`: `project-mismatch` after
   eleven `unused-output` warnings), which is what `docs/comparing_deliveries.rst:589-590` says
   does not happen. `tests/test_cli.py:919-930` pins "as typed" for `generate`'s `generated`
   payload, not for a diagnostic's `location`. Fix: build these locations from the resolved path
   (`loading._resolve`), or amend the sentence on the reference page and the ordering claim.

#### Minor

1. **A reported refusal beside a silenced transitive absence still earns `incomplete-project`**
   (`src/ddd/analysis.py:2671` `explained = own.get(name, True) and all(absent[target] for _,
   target in gone)`; `SPEC.md:1368-1369` "This check fires only when the cause is silenced; a
   reported cause already says the declaration could not resolve"). Trigger (`C06`,
   `-W unknown-constant=ignore`): axis `Az` with `"input": "Cv"`, `Cv` a curve over the silently
   dropped `Ax` -> at `interface[4].definition.input` both `error[reference-kind]: the input of
   axis 'Az' must be of kind 'measurement'` and `info[incomplete-project]: 'Az' is not in the
   data dictionary: its input 'Cv' did not resolve, and the finding that says why is not
   reported`. Fix: a name with a reported refusal of its own is explained
   (`explained = own[name] if name in own else all(...)`).

2. **`duplicate-id` does not see the id of a dropped declaration**
   (`src/ddd/analysis.py:1783` `for name, refs in ordered:` over `ordered = sorted(self._refs.
   items())`, `:720`, the surviving names only). Trigger (`C12` `p2`): `Gamma` with an unknown
   `typename` and `Delta`, both `"id": "abcdefghjkmn"` -> `unknown-type` alone; the shared id
   surfaces as a second wave once the type is fixed. The one failure mode of the previous
   review's design note 1 that survives the census. Fix: walk `self._census` as
   `_select_producer` does.

3. **A text init on an object that is not a string is refused only once the declaration
   resolved** (`src/ddd/analysis.py:3137-3144` runs from `_check_init_shape`, which only
   `_build_variable` calls, `:3019`; `:2237-2244` promises that "an init outside the datatype is
   wrong whatever the shape turns out to be, and silencing unknown-constant must not silence
   that"). Trigger (`C24`): `D1` `"dimensions": ["NOPE"], "init": "text"` on a `uint8` ->
   `unknown-constant` alone, while `D2` with `"init": 300` also gets `init-invalid`; with
   `-W unknown-constant=ignore` the text init is never reported. Fix: test the conversion in
   `_check_init` and leave only the printable and terminator rules to `_check_string_init`.

4. **The enumerator-out-of-range finding sits at `definition` on a declaration and at
   `conversion` on a type** (`src/ddd/analysis.py:2307` `location = ref.location("definition")`
   handed to `_check_enum_fits` at `:2333-2335`, against `:881-885` `entry.location(
   "conversion")`). Trigger (`C24` `E1`, `C13`):
   `a.ddd.json#component.interface[22].definition: error[init-invalid]: enumerator(s) B=256 ...`
   against `t.ddd.json#types[1].conversion: error[init-invalid]: enumerator(s) ON=300 ...`.
   Fix: `ref.location("definition.conversion")`, where the enum is written.

5. **Under a silenced `local-conflict` the owner follows the include order** (carried over,
   previous Minor 7; `src/ddd/analysis.py:2556-2557` `owning = [...] or producers` then
   `owning[0]`). Trigger (`C35`, `C08` `p3`/`p4`): `A` local `X` and `B` output `X` list
   `X ... A (local)` with the includes `a, b, c` and `X ... B` with `b, a, c`; two locals of one
   name the same. Only visible with the check relaxed, but then the generated files depend on
   the include order. Fix: prefer the `local` declaration, else order producers by component.

6. **Under `--standalone` a silenced cause that needs no project leaves no trace at all**
   (`src/ddd/diagnostics.py:208-211` flags `incomplete-project` as one of the ten, so
   `STANDALONE_POLICY` silences the trace together with the checks whose absence is
   legitimate). Trigger (`C14`): `ddd check c.ddd.json --standalone -W dimension-value=ignore` on
   a component whose own constant `ZERO` dimensions a measurement, an axis and a member ->
   `ok: 1 variable in 1 component are consistent`, and `ddd list --standalone` is three rows
   short with nothing said, the very outcome `SPEC.md:1365-1368` gives as the reason the check
   exists. Fix: report `incomplete-project` in a standalone run when the silenced cause is not
   itself a whole-project check, or say in 4 and 7 that `--standalone` silences the trace too.

7. **A dictionary whose `format` is spelled `"9"` or `9.0` is read as a format 9 dictionary**
   (`src/ddd/loading.py:459` `if not isinstance(found, int) or isinstance(found, bool) or found
   <= DICTIONARY_FORMAT: return True`, then `ir.py:593` `format: int = DICTIONARY_FORMAT` coerces
   the text and the float). Trigger (`M05`): the same dump with `"format": "9"` or `9.0` as the
   baseline -> "can replace", exit 0, where `9` is `error[schema]: this dictionary is in format
   9 ... use a newer DDD`. A dump never writes either; a hand edit does. Fix: strict `int` on
   `format`, and refuse a non-integer spelling in `_dictionary_format_is_supported`.

8. **Docs drift on three checks.** `docs/consistency_checks.rst:619` still says
   `a2l-unrepresentable` fires for "an exported object" where `SPEC.md:1345-1346` and the code
   (`C30`: `Hidden4`, `"export": false`, reported because an exported axis names it as `input`)
   say the object the A2L carries; `docs/consistency_checks.rst:397-403` says of
   `dimension-value` "The declaration is dropped" and, like `SPEC.md:1369-1376`, not that at a
   member the type becomes unusable and every declaration naming it is dropped (pass 1 Minor 5,
   confirmed: `C14` prints "it names the type 'S_t', and the dimension-value that says why the
   type is unusable is not reported"); and the in-file `duplicate-type` is a `schema` finding
   located at the whole file, `t3.ddd.json: error[schema]: Value error, type 'W_t' is already
   declared in this file` (`C28`), where `duplicate-unit`, `duplicate-section`,
   `duplicate-constant` and `duplicate-raster` point at the entry (`loading.py:727-736`).

9. **The second copy of a `duplicate-declaration` still earns `unknown-section` and
   `unknown-raster`, and nothing else** (carried over, previous Minor 8; `src/ddd/analysis.py:
   2214-2221` `continue`s before `_check_declared_name`, while `_check_sections` and
   `_check_rasters` walk `component.interface` whole, `:1044-1045`, `:1109-1110`). Trigger
   (`C37`): a duplicate `input` stating `init`, `section: ".nope"`, `raster: "r"` and an enum
   with the enumerator `int` -> `duplicate-declaration`, `unknown-raster`, `unknown-section`; no
   `consumer-*`, no `reserved-identifier`. Harmless; `docs/consistency_checks.rst:483` "The
   second declaration is ignored for the rest of the run" is only mostly true.

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| C1 | `incomplete-project` silent for most silenced drops | fixed | `analysis.py:2111-2131`, `2747-2806`; `C29`, `C06`, `C14` |
| I1 | an unresolvable reference keeps its object | fixed | `analysis.py:2677-2713`, `2603-2626`; `C09` (four objects dropped, `incomplete-project` when silenced) |
| I2 | enum reordering reported twice, once empty | fixed | `analysis.py:162-181`; `C25` (`enum-conflict` alone, with both spellings in the notes) |
| I3 | renamed structured object is N findings | consciously left, spec moved | `SPEC.md:1489-1491`; `M06` |
| I4 | `address-missing` empty map and one-per-run unstated | fixed | `SPEC.md:1348-1356`; `C31b` |
| I5 | a raising hook discards the run's findings | fixed | `cli.py:1365-1373`, `1460-1488`; `M06` "renames into a missing directory" prints the findings before the usage error |
| I6 | docs: "two other load time checks" | fixed | `docs/consistency_checks.rst:244-253`, `272-281` |
| I7 | checks reference lacks `--standalone` | fixed | `docs/consistency_checks.rst:174-225` |
| I8 | `ddd checks` prints no whole-project flag | fixed | `(project)` in text, `needs_every_component` in json; `docs/consistency_checks.rst:1003-1005` |
| I9 | spec: `typename` compares as resolved | fixed | `SPEC.md:505-509`, `1504-1506`; `C26` `T` |
| I10 | spec: reference into another's `local` | fixed | `SPEC.md:1197-1201`; `analysis.py:2715-2745`; `C08` |
| I11 | spec: alignment need per datatype | fixed | `SPEC.md:703-707`; `C15` (4 for `uint32`, 8 for `float64`) |
| M1-M8 | minors, checked in bulk | M1-M6 fixed (`diagnostics.py:156-158`, `README.md:500`, `:579`, `SPEC.md:1345-1346`, `1481-1484`, `analysis.py:2207-2222`, `SPEC.md:1186-1188`); M7 fixed in the spec (`SPEC.md:1412-1413`, `M03` (f)); M5 and M8 of pass 7's list still open as Minor 5 and Minor 9 above | - |

Design notes 1 and 2 of pass 7. Note 1 (dropping versus marking): the analysis now keeps every
declaration in `_census` (`analysis.py:673-680`) and records per declaration whether its cause
was reported (`_dropped`, `:681-687`); ownership (`:2504-2557`), the readers (`:2840-2842`) and
`incomplete-project` (`:2747-2806`) all read it, and the failure modes the note described -
false `missing-producer` and `unused-output`, an owner chosen by include order, silent consumers
- are gone (`C03`, `C03b`). Two censuses still read the surviving names only: identities
(Minor 2) and similar names (`:3202-3224`, `C11`: a dropped `Baz` beside `baz` is not reported,
which the spec's "for the ownership checks" permits). Note 2 (types checked through their
users): `_check_scalar_type` (`:865-888`), `_register_member_enums`, `_check_member_limits` and
`_refuse_infinite_type_limits` check a type once where it is declared, used or not, and a
declaration naming a type skips the limits and enum checks (`:2319-2325`); `C13` shows one
finding per mistake at the types file. No failure mode of that note survives.

Of the previous pass's "spec gaps proven from code", all are written into `SPEC.md` now
(resolved `typename` 505-509 and 1504-1506, the empty map 1349-1350, the verdict 1398-1402, the
renames keys 1407-1413, older formats 1502-1504, a refused reference 1290-1296, whose plugins
1471-1474, the tie-break 1430-1431, both raster findings on one declaration 1042, the in-file
`duplicate-type` 837-838, the project block 1090-1091, a reference into a `local` 1197-1201,
the alignment 703-707, the closure 1345-1346, the note 1480-1484, per-member renames 1489-1491,
`missing-id` on a `local` 1377) except one: that every load-time error, the nine relaxable
checks included, withholds the interface checks is stated at `docs/consistency_checks.rst:
272-281` and nowhere in the spec (`SPEC.md:263-264` says only "loading continues"). Of its
test gaps, five are closed (`tests/test_analysis.py:909-1000`, `:343`, `:1290-1345`,
`:1049-1080`, `tests/test_models.py:334-345`); the rest are listed under "Test gaps".

What passes 1 and 2 forwarded, settled from the code. Pass 1 Important 5: a delivery
comparison does compare the enumerators - `compare.py:128-132` reads
`conversion_identity(o.conversion)`, which for an enum is `("enum", name, tuple((entry.name,
entry.value) ...))` (`models/conversion.py:260-265`), descriptions left out; `M02` prints
`conversion: enum(Mode_t: OFF=0, ON=2) != enum(Mode_t: OFF=0, ON=1)` and the description-only
edit on `Mode2_t` is silent, so 4.1 should say "an enum by its name and its ordered
enumerators". Pass 1 Minor 5: confirmed, Minor 8 above. Pass 1 Minor 6: `"Hi"` and
`[72, 105, 0, 0]` compare unequal, Important 2 above. Pass 1 Minor 12's `duplicate-type` split:
confirmed at `C28`, Minor 8 above. Pass 1 Important 1: the renames id of an array element is
`j1j1j1j1j1j1[0].a` and of a scalar instance's member `k9k9k9k9k9k9.a` (`M02`, `M06`,
`compare.py:201-205`, `:303`) - the spec's "followed by `.`" is wrong for an element, the code
is consistent. Pass 2's two items: a quoted number nested in a list init reaches the analysis
as the number - `C24` `Q3` `["1", "300"]` earns `init value 300 does not fit into uint8`, so the
coercion happens in the model and nothing in the analysis can tell; the per-enclosing-list
`schema` findings of a wrong nested init are the loader's and the file never reaches the
analysis. Neither is a defect of section 4.

### Open questions

1. Is `init` compared as bytes or as spelled (Important 2)? Bytes changes `compare.py:182` and
   makes the strings migration silent; spelled changes 4.1 and 5.3 and keeps `--strict` failing
   a respelling.
2. Should `-W` overrides reach a description baseline's own analysis? `_read_baseline`
   (`cli.py:1408`) analyses it with the run's overrides and without `--strict`; `N03` (h):
   `-W unused-output=error` carries the predecessor's unread output as `error[unused-output]: in
   the baseline: ...` and refuses a verdict, `--strict` does not. A project gating with
   `-W missing-id=error` (`docs/consistency_checks.rst:659-660`) against an older description
   baseline without ids fails on the predecessor. The answer changes either `_read_baseline`'s
   policy or the sentence at `SPEC.md:1393-1396`.
3. Is a reference a read for `unused-output`? `C07`: axes produced by `A` and referenced only by
   `B`'s map are `unused-output`, while for `local-conflict` "a reference is a use as much as a
   declaration is" (`SPEC.md:1198-1199`). Counting referrers changes `_consumers`
   (`analysis.py:2840-2842`) and the demo transcripts; not counting them wants one sentence in 4.
4. Is a diagnostic's json `location.path` absolute, as the reference page says, or as typed, as
   `generate`'s `generated` payload is (Important 3)?

### Test gaps

- `tests/test_calibration.py`: an axis whose `input` names a structured measurement instance is
  `reference-kind` and the A2L names no such measurement (Important 1).
- `tests/test_compare.py`: a scalar init against its broadcast list and a byte list against its
  text on a string, whichever way question 1 goes (Important 2); a baseline whose `format` is
  `"9"` or `9.0` (Minor 7); `-W x=error` reaching a description baseline (question 2).
- `tests/test_cli.py`: the `location.path` of a comparison finding under `--format json`
  (Important 3); the renames file not written when a side cannot be read
  (`test_an_unreadable_baseline_is_reported`, `:422`, checks the message only; previous gap,
  still open); a standalone run with a silenced non-project cause (Minor 6).
- `tests/test_analysis.py`: a reported `reference-kind` beside a silenced transitive absence
  yields no `incomplete-project` (Minor 1); `duplicate-id` between a dropped and a surviving
  declaration (Minor 2); a text init on a dropped non-string declaration (Minor 3); the
  pointer of the enumerator finding on a declaration (Minor 4); three producers give two
  findings (`test_multiple_producers`, `:33`, uses two and asserts membership; previous gap);
  the 1e-9 tolerance inside the band (no test names `isclose` or a value inside it; previous
  gap); a `typename` producer against an equivalent inline consumer checking clean
  (`tests/test_structures.py:825-826` names the type on both sides; previous gap);
  `consumer-raster` and `raster-kind` both on one declaration (`tests/test_rasters.py:396`,
  `:407` test each alone, `SPEC.md:1042` now states both; previous gap).
- `tests/test_models.py`: `duplicate-id` reported on the second in name order when the load
  order differs (`test_two_objects_may_not_share_an_identity`, `:360`, loads in name order;
  previous gap, `C12` shows the behaviour is right).

### Assessment

Section 4 is implemented as written, and the parts the previous review found broken are now
the strongest: dropped declarations count for ownership, every silenced drop leaves an
`incomplete-project` trace, a dangling reference drops its referrer, a reference into a `local`
is the conflict it is, types are checked once where they are declared, and the comparison's
verdict, renames, formats and plugins behave as 4.1 states in every configuration tried. What
remains is at the edges. One check gap reaches a generated file: an axis indexed by a structured
instance is accepted and the A2L then names a measurement that does not exist. One comparison
rule decides a `--strict` verdict on the spelling of an initial value rather than on its bytes,
which the spec has not yet said either way. And one contract of the reference page - an absolute
`location.path` in json - is broken for exactly the findings a comparison produces. The rest are
small consistencies in where a finding sits or which census a check reads, and three prose
drifts between the docs table and the spec.

### Verification

Every candidate of this pass was handed to a second reviewer (group B): 12 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P3-I1 | Important | CONFIRMED | Important | `analysis.py:2700` `elif found.kind is not _EXPECTED_KIND[key]:` reads the kind only; ran `cases/I1` (struct `S_t`, instance `Inst`, axis `Cx` with `"input": "Inst"`, curve `Cu`): `ddd check` -> `ok: 3 variables in 2 components are consistent`; `ddd generate a2l` -> `0x00000000 Inst RL_AXIS_UWORD 0 NO_COMPU_METHOD 2 0 65535`, `COM_AXIS Inst NO_COMPU_METHOD 2 0 65535`, the only measurement `/begin MEASUREMENT Inst.a`; `a2lcheck.py`: "AXIS_PTS Cx input: references MEASUREMENT 'Inst', which is not defined"; the same instance as a curve's `axis` (`cases/I1b`) is refused `error[reference-kind]` |
| P3-I2 | Important | CONFIRMED | Important | `compare.py:182` `ComparedField("init", lambda o: o.init, ...)`; `cases/I2`, baseline `init: 7` on `uint8[4]` and `[72, 105, 0, 0]` on a string, candidate `[7, 7, 7, 7]` and `"Hi"`: `warning[changed-storage]: 'Arr': init: (7, 7, 7, 7) != 7`, `'Str': init: "Hi" != (72, 105, 0, 0)`, "can replace", exit 0; `--strict` (own warnings silenced) -> `2 errors`, `project.ddd.json cannot replace base.json`, exit 1; the generated c is `uint8_t Arr[4] = { 7U, 7U, 7U, 7U };` in both and `{ 72U, 105U, 0U, 0U }` versus `"Hi"`, the same four bytes |
| P3-I3 | Important | CONFIRMED | Important | `cli.py:649` `location = Location(args.candidate)`, `Location.to_dict` (`diagnostics.py:322`) writes `self.path.as_posix()`; `ddd compare base.json cand/project.ddd.json --format json` from `cases/I2` -> `"path": "cand/project.ddd.json"` on `project-mismatch`, both `changed-storage` and `added-object`, beside `"path": "C:/Users/.../cases/I2/cand/sub/deep/p.ddd.json"` on the candidate's own `unused-output` and `missing-id`; `consistency_checks.rst:975` "``location`` is an absolute, forward-slashed path"; in text mode `unused-output` printed before `project-mismatch` |
| P3-M1 | Minor | CONFIRMED | Minor | `analysis.py:2671`; `cases/M1` with `-W unknown-constant=ignore`: at `interface[2].definition.input` both `error[reference-kind]: the input of axis 'Az' must be of kind 'measurement', but 'Cv' is of kind 'curve'` and `info[incomplete-project]: 'Az' is not in the data dictionary: its input 'Cv' did not resolve, and the finding that says why is not reported` |
| P3-M2 | Minor | CONFIRMED | Minor | `analysis.py:1783` `for name, refs in ordered:` over the surviving `_refs`; `cases/M2` (`Gamma` of unknown type, `Delta`, one id): `error[unknown-type]` alone, `1 error`; `cases/M2b` (both resolve): `error[duplicate-id]: 'Gamma' carries the id 'abcdefghjkmn', which 'Delta' already carries` |
| P3-M3 | Minor | CONFIRMED | Minor | `analysis.py:3137` sits in `_check_string_init`, reached from `_check_init_shape` (`:3107`), called at `:3019` in `_build_variable` only; `cases/M3`: `D1` (`"dimensions": ["NOPE"]`, `"init": "text"`) -> `unknown-constant` alone while `D2` (`"init": 300`) also gets `init-invalid`; with `-W unknown-constant=ignore` `D1` gets `incomplete-project` and the text init is never reported |
| P3-M4 | Minor | CONFIRMED | Minor | `analysis.py:2307` `location = ref.location("definition")`; `cases/M4`: `c.ddd.json#component.interface[0].definition: error[init-invalid]: enumerator(s) B=256 of enum 'E_e' do not fit into uint8` against `t.ddd.json#types[0].conversion: error[init-invalid]: enumerator(s) ON=300 ...` |
| P3-M5 | Minor | CONFIRMED | Minor | `analysis.py:2556-2557` `owning = [...] or producers` then `owning[0]`; `cases/M5` with `-W local-conflict=ignore`: `ddd list abc.ddd.json` -> `X ... A (local)  C`, `ddd list bac.ddd.json` -> `X ... B  C` |
| P3-M6 | Minor | CONFIRMED | Minor | `diagnostics.py:208-211` flags `incomplete-project` `needs_every_component=True`; `cases/M6` `ddd check c.ddd.json --standalone -W dimension-value=ignore` -> `4 infos` (all `missing-id`), exit 0, `ddd list --standalone ...` lists `W` alone, `V`, `Ax`, `Obj` gone unmentioned; the same `-W` without `--standalone` prints three `info[incomplete-project]` |
| P3-M7 | Minor | CONFIRMED | Minor | `loading.py:459` `if not isinstance(found, int) or ... : return True`; the `cases/I2` dump re-spelled `"format": "9"` and `"format": 9.0` -> `project.ddd.json can replace f9str.json` / `f9flt.json`, exit 0; `"format": 9` -> `f9int.json#format: error[schema]: in the baseline: this dictionary is in format 9, and this DDD understands up to 8`, exit 1 |
| P3-M8 | Minor | CONFIRMED | Minor | (a) `consistency_checks.rst:619` "an exported object"; `cases/M8a`: `Hidden4` (`"export": false`, input of an exported axis) -> `warning[a2l-unrepresentable]`, `Hidden5` (hidden, unreferenced) silent; (b) `:397-403` "The declaration is dropped"; `cases/M8b` -> `info[incomplete-project]: ... it names the type 'S_t', and the dimension-value that says why the type is unusable is not reported`; (c) `cases/M8c` -> `t.ddd.json: error[schema]: Value error, type 'W_t' is already declared in this file`, located at the whole file |
| P3-M9 | Minor | CONFIRMED | Minor | `analysis.py:2214-2221` `continue`s before `_check_declared_name`; `cases/M9` (second `input Dup` with `init`, `section ".nope"`, `raster "r"`, enumerator `int`): `duplicate-declaration`, `unknown-raster`, `unknown-section`, `3 errors`, no `consumer-storage`, no `reserved-identifier` |

## Pass 4: the generated artefacts, the address information and the dictionary (SPEC.md sections 5 and 6)

### Scope covered

Read in full: `SPEC.md:1508-1781`; `src/ddd/ir.py`; `src/ddd/backends/__init__.py`, `base.py`,
`c/{__init__,backend,literals,model,options,types}.py`,
`a2l/{__init__,backend,model,options,types}.py`, `a2l/templates/project.a2l.jinja`;
`src/ddd/build_info.py`; the five `examples/templates/*.jinja2`;
the dictionary reader `src/ddd/loading.py:420-467`; the checks the outputs depend on
(`src/ddd/analysis.py:127`, `:1540-1585`, `:1648-1668`, `:1860-1885`, `:2325-2370`, `:2440-2502`,
`:2900-2937`, `:3020-3045`, `:3085-3165`, `:3200-3225`, `:3273-3289`); the models the backends call
(`src/ddd/models/common.py:40-160`, `:160-340`, `objects.py:1-200`, `:400-450`, `:750-870`,
`conversion.py:30-309`, `constants.py`, `component.py:30-100`, `sections.py:1-60`);
`src/ddd/cli.py:60-130`, `:187-260`, `:420-560`, `:677-1010`, `:1356-1490`;
`docs/generated_artefacts.rst`, `docs/templates.rst`, `docs/data_dictionary.rst`,
`README.md:600-725`, `CHANGELOG.md:1-90`, `docker/compile.sh`, `docker/verify_symbols.py`,
`docs/superpowers/specs/2026-09-10-string-conversion-design.md` (whole, section 7 in detail);
`previous-review.md:1124-1248`; the forwarded items of `reports/pass-1.md`, `pass-2.md` and
`pass-3.md`.

Ran (scratch under `scratchpad/pass-4/`): `ddd generate all ... --dictionary` on
`examples/demo` (plain and `--const-inputs`), `examples/structures`, `examples/vocabulary`,
`examples/layout`, `examples/pressure/release`, on `examples/demo/components/controller.ddd.json`
alone and on `examples/inconsistent` with `--force`; `ddd dump`, `ddd dump -o` and
`ddd schema dictionary` for each; a reproduction of `docker/compile.sh` with MinGW gcc 13.1
(`compile.sh`: one translation unit per header including it twice, `-std=c11 -Wall -Wextra
-Wpedantic -Werror -Wconversion -Wshadow -Wcast-qual -Wstrict-prototypes`, link, run, `nm` against
`docker/verify_symbols.py`) on every generated directory, the demo also with `-DFEATURE_X`; an A2L
well-formedness checker (`a2lcheck.py`: block nesting, every reference resolved, field counts,
number spellings, encoding) and a schema validator (`dictcheck.py`, `jsonschema`) on every A2L and
dictionary; 28 probe projects written by `probes.py` (strings, every datatype in every shape and
kind, structures with arrays and bits and strings, enums, constants, broadcast, descriptions with
comment and quote injection, a2l options with sections and rasters, empty projects, names at the
cap and differing by case, five name clashes, the axis whose input is an instance, dangling
references under `-W unknown-reference=ignore`, float underflow, compu method sharing, four
dimensions, limits artefacts); 30 template and write-step scenarios (path clashes including case,
helper-only and nonexistent directories, undefined names, syntax errors, `1/0`, a per-component
error, an include escaping the directory, `--dictionary` clashes including case and `sub/..`,
`--dry-run --format json`, an output directory that is a file, a target that is a directory,
stale staging files, mtimes); 12 address maps on the demo and the two-run flow; the demo with
its components included in another order; `--byte-order big`.

### Strengths

- Every example and every probe that the checks admit compiles warning-free under the CI flag
  set, links, runs, and `nm` agrees with the dictionary (`22 of 23 declared variables are
  defined, conditional, absent : ValueG` for the demo; 23 of 23 with `-DFEATURE_X`; the same with
  `--const-inputs`; 88 objects of 11 datatypes in 8 shapes and kinds; 80 leaves of nested
  structures with arrays, bitfields and strings).
- The C literals are right at every extreme probed: `(-9223372036854775807LL - 1)`,
  `18446744073709551615ULL`, `4294967295U`, `3.4028234663852886e+38F`, `1e-07F`, `1e+308`, `-0.0`,
  `1`/`0` for booleans, the string literal `"a\"b\\c\?d\?\?/e\?\?=f%g//h/*i*/j'k"`, a scalar init
  broadcast over `[2][2][2]` and over a curve's and a map's axis-given shape, arrays declared by
  a constant's name (`Cu[C_N]`) and sized by its value, `const volatile` composed on every kind.
- Every A2L generated (5 examples, 26 probes, the single component, the forced inconsistent
  project) passes the checker: balanced blocks, every `AXIS_PTS_REF`, input quantity, conversion,
  layout, `COMPU_TAB_REF` and group reference defined, three-value `MATRIX_DIM` reversed
  (`[2][3]` -> `3 2 1`), `ASCII` with `NUMBER` for calibration strings and members,
  `UBYTE`/`SBYTE` arrays with the `ANNOTATION` for string measurements, `IF_DATA XCP` from the
  object's raster or the component default and none without, `FORMAT`/`DISPLAY_IDENTIFIER` on
  all three record kinds, the export closure pulling a hidden axis and its input, `GROUP`s in
  declaration order with leaves after plain objects, `MOD_PAR` only with constants, `MSB_FIRST`
  under `--byte-order big`.
- Section 6 holds in every scenario: empty map silent, partial map `address-missing` naming the
  uncovered symbols and the unused keys in a note, `--strict` writes nothing, `--force` writes and
  exits 1, `[1]`, `1.5`, `true`, `"1e3"`, `-1`, `0x100000000` refused as usage errors with the
  symbol named, `" 0X20 "` read, and the post-link `generate a2l` run changes only the four
  address fields of the file the first run wrote.
- Determinism: byte-identical output from two runs, two directories and two working
  directories; an unchanged rerun reports `unchanged` and leaves the mtime; a stale
  `.ddd-staging` is overwritten and removed; `--dry-run` creates not even the directory;
  `dump -o` and `--dictionary` are byte-identical and equal to `dump`'s stdout modulo the
  console's newline; every dictionary validates against `ddd schema dictionary` with exactly the
  fourteen top-level keys of 5.3, format 8.
- The write step's promises hold under failure: a template error, a clash (two templates, a
  template against the A2L, a case variant on Windows, `--dictionary` on an artefact by another
  spelling) or a directory in the way leaves no file and no staging file behind; the one
  documented exception (an already-renamed update) is exactly what happens.
- The template contract is documented completely: every attribute the c model exposes
  (`CodeModel`, `ObjectView`, `MemberView`, `StructView`, `ComponentGroup`, `DeclarationView`,
  `ComponentHeaderView`, `ConstantView`, `EnumView`, `SectionGroup`, `guard()`) is in
  `docs/templates.rst:164-341`, every documented one exists, `StrictUndefined` and the helper
  rules behave as described, and the example templates use nothing undocumented.

### Issues

#### Critical

None found.

#### Important

1. **A description containing `/*` produces a header that fails the CI flag set**
   (`src/ddd/backends/c/literals.py:132`: `return collapsed.replace("*/", "* /")`). Trigger: any
   `description` (or `unit`, enumerator, member, structure or constant description) containing
   `/*`, for example `"opens a comment /* inside"` -> the example templates write
   `/** opens a comment /* inside */` and gcc reports `D.h:25:21: error: "/*" within comment
   [-Werror=comment]` in every header and in `ddd_globals.c` (probe `descriptions`; `-Wcomment` is
   in `-Wall`, and `-Werror` is the set `docs/generated_artefacts.rst:365-366` verifies with).
   `docs/templates.rst:265-267` promises `.comment` is "already defused, so that a `*/` in a
   description cannot end the comment"; the opening marker is the other half of the same
   promise. Fix: `sanitize_comment` also replaces `/*` (and `//` is harmless but could go the
   same way), with a test beside `tests/test_generation.py:98`.

2. **Non-ASCII units and descriptions reach the 1.61 A2L as raw UTF-8 with nothing declaring
   it** (`src/ddd/backends/a2l/model.py:659-662`: `a2l_string` escapes `\` and `"` and replaces
   control characters, passes everything else; `SPEC.md:1613` "Files are written UTF-8"). Trigger:
   `"unit": "°C"` - the most common non-ASCII unit - or a description with `é` -> `RAT_FUNC
   "%8.3" "°C"` as the bytes `C2 B0`, no byte order mark (probes `descriptions`, `compu`;
   `a2lcheck.py` flags `°`, `²`, `µ`, `é`, `Ω`, `中`). ASAP2 1.6.1 has no encoding declaration
   (`ENCODING` arrives with 1.7, which the string design at
   `docs/superpowers/specs/2026-09-10-string-conversion-design.md:40-42` acknowledges for the
   string *content* it therefore restricts to ASCII), so a reader either applies its code page
   and shows `Â°C`, or refuses the token. The backend already knows how to transliterate: the
   method *name* for `°C` is `CM_LIN_DEGC` (`_UNIT_WORDS`, `:631-641`) while the unit *string*
   beside it is not. Unconfirmed against a calibration tool - opening the probe's A2L in CANape
   would confirm which of the two outcomes it is. Fix: decide the policy (transliterate the
   quoted strings with the same table, write a BOM, or report an `a2l-unrepresentable`-style
   warning for non-ASCII text) and say it in 5.2.

3. **Derived limits are written as the binary product, so an A2L upper limit can fall below the
   physical value of the datatype's own maximum** (`src/ddd/models/conversion.py:279-281`:
   `low = conversion.to_physical(raw_min)` ... in double arithmetic;
   `src/ddd/backends/a2l/model.py:372-373` and `:397-398`: `format_number(entry.limits.min)`).
   Trigger: `uint8` under `{"factor": 0.03}` with no `limits` -> `UBYTE CM_LIN_U 0 0 0
   7.6499999999999995` (probe `limits-verdict`), `sint16` under `0.7` -> `22936.899999999998`,
   `sint16` under `0.1` -> `3276.7000000000003` (`examples/layout` itself:
   `LayoutDevice.a2l:42` `SWORD CM_LIN_DEGC 0 0 -3276.8 3276.7000000000003`), an `sint64` under
   `{"factor": 1}` -> `-9.223372036854776e+18 9.223372036854776e+18`, one past the raw range. The
   dictionary carries the same numbers (`"max": 3276.7000000000003`). A calibration tool that
   enforces the limits then refuses the physical value of raw 255 (`7.65`), and the engineer
   reading the file sees a limit that is not the one the description implies. The tool itself
   knows the arithmetic is approximate: `ddd check` accepts a stated `max: 7.65` against the
   derived `7.6499999999999995` only through `rel_tol=1e-9` (`src/ddd/analysis.py:3284-3289`),
   and a reading is rounded to 12 significant digits for exactly this reason
   (`conversion.py:299-306`), but the limit written to the file and the dump is not. Fix: round
   the derived physical range the way readings are rounded (or compute it from the decimal
   spelling), in `physical_range`, so every consumer gets `7.65`.

4. **An axis whose `input` names a structured measurement instance binds the A2L to a name that
   has no record** (carried over from pass 3 Important 1, confirmed from the backend:
   `src/ddd/backends/a2l/model.py:412` `input_quantity=axis.references.get("input") or
   NO_INPUT_QUANTITY,` and `:425`, written verbatim; `_resolve_exported`, `:312-323`, pulls only
   what `by_name` - the plain objects - holds, so the instance is never a record). Trigger (probe
   `axis-input-instance`): structure `S_t {a}`, instance `Inst`, axis `Cx` with `"input":
   "Inst"`, a curve over `Cx` -> `ddd check` is clean, and the A2L carries `AXIS_PTS Cx ...
   0x00000000 Inst RL_AXIS_UWORD ...` and `COM_AXIS Inst NO_COMPU_METHOD 2 0 65535` while the
   only measurement is `Inst.a` (`a2lcheck.py`: "AXIS_PTS Cx input: references MEASUREMENT
   'Inst', which is not defined"). What a tool sees is an unresolved input quantity: the ASAP2
   checkers report it, and a tool either drops the reference or refuses the module - the outcome
   `SPEC.md:1698-1701` argues the closure exists to prevent. Fix: pass 3's (refuse a structured
   target of `input` as `reference-kind`); in the backend, a defensive fallback to
   `NO_INPUT_QUANTITY` when the name is not in `self._by_name`.

#### Minor

1. **A runtime error inside a helper template is reported at the helper's line under the
   importing template's name** (`src/ddd/backends/base.py:294` `where = f"template
   '{template_name}'"`, `:311-317` `_template_line` takes the deepest jinja frame's line only).
   Trigger: `_h.jinja2` with `{{ none.x }}` on its line 4, imported and called from line 6 of
   `bad.h.jinja2` -> `ddd: cannot render template 'bad.h.jinja2', line 4: 'None' has no attribute
   'x'`; line 4 of `bad.h.jinja2` is blank. Fix: read the template name off the same frame
   (`f_globals["__jinja_template__"].name` or `f_code.co_filename`) and name it when it differs.

2. **The example type header, and every header of an object-less project, is an empty
   translation unit under `-Wpedantic -Werror`** (`examples/templates/ddd_types.h.jinja2:6-11`
   includes `<stdint.h>` only when an integer datatype exists; `docker/compile.sh:67-69`
   compiles every header alone). Trigger: a project whose objects are all `float32`/`float64`
   (probe `float-underflow`), or a constants-only or empty component (`onlyconstants`,
   `noobjects`) -> `tu_ddd_types.c:4: error: ISO C forbids an empty translation unit
   [-Werror=pedantic]`, and for the empty project `ddd_globals.c` fails the same way. The
   shipped verification therefore fails on a legitimate float-only project. Fix: have the
   example type header always include `<stdint.h>` (or `<stddef.h>`), or give the harness's
   translation units one declaration.

3. **`float32` init below the subnormal range still compiles to an error** (previous review
   Minor 2, still open; `src/ddd/analysis.py:2358` checks magnitude against `raw_max` only).
   Trigger: `"init": 1e-50` on a `float32` -> no finding, `float F32Tiny = 1e-50F;`, gcc `error:
   floating constant truncated to zero [-Werror=overflow]` (probe `float-underflow`; `1e-40`, a
   denormal, compiles). Fix: `init-invalid` when `struct.pack("f", value)` rounds a non-zero
   value to zero.

4. **A `#define` of an extreme whole constant is not the literal its author meant**
   (`src/ddd/backends/c/model.py:195-197` "it is already a c literal of the type its author
   meant"; `examples/templates/ddd_types.h.jinja2:23`). Trigger: `"value":
   -9223372036854775808` or `18446744073709551615` (both accepted since constants hold any
   number) -> `#define C_I64MIN -9223372036854775808`, `#define C_U64MAX 18446744073709551615`;
   used in an expression gcc says `warning: integer constant is so large that it is unsigned`
   (probe `constants`, `use_constants.c:2:39` and `:2:72`), and the first is the unsigned
   `9223372036854775808` negated rather than `INT64_MIN` - the very case `c_literal`
   (`literals.py:31-36`) spells out for an init. Fix: offer a `literal` (or `c_literal`)
   property on `ConstantView` built by `c_literal`'s rules, and temper the docstring.

5. **A scalar `init` is carried unexpanded although the field says "nested to match shape"**
   (`src/ddd/ir.py:187-189`; previous review pass 7 design note 5, unchanged). Evidence: the
   demo's `ValueB` dumps as `"init": 0` with `"shape": [4]` while `ValueK` dumps as a nested
   list; `src/ddd/backends/c/literals.py:87` broadcasts it (`broadcast(entry.init,
   entry.shape)`). `SPEC.md:1745` lists `init` without saying which; a third-party generator
   reading the dictionary has to know to broadcast. Fix: say it in 5.3 and in the docstring (or
   normalise in the analysis). The other half of that note also stands: `leaves` grows with
   every element of an array of structures (80 leaves for three instances in probe `structs`).

6. **`ResolvedComponent.source` docstring says "Path of the description file"** (`src/ddd/ir.py:98`;
   previous Minor 6, still open). The dump carries the file name (`"source":
   "controller.ddd.json"`, `"event_logger.ddd.json"` for a file two directories down), which is
   what keeps the banner machine-independent. Fix: "file name".

7. **The container transcript in the docs counts the demo before the strings landed**
   (`docs/generated_artefacts.rst:399-402`: `20 of 21 declared variables are defined` /
   `21 of 21`). The demo now has 22 objects and one instance: `compile.sh` prints `22 of 23`
   and `23 of 23`. Fix: update the transcript (it is outside `tests/test_transcripts.py`).

8. **`_UNIT_WORDS` transliterates `°`, `µ`, `Ω` and `%` but not `²` and `³`**
   (`src/ddd/backends/a2l/model.py:631-641`). Trigger: `"unit": "m/s²"` -> method
   `CM_LIN_M_PER_S`, the same name `m/s` would get, so whichever is met second becomes
   `CM_LIN_M_PER_S_2` (probe `compu`: `m/s^2` -> `CM_LIN_M_PER_S2`, `m/s²` -> `CM_LIN_M_PER_S`,
   `m per s` -> `CM_LIN_M_PER_S_2`). Deterministic, but the readable name the docs promise
   (`docs/generated_artefacts.rst:790-792`) is lost for the spelling most people type. Fix: add
   `"²": "2"`, `"³": "3"`.

9. **5.2 says "`COMPU_VTAB` per enum"; a table is written only for an enum some record uses**
   (`SPEC.md:1637`, `docs/generated_artefacts.rst:682-683` "one per enum conversion";
   `src/ddd/backends/a2l/model.py:739-750` creates the table from `reference()`). Evidence:
   `examples/structures` dumps `SensorMode_t` under `enums`, and `StructuredDevice.a2l` has no
   `COMPU_VTAB` because its only user is a `bits` member. Right behaviour; the sentence should
   say "per enum a record refers to".

10. **The example plugin's header does not compile on its own**
    (`examples/plugins/ddd_layout.py:255` `sizeof({entry.name}), &{entry.name}` without any
    include of a declaration, `:261`).
    Trigger: `compile.sh` on `examples/layout` -> `ddd_layout.h:18:23: error: 'EngineHours'
    undeclared here`. `docker/compile.sh` accepts any project and compiles every header alone,
    so the shipped example fails the shipped harness. Fix: emit `#include "ddd_globals.h"` (or
    document that the header is to be included after a component header).

11. **Windows file-name traps are not anticipated for a generated header**
    (`src/ddd/analysis.py:1648-1668` checks component names for case only). Two mechanisms,
    both unconfirmed here: a component
    named `Aux`, `Con`, `Nul`, `Prn`, `Com1`..`Com9` or `Lpt1`..`Lpt9` asks for a file Windows 10
    cannot create (`Aux.h` is a device name; this Windows 11 build creates it, so only an older
    Windows would confirm it); and a 128-character component name in a build directory a hundred
    characters deep exceeds `MAX_PATH` without long-path support - observed: `ddd: cannot write
    '.../Cyyy...yyy.h': No such file or directory` (277 characters, probe `names`), the run
    rolled back cleanly. Both end as usage errors, not crashes; the second message could say
    the path is too long.

12. **A nonexistent or non-directory `-t` is reported as an empty one** (previous Minor 3,
    still open; `src/ddd/backends/c/backend.py:94-101`): `-t does-not-exist` and `-t
    examples/templates/_macros.jinja2` both print `no template to render in ...`.

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| I1 | dangling references reach both artefacts once `unknown-reference` is ignored | fixed for objects: they leave the dictionary with `incomplete-project` (probe `dangling`: no record, no definition); the verbatim `input` remains and is this pass's Important 4 for a structured target | `src/ddd/analysis.py`, `src/ddd/backends/a2l/model.py:412`, `:425` |
| I2 | `COMPU_METHOD` sharing key omits the display format in the spec | fixed | `SPEC.md:1633-1637`, `:1675-1683` |
| I3 | export closure: an axis exported in its own right pulls its input | fixed | `SPEC.md:1698-1701` |
| I4 | the display-format rule of 5.2 does not describe what is emitted | fixed | `SPEC.md:1688-1693` |
| I5 | JSON `true`/`false` accepted as an integer init | consciously left (brief) | `src/ddd/models/objects.py:33` |
| I6 | A2L file name and output directory not in 5.2 | fixed | `SPEC.md:1660-1661` |
| I7 | docs name `ddd list --format json` for the symbol check | fixed | `docs/generated_artefacts.rst:396` |

Minor: 1 fixed (`base.py:116` "rename the component or the template"), 4 fixed (`cli.py:244-247`),
5 fixed (`README.md:626`), 7 fixed (`SPEC.md:1764` "JSON integer"); 2, 3 and 6 still open (this
pass's Minor 3, 12 and 6).

Spec gaps proven from code, previous list: closed - the A2L file name and `-o` (`SPEC.md:1660`),
the record order inside `MODULE` and leaves after plain objects (`:1652-1658`), what a `GROUP`
references (`:1643-1647`), the method key and which collision keeps the bare name (`:1675-1683`),
the base datatype of an enum-converted object (`:1559-1561`), declaration order in a component
header versus name order in the definition file (`:1604-1608`), `<unresolved>` (`:1608-1610`),
`address-missing` in section 6 (`:1771-1776`), the default format on the method (`:1691-1693`),
`boolean` under a linear conversion (`:1689-1690`), `MaxDiff 0`, `DIRECT` and `INDEX_INCR`
(`:1630-1631`, `:1687-1688`), control characters in strings (`:1694-1695`). Still unstated: the
address map's whitespace stripping and `-0x` (`a2l/options.py:73-74`), the fallback of the
`HEADER`/`PROJECT`/`MODULE` text to the project name (`a2l/model.py:285`), `--dry-run` creating no
directory, the "no template" message for a nonexistent directory.

Test gaps of the previous list: `MOD_COMMON` `ALIGNMENT_*`, `HEADER` with `PROJECT_NO`/`VERSION`,
the `_2` suffix, `boolean` records, the axis-input dangling case and the `float32` underflow
are still untested (`grep` finds none of them in `tests/`); `BYTE_ORDER` with `MSB_FIRST` is
covered (`tests/test_a2l.py`), and `tests/test_cli.py` now reads `dump`'s stderr.

Forwarded items, settled from code: pass 1 Minor 4 and pass 2 Minor 4 - constants are not
carried "as written" (`SPEC.md:956`): `1e3` becomes `#define C_1E3 1000.0` and `SYSTEM_CONSTANT
"C_1E3" "1000.0"` (`a2l/model.py:291` `value=str(entry.value)`, the template's `{{ constant.value
}}`), `2.5` and `-0.0` stay, so the outputs carry Python's shortest round-trip spelling of the
parsed number and keep only its type. Pass 1 Minor 6 - a string's `init` is dumped as the JSON
string as written (`"init": "OFF"`, `"conversion": {"kind": "string"}`), an integer or list init
on a string object as numbers (`ListInit` dumps `[72, 105, 0, 0]` and still becomes an `ASCII`
record). Pass 1 Minor 10 - `references` carries `axis` for a curve, `x_axis` and `y_axis` for a
map, `input` for an axis and nothing else (`ir.py:212-213` says "keyed by field name"); a leaf's
`a2l.export` is the instance's and the member's answers folded into one boolean
(`analysis.py:2912`, `_carries` reads only it); the `owner` of an unowned object is `null` in the
dictionary and `<unresolved>` in the c (`ir.py:215`, `c/model.py:523`). Pass 2 Important 1 -
a nested quoted number reaches the outputs as the number the loader read (`{ 1U, 2U }`); the
outputs add nothing to that finding. Pass 3 Important 1 - confirmed above (Important 4).

### Open questions

1. Which encoding policy the 1.61 A2L should have for non-ASCII units and descriptions
   (Important 2): transliterating the quoted strings with the `_UNIT_WORDS` table, writing a
   BOM, or a warning. The answer decides whether `°C` may appear in a description file of a
   project that generates an A2L.
2. Whether derived limits should be rounded to 12 significant digits like readings or computed
   from the decimal spelling (Important 3); either changes the dictionary of every project with a
   decimal factor and therefore every archived baseline's `changed-interface` verdict on limits.
3. Whether the shipped verification (`docker/compile.sh` and the example templates) is meant to
   hold for a float-only or object-less project (Minor 2), and for the example plugin (Minor 10).
4. Whether `ConstantView` should offer a C literal (Minor 4) now that constants hold any number,
   or the template contract should say the value is the bare number.

### Test gaps

- A description, unit or enumerator text containing `/*` renders a comment gcc accepts
  (`tests/test_generation.py`, beside the `*/` case at line 98).
- A non-ASCII unit in the A2L, whatever the policy becomes (`tests/test_a2l.py`).
- The spelling of a derived limit under a decimal factor (`7.65`, not `7.6499999999999995`) in
  the A2L and the dictionary (`tests/test_a2l.py`, `tests/test_analysis.py`).
- An axis whose `input` is a structured instance (`tests/test_analysis.py`, `tests/test_a2l.py`).
- A helper template raising: the message names the helper (`tests/test_generation.py`).
- The compile harness on a float-only and on an empty project (`tests/test_cmake.py` or the
  container target).
- `MOD_COMMON` alignments, `HEADER` fields, the `_2` suffix on a colliding method name, a
  `boolean` measurement and characteristic, and `float32` underflow - carried from the previous
  list (`tests/test_a2l.py`, `tests/test_generation.py`).
- `--dictionary` refused for a case variant of an artefact path, and `render`'s clash on a
  case variant of a `{component}` file (`tests/test_cli.py`, `tests/test_backends.py`; a
  `WindowsPath`-only behaviour, so the test has to be platform-aware).

### Assessment

Sections 5 and 6 hold up under everything that could be compiled or checked: five examples and
twenty-six probes covering every datatype, shape, kind, conversion and structure form compile
warning-free under the CI flag set and link to exactly the symbols the dictionary promises,
every A2L is well-formed with every reference resolved, the address map behaves as section 6
says in twelve variants, the dictionary validates and round-trips, and generation is
deterministic to the byte with a write step that fails cleanly. The defects are at the edges of
text and arithmetic rather than in the mapping: a `/*` in a description breaks the compile that
`*/` was defused for, non-ASCII text reaches a format that cannot declare its encoding, derived
limits carry binary artefacts that the tool's own check knows to tolerate but the file does
not, and the one dangling reference left after the previous fix - an axis input naming a
structured instance - still writes a name the A2L does not define. None of the four needs a
design change; each is a few lines in one place, and the strings, constants and dictionary
work that landed since 0.9.0 is implemented as its design says.

### Verification

Every candidate of this pass was handed to a second reviewer (group B): 16 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P4-I1 | important | CONFIRMED | Important | `literals.py:132` `return collapsed.replace("*/", "* /")`; `cases/I4` description `opens a comment /* inside` -> `/** opens a comment /* inside */`; gcc under the CI flags: `out/D.h:21:21: error: "/*" within comment [-Werror=comment]`, likewise `ddd_globals.h:25:21` and `ddd_globals.c:23:21`, `[base] compile failed`; `templates.rst:265-267` promises `.comment` "already defused" |
| P4-I2 | important | CONFIRMED | Important | `a2l/model.py:652-662` `a2l_string` passes every non-control character; `cases/I5`: bytes `RAT_FUNC "%8.3" "\xc2\xb0C"` and `/begin MEASUREMENT Desc "temp\xc3\xa9rature du capteur"`, no BOM, `ddd check` clean; ASAP2 1.6.1 section 1.5.2 (page 16): the encoding "is defined in a Byte-Order Mark", `EF BB BF` UTF-8, and "If no encoding can be detected, ISO-8859-1 (Latin-1) encoding is used" - so a conforming reader decodes the unit as `Â°C` |
| P4-I3 | important | CONFIRMED | Important | `conversion.py:279-280` `low = conversion.to_physical(raw_min)` in double arithmetic; `cases/I6` A2L: `UBYTE CM_LIN_U_2 0 0 0 7.6499999999999995` (`U8`, factor 0.03, no limits) beside `... 0 0 0 7.65` (`U8Lim`, stated, accepted by `ddd check`), `SWORD CM_LIN_U 0 0 -3276.8 3276.7000000000003`, `A_INT64 CM_LIN_C 0 0 -9.223372036854776e+18 9.223372036854776e+18`; dump `"max": 7.6499999999999995`; regenerated `examples/layout`: `LayoutDevice.a2l:42` `SWORD CM_LIN_DEGC 0 0 -3276.8 3276.7000000000003` |
| P4-I4 | important | CONFIRMED | Important | `a2l/model.py:412` and `:425` `input_quantity=... references.get("input") or NO_INPUT_QUANTITY` written verbatim, `_resolve_exported` (`:312-323`) pulls only `by_name` entries; the `cases/I1` run above: `AXIS_PTS Cx ... Inst`, `COM_AXIS Inst`, no `MEASUREMENT Inst`; duplicate of P3-I1, which is primary |
| P4-M1 | minor | CONFIRMED | Minor | `base.py:294` `where = f"template '{template_name}'"`, `_template_line` (`:311-317`) keeps the deepest jinja frame's line only; `_h.jinja2` with `{{ none.x }}` on its line 4, called from line 6 of `bad.h.jinja2` -> `ddd: cannot render template 'bad.h.jinja2', line 4: 'None' has no attribute 'x'` |
| P4-M2 | minor | CONFIRMED | Minor | `ddd_types.h.jinja2:6-11` includes `<stdint.h>` only under `needs_stdint`; `cases/P4M2` (one `float32`): the generated `ddd_types.h` holds the guard alone, `tu_ddd_types.c:4: error: ISO C forbids an empty translation unit [-Werror=pedantic]`; `cases/P4M2b` (empty component): `tu_C.c`, `tu_ddd_globals.c`, `tu_ddd_types.c` and `ddd_globals.c:17` fail the same way |
| P4-M3 | minor | CONFIRMED | Minor | `analysis.py:2358` checks `raw_min <= value <= raw_max` only; `cases/P4M3` `"init": 1e-50` on `float32`: `ddd check` -> `ok`, generated `float F32Tiny = 1e-50F;`, gcc `ddd_globals.c:20:1: error: floating constant truncated to zero [-Werror=overflow]`; `1e-40F` compiles |
| P4-M4 | minor | CONFIRMED | Minor | `c/model.py:195-197` "already a c literal of the type its author meant"; `cases/P4M4` -> `#define C_I64MIN -9223372036854775808`, `#define C_U64MAX 18446744073709551615`; `use.c` under the CI flags: `use.c:2:15: error: integer constant is so large that it is unsigned [-Werror]` and `:3:24`; a warning without `-Werror` |
| P4-M5 | minor | CONFIRMED | Minor | `ir.py:187` "Raw initial value, nested to match ``shape``"; the `cases/I2` base dump carries `Arr` with `"shape": [4]` and `"init": 7`; restates the previous review's design note 5 (`previous-review.md:1672`) |
| P4-M6 | minor | CONFIRMED | Minor | `ir.py:98` "Path of the description file"; the `cases/I2` base dump of `sub/deep/p.ddd.json` carries `"source": "p.ddd.json"`; the previous review's Minor 6 (`previous-review.md:1197`), unchanged |
| P4-M7 | minor | CONFIRMED | Minor | `generated_artefacts.rst:399` "20 of 21 declared variables are defined", `:402` "21 of 21"; the demo regenerated into `verify-B/ex/demo` and run through the compile harness prints `22 of 23 declared variables are defined / conditional, absent : ValueG` and `23 of 23 ... conditional, present: ValueG` |
| P4-M8 | minor | CONFIRMED | Minor | `a2l/model.py:631-641` `_UNIT_WORDS` has no `²`; `cases/I5`: `m/s` -> `CM_LIN_M_PER_S`, `m/s²` -> `CM_LIN_M_PER_S_2` (the collision suffix), `m/s^2` -> `CM_LIN_M_PER_S2` |
| P4-M9 | minor | CONFIRMED | Minor | `SPEC.md:1637` "and `COMPU_VTAB` per enum"; `_vtab` is reached only through `reference()` -> `_create` (`a2l/model.py:521-551`); `examples/structures` dump lists `enums: ['SensorMode_t']`, its only user the leaf `Inlet.status.mode` with `bits: 2`, and `StructuredDevice.a2l` contains no `COMPU_VTAB` |
| P4-M10 | minor | CONFIRMED | Minor | `ddd_layout.py:255` `sizeof({entry.name}), &{entry.name}` after includes of `<stddef.h>` and `<stdint.h>` only (`:239-240`); `compile.sh` on `examples/layout` regenerated: `ddd_layout.h:18:23: error: 'EngineHours' undeclared here (not in a function)` |
| P4-M11 | minor | CONFIRMED | Minor | long-path half: `cases/P4M11b` (component `C` + 127 `y`) -> `ddd: cannot write '.../out/Cyyy...yyy.h': No such file or directory`, exit 2, a 263-character path with `HKLM\...\FileSystem\LongPathsEnabled` = `0x0`; reserved-name half: component `Aux` -> `wrote .../Aux.h (created)` on this Windows 11 (10.0.26100), unconfirmed here as the finder said |
| P4-M12 | minor | CONFIRMED | Minor | `backend.py:93-101` lists templates and reports the empty list; `-t does-not-exist` and `-t c.ddd.json` (a file) both -> `ddd: no template to render in '...': the c sources are generated from templates the project provides ...`, exit 2 |

## Pass 5: the tool interface (SPEC.md sections 3.11, 7 and 7.1)

### Scope covered

Read in full, with line numbers: `SPEC.md:1046-1142` (3.11), `SPEC.md:1782-1994` (7, 7.1),
`SPEC.md:724-759` (3.6); `src/ddd/cli.py` (all 1535 lines); `src/ddd/plugins.py` (all);
`src/ddd/build_info.py`; `cmake/Ddd.cmake` (all 676 lines); `.pre-commit-hooks.yaml`;
`pyproject.toml`; `examples/cmake/CMakeLists.txt` and its five sources;
`examples/plugins/ddd_layout.py`, `examples/layout/*.ddd.json`; `docs/command_line_interface.rst`,
`docs/build_integration.rst`, `docs/plugins.rst` (all three whole); `README.md:469-479, 720-910`;
the outlines of `tests/test_cmake.py`, `tests/test_cli.py`, `tests/test_plugins.py` and the bodies
of `tests/test_cli.py:1689-1703, 1930-1958`; the call sites the findings needed in
`src/ddd/diagnostics.py:257-330, 350-381, 398-523`, `src/ddd/loading.py:380-425, 835-930,
1092-1131`, `src/ddd/backends/base.py:60-125, 170-220`, `src/ddd/backends/a2l/options.py:40-70`,
`src/ddd/identity.py:153-183`, `src/ddd/ir.py:66-67, 127-140, 583-663`,
`src/ddd/lsp/diagnostics.py:50-60`; `docs/consistency_checks.rst:973-1007`,
`docs/comparing_deliveries.rst:580-590`, `docs/editor_integration.rst:100-140`;
`previous-review.md:1249-1421` and `:1733-1806`; the forwarded items of `reports/pass-1.md`
(Important 2, Minor 7, 8, 10), `pass-3.md` (Important 3, open question 2) and `pass-4.md`
(Minor 10-12, the write-step strengths).

Ran (everything under `scratchpad/pass-5/`; the repository was never written to, `git status`
clean at the end): every `--help`; 220 command lines over `examples/demo`, `inconsistent`,
`layout`, `pressure` and 60 fixtures written by `mkfix.py` - 24 plugin modules and projects
(printing, `sys.exit`, `KeyboardInterrupt`, a `BaseException` subclass, raising at import, a
sibling import, a mutating hook, a built-in and a foreign check identifier, a reserved name, a
case-variant, absolute and `..` output paths, a non-backend, a non-list, a directory as module, the
same file named twice, two files with one module name across root and sub-project, a dotted
module, a relative spelling run from another directory, a `@dataclass` body, a compare hook that
raises, a project model with a required setting), an encoding fixture (`°C` against `degC`, a
lone surrogate), copies of the demo for `ddd id --assign` (ids stripped, a syntax error, a
read-only file, a vocabulary and a project file), a copy under `sp ace/dé mo/`, a layout copy
with a duplicate key; `PYTHONIOENCODING=cp1252` and `ascii`, stdout redirected to files, six
commands into `| head -1`, `ddd lsp` on EOF and on one message, and one scripted server session
over pipes. CMake: `examples/cmake` configured and built from a copy under `tree/` with the
venv's CMake 4.4.3, Ninja 1.13.2 and MinGW gcc 13.1 (`-DDDD_EXECUTABLE` pointing at a copy of
`ddd.exe` so it could be touched), then a rebuild after touching a component, a template, a
helper template, the tool, the generated project file, a file outside the closure, after
breaking a component's json and after adding `STRICT`/`SEVERITY` to the call; `ninja
firmware_ddd_check`, `firmware_ddd_list`, `controller.ddd`; `build.ninja` read; nine small
projects written by `mkcmk.py` (the docs' address-map recipe under `STRICT`, a partial map,
`PROJECT` with `NAME` and a plugin, an image named `9fw-x.elf`, an image registering nothing,
two images with and without `NO_PROPAGATE_HEADERS`, the registration refusals, a vocabulary file
on an interface library, a description generated later, a component broken at configure time,
a removed component followed by `ninja -t clean`), a missing and an empty `DDD_EXECUTABLE`,
`-G "Ninja Multi-Config"`, a source and build tree under `sp ace/`;
`python -m pytest tests/test_cmake.py --no-cov -q`: 17 passed in 73 s; `pre-commit try-repo
C:/git/ac11/ddd ddd-id --all-files` in a scratch git repository (the environment installed from
the checkout in 31 s). The example plugin's header compiled with gcc alone, after
`ddd_globals.h` and after `Storage.h`, and linked with `ddd_globals.c`.

### Strengths

- The exit-code contract holds on every command probed: 0 / 1 / 2 exactly as `SPEC.md:1871-1889`
  says, `sources` and `artefacts` tolerant (exit 0 with a missing include reported on stderr,
  exit 1 only for an unreadable root), warnings alone exit 0, `--strict` promotes them, and a
  usage error raised after the analysis prints the findings first in either format
  (`cli.py:1460-1488`; observed for `--renames`, `--dictionary`, `-o`, a plugin hook, an unknown
  plugin override).
- `--format json` carries the document and nothing else on stdout for `check`, `compare`,
  `generate`, `list`, `sources`, `artefacts`, `checks`; `dump` keeps stdout for the dictionary in
  both formats and reports on stderr, `dump -o` leaves stdout empty and names the file with its
  status (`cli.py:958-1009`).
- `--without` subtracts an artefact with its options and refuses a run left with nothing
  (`cli.py:728-752, 838-849`); `--dictionary` counts as something to write and is refused on an
  artefact's path, its case variant and a `sub/..` alias (`cli.py:812-817`).
- Plugin boundary: the check hooks, the factory and `generate` are guarded (`plugins.py:405-495`);
  `sys.exit(3)` in a hook is `exit 2`, `plugin 'exiter' failed in its check hook: SystemExit(3)`;
  a module body that raises, a name outside the grammar or reserved, a check spelled with a
  built-in or another plugin's prefix, two modules claiming one name - across root and
  sub-project too - are `plugin-invalid` at `project.plugins[i]`; a `.py` spelling is resolved
  against the project file wherever the command runs from (`loading.py:847`), and a backend's
  path outside `-o`, a `..` climb, an absolute path elsewhere and a case variant of a built-in
  file are refused before anything is written (`base.py:96-119`).
- The severity machinery is one object end to end: `-W` on `check`, `compare`, `generate`,
  `list`, `dump`, `build-info`; a plugin override held provisionally and verified against the
  loaded plugins; `--standalone` derived from the registry and overridden by an explicit `-W`.
- The CMake module: every declared dependency retriggers the generation (component, template,
  helper, tool, generated project file), `restat = 1` keeps `unchanged` outputs from recompiling
  anything, a file outside the closure triggers nothing, invalid json fails the build with the
  finding, `STRICT`/`SEVERITY` reach the generation command, the check and list targets and
  `ddd-build.json` alike, an unknown check stops the configure with the tool's message, paths
  with spaces are quoted throughout, the seeded `{}` map passes `STRICT`, a partial map fails it
  with `address-missing` naming the symbols, `NAME` is sanitised (`9fw-x.elf` -> `N9fw_x.a2l`),
  `PROJECT` ignores `NAME` with a status line and names the artefacts after the file, and every
  refusal (non-`.ddd.json`, missing file, missing target, `PLUGINS` beside `PROJECT`, a second
  propagating image, a missing tool, a multi-config generator) names the fix.
- The published pre-commit hook works end to end from a git checkout: the environment installs
  with `hatchling` and `hatch-requirements-txt` from PyPI reading `requirements.txt`, the hook is
  handed every staged `*.ddd.json` at once (`nargs="+"`, `cli.py:271`), vocabulary and project
  files are no-ops, a file that is not json is skipped with exit 1, and pre-commit reports
  `files were modified by this hook`, as `.pre-commit-hooks.yaml:5-9` says.

### Issues

#### Critical

None found.

#### Important

1. **A plugin that prints to stdout corrupts the `--format json` document and the dumped
   dictionary** (`src/ddd/cli.py:1373` `dictionary = analyze(workspace, bag)` runs the hooks with
   `sys.stdout` untouched; `:898` `files = render(dictionary, backends, args.output_dir)` runs a
   plugin backend the same way). Trigger: a plugin whose check hook or `generate` contains a
   `print(...)` - a debugging line left behind - under `ddd check --format json`, `ddd generate
   ... --format json`, `ddd list --format json`, `ddd dump` or `ddd dump -o`. Outcome: stdout is
   `NOISY-CHECK-STDOUT` followed by the document, so a job's `json.loads` fails and a
   `ddd dump p.ddd.json > baseline.json` archives a file that is not json; `dump -o`, whose
   stdout `SPEC.md:1870` promises empty, carries the line. Observed (fixture `p_print.py`):
   `ddd check proj_print.ddd.json --format json` -> stdout `NOISY-CHECK-STDOUT` then `{ ... }`,
   exit 0; `ddd dump proj_print.ddd.json -o out.json` -> stdout `NOISY-CHECK-STDOUT`. The
   language server already takes stdout as the wire before a plugin runs
   (`tests/test_plugins.py:2154`); the command line does not. Fix: while hooks and plugin
   backends run, bind `sys.stdout` to `sys.stderr` (the server's arrangement), or state in
   `docs/plugins.rst` that a hook must not write to stdout.

2. **An output path that is one of the run's own input files is overwritten without a word**
   (`src/ddd/cli.py:998` `(result,) = write([GeneratedFile(path, text)])`, `:657` `args.renames
   .write_text(...)`, `:900` `files.append(_dictionary_file(dictionary, args.dictionary, files))`;
   none of the three looks at `workspace.sources()`). Trigger: `ddd dump components/sensor_hub
   .ddd.json -o components/sensor_hub.ddd.json` (a tab-completed `-o`), `ddd compare demo.ddd.json
   demo.ddd.json --renames demo.ddd.json`, or `ddd generate c demo.ddd.json -o gen -t ...
   --dictionary components/dict.ddd.json` into the directory an `includes` wildcard covers.
   Outcome, observed on copies: the component description is replaced by the dictionary
   (`wrote components/sensor_hub.ddd.json (updated)`, exit 0, the file now starts with
   `"format": 8`); the project file is replaced by `[]` (exit 0); the next `ddd check` of the
   demo fails with `components/dict.ddd.json: error[file-kind]: file has 'types' and 'constants'
   and 'rasters' at the top level`. A description file is a hand-written source; `generate`
   already refuses a path two artefacts share, but not one the project was read from. Fix:
   before writing, refuse a `-o`, `--renames` or `--dictionary` target that resolves to a file
   in `workspace.sources()` (and, for `--dictionary`, one inside a directory an include pattern
   of the project matches) as a usage error naming the file.

3. **A removed component's header and a plugin's artefact survive regeneration and
   `ninja -t clean`, and stay on every component's include path** (`cmake/Ddd.cmake:553` declares
   `OUTPUT ${generated_outputs}` - the template-named files, the a2l and the dictionary only, as
   `:358-361` and `docs/build_integration.rst:393-397` say; nothing declares `BYPRODUCTS`, and
   `src/ddd/backends/base.py:172-181` writes and never deletes). Trigger: drop `event_logger` from
   `target_link_libraries(firmware.elf ...)` and rebuild. Outcome, observed (`cmk/stale`): the
   regeneration succeeds, `DemoDevice.ddd.json` no longer lists the component, yet
   `EventLogger.h` and the plugin's `stamp.h` remain in `ddd/firmware.elf/`, `ninja -t clean`
   removes 16 files and leaves `Controller.h EventLogger.h SensorHub.h UserInterface.h stamp.h`
   behind, and a translation unit `#include "EventLogger.h"` reading `ValueJ` still compiles
   (`gcc -c ... exit 0`) against a header of a component the image no longer links - the
   include-path isolation `docs/build_integration.rst:153-155` promises ("a component cannot
   reach a variable it never declared") no longer holds after an incremental build, and a
   `clean` build is not clean. Fix: let `ddd generate` own its output directory - record the
   files it wrote (a manifest beside them) and remove on the next run those it no longer writes -
   which also makes `ninja -t clean` followed by a build equivalent to a fresh build; or read
   the component names off the collected descriptions at generate time and declare the headers
   as `BYPRODUCTS`.

4. **The documented address-map recipe cannot complete the two-run flow on a 64-bit host: every
   build after the first fails** (`docs/build_integration.rst:541-556` extracts every `[BbDdGgRrSs]`
   symbol of the image, `src/ddd/backends/a2l/options.py:59-70` refuses an address outside
   `0 .. 0xFFFFFFFF` "whether or not DDD knows the symbol", as `docs/build_integration.rst:564-567`
   itself says a host build "runs into first"). Trigger: `examples/cmake` plus the page's
   `POST_BUILD` command and `AddressMap.cmake` verbatim, on the Windows/MinGW host this
   repository is developed on (or any 64-bit Linux host). Outcome, observed (`cmk/addr`, `STRICT`):
   first build ok with `{}`, the step writes 98 entries including `"___crt_xc_end__":
   "0x140009018"`, the second build fails `[code=2]` with `ddd: ...addresses.json: address of
   '___crt_xc_end__' is 5368746008, outside the range 0 .. 0xFFFFFFFF that an a2l address can
   hold`, the third build fails the same way, and the a2l keeps `ECU_ADDRESS 0x00000000`. The
   page calls the script "an example to adapt", but the adaptation it needs - dropping symbols
   the dictionary never uses - is the tool's decision, not the toolchain's. Fix: in
   `load_address_map`, range-check only the symbols `addressed_symbols(dictionary)` carries and
   report the others in the `address-missing` note (the range refusal itself is pass 4's
   territory); or make the recipe skip entries whose address does not fit and say so on the page.

5. **A build record naming a check the language server does not know ends the server on the
   first `didOpen`** (carried over from the 2026-09-08 review, pass 5 Important 1;
   `src/ddd/lsp/diagnostics.py:53` `policy = SeverityPolicy.from_strings(list(info.severity),
   strict=info.strict)` is unguarded and `src/ddd/lsp/discovery.py:56` wraps only the read of the
   record). Trigger: a `ddd-build.json` with `"severity": ["no-such-check=ignore"]` - written by
   a newer `ddd` in the build directory while the editor runs an older one. Outcome, observed
   over pipes: `initialize` answered, the record logged, then exit 2 with `ddd: unknown check
   'no-such-check'` on stderr and no `publishDiagnostics`. `SPEC.md:758` says a record the reader
   "does not understand is one it declines rather than misreads". Fix: build the policy under
   `try/except UnknownCheckError`, skip the record and announce it in the log as a record naming
   a missing project is announced. (Pass 6 owns the server; recorded here because the previous
   pass 5 raised it and it is still open.)

#### Minor

1. **Every long option accepts any unambiguous prefix** (`src/ddd/cli.py:146` `argparse.
   ArgumentParser(prog="ddd", ...)`, `allow_abbrev` left at its default). Observed: `ddd check
   controller.ddd.json --stand` -> `ok: 14 variables ...`; `ddd generate all ... --dict x.json
   --dry-run` -> `would write x.json`. A script spelling `--dict` breaks the day a second option
   starting with `--dict` is added, with argparse's "ambiguous option" as the only clue. Fix:
   `allow_abbrev=False` on the parser.

2. **A `BaseException` that is neither `Exception` nor `SystemExit` escapes a hook as a traceback
   with the findings exit code, and Ctrl-C inside a hook prints a 30-line traceback**
   (`src/ddd/plugins.py:487` `except (Exception, SystemExit) as error:`; `src/ddd/cli.py:116-126`
   catches `UnknownCheckError`, `OSError`, `ValueError` only). Observed: a hook raising
   `class Boom(BaseException)` -> traceback, exit 1 (`EXIT_FINDINGS`); a hook raising
   `KeyboardInterrupt` -> traceback, exit 130, the findings gathered before it gone.
   `asyncio.CancelledError` is such a subclass. Fix: catch `BaseException` in `_call`, re-raise
   `KeyboardInterrupt` alone; in `main`, catch `KeyboardInterrupt` to print `ddd: interrupted`
   and return 130, and give a last-resort `except Exception` a code distinct from 1 and 2.

3. **A check hook can rewrite the resolved dictionary, and the rewrite reaches the artefacts, the
   dumped dictionary and the comparison** (`src/ddd/plugins.py:63` hands `dictionary:
   DataDictionary` itself; `src/ddd/ir.py:140`, `:351`, `:663` hold `extensions: dict[str,
   dict[str, Any]]` inside frozen models). Observed (`p_mutate.py`): the hook set
   `block["key"] = 999`, `block["added"] = True` and `dictionary.extensions["mut"] = {...}`;
   `mut.h` written by the plugin's backend, and `--dictionary d.json`, both carry `key: 999`,
   `added: true` and the injected project block. `docs/plugins.rst:135-140` says what a hook
   receives and nothing about whether it may change it. Fix: hand hooks read-only views
   (`MappingProxyType` over deep-copied blocks), or state that the dictionary a hook receives is
   the one every later step consumes.

4. **`ddd id --assign` stops at the first file it cannot write, with a bare errno, the files after
   it untouched and no total** (`src/ddd/identity.py:182` `path.write_bytes(mark + text.encode(
   "utf-8"))` unguarded; `src/ddd/cli.py:1016-1024` loops and prints the total after). Observed:
   `ddd id --assign controller.ddd.json ro.ddd.json after_ro.ddd.json` (the middle one read-only)
   -> `ddd: [Errno 13] Permission denied: 'ro.ddd.json'`, exit 2, `after_ro.ddd.json` still
   without ids, no `wrote N ids` line. `SPEC.md:1823-1824` promises that a file that cannot be
   parsed "is reported while the others are stamped"; one that cannot be written is not held to
   it. Fix: catch `OSError` in `assign`, report the file like an unreadable one, continue.

5. **The I/O errors of `--address-map`, `schema -o` and `build-info -o` are bare errno text that
   names neither the option nor what was being done** (`src/ddd/backends/a2l/options.py:49`
   `json.loads(path.read_text(encoding="utf-8"))` wraps `JSONDecodeError` only;
   `src/ddd/cli.py:1136-1140`, `:1127-1130` write unguarded). Observed: `--address-map
   nosuch.json` -> `ddd: [Errno 2] No such file or directory: 'nosuch.json'`; `--address-map
   adir` -> `ddd: [Errno 13] Permission denied: 'adir'`; `ddd schema all -o afile.txt` ->
   `ddd: [WinError 183] Cannot create a file when that file already exists: 'afile.txt'`;
   `ddd build-info ... -o adir` -> `ddd: [Errno 13] Permission denied: 'adir'`. `compare` and
   `generate` already say `cannot write the --renames file '...'` / `cannot write '...'`. Fix:
   the same wrapping - `cannot read the address map '...'`, `cannot write '...'`.

6. **A closed pipe is reported as a usage error** (`src/ddd/cli.py:124-126` `except (OSError,
   ValueError) as error: print(f"ddd: {error}"...); return EXIT_USAGE`). Observed:
   `ddd schema component | head -1` -> `ddd: [Errno 32] Broken pipe`, exit 2 (the smaller
   outputs of `list`, `dump`, `checks` fit the pipe buffer and exit 0). Under `set -o pipefail`
   a paging script fails on the tool's side. Fix: catch `BrokenPipeError` in `main`, redirect
   the fds to `devnull` and return 0 (or 1) silently, as the Python docs suggest.

7. **The verdict line names two identical file names** (`src/ddd/cli.py:669-673`
   `f"{args.candidate.name} {verdict} replace {args.baseline.name}"`; the comment at `:668` chose
   file names "because two deliveries of one project share a name" - so do two files of one
   delivery). Observed on the shipped examples: `ddd compare examples/pressure/v1.3/pressure.ddd
   .json examples/pressure/release/pressure.ddd.json` -> `pressure.ddd.json can replace
   pressure.ddd.json`. Fix: print the paths as typed when the two names coincide.

8. **A dumped dictionary handed to `check`, `list` or `dump` is refused with a message about
   vocabulary files** (`src/ddd/loading.py` reports `file-kind` off the top-level keys;
   `src/ddd/cli.py:1421-1435` `_holds_a_description` exists only on the `compare` side).
   Observed: `ddd check v13.json` -> `error[file-extension]: 'v13.json' is a DDD description
   file ...` and `error[file-kind]: file has 'types' and 'constants' and 'rasters' at the top
   level; it must have exactly one`. A dump is the one json a user of the tool has at hand
   beside a description. Fix: when the document carries `format` and `objects`, say "this is a
   dumped dictionary; hand it to `ddd compare`".

9. **`missing-plugin` sits at the candidate for both sides and says "this run has not loaded"
   a plugin the run did load** (`src/ddd/plugins.py:389-397` adds both findings at `location`,
   which `src/ddd/cli.py:649` makes `Location(args.candidate)`; `:638` `plugins =
   candidate.plugins` although the baseline description's plugins were imported and ran at
   `:632`). Observed: `ddd compare examples/layout/project.ddd.json layout.json` -> two warnings,
   both located at `layout.json`, the first reading `the baseline was produced with plugin
   'layout', which this run has not loaded`. Fix: locate the baseline's finding at the baseline
   and word it "which is not among the candidate's plugins".

10. **A component whose file is not valid json at configure time loses its `<target>.ddd` check
    until the next configure** (`cmake/Ddd.cmake:165-171` `_ddd_is_component_file` answers
    `FALSE` when `string(JSON ... GET "component")` fails, and `:243-246` then skips the file;
    in the collected mode the file is no `CMAKE_CONFIGURE_DEPENDS`). Observed (`cmk/broken`):
    configure with `{ broken`, fix the file, `ninja comp.ddd` -> `ninja: no work to do.`; after
    `cmake -S ... -B ...` -> `ok: 6 variables in 1 component are consistent`. Fix: treat a file
    that cannot be parsed as a component (the check target then reports the syntax error), or
    add the file to `CMAKE_CONFIGURE_DEPENDS` in that case.

11. **The CLI page and section 7 say `--plugin` is refused "beside a description"; the code
    refuses it beside a project candidate only** (`docs/command_line_interface.rst:84-85`
    "``--plugin`` refused beside a description"; `SPEC.md:1877-1878`; `src/ddd/cli.py:639-645`
    `if args.plugin: if candidate.from_description: raise ValueError(...)`). Observed: `ddd compare
    examples/layout/project.ddd.json layout.json --plugin examples/plugins/ddd_layout.py`
    (description baseline, dumped candidate) -> accepted, exit 0, no `missing-plugin`; the sides
    swapped -> `ddd: --plugin names the plugins of an archived dictionary; a project description
    names its own`, exit 2. This settles pass 1 Minor 7: 3.11 (`SPEC.md:1136-1138`) and the code
    agree; section 7 and the CLI page do not. Fix: "beside a project candidate" in both.

12. **`docs/build_integration.rst` never says that configuring runs the project's plugins**
    (`cmake/Ddd.cmake:98` `execute_process(COMMAND "${DDD_EXECUTABLE}" schema all --output ...
    ${plugin_arguments})` at configure time imports every `PLUGINS` module; `:62` runs `ddd
    sources`, which imports the plugins a `PROJECT` file names). `docs/plugins.rst:209-212` states
    the boundary for "every ``ddd`` command" and the editor, `SPEC.md:1069-1073` and
    `docs/editor_integration.rst:130-140` likewise, and the build page - the one a reader
    configuring a checked-out repository follows - is silent. Fix: one sentence under
    `PLUGINS`/`SCHEMA_DIRECTORY`: configuring imports the named plugins, as any `ddd` command
    over the project does.

13. **The pre-commit hook pins no interpreter and the page does not say it needs Python 3.12**
    (`.pre-commit-hooks.yaml:14` `language: python` without `language_version`;
    `pyproject.toml:14` `requires-python = ">=3.12"`; `docs/build_integration.rst:674-705`
    silent). Trigger: a consuming project whose default `python3` is 3.11 (Ubuntu 22.04's, say):
    `pre-commit install-hooks` fails inside pip with "requires a different Python", pointing at
    nothing the page names. Fix: state the floor on the page, and consider
    `minimum_pre_commit_version` / a `language_version` note in the hook definition.

14. **Three json payload shapes are documented nowhere**: `ddd artefacts --format json` carries
    `artefacts` of `{name, kind}` with `kind` in `built-in` / `plugin` and
    `plugins_without_artefact` (`src/ddd/cli.py:1215-1232`; no hit for either key in `docs/`,
    `README.md` or `SPEC.md`, whose `:1808-1809` says "in a note"); the entries of `ddd list
    --format json`'s `variables` (the union of object and leaf rows, `src/ddd/cli.py:946`, `name`
    on an object and `path` on a leaf) and `components` (`:943-945`) are named by
    `SPEC.md:1805-1806` and shaped by nobody, the dictionary page documenting `objects` and
    `leaves` instead; `dump -o`'s `generated` key is described in words only
    (`docs/command_line_interface.rst:57-59`). Complements pass 1 Minor 10 (the spec side). Fix:
    one example per payload on the CLI page.

15. **The CLI page says a component "generates on its own"; `generate` has no `--standalone`**
    (`docs/command_line_interface.rst:190-192` "A component checks, lists, dumps and generates on
    its own"; `src/ddd/cli.py:165, 236, 258` add `--standalone` to `check`, `list`, `dump` only,
    as `SPEC.md:1848-1850` says). Observed: `ddd generate c examples/demo/components/controller
    .ddd.json -o x -t examples/templates` -> two `missing-producer` errors, nothing written, exit
    1; with `--standalone` -> `unrecognized arguments`. A component with an input generates alone
    only under `--force` or a hand-kept `-W`. Fix: reword the page, or give `generate`
    `--standalone` (which the `<target>.ddd` target would not need).

16. **An image registering no component yields an empty `ddd_globals.c` that the example's own
    flags refuse** (`cmake/Ddd.cmake:256-257` "an empty ``includes`` list, which DDD accepts";
    `examples/cmake/CMakeLists.txt:19` `-Wall -Wextra -Wpedantic -Werror`). Observed
    (`cmk/empty`): `bare.ddd.json` with `"includes": []`, generation ok, then `ddd_globals.c:17:
    error: ISO C forbids an empty translation unit [-Werror=pedantic]`, build exit 1. The same
    mechanism as pass 4 Minor 2 (an empty header), reached through the module. Fix: the
    definition template emits a placeholder declaration when it renders nothing.

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| P5 C1 | the spec denied `--standalone` and the per-component target | fixed | `SPEC.md:1848-1854`, `:1912-1914` |
| P5 I1 | a build record naming an unknown check ends the server | still open - carried over (Important 5) | `src/ddd/lsp/diagnostics.py:53`; probe over pipes, exit 2 |
| P5 I2 | `sources`/`artefacts` exit 0 with errors, `sources` text hides findings | fixed | `src/ddd/cli.py:1284-1287`; `SPEC.md:1884-1887`; observed on a missing include |
| P5 I3 | plugin name grammar, reserved names, "malformed" unspecified | partly fixed: the spec states all of it (`SPEC.md:1077-1082`); `docs/plugins.rst:100` still says only "a lowercase identifier", naming neither `c`/`a2l`/`all` nor the check grammar | `docs/plugins.rst:100` |
| P5 I4 | `ddd checks` does not mark the project-wide checks | fixed | `src/ddd/cli.py:1324-1337`; `docs/consistency_checks.rst:988-1007`; observed |
| P5 I5 | 7.1 omits `<target>.ddd`, `DDD_A2L`, the multi-config refusal | fixed | `SPEC.md:1912-1914`, `:1972-1973`, `:1980-1981` |
| P5 I6 | where a vocabulary file goes is stated nowhere | fixed | `SPEC.md:1906-1907`; `docs/build_integration.rst:51-70`; `cmake/Ddd.cmake:153` |
| P5 I7 | the map's second half documented by nobody | fixed as text (`docs/build_integration.rst:507-570`), but the recipe fails the flow on a 64-bit host: Important 4 | `docs/build_integration.rst:541-556` |
| P8 C3 | opening a file runs repository python and nothing says so | fixed on the pages named; the build page remains silent (Minor 12) | `SPEC.md:1069-1073`, `:2071-2075`; `docs/plugins.rst:209-212`; `docs/editor_integration.rst:130-140`; `editors/vscode/README.md:50-56` |
| P8 I1 | a module runs before it is in `sys.modules` | fixed | `src/ddd/plugins.py:211-233`; probe `p_dc.py` (`@dataclass` under future annotations) -> ok |
| P8 I2 | path clash decided on spelling, nothing keeps a backend inside `-o` | fixed | `src/ddd/backends/base.py:96-119`; probes: `..`, absolute, case variant all refused |
| P8 I3 | template/factory exceptions escape as tracebacks with exit 1 | mostly fixed: factory and `generate` results checked (`src/ddd/plugins.py:405-481`), templates guarded (`tests/test_cli.py:537-561`); no last-resort handler in `main` (`src/ddd/cli.py:116-126`), so a `BaseException` subclass still ends in a traceback with exit 1 (Minor 2) | `src/ddd/cli.py:116-126` |
| P8 I4 | findings discarded when a later step fails | fixed | `src/ddd/cli.py:1460-1488`; `compare ... --renames adir` prints 4 findings, then the error, exit 2 |
| P8 I5 | `sys.exit` in a hook is a clean run | fixed | `src/ddd/plugins.py:487-495`; probe exit 2 `SystemExit(3)` |
| P8 I6 | generation not atomic, wrong file named | fixed | `src/ddd/backends/base.py:184-219`; `cannot write 'afile.txt/ddd_globals.c'` (pass 4 verified the staging) |

Minor ones of the previous pass 5, in bulk: 1 still open (`SPEC.md:1786-1788` still lists
`--plugin` and `--renames` inside the clause that covers `ddd check --baseline`, which takes
neither - observed `unrecognized arguments`); 2 fixed (`SPEC.md:1863-1864` "no finding at all");
3 and 4 are the editor's (pass 6); 5 fixed (`SPEC.md:1853-1854`); 6 fixed (`SPEC.md:1963-1967`);
7 still open (`src/ddd/cli.py:1363` returns before the `verify` at `:1370`: `ddd check
proj_settings.ddd.json -W sett/nosuch=ignore` exits 1 on the `schema` error and never mentions
the typo); 8 fixed (`docs/build_integration.rst:353-358`); 9 fixed (`SPEC.md:1846-1847`,
`README.md:845-848`); 10 fixed (`docs/editor_integration.rst:104-105`, `:162`); 11 fixed
(`docs/plugins.rst:148-151`). Of the previous pass 8's minors in this area: 2 still open (a lone
surrogate in a unit passes `ddd check` and ends `ddd list` with exit 2 after the table header,
`ddd dump` with exit 2 `Error serializing to JSON`; `src/ddd/cli.py:106` reconfigures without
`errors=`); 7 documented rather than changed (`docs/plugins.rst:197-203`; a sibling `import
helpers` still fails, the failure cache is fixed at `src/ddd/plugins.py:220`); 8 still open
(`PROJECT` mode re-runs configure on every component edit - observed `Re-running CMake...` after
touching `storage.ddd.json`); 9 still open (pass 4 Minor 10; see the forwarded items); 11 fixed
(`src/ddd/cli.py:907-912` names the file).

Spec gaps proven from code, previous list: closed - `--standalone`, `<target>.ddd`, `DDD_A2L`,
multi-config, `find_program`/`DDD_EXECUTABLE`, the tool as a dependency, 3.30 for
`ddd_add_component`, the non-`.ddd.json` refusal, `SCHEMA_DIRECTORY` beside `PROJECT`, the
tolerant exits, `artefacts` with neither, the plugin artefact's options, `id --assign`, the
`checks` json keys, the plugin grammar, one import per process, the unchecked `project` path of
`build-info` (`SPEC.md:751-753`), the pre-commit hook. Still unstated: `ddd build-info` accepts
a plugin override it cannot verify (`src/ddd/cli.py:1119`; `-W layout/nosuch=info` writes the
record, exit 0). The server items are pass 6's.

Test gaps of the previous list: closed - `sources` text with findings
(`tests/test_cli.py:1433`), `SEVERITY` reaching the generation and the dictionary
(`tests/test_cmake.py:471-486`). Still none in `tests/`: `STRICT` and `_ddd_check` through the
module, `ADDRESS_MAP` (seeding, dependency, second run), `NAME` defaulting and `NAME` beside
`PROJECT`, `DDD_A2L`, `NO_PROPAGATE_HEADERS` and the two-image refusal, `LINK_LIBRARIES`,
`CONST_INPUTS`, `BYTE_ORDER`, `OUTPUT_DIRECTORY`, `DEPENDS`, the 3.20/3.30 messages, the `.ddd`
target skipping a vocabulary file, `--standalone` on a project root (grep of `tests/test_cmake.py`
finds `SEVERITY` alone among those names; `tests/test_cli.py` has no project-root `--standalone`).

Forwarded items, settled from code:

- Pass 1 Important 2 (`dump -o` under an error finding writes, `generate --dictionary` does not).
  Behaviour, observed on `examples/inconsistent`: `ddd dump project.ddd.json -o inc.json` ->
  4 errors reported, `wrote inc.json (created)`, exit 1; `ddd generate all ... --dictionary
  d.json` -> the same 4 errors, nothing written, exit 1. The two code paths: `src/ddd/cli.py:
  968-976` (`dump`: `resolved, bag = _analyze(...)`; `if resolved is None: ... return`; else
  `_write_dictionary(...)` unconditionally) against `:859-861` (`generate`: `if bag.has_errors
  and not args.force: _report(bag, args.format); return EXIT_FINDINGS` before any backend runs).
  The asymmetry is deliberate in the comments: `:964-965` "``-o`` moves the dictionary into a
  file, the findings and the exit code staying what they were", `:985-986` "the findings, the
  stream they go to and the exit code of the analysis stay what they were", and `:804-806`
  for the other side "a run that fails leaves the last dictionary describing the artefacts still
  beside it". Only the root that cannot be read leaves the `-o` file alone (`:969-971`).
- Pass 1 Minor 7: settled above (Minor 11) - the code refuses `--plugin` beside a project
  *candidate* only, `src/ddd/cli.py:639-645`.
- Pass 1 Minor 8: `cmake/Ddd.cmake:445-447` overwrites `arg_NAME` with the name inside the
  `PROJECT` file (`_ddd_description_name(arg_NAME "${project_file}")`) and `:547` names the
  dictionary `${arg_NAME}.dictionary.json` after that; observed `LayoutDevice.dictionary.json`
  beside `LayoutDevice.a2l` with `NAME Ignored` given, and the status line `NAME is ignored with
  PROJECT - the a2l and the dictionary are named after the project name inside ...`. The page
  states it (`docs/build_integration.rst:238-239`, `:439-443`); the spec's `<NAME>` at
  `SPEC.md:1974` is the only text that does not.
- Pass 1 Minor 10, the shapes: the six keys of `checks` are documented
  (`docs/consistency_checks.rst:988-1007`), `sources` is (`docs/command_line_interface.rst:322`),
  `generated` is by example (`:38`) for `generate` and by words for `dump -o` (`:57-59`);
  `artefacts`'s keys and the `list` entry shapes are documented nowhere (Minor 14). The build
  record's `image` for an unnamed target is the empty string: `src/ddd/build_info.py:64` `image:
  str = ""`, observed `"image": ""`; `SPEC.md:747` "empty" is right, `null` is not accepted. The
  collected mode's floor: 3.30, checked at `cmake/Ddd.cmake:44` (`_ddd_require_transitive_
  properties`, called from `ddd_add_component` at `:201` and from the collected branch at `:452`)
  on top of the module's own 3.20 at `:32`; both are stated on the page
  (`docs/build_integration.rst:37-38`, `:219-223`, `:236-237`) and in the module's header
  (`:11-14`, `:28-31`); the spec states 3.30 for `ddd_add_component` (`SPEC.md:1911`) and
  "its stated floor" for the collected mode (`:1927-1928`) without a number - the number belongs
  there.
- Pass 3 Important 3. The `Location(...)` sites that carry a path as typed: `src/ddd/cli.py:602`
  `compare(baseline, resolved.dictionary, bag, location=Location(args.project))` and `:609`
  under `check --baseline`; `:649` `location = Location(args.candidate)` for `compare` and the
  `missing-plugin` findings; `:712` `Location(path)` for `address-missing` (the map as typed);
  `:1391` `lambda _: Location(path)` for a hook's `locate` on a dumped candidate; and, for a
  baseline or candidate that is a dump or cannot be read, `src/ddd/loading.py:1103` `where =
  origin or Location(path)` with the path `:1388` passes as typed - observed `"path":
  "nosuch.json"` for the baseline's `file-not-found` beside `"path": "C:/.../nosuch.ddd.json"`
  for the same finding on a root. The loader resolves every description it reads (the analysis
  findings are absolute in json), so two kinds of finding in one document follow two rules.
  The documented contract (`docs/consistency_checks.rst:975` "an absolute, forward-slashed
  path") is the one a reader can use; the code is wrong, not the page: build these locations
  from `path.resolve()` (the text renderer already re-relativises against `Path.cwd()` at
  `src/ddd/cli.py:1453-1455`, so the text output would not change). The sorting side effect is
  confirmed: `src/ddd/diagnostics.py:354` keys on `location.path.as_posix()`, and observed with
  `ddd compare demo.json examples/demo/components/controller.ddd.json` the candidate's six
  `unused-output` warnings (absolute path, `C:/...`) precede `project-mismatch` and every other
  comparison warning (`examples/...`), which is what `docs/comparing_deliveries.rst:589-590`
  ("among the warnings it comes first") says does not happen; typed absolute, the same run
  interleaves them the other way, so the order depends on how the candidate was spelled.
- Pass 3 open question 2: `src/ddd/cli.py:1408` `own = DiagnosticBag(SeverityPolicy(bag.policy.
  overrides, strict=False))` - the run's `-W` overrides reach the baseline's own analysis,
  `--strict` does not; they are not treated alike. Observed: `ddd compare examples/pressure/v1.3/
  pressure.ddd.json examples/pressure/release/pressure.ddd.json -W unused-output=error` -> the
  baseline's `unused-output` carried as `error[unused-output]: in the baseline: 'ValveDuty' ...`,
  exit 1, no verdict; the same with `--strict` -> `pressure.ddd.json can replace
  pressure.ddd.json`, exit 0. `ddd check --baseline` behaves the same (`:600`). Whether `-W`
  should follow `--strict` into "the baseline's warnings are its own" is the maintainer's;
  either answer is one line at `:1408`.
- Pass 4 Minor 10 (the example plugin's header): `examples/plugins/ddd_layout.py:255` takes
  `sizeof(EngineHours)` and `&EngineHours` of names it never declares. It compiles after
  `ddd_globals.h` or after `Storage.h` (gcc `-Wall -Wextra -Wpedantic`, exit 0 both, and links
  with `ddd_globals.c`) and fails alone (`'EngineHours' undeclared`). Because a stamped object
  may be `local` to a component, declared in that component's header alone, the one header that
  declares every stamped object is `ddd_globals.h` - which `README.md:627` reserves "for
  `ddd_globals.c` only" and the generated file itself says components "shall include their own
  interface header instead". So the header is meant for a translation unit that includes
  `ddd_globals.h` first, and nothing in `docs/plugins.rst:239-242`, the module docstring
  (`:1-12`) or the generated header says so. Fix: emit `#include "ddd_globals.h"` (pass 4's), and
  say in the docstring that the table is for one dedicated translation unit.
- Pass 4 Minor 11 and 12 stand as reported; `-t nonexistent_templates` still prints `no template
  to render in 'nonexistent_templates'` (observed). Pass 4's write-step strengths hold through
  the CLI probes here (staged writes, `unchanged`, case-variant clashes refused).

### Open questions

1. Should the command line bind a hook's and a plugin backend's stdout to stderr, as the server
   does, or is a printing plugin the plugin author's problem to be documented (Important 1)?
   The first changes `_analyze` and `render`'s call site; the second changes `docs/plugins.rst`.
2. Should `dump -o`, `--renames` and `--dictionary` refuse a target that is one of the run's
   sources (Important 2)? Yes changes three sites in `cli.py`; no leaves a one-keystroke way to
   destroy a description file.
3. Who owns the output directory (Important 3): `ddd generate` removing what it no longer writes
   (a manifest), or the module declaring the per-component headers as `BYPRODUCTS` from names
   read at generate time? The first also fixes `ninja -t clean`; the second only the clean.
4. Should `load_address_map` range-check only the symbols the a2l uses (Important 4)? Yes makes
   the documented recipe work on every host and changes `options.py:59-61`; no keeps pass 4's
   "refused whether or not DDD knows the symbol" and rewrites the recipe on the page.
5. Is a comparison finding's `location.path` absolute (the page) or as typed (the code)? Settled
   here in favour of the page; the maintainer's answer changes either `cli.py:602, 609, 649,
   712, 1391` and `loading.py:1103` or `docs/consistency_checks.rst:975` and
   `docs/comparing_deliveries.rst:589-590`.
6. Should `-W` reach a description baseline's own analysis while `--strict` does not
   (`cli.py:1408`)? The answer changes that line or `SPEC.md:1393-1396`.
7. Should `--plugin` be refused beside a description on either side, as section 7 and the CLI
   page say, or beside a project candidate only, as 3.11 and the code do (Minor 11)?

### Test gaps

- A plugin printing to stdout under `check --format json`, `generate --format json`, `dump` and
  `dump -o` (`tests/test_plugins.py`; only the server case exists at `:2154`).
- `dump -o`, `--renames` and `--dictionary` pointing at a file the run read
  (`tests/test_cli.py`).
- Removing a component from the link graph: the header survives, `ninja -t clean` leaves it,
  and the rebuild afterwards (`tests/test_cmake.py`).
- The documented address-map recipe on the host toolchain, and a map with an out-of-range entry
  for a symbol the dictionary does not carry (`tests/test_cmake.py`, `tests/test_cli.py`).
- A build record naming an unknown check under the server (`tests/test_lsp.py`; carried over).
- `allow_abbrev`: `--stand` and `--dict` refused (`tests/test_cli.py`).
- A hook raising a `BaseException` subclass, and `KeyboardInterrupt` reaching `main`
  (`tests/test_plugins.py`, `tests/test_cli.py`).
- A check hook mutating a block: what the backends and the dump see (`tests/test_plugins.py`).
- `ddd id --assign` with an unwritable file among several (`tests/test_cli.py`).
- A component broken at configure time and its `<target>.ddd` target after the fix
  (`tests/test_cmake.py`).
- An image registering no component built under `-Wpedantic -Werror` (`tests/test_cmake.py`).
- The comparison findings' `location.path` and their text order against the candidate's own
  findings, typed relative and absolute (`tests/test_cli.py`; pass 3's).
- The pre-commit hook end to end (`pre-commit try-repo`) - nothing runs it;
  `tests/test_documentation.py` reads the yaml only.
- `STRICT` with a partial `ADDRESS_MAP`, `NAME` defaulting, `DDD_A2L`, `NO_PROPAGATE_HEADERS`,
  `LINK_LIBRARIES`, `OUTPUT_DIRECTORY`, `DEPENDS` through the module (`tests/test_cmake.py`;
  carried from the previous list).

### Assessment

The tool interface is in better shape than the previous review left it: every option, exit
code, stream and ordering of section 7 that I exercised behaves as the spec and the reference
page now say, the plugin boundary closed every hole the previous pass 8 opened (import
registration, path confinement, `sys.exit`, factory and `generate` results, findings kept
through a failing step), the CMake module regenerates on every dependency it declares and
refuses every misuse with a message that names the fix, and the pre-commit hook installs and
runs from a checkout. What remains is at the edges where the tool meets the world outside its
own analysis: stdout is not the tool's alone while a plugin runs, an output path may be one of
the run's inputs, the output directory keeps what the image no longer has, the one documented
recipe for the second half of the two-run flow does not survive a 64-bit host, and the language
server still dies on a record from a newer build. None of the four Important findings of this
pass requires a design change; each is a guard or a redirection at one site, and the spec
sentences they touch are already right.

### Verification

Every candidate of this pass was handed to a second reviewer (group C): 21 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P5-I1 | Important | CONFIRMED | Important | `cli.py:1373` and `:898` run hooks and plugin backends with `sys.stdout` untouched; ran a plugin printing in its hook: `check --format json` stdout starts `NOISY-CHECK-STDOUT`, `json.loads` of it fails; `dump -o out.json` prints the line on stdout (exit 0); `generate all --format json` carries `NOISY-CHECK-STDOUT` and `NOISY-GENERATE-STDOUT` before the document |
| P5-I2 | Important | CONFIRMED | Important | on copies of the demo: `dump demo.ddd.json -o components/sensor_hub.ddd.json` -> `wrote components/sensor_hub.ddd.json (updated)`, exit 0, the file now starts `"format": 8`; `compare demo.ddd.json demo.ddd.json --renames demo.ddd.json` -> exit 0, the project file is `[]`; `generate c ... --dictionary components/dict.ddd.json` -> exit 0, the next `check` fails `error[file-kind]` on it |
| P5-I3 | Important | CONFIRMED | Important | `Ddd.cmake:553` declares `${generated_outputs}` only, no `BYPRODUCTS`; three-component project, `gamma` (local variables only) unlinked and rebuilt: regeneration succeeds (`Dev.dictionary.json` updated, no `Gamma`), `Gamma.h` with `extern volatile uint16_t G;` stays, a TU including it compiles (exit 0), `ninja -t clean` removes 14 files and leaves `Alpha.h Beta.h Gamma.h stamp.h` |
| P5-I4 | Important | CONFIRMED | Important | recipe of `docs/build_integration.rst:518-556` copied verbatim into `examples/cmake`'s components on MinGW: first build ok, the map has 98 entries (`"___crt_xc_end__": "0x140009018"`), the second and third builds fail `[code=2]` with `address of '___crt_xc_end__' is 5368746008, outside the range 0 .. 0xFFFFFFFF`, and `firmware.a2l` keeps 13 `ECU_ADDRESS 0x00000000` |
| P5-I5 | Important | CONFIRMED | Important | duplicate of P6-I4 (primary); `lsp/diagnostics.py:53` builds the policy unguarded; a `ddd-build.json` with `"severity": ["no-such-check=ignore"]`: `initialize` answered, the record logged, `didOpen` -> stderr `ddd: unknown check 'no-such-check'`, process exit 2, no `publishDiagnostics` |
| P5-M1 | Minor | CONFIRMED | Minor | `cli.py:146` builds the parser without `allow_abbrev=False`; `check controller.ddd.json --stand` -> `ok: 14 variables in 1 component are consistent`; `generate all ... --dict x.json --dry-run` -> `would write .../x.json (created)` |
| P5-M2 | Minor | CONFIRMED | Minor | `plugins.py:487` `except (Exception, SystemExit)`, `cli.py:116-126` catches `UnknownCheckError`, `OSError`, `ValueError` only; a hook raising `Boom(BaseException)` -> traceback, exit 1; `raise KeyboardInterrupt` -> traceback, exit 130 |
| P5-M3 | Minor | CONFIRMED | Minor | `plugins.py:63` hands the `DataDictionary` itself; a hook setting `block["key"] = 999` and `dictionary.extensions["mut"]`: `mut.h` written by the plugin reads `Speed={'key': 999, 'added': True}` / `project={'mut': {'injected': True}}`, and `--dictionary d.json` carries `"key": 999`, `"added": true`, `"injected": true` |
| P5-M4 | Minor | CONFIRMED | Minor | `identity.py:182` `path.write_bytes(...)` unguarded, `cli.py:1016-1024` prints the total after the loop; `id --assign first ro after_ro` with `ro` read-only -> `ddd: [Errno 13] Permission denied: 'ro.ddd.json'`, exit 2, `first` stamped (12 ids), `after_ro` still 0, no `wrote N ids` line |
| P5-M5 | Minor | CONFIRMED | Minor | `options.py:48-54` wraps `JSONDecodeError` only, `cli.py:1127-1130` and `:1136-1140` write unguarded; `--address-map nosuch.json` -> `ddd: [Errno 2] No such file or directory: '...'`; `--address-map adir` -> `[Errno 13] Permission denied`; `schema all -o afile.txt` -> `[WinError 183] Cannot create a file when that file already exists`; `build-info -o adir` -> `[Errno 13]` |
| P5-M6 | Minor | CONFIRMED | Minor | `cli.py:124-126` reports every `OSError` as usage; `set -o pipefail; ddd schema component \|head -1` -> stderr `ddd: [Errno 32] Broken pipe`, rc 2 (`ddd list demo \|head -1` fits the pipe buffer, rc 0) |
| P5-M7 | Minor | CONFIRMED | Minor | `cli.py:670-673` prints `args.candidate.name` and `args.baseline.name`; `compare examples/pressure/v1.3/pressure.ddd.json examples/pressure/release/pressure.ddd.json` -> `pressure.ddd.json can replace pressure.ddd.json` |
| P5-M8 | Minor | CONFIRMED | Minor | `_holds_a_description` (`cli.py:1421-1435`) is reached from `_read_dictionary` only; `check v13.json` on a dump -> `error[file-extension]: 'v13.json' is a DDD description file ...` and `error[file-kind]: file has 'types' and 'constants' and 'rasters' at the top level; it must have exactly one`, exit 1 |
| P5-M9 | Minor | CONFIRMED | Minor | `plugins.py:389-397` adds both findings at the one `location`, which `cli.py:649` makes the candidate, while `:638` `plugins = candidate.plugins` forgets the baseline's plugins `:632` imported and ran; `compare examples/layout/project.ddd.json layout.json` -> both warnings prefixed `layout.json:`, the first saying the baseline's `'layout'` is one "this run has not loaded"; primary of P10-M10 |
| P5-M10 | Minor | CONFIRMED | Minor | `Ddd.cmake:165-171` answers `FALSE` when `string(JSON)` fails and `:243-246` skips the file; configured with `{ broken` -> `build.ninja:78` `build comp.ddd: phony` (no command); file fixed, `ninja comp.ddd` -> `ninja: no work to do.`; after `cmake -S ...` -> `ok: 6 variables in 1 component are consistent` |
| P5-M11 | Minor | CONFIRMED | Minor | `cli.py:639-645` raises only when `candidate.from_description`; description baseline + dump candidate + `--plugin ddd_layout.py` -> exit 0, `layout.json can replace project.ddd.json`; sides swapped -> `ddd: --plugin names the plugins of an archived dictionary; a project description names its own`, exit 2; `command_line_interface.rst:84-85` and `SPEC.md:1877-1878` say "beside a description", `SPEC.md:1136-1138` "beside a project candidate" |
| P5-M12 | Minor | CONFIRMED | Minor | `Ddd.cmake:98` `execute_process(COMMAND "${DDD_EXECUTABLE}" schema all --output "${directory}" ${plugin_arguments})` and `:62` `sources "${project_file}"` import the plugins at configure time; the `PLUGINS` and `SCHEMA_DIRECTORY` rows (`build_integration.rst:433-437`, `:450-455`) say nothing of it, and the page has no line saying configuring runs or imports a plugin (grep) |
| P5-M13 | Minor | CONFIRMED | Minor | `.pre-commit-hooks.yaml:14` `language: python` with no `language_version`; `pyproject.toml:14` `requires-python = ">=3.12"`; the pre-commit section `build_integration.rst:676-710` names no Python floor (the page's only `3.12` is the docker image at `:580`) |
| P5-M14 | Minor | CONFIRMED | Minor | `cli.py:1228-1232` emits `artefacts` (`{name, kind}`) and `plugins_without_artefact`, `:943-946` `components` and `variables`; grep of `docs/`, `README.md`, `SPEC.md` finds no `plugins_without_artefact`, and the CLI page describes `list` (`:132`) and `artefacts` (`:159-160`) in words only |
| P5-M15 | Minor | CONFIRMED | Minor | `command_line_interface.rst:190-192` "A component checks, lists, dumps and generates on its own"; `generate c examples/demo/components/controller.ddd.json -o x -t examples/templates` -> two `error[missing-producer]`, exit 1, nothing written; with `--standalone` -> `ddd: error: unrecognized arguments: --standalone` |
| P5-M16 | Minor | CONFIRMED | Minor | `Ddd.cmake:256-257` "an empty includes list, which DDD accepts"; `examples/templates/ddd_globals.c.jinja2:52-55` renders one comment for `not model.groups`; a project with `"includes": []` generates, then `gcc -std=c11 -Wpedantic -Werror -c ddd_globals.c` -> `ddd_globals.c:17: error: ISO C forbids an empty translation unit [-Werror=pedantic]`; the same through the module, `ninja` exit 1 |

## Pass 6: the editor integration (SPEC.md section 7.2, the language server, the extension)

### Scope covered

Read in full, with line numbers: `SPEC.md:1995-2075` (7.2); every file of `src/ddd/lsp/`
(`__init__.py`, `protocol.py`, `server.py`, `discovery.py`, `diagnostics.py`, `navigation.py`,
`ranges.py`, `edits.py`, `hover.py`, 2878 lines); `src/ddd/build_info.py`; `src/ddd/cli.py:276-335,
520-560, 600-660, 1100-1130, 1340-1370` (the `lsp` and `build-info` parsers,
`_add_policy_arguments`, `_command_lsp`, `_command_build_info`, `_analyze`);
`src/ddd/diagnostics.py:250-300, 396-530` (`STANDALONE_POLICY`, `Location`, `SeverityPolicy`,
`DiagnosticBag`); `src/ddd/plugins.py` (the
exception boundary, `:183-260, 311-360, 465-495`); `src/ddd/loading.py:69-81, 386-420, 470-530,
1092-1125, 1195-1210`; `src/ddd/analysis.py:254-262, 2120-2135`; `src/ddd/models/common.py:42-54`,
`src/ddd/models/objects.py:823-846`; `src/ddd/identity.py:21-40`; `editors/vscode/package.json`,
`src/extension.ts`, `src/config.ts`, `src/config.test.ts`, `src/launch.test.ts`, `README.md`,
`.vscodeignore`, `tsconfig.json`, `package-lock.json:1-12`; `docs/editor_integration.rst` (all);
`README.md:133-237`; `docs/developer_documentation.rst:505-520`; `docs/plugins.rst:205-214`;
`docs/build_integration.rst:252-290`; `.github/workflows/ci.yml:80-98`, `publish.yml:68-110`;
`tests/test_lsp.py`: every class and test name, and the bodies at `:1-88, 338-375, 606-613,
620-727, 2853-2925, 2957-3010, 3438-3468, 4257-4275, 4361-4384`;
`tests/test_documentation.py:655-672`;
`reports/pass-5.md` (Important 5, the status table, the forwarded minors);
`previous-review.md:1275-1352, 1733-1834`; `git log 441c600..HEAD` on the area.

Ran (everything under `scratchpad/pass-6/`; the repository was never written to): a scripted
client over pipes (`lspclient.py`, 47 sessions of the real `ddd lsp`, transcripts of every byte in
`transcripts/*.txt`, summaries `p1*_summary.txt` to `p7_summary.txt`): framing variants, ids of
every type, the lifecycle, unknown methods, bad bodies and headers, an emoji before a finding,
CRLF buffers, six uri spellings plus a junction, a `subst` drive, a differently cased path, a
UNC administrative share, percent-encoded and non-ascii names, `didChange` full and incremental,
`didSave` with and without text, `didClose`, versioned edits, drifted buffers, rename refusals,
every code action, a project file and every vocabulary kind with and without a project, records
with `-W`/`--strict`, an unknown check, an unknown plugin check, a malformed override, a missing
project, two records, a junction loop under `build/`, plugins raising at import and in a hook and
printing to stdout, an unreadable directory under `build/`, a 30 304-file build tree, a flat
directory of 200 components; `ddd check`/`ddd build-info` on the same fixtures for comparison;
Python facts (`Path.resolve()` casing and junctions, `rglob` through a junction, `int(b"1_2")`,
`url2pathname` on each spelling). No node on this machine: the extension is reviewed from source.

### Strengths

- The framing is robust where it matters: invalid json and a batch get the codes json-rpc
  defines and the loop reads on; a negative length ends the run with one line on stderr; a
  body split across three writes and a 200 KB `didOpen` are read whole (`p1_framing.txt`).
- Columns are utf-16: with an emoji earlier on the line, `prepareRename` and the rename edit land
  on `"Speed"` at 79..84 where a code-point count would say 78..83, and a CRLF buffer answers
  the same positions (`p2b_emoji.txt`, `p2_crlf.txt`).
- The document store does what 7.2 promises: positions and edits come from the buffer, a client
  announcing `documentChanges` gets the version of every open file and `null` for the rest, an
  incremental change is left alone rather than misapplied, and a rename touching a declaration a
  buffer has moved is refused naming the file, from either side (`p3_buffers.txt`).
- The record's policy is the build's: `-W unused-output=info`, `missing-producer=ignore` and
  `--strict` reproduce `ddd check` exactly (`p4_policy_inc.txt`, `p2b_strict.txt`).
- The plugin boundary holds in the server: a plugin raising at import or in its `check` hook is
  one `plugin-invalid` on the project file, the open file still gets its own findings, hover
  still answers, and a plugin printing a fake frame to stdout lands on stderr while the wire
  stays intact (`p4_plugin_*.txt`, `p2b_plugin_*.txt`).
- Nothing is analysed per keystroke (no publication after `didChange`, 0.00 s to the next
  hover), discovery skips a directory it may not read and a malformed record, and every file of
  the project is published with both sides of a conflict marked.
- The trust statement is in all three places (`SPEC.md:2069-2075`, `docs/editor_integration.rst:
  130-140`, `editors/vscode/README.md:50-56`), the manifest declares `untrustedWorkspaces`
  unsupported (`package.json:37-42`), the three versions agree (0.9.0), and `publish.yml:106-109`
  attaches `editors/vscode/*.vsix` to the release as the README says.

### Issues

#### Critical

1. **A project file opened in a tree without a build record is checked under the standalone
   policy, so the ten project checks are silenced for the whole project - and opening it
   withdraws them from the components** (`src/ddd/lsp/diagnostics.py:136` `bag, sources =
   analyse_standalone(document)`, reached for any document kind once `containing.projects` is
   empty, which it always is for a project file nothing includes). Trigger: an unconfigured tree
   - a fresh clone, a project not built through CMake, the case `navigation.py:207` calls the one
   "an editor meets constantly" - and the reader opens `project.ddd.json`. Outcome: `ddd check
   project.ddd.json` on `examples/inconsistent` reports `missing-producer` and `unused-output`
   among 4 errors and 1 warning; the server publishes `component_c.ddd.json:
   [definition-mismatch, local-conflict]` and `component_a.ddd.json: [multiple-producers,
   definition-mismatch, local-conflict]` - no `missing-producer`, no `unused-output`
   (`p6_project_nobuild.txt`). Worse: with `component_c.ddd.json` opened first the full findings
   appear (through the containing project), and opening `project.ddd.json` next republishes the
   thinner set, withdrawing the two squiggles from the screen (`p6_component_then_project.txt`).
   `SPEC.md:2030-2035` justifies holding the ten back for "a component read alone"; a project
   file is the whole project. Fix: run a root that is a project under the full default policy
   (`_run(document, DiagnosticBag())`, as `:133` does for a containing project) and keep
   `analyse_standalone` for a component root.

#### Important

1. **Diagnostics, jumps and edits are published under the resolved path, so a document opened
   through a junction, a `subst` drive, a symlink or a differently cased spelling never gets its
   findings in the editor** (`src/ddd/lsp/server.py:625` `{"uri": path.as_uri(), "diagnostics":
   findings}` with `path` the loader's `_resolve()`d spelling, `src/ddd/lsp/diagnostics.py:141-143`;
   the same in `navigation.py:535, 543` and `edits.py:163, 340`). Trigger: VS Code opened on
   `W:\proj` (`subst`), on a junction or mapped drive, on macOS under `/tmp`, or with the path
   cased differently from the disk. Evidence: sent `file:///w%3A/component_c.ddd.json`, published
   `file:///C:/.../ws/inconsistent/component_c.ddd.json` (`p7_subst_live.txt`); sent
   `.../ws/link/component_c.ddd.json`, published `.../ws/inconsistent/...` (`p2_junction.txt`);
   sent `.../C--git-ac11-ddd/...`, published `.../c--git-ac11-ddd/...` (`p2b_casing.txt`; whether
   VS Code matches that last pair case-insensitively is unconfirmed - it does not for the first
   two, which are different paths). VS Code keys diagnostics by the uri string, so the squiggles
   go to a resource that is not the open editor; a rename edit is applied to the real path's
   document, not the one on screen. The one existing test resolves both sides before comparing
   (`tests/test_lsp.py:2904-2909`). Fix: remember the client's spelling per resolved path
   (`didOpen`, `initialize`) and publish and edit under it; files never opened stay resolved.

2. **Through such a spelling the opened file is found as its own containing project and
   analysed a second time under the full policy** (`src/ddd/lsp/navigation.py:281` `if candidate
   == document:` compares the resolved candidate with the client's spelling; `SPEC.md:2029` "the
   opened file itself excluded"). Trigger: as in 1. Outcome: `component_c.ddd.json` gets
   `[missing-producer, missing-producer, missing-producer, definition-mismatch, missing-producer,
   local-conflict]` - three `missing-producer` for inputs the project does produce - and the
   rename and code actions run over two "projects" (`p2_junction.txt`, `p7_subst_live.txt`;
   `navigation.containing_projects` returns `('component_c.ddd.json', 'project.ddd.json')` for
   the junction and the `subst` spellings, `('project.ddd.json',)` for the direct one). Fix:
   compare `candidate == document.resolve()` (resolved once, above the loop).

3. **A rename or a quick fix computed while one file of the project did not load rewrites the
   rest of the project around it** (`src/ddd/lsp/navigation.py:248` `return load_workspace(path,
   DiagnosticBag())` discards the bag, so a workspace whose component was dropped by a `schema`
   error is indexed as if it had never declared anything; `server.py:543-557`). Trigger: F2 on
   `Speed` in `a.ddd.json` while another declaration of `a.ddd.json` has a schema error (`uint99`),
   or from `b.ddd.json` while `a.ddd.json` is in that state - an ordinary mid-edit condition.
   Outcome: edits in `b.ddd.json` and `c.ddd.json` only, `a` keeps `Speed`; `definition` answers
   nothing and hover says "No component produces this"; in `c.ddd.json` the lightbulb offers
   "Remove this unit, which no other declaration of 'Speed' has" although the unloaded `a` is the
   producer (`p5_partial_rename.txt`). `SPEC.md:2012-2014` refuses a rename rather than "renaming
   the rest of the project around it" for a drifted buffer; a dropped file is the same hole.
   Fix: keep the bag in `_loaded` and refuse the rename and the fixes (`REQUEST_FAILED`, naming the
   file) when the load reported an error, as the drift refusal does.

4. **A build record naming a check the server does not know ends the server on the first
   `didOpen`** - carried over (previous pass 5 Important 1, pass 5 of this review Important 5).
   `src/ddd/lsp/diagnostics.py:53` `policy = SeverityPolicy.from_strings(list(info.severity),
   strict=info.strict)` raises `UnknownCheckError` past `run()`; `discovery.py:56` guards the read
   only. Trigger: a record written by a newer `ddd` in the build tree while the editor runs an
   older one, or a hand-edited record; a malformed entry (`"unused-output"`) does the same.
   Outcome: `initialize` answered, the record announced, exit 2 with `ddd: unknown check
   'no-such-check'` and no publication (`p4_unknown_check.txt`, `p4_malformed_override.txt`);
   the client restarts it five times and gives up. `SPEC.md:2047` and
   `docs/editor_integration.rst:110-111` say such a record is skipped. Fix: build the policy under
   `try/except UnknownCheckError` in `load_builds`, skip the record and announce it as a missing
   project is announced.

5. **F2 on an enum's name or on an enumerator opens a rename box whose rename returns an empty
   edit** (`src/ddd/lsp/navigation.py:303` `if pointer.startswith(_DECLARATION) and _key(pointer)
   in VARIABLE_KEYS:` - `_key` is the last segment, so `definition.conversion.name` and
   `definition.conversion.enumerators[0].name` pass as the object's name). Trigger: F2 on
   `StateA_t` or `STATE_OFF` in `examples/demo`. Outcome: `prepareRename` answers a range and
   the placeholder, `rename` answers `{"documentChanges": []}` - the "rename that quietly did
   nothing" `server.py:523-524` says the refusal exists to prevent - and had a variable of that
   name existed elsewhere it would have been renamed instead (`p3_enum_subjects.txt`).
   `SPEC.md:2007-2009` limits the rename to an object, a declared type or a declared constant.
   Fix: match the key directly under `definition` (`re.fullmatch(r"component\.interface\[\d+\]
   \.definition\.(name|axis|x_axis|y_axis|input)", pointer)`); the same applies to
   `constant_at` (`:319`, any `size` key) and `type_at` (`:334`, any `typename` key), which an
   `extensions` block can spell.

6. **A file two build records cover is published with every finding twice, and nothing tells
   the two apart** (`src/ddd/lsp/diagnostics.py:115-117` runs every build,
   `:158-161` appends each run's findings to the same file, `_as_lsp` carries no image).
   Trigger: two images sharing a component - the firmware and the test binary the docs use as
   the example (`SPEC.md:2023-2025`). Outcome: `component_a.ddd.json: [multiple-producers,
   definition-mismatch, local-conflict, unused-output, multiple-producers, definition-mismatch,
   local-conflict, unused-output]` with two records of identical policy (`p4_two_records.txt`):
   every squiggle doubled, the Problems count doubled, and with policies that differ the
   reader cannot say which image reports the error. Fix: drop a finding equal in code, message,
   location and severity to one already filed, or put the image in the message (`[img_b]`).

#### Minor

1. `codeAction` with `"context": null` ends the server with a traceback (carried, previous
   pass 8 Minor 1): `src/ddd/lsp/server.py:583` `reported = params.get("context",
   {}).get("diagnostics", [])`; observed `AttributeError: 'NoneType' object has no attribute
   'get'`, exit 1 (`p1_methods.txt`). Use `_field`.
2. `initialize` with a `workspaceFolders` entry lacking `uri` ends the server: `src/ddd/lsp/
   server.py:595` `self.roots = [uri_to_path(folder["uri"]) for folder in folders]`; observed
   `KeyError: 'uri'`, exit 1 (`p1_init_folders.txt`). Use `_field`.
3. `exit` without `shutdown` returns 0 where the protocol asks for 1 (carried, previous pass 8
   Minor 10): `src/ddd/lsp/server.py:227-228`; `editors/vscode/src/launch.test.ts:33-37` pins
   the 0 (`p1_exit_without_shutdown.txt`).
4. No lifecycle gating: a request before `initialize` is served and one after `shutdown` too,
   `initialize` twice is accepted (`src/ddd/lsp/server.py:222-248`; `p1_order.txt`); the protocol
   wants `ServerNotInitialized` (-32002) and `InvalidRequest`.
5. A notification with bad params is answered with an error carrying `"id": null`, which the
   comment above says a notification never gets (`src/ddd/lsp/server.py:209-213`; `p1_methods.txt`
   after `didOpen` without params). vscode-jsonrpc logs it as an error in the output channel.
6. `Content-Length` is read with `int()`, which accepts `1_2` (as 12), `+7` and surrounding
   whitespace (`src/ddd/lsp/protocol.py:68`; observed: `1_2` swallowed ten bytes of the next
   frame, `p1_bad_bodies.txt`). Match `\d+`.
7. `rglob` follows a junction (Python 3.13 excludes symlinks from `**`, not junctions), so a
   junction loop under `build/` yields 22 spellings of one record, 22 announcements and 22
   copies of every finding (`src/ddd/lsp/discovery.py:40`; `p4_junction_loop.txt`: 88 findings
   on `component_a.ddd.json`). Resolve before adding to `found`, or skip `is_junction()`.
8. The extension's watcher feeds `workspace/didChangeWatchedFiles`, which the server drops, and
   the comment promises the opposite (carried, previous pass 5 Minor 3): `editors/vscode/src/
   extension.ts:50-53`; observed a file rewritten on disk, the notification, no publication,
   `definition` answered from the cached project until the next `didSave` (`p7_watched.txt`).
   Also `package.json:35` `"onLanguage:json"` starts the server, and with `ddd` missing shows
   the error popup, in every workspace where any json file is opened.
9. A record override naming a plugin check nobody registers is accepted silently in the
   editor while `ddd check` refuses it with exit 2: `src/ddd/lsp/diagnostics.py:53` never calls
   `verify` (`p4_unknown_plugin_check.txt` versus `ddd check project.ddd.json -W
   layout/no-such=ignore`). One more place "the same policy" is five call sites.
10. A containing project is checked under the default policy - no `-W`, no `--strict` - which
    no page says (`src/ddd/lsp/diagnostics.py:133` `_run(project, DiagnosticBag())`), and
    `README.md:212-220` skips the containing-project stage altogether ("A file no build claims
    is still checked, on its own") where `docs/editor_integration.rst:112-117` states it.
11. Hover on a declared type's own entry, or on a `typename` inside a types file, answers
    nothing (`src/ddd/lsp/server.py:462-476`: `named_type` is looked up as external only), while
    the same type hovered from a component's `typename` describes the object and its members
    (`p3_subjects.txt`, `p2b_member.txt`). Not promised by the docs; a gap a reader meets.
12. `_related` sends `"uri": ""` for a note without a location and its docstring says the note
    is "given the first line of the file the finding is on" (`src/ddd/lsp/diagnostics.py:211-219`;
    pinned by `tests/test_lsp.py:606-613`). VS Code parses `""` as `file:///`. Unconfirmed
    trigger - every core note carries a location (`analysis.py:2130` `_Cause.location` is
    never `None`); a plugin note would confirm it.
13. Work repeated per save and per first request: discovery walks the build tree on every
    refresh (0.6 s for 30 304 files, `p4_big_build.txt`), `collect` loads every candidate above
    the file and then the containing project again (`src/ddd/lsp/diagnostics.py:121, 133`), and
    the first hover after a save does both once more through `workspaces`
    (`navigation.py:225-226, 231`): a flat directory of 200 components costs 0.5 s per save and
    2.2 s for that hover (`p4_flat.txt`), against 0.7 s for `ddd check` of the whole project. The
    previous review's "three lookups, two implementations" stands; the caches `server.py:154-175`
    remove the repetition between requests, not within a refresh.
14. `_insert` takes the indentation line from `str.splitlines()` while every position counts
    `\n` only (`src/ddd/lsp/edits.py:563`): a form feed, NEL or U+2028 in a description above
    shifts the index and the inserted key copies another line's indentation. Cosmetic; observed
    correct only because the neighbouring lines share the indentation (`p5_linesep.txt`).
15. A document under a scheme other than `file:` becomes a path relative to the server's
    working directory and a `file-not-found` finding is published for a phantom
    `file:///<cwd>/Untitled-1` (`src/ddd/lsp/server.py:92-117`; `p2b_schemes.txt`). The extension
    never sends one (`extension.ts:49` `scheme: "file"`); other clients can.
16. Still open from the previous pass 8, in bulk: 3 (hover markdown unescaped, `src/ddd/lsp/
    hover.py:217, 226` - a unit with a backtick or `|` breaks the table), 5 (the restart race,
    `editors/vscode/src/extension.ts:56-59` still clears the module-level `client` on a rejected
    start whatever `restartServer` assigned meanwhile).

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| P5 I1 | a build record naming an unknown check ends the server | still open - carried over (Important 4) | `src/ddd/lsp/diagnostics.py:53`; `p4_unknown_check.txt` exit 2 |
| P5 M3 | the watcher feeds a notification the server drops; `onLanguage:json` | still open (Minor 8) | `editors/vscode/src/extension.ts:50-53`, `package.json:35`; `p7_watched.txt` |
| P5 M4 | a header block without a length ends the session silently | consciously left: the spec now states it | `SPEC.md:2061-2062`; `src/ddd/lsp/protocol.py:65-66`; observed exit 0 |
| P5 M10 | `-b` relative to the working directory undocumented | fixed | `docs/editor_integration.rst:104-107`; `package.json:66` |
| P8 C1 | VS Code's `file:///c%3A/` uri kills the server on Windows | fixed | `src/ddd/lsp/server.py:83-117`; `p2_uri_vscode.txt` analysed and published under `file:///C:/`, which VS Code normalises; the residual spelling defect is Important 1 |
| P8 C2 | rename and quick-fix edits computed from the disk while the client applies them to its buffer | fixed | `src/ddd/lsp/server.py:176-185, 263-304, 499-518`; `p3_buffers.txt`: buffer positions, versions, drift refused |
| P8 C3 | opening a file runs repository python and nothing says so | fixed for the docs and the extension; the server itself still runs plugins whatever the client, consciously (`SPEC.md:2069-2075` puts the decision on the extension) | `docs/editor_integration.rst:130-140`; `editors/vscode/README.md:50-56`; `package.json:37-42` |
| P8 M1 | `codeAction` with `context: null` ends the server | still open (Minor 1) | `src/ddd/lsp/server.py:583`; `p1_methods.txt` |
| P8 M3 | hover markdown not escaped | still open (Minor 16) | `src/ddd/lsp/hover.py:217, 226` |
| P8 M5 | restart race in the extension | still open (Minor 16) | `editors/vscode/src/extension.ts:56-59` |
| P8 M7 | a plugin that imported is never re-read by the server | consciously left: documented | `docs/plugins.rst:197-203` |
| P8 M10 | `exit` without `shutdown` returns 0 | still open (Minor 3) | `src/ddd/lsp/server.py:227-228`; `launch.test.ts:37` pins it |

The previous pass 8 design notes: "a document store for the server" is done (`server.py:176-185`);
"three lookups, two implementations" remains (Minor 13); "Windows is tested through
`Path.as_uri()` only" is half done - `tests/test_lsp.py:2856-2909` sends the `%3A` spelling but
resolves both sides before comparing what is published (Important 1).

### Open questions

1. Should a project file opened in an unconfigured tree be analysed as the project it is
   (Critical 1)? Yes seems the only answer; the alternative is documenting that the editor shows
   fewer findings than `ddd check` on the project file, which no page would want to say.
2. Under which spelling should the server publish and edit: the client's for the documents it
   opened, and the workspace folder's for the rest (Important 1)? A per-session table from
   resolved path to the client's spelling settles the opened files; the others need a rule,
   and the answer changes whether `Site.path` stays resolved or carries both.
3. Two records covering one file: deduplicate identical findings, or tag each with the image
   (Important 6)? Tagging changes every message an editor shows for a shared component.
4. Should the server refuse plugins unless the client announces a trusted workspace (the second
   half of the previous C3), or is the extension's gate the whole answer, as 7.2 now says?
5. Should `exit` without `shutdown` return 1 as the protocol asks (Minor 3)? `launch.test.ts`
   would have to send `shutdown` first.

### Test gaps

- A project file opened with no build record, and a component opened first then the project
  file: what is published and what is withdrawn (`tests/test_lsp.py`, `TestDiagnostics`).
- A document spelled through a junction, a `subst` drive or a symlink: the published uri equals
  the sent one, and the file is not its own candidate. `TestSymlinkedWorkspace` needs
  `SeCreateSymbolicLinkPrivilege` (or Developer Mode) for `symlink_to`, fails without it, and
  pins only that `workspaces()` finds the build - `_winapi.CreateJunction` would run on any
  Windows account and the assertion should cover the publication (`tests/test_lsp.py:4361-4384`).
- A rename and a quick fix while a file of the project failed to load (`TestRename`,
  `TestPropagating`).
- A record naming an unknown check, and one with a malformed entry (`TestDiscovery`; carried).
- F2 on an enum name and on an enumerator; a `size`/`typename`/`name` key inside an
  `extensions` block (`TestRename`, `TestHover`).
- Two records covering one file: what is published for it (`TestDiagnostics`).
- `codeAction` with `context: null`; `initialize` with a folder entry lacking `uri`; a request
  before `initialize` (`TestServer`).
- A junction loop, or any junction, under `build/` (`TestDiscovery`, Windows).
- `launch.test.ts` still opens no document (carried from the previous test review).

### Assessment

The server is in far better shape than at the previous review: the Windows uri, the buffer
store, the drift refusal, the versioned edits and the plugin boundary all hold under a real
client, the columns are utf-16, and the record's policy is the build's to the letter. What this
pass found is one blind spot and one seam. The blind spot is the project file itself: opened in
an unconfigured tree it is treated as "a component read alone" and the two checks the editor
exists for are silenced and even withdrawn - a Critical on the most ordinary of setups. The seam
is the spelling of a path: everything the server publishes and edits is spelled as the loader
resolved it, so any client spelling `resolve()` changes - a junction, a `subst` or mapped drive,
a symlinked directory, a different case - sends the findings to a resource the editor is not
showing and, through the candidate comparison, adds three wrong `missing-producer` findings on
top. Add the rename computed over a project a file of which did not load, the carried-over exit
on an unknown check, the enum rename box and the doubled findings of two records, and the list
is six Important, all reproduced over pipes with transcripts, each with a one-line fix.

### Verification

Every candidate of this pass was handed to a second reviewer (group D): 23 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P6-C1 | Critical | CONFIRMED | Critical | `lsp/diagnostics.py:136` `analyse_standalone(document)` is reached for a project file no build names, since no candidate includes it; copy of `examples/inconsistent`, no record: `ddd check project.ddd.json` -> `4 errors, 1 warning`; `project.ddd.json` opened -> `component_c: [definition-mismatch, local-conflict]`, `component_a` without `unused-output` - the `--standalone` set (3 errors); `component_c` opened first got `[definition-mismatch, missing-producer, local-conflict]` and `component_a` `unused-output`, opening the project next republished both without them |
| P6-I1 | Important | CONFIRMED | Important | `server.py:625` `path.as_uri()` on the loader's resolved path, `navigation.py:535, 543`, `edits.py:163, 340` likewise; junction `ws/link_inc -> ws/real_inc`: sent `file:///C:/.../link_inc/component_c.ddd.json`, every publication under `.../real_inc/...`; `subst W:`: sent `file:///w%3A/component_c.ddd.json`, published `file:///C:/.../real_inc/...`, rename edits and definition answers under `real_inc` too; control: VS Code's own `c%3A` spelling publishes `file:///C:/`, which it normalises |
| P6-I2 | Important | CONFIRMED | Important | `navigation.py:281` `if candidate == document` compares a resolved candidate with the client's spelling; `containing_projects` answers `['component_c.ddd.json', 'project.ddd.json']` through the junction and through the `subst` drive, `['project.ddd.json']` through the real path; published `component_c: [missing-producer, missing-producer, missing-producer, definition-mismatch, missing-producer, local-conflict]`; a case difference does not trigger it on Windows (`Path` equality is case-insensitive: `['project.ddd.json']`) |
| P6-I3 | Important | CONFIRMED | Important | `navigation.py:248` `load_workspace(path, DiagnosticBag())` discards the bag; `a.ddd.json` with `uint99`: published `{'a.ddd.json': ['schema']}`, F2 on `Speed` in `b` -> `[('b.ddd.json', 1, 1), ('c.ddd.json', None, 1)]`, `a` untouched; `definition []`, hover `*No component produces this.*`, `c` offered "Remove this unit, which no other declaration of 'Speed' has"; with `a` loading again the same rename edits `a`, `b` and `c` |
| P6-I4 | Important | CONFIRMED | Important | duplicate of P5-I5 (pass 6 primary); `lsp/diagnostics.py:53` builds the policy unguarded, `discovery.py:54-57` guards the read only; record with `"severity": ["no-such-check=ignore"]`: `initialize` answered, record announced, `didOpen` -> stderr `ddd: unknown check 'no-such-check'`, exit 2, nothing published; `["unused-output"]` -> `ddd: expected 'check=severity', got 'unused-output'`, exit 2 |
| P6-I5 | Important | CONFIRMED | Important | `navigation.py:303` `_key(pointer) in VARIABLE_KEYS` accepts `conversion.name` and `conversion.enumerators[0].name`; demo `controller.ddd.json`: `prepareRename` on `StateA_t` -> range 72:21-72:29, placeholder `StateA_t`, on `STATE_OFF` -> 74:25-74:34, both renames -> `{"documentChanges": []}`; with a variable `MODE_OFF` in `b.ddd.json`, F2 on the enumerator `MODE_OFF` in `a` answers one edit in `b` (the variable) and none on the enumerator; `"size"` and `"typename"` inside an `extensions` block open a box and rename nothing |
| P6-I6 | Important | CONFIRMED | Important | `lsp/diagnostics.py:158-161` appends each run's findings to the same file and `_as_lsp` (`:192-208`) sends `code, message, range, severity, source` only; two records for `project.ddd.json` (`img_a`, `img_b`): `component_a` 8 findings of which 4 distinct, `component_b` 2, `component_c` 6; with `img_b` at `-W unused-output=error` one range carries severity 2 and severity 1 with one message; `ddd check` reports `4 errors, 1 warning` once |
| P6-M1 | Minor | CONFIRMED | Minor | `server.py:583` `params.get("context", {}).get("diagnostics", [])`; `"context": null` -> no answer, stderr `AttributeError: 'NoneType' object has no attribute 'get'`, exit 1 |
| P6-M2 | Minor | CONFIRMED | Minor | `server.py:595` `folder["uri"]`; `workspaceFolders: [{"name": "x"}]` -> no answer, `KeyError: 'uri'`, exit 1 |
| P6-M3 | Minor | CONFIRMED | Minor | `server.py:227-228` `elif method == "exit": return False` whatever came before; `initialize` then `exit` -> exit code 0; `launch.test.ts:32-37` sends exactly that and asserts 0 |
| P6-M4 | Minor | CONFIRMED | Minor | `server.py:222-248` keeps no lifecycle state; hover before `initialize` answered in full, hover after `shutdown` answered, a second `initialize` answered |
| P6-M5 | Minor | CONFIRMED | Minor | `server.py:213` `error(message.get("id"), ...)`; `didOpen` without `params` -> `{"id": null, "error": {"code": -32602, "message": "'params' is missing or is not dict"}}` where `:210-211` says a notification gets nothing |
| P6-M6 | Minor | CONFIRMED | Minor | `protocol.py:68` `int(raw_length)`; `Content-Length: 1_2` + `{}` + a hover frame -> `-32700 the message body is not json` (12 bytes read), then the split header `ngth: 379` has no length and the server exits 0; the hover is never answered |
| P6-M7 | Minor | CONFIRMED | Minor | `discovery.py:40` `rglob` follows a junction; `mklink /J build/loop build` on a copy of `inconsistent` with one record: `build_files` finds 22 records, 22 log messages in 2.1 s, `component_a` published 88 findings, `component_b` 22, `component_c` 66 |
| P6-M8 | Minor | CONFIRMED | Minor | `extension.ts:53` watches `**/*.ddd.json`, `server.py:218-255` has no branch for `workspace/didChangeWatchedFiles`; definition of `SharedValue` `[a, b]`, `b` rewritten on disk to produce `OtherValue`, the notification -> nothing published, definition still `[a, b]`; after `didSave` `[a]`; `package.json:35` `"onLanguage:json"` |
| P6-M9 | Minor | CONFIRMED | Minor | `lsp/diagnostics.py:53` never calls `verify`; record `["layout/no-such=ignore"]` -> the full findings, exit 0; `ddd check project.ddd.json -W layout/no-such=ignore` -> `unknown check 'layout/no-such': no loaded plugin registers it`, exit 2 |
| P6-M10 | Minor | CONFIRMED | Minor | `lsp/diagnostics.py:133` `_run(project, DiagnosticBag())` is the default policy; `docs/editor_integration.rst:112-117` names the stage and no policy; `README.md:212` "A file no build claims is still checked, on its own" goes straight to standalone |
| P6-M11 | Minor | CONFIRMED | Minor | `server.py:466-467` looks a type name up as external only; `examples/structures`: hover on `"name": "Sample_t"` in `types.ddd.json` -> `null`, on the member `"typename": "Temperature_t"` (declared at `types.ddd.json:6`) -> `null`, on `"typename": "Sensor_t"` in `monitoring.ddd.json` -> `**Inlet** — measurement, ...` |
| P6-M12 | Minor | CONFIRMED | Minor | `lsp/diagnostics.py:219` `{"uri": ""}`; a plugin whose hook adds `notes=[("...", None)]`: published `relatedInformation: [{"location": {"uri": "", "range": 0:0-0:0}, "message": ...}]`; `tests/test_lsp.py:612` asserts the `""` |
| P6-M13 | Minor | CONFIRMED | Minor | `lsp/diagnostics.py:121` then `:133` load the project twice per refresh, `navigation.py:225-226, 231` again on the first request; flat 200 components: a save costs 0.39 s (`collect`) where one load plus `analyze` costs 0.12 s, the first hover after each refresh 0.33 s (`containing_projects` 0.22 s + a load 0.10 s); the finder's 0.6 s and 2.2 s include its client's 0.5 s quiet wait - the 30 304-file tree refreshes in 0.07 s |
| P6-M14 | Minor | CONFIRMED | Minor | `edits.py:563` `text.splitlines()[end["line"]]` against `ranges.py:191` counting `\n` only; a description holding a literal U+2028 above the declaration, `conversion` written last: "Apply this unit" inserts `,\n` + 12 spaces + `"unit": "rpm"` where the plain control inserts 10 - `splitlines()[14]` is the `"kind": "identity"` line, `\n`-line 14 is the `}` |
| P6-M15 | Minor | CONFIRMED | Minor | `server.py:108-117` keeps `urlparse("untitled:Untitled-1").path` as a relative path; `didOpen untitled:Untitled-1` -> published `file:///C:/.../ws/demo/Untitled-1: [file-not-found]`, server alive |
| P6-M16 | Minor | CONFIRMED | Minor | `hover.py:217` wraps the unit in backticks and the model does not validate it (`objects.py:416` `unit: str = ""`); unit `a`, backtick, `b`, pipe, `c` passes `ddd check --standalone` and the hover's unit row carries the raw backtick and pipe, splitting the cell; `extension.ts:56-59` clears the module-level `client` on a rejected start whatever `stop()` and `start()` assigned meanwhile |

## Pass 7: the remaining documentation, the repository machinery and release readiness

### Scope covered

Read in full, with line numbers: `docs/getting_started.rst`, `docs/concept.rst`, `docs/faq.rst`,
`docs/data_contracts.rst` (as a page), `docs/developer_documentation.rst`, `docs/acronyms.rst`,
`docs/index.rst`, `docs/conf.py`, `docs/_static/css/custom.css`, `docs/_static/js/versions.js`,
`docs/_templates/versions.html`; `README.md` and `CHANGELOG.md` whole; `LICENSE`; `pyproject.toml`;
the three `requirements*.txt`; `.github/workflows/ci.yml`, `docs.yml`, `publish.yml` (the
`versions.json` writer read as Python); `docker/Dockerfile`, `docker/compile.sh`,
`docker/verify_symbols.py`, `docker-compose.yml`; `.gitattributes`, `.gitignore`, `.dockerignore`,
`.pre-commit-hooks.yaml`; the tree under `examples/` and where each file is referenced; the status
lines, section 2 and the deferred lists of the five `docs/superpowers/specs/*.md`;
`assets/logo/README.md`; `src/ddd/__init__.py`; `editors/vscode/package.json`;
`tests/test_documentation.py` and `tests/test_transcripts.py` in full, `tests/test_backends.py`
1-125; `SPEC.md` section 2; `git log v0.9.0..master` and the diff of `src/ddd/ir.py`,
`src/ddd/backends/c/model.py`, `src/ddd/cli.py` (the argparse additions) and
`schemas/ddd_dictionary.schema.json`; `previous-review.md:1422-1564`; the six reports of this
review for what they say about `CHANGELOG.md`.

Ran (scratch directory `scratchpad/pass-7/`; this pass was started once before and interrupted,
and the runs of that attempt - `build.log`, `tutorial.sh`/`tutorial.log`, `faq_transcripts.py`/
`.log`, `linkcheck.sh`/`.log` - were reused after reading their scripts; everything else below is
this attempt's):

- `python -m build --outdir dist` from a fresh venv: `ddd_tool-0.9.0.tar.gz` (201 files) and
  `ddd_tool-0.9.0-py3-none-any.whl` (59 files); both listed against `pyproject.toml:70-96`; the
  wheel compared file for file with the 0.9.0 wheel on PyPI (same 59 names).
- The wheel installed into a fresh venv and the whole getting-started tutorial run from a
  directory outside the repository (`tutorial.log`), then `ddd check` on the nine example
  projects, `ddd compare` on the pressure deliveries, `ddd list` on the demo, `ddd schema all`.
- The sdist unpacked, `pip install -e ".[dev]"` from inside it, `python -m pytest` with MinGW gcc
  on the PATH (`sdist_suite_full.log`): **2284 passed, 1 failed** (the known symlink test),
  **coverage 100.00%** (6514 statements, 1938 branches), 10 min 26 s in the cold venv.
- `pip index versions ddd-tool`: 0.9.0, 0.8.0, 0.7.0, 0.6.0, 0.5.0.
- `sphinx-build -b linkcheck` with `JAVA`/`PLANTUML_JAR` set (`linkcheck.log`), the three links
  it called broken re-fetched with `curl`; `gh api` on the environments, the Pages configuration,
  the releases and the last eight runs on master; `https://sauci.github.io/ddd/versions.json` and
  the root redirect fetched.
- The FAQ and data-contracts transcripts the transcript test cannot run, reproduced on files
  written for the purpose (`faq_transcripts.log`, `mine/faq1`, `mine/axis`); the changelog's
  behaviours exercised (`mine/cl`: `dump -o` three ways, `--dictionary`, `--standalone` on
  `list`/`dump`, constants `2.0`/`-3`/`0`/`0.5` and `dimension-value` under `--standalone`, a
  quoted `"12"` init); `docker/compile.sh` run with MinGW gcc on a copy whose only edit is the
  path of `verify_symbols.py`, plain and with `CDEFS=-DFEATURE_X`.
- `sphinx-build -M latex` produced `ddd.tex` (earlier attempt); no LaTeX distribution here, so
  `latexpdf` is unconfirmed.

### Strengths

- What would be released installs and works: the wheel carries `ddd/cmake/Ddd.cmake` and the five
  templates, `ddd cmake-dir` and `ddd templates-dir` find them after a clean install, and the
  tutorial reproduced byte for byte from outside the repository - every command, the exit codes
  0/1/2, the six `created` then `unchanged` lines, the two a2l excerpts, `--const-inputs`, the
  refusal after the edit and `--force` writing six files at exit 1.
- The sdist is now self-contained: its suite runs to the same result as the checkout's (2284
  passed, the coverage gate met), it carries `assets/`, `editors/vscode/`, the workflows and the
  hook definition, and not `docs/superpowers/`.
- The transcripts the test cannot reach hold too: twelve FAQ and data-contracts scenarios
  reproduce the page's lines (the only extra lines are `missing-id` infos on files written
  without ids), including the `SpeedAxis`/`InjectionTime` a2l excerpt and the "1 variable in 2
  components" wording.
- Every `examples/` path and every `:doc:` target quoted on the pages exists; every example file
  is bound to its schema; the nine example projects do what their pages say (demo 23/4,
  inconsistent 4 errors 1 warning, layout with its plugin 3/1, structures 9/2, vocabulary 4/1,
  pressure release->work 2 errors 1 warning 1 info, "cannot replace").
- The changelog entries exercised describe the tool: `dump -o` leaves an unchanged file and a
  file of an unreadable project alone and names the file in the json report, `--dictionary` on an
  artefact's path is refused, `list`/`dump --standalone` lift `unknown-extension`, a constant
  `2.0` reaches `#define GAIN 2.0` and `SYSTEM_CONSTANT "GAIN" "2.0"`, `dimension-value` is
  reported at `dimensions[0]` and at `size` with `--standalone`, `"12"` is `init-invalid`. The
  format history is consistent: 4 (0.5.0), 5 (0.7.0), 6 and 7 (0.8.0), 8 unreleased,
  `DICTIONARY_FORMAT = 8`.
- The release machinery is in the state the developer page describes: the site serves
  `versions.json` with `stable: v0.9.0` and the root redirect, Pages is `legacy` from `gh-pages`
  `/`, every release carries its `ddd-<version>.vsix`, the version is spelled in exactly the nine
  files the page enumerates, and CI and Documentation are green on master today.
- `docker/compile.sh` compiles, links and verifies the demo with MinGW gcc in both variants
  ("22 of 23 declared variables are defined", "23 of 23"); no external link of the documentation
  is broken (three `linkcheck` failures are this machine's certificate chain - all three answer
  200/302 to `curl -k`; the marketplace `manage` page redirects to a sign-in, as expected).

### Issues

#### Critical

None found.

#### Important

1. **`workflow_dispatch` can upload to PyPI from any ref with no tag, release or environment
   check** (`.github/workflows/publish.yml:9-15`, `:131`). Trigger: a maintainer runs Publish with
   `target: pypi` on a branch -> `test`, `build` and `publish-pypi` run, the tag check is skipped
   (`:52` `if: github.event_name == 'release'`), and whatever `pyproject.toml` says is uploaded,
   immutably, with no documentation directory (`docs.yml` publishes only `latest` on dispatch),
   no `.vsix` (`:83` `if: github.event_name == 'release'`) and no tag. Nothing outside the file
   stops it either: `gh api repos/Sauci/ddd/environments` reports `deployment_branch_policy: null`
   for `pypi` and `testpypi`. Evidence: `if: github.event_name == 'release' || inputs.target ==
   'pypi'`. Fix: drop `pypi` from the dispatch choices (the comment at `:3-5` calls dispatch the
   TestPyPI dry run) or gate `publish-pypi` on `startsWith(github.ref, 'refs/tags/v')`, and add a
   `v*` tag rule to the `pypi` environment.

2. **A prerelease tag becomes the site's "stable" version and the root redirect**
   (`.github/workflows/docs.yml:167-182`). Trigger: a release tagged `v0.10.0rc1` (which
   `publish.yml` accepts once `pyproject.toml` says `0.10.0rc1`, and which `release: types:
   [published]` fires for whether or not it is flagged pre-release) -> `order()` returns
   `((0, 10, 0), False, "rc1")`, which sorts above every `(0, 9, 0, ...)`, so `stable =
   tags[0]` is `v0.10.0rc1`, `index.html` redirects there and the menu labels it "(stable)".
   Evidence: `return (numbers, match.group(2) == "", match.group(2))` and `stable = tags[0] if
   tags else "latest"`; the docstring promises only that a prerelease sorts "behind the release
   it leads to", which holds, but not behind the last final release. Fix: choose `stable` as the
   newest tag whose suffix is empty (or skip a release whose `github.event.release.prerelease`
   is true), keeping the prerelease in `versions`.

3. **Every support pointer names a disabled issue tracker** (`README.md:45-46` "problems belong
   in the [issue tracker](https://github.com/Sauci/ddd/issues)"; `pyproject.toml:37` `Issues =
   ...`, which PyPI shows in the sidebar; `editors/vscode/package.json:15-18` `bugs` and `qna`).
   Trigger: a user of the official release follows any of them -> `gh issue list` answers "the
   'Sauci/ddd' repository has disabled issues" and the API reports `has_issues: false`; there is
   no way to report anything. Fix: enable issues before tagging 0.10.0, or point the three at
   where problems should go.

4. **The FAQ says an array has no bound; the tool caps it** (`docs/faq.rst:609-611` "There is
   no bound: a dimension is any integer of at least one ... and DDD caps neither the number of
   dimensions nor their product"). Trigger: a reader sizes a buffer by the page -> `ddd check`
   on `"dimensions": [10000001]` prints `error[schema]: 'Huge' has 10000001 elements; DDD
   carries at most 10000000` (run here), and a structure over 100 000 leaves is refused the same
   way; the caps are 0.9.0's own entry (`CHANGELOG.md:159-177`). Fix: state the four caps and
   that a shape past one is `schema` where it is written.

5. **"Nothing in the suite skips" is false by the page's own criterion**
   (`docs/developer_documentation.rst:301-304` "A test that skips when a tool is absent reports
   success without having run"; `tests/test_plugins.py:1972-1984` `if os.name != "nt":
   pytest.skip("directory junctions are a windows feature")`, then two more `pytest.skip` when
   `mklink` cannot run or the junction is not created). Trigger: every ubuntu cell of the CI
   matrix -> `test_a_junctioned_output_directory_is_reported_as_typed` is reported skipped and
   the junction path of the output-directory resolution (`CHANGELOG.md:419-436`) is exercised on
   Windows only, while the page tells a reader that every cell runs everything. Fix: run the case
   through a symlink where junctions do not exist, or amend the page and add the test it implies
   (no `pytest.skip`/`skipif` under `tests/`).

#### Minor

1. **The README's compile transcript is two objects stale** (`README.md:889-896` "20 of 21
   declared variables are defined ... 21 of 21"). `docker/verify_symbols.py` over today's demo
   prints `22 of 23 declared variables are defined` and `23 of 23` (run here, both variants): the
   demo gained `SoftwareLabel` and `StateName` with the strings. No test pins this block - it is
   not a `$ ddd` command. Fix: update the two counts.

2. **Developer page sentences the repository contradicts.** `:298-299` "The suite runs in a few
   seconds, so there is no reason to run anything less than all of it" - the baseline is 2 min
   22 s in the checkout and 10 min in a cold venv, and the line above it recommends `--no-cov`.
   `:336-337` "ci.yml runs exactly the commands above" - it also runs the extension job
   (`ci.yml:66-98`: `npm ci`, `npm test`, `npm run package`, an artifact), which the CI section
   never mentions; `:346` "Each job installs the project with pip install -e ".[dev]"" - the
   extension job installs `pip install -e .` (`ci.yml:84`). The layer table and "Three smaller
   modules" (`:16-62`) never name `src/ddd/lsp/` (nine modules in the wheel), `identity.py` or
   `build_info.py`, so the page that is the project's CLAUDE.md describes an architecture
   without its language server. Fix: three sentences and three table rows.

3. **The lock-file claim is unverified and nothing pins the lock's version**
   (`docs/developer_documentation.rst:510-513` "`npm ci` refuses a lock file out of step with its
   manifest, so a bump that edits only the manifest fails the extension job rather than a
   test"). `npm ci` validates the dependency specs of `package.json` against the lock, not the
   root package's `version` - unconfirmed here (no `npm` on this machine; run `npm ci` in
   `editors/vscode` with the manifest at `0.10.0` and the lock at `0.9.0`). Either way
   `tests/test_documentation.py:579-585` pins `package.json` only, so `package-lock.json:3` and
   `:9` can ship at 0.9.0 inside a 0.10.0 release. Fix: assert both lock entries equal
   `__version__` beside the manifest test.

4. **The environment paragraph describes a rule the repository does not carry** (carried over
   from the previous review's Minor 8; `docs/developer_documentation.rst:521-528` "GitHub creates
   an environment with its deployments restricted to the default branch ... choose Selected
   branches and tags ... add a tag rule for v*"). `gh api` reports `deployment_branch_policy:
   null` for `pypi` and `testpypi`, v0.9.0 deployed from its tag with that setting, and a leftover
   `github-pages` environment from the `deploy-pages` era still carries a branch policy although
   `docs.yml:238-239` says that environment is gone. Fix: describe the state that exists, or
   create the tag rule (which also closes Important 1) and keep the paragraph.

5. **Four of the five design records carry a stale status line** (`docs/superpowers/specs/`):
   `2026-09-02-xcp-measurement-rasters-design.md:4` "design approved, not implemented" (shipped in
   0.7.0); `2026-09-04-plugins-design.md:4` "approved design, not yet implemented" (0.8.0), and its
   `:445` still defers "Plugin backends under `all`", which 0.9.0 shipped;
   `2026-09-05-plugins-in-the-build-design.md:4` the same (0.9.0), and its `:36-37` says running
   CMake in CI is out of scope "held to the specification by text pins" while `tests/test_cmake.py`
   builds the module in every CI cell; `2026-09-10-string-conversion-design.md:4` "design
   approved, not implemented" (PR #29). Only `2026-09-03-object-identity-design.md:4` is current.
   Fix: one status line each, and strike the shipped deferral.

6. **Changelog wording that the release commit must touch, and two gaps.** `CHANGELOG.md:31`
   "format 8 is unreleased, and a reader that only knows 7 already refuses it" stops being true
   the moment `## Unreleased` becomes `## 0.10.0` (the one "unreleased" left outside the heading).
   The "Strings" entry (`:33-47`) says nothing about the comparison of a string `init` between
   deliveries, although `src/ddd/compare.py` changed for it (`c2b2ce8`) and pass 3's P3-I2 found
   the rule wrong; its "a quoted number as an init ... is now text, refused" is contradicted for
   the nested case by P2-I1, and the constants entry's "a template emits the literal as written"
   by P2-M4 (`2.50` -> `2.5`). `README.md:42-44` still defines the public interface without the
   address map, the dumped dictionary, the `--renames` file and `ddd-build.json` that
   `CHANGELOG.md:7-13` now names (the previous review's Minor 6, half applied), and
   `README.md:933` counts "Four more suites" where `docs/developer_documentation.rst:267` counts
   five. Fix: reword `:31` in the release commit, add a sentence to the strings entry, align the
   README sentence.

7. **Supply-chain hygiene.** Every action is pinned by major tag only (`ci.yml:35-36,79,95`,
   `docs.yml:45-46,66,138`, `publish.yml:24-25,36-37,63,88,92,121,125,139,143`), and the two jobs
   that hold the OIDC token use `pypa/gh-action-pypi-publish@release/v1`, a moving branch
   (`publish.yml:125,143`); `publish.yml:40` installs `pip build twine` unpinned at release time and
   `editors/vscode/package.json:74` runs `npx --yes @vscode/vsce package`, fetching whatever
   `vsce` is current on the day; `requirements-dev.txt:1-13` carries lower bounds only, so a new
   `ruff` (`ruff format --check` is a gate, `ci.yml:63`) or `mypy` release can turn the lint job
   red on a release day; there is no `.github/dependabot.yml`. `ci.yml:95` uses
   `actions/upload-artifact@v5` while `docs.yml:66` and `publish.yml:63` use `@v7`. Concrete
   risk: a compromised or broken tag reaches the token-holding job unreviewed, and a release is
   blocked by a tool nobody upgraded. Fix: pin by commit sha with a dependabot config for
   `github-actions`, `pip` and `npm`, and cap `ruff`/`mypy` to a minor.

8. **The extension is built and released on Node 20, end of life since 2026-04-30**
   (`ci.yml:79-81`, `publish.yml:92-94` `node-version: "20"`; `editors/vscode/package.json:81`
   `@types/node ^20.11.0`; the Node.js schedule gives v20 `end: 2026-04-30`, v22 2027-04-30). Risk:
   the release's `.vsix` is packaged on a runtime without security fixes, and `setup-node` may
   stop offering it. Fix: 22 or 24, and the matching `@types/node`.

9. **The container's edges.** `docs/conf.py:97-99` says plantuml is called "through the jar the
   documentation image ships at /plantuml.jar" - `docker/Dockerfile:38` installs the apt
   `plantuml` launcher and ships no jar, so the default path never exists and the fallback at
   `:102` is what the image runs (harmless, stale). `docker/compile.sh:53` runs `ddd dump
   --format json` after `ddd generate` although `generate --dictionary` now writes the same
   dictionary in the same write (`CHANGELOG.md:68-76`), and the `--format json` empty report
   lands in the log as a JSON block after the `wrote` lines (seen in the run here).
   `.dockerignore:1-12` leaves `node_modules/`, `htmlcov/`, `.coverage` (467 KB here), `*.vsix`,
   `docs/_build/`, `editors/vscode/out/` and `docs/superpowers/*.pdf` (3.5 MB) in the build
   context. `docker-compose.yml:90-95` reinstalls `.[docs]` on every `docs` run. No workflow
   builds the image, which is how it broke unnoticed before (`CHANGELOG.md:658-663`). Fix: the
   comment, `--dictionary`, seven ignore lines, and a `docker build` job or a note that it is
   unguarded.

10. **Acronyms the pages use and the acronyms page lacks** (`docs/acronyms.rst:13-85`): ASCII
    (`docs/consistency_checks.rst:566`), RAM (`:382`), ROM and NVM
    (`docs/file_formats/sections.rst:5`), WSL (`docs/build_integration.rst:588`), GCC
    (`docs/faq.rst:366`), MISRA (`docs/templates.rst:34`), IEEE 754
    (`docs/file_formats/variable_definition.rst:232`), ARXML (`docs/concept.rst:541`), OIDC
    (`docs/developer_documentation.rst:452`), UTF-16 (`docs/comparing_deliveries.rst:99`), ISO
    (`docs/templates.rst:288`), MSVC (`docs/build_integration.rst:120`), AUTOSAR
    (`docs/templates.rst:290`), VSIX (`docs/developer_documentation.rst:536`), API (`:451`), NaN
    (`docs/data_contracts.rst:133`). Also `docs/conf.py:74-77` counts "twenty-six models" where
    `docs/data_contracts.rst` renders thirty-one. The concept page's vocabulary and the acronyms
    page agree with `SPEC.md` section 2 (checked term by term).

11. **The README's relative links are the index page's** (`pyproject.toml:13` `readme =
    "README.md"`): `SPEC.md`, `LICENSE`, `CHANGELOG.md`, `src/ddd/ir.py`, `cmake/Ddd.cmake`,
    `examples/...`, `tests/...`, `editors/vscode`, `docker/...` and the `#cmake-integration`
    anchors resolve on GitHub and not on `pypi.org/project/ddd-tool/`, where `readme_renderer`
    leaves them as written; the logo alone uses an absolute url for exactly that reason
    (`assets/logo/README.md:52`). Unconfirmed - PyPI answered `curl` with a bot challenge; open
    the project page and click `SPEC.md`. Fix: absolute `github.com/Sauci/ddd/blob/master/...`
    links, or a `readme` written for the index.

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| P6 Important 1 | README says `NO_PROPAGATE_HEADERS` on the second call only | fixed | `README.md:830-838` "to **both** calls" |
| P6 Important 2 | sdist ships tests and docs that cannot run from it | fixed | `pyproject.toml:70-96`; suite from the sdist: 2284 passed, coverage 100% |
| P6 Important 3 | data_contracts renders 21 of 31 models | fixed | `docs/data_contracts.rst:236-348` (the new `StringConversion` gap is pass 2's P2-M3) |
| P6 Minor 1-5, 7, 9-11 | FAQ address-map count, "same two overrides", README `--without`/`TEMPLATES`, `BUILT_IN_GENERATED`/`base.py` docstring, two superseding entries, version files unlisted, Dockerfile double install, demo description, transcript suite unnamed | fixed | `docs/faq.rst:90,511`; `README.md:673-679,900`; `docs/developer_documentation.rst:176-191,505-519,278-284`; `src/ddd/backends/base.py:6-9`; `CHANGELOG.md:363-370`; `docker/Dockerfile:49-53`; `examples/demo/demo.ddd.json:5` |
| P6 Minor 6 | changelog header narrower than what it treats as interface | partly fixed | `CHANGELOG.md:7-13` extended; `README.md:42-44` not (Minor 6 here) |
| P6 Minor 8 | environment rule the repository does not carry | still open, carried over | Minor 4 here; `deployment_branch_policy: null` |
| P6 follow-ups | stale status lines in the design records | still open, carried over | Minor 5 here |

### Open questions

- Is 0.10.0 `Development Status :: 5 - Production/Stable` (`pyproject.toml:19` says `4 - Beta`)?
  The answer changes one classifier in the release commit and what "official" means on the index.
- Does the official release claim Python 3.14 (`pyproject.toml:23-24`, `ci.yml:32`; 3.14 shipped
  2025-10)? `tests/test_documentation.py:1470-1488` holds the matrix and the classifiers
  together, so the answer is two lines or none.
- Is the 0.10.0 GitHub release a full release? All five so far are flagged pre-release
  (`gh release list`), and nothing in the workflows reads the flag; the answer changes the
  release page and, if Important 2 is fixed by reading the flag, which release the site calls
  stable.
- Where should problems go (Important 3): enable issues, or replace the three urls?
- Does `workflow_dispatch` keep a `pypi` target at all (Important 1)?
- Which Node for the extension jobs (Minor 8)?

### Release checklist

Ordered; each step names the file and line the 0.10.0 release commit or the maintainer touches.

1. Land the fixes this review decides on first - at least Important 3 (a support channel that
   exists), Important 4 (the FAQ), Minor 6's `CHANGELOG.md:31`, and Important 1 if the `pypi`
   dispatch target goes - so that the release commit is a version bump only, as `release/0.9.0`
   was (9 files, 19 lines).
2. Dry run: Actions -> Publish -> Run workflow, `target: testpypi`, on master
   (`.github/workflows/publish.yml:9-15`, `:111-127`); it exercises `test`, `build`, `twine check
   --strict` and the TestPyPI trusted publisher (`docs/developer_documentation.rst:457-497`).
3. The release commit, on a `release/0.10.0` branch:
   - `src/ddd/__init__.py:16` `__version__ = "0.10.0"` (where `docs/conf.py:13` and every banner
     take it from);
   - `pyproject.toml:11` `version = "0.10.0"` (what the tag is checked against,
     `publish.yml:51-60`);
   - `editors/vscode/package.json:5`;
   - `editors/vscode/package-lock.json:3` and `:9`;
   - `README.md:54` the wheel file name;
   - `docs/getting_started.rst:29` (wheel name), `:39` (`ddd --version`, pinned by
     `tests/test_transcripts.py`), `:57` (shown, not run), `:399`, `:433`, `:466` (banners);
   - `docs/generated_artefacts.rst:134`, `:516`, `:603`, `:610`;
   - `docs/faq.rst:576`;
   - `docs/templates.rst:180`;
   - `CHANGELOG.md:15` `## Unreleased` -> `## 0.10.0` (the older headings carry no date) and
     `CHANGELOG.md:31` reworded (Minor 6);
   - if decided: `pyproject.toml:19` (Development Status), `pyproject.toml:23-24` with
     `ci.yml:32` (3.14).
   Tests that fail on a half-done bump: `tests/test_documentation.py:573-577` (`pyproject.toml`),
   `:579-585` (`package.json`), `tests/test_transcripts.py` on `docs/getting_started.rst:38-39`.
   Nothing pins the lock file, the two wheel names, the seven banners, `:57` or the changelog -
   walk them by hand (`docs/developer_documentation.rst:505-519`), then `ruff check .`,
   `ruff format --check .`, `mypy`, `python -m pytest`, `sphinx-build -b html docs out -W
   --keep-going`, `PYTHONPATH=src python -m ddd --version` -> `ddd 0.10.0`, `python -m build` ->
   `ddd_tool-0.10.0.tar.gz` and `ddd_tool-0.10.0-py3-none-any.whl`.
4. Pull request, merge into master; wait for CI (four matrix cells, lint, extension) and
   Documentation (which deploys `latest`, `docs.yml:78`) to be green on the merge commit.
5. Create the GitHub release on that commit with tag `v0.10.0` - exactly `v` plus
   `pyproject.toml:11`, or `publish.yml:55-59` stops before anything is uploaded - and the
   changelog section as notes; decide the pre-release flag (open question). Publishing it runs
   `publish.yml` (`test` -> `build` -> tag check -> `twine check` -> `publish-pypi` through the
   `pypi` environment's trusted publisher; `extension` -> `ddd-0.10.0.vsix` uploaded with
   `--clobber`, `:106-109`) and `docs.yml` (`site/v0.10.0`, `versions.json` with `stable:
   v0.10.0`, the root redirect, then the read-back, `docs.yml:265-290`).
6. Verify from outside: `pip index versions ddd-tool` lists 0.10.0 and a fresh venv's
   `pip install ddd-tool==0.10.0` answers `ddd 0.10.0`; `https://sauci.github.io/ddd/versions.json`
   says `"stable": "v0.10.0"` and `https://sauci.github.io/ddd/v0.10.0/` answers 200; the release
   carries `ddd-0.10.0.vsix`; both workflow runs are green.
7. If a job fails after the PyPI upload, re-run the failed jobs - the `.vsix` upload clobbers and
   the docs deploy rewrites `site/v0.10.0` - but the index upload cannot be redone: a wrong
   artefact on PyPI means 0.10.1. If the tag check fails, delete the release and the tag and
   re-create them (`publish.yml:56-58`).
8. Afterwards: a new `## Unreleased` heading with the first change; the pypi.org publisher needs
   no change (0.9.0 already uploaded through it).

### Test gaps

- `tests/test_documentation.py` (`TestPackaging`): the two version fields of
  `editors/vscode/package-lock.json`; the wheel file name in `README.md:54` and
  `docs/getting_started.rst:29` and the seven banners as `__version__`; the README's
  `== symbols` counts (Minor 1) - derivable by running `docker/verify_symbols.py`'s `main` over
  the demo dump and the object names of `ddd_globals.c`.
- `tests/test_documentation.py`: the convention "nothing in the suite skips" (no `pytest.skip`,
  `skipif`, `importorskip` or `xfail` under `tests/`), which would have caught Important 5.
- `tests/test_backends.py` (`TestLayering`): `compare.py`, `identity.py`, `build_info.py`,
  `cli.py` and `src/ddd/lsp/` sit outside the import-graph guard, so the language server
  importing a backend, or `compare.py` importing the loader, would pass.
- `docs.yml`'s `order()`/`stable` (`docs.yml:167-182`) has no test at all - it is Python inside
  a heredoc; extracting it to `docker/` or a `tools/` script would let
  `tests/test_documentation.py` pin the prerelease and hotfix orderings (Important 2).
- No workflow builds `docker/Dockerfile` (Minor 9); `tests/test_cmake.py` covers the module but
  nothing covers the image, `compile.sh` or `verify_symbols.py` in CI.

### Assessment

The release path is sound where it has been exercised: the wheel and the sdist build and install,
the tutorial reproduces from outside the repository, the sdist runs its own suite through the
coverage gate, the site and the index are in the state the pages describe, and the changelog's
entries say what the code does. What would make the first official release publish something
wrong sits at the edges nobody has walked yet: a dispatch path that uploads to PyPI unchecked, a
version sort that would crown a release candidate, and three support links pointing at a tracker
that is switched off - each a small change, and each best made before the tag. The developer
page, which is the project's own rulebook, has drifted in a handful of sentences (the suite
skips, runs for minutes, has an extension job and a language server), the FAQ still promises
unbounded arrays two releases after the caps, and the release commit has nine files and one
changelog sentence to touch with only three of them under test.

### Verification

Every candidate of this pass was handed to a second reviewer (group E): 14 confirmed, 2 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P7-I1 | Important | CONFIRMED | Important | `publish.yml:131` `if: github.event_name == 'release' \|\|inputs.target == 'pypi'`; the tag check `:52` runs only `if: github.event_name == 'release'`; `gh api repos/Sauci/ddd/environments/pypi`: `deployment_branch_policy: null`, `protection_rules: []` |
| P7-I2 | Important | CONFIRMED | Important | `order()` copied from `docs.yml:167-173` and run: `v0.9.0` on the site + release `v0.10.0rc1` -> `stable v0.10.0rc1`; + `v0.10.0` -> `v0.10.0`; hotfix `v0.9.1` after `v0.10.0` -> `v0.10.0` (right); `v0.9.1` beside the rc alone -> `v0.10.0rc1` |
| P7-I3 | Important | CONFIRMED | Important | `gh api repos/Sauci/ddd --jq .has_issues` -> `false`; `README.md:45-46` "problems belong in the [issue tracker](https://github.com/Sauci/ddd/issues)", `pyproject.toml:37` `Issues = ...`, `package.json:16,18`; PyPI's 0.9.0 metadata already carries the url |
| P7-I4 | Important | CONFIRMED | Important | `faq.rst:609-611` "There is no bound ... caps neither the number of dimensions nor their product"; `ddd check` on `"dimensions": [10000001]` -> `error[schema]: 'Huge' has 10000001 elements; DDD carries at most 10000000`, exit 1 (`[10000000]` passes) |
| P7-I5 | Important | CONFIRMED | Minor | `developer_documentation.rst:301` "Nothing in the suite skips."; grep of `tests/`: `test_plugins.py:1973` `pytest.skip("directory junctions are a windows feature")` under `if os.name != "nt"`, `:1982`, `:1984`; nothing else |
| P7-M1 | Minor | CONFIRMED | Minor | `README.md:891` "20 of 21 declared variables are defined", `:894` "21 of 21"; `verify_symbols.py` over a fresh `ddd dump` of the demo and the finder's `nm` lists -> "22 of 23" / "23 of 23" |
| P7-M2 | Minor | CONFIRMED | Minor | `:298-299` "The suite runs in a few seconds" (baseline 2 min 22 s); `:336` "runs exactly the commands above" vs `ci.yml:66-98`; `:346` vs `ci.yml:84` `pip install -e .`; grep of the page for `lsp`, "language server", `identity.py`, `build_info`: no hit, nine modules in `src/ddd/lsp/` |
| P7-M3 | Minor | PLAUSIBLE | Minor | `tests/test_documentation.py:573-585` pin `pyproject.toml` and `package.json` only; `package-lock.json:3,9` `"version": "0.9.0"`; no `npm` on this machine to run `npm ci` against a bumped manifest |
| P7-M4 | Minor | CONFIRMED | Minor | `gh api repos/Sauci/ddd/environments`: `pypi` and `testpypi` `deployment_branch_policy: null` (`github-pages` still `custom_branch_policies: true`); `:521-528` tells the reader to add a `v*` tag rule |
| P7-M5 | Minor | CONFIRMED | Minor | the four status lines at `:4` say "not (yet) implemented" against `CHANGELOG.md:623` (0.7.0 rasters), `:579` (0.8.0 plugins), `:312` (0.9.0 plugins in the build), `:33` (strings); `plugins-design.md:445` defers plugin backends under `all` while `CHANGELOG.md:339` says "`all` is the only run that produces a plugin's artefact"; `plugins-in-the-build-design.md:37-38` defers CMake in CI while `ci.yml:48` `pytest` runs `tests/test_cmake.py` |
| P7-M6 | Minor | CONFIRMED | Minor | `CHANGELOG.md:31` "format 8 is unreleased"; `:33-47` says nothing of comparing a string `init` although `ac3c87a` added `_describe_init` to `compare.py`; `README.md:42-44` vs `CHANGELOG.md:7-13`; `README.md:933` "Four more suites" vs `developer_documentation.rst:267` "Five suites" |
| P7-M7 | Minor | CONFIRMED | Minor | every `uses:` pinned by major tag; `publish.yml:125,143` `pypa/gh-action-pypi-publish@release/v1`; `:40` `pip install --upgrade pip build twine`; `package.json:74` `npx --yes @vscode/vsce package`; `requirements-dev.txt:1-13` lower bounds only; `.github/` holds only `workflows/`; `ci.yml:95` `upload-artifact@v5` vs `@v7` in the other two |
| P7-M8 | Minor | CONFIRMED | Minor | `ci.yml:81`, `publish.yml:94` `node-version: "20"`; `package.json:81` `"@types/node": "^20.11.0"`; Node 20's maintenance ended 2026-04-30 on the Node.js schedule (not re-fetched here) |
| P7-M9 | Minor | CONFIRMED | Minor | `docs/conf.py:97-102` names `/plantuml.jar`, `Dockerfile:38` installs apt `plantuml` and copies no jar; `compile.sh:53` `ddd dump ... --format json` after `generate all` while `ddd generate c --help` offers `--dictionary FILE`; `.dockerignore` (12 lines) lacks seven of `.gitignore`'s patterns, `docs/superpowers/*.pdf` (3.4 MB) and `.coverage` (376 KB) sit in the tree; `docker-compose.yml:95` reinstalls `.[docs]`; no workflow runs `docker` |
| P7-M10 | Minor | CONFIRMED | Minor | each of the 17 terms has a page hit (ASCII `consistency_checks.rst:566` ... NaN `data_contracts.rst:133`) and none is on `docs/acronyms.rst`; `docs/conf.py:76` "twenty-six models" vs 31 `autopydantic_model` directives on `data_contracts.rst` (35 with `data_dictionary.rst`) |
| P7-M11 | Minor | PLAUSIBLE | Minor | `pyproject.toml:13` `readme = "README.md"`; 32 relative links in `README.md` (`:13` `](SPEC.md)` ...) and the same 32 in the 0.9.0 description PyPI's json api returns; `assets/logo/README.md:52` "the package index, which renders neither a relative path nor an svg"; pypi.org answers curl and WebFetch with a "Client Challenge" page only |

Notes of the verifier:

- **P7-I5** - regraded to Minor. The sentence is false, but what contradicts it is a
platform-conditional skip of a Windows-only feature (`mklink /J` needs no privilege, so the
two fallback skips at `:1982,1984` are dead on a Windows runner), and every ubuntu run
summary reports the skip; no behaviour, verdict or output is hidden by it, so it is a
developer-page inconsistency to amend, or a skip to turn into a symlink case, not a
misleading contract.

- **P7-M3** - PLAUSIBLE. The half I can check is confirmed: nothing pins the two `version`
fields of `package-lock.json`. The half that decides the outcome - `npm ci` passing a lock
whose root `version` differs from the manifest's - needs `npm`, absent here; npm's documented
`ci` rule speaks of the dependencies matching, not the root version, so the finder's doubt
is well founded. What would confirm it: `npm ci` in `editors/vscode` with the manifest at
`0.10.0` and the lock at `0.9.0` exiting 0.

- **P7-M11** - PLAUSIBLE. The mechanism is in hand - the uploaded description carries the 32
relative links verbatim, and the project's own `assets/logo/README.md:52` records that the
index renders no relative path - but pypi.org hands curl and WebFetch a "Client Challenge"
page, so the 404 itself was not seen. What would confirm it: open
`pypi.org/project/ddd-tool/` in a browser and click `SPEC.md`.

## Pass 8: code review of the core, part A (models, loading, diagnostics, identity)

### Scope covered

Read in full, with line numbers, on the review tree (`master` at `6e9e99f`): `src/ddd/__init__.py`,
`src/ddd/__main__.py`, all thirteen files of `src/ddd/models/` (`__init__`, `common`, `component`,
`constants`, `conversion`, `objects`, `project`, `rasters`, `reserved`, `schema`, `sections`,
`types`, `units`), `src/ddd/loading.py` 1-1272, `src/ddd/diagnostics.py` 1-523,
`src/ddd/identity.py` 1-183, and `src/ddd/lsp/ranges.py` 1-324, because `identity.assign` and
every finding's range go through its `Document`. For the cross-module angle: `src/ddd/cli.py`
95-128, 593-622, 1012-1025, 1356-1460 and every use it makes of the core (grep);
`src/ddd/plugins.py` 94-345; `src/ddd/ir.py` 41-67, 127-190, 583-673; `src/ddd/lsp/diagnostics.py`
63-233,
`lsp/server.py` 1-30, 185-235, 290-312, `lsp/edits.py` 125-160; the import lists and every helper
use in `src/ddd/analysis.py` and `src/ddd/compare.py` (grep); `src/ddd/backends/c/literals.py`.
Tests: the names of the nine listed files, and the bodies of `tests/test_hardening.py` 563-635,
950-1057 and `tests/test_loading.py` 53-63, 434-448. `docs/developer_documentation.rst` 16-63 and
193-242, the coverage section of `pyproject.toml`, `SPEC.md` 63-78, 245-266, 1814-1834, 1854-1866,
1880-1890; `previous-review.md` 52-176 (its pass 7); `reports/pass-1.md` to `pass-7.md`.

Ran, from the venv, everything kept under `scratchpad/pass-8/`: `facts.py` (Python and pydantic
facts, `facts.txt`); `probes.py`, `probes2.py`, `probes3.py` (about 80 commands over 40 throwaway
cases under `cases/`, transcripts `results.txt`, `results2.txt`, `results3.txt`: `check`,
`check --standalone`, `dump`, `compare`, `sources`, `id --assign`, `generate c|a2l`, MinGW gcc 13.1
`-fsyntax-only` on generated c, `jsonschema` over the published component schema, a `subst` drive);
`lsp_probe.py` (a scripted `initialize`/`didOpen` against `ddd lsp`, `lsp_probe.txt`); `gen.py` and
`timeit2.py` (the synthetic project and the timings, `perf_results.txt`); the cold-start and
`python -X importtime` measurements (`importtime.txt`). Probe ids `Pnn`/`Qnn` below refer to those
transcripts.

Forwarded items, settled from the code:

- Pass 2 Important 1 (a quoted number nested in a list init): the chain is `InitValue =
  InitScalar | str | tuple[InitElement, ...]` (`src/ddd/models/objects.py:44-46`), whose tuple
  items are `InitElement = InitScalar | tuple[InitElement, ...]` (`:36`) with `InitScalar =
  Annotated[int, Field(ge, le)] | bool | Real` (`:33`) - no `str` arm below the top level and no
  `strict` on any arm. pydantic's smart union first tries every arm in strict mode, where a
  `str` matches only a `str` arm: at the top level the `str` arm wins before any coercion; one
  level down there is none, so the union falls back to the lax pass, where the `int` arm parses
  `"1"`, `" 1 "` and `"1_0"`, the `bool` arm parses `"yes"`/`"no"`/`"on"`/`"off"`/`"true"`, and
  the `float` arm parses `"1.5"` and `"1e2"` (`facts.txt`; P03: `"init": ["on", "off"]` on a
  `uint8[2]` checks clean and dumps as `[true, false]`, which `backends/c/literals.py:29` renders
  as `{ 1U, 0U }`; `[" 1 ", "1_0"]` dumps as `[1, 10]`). So the fix pass 2 proposed has to make
  all three arms strict, not the `int` and `float` arms alone: the `bool` arm matches by exact
  type only in strict mode, in lax mode it reads words.
- Pass 2 Important 2 and 3, Minor 7 and 9: confirmed from the code (`common.py:144-146`,
  `objects.py:147`, `:484`, `types.py:173`, `conversion.py:87-90`; `loading.py:1154-1193`). A
  second defect of `_one_per_place` is Important 3 below.
- Pass 3 Minor 7: `loading.py:459` `found <= DICTIONARY_FORMAT` after `isinstance(found, int)`
  passes `"9"` and `9.0` to `ir.py:593` `format: int = DICTIONARY_FORMAT`, a lax `int`; P06 adds
  that `0` and `-3` pass the same way (below, Minor 7).
- Pass 5 Minor 4: `identity.py:182` `path.write_bytes(...)` is unguarded, confirmed; the write is
  also not atomic (Minor 18).
- Pass 1 Important 4 / pass 2 open question 2 (the sort key): `loading.py:1006-1010` sorts
  `Path` objects. `PurePath.__lt__` compares `_str_normcase`, which on Windows is
  `ntpath.normcase(str(self))` - lower-cased, backslashed - and on POSIX the string itself. The
  set `Zeta, _under, alpha, Beta, beta2` therefore orders `_under, alpha, Beta, beta2, Zeta` on
  Windows and `Beta, Zeta, _under, alpha, beta2` on POSIX (`facts.txt`, `PureWindowsPath` and
  `PurePosixPath` side by side); a code-point sort - `key=lambda p: p.as_posix()` - would give
  the POSIX order on both. `SPEC.md:255-258` now states the platform order, so the loader
  conforms; the same `sorted(Path)` orders `read_paths` (`:531`, `:558`) and `sources()` (`:396`).
- Pass 6 Important 1 (the resolved spelling): the loader canonicalises in exactly three places -
  the root (`loading.py:498` `_resolve(path)`), a literal include (`:992`) and every wildcard
  match (`:1009`) - and dedupes on the resolved path (`_seen_paths`, `:1026`), so two spellings
  of one file never load twice (P12: a `subst` drive resolves to the real path, and
  `relative_to(Path.cwd())` is suppressed on a `ValueError`, `diagnostics.py:309-310`, so a
  path on another drive renders absolute rather than raising).
- The previous review's pass 7 Important 2, 3, 4, 6, 8 and design note 3: status table below.

Performance (`perf_results.txt`; N components of 50 objects each - 30 measurements, 5 inputs
read from the next component, 5 parameters in a section, 3 constant-dimensioned value blocks, 2
axes, 2 curves, 1 map, 2 structured measurements of a shared two-level structure, the rest a
shared scalar type - plus types, units, sections, constants and rasters files, every producer
stamped with an id; wall clock of `ddd check -W unused-output=ignore`, best of two):

| N | objects | `ddd check` | load (in process) | analyze (in process) |
| --- | --- | --- | --- | --- |
| 10 | 530 | 0.46 s | - | - |
| 100 | 5 300 | 0.86 s | 0.13 s | 0.29 s |
| 1000 | 53 000 | 6.06 s | 1.50 s | 3.89 s |

The loader is linear (0.13 s to 1.50 s for ten times the files). Profiled at N = 1000 (cProfile,
2.57 s under the profiler): pydantic's `validate_python` 52 %, `_locations` 20 % (0.41 s of its own
time building 50 000 `Location`s the analysis then builds again - harmless), `Path.resolve` 9 %,
`json.loads` 8 %, `read_text` 6 %; nothing in these modules dominates. Cold start: `ddd --version`
and `ddd --help` 0.40 s each against 0.05 s for `python -c pass`, of which 0.38 s is
`import ddd.cli` (`importtime.txt`: `ddd.analysis` 176 ms cumulative including `ddd.compare` and
`ddd.ir`, `ddd.models` 111 ms, `ddd.backends` 51 ms with jinja2, `ddd.diagnostics` 48 ms,
`pydantic` 38 ms).

### Strengths

- Every failure of reading came back as a located finding: a directory as the root and as an
  include, a bare `**` sweeping a text file and a 1 MB binary, a 300 MB file of whitespace
  (1.5 s) and of random bytes (1.2 s), a NUL byte, a 5000-digit integer, a 400-digit limit and
  enumerator value, `NaN` and `Infinity` inside a dumped dictionary, a project at the root of a
  `subst` drive with rooted includes (P06, P07, P11, P12, P13, Q1). Only Important 1 below ends
  in a traceback.
- The 64-bit bound sits on every integer path - `common.py:145`, `conversion.py:46`,
  `constants.py:45`, `objects.py:33` and `:70`, `sections.py:52`, `rasters.py:86` - and
  `within_64_bits` (`common.py:122-141`) runs ahead of every union that has a float arm, with
  `tests/test_models.py:423-780` pinning both ends of the range.
- The pointer sort splits on the captured index (`diagnostics.py:291-292`), so a key that only
  looks numeric sorts as text; the severity policy parses whitespace, case, a second `=`, an
  empty check name and a plugin prefix into exactly the documented usage errors (P16).
- The vocabulary registries share one `_register` (`loading.py:713-736`), so the duplicate rule
  holds across a component's inline types and constants and the standalone files alike, with a
  note at the first declaration.
- `sources()` lists the vocabulary files and the plugin modules beside the components (P15), and
  a file that was read and rejected stays a source (`loading.py:566-569`).
- The eight published schemas carry no reStructuredText leftover (a grep of `schemas/*.json` for
  roles, directives and single backticks finds none), and `schema.py` derives the conversion
  kinds and the per-value documentation from the models rather than from lists.
- `_validate_block` runs a plugin's own model under `guarding_plugin_model` (`loading.py:978`),
  so a raising validator becomes one `PluginError` line at the cli and `plugin-invalid` in the
  server (`lsp/diagnostics.py:85-89`) rather than a traceback.

### Issues

#### Critical

None found.

#### Important

1. **A description nested about 500 levels deep ends `ddd id --assign` and the language server
   with a `RecursionError`, while `ddd check` accepts the same file** (`src/ddd/lsp/ranges.py:60`
   `scanner.value("")` - outside the `try` at `:46-48`, which guards `json.loads` alone; the
   scanner recurses two frames per level, `:243-297`; reached from `src/ddd/identity.py:172`
   `document = Document(text)` and from `ranges.py:225` `found = Document(text)` for every file
   a finding is drawn on). Trigger: a component whose `extensions` block nests 520 lists
   (`cases/P01_deep`). Outcome: `ddd check --standalone c.ddd.json` exits 0 with one
   `missing-id`; `ddd id --assign c_520.ddd.json` prints a traceback ending in `RecursionError:
   maximum recursion depth exceeded` and exits 1, where 480 levels are stamped (P01b, P01c); a
   `didOpen` of the file ends `ddd lsp` after the `initialize` answer with the same traceback
   (`lsp_probe.txt`, exit 1 in 0.5 s). Python's json parser gives up only at about 3000 levels
   here (`facts.txt`: 1000 "SCANNER RecursionError", 3000 "json RecursionError"), so the
   band between the two passes the guard that `fix/core-robustness` added and
   `tests/test_hardening.py:587-599` pins only the 100 000-level case above it. Fix: catch
   `RecursionError` around the scan as well (`data = None`, empty spans), or make `_Scanner`
   iterative; a test at 600 levels beside the existing one.

2. **A finding under a definition whose key is spelled with punctuation, or with the name of a
   union variant, is located one level too high, because the pointer walk drops the document
   after the first union tag** (`src/ddd/loading.py:1222` `present, node = _child(node, item)`:
   a segment such as `measurement` is absent from the document, `node` becomes `None`, and
   every later segment is judged by shape alone, `:1223` and `:1267`). Trigger: `"extensions":
   {"a-b": 1}` or `{"map": [1]}` on a definition -> `error[schema]:
   ...component.interface[0].definition.extensions: Input should be a valid dictionary (got:
   1)` with the key gone from the pointer (P02a, P02b), while the same block on the project,
   where no tag precedes it, keeps its key (`project.extensions.a-b`, P02d) - which is exactly
   what `tests/test_loading.py:434-448` pins, at the project level only. A plugin named after
   a variant (`map`, `axis`, `enum`, `string`, `linear`, `curve`...) is a legal plugin name
   (`plugins.py:42`), so the pointer of every malformed block of such a plugin lands on
   `extensions` and the editor underlines the whole block. Fix: advance `node` only when the
   segment was present (`if present: node = child`), so that the walk survives a tag.

3. **Two malformed extension blocks in one definition or one project become one finding**
   (`src/ddd/loading.py:1167` `kept.setdefault(_pointer(item["loc"]), item)` - `_one_per_place`
   keys on the pointer computed without the document, so any key `_is_branch_tag` misjudges by
   shape, or that is in `_UNION_TAGS`, is stripped and two places collapse into one). Trigger:
   `"extensions": {"a-b": 1, "c-d": 2}` on a definition, or `{"map": [1], "axis": [2]}`, or
   `{"a-b": 1, "c-d": 2}` on the project -> one `schema` finding, the second block never
   reported (P02a, P02b, P02d); the control `{"aa": 1, "bb": 2}` gives two (P02c). A lost
   finding on a file the loader refuses, so the reader fixes one block, runs again and meets
   the next. Fix: hand `_one_per_place` the document (key on `_pointer(loc, document)`, or on
   the raw `loc` with the known tags removed), and pin the two-block case in
   `tests/test_loading.py`.

#### Minor

1. **A `condition` ending in a backslash splices the next generated line into the `#if`**
   (carried over, previous pass 7 Minor 1; `src/ddd/models/component.py:78` `for token in
   ("/*", "*/", "//", "#"):` refuses line breaks and comment tokens only). Trigger (Q2):
   `"condition": "defined(FEAT_X) \\"` -> `ddd check` ok, `ddd generate c` writes `#if
   defined(FEAT_X) \` followed by `extern volatile uint8_t A;`, and gcc stops with `error:
   missing binary operator before token "extern"`. Loud, so minor. Fix: refuse a stripped
   condition ending in `\`.

2. **Names MinGW's `<stdint.h>` declares by way of `<crtdefs.h>` pass `reserved-identifier` and
   fail the build** (`src/ddd/models/reserved.py:54` `if _STANDARD_TYPE_PATTERN.match(name) or
   _STANDARD_MACRO_PATTERN.match(name):`; the docstring at `:12-14` promises "everything
   ``<stdint.h>`` declares, because a project's types header may include it"). Trigger (Q3):
   a measurement named `size_t`, `NULL`, `wchar_t`, `ptrdiff_t` or `errno` -> `ddd check` "ok",
   `ddd generate c` with the example templates, and gcc 13.1 (MinGW) refuses the header:
   `'size_t' redeclared as different kind of symbol`, `<stdint.h>:28` -> `<crtdefs.h>`.
   `offsetof`, `assert` and `EOF` compile here; the C23 width macros (`UINT8_WIDTH`,
   `SIZE_WIDTH`) are absent from `_STANDARD_MACRO_PATTERN` (`:42-47`) and compile with this
   toolchain, which does not define them under `-std=c2x` (unconfirmed for a glibc toolchain,
   which does). Fix: add the `<stddef.h>` names (`size_t`, `ptrdiff_t`, `wchar_t`,
   `max_align_t`, `NULL`, `offsetof`) and the `_WIDTH` family; `errno` is `<errno.h>`'s and
   stays a project's own risk.

3. **The a2l format pattern admits non-ASCII digits** (`src/ddd/models/common.py:102`
   `A2L_FORMAT_PATTERN: Final = r"^%\d*\.\d+$"`; pydantic compiles it with the Rust engine,
   where `\d` is Unicode). Trigger (P04): `"a2l": {"format": "%\u0663.\u0662"}` (Arabic-Indic
   digits) -> `ddd check` ok and the generated a2l carries `FORMAT "%٣.٢"`, a string no
   calibration tool parses as a format. The published pattern is the same text under ECMA-262,
   where `\d` is `[0-9]`, so an editor bound to the schema refuses what the loader accepts
   (unconfirmed for the editor - Python's `jsonschema` accepts it too, `re` being Unicode). Fix:
   `[0-9]` in the pattern.

4. **`_resolve` expands a leading `~`** (`src/ddd/loading.py:1206` `return
   Path(path).expanduser().resolve()`). Trigger (P05): a root file named `~x.ddd.json` given
   relative to the working directory -> `C:/Users/x.ddd.json: error[file-not-found]`, a path
   the author never wrote (Windows reads `~x` as user `x`). Only the root is exposed - an include
   is joined to an absolute parent first - and only when the shell did not expand the tilde
   itself. Fix: drop `expanduser()`; expansion is the shell's.

5. **`ddd id --assign` silently skips a declaration whose `name` key is spelled with a json
   escape** (`src/ddd/lsp/ranges.py:307` `text = self.text[start : self.pos]` records the key
   raw, undecoded, while `identity.py:69-88` reads the parsed document, so
   `document.value_span_of(target)` at `identity.py:141` finds nothing and `:143` `continue`s).
   Trigger (P10): `"na\u006de": "V"` -> `wrote 0 ids`, exit 0, while `ddd check --standalone`
   reports `missing-id` for the same declaration; an escaped `scope` key (P10c) is stamped, as
   `_PRODUCING` compares the decoded value. Fix: decode the key (`json.loads('"' + raw + '"')`)
   before building the pointer.

6. **On a file with bare-CR line endings the inserted `id` line ends in LF**
   (`src/ddd/identity.py:94` `return "\r\n" if end > 0 and text[end - 1] == "\r" else "\n"` -
   `_newline_at` looks for `\n` only). Trigger (P20): a component written with `\r` endings ->
   `wrote 1 id`, the file now holds 16 CR and one LF. Implausible today; one more branch.

7. **The dictionary reader keeps the last of two duplicate keys and accepts a `format` of `0` or
   `-3`** (`src/ddd/loading.py:435` `return DataDictionary.model_validate_json(text)` - pydantic's
   parser has no `object_pairs_hook`, where `_read_json` refuses a repeat, `:578`; `:459` `found
   <= DICTIONARY_FORMAT` accepts any lower integer). Trigger (P06): a dump edited to carry
   `"name": "P", "name": "Q"` compares with `project-mismatch: the baseline describes project
   'Q'`, and `"format": 0` or `-3` compares clean and "can replace". Beside pass 3 Minor 7 (`"9"`
   and `9.0`) and the previous review's Minor 4 (the invariants of `DataDictionary`, partly
   done: `ir.py:244-248` now checks `dimensions` against `shape`). Fix: `ge=1, strict=True` on
   `format`, and read the dump through `_read_json`'s hooks (or a `model_validate` over its
   result) so that a duplicate key is refused on both sides.

8. **A dumped dictionary is parsed three times per side** (`src/ddd/cli.py:1432` `data =
   json.loads(path.read_text(encoding="utf-8-sig"))` to sniff the kind, `src/ddd/loading.py:450`
   `data = json.loads(text, parse_constant=_reject_constant)` to peek at `format`, `:435`
   `model_validate_json(text)` to read it). Measured in process on the 45 MB dump of the N = 1000
   project (Q4): 0.39 s + 0.35 s + 1.29 s, so `load_dictionary` alone is 2.35 s of which 0.7 s
   is repeated work, and `ddd compare big.json big.json` takes 6.1 s. Fix: sniff and peek on a
   bounded prefix (the first few kilobytes: `"format"` is the first key a dump writes and
   `"project"`/`"component"` the first of a description), or parse once and validate the dict.

9. **`ddd --version` and `ddd --help` pay for the whole package** (`src/ddd/cli.py:46`
   `from ddd.loading import load_dictionary, load_workspace` and the import block above it pull
   in the analysis, the comparison, the ir, the backends and jinja2 at module level). Measured:
   0.40 s for either against 0.05 s for `python -c pass`; `import ddd.cli` is 0.38 s
   (`importtime.txt`). A pre-commit hook and a cmake configure step call `ddd` per file. Fix:
   import the command modules inside their handlers, or keep `ddd.cli` to argparse and
   dispatch.

10. **A 5000-digit `cycle` count is reported with Python's advice to a programmer**
    (`src/ddd/models/rasters.py:53` `return int(match.group(1)) * _NANOSECONDS[match.group(2)]`
    - `_CYCLE` at `:43` accepts any run of digits, and `int()` raises past 4300 of them).
    Trigger (P13): `"cycle": "111...1ms"` -> `rasters[0]: error[schema]: Value error, Exceeds
    the limit (4300 digits) for integer string conversion ... use
    sys.set_int_max_str_digits() to increase the limit (got: {'raster': 'r', ...` at the whole
    entry, the same pass-through pass 2 Minor 7 found for a double BOM. Fix: bound the count in
    the pattern (`[0-9]{1,18}`) so the ordinary "is no xcp event period" message answers.

11. **An error inside a mapping-form enumerator is located at a key the file does not have**
    (`src/ddd/models/conversion.py:157` `data["enumerators"] = [` rewrites the mapping into a
    list before validation, so pydantic's `loc` says `enumerators, 0, value` and `_pointer` at
    `loading.py:1229` renders `[0]`). Trigger (P14): `"enumerators": {"A": "x"}` ->
    `...conversion.enumerators[0].value: error[schema]: Input should be a valid integer (got:
    'x')`; the editor's range falls back to the parent (`ranges.py:155-164`). Fix: when the
    document holds a mapping where the pointer says `[i]`, render the i-th key instead
    (`_pointer` has the document).

12. **The mapping form's published schema carries neither the value bound nor the name
    pattern** (`src/ddd/models/conversion.py:121` `"additionalProperties": {"type":
    "integer"},`). Trigger (P24, `jsonschema` Draft 2020-12 over
    `schemas/ddd_component.schema.json`): `{"A": 18446744073709551616}`, `{"1bad": 0}` and
    `{"A": 4.0}` are accepted by the schema and refused by the loader (`le`, the identifier
    pattern, strict `int`), where the list form publishes all three constraints. Fix: publish
    `additionalProperties` as the value's own schema (`minimum`/`maximum`) and `propertyNames`
    with `C_IDENTIFIER_PATTERN`.

13. **A `-W` naming a plugin check is never verified when the load reports an error**
    (`src/ddd/cli.py:1363` `if workspace is None or bag.has_errors:` returns before `:1370`
    `bag.policy.verify(bag.registered)`). Trigger (P08): `ddd check p.ddd.json -W
    layout/x=error` with a missing include -> the `file-not-found` finding, exit 1, and no
    `unknown check 'layout/x'`; the typo on the command line surfaces only once the project
    loads. Fix: verify before the early return (the registered plugins are known by then).

14. **An extension key containing `.` or `[n]` yields a pointer no consumer can split**
    (`src/ddd/loading.py:949` `suffix = f"definition.extensions.{name}"`, `:849` for the
    project). Trigger (P09): `"extensions": {"a.b": {}, "c[1]": {}}` -> pointers
    `...extensions.a.b` and `...extensions.c[1]`, which `ranges.segments` (`ranges.py:195-203`)
    reads as two keys and as an index. Cosmetic: such a key is `unknown-extension` anyway. Fix:
    refuse a non-identifier plugin name in the block key, or escape it in the pointer.

15. **A drive-relative include pattern globs the process's current directory, a drive-relative
    literal the project's** (`src/ddd/loading.py:999` `base = Path(anchor) if anchor else
    source.parent` against `:991` `candidate = raw if raw.is_absolute() else source.parent /
    raw`). Trigger (`cases/P30_driverel`, `ddd sources` run from `elsewhere/`): `"includes":
    ["C:*.ddd.json"]` lists `elsewhere/fromcwd.ddd.json`, `"includes": ["C:inproject.ddd.json"]`
    lists `proj/inproject.ddd.json`. Nobody writes the first spelling on purpose, but the two
    answers differ. Fix: join a drive-relative anchor to `source.parent` as the literal path is.

16. **A raster name is capped in code points where the a2l field is bytes**
    (`src/ddd/models/rasters.py:77` `StringConstraints(min_length=1,
    max_length=EVENT_NAME_LENGTH, pattern=r"^\S+$")`, `\S` Unicode). Trigger
    (`cases/P31_raster`): `"raster": "тактовый"` (8 letters, 16 utf-8 bytes) ->
    `ddd check` ok; the `char[9]` `EVENT_CHANNEL_SHORT_NAME` the docstring at `:25-29` sizes
    the cap for would
    not hold it once the `DAQ` block is written. Fix: `pattern=r"^[\x21-\x7e]+$"`, or cap the
    utf-8 length.

17. **No bound on the size of a description file, and `MemoryError` is the one failure
    `_read_text` does not turn into a finding** (`src/ddd/loading.py:1112` `return
    path.read_text(encoding="utf-8-sig")`, handlers at `:1113-1130` for `OSError`,
    `UnicodeDecodeError` and `ValueError`). A 300 MB file is fine (P11: 1.5 s, one finding); a
    file larger than the available memory - a log matched by a careless pattern - ends the run
    with a traceback (unconfirmed - a multi-gigabyte file would confirm it). Fix: `stat()` first
    and refuse above a generous cap with `json-syntax`, or catch `MemoryError` in the same
    handler.

18. **`assign` rewrites the file in place** (`src/ddd/identity.py:182` `path.write_bytes(mark +
    text.encode("utf-8"))`; the artefact writer at `backends/base.py:197` goes through a
    temporary file). A crash or a kill between the truncation and the write leaves a
    hand-authored file empty, and the file changed between `:168` and `:182` is overwritten
    without notice. The unguarded errno is pass 5 Minor 4. Fix: write to a sibling temporary and
    replace.

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| P7 I2 | integers beyond the float range crash with `OverflowError` | fixed | `common.py:145`, `conversion.py:46`, `constants.py:45`, `objects.py:33`, `:70`, `sections.py:52`; Q1 (400-digit limit and enumerator are two `schema` findings); `tests/test_models.py:423-780` |
| P7 I3 | recursion unbounded in the loader, the structure walks, the dictionary reader | partly fixed | includes capped (`loading.py:55`, `:1032-1037`, `tests/test_loading.py:176-303`), structures capped (`analysis.py:71`), `RecursionError` caught around `json.loads` (`loading.py:451`, `:587`, `cli.py:1433`, `ranges.py:48`); the scanner's own recursion is open between about 500 and 3000 levels - Important 1, carried over |
| P7 I4 | a key of non-decimal digits breaks the sort | fixed | `diagnostics.py:291-292`; `tests/test_hardening.py:618-635`, `:1022-1033` |
| P7 I6 | the loader accepts quoted numbers and booleans the schema refuses | consciously left | pass 2 Important 2 lists the residue; the list-init arms of pass 2 Important 1 are the same residue (settled above) |
| P7 I8 | two readers turn malformed inputs into usage errors | fixed | `cli.py:1431-1435`, `loading.py:1115-1121`; `tests/test_hardening.py:569-615` |
| P7 design note 3 | strict by default | open | what remains: `Number` (`common.py:144-146`), `factor`/`offset` (`conversion.py:87-90`), `InitScalar` (`objects.py:33`), `export` (`objects.py:147`), `volatile` (`:484`), `bits` (`types.py:173`), `format` (`ir.py:593`) |
| P7 M1-M9 | minors, checked in bulk | M1 still open (Minor 1 above, carried over); M4 partly (`ir.py:244-248` checks `dimensions` against `shape`; duplicate keys, `format` bounds and orphan references open, Minor 7); M5 open as pass 2 Important 3; M6 open as pass 5 Minor 4 (Minor 18 adds atomicity); M2, M3, M7, M8, M9 lie in the analysis and the backends (pass 3 has M7 as its Minor 5) | - |

### Open questions

1. Should `ddd id --assign` and the server refuse a document by the same depth rule the loader
   applies, or skip it as "not readable"? A stated cap shared by `_read_json` and `Document`
   changes `SPEC.md:200-201` and both readers; a caught `RecursionError` changes `ranges.py`
   alone (Important 1).
2. Is "everything `<stdint.h>` declares" (`reserved.py:12`) the standard's list or what a real
   toolchain's `<stdint.h>` drags in? MinGW's pulls `<stddef.h>` names; the answer decides
   whether `size_t`, `NULL`, `wchar_t`, `ptrdiff_t` join `reserved.py` and section 4's list
   (Minor 2).
3. Does the mapping form of `enumerators` keep its keys in a finding's pointer
   (`enumerators.A` rather than `enumerators[0]`)? The answer changes `_pointer` or the model
   (Minor 11), and what the editor underlines.
4. The wildcard order (pass 1 Important 4, restated with the facts above): keeping `sorted(Path)`
   keeps `SPEC.md:255-258` as written and leaves the Windows/POSIX difference in the a2l's
   `GROUP` order; sorting on `as_posix()` changes `loading.py:1006`, `:531`, `:558` and `:396`
   and `tests/test_loading.py:53-63`.

### Test gaps

- `tests/test_hardening.py`: a document nested 600 levels through `ddd id --assign` and through
  `Document(text)` directly - `:587-599` pins 100 000 levels only (Important 1).
- `tests/test_loading.py`: a hyphenated or variant-named extension key *inside a definition*
  keeps its key in the pointer (`:434-448` pins the project level only), and two malformed blocks
  in one definition yield two findings (Important 2 and 3).
- `tests/test_models.py`: `["on", "off"]`, `[" 1 "]`, `["1_0"]`, `["1e2"]` inside a list init,
  whichever way pass 2's open question 1 goes; `:839` pins the whole init only.
- `tests/test_models.py`: a `condition` ending in a backslash (Minor 1); an `a2l.format` with
  non-ASCII digits (Minor 3); a raster name of eight non-ASCII characters in `tests/test_rasters.py`
  (Minor 16).
- `tests/test_hardening.py::TestNamesThatWouldNotCompile`: `size_t` and `NULL`, if Minor 2 is
  adopted; `:171` covers `<stdint.h>`'s own names only.
- `tests/test_cli.py`: `ddd id --assign` on a json-escaped key, on a bare-CR file, on a read-only
  file (Minor 5, 6, pass 5 Minor 4); no test today reads a file back after `assign` except for
  the ids themselves.
- `tests/test_hardening.py::TestTheArchivedDictionary`: a duplicate key and a `format` of `0` in a
  dump (Minor 7); `:882-895` peeks at a higher version only.
- `tests/test_documentation.py`: the mapping form's schema refuses an out-of-range value and a
  non-identifier key (Minor 12); `tests/test_plugins.py:1010-1060` pins `additionalProperties`
  on the extension blocks only.
- `tests/test_cli.py`: a `-W` naming an unregistered plugin check beside a load error (Minor 13).

### Assessment

The core reads as carefully as the previous review said it does, and the fixes it asked for are
in: the integer bounds are on every path, the pointer sort is index-aware, the readers no longer
turn a malformed file into a usage error, and about eighty adversarial runs - directories, a bare
`**`, 300 MB files, NUL bytes, 5000-digit numbers, `NaN` in a dump, a `subst` drive - all end in
a located finding. The loader is linear and cheap next to the analysis, and nothing in these
modules dominates a run. What this pass adds sits in two places the earlier passes did not read
line by line. The json scanner that `ddd id --assign` and every editor range borrow from the
language server recurses without the guard its parser got, so a file `ddd check` accepts ends
the command and the server in a traceback from about 500 levels on. And the pointer machinery
of the loader has two gaps on one input: after the first union tag the document walk is lost,
so a malformed extension block of a plugin named `map` or `axis` is located a level too high,
and the one-finding-per-place filter, keyed without the document, drops the second of two such
blocks. The rest is small: a carried-over backslash in a condition, names MinGW's `<stdint.h>`
reserves that the list does not, Unicode `\d` and `\S` where bytes were meant, a tilde the
loader expands, three parses of one dump, and a 0.4 s `--version`.

### Verification

Every candidate of this pass was handed to a second reviewer (group F): 20 confirmed, 1 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P8-I1 | Important | CONFIRMED | Important | `ranges.py:60` `scanner.value("")` sits outside the `try` at `:46-48`; a 520-deep `extensions` block: `check --standalone` exit 0 (one `missing-id`), `id --assign` exit 1 `RecursionError: maximum recursion depth exceeded` (480 levels stamp fine), `didOpen` over pipes ends `ddd lsp` with exit 1 before any `publishDiagnostics` or the `shutdown` answer |
| P8-I2 | Important | CONFIRMED | Important | `loading.py:1222` `present, node = _child(node, item)` sets `node = None` at the `measurement` tag; `{"map": [1]}` -> `...interface[0].definition.extensions: error[schema]: Input should be a valid dictionary (got: [1])`, key gone; the same key on the project keeps it: `project.extensions.a-b` |
| P8-I3 | Important | CONFIRMED | Important | `loading.py:1167` `kept.setdefault(_pointer(item["loc"]), item)`; `{"a-b": 1, "c-d": 2}` and `{"map": [1], "axis": [2]}` -> `1 error`; the control `{"aa": 1, "bb": 2}` -> `2 errors`; the pair on the project -> `1 error` as well |
| P8-M1 | Minor | CONFIRMED | Minor | `component.py:78` refuses line breaks and comment tokens only; generated `ddd_globals.h:23` `#if defined(FEAT_X) \` then `extern volatile uint8_t A;`; gcc: `error: missing binary operator before token "extern"` |
| P8-M2 | Minor | CONFIRMED | Minor | `reserved.py:54` matches the `<stdint.h>` patterns only; `size_t` and `NULL` check `ok`; gcc: `'size_t' redeclared as different kind of symbol` (`stdint.h:28` -> `crtdefs.h`), `NULL` refused through `stdint.h:32` |
| P8-M3 | Minor | CONFIRMED | Minor | `common.py:102` `r"^%\d*\.\d+$"`; `"%٣.٢"` checks ok and `out/P.a2l:27` carries `FORMAT "%٣.٢"` |
| P8-M4 | Minor | CONFIRMED | Minor | `loading.py:1206` `Path(path).expanduser().resolve()`; `ddd check ~x.ddd.json` from its directory -> `C:/Users/x.ddd.json: error[file-not-found]` |
| P8-M5 | Minor | CONFIRMED | Minor | `ranges.py:307` records the key raw; `"na\u006de": "V"` -> `check --standalone` reports `missing-id`, `id --assign` prints `wrote 0 ids`, exit 0, file unchanged |
| P8-M6 | Minor | CONFIRMED | Minor | `identity.py:94` looks for `\n` only; a file of 16 CR and 0 LF -> `wrote 1 id`, afterwards 16 CR and 1 LF |
| P8-M7 | Minor | CONFIRMED | Minor | `loading.py:459` `found <= DICTIONARY_FORMAT`, `:435` `model_validate_json(text)`; `"format": 0` and `-3` -> `can replace`; `"name": "P", "name": "Q"` -> `project-mismatch: the baseline describes project 'Q'`; one reader with P3-M7 |
| P8-M8 | Minor | CONFIRMED | Minor | read: `cli.py:1432` `json.loads(path.read_text(...))` (sniff), `loading.py:450` `json.loads(text, ...)` (peek), `:435` `model_validate_json(text)` (read), per side through `_read_baseline`/`_read_dictionary` (`cli.py:1377-1394`); the timing is the finder's Q4 |
| P8-M9 | Minor | CONFIRMED | Minor | `cli.py:34-46` imports `compare`, `identity`, `ir`, `loading` and the backends at module level; `ddd --version` 0.39 s (twice) against `python -c pass` 0.05 s |
| P8-M10 | Minor | CONFIRMED | Minor | `rasters.py:43` `^([0-9]+)...`, `:53` `int(match.group(1))`; a 5000-digit cycle -> `rasters[0]: error[schema]: Value error, Exceeds the limit (4300 digits) ... use sys.set_int_max_str_digits()` |
| P8-M11 | Minor | CONFIRMED | Minor | `conversion.py:157` rewrites the mapping into a list before validation; `{"A": "x"}` -> `...conversion.enumerators[0].value: error[schema]: Input should be a valid integer (got: 'x')` |
| P8-M12 | Minor | CONFIRMED | Minor | `conversion.py:121` `"additionalProperties": {"type": "integer"}`; jsonschema accepts `{"A": 2**64}`, `{"1bad": 0}`, `{"A": 4.0}`, the loader refuses all three (`le`, `^[A-Za-z_][A-Za-z0-9_]*$`, `valid integer`); the list form refuses the first two and accepts `4.0` too (note) |
| P8-M13 | Minor | CONFIRMED | Minor | `cli.py:1363` returns before `:1370` `bag.policy.verify(bag.registered)`; missing include with `-W layout/x=error` -> `file-not-found`, exit 1, no usage error; the same flag on a project that loads -> exit 2 `unknown check 'layout/x'`; a face of P6-M9 |
| P8-M14 | Minor | CONFIRMED | Minor | `loading.py:949` `f"definition.extensions.{name}"`; `{"a.b": {}, "c[1]": {}}` -> `--format json` pointers `...definition.extensions.a.b` and `...definition.extensions.c[1]` |
| P8-M15 | Minor | CONFIRMED | Minor | `loading.py:999` `base = Path(anchor) if anchor else source.parent` against `:991`; run from `elsewhere/`, `"C:*.ddd.json"` lists `elsewhere/fromcwd.ddd.json`, `"C:inproject.ddd.json"` lists `proj/inproject.ddd.json` |
| P8-M16 | Minor | CONFIRMED | Minor | `rasters.py:77` `max_length=EVENT_NAME_LENGTH, pattern=r"^\S+$"` counts code points; `"raster": "тактовый"` (8 letters, 16 utf-8 bytes) -> `ok` |
| P8-M17 | Minor | PLAUSIBLE | Minor | `loading.py:1112` `path.read_text(encoding="utf-8-sig")` with handlers `:1113-1130` for `FileNotFoundError`, `UnicodeDecodeError`, `OSError`, `ValueError` only; no `stat`, `st_size` or `MemoryError` in `loading.py`, `cli.py`, `ranges.py`; a file larger than memory would confirm |
| P8-M18 | Minor | CONFIRMED | Minor | `identity.py:182` `path.write_bytes(mark + text.encode("utf-8"))` in place, where `backends/base.py:190-200` stages `STAGING_SUFFIX` and `temporary.replace(target)` |

Notes of the verifier:

- P8-M17 is PLAUSIBLE, not confirmed: the mechanism is exactly as read (`_read_text` turns four
exception types into findings and `MemoryError` is not one of them; nothing in the loader, the
cli or the scanner looks at a file's size), and a 300 MB file passes; only a file larger than the
available memory would show the traceback, which this machine was not asked to produce.

## Pass 9: code review of the core, part B (analysis, ir, compare)

### Scope covered

Read in full, with line numbers, on the review tree (`master` at `6e9e99f`): `src/ddd/analysis.py`
1-3289, `src/ddd/ir.py` 1-733, `src/ddd/compare.py` 1-672. The models these call, in full:
`src/ddd/models/objects.py`, `conversion.py`, `common.py`, `types.py`, `constants.py`. Every call
site of what the three files export: `src/ddd/cli.py` 585-680, 785-830, 925-1000, 1340-1535
(`_analyze`, `_read_dictionary`, `_read_baseline`, `_holds_a_description`, `_init_cell`,
`_print_table`); `src/ddd/plugins.py` 255-410 (`resolve_blocks`, `settings_of`, the hook runners);
`src/ddd/loading.py` 100-200 and 405-470 (`LoadedComponent`, `LoadedType`, `load_dictionary`,
`_register`); `src/ddd/diagnostics.py` 279-523; `src/ddd/lsp/diagnostics.py` 60-215 and
`lsp/hover.py` 78-102; the backends' uses of the records by grep, `backends/c/model.py` 289-310 and
436-456. `docs/developer_documentation.rst` 1-100 (the layer table), `SPEC.md` 1306-1318 and
1421-1507, `docs/comparing_deliveries.rst` 196-230, 429-530, 655-665, `CHANGELOG.md` 586-640 and
760-772; `tests/test_comparison_tables.py` 40-130 and the names of every test in
`tests/test_analysis.py`, `test_compare.py`, `test_structures.py`, `test_calibration.py`,
`test_embedded.py`, `test_hardening.py`, with the bodies cited below; `previous-review.md`
1590-1700; `reports/pass-3.md`, `pass-4.md`, `pass-8.md`.

Ran, from the venv, everything kept under `scratchpad/pass-9/`: `probes.py`, `probes2.py`,
`probes3.py`, `probes4.py` (28 throwaway cases under `cases/`, about 60 commands - `check`,
`check --standalone`, `list`, `dump`, `compare` with and without `--strict`, `generate c --force`
- transcripts in `results.txt` to `results4.txt`; case ids `Ann`, `Bnn`, `Cnn` below refer to
those); `gen9.py`, which reuses pass 8's `gen.py` read-only for N components of 50 objects and
adds one component of 20 000 objects; `perf.py` (wall clock of `ddd check` at N = 100, 1000, 3000
and on the wide component, `cProfile` of `analyze` at N = 1000 and on the wide component,
`ddd compare` of the N = 100 and N = 1000 dumps against themselves and against a copy with every
name prefixed and no ids; `perf_check_stdout.txt`, `perf_profile_stdout.txt`,
`perf_compare_stdout.txt`); determinism of `dump`, `check --format json` and `list --format json`
under `PYTHONHASHSEED` 0, 1 and 12345 on six examples, two cases and the N = 100 project
(`results3.txt` B30).

### Strengths

- Deterministic in fact, not only by design: `dump`, `check --format json` and `list --format
  json` are byte-identical under three hash seeds on `examples/demo`, `structures`,
  `pressure/release`, `inconsistent`, `vocabulary`, `layout`, two enum cases and the 5 300 object
  project (B30). Every set in the three files is consumed by membership or sorted before it
  reaches a finding (`analysis.py:720`, `:731`, `:771`, `:786`, `:788`, `:2454`, `:2646`,
  `compare.py:270`, `:276`, `:285-287`, `:307`, `:354`).
- Linear and cheap: `ddd check` takes 0.89 s / 9.4 s / 18.8 s for 100 / 1000 / 3000 components of
  50 objects and 2.2 s for one component of 20 000 objects; under the profiler at N = 1000 no
  function of these modules dominates - pydantic's record construction is 19 %, `_build_variable`
  and `Variable.resolve` 20 % together, `_check_similar_names` is one linear pass (0.4 s), the
  absence fixpoint 0.2 s (`perf_profile_stdout.txt`). The three graph walks that could have been
  exponential are not: `_nesting_cycle` shares `settled` across starts (`analysis.py:1274-1276`),
  `_leaves_of_types` counts over the type graph rather than the instance (`:1357-1397`),
  `_reaches_external` is memoised (`:1173-1211`).
- The caps run before any expansion: a map of 4000 x 4000 is refused at the map (A06), a
  structure of one external member dimensioned `[2000000]` checks in 1.2 s with zero leaves (A12),
  a 64-level structure resolves to a 64-deep path and a 65-level one is refused at the type that
  crosses the limit (A06, A06b). Nothing allocates before `_shape_fits` (`:1917`) has weighed
  the product.
- The phase order of `_Analysis.run` holds for every input tried: `_unwalkable_types` is complete
  before `_check_sections` walks a type (`:711` before `:713`, guard at `:1138`), `_type_leaves`
  before `_shape_fits` asks (`:1263`, `:1925`), `_effective` before `_resolve_shape` and the a2l
  closure read it (`:733`, `:736`, `:741`), and every path that drops a declaration records it
  in `_dropped` (asserted at `:2234`). The two fixpoints of `_absent` are monotone (an `and` over
  values that only fall), so they converge on a reference graph of any shape.
- Self references are refused where they are written: an axis whose `input` is itself and a
  curve whose `axis` is itself are `reference-kind` (A05).
- `compare` degrades safely on the inputs the previous review worried about: colliding ids fall
  back to names (`compare.py:208-231`), a swap is two renames and two `reused-name`s, a
  half-migrated project pairs by what each object carries, and a plugin's block is left to the
  plugin - two dumps differing only in `extensions` are `missing-plugin` and nothing else (C05).
- The records are frozen with a hash that leaves the mapping fields out (`ir.py:148`, `:359`,
  `:670`); nothing in the three modules mutates an `extensions` dict after it is built, and
  `resolve_blocks` returns a fresh, sorted dict per object (`plugins.py:270-303`).

### Issues

#### Critical

None found.

#### Important

1. **`narrowed-limits` compares limits exactly, so stating the limit a datatype implies is a
   narrowing by 3e-13 and, under `--strict`, a false "cannot replace"** (`src/ddd/compare.py:590`
   `narrowed = new.limits.min > old.limits.min or new.limits.max < old.limits.max`). Trigger (A11):
   a baseline dumped from `sint16` under `{"factor": 0.1}` with no limits carries `"max":
   3276.7000000000003` (pass 4 Important 3, where the value is *produced*); a candidate that
   writes `"limits": {"min": -3276.8, "max": 3276.7}` - making the implicit limits explicit, or
   adopting a scalar type that states them - is `warning[narrowed-limits]: 'T': limits tightened
   from [-3276.8, 3276.7000000000003] to [-3276.8, 3276.7]`, and with `--strict`, the gate
   `docs/comparing_deliveries.rst:661` recommends, `error[narrowed-limits]` and `c.ddd.json cannot
   replace baseline.json`, exit 1. The reverse edit is silent (widening). The analysis knows this
   arithmetic is approximate - `_below`/`_above` accept `rel_tol=1e-9` (`analysis.py:3284-3289`) -
   and the comparison does not. Fixing pass 4 Important 3 alone moves the problem rather than
   removing it: every archived baseline then carries the unrounded value against a candidate that
   derives the rounded one, which is a narrowing on every rescaled object of every old baseline.
   Fix: compare with the analysis's tolerance (one shared `_below`/`_above` in `models`), whatever
   is decided about rounding the derived value.

2. **A reordered structure, and a bitfield whose width changed, are "can replace", while the
   published schema promises that a comparison reports the reordering** (`src/ddd/compare.py:
   121-148` compares kind, datatype, unit, conversion, shape and locality of each leaf and nothing
   about its `bits` or its position; `src/ddd/models/types.py:124-126` "Reordering members of a
   released structure moves every address after the change, which is why a comparison against a
   baseline reports it", published verbatim in `schemas/ddd_types.schema.json:287` and
   `schemas/ddd_component.schema.json:1376`). Trigger (A08): baseline `S_t {a: uint8, b: uint16, f:
   uint16 bits 3}`, candidate `{b, a, f}` -> no finding, `p.ddd.json can replace baseline.json`,
   also under `--strict`; `f` widened to 4 bits -> no finding (the derived limits widen, which is
   silent); `f` narrowed to 2 bits -> only `warning[narrowed-limits]: 'Inst.f': limits tightened
   from [0, 7] to [0, 3]`, the layout change itself unmentioned. The dictionary carries `bits` on
   every leaf (`ir.py:488`, `ddd list --format json` shows `('Inst.f', 3)`), and
   `tests/test_comparison_tables.py:94` says its guard "walks ResolvedObject.model_fields alone",
   so a leaf field can fall behind unnoticed. `SPEC.md:1422` lists neither in `changed-interface`,
   so the code matches the spec and contradicts the model's docstring. Fix: decide (open question
   1); compare `bits` as an interface field of a leaf and the member order of each `types` entry
   (or drop the sentence from `Member` and say in 4.1 that layout inside a structure is not
   compared), and extend the tables guard to `ResolvedLeaf.model_fields`.

3. **One table typed one datatype too narrow is one `init-invalid` per element** (`src/ddd/
   analysis.py:2339` `for value in definition.scalar_values():` with `self._bag.add(...)` inside
   at `:2351` and `:2359`; the bag keeps every call, `diagnostics.py:485-500`). Trigger (A09): a
   `value_block` `uint8[4096]` with `"init": [300, 300, ...]` -> `ddd check --standalone` prints
   4096 identical lines at one pointer (499 724 characters), `--format json` carries 4096
   diagnostics, and the server publishes 4096 diagnostics on one range (`lsp/diagnostics.py:
   157-160`, `_as_lsp` is one to one). `[1.5] * 8` is eight findings (C07). The enumerator check
   beside it already spells the offending subset in one finding (`_check_enum_fits`, `:2492-2502`).
   Fix: one finding per declaration with the count and the first offending values ("4096 init
   values do not fit into uint8, the first is 300 at [0]"), or collapse identical
   (check, location, message) triples in the bag.

4. **The lost-identity note is quadratic in the additions that share a bucket, so a rename sweep
   on a project without ids takes ten seconds at 5 300 objects and does not finish in fifteen
   minutes at 53 000**
   (`src/ddd/compare.py:439-446` `same = [new for new in candidates if ... not differing(...) and
   not differing(...) and _compare_references(...) is None]`, asked for every removal;
   `:388-409` buckets on kind, datatype and unit only and says "no such delivery has been seen").
   Trigger (`perf_compare_stdout.txt`): the N = 100 dump with every id nulled against a copy with
   every name prefixed `x_` - the naming-convention sweep that a project does *before* it has
   ids, which is what `renames` exists for - compares in 9.6 s against 0.9 s for the same dump
   unchanged, with `differing` called 2.36 million times from `_lost_identity_note` (28.7 s under
   the profiler); the N = 1000 pair - 53 000 objects, 10 000 of them in one bucket - did not
   finish within the 900 s allowed (`TIMEOUT after 900 s`), against 6.0 s for that dump against
   itself. The note is advisory ("if there is exactly one" identical addition). Fix: key the
   bucket on everything hashable the note compares
   (conversion identity, `written_shape`, `local`, `volatile`, `section`, `raster`, the reference
   keys), so a bucket holds only genuine candidates, and skip the note outright when a bucket
   exceeds a small bound - two identical additions already yield no note.

#### Minor

1. **Cyclic structures reach the dictionary's `types`, against the docstring that says they are
   left out** (`src/ddd/analysis.py:432-433` "a cycle is reported by `_check_types` and the
   structures in it are left out"; `:783` hands `_ordered_structures` every declared type).
   Trigger (A01): `A_t <-> B_t` -> `type-cycle`, and `ddd dump` writes `types: [B_t, A_t, Ok_t]`.
   Harmless (`type-cycle` is an error, a forced header fails loudly); fix the sentence.

2. **`ResolvedMember` accepts a member with no storage at all** (`src/ddd/ir.py:297-311` checks
   only that `external` and `header` travel together; `analysis.py:951-963` builds `datatype=None,
   type=None, external=None` for a member naming an unknown type). Trigger (A02, C06): a member
   `"typename": "Nope_t"` -> `unknown-type`, `ddd dump` carries `{"datatype": null, "type": null,
   "external": null}`, the dump reads back and compares clean, and `generate c --force` writes
   `None bad;` into `ddd_types.h` (`backends/c/model.py:453` `str(member.type)`). The docstrings
   at `ir.py:264-268` say each is `None` exactly when the other is stated. Fix: a validator
   "exactly one of `datatype`, `type`, `external`", and `<unresolved>` for the forced spelling.

3. **The bitfield bound is phrased as the datatype, and a value past both the field and the c
   `int` is two findings** (`src/ddd/analysis.py:838-840` passes `member.datatype.value` as the
   phrase while the bounds are `_member_raw_range`; `:862` likewise; `:2467-2474` excepts the
   datatype's range, not the field's). Trigger (A03, C03): `uint8` `bits: 2` with enumerator
   `FAR=5` -> `enumerator(s) FAR=5 of enum 'Mode_t' do not fit into uint8`; limits `[0, 9]` ->
   `exceed the range [0, 3] that uint8 can represent`; `uint64` `bits: 2` with `2**40` -> one
   finding against the c `int` and one "do not fit into uint64". Fix: say "the 2-bit field of
   uint8", and hand `except_outside` the bitfield's range.

4. **A list nested one level too deep is reported as "the object is a scalar"** (`src/ddd/models/
   objects.py:779-780`, reached from `analysis.py:3109`). Trigger (B24): `"init": [[1], [2]]` on
   `uint8[2]` -> `'V': init is a list but the object is a scalar`; the object is an array, its
   element is the scalar. Fix: "element [0] is a list but the shape has no further dimension".

5. **`changed-storage` spells the whole init twice** (`src/ddd/compare.py:103-115` `_describe_init`
   returns `repr(value)`; `cli.py:1491-1511` abbreviates the same value to `[...]` for the table).
   Trigger (A10): a `uint8[100000]` block with one element changed -> one warning of 600 017
   characters in text and in json; a 16 x 16 map costs about 1.6 kB per changed table. Fix:
   abbreviate, naming the first differing index and both values there.

6. **`enum-conflict`'s note "first defined as" points at the better documented copy, not the
   first** (carried over, previous pass 7 Minor 9; `src/ddd/analysis.py:2412-2416` replaces the
   registry entry, location included). Trigger (A07): `A` undocumented, `B` documented, `C`
   conflicting -> the note points at `b.ddd.json`. Fix: keep the first location beside the best
   documented conversion.

7. **Leaves and listed variables are ordered as text: `[0], [10], [11], [1]`** (carried over,
   previous pass 7 Minor 2; `src/ddd/analysis.py:786` `key=lambda x: x.path`, `ir.py:715`).
   Trigger (C04): an instance `[12]` lists `Inst[0].v Inst[10].v Inst[11].v Inst[1].v ...`. Fix: a
   key that splits on `[n]`, as `_pointer_order` does (`diagnostics.py:279-294`).

8. **Only the first registration of an enum screens its enumerators** (`src/ddd/analysis.py:
   2395-2400`; `_check_enum_names` is not reached on a conflicting second copy). Trigger (C02):
   `A` `{OFF, ON}`, `B` `{OFF, ON, EXTRA}`, `C` a variable `EXTRA` -> `enum-conflict` alone, no
   `name-collision` for `EXTRA`. Cosmetic, the conflict is already an error.

9. **`2.0` on a boolean is refused as "init value 2", and `1.0` passes where `1.0` on `uint8` is
   refused** (`src/ddd/analysis.py:2341-2346` `value not in (0, 1)` then `format_number`; `:2348`
   spells the integer case with `{value!r}` for exactly this reason). Trigger (A04): `"init":
   2.0` on `boolean` -> `init value 2 is not a valid bool`; `1.0` -> no finding, `= 1`. Cosmetic.

10. **Rules spelled twice inside the two files** (reuse). `_refuse_infinite_type_limits` re-derives
    a member's raw range inline (`src/ddd/analysis.py:1526-1530`) beside `_member_raw_range`
    (`:3240-3245`); `_describe_references` is copied between `analysis.py:155` and
    `compare.py:84`, and `_condition` renders an absent condition as "no condition" at
    `analysis.py:3264` and "none" at `compare.py:627` (previous pass 7 Minor 3f, still open);
    `Variable.is_local` (`:357`) is re-spelled at `:2900`.

11. **The layer table says the analysis knows "any output format" not at all; it knows the a2l's
    dimension cap and the c `int`, and the leak guard does not read it** (`src/ddd/analysis.py:
    68-69` `_A2L_MAX_DIMENSIONS` "Dimensions `MATRIX_DIM` can carry ... (ASAP2 1.6.1)", `:127-128`
    `_INT_MIN, _INT_MAX` "Range of a c `int` on the 32 bit targets", messages naming `MATRIX_DIM`
    and `ASAP2 1.6.1` at `:2916-2918` and `:3033-3035`, `typedef` at `:1683-1685`;
    `docs/developer_documentation.rst:32-34`, and `:88-89` says the spelling guard reads
    `src/ddd/models/` only). Both facts are what section 4's `a2l-unrepresentable` and the
    enumerator rule are about, so the row's wording is what is wrong, or the two constants belong
    beside `reserved.py` with the same justification. No behaviour rides on it.

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| P7 I1 | a dropped declaration makes the ownership checks lie | fixed | `analysis.py:673-687` (`_census`, `_dropped`), `:2504-2557`, `:2840-2842`; `tests/test_analysis.py:713-775` |
| P7 I5 | arrays of structures expanded without a bound | fixed | `analysis.py:102-125`, `_shape_fits` `:1887-1943`, `_leaves_of_types` `:1357-1397`, `_refuse_wide_types` `:1432-1468`, `_refuse_wide_maps` `:1945-1988`; A06 (1.6e7-element map refused), A12 (2e6 opaque elements in 1.2 s); `tests/test_analysis.py:597-700`, `test_structures.py:638-700` |
| P7 I7 | scalar type findings at keys its users do not have, once per user | fixed | `_check_scalar_type` `analysis.py:865-888`, skipped for a filled-in declaration `:2319-2325`; `tests/test_structures.py:1825-1850` |
| P7 design note 1 | dropping versus marking | mostly closed | `_census` and `_dropped` feed ownership, readers and `incomplete-project`; identities and similar names still read `ordered`, the survivors (`:1783`, `:3211`; pass 3 Minor 2) |
| P7 design note 2 | types checked through their users | closed | `_check_scalar_type`, `_register_member_enums`, `_check_member_limits` at the type |
| P7 design note 4 | implicit phase order in `run` | open, no defect | the order lives in comments (`:726-729`, `:1255-1263`); no assert on entry; every field read is filled first for every input tried (Strengths) |
| P7 design note 5 | the IR is the a2l's shape | open | `leaves` per element (`:785-787`, 10 000 leaves for 2 000 instances at N = 1000); `init` unexpanded (pass 4 Minor 5) |
| P7 M2, M3f, M8, M9 | leaves as text; `_condition`/`_describe_references` twice; member `unknown-type` at `members[i]`; enum note location | open | Minor 7, Minor 10, `analysis.py:1240` (still `members[{index}]`, not `.typename`), Minor 6 |
| P7 M4, M7 | dictionary invariants; owner under a silenced local clash | partly / open | `ir.py:244-248` plus Minor 2 above; pass 3 Minor 5 |
| P7 test review | ~220 `checks(bag) == [...]` order pins; the `1.0` init case; dropped-producer cases | open / open / closed | 345 such pins now (`grep -c` over `tests/`); `1.0` is refused as "written as a fractional number" (A04) and `tests/test_analysis.py:176` still uses `1.5` only; `tests/test_analysis.py:713-775` |

Forwarded items, settled from the code. Pass 3 Important 1: the mechanism is `_refuse_reference`
reading `found.kind` alone (`analysis.py:2700`) - a structured instance is a `Measurement` whose
`declared_type` names a structure, and no test in `_EXPECTED_KIND` looks at `declared_type`;
confirmed, nothing to add. Pass 3 Important 2: `compare.py:182` compares `o.init` as read, and
the dictionary stores `definition.init` as written (`analysis.py:390`); confirmed. Pass 3 Minor
1 (`explained`, `:2671`), Minor 2 (`:1783` over `ordered`), Minor 3 (`_check_init_shape` only
from `_build_variable`, `:3019`), Minor 4 (`location` at `:2307` handed to `:2333-2335`), Minor 5
(`owning[0]`, `:2556-2557`), Minor 6 (`STANDALONE_POLICY` includes `incomplete-project`), Minor 9
(`continue` at `:2221` before `_check_declared_name`): all confirmed as described. Pass 4
Important 3: the derived limits are computed in `physical_range` (`conversion.py:269-281`), reach
the dictionary through `physical_limits()` (`objects.py:600-611`, `analysis.py:3044-3048`) and
`_member_meaning` (`:2999-3001`), and are consumed with a tolerance by `_check_limits_fit`
(`:3284-3289`) and without one by `compare.py:590` - Important 1 above. Pass 4 Minor 5 and 6:
`ir.py:187` and `:98` unchanged. Pass 1 Important 5: `compare.py:128-132` reads
`conversion_identity`, which for an enum is name plus ordered `(name, value)` pairs
(`conversion.py:260-265`); confirmed, descriptions left out. Pass 8 open question 3 (the
enumerator mapping form's pointer): the analysis never builds a pointer into `enumerators` - every
enum finding sits at `...conversion` (`:2332`, `:835`, `:881`) - so the question is the
loader's alone.

### Open questions

1. Is a change of a structure's layout - member order, a bitfield's width - a `changed-interface`
   (Important 2)? Yes changes `compare.py` and the tables guard; no changes the `Member` docstring
   and both published schemas, and wants a sentence in 4.1.
2. Should `narrowed-limits` carry the analysis's `1e-9` tolerance (Important 1), or should the
   derived value be rounded (pass 4 Important 3) and archived baselines be accepted as noisy? The
   first is one helper shared by both modules; the second alone leaves every old baseline tripping
   the check the other way.
3. Should the lost-identity note give up above a bucket size (Important 4), or is a comparison
   without ids allowed to take minutes? The answer decides whether `_by_discriminators` grows keys
   or `_lost_identity_note` grows a bound.
4. Is one `init-invalid` per element wanted anywhere (Important 3)? A per-element pointer is
   never built (`definition.init` for all), so nothing is lost by folding them.

### Test gaps

- `tests/test_compare.py`: stated limits equal to the derived ones compare clean (Important 1;
  no test names `isclose` or a value inside the band, previous gap still open); a reordered
  structure and a changed `bits`, whichever way question 1 goes (Important 2); a changed init of
  a large block reported in a bounded message (Minor 5).
- `tests/test_comparison_tables.py`: a guard over `ResolvedLeaf.model_fields` beside the one over
  `ResolvedObject` (Important 2; `:94` says the leaf is not walked).
- `tests/test_analysis.py`: a table of N bad elements is one finding (Important 3); `1.0` on an
  integer (previous gap, still open - `:176` uses `1.5`); the bitfield phrase and the single
  finding past both bounds (Minor 3); `[[1], [2]]` on `[2]` (Minor 4); the enum note's location
  under a documented second copy (Minor 6).
- `tests/test_structures.py`: a cyclic structure reaching (or not) the dump's `types` (Minor 1);
  a `ResolvedMember` without storage refused (Minor 2); the element order of an instance `[12]`
  (Minor 7).
- A performance guard for `ddd compare` on a rename sweep without ids, or the bound of question 3
  pinned (Important 4).

### Assessment

The three modules read as one design carried through: every drop is recorded where it happens,
the absence machinery is a monotone fixpoint, the caps are weighed before anything expands, the
walks that could have gone exponential are memoised or counted over the type graph, and the
outputs are byte-identical across hash seeds and linear in the project. Nothing in them
dominates a run, and the defects the previous review found in this area - ownership lying about
dropped declarations, unbounded expansion, scalar types checked through their users - are fixed
and tested. What this pass adds sits at the comparison's edges and in one loop of the analysis:
the limit comparison lacks the tolerance the analysis already uses, so making implicit limits
explicit is a strict-mode refusal; a structure's layout is outside what `compare` sees although
the published schema says otherwise; a table typed too narrow is reported once per element; and
the advisory lost-identity note is quadratic on exactly the delivery ids were introduced to
handle. Each is local. The minors are a stale docstring, an IR record that admits a member with
no storage, three messages phrased for the wrong bound or object, one 600 kB message, and four
carried-over small items.

### Verification

Every candidate of this pass was handed to a second reviewer (group F): 15 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P9-I1 | Important | CONFIRMED | Important | `compare.py:590` exact `>`/`<`; the baseline dumped from `sint16` under factor 0.1 carries `"max": 3276.7000000000003`; a candidate stating `3276.7` -> `warning[narrowed-limits]: 'T': limits tightened from [-3276.8, 3276.7000000000003] to [-3276.8, 3276.7]`; `--strict` -> `error[narrowed-limits]`, `cannot replace`, exit 1; the widening direction is silent |
| P9-I2 | Important | CONFIRMED | Important | `compare.py:121-148` compares neither `bits` nor position while `types.py:124-126` (published verbatim at `ddd_types.schema.json:287`) says a comparison reports reordering; `{b, a, f:3}` and `f: 4` -> no finding; `f: 2` -> `narrowed-limits` only; the dump carries `["Inst.f", 3]` |
| P9-I3 | Important | CONFIRMED | Important | `analysis.py:2339` `for value in definition.scalar_values():` with `_bag.add` at `:2351`/`:2359`; `uint8[4096]` init 300 -> 4096 identical `init-invalid` lines at `...definition.init`, 569 357 characters; `--format json` 4096 diagnostics, 1.9 MB; `[1.5] * 8` -> 8 findings |
| P9-I4 | Important | CONFIRMED | Important | `compare.py:439-446` scans the bucket per removal; N=50 (2150 objects) noid vs itself 0.57 s, vs every name prefixed 2.73 s; N=100 (4300) 0.75 s vs 9.67 s - the excess grows 4.1x for 2x objects; the N=1000 timeout is the finder's `perf_compare_stdout.txt` |
| P9-M1 | Minor | CONFIRMED | Minor | `analysis.py:432-433` "the structures in it are left out" against `:783` over every declared type; `A_t <-> B_t` -> `error[type-cycle]` and the dump's `types` are `['B_t', 'A_t', 'Ok_t']` |
| P9-M2 | Minor | CONFIRMED | Minor | `ir.py:297-311` checks `external`/`header` only; member `typename: Nope_t` -> dump `{"datatype": null, "type": null, "external": null}`, which `compare` reads back without a finding; `generate c --force` writes `ddd_types.h:18` `    None bad;` |
| P9-M3 | Minor | CONFIRMED | Minor | `analysis.py:838-840` passes `member.datatype.value` as the phrase; `uint8` bits 2 with `FAR=5` -> `do not fit into uint8`; limits `[0, 9]` -> `exceed the range [0, 3] that uint8 can represent`; `uint64` bits 2 with `2**40` -> one finding against `a c 'int'` and one `do not fit into uint64` |
| P9-M4 | Minor | CONFIRMED | Minor | `objects.py:779-780`; `[[1], [2]]` on `uint8[2]` -> `'V': init is a list but the object is a scalar` |
| P9-M5 | Minor | CONFIRMED | Minor | `compare.py:115` `return repr(value)`; `uint8[100000]` with one element changed -> one `changed-storage` line of 600 077 characters |
| P9-M6 | Minor | CONFIRMED | Minor | `analysis.py:2416` replaces the registry entry, location included; A plain, B documented, C conflicting -> `first defined as: OFF=0, ON=1` at `b.ddd.json`, not `a.ddd.json` |
| P9-M7 | Minor | CONFIRMED | Minor | `analysis.py:786` `key=lambda x: x.path`, `ir.py:715` `key=lambda entry: entry.name`; `ddd list` of `Inst[12]` prints `Inst[0].v`, `Inst[10].v`, `Inst[11].v`, `Inst[1].v`, ... |
| P9-M8 | Minor | CONFIRMED | Minor | `analysis.py:2395-2400` runs `_check_enum_names` on the first registration only; B adds `EXTRA`, C declares a variable `EXTRA` -> `enum-conflict` alone, no `name-collision` |
| P9-M9 | Minor | CONFIRMED | Minor | `analysis.py:2341-2344` `value not in (0, 1)` then `format_number`; `2.0` on `boolean` -> `init value 2 is not a valid bool`; `1.0` on `boolean` passes; `1.0` on `uint8` -> `written as a fractional number` |
| P9-M10 | Minor | CONFIRMED | Minor | read: `analysis.py:1526-1530` re-derives `_member_raw_range` (`:3240-3245`); `_describe_references` at `analysis.py:155` and `compare.py:84`; `_condition` "no condition" (`:3264`) against "none" (`compare.py:627`); `is_local` (`:357`) re-spelled at `:2900` |
| P9-M11 | Minor | CONFIRMED | Minor | read: `developer_documentation.rst:32-34` "does not know about: any output format" against `analysis.py:68-69` (`MATRIX_DIM`, ASAP2 1.6.1), `:127-128` (the c `int`), `:2916-2918`; the guard `tests/test_backends.py:63-66` globs `models/*.py` only |

## Pass 10: code review of the periphery (cli, plugins, backends, build_info, the cmake module)

### Scope covered

Read in full, with line numbers, on the review tree (`master` at `6e9e99f`): `src/ddd/cli.py`
1-1535, `src/ddd/plugins.py` 1-495, `src/ddd/build_info.py` 1-88, `src/ddd/backends/__init__.py`,
`base.py` 1-317, `c/__init__.py`, `c/backend.py` 1-130, `c/literals.py` 1-142, `c/model.py` 1-555,
`c/options.py`, `c/types.py`, `a2l/__init__.py`, `a2l/backend.py`, `a2l/model.py` 1-662,
`a2l/options.py` 1-86, `a2l/types.py`, `a2l/templates/project.a2l.jinja` 1-160 (as code),
`cmake/Ddd.cmake` 1-676 (as CMake code), the five `examples/templates/*.jinja2` (as code),
`examples/plugins/ddd_layout.py` 1-316. For the cross-module angle: `src/ddd/lsp/discovery.py`
(the reader of the build record), `src/ddd/diagnostics.py` 296-330 and 384-523 (`Location`,
`SeverityPolicy`, `DiagnosticBag`), `src/ddd/loading.py` 380-425, 835-945, 985-1030 (`sources`,
`locate`, plugin loading, include expansion), `src/ddd/ir.py` 515-545 and 670-733 (the
`DataDictionary` helpers the backends call), `src/ddd/analysis.py` 424-463 and 720-770
(`_ordered_structures`, the object order), `src/ddd/models/common.py:326-340`,
`objects.py:161`, `:811-820`, `pyproject.toml` 1-120, `docs/developer_documentation.rst` 1-110,
`docs/templates.rst` and `docs/plugins.rst` by grep, `docs/acronyms.rst:170-185`,
`docs/generated_artefacts.rst:740-770`, `docs/faq.rst:596-606`, `SPEC.md:1066-1076`,
`:1722-1730`, `docker/compile.sh:48-53`; the names of every test in `tests/test_cli.py`,
`test_plugins.py`, `test_backends.py`, `test_generation.py`, `test_a2l.py`, `test_calibration.py`,
`test_example_plugin.py`, `test_cmake.py`, `test_external.py`, and the fixture helpers of
`tests/test_external.py:20-68`; `reports/pass-4.md`, `pass-5.md`, `pass-8.md`, `pass-9.md` whole,
`previous-review.md:1700-1837`.

Ran, from the venv, everything kept under `scratchpad/pass-10/`: `perf10.py` (pass 8's `gen.py`
reused read-only; wall clock of `ddd generate all --dictionary` at N = 100 and 1000, twice each;
the phases in process; `cProfile` of `build_code_model` and `build_a2l_model` at N = 1000;
`perf_results.txt`); `cmake_probe.cmake` under `cmake -P` (CMake 4.4.3: `string(JSON)` on a
document with a byte order mark, `cmake_parse_arguments` with a keyword whose value expanded to
nothing, the list handling of `_ddd_project_sources`); `probes10.py` and `probes10b.py` (eleven
cases under `cases/`, transcripts `probes_results.txt` and `probes_results_b.txt`: `ddd list`
into one redirected file, `dump -o .`, `--dictionary .`, three address maps, an include through a
directory named with brackets, a diamond of external-only structures at depths 16, 20 and 24, a
cyclic type under `--force`, a boolean constant, `compare` with `-W` on a baseline-only plugin
check, a wide-character unit in the table, a lone surrogate in a unit, the demo's boolean row).
Probe ids `Pn` below refer to those transcripts.

### Strengths

- The check registry is per bag, not global: `DiagnosticBag.register` fills `self._registered`
  (`src/ddd/diagnostics.py:470-478`) and `CHECKS` is never mutated, so a language server
  checking two projects with different plugins cannot leak a check or an override from one
  into the other, and a plugin loaded twice registers on each bag once.
- A plugin file is cached under a name derived from the sha256 of its *resolved* path
  (`src/ddd/plugins.py:200-201`): two files with one stem in two directories are two modules,
  two spellings of one file are one, and a body that fails or exits is unregistered so that a
  second load retries (`:211-233`); `KeyboardInterrupt` still interrupts.
- `render` resolves the output directory once, anchors bare paths to it, refuses an escape and
  decides a clash on the resolved path (`src/ddd/backends/base.py:96-119`), which on Windows
  folds case through `WindowsPath` equality; `write` decides every status first, stages every
  payload beside its target, renames in order and rewrites the escaping error's `filename` to
  the real target (`:172-220`), exactly as its docstring says.
- The set the example type header includes `<stdint.h>` for counts the members of every
  structure (`src/ddd/ir.py:691-706`), so a project whose only integer sits inside a structure
  still compiles; the types header's order is a name-ordered depth-first post-order over member
  type names whatever their dimensions (`src/ddd/analysis.py:424-463`), so a structure reached
  only through an array member of another is complete before its container.
- The bare `COMPU_METHOD` name is platform-independent: `dictionary.objects` is in name order
  (`src/ddd/analysis.py:720`, `:742`, `:770`), so when two unit spellings share a slug (pass 4
  Minor 8) the alphabetically first object keeps the bare name whatever the include order.
- `boolean` is `bool` with `<stdbool.h>` in the ISO table and `1`/`0` in every literal
  (`src/ddd/backends/c/types.py:18`, `:51`, `c/literals.py:18-24`), so an initialiser needs no
  header on any platform.
- The build record is closed and versioned (`src/ddd/build_info.py:47-54` `extra="forbid"`),
  and a record from a newer tool - an unknown key or a higher stamp - is declined rather than
  misread (`src/ddd/lsp/discovery.py:55-62`), as `SPEC.md:758` says.
- `ddd cmake-dir` and `ddd templates-dir` find their files from a wheel (force-included at
  `pyproject.toml:54-58`), an editable install and a checkout (`src/ddd/cli.py:89-92`,
  `src/ddd/backends/c/backend.py:36-60`); a zip import answers "not part of this installation"
  rather than crashing.
- The conventions hold: outside `cli.py` nothing prints, exits or names a stream except the
  server's own loop (`src/ddd/lsp/server.py:202`, `:638-639`) and `__main__.py:10`; no backend
  imports the loader or the analysis (`tests/test_backends.py:74-87` enforces it), and neither
  re-implements an analysis rule - the a2l's `_carries` and `_default_format` are mapping rules
  section 5.2 states; the naming rules in the docstring of `c/backend.py:8-18` are the ones
  `docs/templates.rst:86-88` documents.
- CMake's `string(JSON)` accepts a byte order mark (`cmake_probe.cmake` 1a-1c), so a description
  the loader reads with `utf-8-sig` is read by `_ddd_description_name`, `_ddd_is_component_file`
  and `_ddd_project_plugins` too.
- The forced generation is safe where a naive walk would not be: a cyclic type under `--force`
  drops the instance, so `_section_groups.alignment` never recurses into the cycle (P6, exit 1,
  four files written), and a boolean constant is refused by the model before any backend spells
  it (P7: `constants[0].value: error[schema]: Input should be a valid integer (got: True)`).
- Performance (`perf_results.txt`): `ddd generate all --dictionary` takes 2.0 s at N = 100
  (4 300 objects, 1 000 leaves) and 21.6 s at N = 1000 (43 000 objects, 10 000 leaves; 17.6 s
  when everything is unchanged). In process at N = 1000: load 1.45 s, analyze 3.96 s, c model
  4.16 s, jinja for the c 0.3 s, a2l model 0.96 s plus 0.7 s of jinja, dictionary text 0.43 s
  (45 MB), write 1.15 s. The renderers, the writer and the a2l record construction are linear;
  what is not is below.

### Issues

#### Critical

None found.

#### Important

1. **The collected project file spells its includes as literal absolute paths, and the loader
   reads any path containing `[` as a glob** (`cmake/Ddd.cmake:260`
   `set(entries "$<$<BOOL:${components}>:\n      \"$<JOIN:${components},\"$<COMMA>\n`
   `\">\"\n    >")`, written verbatim into `"includes"` at `:275`; `src/ddd/loading.py:990`
   `if not any(character in pattern for character in _GLOB_CHARACTERS):` with `:53`
   `_GLOB_CHARACTERS = frozenset("*?[")`). Trigger: the ordinary collected mode on a checkout
   under a directory whose name carries a bracket - `C:/work/proj [v2]/`, a copy Windows or a
   user names that way - or, on POSIX, a `?` or `*`. Outcome (P4a-c, a project including
   `.../cases/proj [v2]/c.ddd.json` by its absolute path): `error[include-empty]: pattern
   '.../proj [v2]/c.ddd.json' matches no file`, exit 1 on `check` and `generate`, nothing
   written, and `ddd sources` lists the project file alone, so the module's dependency list is
   empty as well; the same file under `proj_v2/` checks clean (P4d). The message calls a
   pattern what the module wrote as a path, and nothing in `docs/build_integration.rst` says
   the source tree may not carry those characters. Fix: escape the glob characters in the
   written includes (`[` as `[[]`, and `*`/`?` likewise) in `_ddd_write_project_file`, or let
   `_expand` try the entry as a literal path first and treat it as a pattern only when no such
   file exists.

2. **`ddd_generate` and `ddd_add_component` never read `KEYWORDS_MISSING_VALUES`, so a keyword
   whose value expanded to nothing is silently dropped** (`cmake/Ddd.cmake:363-369`
   `cmake_parse_arguments(PARSE_ARGV 1 arg ...)` followed by `if(arg_UNPARSED_ARGUMENTS)` only;
   `:191-194` likewise). Trigger: `ddd_generate(fw.elf TEMPLATE_DIRECTORY t ADDRESS_MAP
   ${DDD_MAP})` with `DDD_MAP` unset or empty - the ordinary CMake mistake - or `PROJECT
   ${PROJ}`, `SCHEMA_DIRECTORY ${DIR}`, `SEVERITY ${SEV}` the same way. Outcome
   (`cmake_probe.cmake` 2, CMake 4.4.3): `arg_KEYWORDS_MISSING_VALUES='ADDRESS_MAP;PROJECT'`
   and `arg_ADDRESS_MAP` unset, so `:406` `if(arg_ADDRESS_MAP AND NOT arg_NO_A2L)` is false:
   the a2l is generated with every `ECU_ADDRESS 0x00000000`, no map is seeded and none is a
   dependency, and the two-run flow the map was configured for never happens; `PROJECT` without
   a value falls into the collected mode. CMake prints an author warning under CMP0174 OLD and
   nothing at all under a `cmake_minimum_required(VERSION 3.31)` project, where the variable is
   the empty string. Fix: `if(arg_KEYWORDS_MISSING_VALUES) message(FATAL_ERROR ...)` beside the
   unparsed-arguments check in both functions.

#### Minor

1. **`build_code_model` is quadratic in components times objects**
   (`src/ddd/backends/c/model.py:344` `dictionary.owned_by(component.name) +
   dictionary.instances_owned_by(component.name),` per component; `src/ddd/ir.py:722`
   `return tuple(entry for entry in self.objects if entry.owner == component)`). Measured
   (`perf_results.txt`): the c model takes 0.05 s at N = 100 and 4.16 s at N = 1000 - eighty
   times for ten times the project - of which `owned_by` is 2.9 s and `instances_owned_by`
   0.35 s (44 000 000 comparisons), the largest single phase of the
   21.6 s run. Fix: bucket the objects and instances by owner once (`dict[str, list]`) in
   `build_code_model`, or on the dictionary.

2. **The a2l `GROUP` construction walks every leaf once per component**
   (`src/ddd/backends/a2l/model.py:448` `for leaf in self._dictionary.leaves:` inside `_group`,
   called per component at `:279`). Measured: `_group` is 0.56 s of the 0.96 s a2l model at
   N = 1000 (1 000 components times 10 000 leaves), against 0.04 s for the whole model at
   N = 100. Fix: index the leaves by `instance` once in the builder.

3. **A run with an address map builds the whole a2l model twice**
   (`src/ddd/backends/a2l/model.py:223` `model = build_a2l_model(dictionary, A2lOptions(), "")`
   inside `addressed_symbols`, called from `src/ddd/cli.py:700` before `render` builds it again
   at `:898`). Measured: 1.20 s at N = 1000 on top of the 1.67 s a2l render. Fix: build once and
   read the names off the model the backend renders, or compute the exported names without the
   record views.

4. **`_section_groups.alignment` recurses without memoisation, so a diamond of external-only
   structures costs the c model exponential time** (`src/ddd/backends/c/model.py:293-306`
   `def alignment(name: str) -> int:` ... `strictest = max(strictest, alignment(member.type))`).
   Trigger (P5): `L0_t {a: L1_t, b: L1_t}` ... `L23_t {a: Ext_t, b: Ext_t}` - external members
   contribute no leaf, so the leaf cap never weighs the tree - and a placed instance of `L0_t`.
   Outcome: `generate c` 23.1 s against `check` 20.4 s at depth 24 (1.74 s against 1.56 s at
   depth 20), the difference doubling per level; the analysis's own walk grows the same way
   (20 s for `check` alone, pass 9's area). Contrived input, so minor. Fix: memoise per type
   name; the dictionary's types are already acyclic by construction.

5. **The address map refuses a byte order mark that every description file may carry**
   (`src/ddd/backends/a2l/options.py:49` `data = json.loads(path.read_text(encoding="utf-8"))`
   against `src/ddd/loading.py:1112` and `src/ddd/cli.py:1432`, which read `utf-8-sig`).
   Observed (P3a): `--address-map p3_bom.json` -> `ddd: the address map '...' is not valid
   json: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)`, exit 2 -
   Python's advice to a programmer, for a file a Windows tool or Notepad writes that way. Fix:
   `encoding="utf-8-sig"`.

6. **The address grammar is Python's `int()`, and a duplicate symbol keeps the last value
   silently** (`src/ddd/backends/a2l/options.py:73-76` `base = 16 if text.lower().startswith(
   ("0x", "-0x")) else 10` ... `number = int(text, base)`; `:49` `json.loads` without
   `object_pairs_hook`, where the loader refuses a repeated key at `src/ddd/loading.py:578`).
   Observed (P3b, P3c): `"0x1_0000"` -> `ECU_ADDRESS 0x00010000`, the Arabic-Indic digits
   `"١٢"` -> `0x0000000C`, `"+5"` -> `0x00000005`; `{"ValueA": "0x10", "ValueA": "0x20"}` ->
   `0x00000020` with no word. A map is "written by a linker script or a patch tool nobody is
   looking at" (`:52-53`), which is the argument for a strict grammar. Fix: a pattern
   `^(0[xX][0-9A-Fa-f]+|[0-9]+)$` on the stripped text and a pairs hook refusing a repeat.

7. **`dump -o .` and `--dictionary .` end in a Python message about an empty name**
   (`src/ddd/backends/base.py:190` `temporary = target.with_name(target.name + STAGING_SUFFIX)`,
   a `ValueError` for a path with no final component, printed verbatim by `src/ddd/cli.py:125`).
   Observed (P2a, P2c): `ddd dump demo.ddd.json -o .` -> `ddd: WindowsPath('.') has an empty
   name`, exit 2; `-o <existing directory>` says `cannot write 'cases': Access is denied`
   instead (P2b). Fix: refuse a target without a name in `_write_dictionary` and
   `_dictionary_file` with the tool's own words ("-o names a directory, give it a file").

8. **`list` does not flush the table before the findings, unlike its two siblings**
   (`src/ddd/cli.py:953-954` `_print_table(dictionary)` then `_report(bag, args.format)`;
   `artefacts` flushes at `:1245` and `:1255` and `sources` at `:1286` "so that the listing
   must not interleave with the findings in a buffered pipe"). Observed (P1): `ddd list
   examples/inconsistent/project.ddd.json > log 2>&1` -> the two `multiple-producers` and
   `definition-mismatch` errors are the first lines of the file and the table the last, while
   `ddd sources ... > log 2>&1` starts with the listing. `dump` to stdout has the same shape at
   `:973-974`. Fix: `sys.stdout.flush()` before `_report` in both.

9. **The table pads by code points, so an East Asian wide unit shifts its row**
   (`src/ddd/cli.py:1532` `widths = [max(len(row[column]) for row in rows) ...]`, `:1534`
   `value.ljust(width)`). Observed (P9): a unit `温度` is two code points and four columns
   wide, so `SHAPE`, `INIT`, `PRODUCER` and `CONSUMERS` of that row start two columns right of
   the header (`display=65` against `63` for the rows beside it). `°C` is fine. Fix: measure
   with `unicodedata.east_asian_width` (`W`/`F` count two), or leave it as a known limit of
   the text table.

10. **A `-W` naming a check of a plugin only the baseline loads is refused after the baseline
    was analysed under it** (`src/ddd/cli.py:647` `bag.policy.verify(bag.registered)`, where the
    baseline's plugins registered on the private bag of `:1408` `own = DiagnosticBag(
    SeverityPolicy(bag.policy.overrides, strict=False))` - the overrides shared, the
    registrations not). Observed (P8b): `ddd compare examples/layout/project.ddd.json
    layout.json -W layout/removed-entry=ignore` -> `ddd: unknown check 'layout/removed-entry':
    no loaded plugin registers it`, exit 2; without `-W` the same pair reports `missing-plugin`
    for both sides and "can replace" (P8c). The plugin ran for the baseline, its checks were
    resolvable there, and the run then says it never loaded - the same asymmetry as pass 5
    Minor 9, from the other side. Fix: register the baseline's plugin checks on the shared bag
    before `verify` (they are known), or word the error "not among the candidate's plugins".

11. **Templates run as unsandboxed Python, and no page says so beside the plugin boundary**
    (`src/ddd/backends/base.py:225-232` builds a plain `Environment`, so `{{ ''.__class__
    .__mro__[1].__subclasses__() }}` reaches `os` from any template; `docs/plugins.rst:209-212`
    and `SPEC.md:1069-1076` state "naming a plugin runs it" for plugins alone; `docs/templates.rst`
    has no sentence about it). Trigger: a repository's template directory is as much code as its
    plugins, and a reader who has learnt the plugin rule concludes the templates are data. The
    previous review's security note (`previous-review.md:1811`) accepted the boundary "as long as
    it is stated next to them"; it is not. Fix: one sentence on the templates page and beside the
    plugin rule (or `SandboxedEnvironment`, which nothing the example templates do would notice).

12. **Nothing checks that the module and the tool it found are one release**
    (`cmake/Ddd.cmake:39` `find_program(DDD_EXECUTABLE NAMES ddd DOC "The ddd data dictionary
    tool")`; no `--version` handshake anywhere). Trigger: a project that copied `Ddd.cmake` into
    its tree, as `ddd cmake-dir` and the header at `:18` invite, beside a `ddd` of another
    release - 0.10.0's module with 0.9.0's tool, say. Outcome: the configure passes (`schema all`,
    `build-info` and `sources` accept the old tool) and the first build fails with argparse's
    `generate: error: unrecognized arguments: --dictionary`, nothing naming the mismatch; the
    reverse silently builds with the old module's option set. `DEPENDS "${DDD_EXECUTABLE}"`
    (`:559`) likewise watches a wrapper script rather than the tool when `:38`'s "a wrapper
    script running python -m ddd" is used. Fix: run `${DDD_EXECUTABLE} --version` at include
    time and compare with a version spelled in the module (the release already spells it in
    nine files).

13. **The a2l carries `IF_DATA XCP` blocks and no A2ML that defines them, and the pages that
    say what comes "from whatever configures the XCP stack" do not list the A2ML among it**
    (`src/ddd/backends/a2l/templates/project.a2l.jinja:83-89` `/begin IF_DATA XCP` ...
    `/end IF_DATA` per measurement with a raster; no `/begin A2ML` anywhere in the file;
    `docs/generated_artefacts.rst:762-766`, `docs/faq.rst:598-604`, `SPEC.md:1727-1728` name
    the module level `DAQ` list, the protocol layer and the transport). Fact: ASAP2 1.6.1
    defines the content of an `IF_DATA` block only through the A2ML section of the same file.
    Consequence: a reader without an XCP AML of its own either skips the block by bracket
    counting - losing the event assignment the raster feature exists for, silently - or refuses
    it; a project merging the stack's fragment as the pages say gets the AML with it, one that
    loads the file alone does not. Unconfirmed against a calibration tool (none here - CANape
    would settle which of the two it does). Fix: say on both pages that the merged fragment has
    to carry the XCP A2ML, or write the standard block (open question 1).

### Status of the 2026-09-08 findings in this area

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| P8 I1 | a plugin module ran before it was in `sys.modules` | fixed | `src/ddd/plugins.py:211-233` (registered first, popped on failure); `tests/test_plugins.py:237`, `:637` |
| P8 I2 | path clash decided on spelling; a backend could write anywhere | fixed | `src/ddd/backends/base.py:96-119`; `tests/test_backends.py:255-320`, `tests/test_plugins.py:1796-1961` |
| P8 I3 | template and factory exceptions escape as tracebacks with exit 1 | mostly fixed | templates: `base.py:255-270` (bare exceptions too); factory and `generate` results: `plugins.py:423-434`, `:473-480`; residue: no last-resort handler in `main` (`cli.py:116-126`), pass 5 Minor 2 |
| P8 I4 | findings discarded when a later step fails | fixed | `cli.py:1460-1488` (`_reported_on_failure`) around every producing step (`:599`, `:631`, `:830`, `:995`, `:1365`); residue: an exception outside `(OSError, ValueError)` still discards them (same residue as I3) |
| P8 I5 | `sys.exit` in a hook was a clean run | fixed | `plugins.py:214`, `:251`, `:339`, `:487` catch `SystemExit` and name the code (`:183-187`) |
| P8 I6 | generation not atomic, wrong file named | fixed | `base.py:184-219` (staging, rollback of creations, `filename` rewritten to the target); `tests/test_generation.py:277-370` |

Minor ones of the previous pass 8 in this area, in bulk: 2 still open (`cli.py:106`
`reconfigure(encoding="utf-8")` without `errors=`; P10c: a lone surrogate in a unit ends
`ddd list` with `ddd: 'utf-8' codec can't encode character '\ud800'`, exit 2, after the table
header; `check` passes because no finding quotes the unit, json mode is fine); 4 still open
(`src/ddd/backends/c/literals.py:137-142` still folds `Sensor` and `Sensor_` into one guard and
`name-collision` covers case alone); 6 still open (`docker/compile.sh:52` `grep -oE --
'(-W [^ ]+|--strict)'` still misses `-Wcheck=sev`); 7 documented rather than changed (pass 5); 8
still open (pass 5); 9 is pass 4 Minor 10; 11 fixed (`cli.py:907-912`). 1, 3, 5 and 10 are the
server's and the extension's.

The two design notes (`previous-review.md:1814-1821`): "Report before you write" is answered by
`_reported_on_failure` rather than by reordering - the findings are still printed after the
write (`cli.py:902`, then `:923`), but every `OSError` and `ValueError` between the analysis and
the report now prints them first; what remains is the class of exception the block does not
list. "The plugin boundary is thinner than its docstring says" is closed for the factory's result,
the `generate` result, the paths and `SystemExit`, and validators are now guarded too
(`plugins.py:319-342`); what remains is pass 5 Minor 2 (`BaseException`) and Minor 3 (hooks
receive the mutable `dict`s inside the frozen records).

Forwarded items, settled from the code (mechanism confirmed, nothing to add unless said):

- Pass 4 Important 1: `c/literals.py:132` `return collapsed.replace("*/", "* /")` replaces the
  closing marker alone. Important 2: `a2l/model.py:659-662` escapes `\`, `"` and the control
  characters and passes every other code point. Important 4: `a2l/model.py:412` and `:425` write
  `references.get("input")` verbatim; `_resolve_exported` at `:320` pulls only what `by_name`
  holds, and `by_name` is the plain objects (`ir.py:674-675`), so an instance is never a record
  and its name is written anyway. Minor 1: `base.py:294` names `template_name`, `:311-317` reads
  the deepest frame's line and never its template; the `TemplateSyntaxError` branch at `:288-290`
  has the same gap (`error.name` unused), so a syntax error inside an imported helper is named
  under the importer too. Minor 4: `c/model.py:192-198` renders `value: int | float` bare. Minor
  8: `:631-641`. Minor 11: nothing anticipates a reserved name or `MAX_PATH`; the `OSError` of
  `base.py:189` or `:197` surfaces as `cannot write '...'`. Minor 12: `c/backend.py:93-101` -
  `list_templates` over a nonexistent directory is empty, so the "no template" message answers.
- Pass 5 Important 1: `cli.py:1373` and `:898` run hooks and plugin backends with `sys.stdout`
  untouched; one more consequence in the module: `cmake/Ddd.cmake:62-77` turns every stdout line
  of `ddd sources` into a dependency path, so a plugin's stray `print` becomes a file the build
  cannot make. Important 2: `cli.py:998`, `:657`, `:900` compare nothing against
  `workspace.sources()`. Important 3: `Ddd.cmake:553` declares `generated_outputs` alone, no
  `BYPRODUCTS`; `base.py:172-220` never deletes. Minor 1: `cli.py:146`. Minor 2:
  `plugins.py:487`, `cli.py:116-126`. Minor 3: `plugins.py:63` hands the dictionary itself, and
  `resolve_blocks` at `:287` copies a block one level deep. Minor 5: `a2l/options.py:49`,
  `cli.py:1127-1130`, `:1136-1140` unguarded. Minor 6: `cli.py:124-126` (`BrokenPipeError` is an
  `OSError`). Minor 7: `cli.py:669-673`. Minor 8: `cli.py:1421-1435` exists on the compare side
  only. Minor 9: `plugins.py:389-397` one `location` for both sides, `cli.py:638`; Minor 10 above
  is its `-W` face. Minor 10: `Ddd.cmake:165-171`; since `string(JSON)` accepts a byte order
  mark, only invalid json takes that branch. Minor 14: `cli.py:1228-1232`, `:943-946`. Minor 16:
  `examples/templates/ddd_globals.c.jinja2:52-55`.
- Pass 1 Minor 4: `a2l/model.py:291` `value=str(entry.value)` and
  `examples/templates/ddd_types.h.jinja2:23` `{{ constant.value }}` both spell the parsed number.
- Pass 8 Minor 8: `cli.py:1432` reads and parses the whole file to sniff. Minor 9: `cli.py:16-72`
  imports the analysis, the comparison and the backends at module level; only the server is
  lazy (`:1110`). Minor 13: `cli.py:1363` returns before `:1370` verifies.
- Pass 6 Minor 9 (the server never calls `verify`): the five assemblies of the policy are
  `cli.py:626`, `:1119`, `:1360`, `:1408` and the server's; only `:647` and `:1370` verify.
- Pass 3 Important 3: the `Location(...)` sites built from a typed path are `cli.py:602`, `:609`,
  `:649`, `:712`, `:1391`, as pass 5 listed; nothing changed.

### Open questions

1. Should the a2l carry the standard XCP A2ML block beside the `IF_DATA XCP` it writes, or should
   the pages say the merged fragment has to bring it (Minor 13)? The first changes the template
   and the "no module level XCP" decision's neighbourhood; the second is two sentences.
2. Who escapes the glob characters of a collected include (Important 1): the module, when it
   writes the project file, or the loader, by trying an entry as a literal path first? The
   second also helps a hand-written include naming such a directory; the first keeps the loader's
   grammar as written in section 2.
3. Should `ddd_generate` refuse a keyword without a value (Important 2)? Yes is two `FATAL_ERROR`
   lines; no leaves the unset-variable mistake to the a2l reader.
4. Should the module verify the tool's version (Minor 12), and against what - a version spelled
   in the module (a tenth file for the release script) or a `--cmake-api` answer?
5. Should templates be sandboxed (Minor 11), or is the statement enough? `SandboxedEnvironment`
   costs nothing the example templates use, but a project's helper may reach a method the
   sandbox refuses.

### Test gaps

- `tests/test_cmake.py`: a source directory whose name carries `[` under the collected mode
  (Important 1); a keyword given without a value - `ADDRESS_MAP ${UNSET}` - refused (Important 2);
  a `DDD_EXECUTABLE` of another release (Minor 12).
- `tests/test_loading.py`: an include entry that names an existing file whose path contains a
  glob character (Important 1, whichever side takes it).
- `tests/test_backends.py` or `tests/test_generation.py`: a bound on `build_code_model` - linear
  in objects, say N components with M objects each generated in time proportional to N times M
  (Minor 1); the a2l model likewise (Minor 2); a diamond of external-only structures rendered
  (Minor 4).
- `tests/test_a2l.py`: an address map with a byte order mark (Minor 5); one with underscores,
  non-ASCII digits and a repeated key (Minor 6) - `:171-183` cover hex, decimal and the refusals
  only.
- `tests/test_cli.py`: `dump -o .` and `--dictionary .` (Minor 7); a wide-character unit in the
  table (Minor 9); `compare` with `-W` on a check only the baseline's plugin registers
  (Minor 10).
- The interleaving of `list`'s table and findings (Minor 8) has no test on either sibling; a
  test writing both streams into one buffer would pin all three.

### Assessment

The periphery reads as the previous review left it after its fixes, with the boundaries it
asked for now in the code: the plugin cache is keyed on the real file, the check registry is
per bag, the renderer confines and deduplicates on resolved paths, the writer stages and rolls
back, every producing step prints its findings before a usage error, and the module declares
every dependency it can name. The two Important findings sit where the CMake module meets the
loader and CMake's own argument parser: a bracket in a source directory turns every collected
include into a glob that matches nothing, and a keyword whose variable is unset drops the
address map - or the project - without a word. The rest is small and mostly measured: the c
model's per-component scan of every object is the one quadratic loop that shows at a thousand
components, the a2l groups and the second model build behind an address map are its lesser
cousins, an unmemoised alignment walk is exponential on an input nobody writes, the address map
reads with a stricter encoding and a looser grammar than the descriptions, and four cosmetic
items in the command line - an unflushed table, a Python message for `-o .`, wide characters,
an override refused after it was applied. Two questions belong to the maintainer: whether the
a2l should carry the A2ML its `IF_DATA` blocks presuppose, and whether templates, which run as
freely as plugins, should be said to.

### Verification

Every candidate of this pass was handed to a second reviewer (group C): 15 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P10-I1 | Important | CONFIRMED | Important | `Ddd.cmake:260` joins the collected paths verbatim into `includes`, `loading.py:990` treats any entry holding `*?[` as a pattern; collected mode with the source tree under `cmk/proj [v2]/`: the written project carries `".../proj [v2]/ddd/sensor_hub.ddd.json"`, `ninja` -> `error[include-empty]: pattern '.../proj [v2]/ddd/sensor_hub.ddd.json' matches no file`, exit 1, nothing written; the same include from a plain-named directory checks `ok` |
| P10-I2 | Important | CONFIRMED | Important | `Ddd.cmake:363-369` checks `arg_UNPARSED_ARGUMENTS` only; `ddd_generate(fw.elf ... ADDRESS_MAP ${DDD_MAP})` with `DDD_MAP` unset: under `cmake_minimum_required 3.30` CMake itself prints an author warning, under `3.31` nothing; both: no `addresses.json` seeded, `build.ninja` has no `--address-map`, the build passes and `Miss.a2l` has 5 of 5 `ECU_ADDRESS 0x00000000` |
| P10-M1 | Minor | CONFIRMED | Minor | `c/model.py:344` calls `owned_by` and `instances_owned_by` per component, `ir.py:722` scans every object each time; re-ran pass 10's `perf10.py`: c model 0.05 s at N=100 against 3.97 s at N=1000, of which `owned_by` 2.77 s in 44 000 generator calls |
| P10-M2 | Minor | CONFIRMED | Minor | `a2l/model.py:448` `for leaf in self._dictionary.leaves:` inside `_group`, called once per component at `:279`; my profile: `_group` 0.55 s of the 1.47 s `build_a2l_model` at N=1000 (1 000 components x 10 000 leaves) |
| P10-M3 | Minor | CONFIRMED | Minor | `a2l/model.py:223` `model = build_a2l_model(dictionary, A2lOptions(), "")` inside `addressed_symbols`, called from `cli.py:700` before `render` builds the model again at `:898`; measured 1.00 s beside the 1.69 s a2l render at N=1000 |
| P10-M4 | Minor | CONFIRMED | Minor | `c/model.py:293-306` `alignment` recurses per member with no memo; pass 10's diamonds re-run: check / generate c 0.67 / 0.68 s at depth 16, 1.71 / 1.90 s at 20, 19.8 / 22.5 s at 24 - the c model's share doubles per level, on an input nobody writes |
| P10-M5 | Minor | CONFIRMED | Minor | `options.py:49` `path.read_text(encoding="utf-8")` against `loading.py:1112` and `cli.py:1432` `utf-8-sig`; a map starting `EF BB BF` -> `ddd: the address map '...' is not valid json: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)`, exit 2 |
| P10-M6 | Minor | CONFIRMED | Minor | `options.py:73-76` `int(text, base)`, `:49` `json.loads` without a pairs hook; `"0x1_0000"` -> `ECU_ADDRESS 0x00010000`, `"١٢"` -> `0x0000000C`, `"+5"` -> `0x00000005`; `{"ValueA": "0x10", "ValueA": "0x20"}` -> `0x00000020` with no message, exit 0 |
| P10-M7 | Minor | CONFIRMED | Minor | `base.py:190` `target.with_name(target.name + STAGING_SUFFIX)` raises on a path with no name, printed by `cli.py:125`; `dump demo.ddd.json -o .` and `generate c ... --dictionary .` -> `ddd: WindowsPath('.') has an empty name`, exit 2 |
| P10-M8 | Minor | CONFIRMED | Minor | `cli.py:953-954` prints the table then reports without a flush (`:1245`, `:1255`, `:1286` flush); `list examples/inconsistent > log 2>&1` -> first line `error[multiple-producers]`, last line the `UnusedSignal` row; `dump v1.3 > log 2>&1` -> the `unused-output` warning first, `}` last; `sources` starts with the listing |
| P10-M9 | Minor | CONFIRMED | Minor | `cli.py:1532` `len(row[column])`, `:1534` `ljust`; a unit `温度`: its row is 67 code points but 69 display columns (the `V` row 67 / 67), so `SHAPE` onwards sit two columns right of the header |
| P10-M10 | Minor | CONFIRMED | Minor | `cli.py:647` `bag.policy.verify(bag.registered)` after the baseline's plugin registered on the private bag of `:1408`; `compare examples/layout/project.ddd.json layout.json -W layout/removed-entry=ignore` -> `ddd: unknown check 'layout/removed-entry': no loaded plugin registers it`, exit 2; without `-W` the pair compares (`missing-plugin` twice); second face of P5-M9 |
| P10-M11 | Minor | CONFIRMED | Minor | `base.py:225-232` builds a plain `Environment`; a template `{{ cycler.__init__.__globals__.__builtins__.__import__('os').getcwd() }}` rendered the working directory into `ddd_globals.c`, exit 0; `docs/templates.rst` has no sentence on templates being code (grep `trust`, `sandbox`, `as code`, `runs python`: none), `docs/plugins.rst:209-212` states the rule for plugins alone |
| P10-M12 | Minor | CONFIRMED | Minor | `Ddd.cmake:39` `find_program(DDD_EXECUTABLE NAMES ddd ...)`, and no `--version` anywhere in the module (grep); `git show v0.9.0:src/ddd/cli.py` has no `--dictionary`, which `:549` passes on every generation, so a 0.9.0 tool under this module fails at build time with argparse's `unrecognized arguments` |
| P10-M13 | Minor | CONFIRMED | Minor | `project.a2l.jinja:83-89` writes `/begin IF_DATA XCP ... /end IF_DATA` and the file has no `/begin A2ML` and no `/include` (grep); ASAP2 1.6.1 §3.5.75 (p. 130): the parameters of `IF_DATA` "have to be described in the ASAM MCD-2 MC metalanguage", §5.3 (p. 225): the AML's `IF_DATA` tag "is then used by the MCD tool to interpret the data"; `generated_artefacts.rst:762-766` and `faq.rst:598-604` name the `DAQ` list, the protocol layer and the transport, not the AML |

## Pass 11a: the test suite, part A (fixtures, models, loading, analysis, structures, comparison)

### Scope covered

Read in full, with line numbers: `tests/conftest.py`, `tests/test_models.py`,
`tests/test_loading.py`, `tests/test_edge_cases.py`, `tests/test_hardening.py`,
`tests/test_analysis.py`, `tests/test_structures.py`, `tests/test_constants.py`,
`tests/test_types.py`, `tests/test_units.py`, `tests/test_sections.py`, `tests/test_rasters.py`,
`tests/test_calibration.py`, `tests/test_embedded.py`, `tests/test_compare.py`,
`tests/test_comparison_tables.py` (894 collected tests, 39 % of the 2285); `pyproject.toml:98-116`
(pytest and coverage); `docs/developer_documentation.rst:60-320`. To judge what the tests pin,
the code they exercise: `src/ddd/analysis.py` in full, `src/ddd/compare.py` in full,
`src/ddd/diagnostics.py` in full, `src/ddd/loading.py:88-120, 497-660, 985-1200`,
`src/ddd/models/{objects,conversion,common}.py` in full, the validator sites of
`models/{types,rasters,sections,constants,component}.py`, the field lists of `src/ddd/ir.py`.
The "Test gaps" sections of `reports/pass-1.md` to `pass-10.md`, the previous review's test
reviews at `previous-review.md:1674-1686` and `1822-1834`, and the tests named by the ten fix
plans under `docs/superpowers/plans/2026-09-08-*.md` and `2026-09-09-*.md`.

Ran (outputs under `scratchpad/pass-11a/`):

- `python -m pytest --no-cov -q --durations=30 -p no:cacheprovider` over the whole suite
  (`full-suite-durations.txt`): 2284 passed, the one known symlink failure; the summary line is
  absent because `-q` doubled the `-q` of `addopts` into `-qq`, so the wall time is the
  baseline's 2 min 22 s. `python -m pytest --co -q -o addopts=` (`collection.txt`): 2285 items
  in 0.49 s.
- Every file of my half alone, twice (`alone-*.txt`, `alone-timing.txt`): all pass; 12.5-13.3 s
  for the half. The half in reverse collection order through a one-line plugin
  (`reverse_plugin.py`, `pytest_collection_modifyitems(items).reverse()`): 894 passed. The
  classes touching process state (`test_edge_cases.py::TestCommandLineEdges`,
  `test_hardening.py::TestTheRestOfTheEdges`, `test_constants.py::TestTheEditor`) alone, and
  the two entry-point tests in both orders: all pass.
- `--durations=15` over the half (`half-durations.txt`); the half alone under
  `--cov=ddd --cov-branch --cov-report=term-missing` (`half-coverage-core.txt`) to see which
  core lines only the other half reaches.
- Four experiments through `conftest` helpers and the public API (`exp-inf/`, `exp-bits/`,
  `exp-gaps/`), quoted where a finding rests on them. Nothing in the repository was edited.

### Strengths

- The half is order independent: no file needs another to run first, the reverse order passes,
  and the three classes that touch process state restore it (`monkeypatch` on `Path.resolve`,
  `Path.read_text`, `Path.glob` and `sys.argv`; `importlib.reload` of an import-only module;
  a subprocess with a copied environment). No test changes the working directory, the
  environment or a registry: `DiagnosticBag.register` is per bag (`diagnostics.py:470-478`)
  and `CHECKS` is never mutated. `main()` reconfigures the encoding of `sys.stdout` and
  `sys.stderr` on every call (`cli.py:100-112`); under pytest both are capture streams that are
  utf-8 already, so the change is a no-op and needs no teardown.
- Nothing writes outside `tmp_path`: `DEMO` and `EXAMPLES` are only read
  (`tests/test_compare.py:389-466`, `tests/test_edge_cases.py:396-442`,
  `tests/test_embedded.py:230`). `write_tree` writes bytes exactly (`newline=""`,
  `tests/conftest.py:66-80`), so a fixture is the same file on both platforms; the one
  platform-split behaviour, a NUL byte in a path, is exercised on whichever platform the suite
  runs and forced for the other (`tests/test_hardening.py:950-976`). No test depends on mtime,
  hash order, the network or an installed `ddd` (the subprocess runs `sys.executable -m ddd`
  with `PYTHONPATH=src`).
- The only default silence is documented and opted back into where it matters:
  `missing-id=ignore` in `run_analysis` (`tests/conftest.py:92-99`), `missing-id=info` in
  `tests/test_models.py:334-358`; `tests/test_constants.py:405-420` and
  `tests/test_embedded.py:221-239` silence it explicitly for a CLI and an example run.
  Relaxations elsewhere are the subject of the test (`unknown-constant=ignore`,
  `unknown-reference=warning`, `missing-producer=warning`).
- Assertions are behavioural: findings by identifier, messages by their load-bearing phrase,
  pointers by text, generated files by content, dictionaries by round trip. No whole-document
  snapshot exists in the half; the strongest pins are relative ones - the byte identity of the
  embedded and the standalone homes (`tests/test_embedded.py:357-369`), the include-order
  independence of the enum registry (`tests/test_hardening.py:290-319`).
- The fix plans' promised core tests all exist and pin what the plans say: the thirteen of
  `2026-09-08-dropped-declarations-are-marked.md` (`tests/test_analysis.py:704-1039`), the
  seven of `dangling-references-are-dropped.md` (`:1041-1215`, `tests/test_edge_cases.py:306-338`),
  the five of `2026-09-09-local-reference-is-a-use.md` (`:1283-1438`), the six tasks of
  `core-robustness.md` (`tests/test_models.py:423-780`, `tests/test_loading.py:159-302`,
  `tests/test_structures.py:313-726`, `tests/test_analysis.py:579-702`,
  `tests/test_hardening.py:569-633, 1013-1031`, `tests/test_structures.py:1824-1903`) and task 3
  of `listing-commands.md` (`tests/test_analysis.py:343-384`).
- `tests/test_hardening.py` is what its docstring says: 65 tests in eleven classes named by what
  was at stake; 37 of them pin a message phrase and one pins a count. `tests/test_edge_cases.py`:
  39 of its 40 tests assert a behaviour (the one exception is Minor 3).
- The coverage gate is real for this half: with my fifteen files alone, `compare.py` is at 100 %,
  `analysis.py` at 99 % (the eight missed statements are every external-type branch:
  `analysis.py:1030, 1154, 1161, 1203-1205, 1589, 2035-2043`, reached only by
  `tests/test_external.py`), `loading.py` at 91 % (plugin loading and block validation,
  `:892-981`, part B), `diagnostics.py` at 88 % (`to_dict`, the policy's usage errors, `verify`,
  `register`: `tests/test_cli.py:134-142`, `tests/test_plugins.py:531, 1208`). The two pragmas
  in `src/` (`cli.py:104` `no branch`, `identity.py:32` `no cover`) and the two `exclude_also`
  patterns (four Protocol bodies, `TYPE_CHECKING` blocks) hide nothing executable.
- The 27 bare `pytest.raises(ValidationError)` in the half each validate a payload with a single
  failing cause, so none hides a second one today.

### Issues

#### Critical

None.

#### Important

1. **`test_a_literal_that_overflows_to_infinity_is_refused` passes on a different error and
   would stay green with the infinity refusal deleted** (`tests/test_hardening.py:541-548`,
   `'{"name": "X", "datatype": "float64", "conversion": {"factor": 1e400}}}]}}'`). The definition
   states neither `kind` nor `volatile`, so the discriminated union fails before any number is
   read, and the one assertion, `"schema" in checks(bag)`, is satisfied by that. Run on the
   test's own payload (`exp-inf/run.py`): the only finding is
   `definition: error[schema]: Unable to extract tag using discriminator 'kind'`; with `kind` and
   `volatile` added the finding becomes `definition.conversion.factor: error[schema]: Input
   should be a finite number (got: inf)`. Removing `allow_inf_nan=False` from `Real`
   (`src/ddd/models/common.py:112`) changes nothing this test sees. Fix: state `kind` and
   `volatile`, assert the `definition.conversion.factor` pointer and "finite number".
2. **The comparison-table guard cannot see a leaf's own fields, and `bits` is compared by
   nothing** (`tests/test_comparison_tables.py:137-149`,
   `for name in ResolvedObject.model_fields:`; the excuse at `:93-98` says so itself: "which
   this guard does not reach because it walks ResolvedObject.model_fields alone").
   `ResolvedLeaf` adds `path`, `instance`, `instance_id` and `bits` (`src/ddd/ir.py:437-488`);
   `bits` is in no table of `compare.py` and in no excuse, which is exactly the fail-open the
   file exists to prevent. Run (`exp-bits/run.py`): a member widened from 2 to 4 bits between
   two deliveries compares `[]`; narrowed from 4 to 2 it is `['narrowed-limits']` only ("limits
   tightened from [0, 15] to [0, 3]"); the two members of the structure swapped compares `[]`.
   The behaviour is pass 9 Important 2 and its open question; the test defect is that a guard
   documented as an allowlist watchdog leaves the four leaf fields unaccounted, so whichever
   way the question goes nothing fails until somebody decides. Fix: walk
   `ResolvedLeaf.model_fields` beside `ResolvedObject.model_fields` with an excuse dict for
   `path`, `instance` and `instance_id`; `bits` then fails until it is a table entry or an
   excuse with a reason.

#### Minor

1. **A dead alternative in an `or` assertion** (`tests/test_sections.py:232-234`,
   `assert checks(bag) == ["section-alignment", "unused-output"] or checks(bag) == [`). The
   declaration is `local`, so `unused-output` cannot fire (`analysis.py:2848`); the first
   alternative is unreachable and the assertion reads as two accepted outcomes. Fix: keep the
   second.
2. **A subprocess where the in-process test above it already proves the entry point**
   (`tests/test_edge_cases.py:471-482`, `subprocess.run([sys.executable, "-m", "ddd",
   "--version"], ...)`; 0.38 s, the second slowest test of the half). `:456-464` runs
   `runpy.run_module("ddd", run_name="__main__")` and asserts the exit status and the output;
   the subprocess adds only that the documented spelling resolves. Fix: keep one, or assert
   something only the subprocess can show (the exit code reaching the shell).
3. **Three tests assert nothing** (`tests/test_models.py:792` `test_sint8_is_a_byte_too`,
   `tests/test_edge_cases.py:466-469` `test_importing_the_entry_point_module_does_not_run_it`,
   `tests/test_sections.py:487-488` `test_a_name_with_a_dollar_or_a_dot_is_a_section_name`).
   Each proves survival only; the second's claim ("must stay silent") is observable through
   `capsys` and `SystemExit` and is not asserted. Fix: one assertion each.
4. **`test_every_check_is_registered` guards four literals, not the identifiers the analysis
   uses** (`tests/test_analysis.py:569-577`, `# Guards against a typo in a check identifier
   used by the analysis.`). Nothing in the suite walks the first argument of the 66 `bag.add(`
   calls in `src/ddd/analysis.py` (`grep -n` list in `scratchpad/pass-11a`), and an unregistered
   identifier is reported at `error` rather than refused (`diagnostics.py:449-451`). A typo is
   caught only where a test asserts that exact identifier. Fix: an `ast` walk over `src/ddd`
   collecting every string literal passed as the first argument of `.add(` and asserting
   membership in `CHECKS` (plugin identifiers, with `/`, excepted).
5. **Dead statements in tests** (`tests/test_hardening.py:529`, a `write_tree` overwritten on the
   next line; `:522`, `assert location.pointer` on a template that is not a diagnostic;
   `tests/test_sections.py:471`, `= None` followed by `del`; `tests/test_models.py:93-94`,
   re-imports of names the module already imports; `tests/test_compare.py:525, 600, 606, 632,
   654, 675`, `verdict(...)` computed twice per assertion). Fix: delete each.
6. **A core test file imports helpers from the LSP test module**
   (`tests/test_constants.py:1163`, `from test_lsp import build_record, framed, sent`). The
   constants tests depend on `tests/test_lsp.py` importing (its 4476 lines, its fixtures), and
   the three helpers are used by two files. Fix: move `build_record`, `framed` and `sent` to
   `tests/conftest.py`.
7. **Five spellings of one types-file builder** (`tests/test_structures.py:29-51` `val`, `struct`,
   `scalar`, `types`; `tests/test_types.py:31-51` `value`, `structure`, `scalar`;
   `tests/test_constants.py:44-57` `struct_type`, `value_member`; `tests/test_embedded.py:38-55`
   `scalar_type`, `struct_type`, `value_member`, `typed_member`; `tests/test_external.py:42-53`
   `val`, `struct`, `types`). Fix: one family in `conftest.py`, beside `declare`.
8. **Nine order pins depend on the schedule of the analysis; the rest do not**
   (`tests/test_analysis.py:772, 1303, 1434`, `tests/test_structures.py:538`,
   `tests/test_constants.py:465, 494`, `tests/test_compare.py:831, 872`, and the dead half of
   Minor 1). The half carries 329 `checks(bag) == [...]` pins (`test_analysis.py` 76,
   `test_structures.py` 69, `test_constants.py` 38, `test_compare.py` 33, `test_loading.py`
   26, `test_models.py` 20, `test_sections.py` 16, `test_edge_cases.py` 13, `test_rasters.py`
   13, `test_units.py` 10, `test_calibration.py` 8, `test_embedded.py` 6, `test_hardening.py`
   1), but only these nine list two different identifiers, and only those would break on a
   benign reordering of `_Analysis.run` (`analysis.py:743-776`) or of `compare`
   (`compare.py:342-383`): `local-conflict` before `unused-output` (`_select_producer` before
   `_build_variable`), `incomplete-project` before `consumer-storage` and `missing-producer`
   (`_collect_component` before ownership), `schema` before `type-cycle` (the nesting cap
   before the cycle walk), `unknown-type` before `duplicate-declaration`, `renamed-object`
   before `changed-interface`, `reused-name` before the removal and the addition. The previous
   review's "a few hundred" is therefore nine here. Fix: `sorted(checks(bag))` at the nine;
   the report order of `reused-name` is pinned separately and correctly through `bag.sorted`
   (`tests/test_compare.py:1189-1203`).
9. **A redundant pragma, and a collection-only run that reports a coverage failure**
   (`src/ddd/identity.py:32`, `if TYPE_CHECKING:  # pragma: no cover`, already excluded by
   `pyproject.toml:115`; `python -m pytest --co` prints `FAIL Required test coverage of 100%
   not reached. Total coverage: 29.11%` and exits 0, because `--cov --cov-fail-under=100` sit
   in `addopts`, `pyproject.toml:102`). Fix: drop the pragma; document `--co --no-cov` under
   "Running the checks", or move the fail-under into CI.
10. **Two performance tests bound nothing** (`tests/test_structures.py:554-579`, "Nothing about
    the time is asserted here"; `tests/test_sections.py:334-360`, "what this test watches is the
    clock"). Both would pass, minutes late, if the walk they guard went exponential again; the
    suite would become unusable rather than red. A wall-clock bound of ten seconds is not
    flaky on any machine that runs the suite in two and a half minutes. Fix: `time.perf_counter()`
    around the run with a generous bound, or leave as is and record the durations in CI.
11. **`DERIVED_AS` claims the extractor reads the field, and only one entry is executed**
    (`tests/test_comparison_tables.py:41-58`, "The value extractor of that table entry has to
    actually read this field - which is what makes the mapping a claim rather than a comment";
    `:151-162` checks names only, `:276-285` evaluates the `shape` extractor once). A `shape`
    entry that stopped reading `dimensions`, or an `a2l format` entry that stopped reading
    `a2l`, would pass. Fix: for each mapping, build two objects differing only in that field and
    assert the target entry's `value` differs.

### Status of the 2026-09-08 findings in this area

The previous review's core test review (`previous-review.md:1674-1686`):

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| P7 test review 1 | `missing-id` silenced by `conftest`; `missing-producer` and `unknown-constant` relaxed in two files | consciously left, documented | `tests/conftest.py:92-99`, `tests/test_structures.py:1282`, `tests/test_constants.py:400, 427, 443` |
| P7 test review 2 | `test_edge_cases.py:307-338` pin the dangling-reference behaviour and need rewriting | fixed | `tests/test_edge_cases.py:306-338` assert the drop |
| P7 test review 3 | `TestQuotedNumbers` covers three of nine fields; the other six accept quoted values | consciously left (strict mode deferred) | `tests/test_models.py:397-420` |
| P7 test review 4 | no dropped producer with a surviving consumer, or the reverse | fixed | `tests/test_analysis.py:713-733, 944-966` |
| P7 test review 5 | deep JSON tested for the loader only; `_pointer_order` for ASCII only | fixed | `tests/test_hardening.py:569-616, 618-633, 1025-1031`; `Document` in `tests/test_lsp.py` (part B) |
| P7 test review 6 | nothing states what `1.0` does on an integer | still open, carried over (gap 16) | `tests/test_analysis.py:176` still uses `1.5`; today `init-invalid` "written as a fractional number" (`exp-gaps/out.txt`) |
| P7 test review 7 | ~170 message pins, mostly of the load-bearing phrase | unchanged; 292 in the half now, same character | counts per file in Minor 8's list |
| P7 test review 8 | ~220 `checks(bag) == [...]` pins would fail "a few hundred tests" on a benign reordering | re-assessed: nine pins depend on the schedule | Minor 8 |
| P7 test review 9 | the OS-failure monkeypatches assert on the finding, not the mock | unchanged, right | `tests/test_hardening.py:960-1010` |
| P7 test review 10 | loader OS-level cases producible without mocking untested | partly fixed: NUL byte and a directory as root; `..`/`**` patterns, case-variant spellings still open (gaps 9, 11) | `tests/test_hardening.py:950-958`, `tests/test_edge_cases.py:126-136` |

### Open questions

1. Is a bitfield width or a member order change between two deliveries a `changed-interface`
   (pass 9 Important 2, its question 1)? The answer decides whether the leaf guard of
   Important 2 excuses `bits` with a reason or fails until `compare._INTERFACE_FIELDS` carries
   it; the guard should be written either way.
2. Which pass owns `tests/test_external.py` (44 tests)? Neither part A's nor part B's list names
   it, and it is the only cover of the external-type branches of `analysis.py:1030, 1154, 1161,
   1203-1205, 1589, 2035-2043`, `models/types.py:420-439` and `ir.py:304-310`. If nobody reads
   it, those branches ship reviewed by their coverage alone.
3. Does the maintainer want a wall-clock bound on the two performance tests (Minor 10)? Their
   docstrings decline one on flakiness grounds; the alternative is a durations check in CI.

### Test gaps

Scenarios no test in the half pins, found in this pass (the consolidated list below carries
these together with the earlier passes' items):

- `tests/test_compare.py`: a `volatile` flip between deliveries is `changed-storage` with
  `volatile: true != false` (only the table membership is pinned,
  `tests/test_comparison_tables.py:231`); `changed-owner` when either side has no owner
  ("nobody", `compare.py:600-606`); the message texts of `added-object` (kind, owner),
  `project-mismatch` and `reused-name`, and the readers suffix of `renamed-object`
  (`compare.py:344-350, 365-371, 378-383`); a delivery restating exactly the derived limits
  compares clean.
- `tests/test_analysis.py`: `condition-mismatch` message and its location (the `condition` key,
  or the declaration when the other side states none, `analysis.py:3192-3200`);
  declaration-form `local-conflict` message and note (`:2530-2536`, `:60-64` asserts the
  identifier only); `enum-duplicate-value` message (`:2456-2460`); the locations of
  `unused-output`, `multiple-producers` and its note, `missing-producer`, `empty-component`,
  `storage-mismatch`, `name-similar` and its note, `a2l-unrepresentable`, and the own pointer
  of `unknown-reference` and `reference-kind` (`definition.axis`, `:2708`; only the
  `incomplete-project` that follows a silenced one pins the key).
- `tests/test_models.py`: `raw_reading` rounding to twelve significant digits and the enum
  lookup (`models/conversion.py:304-309`), reached in the half by nothing and in the suite
  only through a hover (`tests/test_lsp.py:1591-1601`).
- `tests/test_loading.py`: the `include-cycle` message chain (`loading.py:1023-1024`); the
  `duplicate-component` note (`:646-651`); the `file-not-found` message of a missing include
  ("does not exist", pinned only through the CLI at `tests/test_compare.py:422-424`); a
  directory named by an include entry (root only, `tests/test_edge_cases.py:126-136`); a byte
  order mark on an included file (root only, `tests/test_hardening.py:556-561`).
- `tests/test_sections.py`, `tests/test_rasters.py`: the locations of `section-access`,
  `section-alignment`, `unknown-raster` (both sites), `raster-kind` and the five
  `consumer-*` pointers (`definition.<key>`, `analysis.py:2277-2284`).
- `tests/test_structures.py`: the location of `type-kind` (`definition`) and its note
  (`analysis.py:2158-2164`).

Pinned dimensions per check, from reading every test of the half against every `bag.add` site
(trigger / location / message; the loader's mapping and the models' validators are pinned on
all three except where listed):

| check | trigger | location | message |
| --- | --- | --- | --- |
| `unknown-unit`, `unknown-section`, `unknown-constant`, `dimension-value`, `unknown-type`, `type-cycle`, `include-depth`, `duplicate-id`, `incomplete-project`, `definition-mismatch`, `enum-conflict`, the seven `schema` sites of the analysis, reference-form `local-conflict` | yes | yes | yes |
| `init-invalid` (8 sites) | yes | yes for shape, string and typed init | yes |
| `reserved-identifier` (8 sites) | yes | member, constant, project only | type, member, project, enum sites |
| `name-collision` (9 sites) | yes | no | six of nine |
| `limits-out-of-range` | yes | scalar type only | yes |
| `section-access`, `section-alignment`, `unknown-raster`, `raster-kind`, `consumer-storage`, `consumer-raster`, `consumer-identity`, `storage-mismatch`, `a2l-unrepresentable`, `type-kind`, `name-similar`, `duplicate-declaration` | yes | no | yes |
| `multiple-producers` | yes | no | fragment |
| `duplicate-event` | yes | note only | yes |
| `empty-component`, `unused-output`, `missing-producer`, `enum-duplicate-value`, `condition-mismatch`, declaration-form `local-conflict`, `missing-id`, `include-cycle`, `duplicate-component` | yes | no | no |
| `unknown-reference`, `reference-kind` | yes | no | yes |
| `renamed-object`, `removed-object`, `removed-unused-object`, `changed-interface`, `changed-storage`, `narrowed-limits`, `changed-condition`, `changed-a2l` | yes | n/a (the CLI's, part B) | yes |
| `changed-owner` | yes | n/a | one direction |
| `added-object`, `project-mismatch`, `reused-name` | yes | n/a | no (note text yes for `reused-name`) |
| `missing-plugin`, `address-missing`, `unknown-extension`, `consumer-extension`, `plugin-*` | part B | | |

### Consolidated test gaps (core and formats)

Passes 1, 2, 3, 4, 8 and 9, the previous review's core items and this pass, merged per file,
deduplicated, each grepped for an existing test. Dropped as already pinned: numeric or other
strings inside a list init (pass 2, pass 8) - `tests/test_hardening.py:1035-1055`, a text
element of a nested init is `schema` and `InitElement` refuses every `str`
(`models/objects.py:36-42`); a dropped producer beside a surviving consumer (previous review) -
`tests/test_analysis.py:713-733, 944-966`; deep JSON at the dictionary reader and
`_holds_a_description`, and a non-ASCII pointer key (previous review) -
`tests/test_hardening.py:569-633, 1025-1031`; one finding for an enumerator past both bounds on
a declaration (pass 9 Minor 3, half of it) - `tests/test_analysis.py:442-453`. Items that belong
to `tests/test_cli.py`, `tests/test_lsp.py`, the backends and the documentation guards are
part B's and are not repeated here.

`tests/test_models.py`

1. Quoted and JSON-boolean spellings per field (`"volatile": "no"`, `"export": 0`,
   `"limits": {"min": "0"}`, `"factor": "0.5"`, `"bits": true`): pins the deferred strictness
   decision either way (pass 2 Important 2, previous review).
2. `Identifier` at 128 accepted and 129 refused, on an object name, a constant name and an
   `axis`/`input`/`typename` (pass 2; `models/common.py:44-55`).
3. `"dimensions": []` on a measurement read as the scalar (pass 2, `SPEC.md:410`).
4. A `condition` ending in a backslash (pass 8 Minor 1); an `a2l.format` with non-ASCII digits
   (pass 8 Minor 3).
5. `raw_reading`: twelve significant digits and the enum name lookup, directly (this pass).
6. `duplicate-id` reported on the second in name order when the load order differs (pass 3;
   `:360-371` loads in name order).
7. A definition or component `raster` of `""` or with whitespace (pass 2 Minor 8;
   `tests/test_rasters.py:62` covers the file's entry only).

`tests/test_loading.py`

8. A byte order mark on an included file (pass 2; root only at `tests/test_hardening.py:556`).
9. A literal `..` entry, a character class `[ab]?`, a dot-prefixed file, two case spellings of
   one file loaded once on Windows, a match set created out of sort order, symlink identity
   (pass 2, previous review).
10. An include entry naming an existing file whose path contains a glob character (pass 10
    Important 1, whichever side takes it).
11. A directory named by an include entry (previous review; root only at
    `tests/test_edge_cases.py:126`).
12. The `include-cycle` message chain; the `duplicate-component` note; the `file-not-found`
    message of a missing include (this pass).
13. A hyphenated extension key inside a definition keeps its key in the pointer; two malformed
    blocks in one definition are two findings (pass 8 Important 2 and 3; `:434-448` is the
    project level).
14. A `null` or text inside a 2-D init yields one `schema` finding at the innermost pointer -
    the count (pass 2 Important 3; `tests/test_hardening.py:1035` pins the pointer shape only).
15. A wildcard include whose matches differ only in case class, ordered the same on every
    platform (pass 1 Important 4, once its question is decided).

`tests/test_analysis.py`

16. `1.0` on an integer datatype: today `init-invalid` "written as a fractional number"
    (previous review, pass 9; carried over).
17. A stated limit inside the 1e-9 band: `{"min": 0, "max": 255.0000001}` on `uint8` is
    accepted in silence (`exp-gaps/out.txt`; `analysis.py:3284-3289`) (previous review, pass 9
    Important 1).
18. Three producers give two `multiple-producers` (`exp-gaps/out.txt`: two, plus
    `unused-output`) (pass 3).
19. `consumer-raster` and `raster-kind` both on one declaration (`exp-gaps/out.txt`: both
    fire) (pass 3, `SPEC.md:1042`).
20. An axis whose `input` names a structured instance is `reference-kind`, and the a2l names no
    such measurement (pass 3 Important 1, pass 4).
21. A reported `reference-kind` beside a silenced transitive absence yields no
    `incomplete-project` (pass 3 Minor 1).
22. `duplicate-id` between a dropped and a surviving declaration (pass 3 Minor 2).
23. A text init on a dropped non-string declaration (pass 3 Minor 3).
24. The pointer of the enumerator `init-invalid` on a declaration (pass 3 Minor 4; `:431-440`
    pins the message).
25. A `typename` producer against an equivalent inline consumer checks clean (pass 3;
    `tests/test_structures.py:1245-1257` names types on both sides).
26. A table of N bad elements: today one finding per element (`exp-gaps/out.txt`: three for
    three) - pin the count or a bound (pass 9 Important 3).
27. The bitfield phrase and the single finding past both bounds on a member (pass 9 Minor 3).
28. `[[1], [2]]` on `[2]`: today "init is a list but the object is a scalar"
    (`exp-gaps/out.txt`) - pin, or reword and pin (pass 9 Minor 4).
29. The enum note's location under a documented second copy (pass 9 Minor 6; `:332-341` pins
    the note text).
30. The spelling of a derived limit under a decimal factor, `7.65` not `7.6499999999999995`
    (pass 4).
31. The messages and locations listed under "Test gaps" above: `condition-mismatch`,
    declaration-form `local-conflict`, `enum-duplicate-value`, `unused-output`,
    `multiple-producers`, `missing-producer`, `empty-component`, `storage-mismatch`,
    `name-similar`, `a2l-unrepresentable`, `unknown-reference`, `reference-kind` (this pass).

`tests/test_structures.py`

32. A cyclic structure reaching (or not) the dump's `types` (pass 9 Minor 1;
    `analysis.py:424-463` leaves a cycle out).
33. A `ResolvedMember` without storage refused (pass 9 Minor 2; `ir.py:304-310`, uncovered by
    the half).
34. The element order of an instance `[12]`: `[10]` after `[2]` (pass 9 Minor 7;
    `analysis.py:411-421`).
35. The location and note of `type-kind` (this pass).

`tests/test_constants.py`

36. `2.50` and `1e3` constants through the generated header, pinning the normalisation
    (pass 2 Minor 4).

`tests/test_rasters.py`, `tests/test_sections.py`

37. A raster name of eight non-ASCII characters (pass 8 Minor 16).
38. The locations of `unknown-raster` (both sites), `raster-kind`, `section-access`,
    `section-alignment` and the `consumer-*` pointers (this pass).

`tests/test_compare.py`

39. A scalar init against its broadcast list, and a byte list against its text on a string
    (pass 3 Important 2, its question 1; `_STORAGE_FIELDS` compares `init` raw,
    `compare.py:182`).
40. A baseline whose `format` is `"9"` or `9.0` (pass 3 Minor 7; `tests/test_hardening.py:872-893`
    has `"two"` and `true`).
41. A reordered structure and a changed `bits`: today `[]` and `narrowed-limits`
    (`exp-bits/run.py`) (pass 9 Important 2; with Important 2 above).
42. A changed init of a large block reported in a bounded message (pass 9 Minor 5).
43. The `--renames` id of an array-of-structures member: `k7m2q9xr4t8w[0].a`
    (`exp-bits/run.py`; `TestRenamesOfStructuredVariables` pins `abcdefghjkmn.x` for a scalar
    instance) (pass 1 Important 1).
44. A `volatile` flip is `changed-storage`; `changed-owner` with "nobody"; the `added-object`,
    `project-mismatch` and `reused-name` messages; the readers suffix of `renamed-object`;
    restated derived limits compare clean (this pass).
45. A performance guard for a rename sweep without ids, or the bound of pass 9's question 3
    pinned (pass 9 Important 4).
46. `-W x=error` reaching a description baseline (pass 3; CLI side, shared with part B).

`tests/test_comparison_tables.py`

47. A guard over `ResolvedLeaf.model_fields` (pass 9 Important 2; Important 2 here).
48. Each `DERIVED_AS` mapping executed, not only named (Minor 11 here).

`tests/test_hardening.py`

49. The 1e400 literal refused for its own reason (Important 1 here).
50. A duplicate key and a `format` of `0` in a dump (pass 8 Minor 7; `:872-893` peeks at a
    higher version only).
51. `size_t` and `NULL` reserved, if pass 8 Minor 2 is adopted (`:171` covers `<stdint.h>`'s
    own names).
52. A document nested 600 levels through `ddd id --assign` and `Document(text)` (pass 8
    Important 1; `:587-599` pins 100 000 levels; shared with part B).

`tests/test_edge_cases.py`

53. `test_importing_the_entry_point_module_does_not_run_it` asserting the observable silence
    (Minor 3 here).

### Assessment

The core half of the suite is sound where it counts: it is order independent, it writes nowhere
it should not, it silences one check on purpose and says so, and its assertions are on
behaviour - identifiers, phrases, pointers, generated text, round trips - rather than on mocks
or on whole documents. The fix plans' promised tests all exist and pin what the plans say, and
the coverage gate is honest for this half: the eight core statements it does not reach are the
external-type branches, which a file neither part of this pass owns covers. Two tests would
pass with their feature broken: the infinity refusal is asserted on a payload that fails for a
different reason, and the comparison-table guard cannot see the four fields a leaf adds, so
`bits` is compared by nothing and the guard does not know it. The rest is hygiene: a dead
`or` alternative, a redundant subprocess, three assertion-free tests, a guard that overclaims,
helpers spelled five times, and nine order pins - not a few hundred - that depend on the
analysis schedule. The consolidated list above is 53 gaps, most of them the unpinned location
of a finding, which is the dimension the half pins least and the one an editor relies on.

### Verification

Every candidate of this pass was handed to a second reviewer (group E): 13 confirmed, 0 plausible, 0 refuted. The severity column is the verifier's grade; where it differs from the finder's, the notes say why.

| id | finder | verdict | severity | proof |
| --- | --- | --- | --- | --- |
| P11A-I1 | Important | CONFIRMED | Important | finder's probe rerun: the test's payload -> only `error[schema]: Unable to extract tag using discriminator 'kind'`; with `kind`/`volatile` -> `definition.conversion.factor: error[schema]: Input should be a finite number (got: inf)`; on a copy of `src` with `Real = Annotated[float, Field()]` the test still passes (a probe plugin printed the copy's path) while the complete payload loads with `factor=inf` |
| P11A-I2 | Important | CONFIRMED | Important | `test_comparison_tables.py:139` `for name in ResolvedObject.model_fields:`; `ResolvedLeaf` adds `bits`, `instance`, `instance_id`, `path` (computed); `grep bits src/ddd/compare.py` -> nothing; probe rerun: 2->4 bits `[]`, 4->2 `['narrowed-limits']` only, members reordered `[]` |
| P11A-M1 | Minor | CONFIRMED | Minor | `test_sections.py:228` `declare("local", ...)`; `analysis.py:2848` `producer.scope is Scope.OUTPUT`; the tree replicated: `checks(bag) = ['section-alignment']`, the first alternative never holds |
| P11A-M2 | Minor | CONFIRMED | Minor | `test_edge_cases.py:461-464` asserts the exit status and the output in-process; `:473-481` asserts only `result.stdout.startswith("ddd ")`; finder's durations: `0.38s call ... test_the_module_entry_point_runs_as_documented` |
| P11A-M3 | Minor | CONFIRMED | Minor | `test_models.py:792-793`, `test_edge_cases.py:466-469`, `test_sections.py:487-488` hold no `assert`; the three ran PASSED |
| P11A-M4 | Minor | CONFIRMED | Minor | `test_analysis.py:571-576` four literals; 69 `bag.add(` sites in `analysis.py`; `diagnostics.py:451-452` `if info is None: severity = Severity.ERROR` |
| P11A-M5 | Minor | CONFIRMED | Minor | `test_hardening.py:529` `write_tree(...)` overwritten by `:530`; `:514` template, `:522` `assert location.pointer` on a constant; `test_sections.py:471-472` `= None` then `del`; `test_models.py:93-94` re-imports of `:8-9`; `test_compare.py:525,600,606,632,654,675` `verdict(before, after)` twice |
| P11A-M6 | Minor | CONFIRMED | Minor | `test_constants.py:1163`, `:1208` and `test_external.py:516` `from test_lsp import ...`; the helpers are defined at `test_lsp.py:45,71,80` |
| P11A-M7 | Minor | CONFIRMED | Minor | `test_structures.py:29-51` `val/struct/scalar/types`, `test_types.py:31-51` `value/bits/structure/scalar`, `test_constants.py:44-50` `struct_type/value_member`, `test_embedded.py:38-51` `scalar_type/struct_type/value_member/typed_member`, `test_external.py:42-54` `val/struct/types` |
| P11A-M8 | Minor | CONFIRMED | Minor | scanned the 15 files: 319 `checks(...) == [...]` pins, 10 with two or more distinct identifiers - the finder's nine plus `test_compare.py:514` (`renamed-object` x2 then `reused-name` x2, the `compare.py:342-371` order) |
| P11A-M9 | Minor | CONFIRMED | Minor | `identity.py:32` `if TYPE_CHECKING:  # pragma: no cover` beside `pyproject.toml:115` `'if TYPE_CHECKING:'`; `python -m pytest --co -q` printed `FAIL Required test coverage of 100% not reached. Total coverage: 29.11%` and exited 0 |
| P11A-M10 | Minor | CONFIRMED | Minor | `test_structures.py:561-562` "Nothing about the time is asserted here", `test_sections.py:341-342` "what this test watches is the clock"; neither reads a clock |
| P11A-M11 | Minor | CONFIRMED | Minor | `test_comparison_tables.py:42-43` "The value extractor of that table entry has to actually read this field"; `:160-162` asserts names only; `:281-285` evaluates the `shape` extractor once, on a curve |

## Pass 11b: the test suite, part B (cli, lsp, plugins, backends, generation, a2l, external, cmake, documentation, transcripts)

### Scope covered

Read in full, with line numbers: `tests/conftest.py` (again), `tests/test_cli.py` (2617 lines),
`tests/test_lsp.py` (4476), `tests/test_plugins.py` (2283), `tests/test_backends.py`,
`tests/test_generation.py`, `tests/test_a2l.py`, `tests/test_example_plugin.py`,
`tests/test_external.py` (the file neither half's list named), `tests/test_cmake.py`,
`tests/test_documentation.py` (1672), `tests/test_transcripts.py`,
`editors/vscode/src/config.test.ts`, `launch.test.ts`, `config.ts`, `extension.ts` - 1391 of the
2285 collected tests (61 %). To judge what they pin: `src/ddd/cli.py` in full, `src/ddd/plugins.py`
in full, `src/ddd/backends/base.py` in full, `src/ddd/lsp/server.py` in full, `lsp/discovery.py`,
`build_info.py`; `.github/workflows/ci.yml`; `editors/vscode/package.json` (scripts);
`pyproject.toml:98-116`; `docs/developer_documentation.rst`; the four fix plans the task names;
`reports/pass-11a.md` in full and its outputs; the "Test gaps" of passes 4, 5, 6, 7 and 10; the
previous review's periphery test review at `previous-review.md:1822-1834`, and pass 6's
Important 1 (`reports/pass-6.md:95-106, 257-260`).

Ran (outputs under `scratchpad/pass-11b/`; nothing in the repository was edited - `git status
--short --ignored examples tests` afterwards lists only `__pycache__`):

- Every file of the half alone, `-o addopts= -p no:cacheprovider` (`alone-*.txt`): all pass;
  `test_lsp.py` carries only the known symlink failure. Times: cli 3.6 s, lsp 3.5, plugins 3.7,
  backends 0.6, generation 1.9, a2l 2.1, example_plugin 0.5, external 0.9, cmake 50.4 (73 s in
  pass 5's run), documentation 4.8, transcripts 5.9: 78 s for the half alone.
- The ten files without `test_cmake.py` in one run under `--cov=ddd --cov-branch
  --cov-report=term-missing --durations=30`, the data file redirected into the scratch directory
  (`half-coverage-periphery.txt`): 1373 passed plus the known failure in 42.8 s.
- Two experiments on a copy of `src/` imported through `-o pythonpath=<copy>` (verified with a
  probe test that the copy is what pytest imports, `exp-nopublish/test_which.py`): `refresh`
  without its `_publish` loop (`exp-nopublish/`), and `serve()` dropping its build directories
  with `_builds_now` calling `discover(root)` (`exp-nob/`, with an unpatched control copy).
- `exp-empty/`: what pytest does with an empty parameter set. `transcripts_map.py`: every `$ ddd`
  command of every page with the mode the harness gives it. `ddd check examples/demo/demo.ddd.json`
  with and without `--strict`. A grep of the four plans for the tests they name against `tests/`.

### Strengths

- The half is order independent: each file passes alone, and the classes touching process state
  restore it - `monkeypatch.chdir` at twelve sites, `syspath_prepend` with the module popped from
  `sys.modules` in a `finally` (`tests/test_plugins.py:202-329`), `setitem(sys.modules, ...)`
  (`:355-364`), `sys.stdin`/`sys.stdout` replaced through `monkeypatch`
  (`tests/test_lsp.py:3601-3613`, `tests/test_plugins.py:2154-2210`). `main()`'s stream reconfiguration is harmless on every
  replacement: `_write_utf8` reads `getattr(stream, "reconfigure", None)` (`src/ddd/cli.py:103`).
  Plugin modules are cached under a digest of their resolved path (`src/ddd/plugins.py:200-201`),
  so a `tag_plugin.py` under one `tmp_path` never answers for another.
- Nothing writes into the repository. The transcripts copy `examples/` into `tmp_path`
  (`tests/test_transcripts.py:415`) and chdir there (`:292`); `id --assign` runs on `tree` copies
  (`tests/test_cli.py:2299-2581`); the cmake tests configure the shipped example out of source
  into `tmp_path` (`tests/test_cmake.py:113`).
- The server harness is in-process and deterministic: `Server(BytesIO, BytesIO, root).run()` - no
  pipes, no sleeps, no polling, no timeouts; a server crash is a Python exception in the test, a
  corrupt frame is a return code (`tests/test_lsp.py:3548-3560`). The two mtime tests stamp a
  sentinel ten seconds in the past rather than reading the clock (`tests/test_cli.py:322-327`,
  `tests/test_generation.py:242-247`). No test needs the network; the shell (`bash`) and the
  build tools are asserted present rather than skipped over (`tests/test_transcripts.py:311-312`,
  `tests/test_cmake.py:487-490`).
- The buffer store the previous review found untested is tested: eight server tests send a
  `didOpen` or `didChange` text that differs from the disk (`tests/test_lsp.py:3615, 3688, 3754,
  3817, 3881, 3959, 4128, 4193`), and the rename edits are keyed by the exact uri string the
  client sent (`:3679-3686`, `:4082`).
- The four plans' promised periphery tests exist and pin what the plans say: the six of
  `2026-09-08-cli-reports-before-writing.md` (`tests/test_cli.py:1689-1956`), the buffer,
  version and trust tests of `2026-09-08-lsp-windows-uris-buffers-trust.md` (`tests/test_lsp.py:172,
  2856, 3615, 3688, 4019, 4257`; `tests/test_documentation.py:769-799`), every task of
  `2026-09-09-plugin-boundary.md` (`tests/test_plugins.py:225-242, 455-479, 637-652, 1261-1333,
  1644-1794, 1796-1866`; `tests/test_cli.py:537-561, 1772-1794`; `tests/test_generation.py:263-340`)
  and tasks 1-2 of `2026-09-09-listing-commands.md` (`tests/test_cli.py:1273-1370, 1433-1465`).
  Two deviations are pinned deliberately and say why: a drifted buffer refuses the whole rename
  rather than being skipped (`tests/test_lsp.py:3817-3958`, the plan's `:434-471`), and the
  staging suffix is `.ddd-staging` rather than the plan's `.tmp`
  (`tests/test_generation.py:263-275`).
- The documentation guards that count things have positive controls where a regex could go
  quiet: `assert counts` (`tests/test_documentation.py:174`), `len(enumerations) == 1` (`:188`),
  `assert row is not None` (`:254`), `assert listed is not None` (`:315, 320, 330, 337, 1484`),
  `assert conversions` (`:912`), `assert bound` (`:1427`); the committed schemas are compared
  byte for byte with `schema_text` (`:1389-1398`) and the transcripts re-run 81 documented
  commands through the tool itself.
- Coverage is honest for the half: with the ten periphery files alone `plugins.py`, `build_info.py`
  and `discovery.py` are at 100 %, `cli.py` at 99 % (the misses are `compare --format json` on
  success `:667->674`, a baseline that does not resolve `:601->611` and `cmake-dir` without the
  module `:1168-1169`, all reached by the core half), `lsp/server.py` at 99 % (the constant hover
  `:470-475`, pinned from `tests/test_constants.py`), `backends/base.py` at 99 % (`:272`, a
  template without a trailing newline). Every guard of `plugins.py` has the test that fires it
  (the list is in the gap table below), every write status and failure of `base.py` has one
  (`tests/test_generation.py:227-376`), and every request handler of `server.py` is reached
  through the protocol.

### Issues

#### Critical

None.

#### Important

1. **The server tests compare published and answered uris by file name or resolved path, so the
   server publishing under its own spelling - the defect pass 6 confirmed live - keeps every test
   green** (`tests/test_lsp.py:65`, `uri_to_path(message["params"]["uri"]).name:
   message["params"]["diagnostics"]`; `:2905-2909`, `uri_to_path(m["params"]["uri"]).resolve()
   ... == [path.resolve()]`). Trigger: a client opens `file:///c%3A/...` (VS Code on Windows), a
   junction, a `subst` drive or a case variant; the server publishes `path.as_uri()`
   (`src/ddd/lsp/server.py:625`) and answers edits under it (pass 6 Important 1, observed with
   `p7_subst_live.txt`). Outcome: the seven `published()` call sites (`:2903, 3048, 3054, 3068,
   3104, 3140, 3147`) and the answer checks at `:3208, 3222, 3319, 3416, 3512, 2005, 1936, 2383`
   cannot fail on it; the one test sending the client's spelling resolves both sides before
   comparing, and on posix its `re.sub` (`:2876-2878`) finds no drive, so the CI ubuntu cells
   never send `%3A` at the server level at all. Fix: key `published()` by the uri string; in
   `:2856` assert the publication for the opened file carries `spelled` (with pass 6's fix); compare
   the `changes` keys at `:3319` and `:3416` as strings, as `:3679-3686` and `:4082` already do.
2. **`-b` is accepted by two tests and used by none: a server that drops its build directories
   passes the suite** (`tests/test_lsp.py:3613`, `assert main(["lsp", "-b", str(tmp_path)]) ==
   EXIT_OK` on an empty stdin, so the loop returns before anything is discovered;
   `editors/vscode/src/launch.test.ts:49-54` sends `initialize` and `exit`). Trigger: `serve()`
   (`src/ddd/lsp/server.py:640`) or `_builds_now` (`:325`) losing the argument in a refactor.
   Outcome: the extension's only setting, `ddd.buildDirectories`, stops reaching discovery and
   nothing fails - `Server(..., build_directories=...)` is constructed by no test, and the only
   pin is `build_files(tmp_path, [elsewhere])` at the function level (`:309-313`). Evidence: a copy
   of the package with `serve()` passing `build_directories=()` and `_builds_now` calling
   `discover(root)` passes `test_lsp.py`, `test_cli.py`, `test_plugins.py`, `test_external.py` and
   `test_constants.py` (736 passed; the four failures are the copy's missing `cmake/` and
   `examples/`, identical on the unpatched control - `exp-nob/failures.txt`). Fix: a `TestServer`
   test with a record under `tmp_path / "elsewhere"` and no `build/`, opening a component through
   `Server(..., root=tmp_path, build_directories=[elsewhere])` and asserting the project's
   findings are published; and `main(["lsp", "-b", ...])` fed a framed `didOpen` instead of an
   empty stream.

#### Minor

1. **`test_strict_promotes_warnings` proves nothing about `--strict`** (`tests/test_cli.py:128-130`,
   `assert main(["check", str(DEMO), "--strict"]) == EXIT_OK`). The demo's bag is empty -
   `ddd check examples/demo/demo.ddd.json` prints `ok: 23 variables in 4 components are
   consistent` with and without the flag - so the test passes with the promotion deleted; the
   promotion is pinned only through `address-missing` under `generate` (`:859-875`) and a plugin
   check (`tests/test_plugins.py:1197`), never for a warning of the analysis under `check`. Fix: a
   fixture carrying `unused-output`, `--strict` -> `EXIT_FINDINGS`.
2. **`test_saving_refreshes_as_opening_does` asserts that something was sent**
   (`tests/test_lsp.py:3154`, `assert sent(writer)`). The `window/logMessage` `_announce` writes
   satisfies it: with the `_publish` loop removed from `refresh` the test passes while `:3032`,
   `:3063` and `:3123` fail (`exp-nopublish/`). The dispatch is pinned, the publication on save is
   not. Fix: `assert published(writer)["component_b.ddd.json"]`.
3. **Three uri tests silently prove less on posix** (`tests/test_lsp.py:185`, `if os.name ==
   "nt":`; `:196` and `:203`, the expected value is `server_module.url2pathname(...)` - the
   function under test's own fallback, so on posix both spellings decode alike and nothing is
   pinned; `:2876`, no drive to respell). Fix: assert the decoded posix form
   (`decoded.as_posix().lower().endswith("c:/git/x/a.ddd.json")`), which holds on both platforms.
4. **Five documentation guards pass vacuously when their regex or walker matches nothing**
   (`tests/test_documentation.py:232`, `for word in counted:`; `:245`; `:488` and `:507` over
   `spec_links()`; `:746` over `read`; `:967` over `enumerations_in(...)`). Each phrase exists
   today - nine pages count the fixed checks, one counts the description kinds, the SPEC has
   internal links - and a rewording of any of them turns the guard off without a red test, which
   is how `:222` says the first one went stale. Fix: `assert counted`, `assert spec_links()`,
   `assert read`, `assert enumerations` at module level, or a floor.
5. **The transcript suite degrades to two skipped tests, not two failures, if nothing is found**
   (`tests/test_transcripts.py:389-393` and `:406-410`, parametrized over `SHOWN` and `RUNS`
   computed at import). pytest marks an empty parameter set as a skip ("got empty parameter set",
   `exp-empty/`), so a drift of `SHELL` (`:68`) or of the pages' prompt spelling silences the
   strongest documentation guard, and the "nothing skips" convention has no guard (pass 7). Fix:
   `assert SHOWN and any(RUNS.values())` beside `RUNS` at `:373`.
6. **`test_the_command_list_is_what_the_spec_promises` reads no SPEC, and commands are checked
   in the README only** (`tests/test_documentation.py:264-280`, a literal set; `:260-262`, README
   only) while `docs/developer_documentation.rst:274-276` says "every command ... is named in
   `README.md` and in `SPEC.md`". All fourteen are in the SPEC today. Fix: parametrize
   `commands()` against `SPEC` as `TestConcepts` does, and rename the set test for what it is - a
   change detector on the parser.
7. **A stale docstring and a no-op line** (`tests/test_cli.py:2393-2394`, "`write_tree` writes
   through a text-mode file handle with no explicit `newline`"): `tests/conftest.py:79` passes
   `newline=""`, so the fixture never carries crlf and the replace at `:2401` does nothing. Fix:
   drop the sentence and the replace.
8. **A test asserting on a spy's keyword argument rather than on the bytes**
   (`tests/test_cli.py:2547-2559`, `monkeypatch.setattr(Path, "write_text", spy)` ...
   `assert written["renames.json"] == ""`). Fix: `assert b"\r\n" not in renames.read_bytes()`,
   which is real on Windows and needs no mock.
9. **Nine copies of one fixture** (`tests/test_plugins.py:1625-1866`: each test of `TestGenerate`
   re-spells `write_plugin(tree / "tools", source=...)`, the same `write_tree` and the same
   `arguments`, differing only in the plugin source and the expected line). Fix: a helper
   `generated(tree, source, *extra) -> tuple[int, str]`.
10. **`test_a_project_with_errors_generates_nothing` asserts the exit code only**
    (`tests/test_plugins.py:2062-2066`, `assert main(arguments) == EXIT_FINDINGS`). Fix:
    `assert not (tree / "out").exists()`, as `tests/test_cli.py:391-397` does for the built-ins.
11. **A redundant pragma** (`src/ddd/cli.py:104`, `if reconfigure is not None:  # pragma: no
    branch - absent only on a replaced stream`): `tests/test_lsp.py:3606-3613` replaces
    `sys.stdout` with a `Stream` holding only `.buffer` and calls `main(["lsp", ...])`, so the
    branch the pragma excludes is executed by the suite. Fix: drop it (11a Minor 9's twin).
12. **A second import of helpers from the LSP test module** (`tests/test_external.py:516`, `from
    test_lsp import build_record, framed, sent`; 11a Minor 6 found `tests/test_constants.py:1163`).
    Fix: the three helpers in `conftest.py`.
13. **The tools check names no C compiler** (`tests/test_cmake.py:487-490` parametrizes `CMAKE`,
    `NINJA` and `DDD`; `compiler()` at `:42-46` picks `gcc` when `cl` is absent and otherwise
    leaves it to cmake). On a machine with neither, the first `configure()` fails inside its
    assertion with cmake's whole output rather than the one line `:488-489` promises. Fix: assert
    `shutil.which("cl") or shutil.which("gcc")` in the same test.
14. **Runtime that a fixture would halve** (`tests/test_cmake.py`: fourteen tests each configure
    and build a fresh tree, 50 s alone here and 53 s of the full run's 142 s; `TestTheDictionary`'s
    five and `TestACollectedProjectWithPlugins`' four write identical trees; `:424-434` runs
    `ddd dump` in a subprocess where `main()` under `monkeypatch.chdir` would do).
    `tests/test_documentation.py:1436-1439` builds a validator per example file
    (`jsonschema.validate(document, schema)`; 2.4-5.6 s, the slowest test outside cmake) where one
    `Draft202012Validator` per schema would do; `getting_started.rst` runs eleven bash
    subprocesses (3.7 s). Bounded: a class-scoped configure for the two classes and a cached
    validator take 20-30 s off the suite.
15. **`compared()` discards the exit code** (`tests/test_example_plugin.py:38-41`,
    `main(["compare", before, after, "-W", "missing-id=ignore"])` unasserted): the eleven
    between-deliveries tests pin messages only, so a `layout/*` error reaching `EXIT_FINDINGS`
    under `compare` is pinned nowhere (only `check`, at `:63`). Fix: return and assert the code.
16. **The extension's launch test pins the lenient exit and depends on whatever `ddd` the PATH
    holds** (`editors/vscode/src/launch.test.ts:32-37`, `exit` without `shutdown`,
    `assert.equal(code, 0, ...)` - the code pass 6 Minor 3 wants to be 1; `:29`,
    `spawn(settings.executable, ...)` with
    no `PYTHONPATH`, so locally another installed `ddd` passes it; CI installs the tree editable,
    `ci.yml:84`). A missing executable is an unhandled `error` event (loud); a server that never
    exits hangs the test, `node:test` setting no timeout. Fix: send `shutdown`, assert the code
    the protocol asks for once Minor 3 is decided, and put a timeout on `handshake`.

### Status of the 2026-09-08 findings in this area

The previous review's periphery test review (`previous-review.md:1822-1834`):

| id | finding (one line) | status | where |
| --- | --- | --- | --- |
| P8 test review 1a | `test_lsp.py:152-168` send `as_uri()` only; the `%3A` spelling is never sent | fixed for `uri_to_path` (`tests/test_lsp.py:172-188`) and sent to the server (`:2856-2909`); the server test resolves both sides - Important 1 | `tests/test_lsp.py:172, 2856` |
| P8 test review 1b | `launch.test.ts` opens no document | still open, carried | `editors/vscode/src/launch.test.ts:27-40` |
| P8 test review 2 | `didOpen` without `text`; no buffer differing from the disk | fixed | `tests/test_lsp.py:3615-4255` |
| P8 test review 3 | raising `generate` only; no factory returning a non-backend or a non-list; no dataclass or forward-reference plugin; sibling import; identical spellings at `test_backends.py:234` | fixed except the sibling import, consciously unsupported (plan task 6) | `tests/test_plugins.py:1644-1794, 237-242, 637-652`; `tests/test_backends.py:255-295` |
| P8 test review 4 | `test_cli.py:1371-1391` asserts the message, not that nothing was written; no `--renames` write failure, non-jinja template, hook calling `sys.exit` | partly: the directory-is-a-file test still asserts the message only (`:1634-1654`) while a blocked file target pins nothing written (`:1772-1794`); the three tests exist | `tests/test_cli.py:1704-1722, 537-561`; `tests/test_plugins.py:1261-1280` |
| P8 test review 5 | `TestGenerate::test_json_output` checks statuses only | still open, carried (gap 15) | `tests/test_cli.py:901-917` |
| P8 test review 6 | `test_cmake.py` never exercises `ADDRESS_MAP`, `SEVERITY`/`STRICT`, `NO_PROPAGATE_HEADERS`, `LINK_LIBRARIES`, `DEPENDS`, `BYTE_ORDER`, `<stem>_ddd_check`, a failing `<target>.ddd` | partly: `SEVERITY` (`tests/test_cmake.py:471-484`); the rest still open (gaps 37-38) | `tests/test_cmake.py:121` builds `sensor_hub.ddd` for a passing component only |
| P8 test review 7 | `test_example_plugin.py:284-298` never compiles `ddd_layout.h` | still open (gap 50) | `tests/test_example_plugin.py:283-297` |
| P8 test review 8 | `test_transcripts.py` depends on `bash` and on the installed `ddd` matching the tree | unchanged, verified: the venv's `ddd.exe` imports the tree through the editable `.pth` (`_editable_impl_ddd_tool.pth` -> `src`) and `PYTHONPATH=src` puts it first either way; `site-packages/ddd/` holds only the force-included `cmake/` and `templates/` | `tests/test_transcripts.py:81, 314-320` |
| P8 test review 9 | incidental pins: the whole `list --format json` payload; action titles word for word | unchanged: the payload is documented as the published shape (`tests/test_cli.py:1044-1046`); the titles are still pinned verbatim at eleven sites (`tests/test_lsp.py:2123, 2149, 2355-2358, 2411-2413, 2430-2433, 2462, 2520-2524, 2546-2548, 2623-2626, 2664-2673, 2726-2729`) - they are the fix menu a reader sees, so acceptable | |

Of this review's own periphery findings, pass 7 Important 5 (the three `pytest.skip` at
`tests/test_plugins.py:1973-1984`) is still the only skip in the suite, and pass 6 Important 1 is
the defect behind Important 1 above.

### Open questions

1. Under which spelling is a finding on an opened file published - the client's (pass 6's proposed
   fix) or `as_uri()` for every file? Important 1's test change follows the answer; until it is
   made, the suite cannot tell the two apart.
2. Should `TestSymlinkedWorkspace` use a junction (`_winapi.CreateJunction`) so that it runs on
   every Windows account (pass 6 asked)? The answer decides whether the local baseline stays
   "1 failed" for anybody without `SeCreateSymbolicLinkPrivilege`, and whether the assertion grows
   from the component count (`tests/test_lsp.py:4381`) to the publication.
3. The transcript follow-up, quantified: 51 of the 166 `$ ddd` commands on nine pages run in
   silence (`types.rst` 14 of 17, `faq.rst` 14 of 22, `file_formats/component.rst` 7 of 11,
   `project.rst` 6 of 9, `file_formats/index.rst` 5 of 6, `consistency_checks.rst` 3,
   `data_dictionary.rst` 1, `generated_artefacts.rst` 1), and only 3 of the 81 runs pin an exit
   status. Is that the
   state 0.10.0 ships with, or should the harness report the unrun count per page so the number
   stays visible?
4. Does `-b` deserve the end-to-end test through the extension (Important 2)? `launch.test.ts`
   sending a `didOpen` under a configured build directory would answer both this and the carried
   "opens no document".

### Test gaps

Pinned exit paths per command, from reading every test of the half against `src/ddd/cli.py`
(the test that pins it, or "unpinned"):

| command | pinned | unpinned |
| --- | --- | --- |
| `check` | clean, errors, warnings only, json, `--baseline` (three ways), `-W` refusals, `file-not-found`, `--standalone`, a plugin override after loading, the standalone floor (`tests/test_cli.py:30-197, 1568-1631, 1883-1956`) | `--strict` promoting an analysis warning (Minor 1) |
| `compare` | verdicts, `--renames` (written, unwritable, line endings), `--plugin` (dumps, refused beside a description, verified), `missing-plugin`, BOM baseline, json on failure (`tests/test_cli.py:1704-1881, 2465-2559`; `tests/test_plugins.py:1438-1553`) | `--format json` on success only through the core half (`cli.py:667->674`) |
| `generate` | every artefact, `--without` and its refusals, templates (required, naming, four error shapes), `--force`, `--dry-run`, the address map (seven cases), `--dictionary` (nine), the write failures with findings first, plugin artefacts and their refusals (`tests/test_cli.py:199-930, 1689-1862, 2203-2296`; `tests/test_plugins.py:396-479, 1611-2107`) | json `summary` on a clean run (gap 15) |
| `list`, `dump` | table, pinned payload, `-o` (nine cases), `--standalone`, the hook failure with an empty stdout (`tests/test_cli.py:1049-1176, 2047-2200, 1908-1928`) | `dump -o .` (gap 21) |
| `id`, `schema`, `build-info`, `checks`, `cmake-dir`, `templates-dir`, `artefacts`, `sources`, `--version` | every return path (`tests/test_cli.py:1179-1372, 1399-1565, 1959-2044, 2299-2581`; `tests/test_plugins.py:1080-1136, 2110-2127`) | `cmake-dir` without the module only through the core half (`cli.py:1168-1169`); `id --assign` with one unwritable file among several (gap 18) |
| `lsp` | exit 0 on an empty stream (`tests/test_lsp.py:3601-3613`); framing exit 1 through `Server.run` (`:3548-3560`) | `-b` reaching discovery (Important 2) |

Every guard of `src/ddd/plugins.py` has the test that fires it: the name pattern and the built-in
names (`tests/test_plugins.py:160-163, 2265-2269`), the check spelling and the double
registration (`:165-173`), not found by path and by module (`:212-218`), import failures of three
kinds and their cache (`:220-329`), no `PLUGIN` and the wrong type (`:331-339`), `resolve_blocks`
(`:688-724, 2272-2283`), `settings_of` (`:1402-1410`), `guarding_plugin_model` (`:1336-1399`),
`_call` for `SystemExit` and `KeyboardInterrupt` (`:1298-1333`), `backend_of` (`:1644-1717`),
`_GuardedBackend.generate` (`:1719-1794`), `missing-plugin` (`:1458-1471`). Every write status and
failure of `backends/base.py` likewise (`tests/test_generation.py:227-376`), and every handler of
`lsp/server.py` (`tests/test_lsp.py:2853-4271`). What no test pins, found in this pass (the
consolidated list carries them with the earlier passes' items):

- `tests/test_lsp.py`: findings are read from the disk when the open buffer differs (the promise
  at `:3616-3617`; every buffer test asks for a rename or an action, none publishes); `-b DIR`
  through `Server(build_directories=...)` and through `main` with a framed stdin; a `didSave` that
  publishes; the `%3A` spelling on posix.
- `tests/test_cli.py`: `--strict` promoting a warning of the analysis under `check`.
- `tests/test_plugins.py`: `generate <plugin>` on a project with errors writes nothing.
- `tests/test_documentation.py`: every command named in `SPEC.md`; a positive control on the five
  vacuous guards; the transcripts' parameter sets non-empty.
- `tests/test_example_plugin.py`: the exit code of `compare` on a `layout/*` error.
- `editors/vscode/src/launch.test.ts`: a timeout; a `didOpen` under a configured build directory.

### Consolidated test gaps (periphery and guards)

Passes 4 (generation and a2l), 5, 6, 7 and 10, the previous review's periphery items, 11a's items
that belong to these files, and this pass, merged per file and deduplicated; each grepped for an
existing test. Dropped as already pinned: a factory returning a non-backend or `generate` a
non-list (previous review) - `tests/test_plugins.py:1644-1794`; a `--renames` file that cannot be
written, a template raising a bare exception, a hook calling `sys.exit` (previous review) -
`tests/test_cli.py:1704-1722, 537-561`, `tests/test_plugins.py:1261-1280`; a dotdot alias and a bare
relative path claiming a built-in file (previous review) - `tests/test_backends.py:255-295`; a
dataclass plugin under `from __future__ import annotations` (previous review) -
`tests/test_plugins.py:637-652`; `SEVERITY` reaching the record and the dictionary (previous
review) - `tests/test_cmake.py:471-484`; a hook raising `KeyboardInterrupt` (pass 5, the hook side)
- `tests/test_plugins.py:1302-1313`; a rename *to* an enum or enumerator name (pass 6, half of it) -
`tests/test_lsp.py:2063-2064`; a description containing `*/` (pass 4's neighbour) -
`tests/test_generation.py:96-98`.

`tests/test_lsp.py`

1. The published uri equals the client's spelling for a file opened under `%3A`, a junction, a
   `subst` drive or a case variant, and the file is not its own candidate (pass 6 Important 1 and
   2; Important 1 here).
2. `-b DIR` reaching `discover` through `Server(build_directories=...)` and through
   `main(["lsp", "-b", ...])` with a framed `didOpen` (Important 2 here).
3. Findings published from the disk while the open buffer differs (this pass).
4. A project file opened with no build record; a component opened first, then the project file:
   what is published and withdrawn (pass 6).
5. Two records covering one file: what is published for it (pass 6; `:3438-3467` covers the rename
   only).
6. A record naming an unknown check, and one with a malformed entry (pass 5, pass 6, carried;
   `severity=[...]` names known checks only at `:454, 3044, 3136`).
7. A rename and a quick fix while a file of the project failed to load (pass 6).
8. F2 *from* an enum name and an enumerator; a `size`/`typename`/`name` key inside an
   `extensions` block under hover and rename (pass 6).
9. `codeAction` with `context: null`; `initialize` with a folder lacking `uri`; a request before
   `initialize` and after `shutdown`; `initialize` twice (pass 6 Minor 1, 2, 4).
10. A junction loop, or any junction, under `build/` (pass 6, Windows).
11. `TestSymlinkedWorkspace` through a junction, asserting the publication (pass 6; open
    question 2).
12. A `didSave` that publishes (Minor 2 here); the `%3A` server test on posix (Minor 3 here).
13. A document nested 600 levels through `Document(text)` (pass 8 Important 1; 11a's item 52,
    shared).

`tests/test_cli.py`

14. `--strict` promoting a warning of the analysis under `check` (Minor 1 here).
15. `generate --format json` on a clean run: `diagnostics`, `summary`, and stdout carrying nothing
    but the document (previous review; `:901-917` pins statuses only).
16. `allow_abbrev`: `--stand` and `--dict` refused (pass 5; `ArgumentParser(prog="ddd", ...)` at
    `src/ddd/cli.py:146` leaves the default).
17. `dump -o`, `--renames` and `--dictionary` pointing at a file the run read (pass 5).
18. `ddd id --assign` with an unwritable file among several (pass 5).
19. `KeyboardInterrupt` reaching `main` (pass 5).
20. The comparison findings' `location.path` and their text order against the candidate's own
    findings, typed relative and absolute (pass 3 through pass 5).
21. `dump -o .` and `--dictionary .`; a wide-character unit in the table; `compare -W` on a check
    only the baseline's plugin registers (pass 10 Minor 7, 9, 10).
22. The interleaving of `list`'s table and findings in one buffer (pass 10 Minor 8; the transcript
    harness merges the streams in call order at `tests/test_transcripts.py:296-299` and cannot see
    it).
23. `--dictionary` refused for a case variant of an artefact path; `render`'s clash on a case
    variant of a `{component}` file (pass 4; `WindowsPath` only, so platform-aware).
24. The documented address-map recipe on the host toolchain; a map entry out of range for a symbol
    the dictionary does not carry (pass 5).
25. `-W x=error` reaching a description baseline (pass 3; 11a's item 46, shared).
26. A document nested 600 levels through `ddd id --assign` (pass 8 Important 1; 11a's item 52).

`tests/test_plugins.py`

27. A plugin printing to stdout under `check --format json`, `generate --format json`, `dump` and
    `dump -o` (pass 5; only the server case at `:2154-2210`).
28. A check hook mutating a block: what the backends and the dump see (pass 5).
29. `generate <plugin>` with errors writes nothing (Minor 10 here).
30. The junction test running on every platform, or the convention amended (pass 7 Important 5).

`tests/test_backends.py`

31. The import-graph guard over `compare.py`, `identity.py`, `build_info.py`, `cli.py` and
    `src/ddd/lsp/` (pass 7); and a backend importing `ddd.cli` or `ddd.plugins` (`:81-85` forbids
    `ddd.loading` and `ddd.analysis` only).
32. A bound on `build_code_model` and on the a2l model, linear in objects; a diamond of
    external-only structures rendered (pass 10 Minor 1, 2, 4).

`tests/test_generation.py`

33. A description, unit or enumerator text containing `/*` (pass 4).
34. A helper template (`_x.jinja2`) raising: the message names the helper (pass 4).
35. `MOD_COMMON` alignments, `HEADER` fields, the `_2` suffix on a colliding method name, a
    `boolean` measurement and characteristic, `float32` underflow (pass 4, carried; none in
    `tests/test_a2l.py` by grep).

`tests/test_a2l.py`

36. A non-ASCII unit; the spelling of a derived limit under a decimal factor (`7.65`); an axis
    whose `input` is a structured instance (pass 4; the analysis side is 11a's item 20).
37. An address map with a byte order mark, underscores, non-ASCII digits and a repeated key
    (pass 10 Minor 5, 6; `:171-187` cover hex, decimal and the refusals).

`tests/test_cmake.py`

38. A failing `<target>.ddd` component target; a component broken at configure time and its
    target after the fix (pass 5, previous review; `:121` builds `sensor_hub.ddd` for a passing
    component only).
39. `STRICT`, `ADDRESS_MAP` (the seeded map and the two-run flow), `BYTE_ORDER`,
    `NO_PROPAGATE_HEADERS`, `LINK_LIBRARIES`, `DEPENDS`, `OUTPUT_DIRECTORY`, `NAME` defaulting,
    `DDD_A2L`, `<stem>_ddd_check` (pass 5, previous review).
40. Removing a component from the link graph: the header survives, `ninja -t clean` leaves it,
    the rebuild afterwards (pass 5).
41. An image registering no component under `-Wpedantic -Werror`; the compile harness on a
    float-only and on an empty project (pass 4, pass 5).
42. A source directory whose name carries `[` under the collected mode; a keyword without a value
    (`ADDRESS_MAP ${UNSET}`); a `DDD_EXECUTABLE` of another release (pass 10).
43. The pre-commit hook end to end (`pre-commit try-repo`) (pass 5; `TestPreCommitHook` reads the
    yaml only).
44. The C compiler among the tools said to exist (Minor 13 here).

`tests/test_documentation.py`

45. The two version fields of `editors/vscode/package-lock.json`; the wheel file name in
    `README.md:54` and `docs/getting_started.rst:29`; the seven banners as `__version__`; the
    README's `== symbols` counts (pass 7).
46. "Nothing in the suite skips": no `pytest.skip`, `skipif`, `importorskip` or `xfail` under
    `tests/` (pass 7).
47. Every command named in `SPEC.md`, and positive controls on the five vacuous guards (Minor 4
    and 6 here).
48. `docs.yml`'s `order()`/`stable` orderings (pass 7 Important 2).
49. Nothing builds `docker/Dockerfile`, `compile.sh` or `verify_symbols.py` in CI (pass 7 Minor 9).

`tests/test_transcripts.py`

50. A positive control on `SHOWN` and `RUNS` (Minor 5 here).
51. The 51 commands on nine pages that run in silence, and `echo $?` pins for more than 3 of the
    81 runs (the maintainer's follow-up; open question 3).

`tests/test_example_plugin.py`

52. `ddd_layout.h` compiled (previous review Minor 9; `:283-297` asserts substrings).
53. The exit code of `compare` on a `layout/*` error (Minor 15 here).

`editors/vscode/src/launch.test.ts`

54. A `didOpen`, and a configured build directory reaching discovery (previous review; Important 2
    here); a timeout on the handshake (Minor 16 here).

### Assessment

The periphery half of the suite is what the developer page says it is: order independent,
writing nowhere but `tmp_path`, in-process and deterministic where the server is concerned, and
behavioural in its assertions - exit codes, files on disk, bytes of an a2l, the frames a client
would read back. The four fix plans' promised tests all exist, two of them pinning a deliberately
stronger contract than the plan wrote. Coverage is honest: the guards of `plugins.py` and the
write-step statuses of `base.py` each have the test that fires them, and the half alone leaves
only lines the core half reaches. Two things would pass with a real defect behind them: the
server tests compare uris by file name or resolved path, which is exactly why pass 6's
publication defect never turned a test red, and `-b` - the extension's one setting - is accepted
by two tests and used by none, so a server dropping its build directories passes 736 tests. The
rest is hygiene: a no-op `--strict` test, an assertion satisfied by a log line, three
platform-vacuous checks, five documentation guards and one transcript suite that go quiet rather
than red when their regex finds nothing, a stale docstring, a spy where the bytes would do, nine
copies of a fixture, and a cmake file that spends a third of the suite's time configuring the same
tree fourteen times. The consolidated list is 54 gaps, most of them carried from passes 5, 6 and
7 and verified still open; the two that matter most are the ones the two Important findings would
close.

### Verification

Not verified.
