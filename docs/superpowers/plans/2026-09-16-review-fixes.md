# Fixing the complete review of 2026-09-15

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development to
> implement this plan branch by branch. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** close the 219 findings of the 2026-09-15 complete review that do not need a business
decision from the maintainer, so that 0.10.0 can be released.

**Architecture:** nine stacked branches, one per area, merged in the order below. They stack
because they all add to `CHANGELOG.md` and six of them edit `SPEC.md`; each retargets to master
as the previous one merges, which is the convention the 2026-09-08 review's fixes used.

**Tech stack:** python 3.12+, pydantic v2, jinja2, pytest with a 100 % line-and-branch coverage
gate, ruff, mypy strict, sphinx with `-W`, CMake, TypeScript for the editor extension.

**Spec:** `docs/superpowers/reviews/2026-09-15-complete-review.md` on branch
`review/complete-review-2026-09-15`. Every finding below is named by its id (`P6-C1`, `S-I1`,
`SD-M4`); the review's section for that pass carries the trigger, the evidence, the anchored
line and the proposed fix, which together are the specification of each task. Read it with
`git show review/complete-review-2026-09-15:docs/superpowers/reviews/2026-09-15-complete-review.md`.

## Global constraints

- `python -m pytest` must pass with coverage at 100 % of lines **and** branches
  (`pyproject.toml:102`). One failure is expected on this machine and only here:
  `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`
  needs a Windows privilege the shell does not hold.
- `ruff check .`, `ruff format --check .` and `mypy` must pass; `sphinx-build -W --keep-going -b
  html docs <out>` must build clean.
- Run pytest from Git Bash, never from PowerShell, with
  `export PATH="/c/git/ac11/ddd/.venv/Scripts:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:$PATH"`.
  The docs build needs `JAVA` and `PLANTUML_JAR` set (see `docs/conf.py`).
- Every behaviour change that touches the public interface the changelog preamble defines - check
  identifiers, command names and options, the json file formats, the `ddd_generate()` /
  `ddd_add_component()` signatures, the names a template renders from - gets a `## Unreleased`
  entry saying what changed and what the migration costs.
- A rule that changes reaches all of its homes: `SPEC.md`, the model docstring (which is
  published in `schemas/`), the file-format page, the README and the changelog. Regenerate the
  schemas with `ddd schema <kind>` when a model changes;
  `tests/test_documentation.py:1389-1398` compares them byte for byte.
- Tests first. Each task adds the test that fails on the defect, then the fix, then the run.
- One commit per task, pushed as it lands (the maintainer reviews on the GitHub server).
- No pull request is opened without asking.

## Decisions taken on the review's open questions

The review left eleven questions to the maintainer. Waiting on all of them would stop the work,
so each is decided here with its reason; every one is a line or two to reverse, and the
changelog entry says what was chosen. **Four are deliberately left open** at the end.

1. **An `init` compares as bytes, not as spelled** (`P3-I2`). A delivery whose storage is
   byte-identical can replace its predecessor; a respelling is not a change. `7` on `uint8[4]`
   broadcasts to `[7, 7, 7, 7]` and a string's text compares as its padded byte tuple.
2. **Wildcard includes sort by code point** (`P1-I4`, `P2` question 2, `P8` question 4). "The
   same project generates the same bytes on any machine" (`SPEC.md:1604-1607`) is the promise
   worth keeping; nobody depends on a platform's own path order. `sorted()` on `as_posix()`.
3. **A structure's layout is part of its interface** (`P9-I2`, `P11A-I2`). Member order and a
   bitfield's width move every address after them, and the `Member` docstring published in two
   schemas already says a comparison reports the reordering.
4. **Derived limits are rounded, and `narrowed-limits` carries the analysis's tolerance**
   (`P4-I3`, `P9-I1`). Both: rounding alone leaves every archived baseline tripping the check
   from the other side. One shared helper for "below within tolerance" / "above within
   tolerance".
5. **The a2l is written with a byte order mark** (`P4-I2`). ASAP2 1.6.1 section 1.5 says a reader
   detects the encoding from a byte order mark and otherwise falls back to ISO-8859-1, so the
   mark is what makes the utf-8 the tool already writes readable.
6. **`ddd generate` owns its output directory** (`P5-I3`). It records what it wrote in a manifest
   beside the artefacts and removes, on the next run, the files it no longer writes. Only files
   the tool itself wrote are ever removed, and `ninja -t clean` becomes equivalent to a fresh
   build.
