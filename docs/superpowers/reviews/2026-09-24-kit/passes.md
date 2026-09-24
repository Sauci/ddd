# The passes of the 2026-09-24 review

Each pass reads `review-brief.md` first. Paths are relative to the review tree.

## Pass 1: SPEC.md on its own
`SPEC.md` in full (2411 lines): contradictions, gaps, ambiguities, requirement words (1.1), undefined
terms, cross-references that point to the wrong section, examples that do not follow the text.
Pay particular attention to what changed since 2026-09-15 (`git diff 6e9e99f faee81e -- SPEC.md`):
`point_counts`, dictionary format 9, the constants/string sentences, the `ddd gui` mentions, and the
sentences the 2026-09-16 fixes added. Previous review: its pass 1.

## Pass 2: file formats (SPEC 3.1 to 3.10)
SPEC 3.1-3.10 against `schemas/*.json`, `src/ddd/models/`, `src/ddd/loading.py`, `docs/file_formats/*.rst`,
and the GUI's copy of the schemas (`gui/scripts/schemas.mjs` and what it generates). Every key: spec says
X, schema says Y, model says Z, loader does W, doc says V - do they agree? Include `point_counts`
(project default, component override), the build record (3.6) with dictionary format 9, unit and
constant vocabularies, rasters. Probe with real files: valid edge cases and invalid ones, check the
error and its location. Previous review: its pass 2.

## Pass 3: consistency checks and comparison (SPEC 4, 4.1)
SPEC 4 and 4.1 against `analysis.py`, `compare.py`, `identity.py`, `diagnostics.py`, the check sites in
`loading.py`, `docs/consistency_checks.rst`, `docs/comparing_deliveries.rst`, README's check list.
Every check identifier: registered, fires, message as documented, severity as documented. The new
checks (`point-counts-unrepresentable`, `point-counts-mismatch`, any GUI-era ones) and how compare
treats point counts, format 9 vs older dictionaries. Probe with throwaway projects. Previous review: its pass 3.

## Pass 4: generated artefacts, address information, dictionary (SPEC 5, 6)
SPEC 5 and 6 against `ir.py`, `backends/` (c and a2l), `build_info.py`, `examples/templates/`,
`docs/generated_artefacts.rst`, `docs/data_dictionary.rst`, `docs/templates.rst`. Generate C and A2L for
probe projects covering every datatype, shape, kind, conversion, structure, raster and both
`point_counts` values; compile the C with gcc under the CI flag set (find it in `.github/workflows/ci.yml`
/ `tests/test_generation.py`); check the A2L's structure (RECORD_LAYOUTs, NO_AXIS_PTS, references,
nesting) against the ASAP2 rules the spec cites; check the dictionary against its schema and the spec.
Previous review: its pass 4.

## Pass 5: tool interface (SPEC 3.11, 7, 7.1)
SPEC 3.11, 7, 7.1 against `cli.py`, `plugins.py`, `cmake/Ddd.cmake`, `.pre-commit-hooks.yaml`,
`docs/command_line_interface.rst`, `docs/plugins.rst`, `docs/build_integration.rst`, `examples/cmake`,
the example plugin. Every command and option: documented, implemented, exit codes, stdout/stderr split,
`--format json` shapes. `ddd gui`'s command-line surface (options, host/port, messages) belongs here too.
Run the CMake tests and a real CMake build of `examples/cmake`. Previous review: its pass 5.

## Pass 6: editor integration (SPEC 7.2)
SPEC 7.2 against `src/ddd/lsp/*` read line by line, `editors/vscode/` (package.json, src, the
extension's settings), `docs/editor_integration.rst`. Drive the server over stdio with a probe client
(see how `tests/test_lsp.py` does it). Check the 2026-09-15 pass 6 findings, its one Critical above all.
Previous review: its pass 6.

## Pass 7: the web GUI, server side
`src/ddd/gui/` (server.py, session.py, api.py, contract.py) and the modules that exist for it:
`editing.py`, `object_values.py`, `declaration_plans.py`, `variable_keys.py`, `variables.py`,
`project_types.py`, `project_units.py`, `type_plans.py`, `finding_routes.py`, `finding_fixes.py`,
`value_identity.py`, `graph.py`, `pointers.py`; read line by line. The reference is the design specs
`docs/superpowers/specs/2026-09-17-web-gui-design.md` and every later `*gui*` spec, plus SPEC 7's
mentions. Priorities, in order: (1) security of the local server - token/cookie sign-in, Host and
Origin checks, CSRF, CSP, DNS rebinding, path confinement to the project's sources (symlinks,
junctions, `..`, drive letters, UNC, case), `--host` other than loopback; (2) the edit engine - an
edit that loses or corrupts a file, a partial write, a concurrent edit from two tabs or from the
editor and the GUI at once, the verify-by-reading-back, `os.replace` on Windows with the file open,
undo; (3) API contract - every endpoint against `contract.py` and the TS types; refusals; (4) the
rest. Start a real `ddd gui` on a probe project and hit it with `curl`/python. Tests: `tests/test_gui_*`,
`test_editing.py` and the helpers' tests - note what they leave open.

