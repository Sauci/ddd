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
11. The test suite: what it pins, what it leaves open, and how it would fail.

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
