## Pass 23: the test suite of the page

> **Read this first.** The page has two suites that differ in kind. Vitest holds `api`, `lib` and
> `state` to 100 % coverage with tests that read like specifications, and it earns the gate: with its
> hangs it kills 88 % of the mutants there that compile, in five seconds. The 294 journeys are the
> only test of the other 64 % of the page's code, by the design's own account; they are careful,
> isolated, retry-free, drive the real `ddd gui`, pin behaviour and not pixels, and execute 97.5 to
> 100 % of the screens' lines - yet they kill only 52 % of the `.tsx` folders' compiled mutants, and on
> `lib` code they catch half of what Vitest catches (I2). None of the page defects passes 15 and 16
> found by hand fails any test; each fails a journey of 5 to 18 lines (I1). Everything cited lives
> in `SCRATCH/pass-23/` (`notes.md` is the working log, including four harness defects of mine and
> their repair; `evidence/` holds what outlives the copies).

### Scope covered

**Read in full, with line numbers**: `gui/e2e/fixtures.ts` (493), `gui/e2e/demo.ts` (615),
`gui/e2e/keys.spec.ts` (250), `gui/e2e/skeleton.spec.ts` (260), `gui/e2e/values.spec.ts` (908),
`gui/e2e/large.spec.ts` (178), `gui/src/lib/refusals.test.ts` (140), `gui/src/census.test.ts`,
`gui/package.json`, `gui/vite.config.ts`, `gui/playwright.config.ts`,
`gui/playwright.screenshots.config.ts`, `gui/playwright.bench.config.ts`, `gui/tsconfig.json`,
`gui/biome.json`, `gui/.ladle/*`, `gui/screenshots/stories.spec.ts`,
`.github/workflows/ci.yml:1-63, 158-310`, part 19c's plan
(`docs/superpowers/plans/2026-10-21-gui-journeys-remaining.md:1-60, 1713-1725, 1880-2085`), part 19b's
spec (`docs/superpowers/specs/2026-10-08-gui-journeys-every-action-design.md:13-80, 188-200`),
`docs/developer_documentation.rst:905-948`.
**Read in part**: `gui/e2e/start.spec.ts:1-120, 300-345, 372-395, 440-544`, `helpers.spec.ts:1-135`,
`network.spec.ts:1-120`, `canvas.spec.ts:500-607`, `units.spec.ts:81-142`,
`declarations.spec.ts:41-100`, `kept.spec.ts:1-60`, `shared.spec.ts:240-275, 446-480, 700-740`,
`compare.spec.ts:65-113`; the titles of all 294 journeys; `ValuesGridView.stories.tsx:1-80`; the
test names of `client.test.ts` and `objectValues.test.ts`, `findings.test.ts:530-560`; the code
beside every probe, every survivor (85, `labels23.tsv`) and every line no journey reaches.
**Not read**: the other ~5,400 lines of the 27 spec files, the bodies of 36 of the 38 Vitest files
(about 9,000 lines), 51 of the 52 story files (2,530 lines) and `src/stories/fixtures.ts` (3,253),
`gui/bench/page.bench.ts` beyond its test names (run by hand only, by design). They were measured
instead, by the line map, the campaign, the probes and the screenshot experiment.

**Ran**, on copies under `SCRATCH/pass-23/` (`base`, `cov`, `w/0-5`, `probe`, `probe-fix`; made with
`tar -m`, so with fresh timestamps), never in the tree (`git status` clean before and after):
- **A line map of the journeys**: the whole suite with V8 block coverage per journey (a `page`
  fixture added in the copy), four shards in parallel (4 min 47 s), mapped to source lines through
  the bundle's source map (`harness/linemap.mjs`, `linemap.json`): 292 journeys (the two helper
  journeys that open no page are not), every document a journey loads counted.
