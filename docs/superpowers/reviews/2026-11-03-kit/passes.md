# The passes of the 2026-11-03 review

Each pass reads `review-brief.md` first. Paths are relative to the review tree. Parts A and B answer
the maintainer's three questions directly and come first, so that their readers come to the code
fresh; part C is the area-by-area correctness review, after the shape of the 2026-09-15 review
(whose pass each one continues is named); part D holds the suite to account.

## Part A: the concept and the split

### Pass 1: is the concept sound?

Not "does the code do what the spec says" but "is what the spec says the right thing, and does the
method really deliver it". Read `docs/concept.rst`, `SPEC.md` sections 1, 2, 3.3.1, 4 (its opening),
4.1 (its opening), 5, 6, `README.md`, `docs/faq.rst`, then whatever code you need.

Questions to settle, each with evidence and with probes where a probe can decide:

- The premises. Global variables as the interface; one JSON file per component; every side restating
  the whole definition so that drift is detectable, next to declared types where there is nothing
  left to disagree about. Does the model hold together? Is there anything a real integrator needs that
  it cannot express, or something it forces them to lie about?
- What the generated C really guarantees, **under the C standard and under real compilers** rather
  than under the documents' description of them. Every claim about enforcement, `const`, `volatile`,
  `--const-inputs`, visibility, one definition, conditions, initialisers, sections. Compile probes
  with gcc at several optimisation levels, read the assembly, and cite C11 clauses where you rely on
  them.
- What the generated A2L really guarantees against ASAP2 1.6.1, and what the design assumes about
  calibration tools. The flattening decision; the addresses (zero until the second run); `SYMBOL_LINK`;
  `IF_DATA XCP` without its A2ML; the record layouts and `point_counts`.
- The two questions `ddd check` and `ddd compare` answer. Is the graded comparison sound: can a change
  that breaks a consumer pass as clean or as a warning? Is `id` a sound basis for rename detection?
- The image/project split and the build integration: one component in several images, the link graph
  collection, the two-run build, reproducibility, who owns the output directory.
- The trust model: a description file names a plugin, a plugin is Python, so opening or checking a
  repository runs its code. Is that consistent across the CLI, the build, the editor and the GUI, and
  is it stated where a user would see it?
- Has the concept stayed one concept? DDD started as a generator. It is now also an editor (language
  server, GUI, edit engine), a reverse-engineering tool (`ddd tool from-elf`) and a delivery
  comparator. Does each still follow from the principles of `docs/concept.rst`, and do the principles
  still describe the tool? Does the GUI's model (the files are the project; textual edits; a revision
  per analysis; undo in memory) fit the method, or fight it? What should DDD refuse to become?
- What does the design make hard or impossible, that a user is likely to want next?

Report also a short "verdict by principle": for each principle, holds / holds with a caveat / does not
hold, and why.

### Pass 2: the split of the Python code

Is `src/ddd/` split cleanly? Measure, do not guess: compute the real import graph (top-level and
lazy imports), fan-in and fan-out, cycles, sizes, and what each module actually knows about, then
judge it against `docs/developer_documentation.rst` (sections Layers and The split is enforced by a
test), `README.md` (Layout), `docs/concept.rst` (How the tool is put together) and
`tests/test_backends.py`.

Read in full whatever the question requires. At least the module docstrings and public surface of
every module, and in full `src/ddd/gui/api.py`, `src/ddd/gui/session.py`, `src/ddd/editing.py`,
`src/ddd/lsp/navigation.py`, `src/ddd/lsp/units.py`, `src/ddd/lsp/edits.py`, `src/ddd/project_units.py`,
`src/ddd/type_plans.py`, `src/ddd/declaration_plans.py`.

Questions: what are the real layers, and do they match the documented ones? Which direction does each
dependency run, and should it? What is each package for (`gui`, `lsp`, the modules at the root), and
does its name say so? Which rules exist twice? Which module changes for more than one reason? Is
the UI's vocabulary (tabs, panels, pages) leaking below the UI? Is transport (HTTP, JSON-RPC) kept
at the edge? Can the core be used, and tested, without the editor layers? Could a second user
interface, or a batch tool that makes the same edits, be built on what exists without importing
`ddd.gui` or `ddd.lsp`? Are the import guards guarding the layers that exist today? Sizes: are the large
files and classes (`analysis.py`, `gui/api.py`, `cli.py`, `gui/contract.py`, `gui/queries.py`,
`_build_parser`) large because the job is large, or because things that should be apart are together?
Do comments and docstrings cite planning artefacts ("Task 2", "part 5") that a future reader cannot
resolve?