## Pass 8: the web GUI, front end
`gui/` in full: `src/` (api, app, state, lib, screens, components, ui, styles), `e2e/`, `scripts/`,
`vite.config.ts`, `playwright*.config.ts`, `biome.json`, `package.json`, `index.html`, and how the
built pages reach the wheel (`pyproject.toml` hatch artifacts, `publish.yml`, `ci.yml` gui job,
the docker image). Reference: the `*gui*` design specs. Look for: wrong state after an edit, a
refusal or a conflict; polling / long-poll races; undo that restores the wrong thing; values grid
and number parsing (locale, NaN, very large integers beyond 2^53, hex); keys/types/units editors
that write something the server or the schema refuses; XSS (any `dangerouslySetInnerHTML`, text from
the project reaching HTML); accessibility basics (keyboard, labels, focus); the contract between
`api/types.ts` and `src/ddd/gui/contract.py`. Run `npm run lint`, `typecheck`, `test`, `build`, and
the Playwright journeys. Drive a live `ddd gui` in a browser via Playwright scripts of your own if
useful.

## Pass 9: remaining documents and the repository
`docs/getting_started.rst`, `concept.rst`, `faq.rst`, `data_contracts.rst`, `developer_documentation.rst`,
`index.rst`, `acronyms.rst`, `README.md`, `CHANGELOG.md` (0.11.0 and 0.10.0 sections: accurate?),
`examples/`, `docker/` and compose files, `.github/workflows/*`, `pyproject.toml`, packaging (build the
wheel and sdist, install in a fresh venv outside the repo, run the tutorial, `ddd gui` from the wheel),
`requirements*.txt`, dependabot, `.pre-commit-config.yaml`, licences (`gui/scripts/licenses.mjs`
output). Release readiness for 0.11.1: an ordered checklist. Note the GitHub Release for v0.11.0 is
not yet created. Build the docs with `sphinx-build -W --keep-going`. Previous review: its pass 7.

## Pass 10: code review of the core, part A
Line by line: `src/ddd/models/` (all), `loading.py`, `diagnostics.py`, `identity.py`, `names.py`,
`pointers.py`. Bugs, unhandled inputs, wrong types, dead branches, complexity that hides a defect,
performance cliffs (try a large generated project). Previous review: its pass 8.

## Pass 11: code review of the core, part B
Line by line: `analysis.py`, `ir.py`, `compare.py`. Same criteria. Previous review: its pass 9.

## Pass 12: code review of the periphery
Line by line: `cli.py`, `plugins.py`, `backends/` (all), `build_info.py`, `cmake/Ddd.cmake`,
`src/ddd/__init__.py`, `__main__.py`. Same criteria. Previous review: its pass 10.

## Pass 13a: the test suite, core and formats
`tests/conftest.py`, `test_models`, `test_loading`, `test_analysis`, `test_structures`, `test_constants`,
`test_rasters`, `test_point_counts`, `test_types`, `test_units`, `test_sections`, `test_calibration`,
`test_compare`, `test_comparison_tables`, `test_edge_cases`, `test_hardening`, `test_embedded`,
`test_pointers`, `test_settle`. What each pins, what it leaves open, tests that would pass on wrong
code (try mutating the code in a scratch copy of the tree - never the review tree), assertions on
error text only, fixtures that hide cases. Run the suite with coverage. Previous review: its pass 11a.

## Pass 13b: the test suite, periphery, GUI API and guards
`test_cli`, `test_plugins`, `test_example_plugin`, `test_cmake`, `test_backends`, `test_a2l`,
`test_generation`, `test_external`, `test_lsp`, `test_gui_api`, `test_gui_server`, `test_gui_session`,
`test_gui_contract`, `test_editing`, `test_object_values`, `test_declaration_plans`, `test_unit_plans`,
`test_variable_keys`, `test_variables`, `test_project_types`, `test_type_plans`, `test_unit_index`,
`test_finding_routes`, `test_finding_fixes`, `test_graph`, `test_documentation`, `test_transcripts`.
Same criteria. Previous review: its pass 11b.