7. **The server publishes and edits under the spelling the client used** for a document it
   opened, and resolves for every other file (`P6-I1`, `P6-I2`, `P11B-I1`).
8. **A hook's and a plugin backend's stdout is bound to stderr** while they run (`P5-I1`), the
   arrangement the language server already uses. A printing plugin keeps its output, on the
   stream that is not a document.
9. **`-W` does not reach a description baseline's own analysis** (`P3` question 2, `P5` question
   6), which is what `--strict` already does: the baseline's findings are its own.
10. **A quoted number nested in a list `init` is refused** (`P2-I1`). The specification, the
    model's own docstring and the published schema all say it is text; only the loader disagreed.
    The rest of the strict-mode residue (`P2-I2`) stays deferred, as the maintainer left it.
11. **A literal with a point or an exponent is fractional** (`P1-M4`, `P2` question 3). Stated in
    3.9 and in the constant's docstring rather than given a parser hook.

**Left to the maintainer, and not touched by this plan.** Enabling the issue tracker or choosing
another support channel (`P7-I3`); the `Development Status` classifier, python 3.14, whether the
0.10.0 release is flagged pre-release, and the Node version of the extension jobs (`P7`); whether
the a2l should carry the XCP A2ML block its `IF_DATA` presupposes (`P10-M13`) - documented as a
reader obligation instead; whether templates run sandboxed (`P10-M11`) - documented instead.

---

## Branch 1: `fix/editor-critical` (off `master`)

The review's one Critical, every Important of the language server, and the editor's minors.

**Files:** `src/ddd/lsp/diagnostics.py`, `navigation.py`, `server.py`, `ranges.py`,
`discovery.py`, `protocol.py`, `hover.py`, `edits.py`; `editors/vscode/src/extension.ts`,
`launch.test.ts`; `tests/test_lsp.py`, `tests/test_constants.py`, `tests/test_external.py`,
`tests/conftest.py`; `SPEC.md` 7.2; `docs/editor_integration.rst`; `README.md:133-237`;
`CHANGELOG.md`.

- [ ] **Task 1 (`P6-C1`, Critical):** a root that is a project is analysed under the full default
      policy, as a containing project already is; `analyse_standalone` stays for a component
      root. Test: `examples/inconsistent/project.ddd.json` opened with no build record publishes
      `missing-producer` and `unused-output`; opening a component first and the project next does
      not withdraw them.
- [ ] **Task 2 (`P6-I4`, = `P5-I5`):** `load_builds` builds the policy under
      `try/except UnknownCheckError` and skips a record naming a check this tool does not know,
      announcing it as a missing project is announced. Test: a record with
      `"severity": ["no-such-check=ignore"]` and one with a malformed entry; the server serves on.
- [ ] **Task 3 (`P6-I1`, `P6-I2`, `P11B-I1`):** remember the client's spelling per resolved path
      on `didOpen` and publish, answer and edit under it; compare `candidate == document.resolve()`
      in `containing_projects`. Rewrite the tests that key `published()` by file name or resolve
      both sides so they compare uri strings. Test: a junction and a `subst` drive.
- [ ] **Task 4 (`P6-I3`):** keep the bag of `load_workspace` in `_loaded` and refuse a rename and
      the quick fixes with `REQUEST_FAILED`, naming the file, when the load reported an error.
- [ ] **Task 5 (`P6-I5`, `S-I2`):** match the rename subject's key directly under `definition`
      (`name`, `axis`, `x_axis`, `y_axis`, `input`), and the same for `constant_at` and
      `type_at`; register the enum names and enumerators of every scalar type and every member
      conversion in `Index.occupied`. Test: F2 on an enumerator offers no rename; a rename onto
      `MODE_IDLE` of `examples/structures` is refused.
- [ ] **Task 6 (`P6-I6`):** drop a finding equal in code, message, location and severity to one
      already filed for that file in the same refresh. Test: two records covering one component.
- [ ] **Task 7 (`P8-I1`):** catch `RecursionError` around `scanner.value("")` in
      `ranges.Document`, leaving empty spans, so `ddd id --assign` reports the file as one it
      cannot read and the server survives. Test: a 600-level document through `Document`, through
      `ddd id --assign` and through `didOpen`.
- [ ] **Task 8 (`P6-M1`, `M2`, `M5`, `M6`, `M15`):** `_field` for `context` and for a workspace
      folder without `uri`; no error response for a notification; `Content-Length` matched as
      `\d+`; a document under a scheme other than `file:` refused rather than made relative.