Give the target structure you would move to (packages, what moves where, what the guards should then
say), the order of the moves and a rough size for each. Say also which part of the present structure
you would leave exactly as it is, and why.

### Pass 3: the split between the UI and the backend, and inside the front end

Where is the line between `gui/` (TypeScript, React) and `src/ddd/` (the server and what it calls),
and is it in the right place? Read in full `gui/src/api/`, `gui/src/app/`, `gui/src/state/`, a
representative half of `gui/src/lib/` including `variableKeys.ts`, `objectValues.ts`, `shared.ts`,
`files.ts`, `units.ts`, `findings.ts`, `undo.ts`, and of `gui/src/screens/` including `VariablePanel.tsx`,
`FilesPage.tsx`, `ValuesPage.tsx`, `GraphPage.tsx`, with their `*View.tsx` partners; `gui/scripts/`;
`src/ddd/gui/contract.py` and `queries.py`; `gui/package.json`, `vite.config.ts`.

Questions: does the page decide anything the server should decide, or the server decide anything that
is the page's (wording, layout, what a tab shows)? List every domain rule the page holds (a name's
validity, a datatype's range, what a kind carries, how a plan is composed) with the Python that holds
the same rule, and whether they can drift, and try to make them. Is the contract truly one definition:
what does `gui/src/generated/` cover, and what is hand-mirrored (`api/types.ts`, query strings in
`api/client.ts`, refusal texts matched by the page)? Do the folders of `gui/src` (`api`, `app`,
`components`, `lib`, `screens`, `state`, `ui`) mean what they suggest, and is the direction of their
imports sound (a measured graph, including the `api` <-> `state` edge)? Is the `screens` / `*View`
split holding, or do screens carry logic that is then only reachable from a browser test? Are the
files that have grown to several hundred lines cohesive? What of the design is justified by the size of
the job, and what would be simpler with no loss? Dependencies: are they all needed?

Give the boundary you would draw and what would move across it, with a rough size for each move.

## Part B: the documentation

### Pass 4: what does the documentation miss?

Not whether each sentence is right (later passes check that), but whether a person can find out what
they need. Build, then read as five readers in turn: a newcomer who has just heard of DDD; a component
author; an integrator wiring it into a build; somebody asked to use `ddd gui`; a contributor changing
the code. Build the site with `sphinx-build -W --keep-going -b html docs "$SCRATCH/pass-4/html"` and
read `docs/index.rst` and everything it reaches, `README.md`, `SPEC.md`'s structure, `SECURITY.md`,
`editors/vscode/README.md`, `examples/`' READMEs if any, `CHANGELOG.md`'s `## Unreleased` (does it tell
a user what they must do?).

Then an inventory, tool against documents, in tables, each row marked documented (where) or missing:
every command and option (`ddd --help`, each subcommand's); every check (`ddd checks`); every CMake
keyword, target and property; every file kind and key (`ddd schema all`); every environment variable the
code reads; every exit code; every screen, tab, panel, action and state of the GUI (read `gui/src/app/App.tsx`,
`gui/src/screens/` and run it), its address, sign-in, polling, undo, what it writes and when, and its
limits; every LSP capability and setting; every plugin hook; every tool of the toolbox. For a contributor:
is there an account of how the GUI is put together, its server, its session, its plans, its contract,
its page, where a new endpoint or screen goes? What is the SPEC's coverage of each thing the tool does,
given that it calls itself the authoritative contract? Is anything documented only in
`docs/superpowers/` (specs, plans) that a user or contributor needs? Should `docs/superpowers/` be part
of the built site (check `docs/conf.py`), and of master at all? Are the pages the right size and shape for
what they do: is reference mixed with history, is a reader made to wade through a page's defence of itself?

Rank what is missing by how many people it stops and how badly.

## Part C: does it work (spec, code and docs of one area together)

### Pass 5: SPEC.md on its own
`SPEC.md` in full (2550 lines): contradictions, gaps, ambiguities, requirement words (1.1), undefined
terms, cross-references that point to the wrong section, examples that do not follow the text. Pay
particular attention to what changed since the last reviewed state (`git diff 6e9e99f HEAD -- SPEC.md`).
Carry forward, confirmed or not, the findings of `SCRATCH/pass-1-2026-09-24.md`. Previous review: its pass 1.

### Pass 6: file formats (SPEC 3.1 to 3.10)
SPEC 3.1-3.10 against `schemas/*.json`, `src/ddd/models/`, `src/ddd/loading.py`, `docs/file_formats/*.rst`,
`docs/data_contracts.rst`, and the GUI's copy of the schemas (`gui/scripts/schemas.mjs` and what it
generates). Every key: spec says X, schema says Y, model says Z, loader does W, doc says V - do they
agree? Include `point_counts`, the build record (3.6), unit and constant vocabularies, rasters, empty
vocabulary files, the dictionary format. Probe with real files: valid edge cases and invalid ones, check
the error and its location. Previous review: its pass 2.