- **A mutation campaign over `gui/src`**: 106 runtime files, 11,339 sites (`harness/gen.mjs`, Babel's
  parser; the operators of passes 21 and 22, plus a screen's early returns, dropped JSX attributes
  and children, hook dependencies, option objects), a sample stratified by folder and then by
  operator (`sample23.py`, so any prefix is stratified), runner `harness/runmut23.py`. Each mutant:
  `tsc`; Vitest as CI runs it (`--coverage`, 100 % thresholds) for `api`, `lib`, `state`, ten null
  mutants and 16 others; the build; the journeys the line map says reach its line, those reaching
  most of its file first, at most 60, `--max-failures=1`, a failure in a fixture asked again without
  that journey; one in four Vitest-killed logic mutants also asked of the journeys. Stopped at 386
  outcomes; survivors cut by the cap asked again past it (`results-beyond.jsonl`).
- **Ten probe journeys** for hand-found defects of passes 15 and 16, and two crude fixes
  (`evidence/p23-probes.spec.ts`, `evidence/crude-fixes.patch`).
- **The fixtures mutated**: the 53 journeys calling `demo.ts`'s regex drift helpers, with the nine
  helpers made no-ops (`evidence/noop_helpers.py`, `evidence/noop-helpers-run.txt`).
- **The story screenshots**, with references made on this machine from the unmutated build (162 of
  162 stable on a second run), against six mutants the journeys let through (`shots-mutants.jsonl`).
- **Flakiness**: 24 timing-sensitive journeys repeated under load (33 runs, `flake1/`) and on a
  quiet machine (229 runs, `flake2/`); the stale-build trap (`evidence/stale-*.txt`); `ddd check` of the
  chain fixture.

**Harness defects of mine, repaired** (`notes.md`): (1) the first line map kept one coverage entry
per journey, and 27 journeys load the page twice, so code reached only after a `goto` or a reload
read as unreached: found by a direct mutant (`ValuesPage.tsx:283`), fixed, and the 19 survivors whose
selection grew asked again; (2) Python's text mode wrote CRLF on the first restore, caught by the
restore check before any outcome was recorded; (3) ties in the journey order were first broken by
duration, which put the long, specialised journeys past the cap (`UpdatingNote.tsx:26`'s killer
ranked 148 of 278): since then a hash, and the earlier survivors were asked again; (4) a Vitest run
that hung (300 s) was recorded as no kill: counted as hung, as pass 22 counts it (2 mutants).

### Strengths

- **The journeys pin behaviour, and pin it hard.** 1,591 `getByRole`, 203 reads of what was written
  back to disk, 201 `toHaveText` and many exact sentences; not one screenshot. Nearly every Apply in
  `keys.spec.ts`, `values.spec.ts`, `skeleton.spec.ts` is followed by the file read back. The twenty
  CSS and geometry checks are deliberate (a module dimmed, a dashed border for a file that did not
  load, a focus outline, an alert above the canvas).
- **They reach almost everything, by design.** Each tab's states (reading, failing, kept, stale,
  refused, failed by the server) are rows of part 19b's and 19c's plans with a journey each, and the
  line map agrees: journeys execute 99.7 % of `app`'s mapped lines, 98.7 % of `components`', 97.5 % of
  `screens'`, all of `ui`'s, 96.9 % of `lib`'s.
- **The unit tests are good tests.** Exact expected values, parametrised refusals, domain names
  (`refusals.test.ts`, `client.test.ts`); Vitest, with its two hangs, kills 94 of the 107 compiled mutants of `api`,
  `lib`, `state` (88 %); of the twelve that live, nine are equivalent (a leaked listener, a key's
  order, a timing default) and three are real gaps (Test gaps). It cannot reach a `.tsx` at all: 16 of 16 such mutants
  asked of it lived, as its module graph says they must.
- **No retries anywhere** (`playwright.config.ts` sets none; no `test.retry`, `skip`, `fixme` or
  `slow`), one `waitForTimeout` (16 ms in a bounded settle, `demo.ts:166`): a flaky journey goes red.
  Part 19c's hunts ran every journey five times on three legs and worked their two failures to a
  cause rather than retrying them (plan, 1913-1925, 2083-2084).
- **Isolation holds, and so does the suite under load.** Each journey serves its own copy on port 0
  in a fresh context; ten null mutants ran ten different subsets of 5 to 60 journeys under six to
  eight parallel runners at 90-99 % CPU and all lived. Of 779 journey runs with no mutant (coverage,
  nulls, the loaded flake sample) 775 passed, the 4 failures all one fixture bound (M2); on a quiet
  machine 229 of 229 passed (21 timing-sensitive journeys ten times each, the chain journey ten
  times, the three large ones three times), which agrees with part 19c's hunts.
