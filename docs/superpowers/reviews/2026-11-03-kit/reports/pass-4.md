## Pass 4: what does the documentation miss?

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-4/`. Line numbers are on the review tree.

**The answer, plainly.** As a reference, the documentation misses almost nothing: of 72 checks, 15 ELF findings, 21 commands,
26 options, 153 schema keys, 18 CMake keywords, 7 targets and every plugin field, one schema key is left to the generated
reference and nothing else is absent. Few tools can say that, and most of it is held there by tests. What it misses is everything
that is not a reference. `ddd gui`, which is over half the code, has no guide: its only account is one cell of a table on the command line
page, 3,960 words long. No page says how a project with existing C adopts DDD, and the first step a real adopter takes fails at the
link. No page says how to get from the generated a2l to a connected calibration tool. A contributor is not told how to set up a checkout or where
a new endpoint goes. The tutorial's `ddd id --assign` step fails on Windows. The changelog files features under a release that does not have
them and omits a format change altogether. And at 141,627 words the documents are long because the same facts are told up to eight
times, with history and self-defence woven into the reference, so a correction has many places to miss, and several already missed.

### Scope covered

**Built:** `sphinx-build -W --keep-going -b html docs SCRATCH/pass-4/html`, with the system python's sphinx (the review venv has no
`docs` extra), `dot` 15.1.1 and plantuml through `JAVA` and `PLANTUML_JAR`. It **passes under `-W`** (`sphinx-build.txt`), 28 pages. Graphviz was
present, so nothing was left undrawn.

**Read in full, with line numbers:** `README.md`; every page `docs/index.rst` reaches: `getting_started`, `concept`, all nine of
`file_formats/`, `consistency_checks`, `comparing_deliveries`, `plugins`, `generated_artefacts`, `templates`, `command_line_interface`, `toolbox`,
`build_integration`, `editor_integration`, `gui_security`, `data_contracts`, `data_dictionary` (their prose; the generated model reference only by
headings), `developer_documentation`, `faq`, `acronyms`; `docs/conf.py`; `SECURITY.md`; `editors/vscode/README.md`; `CHANGELOG.md:1-240` and
the `## 0.11.0` section by its diff against the tag; `SPEC.md`'s structure, sections 1, 3.6 and 7 to 7.3; `gui/src/app/App.tsx`, `gui/src/lib/route.ts`, and of
`gui/src/screens/`: `GraphPage`, `StartPage`, `ProjectPage`, `UndoStrip`, `FindingsPage`, `ComparePage`, `ComponentPage`.

**Read by their user-visible strings only (pass 3 read them whole):** the other twelve screens and their views (`gui_strings.py`, `inv/gui_strings.txt`).
**Read in part:** `src/ddd/plugins.py:1-240`, `src/ddd/gui/server.py` (header, `run`), `cmake/Ddd.cmake:395-474` and its keywords, the headings of
`tests/test_documentation.py`, `docs/superpowers/specs/2026-09-17-web-gui-design.md` 60-160 and 498-537, the "Left open" of every plan (searched for documentation items).
**Not covered:** the older sections of `CHANGELOG.md`; whether each sentence is right, except where a gap and a wrong sentence are one thing (passes 5 to 20); `docs/superpowers/` beyond the above.

**Run:** the inventories (`inventory_cli.py`, `inventory_checks.py`, `inventory_schema.py`, `shape.py`, `linkcheck.py`, results in `inv/`); `ddd gui` on a scratch copy of
`examples/demo`, walked headless in Edge (`walk.cjs`, `shots/walk.txt`, 17 screenshots in `shots/`; no edit applied); the tutorial's commands under
PowerShell 5.1 and cmd (`inv/windows-tutorial.txt`); a half migrated project through gcc (`inv/half-migrated.txt`); `git` and `gh api` for the changelog and the tracker (`inv/evidence.txt`). The tree is untouched.

### Strengths

- **Tool against documents, the reference is complete and mostly held by tests.** See the inventory below: 72 of 72 checks have a table row at the registry's severity (`inv/checks.txt`),
  `tests/test_documentation.py:192-301` keeps them there; 15 of 15 `elf-*` findings (`docs/toolbox.rst:198-258`); the CLI reference is generated from the parser and every option also has prose;
  the file format pages are generated in part from the models.
- **The commands shown really run.** `tests/test_transcripts.py` re-runs 122 of the 173 commands shown and says out loud how many it does not (`:424-441`, 51). That is unusual honesty, and the tutorial is the better for it.
- **The site builds clean and links clean,** one link apart (M1). `-W` is meant and kept.
- **Good pages exist, and they show what the others could be.** `docs/toolbox.rst` (1,388 words): what it does, an example, a table of where each key comes from, a table of findings. `docs/file_formats/conversions.rst`, `units.rst`, `sections.rst`;
  `docs/comparing_deliveries.rst`'s worked example over shipped deliveries; `docs/getting_started.rst` as a narrative. `docs/faq.rst` asks real questions and answers them.
- **The rationale a future maintainer needs is written down.** `docs/developer_documentation.rst:255-283` records what was tested against CANape; `:765-867` is a precise account of the release and of what guards it.
- **Trust is stated where it counts for the editor:** `docs/editor_integration.rst:212-225`, `editors/vscode/README.md:50-56`, `docs/plugins.rst:245-257`, `docs/templates.rst:73-85` (for the rest see pass 1 I15).

### Issues

#### Critical

None. No gap here produces wrong output by itself. The nearest, nothing warning that `ddd gui` over a collected project loses work, is pass 1 C4's; its documentation half is in I1.

#### Important

- **I1. `ddd gui` has no guide; its one account is a single table cell of the command line page (KNOWN: "part 20").** `docs/command_line_interface.rst:294-567`, `docs/index.rst:25`. KNOWN: `docs/superpowers/specs/2026-09-17-web-gui-design.md:147,509`, `2026-09-30-gui-large-projects-design.md:20` ("the user guide: every screen, with its screenshots"), `2026-10-21-gui-journeys-remaining-design.md:230`. Graded as I would grade it myself.
  *Trigger:* somebody is asked to use `ddd gui` and opens the site. The sidebar's only entry with "GUI" in it is *GUI security* (`index.html`, by script). `concept.rst`, `getting_started.rst`, `faq.rst` and `index.rst`'s prose never name it. The account they eventually reach is row 11 of a `list-table`: 3,960 words of the page's 7,771 (51 %), 274 source lines, no heading, no anchor (`#ddd-gui` lands on the argparse help), no screenshot. It runs from "The project opens on a graph" to refusal sentences quoted verbatim and benchmark figures (`:533-544`, "Measured on a developer's desktop over a generated project of 100,000 declarations").
  *Evidence of what it does not give:* its words follow the order of the plans, not of a reader's questions: Files tab 93 lines, Shared files 57, large projects 35, Units half a sentence, Types 3, Graph 7. Twenty things a reader meets on screen are missing or get one clause, the table below; "Tidy", "Search modules", "Adopt" and "Add to the vocabulary" appear in no document at all (`inv/evidence.txt`, `inv/gui_strings.txt`). A person who wants to know whether a project's units can be adopted finds the answer only in `CHANGELOG.md`'s `## 0.11.0`, whose first bullet (2,139 words) is the other half of the de facto guide.
  *Who:* everybody asked to use the GUI, which is its purpose: "developers who would rather not edit JSON" (`CHANGELOG.md:247`), the readers least able to reverse-engineer a table cell. *Where:* a new `docs/gui.rst`, "The browser interface", under *Using DDD* ahead of the security page: what it is and when to use it, starting it, a tour by task (settle a disagreement, edit a curve, adopt a vocabulary, undo, compare), one short section per tab, what it writes and when, working beside an editor and a build, what it cannot do. The CLI row shrinks to four lines. The refusal sentences go (they are the page's to say, and a test's to pin), the timings go to the developer page. *Size:* M, two to three days, about 2,500 words and ten screenshots, which the Ladle stories or the journeys already produce. I would not wait for the last screens: the row is already written and growing.