### Pass 7: consistency checks and comparison (SPEC 4, 4.1)
SPEC 4 and 4.1 against `analysis.py`, `compare.py`, `identity.py`, `diagnostics.py`, the check sites in
`loading.py`, `docs/consistency_checks.rst`, `docs/comparing_deliveries.rst`, README's check list. Every
check identifier: registered, fires, message as documented, severity as documented. Probe with throwaway
projects, and try for false negatives: a broken project that passes, a breaking change `compare` grades
as a warning or nothing. Previous review: its pass 3.

### Pass 8: generated artefacts and addresses (SPEC 5, 6)
SPEC 5 and 6 against `ir.py`, `backends/` (c and a2l), `addresses.py`, `build_info.py`, `examples/templates/`,
`docs/generated_artefacts.rst`, `docs/data_dictionary.rst`, `docs/templates.rst`. Generate C and A2L for
probe projects covering every datatype, shape, kind, conversion, structure, raster and both
`point_counts` values; compile the C with gcc under the CI flag set (`docker/compile.sh`,
`tests/test_generation.py`); check the A2L's structure against the ASAP2 rules the spec cites and, with
`--image`, every address against what the linker placed. Previous review: its pass 4.

### Pass 9: tool interface and build integration (SPEC 3.11, 7, 7.1)
SPEC 3.11, 7, 7.1 against `cli.py`, `plugins.py`, `cmake/Ddd.cmake`, `.pre-commit-hooks.yaml`,
`docs/command_line_interface.rst`, `docs/plugins.rst`, `docs/build_integration.rst`, `examples/cmake`,
`examples/plugins`. Every command and option: documented, implemented, exit codes, stdout/stderr split,
`--format json` shapes. `ddd gui`'s command-line surface belongs here too. Run `tests/test_cmake.py` and
a real CMake build of `examples/cmake`. Previous review: its pass 5.

### Pass 10: editor integration (SPEC 7.2)
SPEC 7.2 against `src/ddd/lsp/*` read line by line, `editors/vscode/` (package.json, src, settings),
`docs/editor_integration.rst`. Drive the server over stdio with a probe client (see how
`tests/test_lsp.py` does it). Previous review: its pass 6, its one Critical above all.

### Pass 11: the toolbox and the ELF reader (SPEC 7.3)
New since the last review. SPEC 7.3 and 6 against `src/ddd/elf.py`, `src/ddd/toolbox/*`, the `--image`
paths of `addresses.py`, `docs/toolbox.rst`, `tests/fixtures/elf`, `tests/fixtures/addresses`,
`docker/build_elf_fixtures.py`, `docker/build_address_fixtures.py`. Build probe images with gcc (DWARF
variants, structures, bitfields, arrays, enums, tentative definitions, sections). Does an extracted
declaration round-trip: `from-elf` -> DDD -> compile -> same layout? Malformed and hostile ELF input: a
truncated file, a loop in DWARF references, a huge count. Does the wrong answer ever come out silently?