- [ ] **Task 9 (`P6-M3`, `M4`):** `exit` without `shutdown` returns 1; a request before
      `initialize` is `ServerNotInitialized` and one after `shutdown` is `InvalidRequest`. Update
      `editors/vscode/src/launch.test.ts` to send `shutdown` first and give the handshake a
      timeout (`P11B-M16`).
- [ ] **Task 10 (`P6-M7`, `M9`, `M11`, `M12`, `M14`, `S-M4`):** resolve before adding a record
      to `found` so a junction loop yields one; verify a record's plugin overrides against the
      loaded plugins; hover on a declared type's own entry and on a `typename` inside a types
      file; a note without a location carries the file's uri; `_insert` counts `\n` as every
      position does; the no-record log says a file under a project is checked through it.
- [ ] **Task 11 (`P6-M8`, `M16`):** the extension's watcher notification refreshes the document
      (or the comment is corrected and the watcher dropped); `restartServer` does not clear a
      client another start assigned; hover markdown escapes a backtick and a pipe.
- [ ] **Task 12:** `SPEC.md` 7.2, `docs/editor_integration.rst` and `README.md:212-220` say what
      the server now does: the project file's policy, the containing project's default policy
      (`P6-M10`), the spelling it publishes under, and a record it declines. Changelog entry.

## Branch 2: `fix/release-machinery` (off branch 1)

What would make the first official release publish something wrong.

**Files:** `.github/workflows/publish.yml`, `docs.yml`, `ci.yml`; `docs/faq.rst`;
`docs/developer_documentation.rst`; `tests/test_documentation.py`; `CHANGELOG.md`.

- [ ] **Task 1 (`P7-I1`):** `publish-pypi` runs only for a `release` event, or for a dispatch
      whose ref is a `v*` tag. The comment at the head of the file already calls dispatch the
      TestPyPI dry run.
- [ ] **Task 2 (`P7-I2`):** `stable` is the newest tag whose version carries no suffix; a
      prerelease stays in `versions`. Extract the `order`/`stable` logic into a small script the
      workflow runs so that a test can exercise it, and pin `v0.9.0` / `v0.10.0rc1` / `v0.10.0`
      and a hotfix `v0.9.1` published after `v0.10.0` (`P11B` gap 48).
- [ ] **Task 3 (`P7-I4`):** `docs/faq.rst:609-611` states the four caps and that a shape past one
      is `schema` where it is written.
- [ ] **Task 4 (`P7-I5`, `P11B-M4`, `M5`, `M6`):** either the junction test runs everywhere or
      the developer page stops claiming nothing skips; a guard in `tests/test_documentation.py`
      that no `pytest.skip`, `skipif`, `importorskip` or `xfail` is added under `tests/`;
      positive controls on the five vacuous documentation guards and on the transcript parameter
      sets; the command list checked against `SPEC.md` as well as the README.
- [ ] **Task 5 (`P7-M1`, `M2`, `M3`, `M4`, `M9`):** the README's compile transcript counts; the
      developer page's runtime, extension job, layer table (the language server, `identity.py`,
      `build_info.py`), lock-file claim and environment paragraph; the container's stale jar
      comment, `--dictionary` instead of a second `dump`, and the `.dockerignore` entries.
- [ ] **Task 6 (`P7-M5`, `M6`, `M10`, `SD-M9`):** the four stale status lines under
      `docs/superpowers/specs/`; the changelog's "format 8 is unreleased" sentence and the
      strings entry's silence on the init comparison; the sixteen acronyms; one reading of how
      long a check identifier lives.
- [ ] **Task 7 (`P7-M7`, `M8`):** a `.github/dependabot.yml` for `github-actions`, `pip` and
      `npm`; `ruff` and `mypy` capped to a minor in `requirements-dev.txt`; the `upload-artifact`
      versions aligned. The Node version and the pinning of actions by sha are left to the
      maintainer with a note in the plan's "left open" list.
- [ ] **Task 8 (`P11A-M9`, `S-M5`):** drop the redundant pragma at `src/ddd/identity.py:32`, and
      either drop `-q` from `addopts` or say beside it that a second `-q` silences the summary.

## Branch 3: `fix/generated-artefacts` (off branch 2)

Everything that reaches a generated file.