- **I2. No page tells a project with existing code how to adopt DDD, and the natural first step fails at the link.** `docs/toolbox.rst:11` ("A project that adopts DDD rarely starts from nothing"), `docs/consistency_checks.rst:119-120`, `docs/concept.rst:317-320`; compare pass 1 I13.
  *Trigger:* one component is described, as `consistency_checks.rst:120` allows ("a project being migrated onto DDD"), and reads a global the old code still defines. `ddd generate c` stops on `missing-producer`; with `-W missing-producer=ignore` DDD writes a definition of that global too, under `<unresolved>`, and the image fails: `multiple definition of 'LegacySpeed'` (reproduced, `inv/half-migrated.txt`). `concept.rst:318-320` says the opposite: "such a project would link only if some hand written translation unit happened to define the symbol". Nothing says that a template can skip that group, and pass 1 I13 is the deeper point: the model cannot state "defined elsewhere".
  *What exists:* `ddd tool from-elf` to get first declarations, `-W file-extension=warning` to rename gradually, a sentence on `unknown-unit` (`units.rst:49-50`). *What does not:* an order of work; what happens to hand-written `extern`s and definitions; whether components can move one at a time, and how; what a hand-maintained a2l and the datasets keyed on it become; how to take the first baseline. A search for `migrat`, `existing project`, `existing code` and `adopt` finds only sentences like those.
  *Who:* every real integrator, since greenfield is the exception. *How badly:* they must discover the path, and hit a link error on the way. *Where:* new how-to, `docs/adopting.rst`, after Getting started. *Size:* M. It needs an answer to pass 1 I13 first, or at least the template workaround stated and an example project.

- **I3. Nothing tells an integrator how to get from the generated a2l to a connected tool (KNOWN: P10-M13, "documented as a reader obligation", which did not happen; see pass 1 I8).** `docs/file_formats/rasters.rst:126-133`, `docs/faq.rst:612-618`, `docs/acronyms.rst:147-151`, `docs/file_formats/sections.rst:98-103`.
  *Trigger:* an integrator generates the a2l and loads it to measure over XCP. The pages say three times that the module's `DAQ` block, `PROTOCOL_LAYER` and transport "come from whatever configures the XCP stack", and stop. **`A2ML` and `EPK` appear in no document** (`inv/evidence.txt`), `MEMORY_SEGMENT` only as "planned". The file says `DO NOT EDIT`, a rerun overwrites a patched copy, and no page says what to add, where, or how a build merges it. `concept.rst:236` goes further ("There is nothing for a project to decide there").
  *Who:* everyone who calibrates, which is what the a2l is for. *How badly:* stuck at the last step, with no pointer. *Where:* a section "Taking the a2l to a calibration tool" on `generated_artefacts.rst`: what a tool needs, what DDD writes, what the project adds, a build step that assembles them, what was tested with which tool and what was not. *Size:* S to state what is absent, M with a recipe proved on a tool (pass 1 open question 7).

- **I4. The tutorial's `ddd id --assign` step fails on Windows, and no page says its transcripts are a POSIX shell.** `docs/getting_started.rst:262`, `docs/comparing_deliveries.rst:156`; against `README.md:68` ("on Windows and Linux") and `docs/getting_started.rst:15-16` ("needs nothing but python").
  *Trigger:* `ddd id --assign components/*.ddd.json` in PowerShell or cmd, neither of which expands the pattern. *Observed:* `components\*.ddd.json: not readable as json, skipped`, `wrote 0 ids`, exit 1 (reproduced, `inv/windows-tutorial.txt`), where the page shows `wrote 2 ids`. The message sends the reader to the wrong problem. `getting_started.rst:61` and `README.md:79` (`PYTHONPATH=src python -m ddd`) are bash too. The suite cannot see it: `tests/test_transcripts.py:333` runs every transcript through `bash`, on the Windows cells as well.
  *Who:* every Windows newcomer, on one of the two supported platforms, in the first ten minutes. *Change:* have `ddd id` expand a pattern the shell left unexpanded (as `includes` already does) and say that the transcripts are bash, with the one PowerShell spelling that differs. *Size:* S.

- **I5. There is no account of how the GUI is put together; a contributor cannot find where a new endpoint or screen goes.** `docs/developer_documentation.rst:899-1201`, extending pass 2 I5 and pass 3 I7.
  *Evidence:* the section is 3,747 words under one heading, in the order the features were added ("The edit engine learnt one thing for adoption", `:1173`; "`ddd.variables.narrowed` is gone", `:1133-1134`). `contract.py`, `queries.py` and `routes.py`, the wire's three definitions, appear **zero** times; so do `gui/src/app`, `screens`, `components` and `generated` (`src/api`, `src/lib`, `src/state` once, as a coverage list, `:939`). The long poll: one passing mention, in a paragraph on a test helper (`:1008-1009`). Revisions: three passing mentions. The page's own rules, "no decision in a tsx", `*View` as a picture of its props, TanStack Query, `useKept`, never `waitForResponse`, are on the page zero times and on 13 to 213 lines of the plans each (`inv/evidence.txt`). What it has instead: a 556-word paragraph on e2e helpers (`:976-1011`), and three shells' spelling of a variable for a mapped drive journey (`:956-974`).
  *Consequence:* the code a contributor is likeliest to touch, 29,645 of 55,423 lines counting four groups (page 21,065 and server 8,580, against edit layer with language server 11,185 and core 14,593), has its only overview in a record of milestone 1 (`specs/2026-09-17-web-gui-design.md:68-99`) and is otherwise learned by failing tests.
  *Where:* the section split: The pieces (that diagram, brought up to date); A request's life (server, session and revisions, api, plan, preview, apply); Adding a route; Adding a plan; Adding a screen (`lib`, `screens`, `*View`, stories, journeys); the page's rules. The helpers move into `gui/e2e/` beside what they describe; the layer table takes pass 2's target. *Size:* M.