### Pass 12: the web GUI, security of the local server
`src/ddd/gui/server.py`, `routes.py`, `queries.py`, `depth.py`, `SECURITY.md`, `docs/gui_security.rst`,
specs `2026-10-05-gui-security-design.md`, `2026-10-07-gui-token-out-of-cookie-design.md`, plans of the
same dates (their "What was left open"). Threat model first: is it the right one, and stated? Then try
it: token, one-time code, `localStorage`, Host and Origin checks, `Sec-Fetch-Site`, CSRF, CSP (the
inline-script hash), DNS rebinding, IPv6, path confinement (symlinks, junctions, `..`, drive letters, UNC,
case, 8.3 names, trailing dots, alternate data streams on Windows), `--host` beyond loopback, the
connection cap, oversized and slow requests, headers on error answers, what opening a project executes
(plugins), a hostile project file reaching the page (XSS through a name, a description, a unit, a
finding's text; `dangerouslySetInnerHTML`; SVG; `href`). Start a real `ddd gui` on a probe project and
attack it with `curl` and Python. The `tests/test_gui_server.py` and `test_gui_hostile.py` coverage of
each. Previous review: none.

### Pass 13: the web GUI, the edit engine and the plans
`src/ddd/editing.py`, `src/ddd/gui/session.py`, `declaration_plans.py`, `type_plans.py`, `shared_plans.py`,
`file_plans.py`, `src/ddd/lsp/units.py`, `src/ddd/lsp/edits.py`, `object_values.py`, `identity.py`,
`file_names.py`, `pointers.py`, read line by line. Priority: can an edit lose or corrupt a file? A partial
write across several files; a concurrent edit (two tabs, the editor and the GUI at once, a build
rewriting a file, a branch switch); read-back verification; `os.replace` on Windows with the file open;
fingerprints; undo restoring the wrong bytes; a file with CRLF, a BOM, tabs, non-ASCII, duplicate keys,
deep nesting, a very long line, `\u` escapes; a read-only file; a file reached through a symlink. Does a
plan always produce a file the loader accepts, and the change it announced? Write a randomised probe (it
may live in your scratch folder) that applies plans to generated files and compares the outcome against a
parse-modify-compare oracle. Does the revision/analysis threading have races (`session.py`)?

### Pass 14: the web GUI, the API and its answers
`src/ddd/gui/api.py`, `contract.py`, `compare.py`, `derived.py`, `project_units.py`, `project_types.py`,
`project_shared.py`, `variables.py`, `variable_keys.py`, `value_identity.py`, `graph.py`, `finding_routes.py`,
`finding_fixes.py`, `findings_by_file.py`, `deliveries.py`, read line by line, against the `*gui*` design specs
(`docs/superpowers/specs/2026-09-17-web-gui-design.md` and later). Every endpoint: what it promises, what
it answers on a valid project, a broken one, one half way through an analysis, one that changed under it.
Does what the page is told agree with what `ddd check` and `ddd compare` say? Performance on a large
generated project (`tools/generate_project.py`, `tools/bench_gui.py`).

### Pass 15: the web GUI, the logic of the page
`gui/src/api/`, `gui/src/state/`, `gui/src/app/`, `gui/src/lib/` in full, tests beside them read for what
they pin. Wrong state after an edit, a refusal or a conflict; polling and long-poll races; undo restoring
the wrong thing; values grid and number parsing (locale, NaN, hex, integers beyond 2^53, `1.0` against
`1`, exponents); paste; keys, types and units editors writing what the server or the schema refuses; route
parsing; the token in `localStorage`; retries of non-idempotent requests.

### Pass 16: the web GUI, the screens as a user meets them
`gui/src/screens/`, `components/`, `ui/`, `styles/`, `index.html`, `public/`; run the Playwright journeys
(`npm run e2e`), with results redirected to your scratch folder, and drive a live `ddd gui` on `examples/demo`,
`examples/vocabulary` and a generated large project with your own Playwright script, taking screenshots
and reading them. Can a person who has not read the code do each job: fix a finding, rename a unit,
change a value, add a declaration, undo, compare against a delivery? What does an empty project, a
project with errors, a file that does not parse, a lost server look like? Accessibility: keyboard,
labels, focus, contrast, reduced motion. Honest usability notes are in scope here, with screenshots.

### Pass 17: code review of the core, part A
Line by line: `src/ddd/models/` (all), `loading.py`, `diagnostics.py`, `names.py`, `pointers.py`,
`file_names.py`. Bugs, unhandled inputs, wrong types, dead branches, complexity that hides a defect,
performance cliffs (try a large generated project). Previous review: its pass 8.

### Pass 18: code review of the core, part B
Line by line: `analysis.py` (3692 lines), `ir.py`, `compare.py`, `identity.py`. Same criteria. Previous
review: its pass 9.

### Pass 19: code review of the periphery
Line by line: `cli.py`, `plugins.py`, `backends/` (all), `build_info.py`, `addresses.py`, `cmake/Ddd.cmake`,
`src/ddd/__init__.py`, `__main__.py`, `difflib_lock.py`. Same criteria. Previous review: its pass 10.

### Pass 20: the repository and the remaining documents
`docs/getting_started.rst`, `concept.rst`, `faq.rst`, `data_contracts.rst`, `developer_documentation.rst`, `index.rst`,
`acronyms.rst`, `README.md`, `CHANGELOG.md` (accurate?), `SECURITY.md`, `examples/`, `docker/` and compose files,
`.github/workflows/*`, `.github/dependabot.yml`, `pyproject.toml`, `requirements*.txt`, `tools/`,
`.pre-commit-hooks.yaml`, `.gitignore`, licences (`gui/scripts/licenses.mjs`). Packaging: build the wheel and
sdist into your scratch folder, install them in a fresh venv outside the repository, run the tutorial
and `ddd gui` from the wheel. Build the docs with `sphinx-build -W --keep-going`. The state of the
GitHub side as far as it can be read (`gh release list`, `gh api repos/Sauci/ddd`; read only). Release
readiness of what is unreleased: an ordered checklist. Previous review: its pass 7.

## Part D: the test suite

### Pass 21: the test suite, core and formats
`tests/conftest.py`, `test_models`, `test_loading`, `test_analysis`, `test_structures`, `test_constants`,
`test_rasters`, `test_point_counts`, `test_types`, `test_units`, `test_sections`, `test_calibration`,
`test_compare`, `test_comparison_tables`, `test_edge_cases`, `test_hardening`, `test_embedded`,
`test_pointers`, `test_settle`, `test_backends`, `test_a2l`, `test_generation`, `test_external`. What each pins,
what it leaves open, tests that would pass on wrong code (mutate the code in a scratch copy of the tree,
never the review tree), assertions on error text only, fixtures that hide cases. Previous review: its pass 11a.

### Pass 22: the test suite, periphery and GUI server
`test_cli`, `test_plugins`, `test_example_plugin`, `test_cmake`, `test_lsp`, `test_lsp_decisions`, `test_gui_*`,
`test_editing`, `test_editing_at_once`, `test_object_values`, `test_declaration_plans`, `test_file_plans`,
`test_shared_plans`, `test_type_plans`, `test_unit_plans`, `test_project_*`, `test_variable_keys`, `test_variables`,
`test_unit_index`, `test_finding_routes`, `test_finding_fixes`, `test_graph`, `test_elf`, `test_toolbox_from_elf`,
`test_addresses`, `test_documentation`, `test_transcripts`. `tests/test_gui_api.py` alone is 10266 lines:
sample by mutation where reading is not practical, and say so. Same criteria. Is the suite's runtime and
size proportionate to what it protects; can a contributor run what matters quickly? Previous review: its pass 11b.

### Pass 23: the test suite of the page
`gui/src/**/*.test.ts`, `gui/e2e/`, `gui/playwright*.config.ts`, the Vitest config in `gui/vite.config.ts`, stories
and screenshot references, the `gui` job of `.github/workflows/ci.yml`. The 100 % gate covers `src/api`,
`src/lib`, `src/state` alone: what is therefore tested by journeys only, and which of a screen's states
by nothing? Mutate a copy. Flakiness: `waitFor`s, timeouts, order dependence, what the "hunt" of part 19c
found and fixed. Do the journeys pin behaviour or pixels? Maintenance cost: `gui/e2e/demo.ts`, `fixtures.ts`.

## Afterwards

- **Verification**: every candidate gets CONFIRMED, PLAUSIBLE or REFUTED, from a reader who did not
  find it, by reproducing it on the tree; the grade may change. Groups of two to three passes each.
- **Sweeps**: a code sweep and a documents sweep, each reading only what no pass looked at closely and
  what several passes touched from different sides.
- **Summary**: the maintainer's questions answered in order, what to fix first, decisions only the
  maintainer can take.