**Files:** `src/ddd/backends/c/literals.py`, `c/model.py`, `c/backend.py`;
`src/ddd/backends/a2l/model.py`, `a2l/backend.py`, `a2l/options.py`;
`src/ddd/models/conversion.py`; `src/ddd/analysis.py`; `src/ddd/backends/base.py`;
`examples/templates/ddd_types.h.jinja2`; `examples/plugins/ddd_layout.py`;
`tests/test_generation.py`, `tests/test_a2l.py`, `tests/test_analysis.py`,
`tests/test_example_plugin.py`; `SPEC.md` 5.1, 5.2; `docs/generated_artefacts.rst`;
`docs/templates.rst`; `CHANGELOG.md`.

- [ ] **Task 1 (`P4-I1`):** `sanitize_comment` defuses `/*` as it defuses `*/`. Test: a
      description containing `/*` renders a comment gcc accepts under the CI flag set.
- [ ] **Task 2 (`P4-I2`, decision 5):** the a2l is written with a utf-8 byte order mark; 5.2 and
      the artefacts page say so, naming ASAP2 1.6.1 section 1.5. Test: the first bytes of the
      file, and a non-ASCII unit round-tripping.
- [ ] **Task 3 (`P4-I3`, decision 4):** `physical_range` rounds as `raw_reading` rounds, so a
      `uint8` under `{"factor": 0.03}` states `7.65`. Test: the a2l, the dump and
      `examples/layout`'s shipped numbers.
- [ ] **Task 4 (`P3-I1`, `P4-I4`, `S-I1`):** `_refuse_reference` refuses a target whose
      `declared_type` names a structure as `reference-kind`; the a2l backend falls back to
      `NO_INPUT_QUANTITY` for a name it does not carry; `name-collision` gains the
      constant-against-structure-member pair, and `SPEC.md:1307` lists it.
- [ ] **Task 5 (`P4-M1`, `M3`, `M4`, `M8`, `M12`, `S-M1`):** a template error names the file the
      failing frame belongs to; a `float32` init that rounds to zero is `init-invalid`;
      `ConstantView` offers a c literal; `²` and `³` transliterate; a `-t` that does not exist or
      is not a directory says so; a shape with more dimensions than a stated limit is refused
      where `_shape_fits` weighs it.
- [ ] **Task 6 (`P4-M2`, `M10`, `P5-M16`):** the example type header always includes `<stdint.h>`,
      the definition template emits a placeholder when it renders nothing, and the example
      plugin's header includes `ddd_globals.h`; `docker/compile.sh` then passes on a float-only,
      an object-less and the layout project.
- [ ] **Task 7 (`P4-M5`, `M6`, `M7`, `M9`, `M11`, `SD-M1`, `SD-M2`):** the documentation of what
      the dictionary carries (`init` unexpanded, `source` a file name), the container transcript
      and the getting-started and artefacts excerpts brought up to the demo as it is, the
      `COMPU_VTAB` sentence, and a message when a path is too long for the platform.

## Branch 4: `fix/comparison-verdicts` (off branch 3)

Everything that decides whether a delivery can replace another.

**Files:** `src/ddd/compare.py`, `src/ddd/ir.py`, `src/ddd/analysis.py`,
`src/ddd/models/objects.py`; `tests/test_compare.py`, `tests/test_comparison_tables.py`;
`SPEC.md` 4.1, 5.3; `docs/comparing_deliveries.rst`; `CHANGELOG.md`.

- [ ] **Task 1 (`P3-I2`, decision 1):** `init` compares as bytes - broadcast over the shape, a
      string's text as its padded byte tuple. Test: `7` against `[7, 7, 7, 7]`, `[72, 105, 0, 0]`
      against `"Hi"`, and a real difference still reported.
- [ ] **Task 2 (`P9-I1`, decision 4):** `narrowed-limits` uses the shared tolerance helper of
      branch 3 task 3. Test: a candidate stating the limits its datatype implies compares clean
      under `--strict`.
- [ ] **Task 3 (`P9-I2`, `P11A-I2`, decision 3):** a leaf's `bits` and a structure's member order
      are interface fields; the comparison-tables guard walks `ResolvedLeaf.model_fields` with an
      excuse dict for `path`, `instance` and `instance_id`, and every `DERIVED_AS` mapping is
      executed rather than named.
- [ ] **Task 4 (`S-I4`):** instances are paired (by id, then by name) and compared: `type`,
      `shape` and `local` as interface, `volatile`, `section`, `raster`, `condition`, `owner` and
      `a2l` as storage, leaving the members to the leaves. Test: a type renamed with identical
      members; an instance-level `volatile` flip reported once.