- **I6. A contributor is not told how to set up, nor what a change has to touch.** `README.md:995-1003`, `docs/developer_documentation.rst:392-402`.
  *Evidence:* both start at `python -m pytest`. `pip install -e ".[dev]"` appears once, as a fact about ci (`:535`). There is no `CONTRIBUTING`, no pull request template. `CHANGELOG` is named on the developer page **zero** times; `SPEC.md` once, as what a test reads (`:322`), although `README.md:1055` calls it binding and every feature so far changed it. "Anyone adding a check" (`:246-253`) names the registry and the code, and not the README row, the SPEC row and the reference row the suite will then demand (`tests/test_documentation.py:194-198,295`). There is a walk for an output format (`:195-233`) and none for a key, a file kind, an option or a route.
  On Windows, two things stop the first run and neither is stated: `bash` must be Git Bash (under PowerShell it resolves to WSL and the transcripts fail) and `tests/test_lsp.py:6526` needs the symlink privilege. The page says "Nothing in the suite skips" (`:416`), so the reader takes the failure for a real one.
  *Who:* every new contributor. *Where:* "Working on DDD" at the top of the developer page, or a `CONTRIBUTING.md` pointing at it: clone, venv, install, first green run per platform, then a table of what each kind of change touches. *Size:* S, half a day.

- **I7. The changelog files features under a release that does not have them.** `CHANGELOG.md:345,356,371,389`, inside `## 0.11.0` (`:235-458`); against `README.md:40-41` ("says what changed in it").
  *Trigger:* a reader on 0.11.0, the site's `stable` (`versions.json`, fetched), reads "A sixth tab, Compare" (`:371`), pasting a table (`:345`), the plot (`:356`), the mismatch button (`:389`). `git ls-tree v0.11.0 gui/src/screens/` holds no `ComparePage.tsx`, and `git show v0.11.0:CHANGELOG.md` holds none of the four (`inv/evidence.txt`): PRs #61, #63, #64 and #65 were merged after the tag and their entries written into the released section (`git diff v0.11.0 2b4bae6c -- CHANGELOG.md`, hunks at 342 and 410). A reader of `## Unreleased` learns none of them is new. *Change:* move them. *Size:* S.

- **I8. Two whole tabs and a format change have no changelog entry at all, and `## Unreleased` says nothing of what a user must do.** `CHANGELOG.md:7-15`, `:17-234`, `:467`.
  *Evidence:* the file's own rule is that a release changing a check identifier or a file format "says here what the migration costs" (`:7-11`), and that an entry costing anything "ends with **Migration:**" (`:467`). `empty-vocabulary` is a new check identifier and a format change, by `39f77bab`, PR #72: `minItems` left all five vocabulary schemas, a file that was refused now loads, and a units file listing nothing now opts a project into `unknown-unit`. **`empty-vocabulary` occurs nowhere in the changelog** (`grep`, `inv/evidence.txt`). The Shared files tab (PRs #67, #69, #71) and the Files tab (#73), with everything they write (`constants.ddd.json`, New file, Add a file, Remove), have no entry: "Files tab" occurs only in two later fixes (`:34,52`).
  `## Unreleased` holds 28 bullets, 25 of them about the preview GUI (`net::ERR_NO_BUFFER_SPACE` among them), and 0 `Migration:` lines, though `pyelftools` is a new runtime dependency that an air-gapped install has to bring (M3) and the bullet says only "No file format changes". *To the pass's question:* no. It does not tell a user what they must do, and does not say "nothing" either; they read 218 lines to find out. *Change:* add the entries, a one-line *What to do* at the top of the section, the preview's fixes under one sub-bullet. A test that every registered check is named in the changelog would have caught `empty-vocabulary`. *Size:* S.

- **I9. The SPEC calls itself the authoritative contract and gives the largest part of the tool two clauses.** `SPEC.md:785,2134-2137`; `README.md:1055-1058`, `README.md:13`.
  *Evidence:* the SPEC covers everything else to the last key (table below). `ddd gui` is "editing a project's description files in a browser ... a preview whose options are not yet part of this interface", and one mention in 3.6. The decision recorded (`specs/2026-09-17-web-gui-design.md:505`) was about *options*. There is no sentence on what it writes, when, in what layout, what a refusal is, what undo guarantees, what the server defends, or the edit engine. So there is nothing for "does it work" to be held to: passes 12 to 16 measure against a table cell, a security page and the plans.
  *Consequence:* the 29,645 lines of I5 are outside the contract, and the README's sentence "states ... the command line and the generated artefacts this implementation is measured against" reads as if not. *Change:* the maintainer's call (open question 1): a section 7.4 with what a project may rely on (at the least: only `Apply` writes, what is written and where, what is refused, the trust model), or a plain sentence that the preview stands outside the contract until `preview` is removed. *Size:* S for the sentence, M for the section.

- **I10. The same facts are written in up to eight places, the README is not the short version it says it is, and the suite forbids it from being one.** `README.md:38` ("This README is the short version"), `tests/test_documentation.py:194,385,590`.
  *Evidence:* the README is 1,058 lines, 9,762 words, with the full check table, comparison table, command table and key tables, and the suite requires every check, command and common key to be there, so it cannot shrink. The `volatile` essay is told at `README.md:411-447`, `getting_started.rst:225-235`, `concept.rst:338-349`, `variable_definition.rst:71-89,457-461,566-577`, `generated_artefacts.rst:412-510`, `component.rst:231-237,353-363`, `consistency_checks.rst:846-855`, `comparing_deliveries.rst:287-296`, about 230 lines. The eight fixed checks are listed on six pages, `--const-inputs`' constraint violation on five, `NO_PROPAGATE_HEADERS` on three, the docker `gui` service on three.
  *Consequence, already measured:* the copies have parted. `--image` did not reach five pages (M2); the language server's newer renames did not reach the SPEC and two READMEs (M11); `pyelftools` reached the README and not the tutorial (M3); pass 1's I7 (the `.rodata` claim, false on gcc 13+) and C1 (`--const-inputs`) now each need the same correction on five or six pages. Tests hold counts and names together, not meaning.
  *Change:* one home per fact, everything else a link. A README of about 150 lines (what it is, install, quick start, where everything is); the name tests move from the README to the reference pages, which already have them. *Size:* M, mostly deletion, plus the maintainer's yes (open question 3).

#### Minor

