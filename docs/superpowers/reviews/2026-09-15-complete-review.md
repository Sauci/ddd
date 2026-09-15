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