- [ ] **Task 5 (`S-I3`):** `reused-name` also fires when a shared name is the new side of a
      rename, with a note naming the object now under it; `SPEC.md:1422` lists the third proof.
- [ ] **Task 6 (`P9-I4`):** the lost-identity note buckets on everything hashable it compares and
      gives up above a small bound. Test: the note still appears for one candidate; a sweep of
      5 000 renamed objects compares in seconds.
- [ ] **Task 7 (`P9-M5`, `S-M2`, `P9-M4`, `M9`):** `_describe_init` abbreviates a long init and
      spells a list as json; the nested-too-deep message names the element; `2.0` on a boolean
      reads as written.
- [ ] **Task 8 (`P3-M7`, `P8-M7`):** `format` is a strict integer of at least 1, and a dump is
      read through the loader's hooks so a duplicate key is refused on both sides.
- [ ] **Task 9:** 4.1 and 5.3 say what changed: the enumerators inside `changed-interface`
      (`P1-I5`), a string's `init` and the byte comparison, the layout fields, the third
      `reused-name` proof, the renames spelling of an array member (`P1-I1`). Changelog entry.

## Branch 5: `fix/cli-and-plugins` (off branch 4)

The command line's boundary with plugins, paths and streams.

**Files:** `src/ddd/cli.py`, `src/ddd/plugins.py`, `src/ddd/identity.py`,
`src/ddd/backends/a2l/options.py`, `src/ddd/backends/base.py`, `src/ddd/diagnostics.py`;
`tests/test_cli.py`, `tests/test_plugins.py`; `docs/command_line_interface.rst`,
`docs/plugins.rst`, `docs/consistency_checks.rst`; `SPEC.md` 7; `CHANGELOG.md`.

- [ ] **Task 1 (`P5-I1`, decision 8):** hooks and plugin backends run with `sys.stdout` bound to
      `sys.stderr`. Test: a plugin printing under `check --format json`, `generate --format
      json`, `dump` and `dump -o`.
- [ ] **Task 2 (`P5-I2`, decision: refuse):** `dump -o`, `--renames` and `--dictionary` refuse a
      target that resolves to one of `workspace.sources()`, as a usage error naming the file.
- [ ] **Task 3 (`P3-I3`, decision: the page is right):** every `Location` built from a typed path
      in `cli.py` and `loading.py:1103` is built from the resolved path, so a diagnostic's json
      `location.path` is absolute wherever it comes from. Test: the `location.path` of a
      comparison finding, and the text order against the candidate's own findings.
- [ ] **Task 4 (`P5-M1`, `M2`, `M6`, `P10-M7`):** `allow_abbrev=False`; `_call` catches
      `BaseException` and re-raises `KeyboardInterrupt`, which `main` turns into `ddd:
      interrupted` and 130; `BrokenPipeError` exits quietly; `-o .` is refused with the tool's
      own words.
- [ ] **Task 5 (`P5-M4`, `M5`, `M7`, `M8`, `M9`, `P10-M10`):** `id --assign` reports an
      unwritable file and continues; the address map, `schema -o` and `build-info -o` say what
      they were doing; the verdict line prints paths when two file names coincide; a dumped
      dictionary handed to `check` says so; `missing-plugin` for the baseline sits at the
      baseline, and a `-W` naming one of its checks is not refused after it was applied.
- [ ] **Task 6 (`P8-M13`, `P6-M9` cli side, `P3` question 2 / decision 9):** `-W` is verified
      even when the load reported an error, and does not reach a description baseline's own
      analysis.
- [ ] **Task 7 (`P10-M5`, `M6`, `P5-M3`):** the address map reads `utf-8-sig`, holds its
      addresses to a pattern and refuses a repeated symbol; a hook receives read-only views of
      the blocks and of the dictionary, or `docs/plugins.rst` states that what it changes is what
      the backends render.
- [ ] **Task 8 (`P10-M8`, `M9`, `S-M6`, `P5-M14`, `P1-M10`):** `list` and `dump` flush before
      their findings; the table measures display width; every `variables` row carries a `name`;
      the json payloads of `list`, `artefacts` and the reports are documented, in the spec and on
      the page.
- [ ] **Task 9 (`P5-M11`, `M12`, `M13`, `M15`, `P10-M11`, `SD-M7`, `SD-M10`):** the pages say
      what the code does about `--plugin` beside a description, plugins running at configure
      time, the hook's python floor, a component generating on its own, templates being code, the
      plugin artefact's `--dictionary`, and what `ddd checks` and `ddd sources --help` describe.