- **M1. The home page's "Module Index" is a 404.** `docs/index.rst:41`. The site documents no python module, so `py-modindex.html` is not built, and `-W` does not notice (reproduced, `inv/linkcheck.txt`: the one broken internal link of 30 pages). Delete the line. S.
- **M2. `--image` did not reach five pages.** `docs/acronyms.rst:66-70` ("DWARF ... DDD does not read it"), `:233-236` ("until an address map supplies"), `docs/faq.rst:553-565` (zero is what a run gets with no `--address-map`, and "keeps address zero silently", against the warning shown at `:517` and `:527`), `docs/getting_started.rst:532-535`, `docs/file_formats/types.rst:333-336`. Read off the lines. S.
- **M3. The tutorial's dependency list is wrong and an air-gapped install has no recipe.** `docs/getting_started.rst:21-24,31-33` ("its only runtime dependencies are pydantic ... and jinja2", "apart from pydantic and jinja2"), `docs/developer_documentation.rst:631`; `requirements.txt` has three, `README.md:52-53` says so. `README.md:57`'s "from a delivered wheel, no network" fails on the dependencies, and no page gives `pip download` plus `--no-index --find-links`. Who: the firewalled builds the sentence is addressed to. Read off the lines. S.
- **M4. The component page teaches what another page calls a mistake.** `docs/file_formats/component.rst:450-491` checks a component with `-W missing-producer=ignore` and never names `--standalone`; `docs/consistency_checks.rst:220` says "Naming the overrides by hand instead is the mistake the flag exists to end". A component author reads this page first. Read off the lines. S.
- **M5. "The exit code is the same everywhere" has two exceptions no page gives.** `docs/command_line_interface.rst:150,182-187` (130 for Ctrl-C). `ddd gui`, whose normal end is Ctrl-C, returns 0 (`src/ddd/gui/server.py:1051-1057`); `ddd lsp`'s 0 or 1 by whether `shutdown` came first is in `SPEC.md:2460-2463` alone. Read off the lines. S.
- **M6. How to bind a file to its schema is in the README and not on the site.** `README.md:119-138,258-272`; `docs/file_formats/index.rst:118-124` says an editor "can offer completion" and not how, `docs/editor_integration.rst` has no `$schema`, `docs/plugins.rst:276` assumes it, and the commit-or-generate choice is README-only. The README's "full documentation" is missing what its short version has. Who: every component author, lightly. Where: a section "Validation while typing" on the editor page. S.
- **M7. No recipe for a build that is not CMake.** `docs/build_integration.rst:8` ("Two integrations are shipped"), against `docs/concept.rst:402` and `command_line_interface.rst:717`. The pieces are scattered: `ddd sources`, the two runs, `ddd build-info` for the editor (`command_line_interface.rst:568-572`), compile the definitions as objects not a static library (`build_integration.rst:398-402`), the include rule. Who: Make, IDE-managed and older-CMake builds, of which embedded has many. Where: "Without CMake" on that page, a tested Makefile of about 40 lines. S.
- **M8. The tutorial stops before a compiler, and does not say the rest exists.** `docs/getting_started.rst:597-619`, `docs/index.rst:4-7`. It ends at generated files. No page shows hand-written C using them: `examples/cmake/components/controller.c` is named by no page, and "reads a curve, a structure member, an enum" has no snippet. "Where to go next" names neither the build integration, the editor nor the GUI, and `index.rst` offers no path by role. Where: a page "From description to linked image" over the thermostat (two `.c`, a `CMakeLists.txt`, a linked a2l); three lines in *next*; role paths in the index. S to M.
- **M9. No "upgrading DDD" how-to.** Scattered: re-run `ddd schema all` (`README.md:263`), reinstall the `.vsix` (`editor_integration.rst:258`), the module refuses another release (`build_integration.rst:37`). The copied templates have nothing: `docs/templates.rst:476` ("Nothing refers back"), though a copy taken before sections existed silently places nothing, the attribute being the template's (`examples/templates/ddd_globals.c.jinja2:4`). Add "diff your copy against `ddd templates-dir`". Where: FAQ or Getting started. S.
- **M10. The editor page has no trouble-shooting, and no recipe for the editors it names.** `docs/editor_integration.rst:34-36`, `README.md:151`, `editors/vscode/README.md:10`: Neovim, Helix and Emacs "need only the command", with no filetype pattern or snippet. "Announced as log messages" (`:179`) does not say where; no page answers "no squiggles appear" (not trusted, not on the `PATH`, no record found). S.
- **M11. SPEC 7.2 and both READMEs stop at variables, types and constants.** `SPEC.md:2353-2362`, `README.md:212-224`, `editors/vscode/README.md:91-95`, against `docs/editor_integration.rst:91-122,154-158`: renaming a unit, a section and a raster, and `unknown-unit`'s two quick fixes, are in the "authoritative contract" nowhere. The server does them (`src/ddd/lsp/server.py:727-791`). S.
- **M12. `SPEC.md:2215` says the dictionary format is "today `8`"; it is 9 (KNOWN: `SCRATCH/pass-1-2026-09-24.md:65`).** `src/ddd/ir.py:645`, `docs/data_dictionary.rst:228`. Left to pass 5. S.
- **M13. Whether the plugin api is public is not stated.** `README.md:42-46` and `CHANGELOG.md:7-11` list the public interface without it, though `docs/plugins.rst:120-121` promises "without breaking a plugin written against the previous version" and a plugin imports `ddd.plugins`, `ddd.diagnostics`, `ddd.backends`. A plugin author cannot tell what may change. Open question 4. S.
- **M14. `examples/` and `gui/` have no README.** Ten example directories, and no page or file says which shows what; the mentions are spread over the README and the pages. A table in `examples/README.md`; a pointer in `gui/README.md`. S.
- **M15. The glossary has holes.** `docs/acronyms.rst`: no LSP, A2ML or EPK; `concept.rst`'s vocabulary has none of the words the GUI and its refusals use (plan, revision, stale, Apply). S.
- **M16. Three environment variables are documented only in code.** `docs/conf.py:102-103` (`PLANTUML_JAR`, `JAVA`; `developer_documentation.rst:674-681` says only that both programs are apt packages, which leaves a Windows contributor at a warning per diagram), `gui/scripts/schemas.mjs:13` (`DDD`). `BROWSER`, read through `webbrowser` (`src/ddd/gui/server.py:1048`), is named only as a test fixture (`developer_documentation.rst:1015`), though `gui_security.rst:237` tells the reader to use "a browser profile of its own" without saying how: `--no-browser` and paste, or `BROWSER`. S.
- **M17. The security page does not say what the reader should do.** `docs/gui_security.rst`. It is a threat model and a list of limits; one bullet (`:47-106`) is 933 words on byte counts and refusal codes. The instructions a user needs are spread over it: paste rather than click (`:136-138`), open pages from the printed address (`:182-183`), publish on loopback (`:188`), a browser profile of its own (`:237`), the terminal's reused-code line means restart (`:217-223`), plugins run (`:126-127`). Add "What you should do", six lines, on top; move the limits to the end, or a reference. S.
- **M18. Reference is mixed with history and with defence of itself.** Examples in *Page shape* below. An editing pass, S to M, no decisions needed.
- **M19. Pages whose order or size stops a reader.** `docs/templates.rst` argues to `:86` (Why the templates belong to the project, The a2l file is not templated, Why jinja2, A template directory is code) and its *Getting started* is at `:449` of 507. `docs/generated_artefacts.rst` is two pages (c, a2l) of 1,374 lines, with a 100-line essay. `docs/developer_documentation.rst` has no working-on-it section and 410 lines on ci and publishing (`:485-897`). `docs/data_contracts.rst` renders to 2.4 MB, 49 % of the site, and its prose restates `file_formats/index.rst`. S to M.
- **M20. The design records' status lines have regrown wrong, and the documents depend on the records (KNOWN: 2026-09-15 pass 7 Minor 5).** `docs/superpowers/specs/*.md`: of 32, 14 have no status and 12 say "to be planned" or "not implemented" of merged work (`2026-09-24-gui-paste-design.md:4`, `2026-09-30-toolbox-from-elf-design.md:4`). `docs/developer_documentation.rst:1055,1091` send a reader there for what "findings-heavy" means and for the figures; `src/ddd/toolbox/from_elf.py:4`, `src/ddd/gui/queries.py:7`, `tools/*.py`, `gui/src/styles/*.css` cite them too, and the sdist excludes them (`pyproject.toml:105`), so for its reader they dangle. `gui/src/stories/fixtures.ts:1577` cites `.superpowers/sdd/...`, in no repository. See pass 2 M9, pass 3 M10. S.

