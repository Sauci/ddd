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