## Branch 6: `fix/build-integration` (off branch 5)

**Files:** `cmake/Ddd.cmake`, `src/ddd/backends/base.py`, `src/ddd/loading.py`,
`src/ddd/backends/a2l/options.py`; `tests/test_cmake.py`, `tests/test_backends.py`;
`docs/build_integration.rst`; `SPEC.md` 7.1; `CHANGELOG.md`.

- [ ] **Task 1 (`P5-I3`, decision 6):** `ddd generate` writes a manifest of the files it wrote
      beside them and removes, on the next run, those it no longer writes; the module needs no
      change for `ninja -t clean` to become equivalent to a fresh build. Test: a component
      removed from the link graph, then a rebuild and a clean.
- [ ] **Task 2 (`P10-I1`, decision: the loader):** an include entry that names an existing file
      is taken as that file before it is taken as a pattern. Test: a directory named `proj [v2]`.
- [ ] **Task 3 (`P10-I2`):** `ddd_generate` and `ddd_add_component` refuse a keyword given
      without a value, naming it.
- [ ] **Task 4 (`P5-I4`, decision: the tool):** `load_address_map` range-checks only the symbols
      the dictionary carries and reports the others in the `address-missing` note; the recipe on
      the page then completes on a 64-bit host.
- [ ] **Task 5 (`P5-M10`, `P10-M12`, `S-M3`, `P5-M16`, the rest of `P7-M9`):** a component whose
      file cannot be parsed still gets its check target; the module compares its own version with
      the tool's at include time; the build page's include-isolation sentence says what the module
      builds; the `docs` compose service stops reinstalling `.[docs]` on every run, and either a
      job builds `docker/Dockerfile` or the developer page says the image is unguarded.