### Status of the 2026-09-15 findings in this area

The rest of that review's pass 7 is plainly fixed on this tree: the issue tracker (`gh api`: `has_issues: true`), the FAQ's array bound (`docs/faq.rst:620-667`), "nothing skips" (`developer_documentation.rst:416`), the README's stale transcript and relative links, the interface sentence, the environments paragraph (`:847-858`).

| finding | one line | status | where |
| --- | --- | --- | --- |
| P7 Minor 5 | design records carry a stale status line | STILL OPEN: the four named are fixed, 26 new | M20 |
| P7 Minor 2 | the developer page's layers omit a whole subsystem | REGRESSED in kind: `lsp` was added, `gui` and 20 root modules are absent | pass 2 I5; I5 here |
| P7 Minor 10 | acronyms the pages use and the page lacks | fixed as listed; drift since: LSP, A2ML, a stale DWARF row | M2, M15 |
| plan 2026-09-16, Left open | README in-page anchors resolve on GitHub alone | KNOWN, still open: `README.md:69,266,294,364,1045`; not reachable from here to test PyPI | Minor, unfiled |
| plan 2026-09-17, Left open | SPEC 3.6's "(`ddd gui`, section 7)" is plain text | KNOWN, still open: `SPEC.md:785` | trivial, unfiled |

### Open questions

1. **Is `ddd gui` inside the SPEC?** Yes: a section 7.4, and passes like 12 to 16 get a contract, at M. No: one sentence saying so, and `README.md:1055-1058` is true again, at S. I would write the small section now, on what a project may rely on, and let screens stay out.
2. **Where do the design records live?** Off the site in any case. On master, as they are; on master with an index and without the binaries (my choice, below); or on an orphan branch, which is cleanest for readers and needs the citations of M20 gone first.
3. **Does the README stay exhaustive?** The suite makes it so (`tests/test_documentation.py:194,385,590`). If it may become short, I10 is mostly deletion, and PyPI's page, which shows the README, gets shorter too. If it must stay, take "the short version" out of its sentence.
4. **Is the plugin api public?** If yes, add it to `README.md:42-46` and `CHANGELOG.md:7-11`, and a change to a context becomes a migration line. If not, say so on `docs/plugins.rst`.
5. **When is the GUI guide written?** The plans have it at part 20, after journeys it no longer depends on. I would write it now without the screenshots: its absence is what the row's growth is compensating for, and a pilot's readers need it first.
6. **The a2l recipe needs a tool (I3).** Somebody with CANape or INCA has to prove one; the same hour as pass 1 open question 7.

### Test gaps

- Nothing holds `CHANGELOG.md` to the public interface: a check added to the registry with no entry passes (`empty-vocabulary`). `TestTheReleaseNote` (`tests/test_documentation.py:1517`) checks counts in an entry, not presence. Registry against changelog is ten lines.
- Nothing notices an edit to a released section: a test comparing the section under each tag with `git show <tag>:CHANGELOG.md` would have caught I7, or a rule in the release walk.
- `tests/test_transcripts.py:333` runs everything through `bash`, so no page's command is ever tried under the shells of a supported platform (I4).
- `-W` does not check generated links: the 404 of M1 passes. `sphinx-build -b linkcheck` restricted to internal links, or `SCRATCH/pass-4/linkcheck.py`'s 40 lines, would.
- 51 of 173 commands shown are not run (`tests/test_transcripts.py:424`, disclosed), 14 of them in `faq.rst`, where the staleness of M2 sits; the prose around a run command is not compared at all.
- Nothing ties the GUI's tabs (`gui/src/app/App.tsx:29-38`) or routes-as-screens to a page. `tests/test_gui_docs.py` holds the route table to the server (good, 36 of 36); once a guide exists, the same for its tabs.
- `tests/test_documentation.py` holds names, not meaning: all of I10's parted copies pass.

### Assessment

The documentation answers "what exactly does this key, check or option do?" better than almost any tool of this size: the inventories are close to complete and the tests keep them so. It does not answer "how do I do this?", and for the largest part of the tool it does not answer "what is this?". Its readers are served in the order the documents were written: a component author very well, an integrator on CMake well until the a2l leaves the build, a newcomer on Linux well for ten minutes, a contributor on the release machinery in depth and on the GUI not at all, and somebody asked to use `ddd gui` with one table cell. Most of the twenty minor findings, and I4, I6, I7 and I8, are half a day's work or less. The one structural step is to give each fact one home and to accept a short README, because the length is not padding but repetition, and the repetition has started to contradict itself. What would change most for the least: the GUI guide from text that already exists (I1), a Windows line and the contributor's first section (I4, I6), the changelog put right before the next release (I7, I8).

#### What is missing, ranked by how many people it stops and how badly