- **The fixtures fail with a reason, and the journeys fail when their fixture does not do its job.**
  `fixtures.ts:209-216`, `303-387` bound and name their waits; the helpers have journeys of their own
  (`helpers.spec.ts`, 11); with every drift helper a no-op, all 49 journeys that call one fail, none
  vacuously (M5 is about what they say).
- **The story screenshots add something real for components.** Of six mutants the journeys let
  through in `components` and `ui`, the stories catch four (`UpdatingNote` inverted, 16 pictures;
  a class in `UnitPanelView`, 2; the unused count of `UnitsTableView`, 4; the "Type" column header,
  4).
- **The quick loop is quick where the gate is**: `tsc` 0.6 s (TypeScript 7's native compiler),
  Vitest 4.5 s with coverage for 959 tests, Biome under a second, a build 2.2 s. One spec file runs
  in 1.5 to 92 s (median journey 2.5 s), `npx playwright test e2e/<file>.spec.ts:<line>` runs one
  journey. The whole suite: 13.0 min serial on this machine (the coordinator's baseline), 6.1 min on
  the Linux PC (plan, 1931) and 6.8 to 9.9 min a CI leg in its last runs (plan, 1891-1910).

### Issues

#### Critical

None. No survivor is a present defect: each is a wrong program the suite would let through. The
present defects are passes 15 and 16's, and none has a test (I1).

#### Important

- **I1. No test fails on any of the page defects passes 15 and 16 found by hand; each fails a
  journey of 5 to 18 lines built from the suite's own fixtures and helpers.**
  `SCRATCH/pass-23/evidence/p23-probes.spec.ts`, run against the tree's own build
  (`evidence/probes-on-tree.txt`, `evidence/probe-p16C1-on-tree.txt`): 10 failed, the control
  passed, each for the reason its pass gave:

  | defect | the probe observes on the tree's build | lines |
  | --- | --- | --- |
  | pass 15 C1 | after Apply on `datatype`, the unit row the panel moves to reads `uint16` | 18 |
  | pass 15 I1 | an enabled `Apply to 2 files` while the field reads `km/h`; pressed, `rpm` is written | 15, 9 |
  | pass 16 C1 | `5` set and `0` typed by key into MapA's `element 2, 4`: the cell reads `5` | 13 |
  | pass 16 I2 | Apply after a map cell is typed: viewport ratio 0 | 5 |
  | pass 15 I2 | after an `offline` event, Apply pressed: nothing written in 5 s | 7 |
  | pass 15 I5 | a lone surrogate unit in `pump.ddd.json`: Pump's page blank, `URIError: URI malformed` | 18 |
  | pass 16 I10 | Remove offered while `controller.ddd.json` does not load, no word of it | 8 |
  | pass 16 I13 | Close by keyboard: focus not back on the opener | 10 |
  | pass 16 I5 | Shared files with entries: no Declare button | 9 |

  Two pass once their defect is crudely fixed in a copy (`evidence/crude-fixes.patch`:
  `stopPropagation` for a one-character key in the cell's `onKeyDown`, `ValuesGridView.tsx:229`;
  `chosen` reset when `selected` changes, `VariablePanel.tsx`), so they test the defect and not
  something near it. Pass 16 C1's probe is one call away from an existing journey:
  `values.spec.ts:254` sets the same cell with `.fill("50")`. Pass 15 I1's sits beside
  `units.spec.ts:81-112`, which types into the same chooser and Tabs away, but never presses Apply.
  Others of the two passes are as cheap: pass 15 I3 (a second page opening another project, about
  20 lines), pass 16 I1 and I3 (a long value's `scrollWidth`, two cells typed; under 10 each), the
  contrast findings (`axe-core` 4.13 is already in `node_modules` through Ladle, and nothing uses it).
  *Why it is structural*: the journeys walk every state a plan row names, through `.fill()` (151
  times; never `pressSequentially` or `keyboard.type`), one key, one document, one revision at a
  time; each hand-found defect needs the second thing - the key the panel moves to next, text left in
  a field at the press, a key reaching the grid, a second event source, a hostile string. The same
  shape as pass 22 I1 on the Python side. *Change* (S, an hour or so each): land each fix with its
  probe; make driving a field with key handling (grid cells, choosers) by `pressSequentially` a rule
  of the journeys (open question 2).

- **I2. The journeys alone guard 64 % of the page's code, and they execute far more of it than they
  check: they kill 52 % of its compiled mutants where Vitest kills 88 % of the logic folders'.**
  `components`, `screens`, `ui`, `app` (10,581 of the page's 16,570 runtime lines) are outside Vitest
  by construction: `vite.config.ts:14-21` takes `src/**/*.test.ts` in `node` and covers `src/api`,
  `src/lib`, `src/state`; no test imports a `.tsx`; 16 of 16 such mutants asked of Vitest lived
  (KNOWN that no unit test reaches a `.tsx`: pass 3 I7; part 19b's spec says so itself, "The journeys
  are the screens' only test", `2026-10-08-gui-journeys-every-action-design.md:15`). The campaign
  (`results.jsonl` and the follow-ups, `harness/final.py`, `final-tables.txt`): 386 outcomes, 375 of
  them mutants and 10 null, stratified by folder; a survivor reached by more journeys than the
  first 60 was asked all the others too:

  | folder | sampled | `tsc` caught | compiled | killed | survived | score |
  | --- | --- | --- | --- | --- | --- | --- |
  | components | 55 | 21 | 34 | 16 (journeys) | 18 | 47 % |
  | screens | 54 | 16 | 38 | 16 (journeys) | 22 | 42 % |
  | ui | 53 | 16 | 37 | 27 (journeys) | 10 | 73 % |
  | app | 52 | 27 | 25 | 11 (journeys) | 14 | 44 % |
  | **the four, by the journeys** | 214 | 80 | 134 | 70 | 64 | **52 %** |
  | lib | 54 | 19 | 35 | 27 Vitest, 1 coverage only, 2 hung, 1 journeys | 4 | 89 % |
  | api | 54 | 17 | 37 | 36 Vitest | 1 | 97 % |
  | state | 53 | 18 | 35 | 27 Vitest, 1 coverage only | 7 | 80 % |
  | **the three, by Vitest** | 161 | 54 | 107 | 94 | 12 (+1 to journeys) | **88 %** |

  On the same `lib`, `api`, `state` code the journeys kill 24 of the 48 mutants Vitest killed that
  were also asked of them: a coarse oracle, even where they run the code. The 64 survivors of the
  four journey folders, read one by one (`labels23.tsv`): 24 cosmetic (class names, a 1 px offset,
  a glyph), 14 equivalent, 5 visible texts no journey reads (a column header, a meta line, a rename
  note), and 21 behaviours a reader meets that no journey checks (two of them, the unit count, the
  stories' pictures catch): a section panel's "Updating the findings…" note inverted
  (`SectionPanelView.tsx:191`) and the note's `status` role dropped (`UpdatingNote.tsx:25`); the
  Files tab's controls left enabled under a stopped server (`FilesPage.tsx:424`); the add form's
  field enabled while busy and its Show changes never opening (`SharedAddView.tsx:159`, `:201`); a
  raster panel's old failure kept after the next action (`RasterPanel.tsx:270`); a constant's panel
  left open when the constant is removed from outside (`ConstantPanel.tsx:90`; the raster's copy has
  a journey); a row with an error and a warning no longer marked in error (`ComponentPage.tsx:302`);
  a unit used by a type and a variable counted unused (`UnitsTableView.tsx:58`, two operators); a diff
  left open after Apply (`VariablePanel.tsx:257`); the adopt preview left open (`UnitsPage.tsx:105`);
  the unit panel blanking to "reading" on each revision (`UnitPanel.tsx:64`); the heading and
  masthead of an unnamed project empty (`App.tsx:169`, `:297`); the heading of a project opened but
  not analysed (`App.tsx:242`); a closed panel leaving a history entry (`App.tsx:129`); a modified
  click on a tab (`LinkTabs.tsx:21`, two operators); an invalidation after a declaration or a section
  edit dropped (`DeclarePanel.tsx:149`, `SectionPanel.tsx:201`). Seven more survived their first
  60 journeys and died to one further on, which is what the cap would otherwise have hidden.
  Against `vite.config.ts:4-6` ("the screens are covered end to end by Playwright") and
  `docs/developer_documentation.rst:938-940` ("The screens are covered by `npm run e2e`"): they are
  executed, not checked. *Why it matters*: the decisions pass 3 I7 counted in the `.tsx` files
  (about 600 conditionals) change with every screen, and half of their mutations reach CI green; the
  journeys grow at about 30 lines and 2.5 s each and still miss what a unit test of the decision
  would pin in a line. *Change*: open question 1 - the decisions into `lib/` under the existing gate
  (M per screen), or a DOM environment for Vitest over `components` and `ui` (S to set up, then per
  component).

#### Minor

- **M1. The developer page never says the journeys serve the compiled pages, so a screen edited and
  `npm run e2e` run tests the build from before, green; nor what the suites cost.** Reproduced
  (`evidence/stale-before-build.txt`, `stale-after-build.txt`): "Reading the values…" changed in
  `ValuesPage.tsx:263` and not built, `values.spec.ts:613` passes; built, it fails.
  `docs/developer_documentation.rst:913-948` lists `npm run build` and `watch` but not that the
  journeys need one first; part 19c's plan tells its agents
  (`2026-10-21-gui-journeys-remaining.md:56`), and nothing in `playwright.config.ts` or
  `fixtures.ts` builds or checks the age of `src/ddd/gui/static/`. CI builds first (`ci.yml:209`), so
  only the local loop is fooled. The page gives no time for the journeys (13 min here) and no
  advice to run one file or one line. *Change* (S): a `globalSetup` that builds (2 s), or refuses a
  `static/` older than `gui/src`; two sentences on the page.
- **M2. The fixtures' bounds are calibrated on the Linux PC; on this Windows machine the chain
  fixture's first analysis does not fit in them under load.** `ANALYSIS_WAIT_MS` 30 s
  (`fixtures.ts:216`). The plan measured `chainedGui`'s project "served and analysed in 484 ms" and
  its journey 1.1-1.2 s (`2026-10-21-gui-journeys-remaining.md:1938`); here, on a
  quiet machine, `canvas.spec.ts:508` takes 13.6 to 23.7 s (ten runs, all passed) and `ddd check` of a
  freshly generated copy of its project 10.2 s, 1.6 s once its 2,004 files have been read - and a fresh
  copy is what every run of the fixture analyses (Defender's scanner was the busiest process during
  the loaded runs; that it is the cold cost is my inference); under load the check took 37 s, and the journey failed "had not finished its first analysis 30 s after printing its address" in all 4 failures of
  the 779 no-mutant runs (2 of its 2 runs in the loaded flake sample, 1 in the coverage run, 1 in a
  null mutant); the campaign met the same bound twice more, once on `large.spec.ts:77` (12 to 18 s quiet).
  On CI's legs it takes 3.4-4.5 s, so this fails contributors, not CI. *Change* (S): a bound scaled
  to the project, or a smaller chain (908 components is the measured threshold, 2,000 are served).
- **M3. No `actionTimeout`: a control a regression removed is waited for until the test's 60 s, with
  no word of which.** `playwright.config.ts:10-11` set `timeout` and `expect.timeout` alone. Seen in
  the campaign (`results-reask-timeouts.jsonl`): `ComponentPage.tsx:51` negated, `start.spec.ts:430`
  fails after 60 s in `withinBox`'s `target.boundingBox()` (`demo.ts:191`), while `demo.ts:136-138`
  says a target that never comes within the box "fails here, in words that say why"; the no-op
  helpers' run had 11 clicks waiting out 60 s, and its 53 journeys took 23.2 min. With no
  `--max-failures` in CI (`ci.yml:231`), a regression that breaks most of 294 journeys, each failing after 10 to 60 s,
  needs far longer than the job's 30 minutes (`ci.yml:187`). *Change* (S): `actionTimeout: 15_000` under `use`.
- **M4. Two of the three copies of a shared entry's stale refusal have no journey, against P19c-10's
  reason for leaving them.** The constant's has one (`shared.spec.ts:456`); the section's and the
  raster's own copies of that code are executed by no journey (`SectionPanel.tsx:189-190, 223`,
  `RasterPanel.tsx:184-185, 218`; `evidence/unreached.txt`), though the ruling left the other splits
  because "another journey draws the same branch" (`2026-10-21-gui-journeys-remaining.md:2058-2063`).
  Pass 3 I6 found these copies already differ on a refusal. The same holds of other states no journey
  draws (Test gaps). *Change* (S): parametrise `shared.spec.ts:456` over the three kinds, as
  `:732-738` already does for the server's failure.
- **M5. `demo.ts`'s drift helpers edit the examples by regular expression and never check that their
  edit landed; a change of the demo's layout turns about fifty journeys red with messages about
  something else.** `demo.ts:19-47, 236-254, 330-338, 344-397`, against the specs' own local helpers,
  which throw (`values.spec.ts:50, 62-64, 78`). Measured (`evidence/noop-helpers-run.txt`): with the
  nine drift helpers made no-ops, the 49 journeys that call one all fail - none passes vacuously -
  but with 31 "element(s) not found" and 11 clicks waiting out 60 s, never "the drift did not
  apply". The journeys also pin the demo's counts and geometry ("Controller's fourteen declarations",
  `demo.ts:105-106`; "the box is 432px tall ... 495px", `values.spec.ts:569-571`) and the generator's
  exact output ("25000 findings", row 24999 in `c00665.ddd.json`, `large.spec.ts:131-152`); the demo
  has not changed since 2026-09-10 and is cited about a hundred times by `tests/` and `docs/` too.
  The two helper files took 53 commits in seven weeks, 16 of them about timing (races, unseen
  writes, stamps, scroll windows, the hang); 31 % of their lines are comments. *Change* (S): throw
  where a pattern matched nothing, as the local helpers do.
- **M6. The screenshot job pins pixels of the stories alone, and the stories' props skip states
  their components draw.** `ci.yml:271-272`: "a look that changes without meaning to fails here".
  The 163 references are all of `components` and `ui` stories (152 and 11), none of a screen. Of the
  six mutants tried, the stories miss a section panel's inverted updating note (163 of 163 equal:
  no story passes `updating`) and a modified click (nothing drawn). The job cannot run on a machine
  without Playwright's own Chromium: `playwright.screenshots.config.ts:12` names no channel, and here
  163 of 163 failed to launch (`shots-win-vs-linux.txt`); the developer page says as much
  (`docs/developer_documentation.rst:932-936`), so this is a limit, not a surprise.

### Status of the 2026-09-15 findings in this area

None: the 2026-09-15 review predates the page (its milestone 1 is dated 2026-09-17) and has no
finding on the page's tests.

### Open questions

1. **What guards the decisions in the `.tsx` files: the journeys, a unit gate, or moving them out?**
   Part 19b's spec makes the journeys "the screens' only test" and grew them to 294; I2 shows that
   executing a line is not checking it. (a) The journeys stay the guard, and each new decision lands
   with a journey shown to fail on more than the one change its row names; (b) a DOM environment for
   Vitest (happy-dom, jsdom or Vitest's browser mode; none is a dependency today) and the 100 % gate
   widened to `components`, `ui`, `screens`, `app`; (c) pass 3 I7's direction, the decisions moved
   into `lib/` where the gate already holds them. (c) is cheapest per decision and keeps one gate;
   (b) catches most for the least restructuring.
2. **Is typing key by key, rather than `.fill()`, a rule for the journeys?** Yes makes pass 16 C1's
   class of defect a gate at a cost of seconds per journey; no means every key handler (grid cells,
   choosers, type-to-find) is tested by nothing.
3. **Is a stock Windows machine, with Defender scanning, a supported place to run the journeys?** Yes
   means room in the fixtures' 20 s and 30 s bounds and a smaller chain fixture (M2); no means the
   developer page says the journeys are for CI and Linux, and how long they take there.

### Test gaps

Beyond those passes 3, 15 and 16 listed (not repeated here):
- the ten probes of I1, each a ready journey (`evidence/p23-probes.spec.ts`);
- the behaviours of I2 no journey checks, and three in `lib` and `state` no test pins: `"types"` dropped
  from `SHOWN` (`findings.ts:324`: a routeless finding in a types file would read "has no page yet";
  `findings.test.ts:537-558` covers `project` only), a first poll that fails stopping the follow
  with no retry (`revisions.ts:36`: the retry is tested only after a success), and a path whose
  second part is empty after a non-empty first (`C://x`) read as a network root (`paths.ts:38`);
- states no journey draws (`evidence/unreached.txt`, 102 mapped lines in 18 files): the findings list
  inside a constant's, a raster's and a section's panel (`ConstantPanelView.tsx:165-172`,
  `RasterPanelView.tsx:223-230`, `SectionPanelView.tsx:193-200`); the section's and raster's stale
  refusal (M4); the "Updating the findings…" placeholder of a unit's, a section's and a raster's
  panel (`UnitPanel.tsx:223-225`, `SectionPanel.tsx:241-243`, `RasterPanel.tsx:236-238`); the
  component page's "is no longer declared in the open project" (`ComponentPage.tsx:234-236`); a
  type's "Nothing in the project uses" (`TypePanelView.tsx:180`); typing a section's access
  (`SectionPanel.tsx:259-262`);
- what the CI job lets through, read off the campaign: half of the compiled behaviour changes in the
  screens; any change of a screen's look (no screen has a story); anything only a key, a modified
  click or a second document shows; accessibility (no check, `axe-core` unused); Firefox, Safari and
  macOS (KNOWN, plan 1962); the server half of a journey on Python 3.13 and 3.14 (the job runs 3.12,
  `ci.yml:195`; pytest covers the server there);
- no journey runs with an `actionTimeout`, so none can say which control was missing (M3); nothing
  checks that the pages served are the ones just built (M1).

### Assessment

The page's suite is two suites of different worth. Vitest is the strong one: specification-like
tests over `api`, `lib` and `state`, a 100 % gate that means something, nine in ten compiled mutants
killed in five seconds, three small gaps found. The journeys are the honest, careful and expensive one -
294 of them, isolated, retry-free, worked to the cause when they failed, pinning sentences and the
bytes on disk rather than pixels - and they are, by the design's own words, the only test of the
two thirds of the page that lives in `.tsx` files. There the numbers turn: they execute almost
every line and check about half of what changes on it, and on `lib` code, where both run, they catch
half of what Vitest catches. Every defect passes 15 and 16 found by hand goes through all 294,
because none types key by key, presses Apply with text still in a field, or builds a second key,
document or event, and a journey of 5 to 18 lines would have caught each one. Around that sit the
costs of a large browser suite: 13 minutes here, a fixture bound that a loaded Windows machine
misses, 60 s lost per missing control, a pair of helper files that took 53 commits in seven weeks,
and journeys tied to the demo's layout and geometry. The CI job runs them well; what it lets
through is exactly what they do not look at.

```candidates
23|I1|gui/e2e/values.spec.ts:254|No test fails on the page defects passes 15 and 16 found by hand: ten 5-18 line probes fail today, two shown to pass with a crude fix
23|I2|gui/vite.config.ts:18|Journeys alone guard 64 % of the page and kill 52 % of its compiled mutants where Vitest kills 88 % of the logic folders'; 21 reader-visible behaviours unchecked
23|M1|docs/developer_documentation.rst:940|The page never says the journeys serve the compiled pages: a screen edited and not built passes its journey (reproduced)
23|M2|gui/e2e/fixtures.ts:216|The 30 s analysis bound is calibrated on the Linux PC: the chain journey takes 14-24 s on a quiet Windows machine and fails it under load
23|M3|gui/playwright.config.ts:11|No actionTimeout: a removed control is waited for 60 s with no word of which, against demo.ts:136-138
23|M4|gui/src/screens/SectionPanel.tsx:189|The section's and raster's stale refusals have no journey, against P19c-10's reason for leaving them
23|M5|gui/e2e/demo.ts:42|Regex drift helpers never check their edit landed: a demo layout change fails ~50 journeys with unrelated messages
23|M6|.github/workflows/ci.yml:272|Screenshots pin pixels of the stories alone: no screen has one, and a story's props skip states (section updating note)
```
