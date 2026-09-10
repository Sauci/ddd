# Documentation corrections - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every documentation statement the review found inaccurate is corrected against the code, the published schemas' descriptions are current, the sdist can run its own tests and docs, and the transcripts harness no longer skips a page silently.

**Architecture:** Prose and docstring edits, one regeneration of `schemas/`, one packaging list, and one test-harness change. No behaviour change except the schemas' type-name pattern (an editor-facing validation) and the harness.

**Tech Stack:** Markdown, Sphinx RST, pydantic docstrings, `pyproject.toml`, pytest.

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md` (branch `review/complete-review-2026-09-08`): pass 2 Important 1, 2, 3, 5 and Minor 1, 2, 3, 4, 6, 7, 8, 9; pass 3 Important 6, 7 and Minor 1, 2; pass 4 Important 7 and Minor 1, 5, 6, 7; pass 5 Important 6, 7 and Minor 8, 9, 10, 11; pass 6 Important 1, 2, 3 and Minor 1, 2, 3, 4, 5, 9, 10, 11; the transcripts-harness follow-up from branch 3's final review.

## Global Constraints

- Branch: `docs/corrections`, off `master` once the previous branches have merged. Push after every task. Do not open a pull request.
- Every sentence must be true of the code on `master` at the time; the reviewers' reports quote the code locations, and the implementer verifies each claim against the tool before writing it.
- `python -m pytest tests/test_documentation.py tests/test_transcripts.py --no-cov` after every task; the full suite, ruff format check and the Sphinx build with warnings as errors (`docs/conf.py`; `JAVA` and `PLANTUML_JAR` as recorded in the memory `ddd-local-build-toolchain`) before the last commit.
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. House style: British spelling; ` - ` not em dashes; the page's voice.

---

### Task 1: The published schemas say what the tool does

**Files:** `src/ddd/models/objects.py`, `conversion.py`, `types.py`, `project.py`, `component.py`, `common.py` (docstrings and `TYPE_NAME_PATTERN`), `schemas/*.schema.json` (regenerated), `README.md`, `docs/file_formats/variable_definition.rst`, `docs/acronyms.rst`.

- [ ] The measurement docstring and the two prose passages: a calibration tool can read and write a measurement (pass 2 Important 1: `objects.py:48` and `:483`, `README.md:332-333`, `variable_definition.rst:426-427`, `acronyms.rst:108-110`).
- [ ] `identity`'s description: "physical == raw; stated like any other conversion, `{}` being its shortest spelling" (Important 2).
- [ ] A definition's `unit` description: free text, checked against the vocabulary where the project declares one; the same on `variable_definition.rst:99-103` and `README.md:317` (Important 3).
- [ ] `TYPE_NAME_PATTERN` case-insensitive lookahead so the published schema refuses `UINT16` as the loader does (Important 5), and a test validating a mixed-case name against the published schema.
- [ ] Minor 1 (`includes` description names rasters files and the `[` wildcard), 2 (`StructType.name` reason), 3 (`Enumerator.value` describes the warning), 4 (`scope: output` "owns; provides for a calibration object"), 6 (kind counts in two docstrings), 7 (`component.rst`'s note lists the five consumer-refused keys), 8 (`project.rst`: `file-not-found` and the sorted order), 9 (README `extensions` default `{}`).
- [ ] Regenerate: `PYTHONPATH=src python -m ddd schema all -o schemas`. Commit: `say in the schemas what the loader does`.

### Task 2: The checks page and the command line page

**Files:** `docs/consistency_checks.rst`, `docs/command_line_interface.rst`, `src/ddd/diagnostics.py` (two descriptions), `README.md` rows.

- [ ] Pass 3 Important 6: which load-time errors withhold the interface checks (the seven fixed, `file-extension`, `include-empty`, the six `duplicate-*`, `unknown-extension`), and that relaxing whichever fired lets the second wave through.
- [ ] Pass 3 Important 7: the note recommending two hand-listed overrides becomes `ddd check <component> --standalone`, listing the ten checks it holds back.
- [ ] Pass 3 Minor 1: `reserved-identifier`'s registry description and README row name the `<stdbool.h>` names and the two underscore families; Minor 2: README rows for `duplicate-type` and `changed-storage`.
- [ ] Pass 4 Minor 4: `ddd dump --format json`'s help string. Pass 5 Minor 11: the plugin artefact's options on the plugins page. Commit: `describe the load-time gate, --standalone and the reserved names as the tool applies them`.

### Task 3: The build, editor and generated-artefacts pages

**Files:** `docs/build_integration.rst`, `docs/generated_artefacts.rst`, `docs/developer_documentation.rst`, `docs/editor_integration.rst`, `README.md`, `cmake/Ddd.cmake` (one comment).

- [ ] Pass 4 Important 7: `ddd dump --format json` where four pages say `ddd list --format json` (`README.md:852`, `developer_documentation.rst:314`, `build_integration.rst:508`, `generated_artefacts.rst:394`).
- [ ] Pass 5 Important 6: where a project-wide vocabulary file goes in the CMake build (a target every image links, or the image itself), and the `Ddd.cmake:153` comment naming rasters.
- [ ] Pass 5 Important 7: producing the address map is the project's step; a worked `add_custom_command(TARGET <image> POST_BUILD ...)` example writing the JSON of section 6 from the toolchain's symbol lister into the seeded path.
- [ ] Pass 5 Minor 8 (`build_integration.rst:327`), 9 (the pre-commit hook in the README's build section), 10 (`-b` relative to the workspace folder / working directory).
- [ ] Pass 6 Important 1: the README's `NO_PROPAGATE_HEADERS` paragraph says both calls opt out. Pass 4 Minor 5 (README `ddd_types.h` row lists the external includes), Minor 1 (`base.py`'s stale "prefix" usage message).
- [ ] `<image>_ddd_headers` / `<image>_ddd_globals` in `docs/build_integration.rst` become `<stem>_...` as the spec spells them (the changelog's older entries stay as written). Commit: `match the build, editor and artefact pages to the module and the tool`.

### Task 4: README, contracts page, packaging, developer page, FAQ, Dockerfile

**Files:** `README.md`, `docs/data_contracts.rst`, `pyproject.toml`, `docs/developer_documentation.rst`, `docs/faq.rst`, `docker/Dockerfile`, `examples/demo/demo.ddd.json`, `CHANGELOG.md`.

- [ ] Pass 6 Important 2: the sdist include list gains `/assets`, `/editors/vscode` (sources, `package.json`, `package-lock.json`, `LICENSE`, `icon.png`), `/.github/workflows` and `/.pre-commit-hooks.yaml`; verify by building the sdist into the scratchpad and running `tests/test_documentation.py` and the docs build from it.
- [ ] Pass 6 Important 3: `autopydantic_model` directives for the ten models missing from `data_contracts.rst`.
- [ ] Pass 6 Minor 1 (the FAQ address-map transcript, spelled so the test owns it), 2 (the FAQ's per-component target sentence), 3 (README `--without` and `TEMPLATES`), 4 (developer page: `BUILT_IN_GENERATED`, the module always asks for `all`, the `base.py` docstring), 5 (merge the two `ddd-compile` changelog entries into one), 9 (Dockerfile's duplicated cmake/ninja install), 10 (the demo's description), 11 (the developer page names the transcript test).
- [ ] Pass 6 Minor 6 (the changelog header's definition of the public interface widened to the command options, the cmake signatures, the template model, the `--renames` and `ddd-build.json` formats) and Minor 7 (a sentence in "Publishing a release" listing where the version is spelled). Commit: `correct the README, the contracts page, the sdist and the developer page`.

### Task 5: The transcripts harness stops skipping pages

**Files:** `tests/test_transcripts.py`, `docs/file_formats/component.rst` (and any other page the harness now reaches).

- [ ] Test first: a page under `docs/` that contains a `$ ddd` line and yields no runnable transcript fails the suite with a message naming the page and the command (today `Transcript.mode()` returns `None` and the page is silently absent from the parametrisation).
- [ ] Implement: `transcripts(page)` raises (or the parametrised test asserts) when a page has `$ ddd` commands and none is runnable; make `docs/file_formats/component.rst`'s four commands runnable by spelling `examples/vocabulary/...` paths (and `-t examples/templates` where needed), and re-pin their outputs from the tool. Run the whole harness; fix every page it now reaches.
- [ ] Commit: `run every documented transcript, or fail the page that cannot be run`. Then the final verification (full suite, Sphinx `-W`, ruff format check) and a changelog bullet for the schema pattern change and the sdist.