| # | What is missing | Who | How badly | Where it should go | Size | Finding |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | A guide to `ddd gui` | everyone asked to use it | cannot find what exists; no picture; no limits | new `docs/gui.rst` | M | I1 |
| 2 | How to adopt DDD in a project with code | nearly every real project | no path, and a link error on the first step | new `docs/adopting.rst` | M | I2 |
| 3 | From generated a2l to connected tool | everyone who calibrates | stuck at the last step | section on `generated_artefacts.rst` | S-M | I3 |
| 4 | Windows in the tutorial | every Windows newcomer | fails at the id step, wrong message | `ddd id`, `getting_started.rst` | S | I4 |
| 5 | How the GUI is put together | every GUI contributor, over half the code | learned from plans and failures | `developer_documentation.rst` | M | I5 |
| 6 | Set-up and definition of done | every new contributor | stalls, then finds out by failing tests | top of the developer page | S | I6 |
| 7 | Honest release notes | every upgrader | misled on 0.11.0; `empty-vocabulary` unannounced | `CHANGELOG.md` | S | I7, I8 |
| 8 | What a project may rely on from the GUI | maintainers, reviewers, then users | nothing to test it against | `SPEC.md` 7.4, or one sentence | S-M | I9 |
| 9 | One home per fact | all, indirectly | contradictions spreading | README, all pages | M | I10 |
| 10 | Schema binding on the site | every component author, lightly | a detour to the README | editor page | S | M6 |
| 11 | A first linked image, and C using the headers | newcomers, component authors | stops at generated files | new short page | S-M | M8 |
| 12 | A build without CMake | Make and IDE builds | assembles it from six places | `build_integration.rst` | S | M7 |
| 13 | Upgrading DDD | every project, once a release | steps scattered; copied templates unmentioned | FAQ or tutorial | S | M9 |
| 14 | Air-gapped install | firewalled builds | wrong list, no recipe | `getting_started.rst` | S | M3 |
| 15 | Rules for a GUI user on security | GUI users | buried in a threat model | top of `gui_security.rst` | S | M17 |
| 16 | Editors other than VS Code; trouble-shooting | a minority | works it out | editor page | S | M10 |

#### Tool against documents

Documented rows are summarised. Every row marked missing is listed.

| Inventory | The tool has | Documented | Where |
| --- | --- | --- | --- |
| commands | 21, nested ones included (`inv/cli.txt`) | 21 | CLI table, generated reference, README, SPEC 7 |
| options | 26 distinct, 90 argument rows | all | generated reference; each also in prose (`-b`, `-o` by their short form) |
| checks | 72: 8 fixed, 9 project, 13 comparison | 72, severities equal | `consistency_checks.rst`, README, SPEC 4 |
| toolbox | 1 tool, 15 findings | all | `toolbox.rst`, SPEC 7.3 |
| CMake | 18 keywords, 7 targets, `DDD_A2L`, `DDD_DICTIONARY`, `DDD_JSON`, `DDD_EXECUTABLE` | all | `build_integration.rst`, SPEC 7.1. Internal properties rightly not |
| file kinds and keys | 8 schemas, 153 key rows (`inv/schema.txt`) | 152 in prose; `cycle_ns` in the generated reference only | `file_formats/*`, `data_dictionary.rst`, SPEC 3 |
| other files | `ddd-build.json`, `.ddd-manifest.json`, `renames.json`, address map | all | build, artefacts and compare pages, SPEC |
| exit codes | 0, 1, 2, 130 | yes, but for M5 | `command_line_interface.rst:150-187`, `consistency_checks.rst:959-986` |
| LSP | sync, diagnostics, definition, references, hover, rename with prepare, quick fixes, watched files, log messages; 2 settings, 1 command | all | `editor_integration.rst`; SPEC and READMEs lag (M11) |
| plugin api | `Plugin` 7 fields, 3 contexts, `bag`, `locate`, `GeneratedFile` | all | `plugins.rst`, SPEC 3.11 |
| gui routes | 36 | 36, test-held | `gui_security.rst:269` |
| environment | 18 variables read | 14 | build page, README, developer page. Missing below |

| Environment variable | Read by | Status |
| --- | --- | --- |
| `PLANTUML_JAR`, `JAVA` | `docs/conf.py:102-103` | **missing**: a comment in `conf.py` only |
| `DDD` | `gui/scripts/schemas.mjs:13` | **missing**: the script's comment only |
| `BROWSER` | python's `webbrowser`, `src/ddd/gui/server.py:1048` | **missing for a user**: named only as a test fixture |

**`ddd gui`.** Documented, 20 items: address, one-time code, token and gate (`gui_security`); the graph's arrows, the Table, Findings as a list, a settlement button, the variable's panel, adding and removing a declaration, values grid, paste, plot, a scalar type's change and rename, undo, Compare, Shared files, Files, what is served (bounds), large-project behaviour, options (all `command_line_interface.rst:294-567`). Missing:

| Screen, action or state | Source | Status |
| --- | --- | --- |
| Start page: `Open a project`, `Found under`, "built as", `Build records not used`, none found | `screens/StartPage.tsx` | `--help` one clause; the rest **missing** |
| Masthead: `Projects`, switching project, what happens to undo | `app/App.tsx:292-298` | **missing** (`developer_documentation.rst:1192` in passing) |
| Graph: `Search modules` (fades the rest, Enter centres) | `screens/GraphPage.tsx:327-336` | **missing**, no document names it |
| Graph: `Tidy`, `Fit`, zoom | `:337-338,383` | **missing**, no document names them |
| Graph: dragging, positions kept per browser | `state/positions.ts` | **missing** |
| Graph: what an arrow's number and colour mean, and a click: one object opens it, several ask which, agreeing opens nothing | `:285-304` | colour one clause; the rest **missing** |
| Graph: `no dictionary, so its modules are drawn without arrows` | `:96-100` | **missing** |
| Units: `Adopt N units`, `Show changes`, `units.ddd.json` | `components/AdoptBannerView.tsx` | **missing**; changelog only |
| Unit panel: places, rename and merge, description, add, remove | `components/UnitPanelView.tsx` | "maintaining its vocabulary"; changelog only |
| Types: structures, externals, members table, description; that nothing can be created there | `components/TypePanelView.tsx` | scalar change and rename only; the rest **missing** |
| Findings: `missing-id` fix from the panel, its link and notes, "no longer reported" | `components/FindingPanelView.tsx` | **missing** for a user; `developer_documentation.rst:1127` |
| Component page: Unit cell opens the picker, chips, `Findings in this component`, "no longer declared" | `screens/ComponentPage.tsx` | **missing** |
| The one pattern everywhere: plan, `Show changes`, `Apply`, a refusal held until the next revision | every panel | case by case; no statement |
| Working beside an editor: the page follows files on disk, about once a second; a half-saved file reads `did not load` | `gui/session.py` | **missing** for a user |
| What it writes and when: only on Apply, no git, what the browser keeps (token, positions) | | "in their own layout"; the rest **missing** |
| A project CMake collected: which file opens, where New file writes | pass 1 C4 | **missing**: no warning anywhere |
| What it cannot do: create a type, edit members, change scope or kind, `condition`, the `a2l` block, `extensions`, the raw text of a file that does not parse | `lsp/edits.py:64` | **missing** |
| Which browsers it is tried on (Chromium, Edge) | `ci.yml` | security page by header only; `developer_documentation.rst:496` |
| What `preview` means, and what is planned | `app/App.tsx:290` | "options not stable"; plans only |
| Stopping it: Ctrl-C, exit 0 | `gui/server.py:1051` | "until interrupted" (M5) |