- [ ] **Task 6 (`P10-M1`, `M2`, `M3`, `M4`, `P6-M13`):** the c model buckets objects and
      instances by owner once; the a2l indexes leaves by instance once; a run with an address map
      builds the a2l model once; the alignment walk is memoised. Test: a generation bounded in the
      size of the project. With them the language server's repeated work: `collect` loads a
      containing project twice per refresh and `workspaces` does both again on the first request
      after a save (the previous review's "three lookups, two implementations"), which one
      `resolve_projects(document)` used by both would settle.
- [ ] **Task 7:** the cmake tests the review lists as missing (`STRICT`, `ADDRESS_MAP` and the
      two-run flow, `NO_PROPAGATE_HEADERS`, `LINK_LIBRARIES`, `DEPENDS`, `BYTE_ORDER`,
      `OUTPUT_DIRECTORY`, `NAME` defaulting, `DDD_A2L`, `<stem>_ddd_check`, a failing
      `<target>.ddd`), and a class-scoped configure so the file stops costing a third of the
      suite (`P11B-M14`).

## Branch 7: `fix/loader-and-models` (off branch 6)

**Files:** `src/ddd/loading.py`, `src/ddd/models/objects.py`, `common.py`, `constants.py`,
`conversion.py`, `rasters.py`, `reserved.py`, `types.py`, `component.py`;
`src/ddd/identity.py`, `src/ddd/analysis.py`; `schemas/*.json`; `tests/test_models.py`,
`tests/test_loading.py`, `tests/test_hardening.py`; `CHANGELOG.md`.

- [ ] **Task 1 (`P2-I1`, decision 10):** every arm of `InitScalar` is strict, so `["1", "2"]` and
      `["on", "off"]` are refused where `"1"` already is. Changelog migration note.
- [ ] **Task 2 (`P2-I3`):** `_meaningful` drops an item whose input is a list or an object when a
      strictly deeper item exists under it, so a nested `init` mistake is one finding at the
      innermost pointer.
- [ ] **Task 3 (`P8-I2`, `P8-I3`):** the pointer walk advances only when a segment was present,
      and `_one_per_place` keys on the pointer computed with the document.
- [ ] **Task 4 (`P9-I3`, decision: fold):** one `init-invalid` per declaration, naming the count
      and the first offending values.
- [ ] **Task 5 (`P8-M2`, `M3`, `M4`, `M16`, `M1`):** the `<stddef.h>` names and the `_WIDTH`
      family join `reserved.py`; the a2l format pattern uses `[0-9]`; `_resolve` stops expanding
      a leading tilde; a raster name is held to printable ASCII; a `condition` may not end in a
      backslash.
- [ ] **Task 6 (`P8-M5`, `M6`, `M18`, `P5-M4` write side):** `assign` decodes an escaped key,
      keeps a file's own line ending, and writes through a temporary.
- [ ] **Task 7 (`P8-M10`, `M11`, `M12`, `M14`, `M15`, `M17`, `P2-M6`, `M8`):** a bounded cycle
      count; the mapping form of `enumerators` keeps its keys in a pointer and publishes its
      bounds and name pattern; an extension key that is not an identifier is refused; a
      drive-relative pattern is joined like a literal; a file too large to read is a finding; a
      raster reference is held to the declaration's spelling.
- [ ] **Task 8 (`P8-M8`, `M9`):** a dump is parsed once rather than three times, and `ddd
      --version` does not import the backends.
- [ ] **Task 9 (`P3-M1`, `M2`, `M3`, `M4`, `M5`, `M6`, `M9`, `P9-M1`, `M2`, `M3`, `M6`, `M7`,
      `M8`, `M10`):** the analysis's own minors - the `explained` expression, `duplicate-id` over
      the census, a text init on a dropped declaration, the enumerator pointer, the owner under a
      silenced clash, the standalone trace, the second copy of a duplicate, the cyclic-types
      docstring, a member with no storage, the bitfield phrase, the enum note's location, the
      element order of an instance, the second enum registration, and the rules spelled twice.

## Branch 8: `docs/review-corrections` (off branch 7)

Every sentence the review found wrong that an earlier branch did not already correct.

**Files:** `SPEC.md`; `README.md`; `docs/*.rst`; `docs/file_formats/*.rst`; `CHANGELOG.md`;
`tests/test_documentation.py`.

- [ ] **Task 1 (`P1-I1`, `I2`, `I4`, `I5`):** the `--renames` member spelling; what `dump -o`
      does under an error finding; the same-bytes promise now that includes sort by code point
      (decision 2, whose loader change lands in branch 7 task 7); the enumerators in
      `changed-interface`.
- [ ] **Task 2 (`P1-M1`, `M2`, `M3`, `M5`, `M6`, `M7`, `M8`, `M9`, `M11`, `M12`):** the
      requirement words and their subjects; the `must` with no check; a member's
      `dimension-value`; a string's `init`; `--plugin`; `<NAME>`; the undefined terms; the
      concept rows; the six small inconsistencies.
- [ ] **Task 3 (`P2-M1`, `M2`, `M3`, `M4`, `M5`, `P1-M4`, decision 11):** the README's "named
      integer"; the page that contradicts itself about the include depth; `StringConversion` on
      the contracts page; the "literal as written" claim in three places; the four python-only
      rules in the schema descriptions.
- [ ] **Task 4 (`P3-M8`, `P5-M15`, `P7-M11`, `SD-M3`, `M4`, `M5`, `M6`, `M8`):** the checks page's three
      drifts; the vocabulary table and the undefined terms on the site; the dictionary reference's
      five missing records; the conversion `kind` descriptions; `rasters` in the component
      sentence; the hover texts naming python identifiers; the README's relative links, which
      ship as the PyPI description and resolve only on GitHub; and `docs/concept.rst:145`, which
      still makes the include-isolation claim branch 6 corrected on the build page and in the
      README.
- [ ] **Task 5:** the changelog entry for the whole review, naming every migration the eight
      branches introduce, and a `tests/test_documentation.py` guard that every `BaseModel`
      exported by `ddd.models` is rendered on the contracts page (`P2-M3`).

## Branch 9: `test/review-gaps` (off branch 8)

**Files:** `tests/*`; `docs/developer_documentation.rst`.

- [ ] **Task 1 (`P11A-I1`):** the infinity test states `kind` and `volatile` and asserts the
      `definition.conversion.factor` pointer and "finite number".
- [ ] **Task 2 (`P11A-M1`, `M3`, `M5`, `M8`, `P11B-M1`, `M2`, `M3`, `M7`, `M8`, `M10`, `M15`):**
      the dead alternative; the three assertion-free tests; the dead statements; the nine order
      pins sorted; the no-op `--strict` test; the `didSave` assertion; the three posix-vacuous
      uri tests; the stale docstring; the spy replaced by bytes; the unasserted exit codes.
- [ ] **Task 3 (`P11A-M4`, `M11`, `P11B-M13`):** an `ast` walk asserting every identifier passed
      to `bag.add` is registered; the `DERIVED_AS` claims executed; a compiler among the tools
      `tests/test_cmake.py` says exist; and the second `# pragma: no branch`, at
      `src/ddd/cli.py:112`, which branch 5's implementer found to be over a branch the suite does
      reach - branch 2 removed only the one the review named.
- [ ] **Task 4 (`P11A-M6`, `M7`, `P11B-M12`):** `build_record`, `framed` and `sent` move to
      `conftest.py`; one family of types-file builders replaces the five spellings.
- [ ] **Task 5:** the highest-value gaps of the two consolidated lists that the earlier branches
      did not already close, chosen by what they would have caught: the locations of the findings
      an editor underlines, `--strict` on an analysis warning, `-b` reaching discovery
      (`P11B-I2`), a plugin printing under each format, and the transcript harness reporting the
      count of commands it does not run (`P11B` question 3).

---

## Left open by the implementers

Recorded as each branch landed, so that nothing is lost between a task and the release notes.

- **An instance's `a2l` is not compared** (branch 4 task 4, `S-I4`). The five other
  variable-level fields moved to the instance; `a2l` did not, because the analysis folds an
  instance's `export` into every leaf and its `format` and `display_identifier` reach no record
  at all. So flipping a variable's `a2l.export` is still one `changed-a2l` per member, and
  changing its `display_identifier` is no finding. Separating the two halves needs a dictionary
  format change, which no decision of this plan covers. The pages say what the code does.
- **A structure member's dimension count is not capped** (branch 3 task 5, `S-M1`). The cap of 64
  dimensions is on a declaration's own shape, where the `RecursionError` was; a member with 600
  dimensions produces no traceback, only an unbounded shape, so the asymmetry is left for a
  decision rather than fixed by guesswork.
- **`1.0` on a boolean is accepted** where `1.0` on `uint8` is refused (branch 4 task 7,
  `P9-M9`'s second half). Refusing it is a behaviour change no decision covers.
- **An artefact a project stops providing keeps the files it wrote** (branch 6 task 1,
  `P5-I3`). A run weighs only the artefacts it produced itself, because `ddd generate a2l`
  into the directory a `generate all` filled has to regenerate the a2l "without touching the
  sources the image was built from" (`SPEC.md` section 6), and the same holds for `--without`
  and for `NO_A2L`. So a plugin a project stops naming leaves its header behind: the run
  produces no artefact of that name and therefore weighs none of its entries. Weighing the
  entries whose artefact the project can no longer produce *at all* would close it, but the
  manifest keys on the name a plugin's backend object gives itself, which a run that does not
  instantiate that backend cannot know - so the rule would delete the files of a plugin whose
  backend happens to be named otherwise. Keying a plugin's artefact on the plugin's name is
  the change that would make it safe, and no decision of this plan covers it.
- **The `.rodata` / `.data` measurement of the artefacts page was not re-measured** (branch 3 task
  7): `docker compose` cannot run on the machine the fixes were written on and MinGW emits PE
  sections, so the page now says what was measured and when rather than quoting a number nobody
  can reproduce.

## Self-review

**Coverage.** Every id of the review's verified list is named in exactly one branch above,
except: `P7-I3` and the four release questions (the maintainer's), `P10-M13` and `P10-M11`
(documented rather than changed, branch 5 task 9 and branch 3 task 7), `P2-I2` and `P2-M6` (the
deferred strict-mode residue, kept deferred by decision 10), `P11B-I2` (branch 9 task 5),
`P4-M11`'s Windows device names (unreproducible on this machine; the path-length half is branch 3
task 7), `P9-M11` (the layer table's wording, branch 2 task 5), `P8-M17` (branch 7 task 7).
`P6-M13` was missing from every branch when this plan was first written, as the implementer of
branch 1 noticed; it is in branch 6 task 6, beside the other measured repetitions. `P7-M11` was
missing the same way, as branch 2's implementer noticed; it is in branch 8 task 4, with the other
pages. Branch 2 left two halves of `P7-M9` (the `docs` service reinstalling `.[docs]`, and no
workflow building the image); they join branch 6 task 5, where the build is.

**Order.** Branch 3 task 3 introduces the tolerance helper that branch 4 task 2 consumes; branch
7 task 7 changes the include sort that branch 8 task 1 documents; branch 1 task 3 changes the
publication spelling that its own task 3 tests. No task consumes something a later branch
produces.

**Placeholders.** Each task names its finding ids; the review's section for each is the
specification, with the trigger to turn into a test and the fix in a sentence. No task says
"handle edge cases" or "add validation" without naming the input that must be refused.