**For a contributor.**

| Question | Developer page | Instead |
| --- | --- | --- |
| Set up a checkout | **missing** | a sentence about ci, `:535` |
| What a change has to touch (SPEC, changelog, README, schemas) | **missing**, but for two walks | failing tests |
| GUI server, session, api, contract, queries, routes | **missing** | milestone 1's spec, 4.1 and 6.3-6.5 |
| Where a new endpoint goes | **missing** | failing tests (`test_gui_docs`, the contract) |
| Where a new screen goes, the page's rules | **missing** | plans |
| A plan module's job, the edit engine, undo | present, as narrative | `:1094-1200` |
| Build and test the page, stories, journeys | present | `:902-975` |
| Windows: Git Bash, symlink privilege | **missing** | this review's brief |
| Release, ci, development builds, publishing | present, in depth | `:485-867` |

#### The five readers

- **The newcomer.** Reaches generated files in ten minutes on a POSIX shell, with every transcript true, and has understood why after `concept.rst`, whose three failure modes are the best page of argument here. Stops at: Windows (I4); no compiled image and no C using the headers (M8); never told an editor server or a GUI exists (`getting_started.rst:597-619`; pass 1 M1).
- **The component author.** Best served. Every key has a row, examples compile, findings explain themselves, and the schema hovers while typing. Stops at: `$schema` not on the site (M6), and the stale way to check alone (M4).
- **The integrator.** On CMake the reference is complete to the last keyword, and the module's refusals are explained. Stops at: adopting at all (I2), the a2l leaving the build (I3), not being on CMake (M7), running `ddd gui` over the collected project (pass 1 C4, no warning), tool-only objects under `--gc-sections` (pass 1 I11, no page says `KEEP`).
- **Somebody asked to use `ddd gui`.** Starts it and the screens carry them a long way; they are clear, and their sentences are good. The documents add little. They cannot find what `Tidy` does, how to adopt a vocabulary, what it will not do, or what to take care of (I1, M17).
- **The contributor.** Finds a treatise on publishing and on what guards it, the reasons for the a2l's shape, and 100 % coverage's rationale. Does not find how to get a green first run (I6) or where anything in the GUI goes (I5).

#### The SPEC's coverage of what the tool does

| What the tool does | SPEC | Coverage |
| --- | --- | --- |
| File formats, plugins, build record | 3.1-3.11 | full, to the key |
| Consistency checks, comparison | 4, 4.1 | full, 72 of 72 |
| C, a2l, dictionary, addresses | 5.1-5.3, 6 | full; format number stale (M12) |
| Command line | 7 | full, as one paragraph of 1,218 words |
| CMake | 7.1 | full |
| Language server | 7.2 | partial: unit, section and raster rename, `unknown-unit` fixes absent (M11) |
| Toolbox | 7.3 | full |
| Pre-commit hook | 7, one clause | enough |
| **`ddd gui`: screens, plans, undo, session, server, security** | 7, 3.6: two clauses | **none** (I9) |
| **The edit engine** (`ddd.editing`, what "in their own layout" promises) | none | **none** (I9) |
| Docker services, release machinery | none | rightly |

Shape: `SPEC.md:2064-2156` is a single paragraph, and its section 4's check list is 1,863 words of one list; pass 5 reads it in full.

#### `docs/superpowers/`: what only it holds, and whether it belongs

**The site.** It is not built: `docs/conf.py:35` does not exclude it, it stays out only because it holds no `.rst` (the built site has no page of it, checked). Make that a line of `exclude_patterns`. It should stay out: a record of what was decided at a date, 26 of 32 specs with no status or a wrong one, some superseded by design (`docs/superpowers/plans/2026-09-18-gui-units.md`, "the web GUI spec's section 6.7 still describes milestone 1's unit editor"). Published, it would be read as documentation.

**Needed by a user or contributor, and only there:**

| Held only in `docs/superpowers/` | Who needs it | Should go to |
| --- | --- | --- |
| The GUI's pieces, session and revisions, the api's conventions, refusal codes (`specs/2026-09-17-web-gui-design.md` 4, 6.3-6.6) | contributor | developer page (I5) |
| The page's rules and the journeys' conventions (several plans) | contributor | developer page (I5) |
| What "findings-heavy" means, the large-project figures (`plans/2026-09-30-gui-large-projects.md`) | contributor | developer page, cited at `:1055,1091` |
| What is planned: guide, pilot, removing preview | user, integrator | one paragraph in the guide |
| Known limits, in 27 "Left open" lists (no filter on Findings, no address for the blank form) | user, contributor | a "Known limits" list in the guide; the rest to issues |
| The decisions taken on reviews (`plans/2026-09-16-review-fixes.md`) | maintainer | where they are; a record is the right home |

**On master.** I would keep the text and change three things: an index, `docs/superpowers/README.md`, one line per record with its status and "records, not documentation; may be wrong"; the 53 mockups and screenshots (47 PNG, 6 HTML; 4.4 MB of 9.6 MB on master) out, to a release asset or the record's PR; and no citation of them from code or a page. It is already kept apart from everything else: excluded from the sdist (`pyproject.toml:105`), from ruff (`:146`), from the doc tests (`tests/test_documentation.py:60`, `tests/test_transcripts.py:64`). Those four exclusions are what a separate branch would make unnecessary, so an orphan `design-records` branch is the other honest answer; its cost is losing the search beside the code. The maintainer's call (open question 2).

#### Page shape

Words of prose, a crude count (`shape.py`, `inv/shape.txt`). Total 141,627; SPEC 29,115; developer page 12,510; README 9,762; artefacts 8,825; checks 8,306; CLI 7,384; build 6,979.

| Page | Verdict | Why |
| --- | --- | --- |
| `getting_started`, `toolbox`, `comparing_deliveries`, `faq`, `conversions`, `units`, `sections` | right | each is what it says it is |
| `command_line_interface` | wrong shape | 51 % is one cell (I1); the row carries benchmarks and refusal text |
| `README` | wrong size | "the short version" at 9,762 words (I10) |
| `developer_documentation` | wrong order | 17 sections; a third publishing, none on starting; GUI unsectioned (I5, I6) |
| `gui_security` | mixed | threat model, limits, instructions and a route table; a 933-word bullet (M17) |
| `templates` | wrong order | argues to `:86`, gets started at `:449` (M19) |
| `generated_artefacts` | too long | c and a2l are two pages; the essay on `volatile` (`:412-510`) is a third (M19) |
| `consistency_checks` | good, with lapses | reference table, wise severities page, then history (below) |
| `editor_integration` | one wall | the Rename paragraph is 628 words (`:82-122`), half of it about section and raster names |
| `data_contracts` | duplicates | prose restates `file_formats/index`; 2.4 MB rendered (M19) |

**History in the reference** (M18). A reference says what is; these say what was:

- `consistency_checks.rst:839`: "Two other properties used to be settled this way, and left in opposite directions." `:854`: "a project adopting this version of DDD adds the key everywhere in one go".
- `generated_artefacts.rst:610-612`: "Its header used to stay where the last run had put it". `:491-498`: a note on files "written before it existed", on a page about what is generated. `:866`: "exactly as before rasters existed"; `rasters.rst:97-98` again.
- `build_integration.rst:548-554`: "so it used to be dropped in silence ... `PROJECT` without a value fell into the collected mode".
- `command_line_interface.rst:189-191`: "where the broken pipe used to be reported as a usage error".
- `file_formats/component.rst:323-324`: "turned the declaration below it into part of the condition, and the compiler stopped there".
- `developer_documentation.rst:419-427` ("Two places used to do it"), `:513-516`, `:715-717`, `:880-886`, `:1131-1134`. The changelog is where these belong, and the page's reader needs the rule.

**Defence in the reference** (M18). The page argues where it could state, and a reader wades:

- `consistency_checks.rst:519-521,526-528,534-535`, in three table rows: "Kept a separate identifier from `consumer-storage`, whose published description says storage, which a raster is not." Nobody asks this while reading what the check does.
- `file_formats/index.rst:4-12`: nine lines on why the double extension before the rule, and `README.md:106-110`, `getting_started.rst:124-128`, `faq.rst:16-22` say it again.
- `file_formats/rasters.rst:22-31`: why eight characters, including that "No file DDD writes carries an event name today". Justifying wording is 10.3 per 1,000 words here against 2.1 on `conversions.rst`.
- `templates.rst:15-64`: three argued sections before the first rule.
- `comparing_deliveries.rst:476-477`: why the last line names files rather than projects. `build_integration.rst:313-314`: why the record is not named `*.ddd.json`. `developer_documentation.rst:12-14`: "That is not a style preference".
- Roadmap inside the reference: `sections.rst:98-100` ("is planned"), `rasters.rst:30-31`.

The reasons are worth keeping, and many are the best writing in the set. The change is where they go: state the rule first, in one line; keep the reason in a "Why" paragraph at the end of the section or in `concept.rst`; send the past to the changelog.

```candidates
4|I1|docs/command_line_interface.rst:294|ddd gui has no guide: its one account is a 3,960 word table cell, and twenty things on screen are missing or get one clause (KNOWN part 20)
4|I2|docs/toolbox.rst:11|No page says how a project with existing code adopts DDD; relaxing missing-producer for a global old code defines fails at the link, against concept.rst:318
4|I3|docs/file_formats/rasters.rst:126|Nothing says how to get from the generated a2l to a connected tool: A2ML and EPK appear in no document (KNOWN P10-M13, see pass 1 I8)
4|I4|docs/getting_started.rst:262|The tutorial's ddd id --assign components/*.ddd.json fails on Windows (wrote 0 ids, exit 1), and no page says the transcripts are bash
4|I5|docs/developer_documentation.rst:899|No account of how the GUI is put together: contract, queries, routes, screens named nowhere; where a new endpoint or screen goes is unanswered
4|I6|docs/developer_documentation.rst:392|No set-up and no definition of done for a contributor: CHANGELOG named zero times, pip install -e only as a fact about ci, Windows stoppers unstated
4|I7|CHANGELOG.md:371|The 0.11.0 section lists the Compare tab, paste, plots and the mismatch button, none of them in the v0.11.0 tag
4|I8|CHANGELOG.md:17|empty-vocabulary, a new check and format change, is nowhere in the changelog, nor are the Shared files and Files tabs; Unreleased has no Migration line
4|I9|SPEC.md:2134|The authoritative contract gives ddd gui two clauses: nothing on what it writes, refuses, undoes or defends, for over half the code
4|I10|README.md:38|The same facts are written in up to eight places, the short README is 9,762 words, and tests force it; copies have already parted
4|M1|docs/index.rst:41|The home page's Module Index link is a 404, and -W does not notice
4|M2|docs/acronyms.rst:66|--image did not reach five pages: DWARF DDD does not read it, FAQ's keeps address zero silently
4|M3|docs/getting_started.rst:21|The tutorial's dependency list omits pyelftools, and an air-gapped install has no recipe
4|M4|docs/file_formats/component.rst:450|The component page teaches -W missing-producer=ignore, which consistency_checks.rst:220 calls the mistake --standalone ends
4|M5|docs/command_line_interface.rst:150|The exit code is the same everywhere has exceptions: ddd gui exits 0 on Ctrl-C, ddd lsp's codes are in the SPEC alone
4|M6|docs/file_formats/index.rst:122|How to bind a file to its schema is in the README and not on the site
4|M7|docs/build_integration.rst:8|No recipe for a build that is not CMake; the pieces are on six pages
4|M8|docs/getting_started.rst:597|The tutorial stops before a compiler, no page shows C using the headers, and where next omits build, editor and GUI
4|M9|docs/templates.rst:476|No upgrading how-to, and nothing says a project's copied templates lack what later releases add
4|M10|docs/editor_integration.rst:34|No recipe for the editors it names and no trouble-shooting
4|M11|SPEC.md:2353|SPEC 7.2 and both READMEs omit renaming a unit, section or raster and the unknown-unit fixes
4|M12|SPEC.md:2215|SPEC says dictionary format today 8; it is 9 (KNOWN, 2026-09-24)
4|M13|README.md:42|Whether the plugin api is public is stated nowhere
4|M14|examples:1|examples/ and gui/ have no README and no index of what shows what
4|M15|docs/acronyms.rst:17|The glossary lacks LSP, A2ML, EPK, and the words the GUI uses
4|M16|docs/conf.py:102|PLANTUML_JAR, JAVA, DDD and a user's BROWSER are documented only in code or as a fixture
4|M17|docs/gui_security.rst:47|The security page never says what the reader should do; its instructions are spread through a threat model
4|M18|docs/consistency_checks.rst:839|Reference is mixed with history and with defence of itself
4|M19|docs/templates.rst:449|Pages whose order or size stops a reader: templates, generated_artefacts, developer page, data_contracts at 2.4 MB
4|M20|docs/developer_documentation.rst:1055|Design records' status lines have regrown wrong (26 of 32), and pages and code depend on records the sdist excludes (KNOWN)
```
