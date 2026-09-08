# Complete review of DDD, 2026-09-08

A whole-tool review run as a sequence of independent passes, each by one reviewer reading the
material fresh. The passes, in order:

1. `SPEC.md` on its own: contradictions, gaps, ambiguities, requirement words, undefined terms.
2. File formats: `SPEC.md` section 3 against the published schemas, the pydantic models, the
   loader and the file format documentation.
3. Consistency checks and comparison: `SPEC.md` section 4 against `analysis.py`, `compare.py`,
   `identity.py`, `diagnostics.py` and their documentation.
4. Generated artefacts and address information: `SPEC.md` sections 5 and 6 against `ir.py`,
   the backends, `build_info.py`, the shipped templates and their documentation.
5. Tool interface: `SPEC.md` sections 3.11 and 7 against `cli.py`, `plugins.py`, `Ddd.cmake`,
   the language server, the editor extension and their documentation.
6. The remaining documentation and repository: getting started, concept, FAQ, data contracts,
   developer documentation, README, CHANGELOG, examples, docker, CI, packaging.
7. Code review of the core: loading, analysis, ir, compare, identity, diagnostics, models.
8. Code review of the periphery: cli, plugins, backends, build_info, lsp, cmake module,
   extension.

Line numbers refer to master at `441c600` unless a pass says otherwise.

## Baseline

`python -m pytest` on master at `441c600`, Python 3.13, Windows: 1910 passed, 12 failed,
coverage 100%. The 12 failures are environmental: the eleven in `tests/test_cmake.py` need
`cmake`, `ninja` and `ddd.exe` beside the interpreter (they come from `requirements-dev.txt` in
a venv), and `tests/test_lsp.py::TestSymlinkedWorkspace` needs a Windows privilege the shell
does not hold.

## Summary

Eight passes, 6 Critical, 65 Important and 87 Minor findings, plus the open questions each
pass left. Every finding was verified by the reviewer that reported it against the text or by
running the tool; the one that decides whether the editor integration works on Windows (pass 8,
Critical 1) was reproduced a second time by hand. Two findings are reported twice because two
passes met them from different sides: the spec's denial of `--standalone` (pass 1 Important 1,
pass 5 Critical 1) and `address-missing` on an empty map (pass 1 Critical 1, pass 3 Important 4).

| pass | subject | Critical | Important | Minor |
| --- | --- | --- | --- | --- |
| 1 | the specification on its own | 1 | 18 | 21 |
| 2 | file formats: spec, models, schemas, docs | 0 | 5 | 9 |
| 3 | consistency checks and comparison | 1 | 11 | 8 |
| 4 | generated artefacts, address map, dictionary | 0 | 7 | 7 |
| 5 | tool interface: CLI, plugins, CMake, editor | 1 | 7 | 11 |
| 6 | remaining documentation and repository | 0 | 3 | 11 |
| 7 | code review of the core | 0 | 8 | 9 |
| 8 | code review of the periphery | 3 | 6 | 11 |

**Verdict.** On a project a team would plausibly write, the tool gives the right answers, the
generated C compiles warning-free under the CI flag set, the A2L is well formed, the outputs
are deterministic, throughput is linear, and the tutorial, the transcripts, the static checks,
the docs build and the release machinery all hold. The problems are of three kinds.

1. **The specification has drifted behind the last two releases.** It still denies
   `--standalone`, says `address-missing` fires on an empty map, keys `COMPU_METHOD` sharing
   on conversion and unit alone, and under-specifies the artefacts it calls public contracts:
   the dictionary, the `--renames` file, the listings, the A2L file name, the CMake targets, the
   plugin name grammar. Two load-bearing words, "instance" and "storage", are undefined or
   overloaded. All of it is sentences, not redesign; pass 1 proposes wording for each.
2. **The editor integration does not survive contact with VS Code on Windows, and its edits
   are unsafe.** The server decodes `file:///c%3A/...` into a relative path and exits on the
   first opened file; rename and quick-fix edits are computed from the disk and applied by the
   client to its buffer; and opening a repository runs the Python its description files name,
   with no warning and no trust check.
3. **The edges of the input space are guarded in one place and not in the others.** Relaxing
   `unknown-reference` puts a curve into the C as a scalar and a dangling name into the A2L;
   `incomplete-project` is silent for most of the drops it exists for, and a dropped
   declaration makes the ownership checks accuse the wrong component; huge integers, deep
   recursion and per-element expansion end in tracebacks; the loader accepts quoted numbers the
   published schema refuses; findings are lost whenever a step after the analysis fails; and
   the plugin boundary is thinner than its docstrings claim.

**What to fix first, in order.**

1. Language server URI decoding on Windows (pass 8, Critical 1).
2. Edits from the client's buffer, with versioned `documentChanges` (pass 8, Critical 2).
3. State the plugin trust boundary in the editor docs and the spec, and gate the extension on
   workspace trust (pass 8, Critical 3).
4. Mark dropped declarations instead of erasing them, so that `incomplete-project` fires for
   every silenced drop and `missing-producer` / `unused-output` stop accusing the other
   component (pass 3, Critical 1; pass 7, Important 1; pass 7, design note 1).
5. Drop an object whose reference does not resolve, or guard both backends against it
   (pass 3, Important 1; pass 4, Important 1).
6. Report the findings before any fallible output step: `--renames`, the address map, the
   templates, the plugin hooks (pass 8, Important 4; pass 3, Important 5).
7. The server's handling of a build record naming an unknown check (pass 5, Important 1).
8. The plugin boundary: `sys.modules` before `exec_module`, paths normalised and kept inside
   `-o`, `SystemExit` caught, factory results validated, atomic writes (pass 8, Important 1,
   2, 3, 5, 6).
9. Core robustness: bounded integers, bounded recursion, the pointer sort on non-decimal
   digits, a leaf-count limit before flattening, strict mode on the models, scalar types
   checked at their declaration (pass 7, Important 2 to 8).
10. `ddd sources` reporting its findings in text mode, `ddd checks` printing the
    whole-project flag, the enum-reorder double report (pass 5, Important 2 and 4; pass 3,
    Important 2).

**Specification updates, grouped.** `--standalone` and the per-component target, the
`<image>_ddd_headers` / `<image>_ddd_globals` names, `DDD_A2L`, the multi-config refusal
(passes 1 and 5); the empty address map and the one-per-run shape of `address-missing`
(passes 1 and 3); the `COMPU_METHOD` key, the boolean display format, the closure over an
exported axis's input, the `GROUP` contents, the A2L file name and `-o`, the record order
(passes 1 and 4); a `typename` compared as what it resolves to, the alignment need per
datatype, references into another component's `local` object, per-member `renamed-object`,
the verdict criterion, the `--renames` shape, the tolerant exit of `sources` and `artefacts`
and the listing orders (passes 1, 3 and 5); a section describing the dictionary (pass 1
Important 8, pass 4 answer k); the plugin name grammar and reserved names (passes 1 and 5);
`"dimensions": []` as the scalar spelling (pass 2); the terms "instance", "leaf" and
"storage" (pass 1).

**Documentation updates, grouped.** The stale schema descriptions of `identity`, a
definition's `unit`, `StructType.name`, `Enumerator.value`, `scope: output` and "a
calibration tool only reads a measurement" (pass 2); the checks reference's account of
`--standalone` and of which load-time errors withhold the interface checks (pass 3); `ddd
dump` where four pages say `ddd list` for the container's symbol check (pass 4); where a
project-wide vocabulary file goes in CMake, and who produces the address map (pass 5); the
README's `NO_PROPAGATE_HEADERS` paragraph, the sdist contents, the ten models missing from
`data_contracts.rst` (pass 6).

**Test gaps worth closing first.** A Windows client's URI spellings and a buffer that differs
from the disk (pass 8); a dropped declaration with a surviving counterpart in another
component (pass 7); the empty and the hole-carrying address map through the CMake module,
`STRICT` and `SEVERITY` reaching the record and the commands (pass 5); `incomplete-project`
for a poisoned type and for a silenced axis (pass 3); the `_2` suffix on a `COMPU_METHOD`
name collision and a `boolean` in the A2L (pass 4); a mixed-case type name against the
published schema (pass 2).

**Open questions for the maintainers** (each pass lists its own; these decide behaviour):
whether a reference to another component's `local` object is a use; whether a `typename`
should compare as spelled or as resolved; whether the baseline's own plugins load in a
comparison; what "can replace" counts, the candidate's own errors and the baseline's carried
errors included or not; which names `reserved-identifier` polices; whether a project-level
extension block for an unloaded plugin is `schema` or `unknown-extension`.

## Pass 1: SPEC.md, internal quality

Review of `SPEC.md` (1729 lines, sections 1 to 7) as a normative document, on its own terms.
Line numbers refer to the file as checked out at commit `441c600`.

### Scope covered

- The whole of `SPEC.md`, read in six contiguous chunks (lines 1-205, 206-445, 445-700,
  700-1022, 1023-1320, 1321-1521, 1522-1729). No section was sampled or skipped.
- Table of contents against headings and every `[section N](#anchor)` reference against
  the heading anchors, checked mechanically: all resolve, numbering is continuous.
- The examples of sections 3.1, 3.4, 3.5, 3.7, 3.9, 3.10 and 3.11 checked against the
  rules they illustrate: none violates its own rule.
- Secondary sources, read in full: `CHANGELOG.md` sections "Unreleased" and "0.8.0", and
  the four design documents under `docs/superpowers/specs/`.
- I looked at the source four times, only to settle whether the changelog or the spec
  describes the shipped tool: `src/ddd/cli.py` (`--standalone`, the empty address map),
  `src/ddd/backends/a2l/model.py` (the `COMPU_METHOD` sharing key, the boolean display
  format) and `src/ddd/plugins.py` (reserved artefact names). Each place where I did so is
  marked "(code checked)" below. I did not review the code, the schemas or the RST
  documentation against the spec; that is the work of later passes.

### Strengths

- Section 1.1 is a real convention, not a preamble: the requirement words are defined, the
  plain present tense is declared binding, and the document mostly honours that (the
  exceptions are listed under Minor 1).
- Every check has a stable identifier, a default severity by list membership, an anchoring
  rule ("reported once per declaration that deviates, ... with a note pointing at the
  reference", `SPEC.md:1049-1056`), and the set of checks that need the whole project is
  spelled out once (`SPEC.md:1039-1043`) and referred to, not restated, from 7.2.
- Key ownership is one rule applied consistently: 3.3.1.2 defines the producer-only keys
  and section 4 carries exactly one `consumer-*` check per key (`consumer-storage`,
  `consumer-raster`, `consumer-identity`, `consumer-extension`). 3.3.1.3 even owns up to
  the misnamed `storage-mismatch` rather than silently redefining it.
- The rationale sits beside the rule (why `volatile` has no default, why `const volatile`
  costs RAM, why `init` is raw, why the definitions are one file), so the intent behind a
  requirement is recoverable when a later change has to touch it.
- Determinism is stated where it is cheap to forget: sort order of generated objects,
  wildcard expansion order, the code-point rule for names, the byte-identical rerender that
  keeps a second run from rebuilding.
- The three recent features (rasters, identity, plugins) landed in the spec in the shape
  their design documents agreed, including the later revision that put plugin artefacts
  under `ddd generate all`.

### Issues

#### Critical

1. **A first build with a seeded address map and `STRICT` can never reach its link step.**
   - Where: `SPEC.md:1188-1191` (`address-missing`), `SPEC.md:1629-1635` (the seeded map),
     `SPEC.md:1586-1590` (exit codes, `generate` writes nothing), `SPEC.md:1640` (`STRICT`).
   - What: section 4 says `address-missing` "fires only when a map is supplied: without one
     every address is zero by construction, which is the run a build makes before it has
     linked anything." Section 7.1 says the first build *does* have a map: "A map named
     inside the build tree that does not exist yet is seeded empty at configure time, so
     that the first build runs with address zero instead of failing over a file only the
     link can produce." An empty map is a supplied map, so by the letter every exported
     object earns an `address-missing` warning on the first build. Under `STRICT` those are
     errors, and "`ddd generate` with error findings writes nothing": the definition sources
     are never rendered, the image is never linked, and the map the second run waits for is
     never produced. Without `STRICT` the flow survives, but every first build reports one
     warning per exported object, which is precisely the case section 4's own rationale
     says is not a finding.
   - Why it matters: the two-run flow of 1.6 and 7.1 is the build integration's central
     promise, and `STRICT` is a normal CI setting. The shipped tool already deviates from
     the text: CHANGELOG 0.8.0 says "An empty address map is a first run rather than a map
     with holes: it raises no `address-missing`", and `src/ddd/cli.py:625` implements that
     (code checked). The spec describes behaviour the tool was deliberately changed away
     from.
   - Fix: in section 4, "It fires only when a map with at least one entry is supplied:
     without a map, or with an empty one, every address is zero by construction, which is
     the run a build makes before it has linked anything." In 7.1, add after "seeded empty
     at configure time": "and an empty map raises no `address-missing`, so the first build
     passes under `STRICT`".

#### Important

1. **Section 7 denies a command line option the tool has (`--standalone`), and 7.1 omits the
   per-component check target that uses it.**
   - Where: `SPEC.md:1570-1573`; `SPEC.md:1653-1655`; CHANGELOG 0.8.0 "Checking a component
     on its own".
   - What: "a component alone is checked with every check, the whole project ones included,
     because holding them back is the editor's leniency (section 7.2), not the command
     line's." The changelog says the opposite: "`ddd check --standalone` holds back the
     checks that need every component of a project, derived from the registry the way the
     language server derives them, and an explicit `-W` on the same run still wins. The
     CMake module's per-component target uses it". `src/ddd/cli.py:154` defines the option
     (code checked). Section 7.1 knows only the image-level `<stem>_ddd_check` target.
   - Why it matters: a public option with a severity-policy interaction ("an explicit `-W`
     ... still wins") is unspecified, and the one sentence the spec does have about the case
     is false about the tool. An implementer of 7.1 also cannot build the per-component
     target the module ships.
   - Fix: replace the clause with "a component alone is checked with every check unless
     `--standalone` holds back the ten whole-project checks of section 4, the way the editor
     does (section 7.2); an explicit `-W` on the same run overrides that policy." In 7.1,
     add the per-component target: its name, that it runs `ddd check --standalone` on the
     registered files, and under which severity policy.

2. **"instance" and "leaf" are load-bearing terms that section 2 never defines.**
   - Where: `SPEC.md:980`, `SPEC.md:1012-1013`, `SPEC.md:1208`, `SPEC.md:1235`,
     `SPEC.md:1308-1309`; the concept table `SPEC.md:139-161`.
   - What: `missing-id` is defined as "a producing declaration or instance states no `id`",
     `--renames` lists "a member of a structured object ... under its instance's `id`", and
     3.11 says "A leaf of a structured variable carries no block; the instance carries one
     for the whole structure." Section 3.3.2 calls the same thing "a structured object" and
     never uses "instance". "Leaf" appears once. Neither is in the concept table, which
     defines "declaration", "definition", "data object" and "access path".
   - Why it matters: "a producing declaration *or* instance" reads as if an instance were
     something other than a declaration, so a reader cannot tell whether `missing-id` fires
     once per structured object or once per member. The `--renames` format and the
     dictionary (`objects` / `instances`, per the changelog) are keyed on the distinction.
   - Fix: add to section 2: "**instance** | a declaration naming a structure type; one C
     object whose members are data objects in their own right, each reached by its access
     path" and "**leaf** | one value-holding member of an instance, as the dictionary and
     the A2L see it". Then use "structured object" or "instance" consistently in 3.3.2, 3.7
     and 5.2, and drop "or instance" from `missing-id` or explain it.

3. **"storage" carries three meanings, and the spec acknowledges only two of them.**
   - Where: datatype sense at `SPEC.md:459`, `SPEC.md:529`, `SPEC.md:753`, `SPEC.md:769`
     ("the storage (`datatype` or `typename`)", "A definition states its storage exactly
     once", "opaque storage"); placement sense at `SPEC.md:477-487` ("The storage keys are
     `init` and `section`"); the acknowledged third sense at `SPEC.md:496-500`,
     `SPEC.md:1170`, `SPEC.md:1274` (`storage-mismatch` polices presentation,
     `changed-storage` covers volatility and raster).
   - What: 3.3.1.1 lists "the storage" among the *interface* keys, and the very next
     subsection is titled "Storage" and holds `init` and `section`, which are not interface
     keys. 3.3.1.3 explains that the check names use "storage" more broadly than the groups,
     but not that the group named "Storage" and the "storage" of 3.3.1.1 are different
     things.
   - Why it matters: "a claim over storage the component does not own" (`SPEC.md:479`) and
     "states its storage exactly once" (`SPEC.md:529`) use the same word for a producer-only
     key and for a key every declaration must state; a reader of `consumer-storage` can
     reasonably expect it to cover `datatype`.
   - Fix: reserve "storage" for the 3.3.1.2 group (or for the check names, but pick one),
     and say "the datatype, stated as `datatype` or `typename`" at 459, 529, 753; "opaque
     bytes" at 769.

4. **By the letter, a `boolean` object defaults to the display format `%8.3`.**
   - Where: `SPEC.md:371-373`; `SPEC.md:1468-1471`.
   - What: 3.3 rules that "`boolean` does not count as an integer datatype"; 5.2 says the
     format "defaults to `%8.0` for integral values, that is an integer datatype under an
     identity or under a linear conversion whose `factor` and `offset` are whole numbers,
     and to `%8.3` otherwise". Composed, a boolean is "otherwise". The tool treats boolean
     as integral (`src/ddd/backends/a2l/model.py:586`, code checked), so the spec and the
     tool disagree on the emitted file.
   - Why it matters: a conforming implementation produces a different A2L from the shipped
     one, and the difference is visible in every calibration tool.
   - Fix: at 1468, "for integral values, that is a `boolean` or an integer datatype under an
     identity or ...".

5. **The `COMPU_METHOD` sharing key is stated as conversion and unit; the tool and the
   changelog key on the display format as well, and the spec leaves the shared method's
   format undefined.**
   - Where: `SPEC.md:1429` ("shared between objects with the same conversion and unit");
     `SPEC.md:1459-1462` (names `CM_LIN_<unit>`, `CM_IDENT_<unit>`); `SPEC.md:1468-1471`;
     CHANGELOG 0.8.0 "The a2l keeps one `COMPU_METHOD` per display format".
   - What: an A2L `COMPU_METHOD` carries a format string. Under the spec's key, a `uint8`
     identity in volts and a `float32` identity in volts share `CM_IDENT_V`, and nothing
     says whether that record states `%8.0` or `%8.3`. The tool keys on (conversion, unit,
     default format of the datatype) (`src/ddd/backends/a2l/model.py:495`, code checked),
     which the changelog records as a fix.
   - Why it matters: generated identifiers and record counts differ between a conforming
     implementation and the tool; the `_2`, `_3` suffix rule (1461) then applies to
     different collisions.
   - Fix: "shared between objects with the same conversion, unit and default display
     format (the format derived from the datatype and the conversion, 1468), so that a
     method never states a format one of its objects would override".

6. **The comparison's verdict has no stated criterion, and the candidate's own findings have
   no stated place in the report.**
   - Where: `SPEC.md:1222-1228`, `SPEC.md:1229-1230`, `SPEC.md:1583-1584`,
     `SPEC.md:1586-1589`.
   - What: 4.1 specifies that "The baseline is analysed in its own right, and only its error
     findings are carried into the report, each prefixed with 'in the baseline:'", but says
     nothing about the candidate, which "**may** also be given as a project or component
     description". The verdict line says "whether the candidate can replace the baseline"
     without saying when it can: no comparison finding at error severity? Also no error in
     the candidate's own analysis? Do the baseline's carried errors count? Section 7 ties
     exit code 1 to "findings reported as errors" without saying which findings a `compare`
     run counts.
   - Why it matters: a CI gate keys on the exit code and the verdict; two implementations
     can disagree on whether a candidate that fails `ddd check` "can replace" a baseline.
   - Fix: state (a) the candidate is analysed and all of its findings are reported, at their
     own severities; (b) the verdict is "can replace" exactly when no finding of the run,
     candidate analysis and comparison included, is reported as an error, the baseline's
     carried errors excluded or included, whichever is intended; (c) exit code 1 follows the
     verdict.

7. **The `--renames` file is a public JSON format whose keys the spec never names.**
   - Where: `SPEC.md:1230-1236`; design 2026-09-03 section 7.
   - What: "as its `id`, its old name and its new name, sorted by the new name ... a member
     of a structured object is listed under its instance's `id` followed by its member
     path". The design settles `[{ "id", "from", "to" }]` and that an empty comparison
     writes `[]`; the spec states neither the key names, nor the top-level shape, nor how
     "its instance's `id` followed by its member path" is spelled (one string? two keys?).
   - Why it matters: the file exists "so that a calibration dataset ... can be migrated
     without parsing the findings", which means a script parses it; the changelog calls the
     json file formats public interface.
   - Fix: "a JSON list of objects `{"id", "from", "to"}`, sorted by `to`; for a member,
     `id` is `<instance id>.<member path>`; a comparison with no rename writes `[]`."

8. **The data dictionary, the artefact the spec calls a published contract, is described
   nowhere in the spec.**
   - Where: `SPEC.md:160` ("the contract between the checking front end and the output
     backends, and DDD publishes it"); `SPEC.md:1594-1599` (`format`, today `7`);
     scattered statements of what it "records" at `SPEC.md:524-526`, `SPEC.md:660`,
     `SPEC.md:1009-1013`; `SPEC.md:1020` (the plugin API "is documented in the plugins page
     of the documentation").
   - What: section 5 covers C and A2L; nothing covers the dictionary's top-level keys, what
     an object, an instance and a leaf carry, which fields are resolved rather than as
     written, or what a reader of format 7 may assume of format 6 and older. The plugin API
     (`Plugin`, the three contexts, `CheckInfo`) is likewise delegated to documentation
     although the changelog calls the plugin contract part of the versioned interface.
   - Why it matters: "a generator DDD does not ship can consume it without depending on the
     implementation" is a promise only a specification can keep; the JSON schema documents
     the shape but not the semantics (which fields compare, which are resolved).
   - Fix: add a section 5.3 "Data dictionary" listing the top-level keys, the object /
     instance / leaf records with a sentence per field saying whether it is authored or
     resolved, the `format` history, and the rule for reading older formats; either
     specify the plugin API in 3.11 or state explicitly that the documentation page is
     normative for it.

9. **Whether `typename` and `datatype` compare as written or as resolved is not stated.**
   - Where: `SPEC.md:459` (interface key "the storage (`datatype` or `typename`)");
     `SPEC.md:549-551`; `SPEC.md:1063-1067` (`definition-mismatch`); `SPEC.md:1240-1241`
     (`changed-interface`); the spelling rule for constants at `SPEC.md:877-881`.
   - What: one declaration states `"typename": "Temperature_t"`, another states
     `"datatype": "uint16"` with the unit, conversion and limits the type fixes. 3.9 rules
     that a constant name and its value "are different spellings of one size" and must
     agree as spelled; 3.4 rules the same for conversions. For the type name the spec is
     silent, and `definition-mismatch` lists "datatype" without saying whether a type name
     is compared as a name. The same question arises for `changed-interface` between two
     deliveries (the plugins design doc lists "kind, datatype or type").
   - Why it matters: it decides whether a project can migrate consumers to a scalar type one
     component at a time.
   - Fix: one sentence in 3.3.1.1: "The datatype compares as spelled: a declaration naming
     a type and one naming the base datatype the type fixes disagree
     (`definition-mismatch`), exactly as a constant's name and its value do (section 3.9)",
     and the counterpart in 4.1.

10. **`section-alignment` compares against an alignment need the spec never defines.**
    - Where: `SPEC.md:641-647`; `SPEC.md:1450` (`MOD_COMMON` "fixed alignments (1/2/4/8,
      floats 4/8)").
    - What: "An object whose datatype needs stricter alignment than its section guarantees
      is `section-alignment`" - the need per datatype is not stated (natural alignment equal
      to the size? `boolean` as 1? `float64` as 8 on a target where `double` aligns to 4?).
      The only numbers in the document are the ones the A2L `MOD_COMMON` states, in a
      different section and for a different purpose.
    - Why it matters: the warning's firing condition is observable and toolchain dependent
      as written.
    - Fix: state the table once, in 3.5: "the need of a datatype is its size in bytes,
      `boolean` counting 1", and let 5.2 refer to it.

11. **What happens to a curve, map or axis whose referent does not exist is unspecified, and
    the changelog implies an answer the "dropped" rule contradicts.**
    - Where: `SPEC.md:1141-1144` (`unknown-reference`, `reference-kind`); `SPEC.md:884-886`
      (a declaration whose shape does not resolve is dropped); kind table `SPEC.md:387-389`
      (curve storage "array `[size of the axis]`"); CHANGELOG 0.8.0 ("leaves out a curve
      whose axis is unknown rather than writing it incomplete").
    - What: section 4 covers only the case where the referent "was declared but dropped as
      unresolvable" ("the referring object is dropped with it"). For an axis nobody
      declares, a curve's shape "`[size of the axis]`" cannot resolve, so 3.9's rule says
      the curve is dropped; the changelog says the a2l backend "leaves out" such a curve,
      which implies it was in the dictionary. For an axis whose `input` measurement does not
      exist, the axis's own shape resolves, so it stays, and 5.2 does not say whether its
      `AXIS_PTS` then names the missing measurement or `NO_INPUT_QUANTITY`.
    - Why it matters: with `unknown-reference` relaxed, the C, the A2L and `ddd list` are
      observably different under the two readings, and `incomplete-project` fires only under
      one of them.
    - Fix: in section 4, after the sentence about dropped referents: "A curve or map whose
      axis no declaration provides has no shape and is dropped the same way; an axis whose
      `input` names no measurement keeps its shape, stays, and reaches the A2L with
      `NO_INPUT_QUANTITY`" (or whatever is intended).

12. **Plugin names: the grammar is unstated and the reserved names `c`, `a2l`, `all` are in
    the changelog and the code but not in the spec.**
    - Where: `SPEC.md:991-996`; `SPEC.md:968` ("exposes a malformed one");
      `SPEC.md:1530-1533` (`ddd generate <name>` beside `c`, `a2l`, `all`); CHANGELOG 0.8.0
      ("A plugin cannot be named `c`, `a2l` or `all`"); `src/ddd/plugins.py:45` (code
      checked).
    - What: the name is the `extensions` key, the `ddd generate` artefact name and the
      prefix of every check identifier, yet its grammar (the design says
      `^[a-z][a-z0-9_]*$`) and its exclusions are not in the spec. "Malformed" in
      `plugin-invalid` has no definition to point at.
    - Why it matters: a plugin named `all` would be selectable by neither spelling; a plugin
      named `Layout` would produce check identifiers section 4 says follow the built-in
      grammar.
    - Fix: in 3.11: "`name` matches `[a-z][a-z0-9_]*` and is none of `c`, `a2l` and `all`,
      which name the built-in artefacts; a `PLUGIN` whose name breaks either rule is
      `plugin-invalid`."

13. **A project-level `extensions` block for a plugin the project does not load is either
    `schema` or `unknown-extension`, and the two are not equally relaxable.**
    - Where: `SPEC.md:972-977` (project block: "a block stated for a plugin that declares no
      project model is `schema` as well, as any unknown key is"); `SPEC.md:984-987`
      (definition block: "A block naming no loaded plugin is `unknown-extension`, an error;
      relaxing it is how a project carries a block no installed plugin interprets").
    - What: the project bullet covers a *loaded* plugin without a project model; the
      definition paragraph covers an *unloaded* plugin. A project block keyed by a name no
      loaded plugin has falls under "as any unknown key is" (`schema`, unrelaxable) or under
      "A block naming no loaded plugin" (`unknown-extension`, relaxable), and the text
      supports both.
    - Why it matters: the documented escape hatch (carrying a block for a plugin not
      installed) either works for the project block or does not.
    - Fix: one sentence in the project bullet: "A project block keyed by a name no loaded
      plugin has is `unknown-extension`, as on a definition."

14. **The orders of the listings are unstated, and so is whether `ddd sources` and
    `ddd artefacts` answer at all when the project has error findings.**
    - Where: `SPEC.md:1538-1546` (`ddd list`, `ddd artefacts`); `SPEC.md:1556-1560`
      (`ddd sources`); `SPEC.md:1563-1565` (`ddd checks`); `SPEC.md:1586-1589` (exit codes);
      CHANGELOG Unreleased ("`ddd artefacts` ... is tolerant the way `ddd sources` is: which
      artefacts exist follows from the plugins a project names, not from whether its
      interfaces agree").
    - What: 5.1, 5.2 and 7 state the order of generated objects, A2L records and
      diagnostics precisely; nothing states the row order of `ddd list` (by name? by
      component? are leaves rows?), the order of `ddd sources` (the design says sorted), of
      `ddd artefacts` or of `ddd checks`. The changelog describes `sources` and `artefacts`
      as "tolerant" of a project that does not check out; the spec's exit-code rule ("a
      findings exit is reserved for findings reported as errors") applied to them means a
      build system's configure step fails on the first `definition-mismatch`, which is the
      opposite of tolerant.
    - Why it matters: a build system parses `ddd sources` at configure time and depends on
      its exit code; a diff of two `ddd list` outputs is meaningless without a stated order.
    - Fix: state each order in section 7, and add: "`ddd sources` and `ddd artefacts` report
      their list whatever the findings and exit 0 unless the file tree cannot be read,
      because what a project is built out of does not depend on whether it is consistent."

15. **Neither the A2L output file name nor the output directory option of `ddd generate` is
    stated on the command line side.**
    - Where: `SPEC.md:1420-1445`, `SPEC.md:1516-1517` (`ddd generate a2l` "writes the A2L
      alone"); `SPEC.md:1621-1623` (only in the CMake context: the project name "becomes
      the A2L project, module and file name"); `SPEC.md:1638` (`OUTPUT_DIRECTORY` with no
      command line spelling, unlike `TEMPLATE_DIRECTORY (required, --template-dir)`).
    - What: 5.1 lets a build system derive the C file names from the template directory
      "without running the generator first"; for the A2L, the file name (`<project>.a2l`?)
      is stated only as a side remark in 7.1, and where it is written (`-o`?) is not stated
      at all; `-o` appears in the spec only for `ddd schema all` and `ddd build-info`.
    - Why it matters: a non-CMake build has to declare the A2L as an output.
    - Fix: in 5.2: "The file is written as `<project name>.a2l` into the output directory
      (`-o`, default the working directory)"; in 7.1: "`OUTPUT_DIRECTORY` (`-o`, ...)".

16. **The subjects of `reserved-identifier` are not enumerated, unlike those of the length
    cap and of `name-collision`.**
    - Where: `SPEC.md:1145-1150`; `SPEC.md:375-378` (the cap "holds wherever a name is
      written: objects, components, projects, enums, enumerators, types, members and
      `display_identifier`"); `SPEC.md:862-864` (constants: "`reserved-identifier` and
      `name-collision` apply to it").
    - What: "a name collides with a C keyword ..." - which names? A component named
      `int` becomes a header `int.h` and an A2L group, legal in both; a `display_identifier`
      reaches no C; a struct member named `_Bool` reaches C.
    - Why it matters: the check is an error, and whether a component or a
      `display_identifier` can trip it is observable.
    - Fix: "applies to every name that reaches the generated C: objects, enums,
      enumerators, types, members and constants; not to components, projects or
      `display_identifier`" (or whichever set is intended).

17. **The CMake targets a user is told to link are unnamed in the spec.**
    - Where: `SPEC.md:1610-1613` ("an interface library", "an object library of their own");
      `SPEC.md:1647` (`NO_PROPAGATE_HEADERS` "to stop that interface library being linked
      into every registered component"); CHANGELOG Unreleased ("Linking
      `<image>_ddd_headers` is enough now", `<image>_ddd_globals`).
    - What: a project that sets `NO_PROPAGATE_HEADERS`, or that compiles a target outside
      the link graph, has to link the interface library by name, and the changelog's
      migration note assumes the user knows it. 7.1 names `<stem>_ddd_check` but not the
      two libraries.
    - Fix: name them where they are introduced: "an interface library `<image>_ddd_headers`
      ... an object library `<image>_ddd_globals`".

18. **A baseline given as a project that names plugins: nothing says whether its plugins
    load, so its blocks may be refused and `missing-plugin` may misfire.**
    - Where: `SPEC.md:1015-1019` ("A comparison whose candidate is a project runs that
      project's plugins"); `SPEC.md:1222-1228` (either side may be a project, "The baseline
      is analysed in its own right"); `SPEC.md:1291-1294` (`missing-plugin`: "the baseline
      or the candidate records a plugin this run has not loaded").
    - What: only the candidate's plugins are addressed. A baseline project naming plugin X
      while the candidate names Y is analysed "in its own right": if X is not loaded, every
      block for X in the baseline is `unknown-extension` (an error, carried into the report
      as "in the baseline:"), and `missing-plugin` fires for X even though the baseline's
      files name it and it could have been loaded.
    - Fix: "Each side given as a description runs the plugins it names for its own analysis;
      the comparison hooks are those of the candidate, and `missing-plugin` is reported
      for a plugin a side records that the comparison did not run."

#### Minor

1. **Requirement words bound on actors other than DDD and the data.** `SPEC.md:96-97`
   ("the global data objects **shall** be defined and declared by code DDD renders" - a
   requirement on the project), `SPEC.md:672` ("A build **shall** therefore write a
   record"), `SPEC.md:1727` ("An editor extension **shall** do no more than launch the
   server"), `SPEC.md:432` ("**should** be confirmed on the toolchain a project ships with"
   - advice to the user, with no consequence for deviation). Section 1.1 defines **shall**
   as "a binding requirement on DDD" and **should** as a recommendation whose deviation
   "requires a reason". Fix: unbold and rephrase as statements of what the build, the
   extension and the project are expected to do, or extend 1.1 to say the words also bind
   the artefacts DDD ships (the CMake module, the extension).

2. **The refusal of a vocabulary file at the root of a run has no identifier or actor.**
   `SPEC.md:188` ("only the first two can be the root of a run"), `SPEC.md:710`,
   `SPEC.md:822-823`, `SPEC.md:848` ("handed to the tool as the root of a run, it is
   refused, with a hint"). By 1.1 a command line input violation is a usage error (exit 2),
   which is probably intended, but the four passages say "is refused" and the sections and
   rasters files are not covered by any of them. Fix: say once, at 188: "handed as the root
   of a run, any other kind is a usage error naming the include that should carry it."

3. **Terminology drift.** "scaling" for conversion (`SPEC.md:1064`, `SPEC.md:1240`, and 1.2);
   "variable" for data object throughout 3.10, 3.11, `SPEC.md:1200-1203` and the `ddd list`
   JSON key `variables` (`SPEC.md:1540`) beside the dictionary's `objects`; "a2l" in prose
   (`SPEC.md:897`, `SPEC.md:910`, 4's `raster-kind` and `unknown-raster`, `SPEC.md:1640`)
   against "A2L" elsewhere; "member path" (`SPEC.md:1443`, 5.1) against the defined "access
   path" (`SPEC.md:156`); "storage category" (`SPEC.md:1426`, `SPEC.md:1460`) never defined
   (it means the `VALUES` / `AXIS` record layouts). Fix: one spelling each; define
   "storage category" or say "per datatype, once for values and once for axis points".

4. **Two table cells that do not say what they mean.** `SPEC.md:317`: the default of `a2l`
   is given as "export", which is neither a value nor a rule (3.3.1.3 gives the rule:
   exported when no declaration states `export`). `SPEC.md:316` under "Attributes common to
   every kind" (`SPEC.md:301`) says `raster` is "on a measurement only". Fix: `{"export":
   true}` and a footnote, or move `raster` to the kind table.

5. **The note of a `definition-mismatch` on limits points somewhere section 4 does not
   allow.** `SPEC.md:470-472`: the reference for limits is the producer's, "otherwise ...
   the first declaration in load order that states them"; `SPEC.md:1052-1053`: the note
   points at "the producer's declaration or the first loaded one", which may be a
   declaration stating no limits. Fix: "or the reference declaration of section 3.3.1".

6. **`type-kind` is stretched to a case its definition does not describe.** `SPEC.md:787-788`
   (`init` on a structured declaration is `type-kind`) against `SPEC.md:1113-1115` ("a
   declared type is used where its shape does not fit"). Fix: extend the definition ("or
   carries a key a structured object cannot take, such as `init`").

7. **`enum-conflict` compares "ordered name and value pairs", but one of the two authored
   forms is a JSON object.** `SPEC.md:1128-1130` against `SPEC.md:566-568` (the mapping form
   `{"STATE_OFF": 0, "STATE_FAULT": 15}`). JSON does not define member order; the spec should
   say the textual order counts for both forms, since a reordering "conflicts".

8. **An omitted `unit` is a stated empty unit, not a deferral, and nothing says so.**
   `SPEC.md:306` (default `""`) against `SPEC.md:466-468` ("`limits` are the one interface
   key a declaration **may** leave out"). A consumer omitting `unit` where the producer says
   `rpm` is `definition-mismatch`; that follows from the text but is the kind of surprise a
   sentence would prevent: "An omitted `unit` is the empty unit and compares as such."

9. **3.3.1.2 opens by naming two storage keys and closes by saying the group holds five.**
   `SPEC.md:477` ("The storage keys are `init` and `section`") and `SPEC.md:486-487` ("this
   group holds exactly the keys a consumer **must not** state": `init`, `section`, `id`,
   `raster`, `extensions`). Fix: "The storage keys are `init` and `section`; the group
   also holds `id`, `raster` and `extensions`".

10. **Section 4's definition of `plugin-invalid` lacks the case 3.11 and 7.2 add.**
    `SPEC.md:1090-1091` lists import failure, no `PLUGIN`, malformed, duplicate name;
    `SPEC.md:1001-1004` and `SPEC.md:1710-1712` add "a hook that raises while a file is
    checked", reported by the language server under the same identifier. Fix: add the case
    to the section 4 entry.

11. **`reused-name` "is reported above the removal and addition it accompanies", but the
    stated ordering cannot put an info finding beside an error.** `SPEC.md:1253` against
    `SPEC.md:1580-1582` ("ordered by severity, then path, then location"). Only the removal
    can follow it; and the tie-break for findings at one location (the changelog says
    report order) is unstated. Fix: "above the removal" and add "findings at one location
    keep the order they were reported in".

12. **`include-cycle` is not named where cycles are ruled out.** `SPEC.md:231` ("Include
    cycles are an error") - every other refusal in 3.1 names its identifier.

13. **The export closure is narrower as written than its rationale needs.**
    `SPEC.md:1476-1479`: "a *pulled in* axis pulls the measurement indexing it". An axis
    exported in its own right has the same dangling input quantity if its measurement is
    not exported. Fix: "an axis in the file, exported or pulled in, pulls the measurement
    indexing it".

14. **The `GROUP` sentence mixes "contributes" and "declares".** `SPEC.md:1436-1438`: one
    group per component "that contributes at least one exported object, referencing the
    measurements and characteristics it declares" - it is not said whether the references
    cover the component's `input` declarations (so that an object shared by three
    components is in three groups) or only what it produces.

15. **Determinism promised but left to "fixed" or unstated orders.** `SPEC.md:1370`
    (external headers "in a fixed order" - which?), `SPEC.md:1623` (includes "keep the link
    graph's traversal order" - depth first? in what order over `target_link_libraries`?),
    `SPEC.md:1616` (`NAME` "sanitised into an identifier" - by what rule; it names the A2L
    file), `SPEC.md:1443` (records "sorted by object name" - the order of record *kinds*
    within the `MODULE` is not stated). 5.1 claims "the same project generates the same
    bytes on any machine", which each of these has to honour.

16. **`ddd_add_component(<target> JSON <file>...)` "registers descriptions, component and
    types files alike"** (`SPEC.md:1605`) - whether units, sections, constants and rasters
    files may be registered the same way, and on which target a project-wide vocabulary
    belongs, is not said.

17. **Lesser changelog behaviours the spec does not carry.** From 0.8.0 and Unreleased: a
    baseline is analysed without `--strict`; `ddd id --assign` fills an explicit
    `"id": null` and skips a file it cannot parse rather than rewriting it; a comparison
    with no rename writes `[]` (design doc); `NO_A2L` stops the address map being a
    generation dependency (`SPEC.md:1629-1631` says it always is); `ddd artefacts` names a
    plugin without a backend in a note. Each is observable; each is one sentence.

18. **Optional keys whose admissibility is left to "unknown keys are rejected".** Whether a
    scalar or struct type entry, or a struct member, may carry `description`
    (`SPEC.md:744-758` say nothing; only the external type has "`description` is optional",
    `SPEC.md:762`); whether a structured declaration stating `format` or `display_identifier`
    (`SPEC.md:790-794`: "per member, a whole structure having no display format of its own")
    is `schema` or silently ignored.

19. **Small unstated outcomes.** Whether a `boolean` `init` may be spelled `true`/`false` or
    only `1`/`0` (`SPEC.md:362-364`); whether `c_type` of an enum-converted object is the
    datatype or the generated `typedef enum` (`SPEC.md:360`, `SPEC.md:570-573`); which of
    `consumer-raster` and `raster-kind` an `input` declaration of a calibration object with
    a `raster` earns (`SPEC.md:1073-1078`, `SPEC.md:1121-1124`); where `ddd dump --format
    json` puts its findings when stdout is the dictionary (`SPEC.md:1585-1586`); which
    options a plugin artefact takes under `ddd generate <name>` (`SPEC.md:1530-1533`);
    whether `ddd check --baseline` accepts `--renames` (`SPEC.md:1526-1529`); what a
    malformed address map or an address over 32 bits produces - a usage error by 1.1's rule,
    but "**must** fit" at `SPEC.md:1511` names no consequence.

20. **Wording.** `SPEC.md:1267` "a baseline recorded before an id existed on either side"
    (meaning: at a format that had no `id` key); `SPEC.md:1230` "`--renames <file>` writes
    beside it" (it writes a file, not beside the verdict); `SPEC.md:551-552` "one object per
    member" against `SPEC.md:1483-1484` "one object per value-holding member".

21. **`duplicate-type` is the one vocabulary check that splits the same-file case off as
    `schema`.** `SPEC.md:765-766` against `duplicate-unit`, `duplicate-section`,
    `duplicate-constant`, `duplicate-raster` ("within one file or across files",
    `SPEC.md:1093-1100`). Not a contradiction, but a reader of the four parallel checks
    expects the fifth to match, and a same-file duplicate type cannot be relaxed while a
    same-file duplicate unit can.

### Open questions

1. **A curve may refer to an axis that is `local` to another component** ("Referring is not
   using", `SPEC.md:413-416`; `local`: "another component **must not** use it",
   `SPEC.md:169`). The letter allows it; the referring component's code cannot see the
   axis, only the calibration tool can. Intended, or should `reference-kind` (or a new
   finding) refuse a reference into another component's `local`?
2. **Does a type name compare as spelled** (Important 9)? The precedent of 3.4 and 3.9 says
   yes; the loader's convenience says a resolved comparison. Which is meant decides whether a
   project can introduce scalar types one component at a time.
3. **Do the baseline's own plugins load when the baseline is a project** (Important 18)?
   Both answers are defensible: loading them makes the baseline's analysis truthful; not
   loading them keeps "the plugins in play are the candidate's" simple.
4. **Is a project-level block for an unloaded plugin `schema` or `unknown-extension`**
   (Important 13)? The escape hatch reads as if the latter were intended.
5. **What does "can replace" mean** (Important 6)? Specifically whether the candidate's own
   `ddd check` errors and the baseline's carried errors decide the verdict.
6. **Which names does `reserved-identifier` police** (Important 16)? The C-facing set is the
   natural answer; the cap's set (`SPEC.md:375-378`) is the one the spec already has.

### Assessment

As a normative document the specification is in good shape: it has a real requirement-word
discipline, every check is identified and anchored, and the recent features arrived in the
shape their designs agreed. Its weaknesses are of two kinds. It has drifted behind the tool
in exactly the places the last two releases touched (`--standalone`, the empty address map,
the `COMPU_METHOD` key, the reserved plugin names), and one of those drifts leaves the
specified `STRICT` two-run build unable to start. And it under-specifies the artefacts it
calls public contracts - the dictionary, the renames file, the listings, the A2L file name -
while leaving two of its own load-bearing words, "instance" and "storage", undefined or
overloaded. All of it is repairable with sentences rather than redesign.

## Pass 2: the file formats (SPEC.md section 3.1 to 3.10)

### Scope covered

Read in full: `SPEC.md` lines 41-175 (conventions and vocabulary) and 176-942 (section 3);
every file of `src/ddd/models/` (`__init__`, `common`, `component`, `constants`, `conversion`,
`objects`, `project`, `rasters`, `reserved`, `schema`, `sections`, `types`, `units`);
`src/ddd/loading.py` whole; `src/ddd/build_info.py` (spec 3.6); the analysis excerpts the format
rules delegate to (`src/ddd/analysis.py` 930-960, 1010-1045, 1425-1450, 1560-1600, 1640-1725);
all ten pages of `docs/file_formats/`; `README.md` lines 96-462; the 34 `*.ddd.json` files under
`examples/`; the outline of `tests/test_documentation.py` and `tests/test_transcripts.py` (every
`$ ddd ...` transcript on the RST pages and in the README is re-run by a test, so the printed
outputs were not re-verified by hand).

Ran: `ddd schema all` into the scratchpad and diffed against `schemas/` (identical, the
published copies are current); `ddd check` over 46 throwaway description files covering the
rules reading alone could not settle; `jsonschema` (Draft 2020-12) over the published schemas
for the cases where the schema and the loader might part ways; `ddd check` over the spec's own
example files of 3.5, 3.7, 3.8, 3.9 and 3.10 plus the README's component example, assembled into
one project (loads clean).

Not covered: `ddd_dictionary.schema.json` beyond the descriptions it shares with the component
and types schemas (the dictionary is another pass's subject); the `plugins`/`extensions` keys of
3.1 and 3.3 beyond their presence (section 3.11 belongs to the tool-interface pass); anything the
check identifiers of section 4 decide once a file has loaded.

### Strengths

- Every `schema`-level rule of section 3 that I probed is enforced by a model validator, with
  the identifier the spec names and a message that states the reason: storage named exactly
  once, conversion required beside `datatype`, restating beside a `typename`, enum on an
  integer only (`boolean` excluded), bits width and datatype, header spelling, id alphabet,
  a2l `format` pattern, section name pattern and power-of-two alignment, raster name and cycle
  rule, constants strict `>= 1`, the 128-character cap, non-finite derived limits.
- The loader does what the intro of section 3 and 3.1 say, in every case tried: BOM, duplicate
  keys (`json-syntax`), nesting depth, invalid UTF-8, `NaN`, non-object top level, several or no
  top-level keys, include-only kinds refused as root with the hint, case-insensitive extension,
  `[...]` character classes, dot-prefixed files, directory-as-literal (`file-not-found`),
  diamond graphs, cycles.
- The published schemas are regenerated byte-for-byte from the models, every authored field
  and every enumerated value carries documentation, and a test guards both.
- The documentation transcripts are executed by the test suite, so the pages show what the tool
  prints rather than what it printed once.

### Issues

#### Critical

None found.

#### Important

1. **The docs and the published schema say a calibration tool only reads a measurement; the spec says it can write one**
   - Where: `README.md:332-333` ("an online value that the software writes and the calibration
     tool only reads"); `docs/file_formats/variable_definition.rst:426-427` ("the calibration
     tool only observes"); `schemas/ddd_component.schema.json:1284`,
     `schemas/ddd_dictionary.schema.json:329` and `:339`; sources `src/ddd/models/objects.py:48`
     (`ObjectKind.MEASUREMENT`) and `:483` (`Measurement`). Spec: `SPEC.md:149` ("a calibration
     tool can both read and write it as well") and `SPEC.md:323-324` ("A measurement needs
     [`volatile`] when an interrupt, a second core, a peripheral or a calibration tool writes the
     variable").
   - What: three published texts state the opposite of the concept table, and the opposite of
     the reason the spec gives for `volatile` on a measurement.
   - Why it matters: a reader deciding `volatile` for a measurement a tool is meant to poke is
     told, by the hover text and the README, that the case does not exist.
   - Fix: reword the two docstrings (and thereby the schemas) and the two prose passages to the
     spec's wording: the software writes it; a calibration tool measures it and may write it.

2. **Schema description of `identity`: "the default for every variable"**
   - Where: `src/ddd/models/conversion.py:53`; published at
     `schemas/ddd_component.schema.json:814`, `schemas/ddd_types.schema.json:205`,
     `schemas/ddd_dictionary.schema.json:235`. Spec: `SPEC.md:580-582` ("A conversion **must** be
     stated wherever storage is named by `datatype` ... although the identity would be derivable
     (`schema`)").
   - What: the hover text of the identity variant states a default that the format deliberately
     does not have; the `conversion` field's own description two lines away says the opposite.
   - Fix: "``physical == raw``; stated like any other conversion, `{}` being its shortest
     spelling."

3. **Schema description of a definition's `unit` predates the unit vocabulary**
   - Where: `src/ddd/models/objects.py:297-301` ("Free text, so DDD does not know that ``rpm``
     and ``1/min`` are the same thing; it only checks that every component declaring this object
     spells the unit the same way"); published six times in `schemas/ddd_component.schema.json`
     (lines 126, 476, 978, 1182, 1551, 1873). Spec: `SPEC.md:311` ("checked against the
     vocabulary where the project declares one") and 3.8.
   - What: "only checks ... the same way" is false once a `units` file exists (`unknown-unit`).
     The same omission, without the false "only", is in `docs/file_formats/variable_definition.rst:99-103`
     and `README.md:317`, neither of which mentions the vocabulary in the key table.
   - Fix: the docstring should say what `Member.unit` and `ScalarType.unit` already imply and
     `units.py` states: free text, checked against the vocabulary where the project declares
     one; the two key tables should point at the units page.

4. **`"dimensions": []` on a measurement is accepted as a scalar; the spec says the list is non-empty**
   - Where: `SPEC.md:391` ("`dimensions` is a non-empty list of array dimensions"); code
     `src/ddd/models/objects.py:486` (`dimensions: tuple[Dimension, ...] = ()`, no `min_length`),
     `src/ddd/models/types.py:139` (member, same); schema `Measurement.dimensions` publishes
     `"default": []` and no `minItems` (a `jsonschema` run reports the document VALID); docs
     `docs/file_formats/variable_definition.rst:483` ("a list of array dimensions that is empty
     for a scalar"). Observed: `ddd check e01_dims_empty.ddd.json` → no finding.
   - What: code, schema and page agree with each other and read the empty list as the scalar
     spelling; the spec's "non-empty" would have it refused. Only `value_block` (and, per the
     spec, nothing else) enforces `minItems: 1`.
   - Why it matters: a normative sentence and the implementation disagree about the validity of
     a file, and dictionary dumps already spell scalars as `[]`.
   - Fix: on the spec side, since the behaviour is the sensible one: "`dimensions` is a list of
     array dimensions ...; a measurement without `dimensions`, or with an empty list, is a
     scalar". Otherwise add `Field(min_length=1)` on `Measurement.dimensions` and `Member.dimensions`.

5. **The published type-name pattern refuses only the lowercase base datatypes; the loader refuses any case**
   - Where: `src/ddd/models/common.py:231-234` (`TYPE_NAME_PATTERN`, negative lookahead over
     the exact spellings) and its docstring `:235-244` ("matching without regard to case is
     what the schema dialect cannot say"); published at `schemas/ddd_component.schema.json:107`
     (and 457, 787, 959, 1163) and in `ddd_types.schema.json`. Spec: `SPEC.md:538-539` ("A
     `typename` **must not** spell a base datatype, compared without regard to case (`schema`)").
     Observed: `jsonschema` accepts `"name": "UINT16"` and `"typename": "Uint16"` against the
     published schemas; `ddd check` refuses both with `schema` (e03).
   - What: the schema is the editor-facing layer the spec's `schema` identifier is about, and
     here it validates a file the loader refuses. The docstring's premise is wrong: ECMA-262
     needs no flag for this, `[Uu][Ii][Nn][Tt]16` spells it, and current engines also accept
     `(?i:...)`.
   - Fix: publish the lookahead case-insensitively, e.g.
     `^(?![Bb][Oo][Oo][Ll][Ee][Aa][Nn]$|[UuSs][Ii][Nn][Tt](?:8|16|32|64)$|[Ff][Ll][Oo][Aa][Tt](?:32|64)$)[A-Za-z_][A-Za-z0-9_]*$`,
     and correct the docstring.

#### Minor

1. **`includes` description omits `rasters` files and the `[` wildcard**
   - Where: `src/ddd/models/project.py:24-28` → `schemas/ddd_project.schema.json:24` ("Paths to
     component, types, units, sections, constants or sub-project files ... Shell style wildcards
     (``*``, ``?``, ``**``)"); `README.md:250` and `docs/file_formats/project.rst:94-95` name
     `*`, `?`, `**` only. Spec: `SPEC.md:224-226` (rasters listed) and `:237-239` ("one of `*`,
     `?` or `[` ... `[...]` is a character class").
   - Fix: add "rasters" and the character class to the docstring and both pages.

2. **`StructType.name` description reasons from a union that no longer exists**
   - Where: `src/ddd/models/types.py:284-286` ("where a name is written, a base datatype wins
     the union") → `schemas/ddd_component.schema.json:1771`, `schemas/ddd_types.schema.json:532`.
     Spec: `SPEC.md:538-541` (two keys; the reason is that the name "wears the name of storage it
     is not").
   - Fix: use the spec's reason, as `ScalarType.name` (`types.py:325-328`) already does.

3. **`Enumerator.value` description states a uniqueness rule the tool only warns about and the spec does not have**
   - Where: `src/ddd/models/conversion.py:46` ("every enumerator of one enum needs a value of its
     own") → `schemas/ddd_component.schema.json:755`, `ddd_types.schema.json:146`,
     `ddd_dictionary.schema.json:215`. Observed: `{"P": 0, "Q": 0}` loads with
     `warning[enum-duplicate-value]` (e11); `SPEC.md:560-575` (3.4) states no such rule
     (`enum-duplicate-value` appears only in section 4, `SPEC.md:1181`).
   - Fix: "The raw value; two enumerators sharing one is reported as a warning
     (`enum-duplicate-value`)".

4. **`scope: output` described as "writes the variable"**
   - Where: `src/ddd/models/component.py:23` → `schemas/ddd_component.schema.json:1754`,
     `ddd_dictionary.schema.json:1203`. Spec: `SPEC.md:164` ("the component owns the object") and
     `:170-172` (for calibration objects `output` means it provides the data).
   - Fix: "The component owns the object and, for a measurement, writes it; exactly one
     component may produce a name."

5. **Whole-valued float initialisers are refused as "fractional"**
   - Where: `src/ddd/analysis.py:1586-1593`; observed `"init": 1.0` on `uint8` →
     `init-invalid: init value 1.0 is written as a fractional number` (e10).
     `docs/file_formats/variable_definition.rst:300-301` also promises the rule as "a fractional
     value in an integer object". Spec `SPEC.md:398-400` asks only that the value fit the raw
     range.
   - Fix: either word the finding as what is checked ("is written as a floating point literal,
     but ... has the integer datatype") and state the rule in the spec and the page, or accept a
     float with an integral value.

6. **Stale kind counts in two docstrings**
   - Where: `src/ddd/models/common.py:19` ("Base of the hand-written file roots: project,
     component and types"); `src/ddd/build_info.py:20-21` ("none of the four top level keys").
     Spec `SPEC.md:183-188` lists seven.
   - Fix: "the seven file roots" / "none of the top level keys a description may have" (the
     spec's own wording at `SPEC.md:682`).

7. **component.rst's note on consumer-refused keys lists one of five**
   - Where: `docs/file_formats/component.rst:355-358` ("Two keys of the block sit outside that.
     ``init`` is refused on a consumer altogether, as ``consumer-storage``"). Spec 3.3.1.2
     (`SPEC.md:458-470`): `init`, `section`, `id`, `raster`, `extensions` are all refused on a
     consumer, under four identifiers.
   - Fix: name the group ("the storage and identity keys - `init`, `section`, `id`, `raster`,
     `extensions` - are refused on a consumer") or point at the variable definition page.

8. **project.rst never says what a missing literal include yields, nor in which order matches load**
   - Where: `docs/file_formats/project.rst:88-142` documents `include-empty`, the excluded
     project file and diamonds, but not `file-not-found` for a literal path
     (`SPEC.md:247-250`) nor the sorted processing order (`SPEC.md:242-245`), which 3.3.1
     (`SPEC.md:440-444`) makes load-bearing for a project that relaxes `missing-producer` and
     for the reference limits.
   - Fix: one sentence each after the `include-empty` paragraph.

9. **README table gives `extensions` the default "none"**
   - Where: `README.md:325`; spec `SPEC.md:318` and
     `docs/file_formats/variable_definition.rst:146-147` say `{}`.
   - Fix: `{}`.

### Spec gaps proven from code

- `"dimensions": []` is the scalar spelling on a measurement and on a member
  (`src/ddd/models/objects.py:486`, `src/ddd/models/types.py:139`); the spec says non-empty
  (Important 4).
- `$schema` is "accepted and ignored" only as a string or `null`; `"$schema": 5` is refused as
  `schema` (`src/ddd/models/common.py:31`; observed e02).
- `a2l.export` accepts `null`, which counts as unstated (`src/ddd/models/objects.py:106`;
  published as `anyOf [boolean, null]`).
- A definition's `section` reference is held to the section-name pattern and refused as
  `schema` before `unknown-section` gets a say (`src/ddd/models/objects.py:303`; observed e08;
  deliberately tested at `tests/test_sections.py:383`). 3.5 only describes the pattern on the
  declaration.
- `description` is accepted on scalar and struct entries and on members
  (`src/ddd/models/types.py:121`, `:289`, `:331`); 3.7 (`SPEC.md:745-762`) states it only for
  external types.
- `header` refuses whitespace, quotes of its own, an unclosed angle form and angle brackets
  inside a quoted name (`src/ddd/models/types.py:361-390`; observed e29); 3.7 (`SPEC.md:760-762`)
  states only the two forms.
- A member's `dimensions` may name a declared constant and is reported as `unknown-constant`
  at `members[i].dimensions[j]` (`src/ddd/models/types.py:139` uses `Dimension`;
  `src/ddd/analysis.py:1010-1015`); 3.9 (`SPEC.md:875-877`) names only a definition's
  `dimensions` and an axis `size`; `docs/file_formats/constants.rst:52-53` documents it.
- The literals `NaN`, `Infinity`, `-Infinity` are refused as `json-syntax`
  (`src/ddd/loading.py:79-88`; observed e43), and a numeric literal that overflows to infinity,
  `1e400`, is refused as `schema` "finite" (`src/ddd/models/common.py` `Real`; observed e36).
  The intro of section 3 mentions neither; `docs/file_formats/index.rst:105-110` documents the
  first.
- A top-level JSON value that is not an object is `file-kind` (`src/ddd/loading.py:577-583`;
  observed e19).
- A units entry `""` is refused as `schema` (`src/ddd/models/units.py:29`; observed e07); 3.8
  says only that the empty unit is always allowed on an object.
- `init: true`/`false` is accepted for an integer datatype (counted as 1/0, no finding), and
  `1`/`0` for a `boolean` (`src/ddd/analysis.py:1576-1584`; observed e10).
- `"unit": ""` beside a `typename` is refused as restating, because presence rather than value
  decides (`src/ddd/models/objects.py:152-171` uses `model_fields_set`; observed e14).
- `file-extension` is reported after the file has been read and loading continues
  (`src/ddd/loading.py:484`, `:1014`); 3 says only that the file "must" be so named.
- 3.3.1.3's "left out only when every stated answer is `false`" (`SPEC.md:505-507`) has an
  exception stated only in 5.2 (`SPEC.md:1478`) and on
  `docs/file_formats/variable_definition.rst:402`: an axis a curve or map refers to is exported
  regardless.

### Test gaps

- 3.1, character class: no test includes a pattern with `[...]` (`grep '\[ab\]\|\[cs\]' tests/`
  finds nothing).
- 3.1, dot-prefixed files matched like any other: no test (`tests/test_structures.py:1048`
  is unrelated).
- 3.1, sorted processing order of wildcard matches: `tests/test_loading.py:52-63` asserts
  `["A", "B"]`, which is also the file system's natural order; nothing shows the sort winning
  over enumeration order.
- 3.1, file identity through symbolic links: no loader test (`symlink` appears only in
  `tests/test_lsp.py`).
- 3.3, the 128-character cap: exercised only through the rename path
  (`tests/test_lsp.py:1854-1856`); no model or loader test for a 129-character name.
- 3 intro, BOM tolerance in the loader: only indirectly, via `ddd id --assign` keeping the BOM
  (`tests/test_cli.py:1572-1582`); no `load_workspace` test on a BOM'd file.
- 3.3, `"dimensions": []` on a measurement: no test pins the intended reading (Important 4).
- 3.3.2, the published type-name pattern against a mixed-case name: no test validates
  `UINT16` against the published schema (`test_documentation.py:1201` validates the shipped
  examples only), which is how Important 5 went unnoticed.

### Assessment

The file formats conform closely: every refusal section 3 attaches to `schema` is enforced by
the models with the identifier and severity the spec names, the loader's reading rules match
the intro and 3.1 in every case tried, the published schemas are current and the spec's own
example files load. What has drifted is prose rather than behaviour: four descriptions in the
published schemas predate the unit vocabulary, the required conversion, the two-key storage
rule and the concept table's reading of a measurement, and one of them is echoed by the README
and the variable definition page. The one genuine behavioural disagreement, the empty
`dimensions` list, is a spec sentence the code, the schema and the page all read the other way.

## Pass 3: the consistency checks and the comparison (SPEC.md section 4)

### Scope covered

Read in full: `SPEC.md` sections 1, 2, 3.3.1 and 4 (lines 41-175, 445-526, 1023-1320), plus the paragraphs of 3.5, 3.11 and 7 that section 4 leans on (lines 626-660, 996-1006, 1595-1601, 1710-1718); `src/ddd/analysis.py` (all 2261 lines), `src/ddd/diagnostics.py`, `src/ddd/compare.py`, `src/ddd/identity.py`, the check-reporting parts of `src/ddd/loading.py` (lines 402-449, 550-640, 700-720, 860-1010, 1040-1100), `src/ddd/plugins.py` 223-371, `src/ddd/lsp/diagnostics.py` 1-140, `src/ddd/cli.py` 100-135, 520-700, 1115-1275, `src/ddd/ir.py` 560-720, `src/ddd/models/reserved.py`, the datatype table in `models/common.py`, the condition validator in `models/component.py`, `conversion_identity` and `resolve_export`; `docs/consistency_checks.rst` and `docs/comparing_deliveries.rst` in full; `README.md` 474-597.

Run: `ddd checks` (text and json) and 27 throwaway projects under the scratchpad (`exp/a` .. `exp/st`), exercising every question (a)-(r) plus ownership, `definition-mismatch` fan-out, `incomplete-project`, load-time blocking, the severity policy, `--standalone`, the dictionary format rule, the lost-identity note and the renames file. Every one of the 67 identifiers of section 4 was checked one by one against the registry and its firing code; 41 of them were additionally observed firing. Tests were searched (`tests/`) for the requirements listed under "Test gaps"; `tests/test_compare.py`, `tests/test_analysis.py` and `tests/test_comparison_tables.py` pass (134 tests). Transcript output inside the docs was not re-verified (covered by `tests/test_transcripts.py`).

Not covered: plugin-provided checks beyond `missing-plugin`/`plugin-invalid`/`unknown-extension`, the language server's range mapping, and the generated artefacts themselves except where a relaxed check let a dangling reference through.

### Strengths

- The registry (`src/ddd/diagnostics.py:89-249`) matches section 4 exactly: all 67 identifiers, every default severity, the seven fixed checks (`overridable=False`), and exactly the ten whole-project checks flagged `needs_every_component`, from which `STANDALONE_POLICY` (251-270), `--standalone` (`cli.py:1160-1163`) and the language server (`lsp/diagnostics.py:57-60`) are all derived; observed `--standalone` silencing the ten and a later `-W` overriding it.
- The ownership rules are implemented word for word: `multiple-producers` on every producer after the first with a note at the first (`analysis.py:1748-1757`), `missing-producer` once per consumer (1758-1765), `unused-output` once on the producer and never on a `local` (1860-1869), a `local` clash reported as `local-conflict` alone (1737-1747, the `elif` at 1748); all observed.
- Reference declaration and notes: the producer, else the first loaded (`analysis.py:493-494, 2029`), every deviating declaration reported once with a "reference declaration" note (2132-2168); limits resolved and compared against the first *stating* declaration (2069-2099). Observed with two deviating consumers and with a missing producer.
- The comparison is careful where it matters: pairing by identity then by name with the two-ids-differ refusal (`compare.py:211-251`), `reused-name` reported before the removal it explains via the `sequence` tie-break (`diagnostics.py:334-351`, `compare.py:316-334`), `narrowed-limits` held back under an interface change (553-561), references compared by identity (454-490), the format-3 fallback to value-only shapes (113-140), and the baseline's warnings kept out of the report (`cli.py:1190-1214`). The verdict and exit code behave as documented in every configuration tried.
- The severity policy is exactly the spec's: last override wins, `--strict` applied after overrides, fixed checks and unknown names/severities as usage errors with exit 2, provisional plugin overrides verified after loading (`diagnostics.py:399-453`, `cli.py:598`).

### Issues

#### Critical

1. **`incomplete-project` stays silent for most silenced drops**
   - Where: `SPEC.md:1197-1206`; `src/ddd/analysis.py:1369-1374` (a declaration of a poisoned structure returns `None` without `_refuse`), `1380-1383` (poisoned scalar type, same), `1769-1790` (`_unresolved` drops every object referring to a dropped one, with no finding), against `1266-1294` (`_refuse`, the only path that reports `incomplete-project`, used at 1307, 1345, 1359, 1423).
   - What: the spec says the check fires whenever "a declaration was dropped and the finding that explains why is set to `ignore`", naming "a variable of an unknown type" as the example. Observed on `exp/inc` with `-W type-cycle=ignore -W unknown-type=ignore -W unknown-constant=ignore`: `Loop` (cyclic structure), `Bad` (structure whose member names an unknown type), `Sized` (structure member dimensioned by an undeclared constant) and `Gain` (curve over the dropped axis `Ax`) all vanish from `ddd list` with no finding at all; only `Ax` (declaration-level `unknown-constant`) earns `incomplete-project`. Output: `1 info`, listing shows `Ok` alone.
   - Why it matters: this is exactly the hazard the spec and the code's own `_refuse` docstring describe: a dictionary, a dump and every backend one or four objects short, and an exit code of 0.
   - Fix: have `_resolve_type` route the poisoned-type drops through `_refuse` (record, per poisoned type, whether its cause was reported, and report `incomplete-project` at the declaration when it was not), and have `_unresolved` report `incomplete-project` for each dependent whose root cause was silenced. Add tests for the three type-level causes and for a curve over a silenced axis.

#### Important

1. **An unresolvable reference keeps its object, and relaxing `unknown-reference` generates wrong artefacts**
   - Where: `SPEC.md:1150-1153` and `1197-1206`; `src/ddd/analysis.py:1806-1825` (a curve or map whose axis lookup failed resolves to shape `((), ())`), `1832-1858` (`_lookup` reports and returns `None` without dropping), `1774-1778` (the docstring explaining why a dangling name must not reach the a2l).
   - What: on `exp/f`, `ddd check` reports `unknown-reference` twice (correct); with `-W unknown-reference=ignore`, `ddd list` still lists `Gain` (curve, shape `-`) and `Ax` (`input: NoInput`), `ddd dump` records `Gain` with `"shape": []` and `"references": {"axis": "NoAxis"}`, and `ddd generate all` writes `const uint16_t Gain;` (a curve as a scalar) and an `AXIS_PTS Ax ... NoInput` record naming a measurement that does not exist. No `incomplete-project` either, because nothing was dropped.
   - Why it matters: the spec's rule for a dropped referent ("the referring object is dropped with it") rests on exactly the argument that applies here (no shape, dangling a2l name), and the check is relaxable by design.
   - Fix: treat a failed `_lookup` like an unresolved shape: drop the referring object through `_refuse("unknown-reference"/"reference-kind", ...)` so that a silenced cause yields `incomplete-project`; state in section 4 that a curve, map or axis whose reference does not resolve is dropped as unresolvable.

2. **An enum reordering is reported twice, once with an empty message**
   - Where: `SPEC.md:1050-1052` ("reported once per declaration that deviates") and `1146-1148`; `src/ddd/analysis.py:90-106` (`_conversion_value` returns the full `conversion_identity`, enumerators included) with `2136-2145`, and `1629-1638` (`enum-conflict`).
   - What: `exp/l` (mapping form, `{"OFF":0,"ON":1}` vs `{"ON":1,"OFF":0}`) yields `error[definition-mismatch]: ... (conversion: enum(Mode_t) != enum(Mode_t))` and `error[enum-conflict]: enum 'Mode_t' is defined with different enumerators` at the same declaration. The first message prints identical text on both sides of `!=`.
   - Why it matters: one deviation, two errors, and the one that sorts first says nothing a reader can act on.
   - Fix: in `_conversion_value` return `("enum", conversion.name)` for an `EnumConversion` (the enumerators belong to `enum-conflict`, which already compares them by `conversion_identity`), or else make `describe` spell the enumerators out. Add a test for the reorder case at the analysis level (only the value-change case is tested, `tests/test_analysis.py:330-339`).

3. **A renamed structured object is N `renamed-object` findings, the spec says one**
   - Where: `SPEC.md:1308-1310` ("Renaming the instance therefore keeps every member paired and is one `renamed-object`"); `src/ddd/ir.py:672-683` (`comparable` holds objects and leaves, never the instance), `src/ddd/compare.py:305-314`.
   - What: `exp/c` renames `Pack` (two members) to `Bundle`: two findings, `'Pack.hi' is now called 'Bundle.hi'` and `'Pack.lo' is now called 'Bundle.lo'`, and two entries in `--renames` (`pppppppppppp.hi`, `pppppppppppp.lo`); nothing names the instance. `docs/comparing_deliveries.rst:156-159` describes the per-member entries, so the docs already follow the code.
   - Fix: the per-member listing is what a migration tool needs, so the spec should move: "keeps every member paired, each reported as a `renamed-object` under its path". If one finding per instance is wanted instead, `compare` needs the instances in `comparable`.

4. **`address-missing`: the empty-map exemption and the one-per-run shape are unstated**
   - Where: `SPEC.md:1186-1194`; `docs/consistency_checks.rst:545-551`; `src/ddd/cli.py:637-642` (an empty map returns early), `651-657` and `660-668` (one finding naming up to five missing symbols and a count); `CHANGELOG.md:124`.
   - What: observed on `exp/a`: no map, no finding; `{}`, no finding; `{"Alpha":..., "Stale":...}`, one warning `the address map has no entry for 'Beta'; it reaches the a2l at address 0` with the note `the map also carries 'Stale', which the a2l does not`; `--strict` turns it into an error and writes nothing. The spec says the check "fires only when a map is supplied" and is phrased per object ("an object the A2L carries has no entry"). The changelog documents the empty-map rule; the spec and the checks reference do not.
   - Fix: add to `SPEC.md` and `docs/consistency_checks.rst` that an empty map is the pre-link run and raises nothing (the CMake two-run flow depends on it, `docs/build_integration.rst:409-410`), and that one finding per run names the missing objects.

5. **A plugin hook that raises discards every finding of the run on the command line**
   - Where: `SPEC.md:1002-1005` (usage error on the command line, `plugin-invalid` in the language server) and `1102-1103` (`plugin-invalid` in section 4 lists neither); `src/ddd/plugins.py:366-371`, `src/ddd/cli.py:112-114` (the `ValueError` handler prints one line and returns 2, `_report` never runs), `src/ddd/lsp/diagnostics.py:75-82`; `docs/consistency_checks.rst:828-832` (exit 2: "Nothing was checked").
   - What: `exp/n` (a plugin whose `check` raises): `ddd check` prints only `ddd: plugin 'bad' failed in its check hook: boom`, exit 2; the language server's `_run` returns `plugin-invalid` plus the run's own findings (`missing-id` was still there). The behaviour matches 3.11 and 7.2, but the project's findings, collected before the hook ran, are thrown away, and the exit-code table then says nothing was checked.
   - Fix: either print the bag before the usage error in `_command_check`/`_command_compare`, or report the failure into the bag as `plugin-invalid` the way the server does; cross-reference the hook case from the `plugin-invalid` entry in section 4 and in the checks table (`docs/consistency_checks.rst:367-371`).

6. **Docs: "the two other load time checks are relaxable" is false, and the second wave is withheld by more than two checks**
   - Where: `docs/consistency_checks.rst:204-208` and `227-233`; `src/ddd/cli.py:1166-1167` (any load error stops the analysis); `src/ddd/loading.py:627-634` (`duplicate-component`), `710-718` (`duplicate-unit/-section/-constant/-raster`, `duplicate-type`), `944-949` (`unknown-extension`), `984-992` (`include-empty`), `588-593` (`file-extension`).
   - What: observed on `exp/lt`: two components named `Same` and a consumer nobody produces give `duplicate-component` alone; with `-W duplicate-component=warning` the `missing-producer` appears. The loader reports nine relaxable checks, not two, and an error from any of them holds the interface checks back. Also observed on `exp/own`: a consumer's `extensions` block for an unloaded plugin (`unknown-extension`) blocked the whole run, so `consumer-extension` can only ever fire once the plugin loads.
   - Fix: rewrite the two passages to say that every check the loader reports (the seven fixed, `file-extension`, `include-empty`, the six `duplicate-*` and `unknown-extension`) withholds the interface checks while it is an error, and that relaxing whichever fired lets the second wave through.

7. **Docs: the checks reference never mentions `--standalone` or the ten whole-project checks, and recommends the hand-listed policy**
   - Where: `SPEC.md:1039-1043`; `docs/consistency_checks.rst:173-188` (the note recommends `-W missing-producer=ignore -W unused-output=ignore`); `src/ddd/diagnostics.py:256-270` (the docstring records that listing by hand "is how this went wrong twice already"); `--standalone` appears in `README.md:706, 722` and `docs/command_line_interface.rst:92` but nowhere in the checks reference.
   - What: a component checked alone with the documented two overrides still reports `unknown-type`, `unknown-unit`, `unknown-section`, `unknown-constant`, `unknown-raster`, `unknown-extension`, `unknown-reference` and `incomplete-project` for everything declared in files it was not handed. The page that explains the severity policy is the one place a reader would look for the rule.
   - Fix: replace the note with `ddd check <component> --standalone`, list the ten checks it holds back (or point at the registry flag, see the next item), and keep the `-W` form only as the way to re-enable one of them.

8. **`ddd checks` does not print which checks need every component**
   - Where: `SPEC.md:1031` ("The authoritative list is the one the tool prints itself") and `1039-1043`; `src/ddd/cli.py:1115-1133` (json carries `check`, `default_severity`, `description`, `overridable` only; the text form marks `(fixed)` only); `docs/consistency_checks.rst:891-910`.
   - What: the ten checks exist only as prose in the spec and as a flag in `diagnostics.py`; a build or editor integration that wants the set (the flag `STANDALONE_POLICY` is derived from) cannot read it from the tool.
   - Fix: add `needs_every_component` to the json output and a marker such as `(project)` to the text form, and mention it under "the registry itself is machine readable".

9. **Spec gap: `typename` compares as what it resolves to, in both checks**
   - Where: `SPEC.md:457-460` ("the storage (`datatype` or `typename`) ... Every declaration must state the same thing") and `1060-1062`; `src/ddd/analysis.py:1386-1396` (a scalar type is folded into the definition before comparison), `110-116`; `src/ddd/compare.py:86` (the dictionary carries the resolved datatype only).
   - What: `exp/d`: a producer stating `typename: Speed_t` and a consumer stating `datatype: uint16, unit: rpm, factor 0.5` check clean; a dump of the typed producer compared with the plain one reports no `changed-interface`. Both are sensible, but the spec reads as if the spelling had to agree.
   - Fix: state in 3.3.1.1 and under `definition-mismatch` that a `typename` is compared as the datatype, unit, conversion and limits it fixes, and in 4.1 that a dictionary records no type names for values, so adopting a scalar type is not a change of interface.

10. **Spec gap: a reference to another component's `local` object is accepted silently**
    - Where: `SPEC.md:165-170` (`local`: "another component must not use it (`local-conflict`)"); `src/ddd/analysis.py:1841` (`_lookup` reads `_effective` without regard to scope), `1737-1747` (`local-conflict` looks at declarations only).
    - What: `exp/r`, a curve in component `A` over an axis declared `local` by `B`: `ok: 2 variables in 2 components are consistent`. The generated A2L then binds `A`'s curve to `B`'s private axis.
    - Fix: decide in the spec whether a reference is a use; if it is, report `local-conflict` at the referring definition (with a "declared local here" note); if it is not, say so under 2.1.

11. **Spec gap: the alignment need per datatype**
    - Where: `SPEC.md:645-650` (only the structure rule is given); `src/ddd/analysis.py:818-859` (a base datatype needs its size; an array its element's; a structure the strictest member, nested structures walked; a structure reaching an external type gets no estimate; a cyclic type none); `src/ddd/models/common.py:165-167`.
    - What: observed on `exp/e`: `boolean` and `uint8` need 1, `uint16` 2, `float32` 4, `float64` and `uint64` 8, `uint8[4]` 1, `Mix_t{uint8,uint32}` 4, `Wide_t{float64}` 8.
    - Fix: one sentence in 3.5: a base datatype needs an alignment of its size, an array that of its element.

#### Minor

1. **The registry undersells `reserved-identifier`, and the README omits half of it** - `src/ddd/diagnostics.py:152` says "a name collides with a c keyword"; `README.md:510` says "a c keyword or with something `<stdint.h>` declares"; the check also refuses the `<stdbool.h>` names and the two underscore families (`src/ddd/models/reserved.py:23-60`, observed on `exp/h`: `a__b`, `_Y`, `SIZE_MAX`, `bool`; `_x` and `display_identifier: "int"` accepted). The docs table (`docs/consistency_checks.rst:401-406`) is accurate; the spec (`SPEC.md:1154-1160`) does not say which names are policed (project, component, object, type, member, enum, enumerator, constant; not `display_identifier`). Align the two short descriptions with the docs.
2. **README wording** - `README.md:491` `duplicate-type` "the same structured datatype name": scalar and external types too (`loading.py:710-718`); `README.md:569` `changed-storage` "decides whether the object still lives in read only memory": volatility decides tunability, the section decides the memory (`SPEC.md:1275-1279`, `docs/comparing_deliveries.rst:258-261`).
3. **`a2l-unrepresentable` fires for what reaches the a2l, not only for what is exported** - `SPEC.md:1184-1185` and `docs/consistency_checks.rst:542` say "an object the A2L exports"; `src/ddd/analysis.py:560-580, 2041-2051` use the closure (observed on `exp/closure`: `Big`, `export: false`, reported because an exported axis names it as `input`). The code is right (the file carries it); reword spec and docs to "an object the a2l carries".
4. **The lost-identity note is looser than "every compared field"** - `SPEC.md:1296-1298`; `src/ddd/compare.py:402-409` compares interface, storage and references only. Observed on `exp/note`: a removal and an addition differing in limits (0..10 vs 0..20), owner, condition and a2l format still get `'New' was added with an identical interface`. The message is accurate for the interface; the spec's wording should say "identical in interface, storage and references".
5. **A duplicate declaration whose first copy was dropped is not a duplicate** - `src/ddd/analysis.py:1466-1500` (`seen` records resolved declarations only). Observed on `exp/dd`: `X` as an unknown `typename` then `X` as `uint16` gives `unknown-type` alone; with `-W unknown-type=ignore`, `incomplete-project` says `'X' is not in the data dictionary` while `ddd list` lists `X`. Record every declared name in `seen` before resolving.
6. **The generic note rule does not cover limits** - `SPEC.md:1050-1054` says the note points at "the producer's declaration or the first loaded one"; for limits it points at the first *stating* declaration (`analysis.py:2069-2099`, observed on `exp/j`: producer silent, `A` [0,10] is the reference, `B` [0,20] reported with a note at `A`), which 3.3.1.1 says but section 4 should echo.
7. **`--renames` is not written when a side cannot be read** - `SPEC.md:1236-1238` ("written whether or not the comparison found errors"); `src/ddd/cli.py:585-587` returns before line 603. Observed: `exp/c/never.json` not created. Say so, or write `[]`.
8. **`duplicate-declaration` drops the second copy before the consumer checks** - `src/ddd/analysis.py:1489-1498` `continue`s before `_check_declaration`, so a duplicate `input` stating `init`, `section`, `id` or `raster` gets no `consumer-*` finding, while `_check_sections`/`_check_rasters` (730-816) still report `unknown-section` on it (observed on `exp/own`, `Trip` in `C`). Harmless, but the split is arbitrary; the docs' "The second declaration is ignored for the rest of the run" (`docs/consistency_checks.rst:419-420`) is only mostly true.

### Answers to the questions from pass 1

- **(a) `address-missing`.** Absent map: no finding (`cli.py:728-733`, the coverage check is not called). Empty map `{}`: no finding, by the early return at `cli.py:637-642`. Map with holes: one warning per run naming the missing objects (five, then a count) with a note listing the map entries nothing wants; `--strict` makes it an error and nothing is written. Observed on `exp/a` (`Alpha`/`Beta`, map naming `Alpha` and `Stale`). The spec (1188-1194) should move: state the empty-map exemption and the one-finding shape (Important 4).
- **(b) The verdict.** `ddd compare` shares one bag between the candidate's own analysis (when it is a description), the baseline's carried errors and the comparison; the verdict is `cannot` iff `bag.has_errors` (`cli.py:612`) and the exit code is 1 iff the same (617). So the candidate's own error findings are reported and decide the verdict (observed `exp/b` B3: a `missing-producer` alone gives `cannot replace`, exit 1), and the baseline's carried errors decide it too (B1: `in the baseline: 'X' is written by ...`, `cannot replace`, exit 1). When the baseline carries an error and the candidate is a description, the candidate is not analysed and no verdict line is printed (B2, exit 1, per `cli.py:1181-1182`). When either side cannot be read, no verdict, exit 1 (585-587). The baseline's warnings and infos are dropped (B5), and `--format json` prints no verdict (B6). `ddd check --baseline` returns the same code without a verdict line (B4). The spec (1223-1231) does not say that the candidate's own errors count; the docs do (`comparing_deliveries.rst:128-132, 626-632`). Spec should state it.
- **(c) `--renames`.** `json.dumps(renames(paired), indent=2) + "\n"` (`cli.py:606-608`): a JSON list of objects with the keys `id`, `from`, `to` in that order, sorted by `to` (`compare.py:254-270`), written with `\n` line endings, `[]\n` for an empty comparison, written on a failing comparison, not written when a side cannot be read. A member is keyed `"<instance id><path below the instance>"`, e.g. `pppppppppppp.hi`, one entry per member. Observed on `exp/c`. The spec (1232-1238) names no keys; the docs (`comparing_deliveries.rst:156-168`) do. Minor 7 for the unreadable case.
- **(d) `typename` and `datatype`.** Both compare as resolved: `_resolve_type` folds a scalar type's datatype, unit, conversion and limits into the definition (`analysis.py:1386-1396`) before `_INTERFACE_FIELDS` (110-116) reads `datatype`; the dictionary records the resolved datatype only, so `changed-interface` (`compare.py:86`) compares that. Observed clean on `exp/d`, `exp/d2`, `exp/d3`. A structured object compares by its `typename` (110-116, `d.datatype is None`). Spec should state it (Important 9).
- **(e) `section-alignment`.** `datatype.size` for a base datatype: `boolean` 1, 8/16/32/64-bit integers 1/2/4/8, `float32` 4, `float64` 8; an array needs its element's; a structure the strictest of its members through nested structures; a structure reaching an external member gets no estimate; a cyclic type none (`analysis.py:818-875`). Observed on `exp/e`. Spec should state the per-datatype rule (Important 11).
- **(f) Missing axis, missing input.** Both are `unknown-reference`, located at `definition.axis`/`definition.input`. The referring object is kept: a curve resolves to shape `()` (`analysis.py:1806-1810`), the axis keeps `references.input` pointing at nothing. With the check relaxed, `ddd dump` carries `Gain` with `"shape": []` and `"references": {"axis": "NoAxis"}`, `ddd generate` writes `const uint16_t Gain;` and an `AXIS_PTS` record naming `NoInput`; no `incomplete-project`. Only a reference to a *dropped* declaration drops the referrer (1769-1790). Code should move (Important 1) and the spec should state the rule.
- **(g) Project-level block for an unloaded plugin.** `unknown-extension`, located at `project.extensions.<name>` (`loading.py:907-949`), observed on `exp/g` with no plugin and on `exp/g2` beside a loaded one. It is reported by the loader, so as an error it withholds the interface checks; relaxed, the block reaches the dictionary verbatim (`plugins.py:223-256`; observed `"extensions": {"nope": {"x": 1}}` in the dump). Spec, code and docs agree.
- **(h) `reserved-identifier`.** Project names (`analysis.py:1078-1091`), component names (1453-1458), object names (1514-1519), type names (887-892), structure members (1042-1059), enum names and enumerators (1645-1660), constants (1061-1076). Not `display_identifier` (observed `"int"` accepted), not a leading underscore followed by a lowercase letter (`_x` accepted, per spec). Docs list the names (`consistency_checks.rst:401-406`); the spec and the registry description do not (Minor 1).
- **(i) Baseline as a project naming plugins.** `_read_baseline` resolves it through `load_workspace`/`analyze` in its own bag (`cli.py:1190-1214`, 1179-1183), so its plugins load, its blocks validate and its check hooks run for its own analysis. The comparison hooks run with the *candidate's* plugins, or `--plugin` for a dumped candidate (`cli.py:589-598`), and `missing-plugin` is reported once per side for every recorded plugin not among those (`plugins.py:314-323`). Observed: `examples/layout/project.ddd.json` against its own dump gives two `missing-plugin` warnings (baseline and candidate sides); `--plugin examples/plugins/ddd_layout.py` gives none. Consistent with 1288-1292; the spec could say whose plugins "this run" means.
- **(j) `definition-mismatch` on limits with a silent producer.** The reference is the first declaration in load order that states limits (`analysis.py:2069-2082`); every other stating declaration is compared against it and the note points at that declaration (2084-2099). Observed on `exp/j`: `B` reported, note at `A`. Consistent with 3.3.1.1; section 4's generic note sentence should mention it (Minor 6).
- **(k) `init` on a structured declaration.** `type-kind`, at `definition`, with a "declared here" note at the type (`analysis.py:1398-1430`), and the declaration is dropped through `_refuse`. Observed on `exp/k`. Matches `SPEC.md:788-790`; section 4's `type-kind` entry ("used where its shape does not fit") could cross-reference it.
- **(l) `enum-conflict` and the mapping form.** Order counts: `conversion_identity` keeps the ordered (name, value) tuples (`models/conversion.py:204-209`) and the mapping form preserves the document's order. Observed on `exp/l`: `ON,OFF` vs `OFF,ON` conflicts, with the note `first defined as: OFF=0, ON=1`. Matches the spec; but the same reorder is also a `definition-mismatch` with an empty message (Important 2).
- **(m) Omitted `unit`.** An omitted unit is the empty unit, and `unit` is not optional in `_INTERFACE_FIELDS` (`analysis.py:117`), so it is `definition-mismatch (unit: '' != 'rpm')`; observed on `exp/m`. Consistent with 3.3.1.1 (only `limits` may be left out); the spec could say in one clause that an omitted unit is `''` and does compare.
- **(n) A hook that raises.** Command line: `PluginError` (`plugins.py:366-371`) is a `ValueError`, caught at `cli.py:112-114`: one line, exit 2, the run's findings discarded. Language server: `plugin-invalid` at the project file, findings kept (`lsp/diagnostics.py:75-82`). Both as 3.11 (1002-1005) and 7.2 (1714-1716) specify; section 4's `plugin-invalid` entry does not mention the server case, and the discarded findings are Important 5.
- **(o) `reused-name` placement.** Reported after the paired objects and before the removals and additions (`compare.py:316-346`); all comparison findings share one location, so within a severity the tie-break is `Diagnostic.sequence`, the order of reporting (`diagnostics.py:334-351`). Observed on `exp/o`: `reused-name 'A'` (with the rename note), `reused-name 'B'`, then `removed-object 'B'`; `renamed-object` and `added-object` follow by severity. The spec (1252-1253) is met; it states no tie-break rule (spec gap below).
- **(p) `raster` on an `input` calibration object.** Both: `consumer-raster` and `raster-kind`, at the same `definition.raster` (`analysis.py:1521-1550`). Observed on `exp/p`. Neither spec entry (1074-1079, 1125-1128) excludes the other; a spec sentence would settle it.
- **(q) `duplicate-type` within one file.** `schema` (`type 'Foo_t' is already declared in this file`), from the types model, not `duplicate-type` (which is the loader's cross-file registry, `loading.py:710-718`). Observed on `exp/q`. Matches the spec's wording ("two files", 1091) and the docs' ("two different files"); note the consequence that the in-file case has a fixed severity while the cross-file case is relaxable.
- **(r) A curve over another component's `local` axis.** Accepted with no finding (`analysis.py:1841`); observed `ok: 2 variables in 2 components are consistent` on `exp/r`. Spec gap (Important 10).

### Spec gaps proven from code

- A `typename` compares as the datatype, unit, conversion and limits it resolves to (`analysis.py:1386-1396`), and `changed-interface` compares the resolved datatype (`compare.py:86`).
- An empty address map raises no `address-missing`; one finding per run names up to five missing objects (`cli.py:637-668`).
- The candidate's own error findings and the baseline's carried errors both decide the verdict and the exit code; an unreadable side or a baseline error with a description candidate prints no verdict (`cli.py:577-617`, `1181-1182`).
- The `--renames` file's keys are `id`, `from`, `to`; nothing is written when a side cannot be read (`cli.py:585-608`).
- A dictionary of an older format is read with defaults: no `dimensions` (format 3) makes the shape comparison value-only (`compare.py:113-140`), no `plugins` (format 6) means `missing-plugin` cannot fire for it, no `rasters`/`constants` (format 4). Observed a format-3 baseline against a project spelling a size by a constant: clean.
- A curve, map or axis whose reference names no object is kept with an empty shape and a dangling reference (`analysis.py:1806-1825`).
- The comparison's plugins are the candidate description's, or `--plugin` for a dumped candidate; a plugin loaded only for the baseline's analysis still yields `missing-plugin` (`cli.py:589-602`, `plugins.py:314-323`).
- Findings at one location are ordered by the sequence in which they were reported (`diagnostics.py:334-351`); comparison findings all sit at the candidate path with no pointer.
- `consumer-raster` and `raster-kind` both fire on one `input` calibration declaration stating a raster (`analysis.py:1521-1550`).
- `duplicate-type` within one file is `schema` (fixed), across files `duplicate-type` (relaxable).
- A project-level `extensions` block for an unloaded plugin is `unknown-extension`, reported by the loader, so it withholds the interface checks while it is an error, and reaches the dictionary verbatim when relaxed (`loading.py:935-949`, `plugins.py:223-256`).
- `unknown-extension`, the six `duplicate-*` checks, `file-extension` and `include-empty` are all reported at load time and, as errors, stop the analysis (`cli.py:1166-1167`).
- A reference from one component's curve, map or axis to another component's `local` object is not a `local-conflict` (`analysis.py:1841`).
- The alignment need of a base datatype is its size; an array's its element's; a structure with an external member or in a cycle has none (`analysis.py:818-875`).
- `a2l-unrepresentable` fires for every object the a2l carries, the closure over references included (`analysis.py:560-580`).
- The lost-identity note ignores limits, owner, condition and the a2l block (`compare.py:402-409`).
- A renamed instance is one `renamed-object` and one `--renames` entry per member (`ir.py:672-683`, `compare.py:254-314`).
- `missing-id` fires for `local` declarations as well as `output` (`analysis.py:1533-1542`, `models/component.py:29-30`), and for `"id": null`.
- A plugin hook that raises discards the command line run's findings (`cli.py:112-114`).
- `incomplete-project` fires only through `_refuse`, i.e. for declaration-level `unknown-type`, `unknown-constant` and `type-kind` (`analysis.py:1266-1294`).

### Test gaps

- `incomplete-project` for a declaration dropped through a poisoned type (`type-cycle`, member `unknown-type`, member `unknown-constant`) or through a dropped referent: no test (`tests/test_constants.py:305, 323` cover the declaration-level constant only); the behaviour is also missing.
- `multiple-producers` "on every producer after the first" with three producers: `tests/test_analysis.py:31-37` uses two and asserts membership only.
- `enum-conflict` on a pure reordering, and with the mapping form: `tests/test_analysis.py:330-339` changes a value; `tests/test_compare.py:110` covers only the comparison side.
- `definition-mismatch` between a `typename` declaration and an equivalent `datatype` declaration (should be clean): no test found (`tests/test_structures.py:824` is the structure case).
- `consumer-raster` and `raster-kind` both firing on one declaration: `tests/test_rasters.py:396, 407` test each alone.
- A curve, map or axis of one component referring to a `local` object of another: no test asserting either outcome.
- `duplicate-id` reported on the second in *name* order when the load order differs: `tests/test_models.py:318-350` loads the names in name order.
- The 1e-9 tolerance of `limits-out-of-range`: `tests/test_analysis.py:253-262` tests a value exactly on the range, none inside the tolerance band.
- `missing-id` firing on a `local` declaration specifically: no dedicated test found (the fixture silences the check, `tests/conftest.py:92-99`).
- What a relaxed `unknown-reference` leaves in the dictionary and the artefacts: `tests/test_calibration.py:227-282` assert the finding only.
- `--renames` when a side cannot be read: `tests/test_cli.py:1003` covers the flag's absence only.

### Assessment

The registry, the severities, the fixed set, the whole-project set and the severity policy are exactly section 4, and the ownership, reference-declaration, note and comparison rules were all observed doing what the spec says, including the subtle ones (`reused-name` ordering, the narrowing gate, identity-resolved references, the format-3 fallback, the baseline's warnings). The conformance problems are at the edges of what gets dropped: `incomplete-project` misses most of the drops it exists for, and an unresolvable reference is not a drop at all, so a relaxed run generates a curve as a scalar and an a2l with a dangling name. Beyond that the spec is silent on a handful of choices the code makes (resolved `typename` comparison, the empty map, alignment needs, references to `local` objects, per-member renames) and the checks reference page needs `--standalone` and a correct account of which load-time errors withhold the interface checks.

## Pass 4: the generated artefacts, the address information and the dictionary (SPEC.md sections 5 and 6)

### Scope covered

Read in full: `SPEC.md` sections 1, 2, 3.3-3.7, 3.10, 3.11, 4.1, 5, 6 and 7; `src/ddd/ir.py`; `src/ddd/backends/__init__.py`, `base.py`, `c/{__init__,backend,literals,model,options,types}.py`, `a2l/{__init__,backend,model,options,types}.py` and `a2l/templates/project.a2l.jinja`; `src/ddd/build_info.py`; the whole of `src/ddd/cli.py`; the five shipped templates in `examples/templates/`; `docs/generated_artefacts.rst`, `docs/templates.rst`, `docs/data_dictionary.rst`, `docs/data_contracts.rst`; `README.md` lines 598-701; `docker/compile.sh` and `docker/verify_symbols.py`; and, as far as the artefacts depend on them, the export/raster/closure/flattening/reference parts of `src/ddd/analysis.py` and the helpers in `src/ddd/models/{common,objects,conversion,component}.py`.

Generated with `PYTHONPATH=src python -m ddd generate all ... -t examples/templates` into the scratchpad: `examples/demo`, `examples/structures`, `examples/vocabulary`, `examples/pressure/work`. Compiled every one with MinGW gcc 13.1.0 twice, under `-std=c99 -Wall -Wextra -pedantic` and under the CI set of `docker/compile.sh:22` (`-std=c11 -Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow -Wcast-qual -Wstrict-prototypes`), the way `compile.sh` does it: one translation unit per generated header including it twice, every generated `.c`, linked with a `main` and run. All four projects: no warning, no error, link and run clean. Read all four A2L files line by line against the ASAP2 1.6.1 record grammar.

Beyond the examples, five throwaway projects (`scratchpad/pass4/edge1..edge5`): literal extremes and A2L record fields (uint64/int64 ends, `INT64_MIN`, negative and exponent floats, boolean `true`/`1`, a boolean with a unit, an integer and a float sharing a conversion and unit, `format`/`display_identifier`, four dimensions, a 2-D value block, a description with quotes/backslash/`*/`/control characters, a compound condition, an enum, a 9-element array); the export closure (an axis exported in its own right over an unexported input, and a fully unexported curve/axis/measurement chain); dangling references under `-W unknown-reference=ignore`; structures with an array of structures, a nested array member, an enum member, two external types with angle and quoted headers, a bits member, sections on a structured object, a component raster default over a parameter and a structured measurement; and the refusals (`true` for `uint8`, `2` for `boolean`, `5.0` for `uint8`, boolean under linear and enum, a float32 init of `1e-50`). Seven address maps (good, negative, over 32 bits, float, boolean, list, broken JSON), `--without a2l` beside `--address-map`, `--without` both, `generate a2l -t`, `--strict` with a partial map, template misspelling (project and per-component), template syntax error, a template in a subdirectory, `--dry-run` into a missing directory, a nonexistent template directory, `ddd dump --format json` stream placement, `ddd build-info` (including a bad `-W`), `ddd schema dictionary`, a rerender (mtime and bytes), generation from a different cwd with a different path spelling, and number formatting under a German locale.

Ran `tests/test_a2l.py tests/test_generation.py tests/test_backends.py tests/test_calibration.py tests/test_hardening.py --no-cov`: 197 passed.

Not covered: the CMake module beyond the `NAME` sanitising rule (another pass); parsing the A2L with a third-party ASAP2 parser (none available here, checked by hand); the GCC 12.2.0 `.rodata`/`.data` size measurements quoted in `docs/generated_artefacts.rst`.

### Strengths

- The determinism claim holds where I could probe it: LF line endings on Windows (`base.py:84-98` writes bytes, `.gitattributes` pins the templates), no trailing whitespace, no timestamp, byte-identical output from another cwd and another spelling of the project path, an unchanged rerender leaves the mtime alone, and float formatting is `repr`-based so a `de_DE` locale changes nothing.
- The C is right where it is easy to get wrong: `(-9223372036854775807LL - 1)` for `INT64_MIN`, `18446744073709551615ULL`, `1e-05`/`1e+20` floats, `1`/`0` booleans, bitfield widths after the declarator, `const volatile` composed rather than chosen, the section attribute between declarator and initialiser, angle and quoted external headers, nested structures in dependency order.
- The A2L is well formed on every file I read: balanced `/begin`/`/end`, positional fields in the right order for `MEASUREMENT`, `AXIS_PTS`, `CHARACTERISTIC` and `AXIS_DESCR`, `MATRIX_DIM` reversed and padded, `COEFFS` inverted with `-0.0` normalised to `0`, 64-bit limits kept whole, strings escaped, `SYMBOL_LINK` everywhere, the closure over references, leaves at their access paths.
- The docs quote real output: the definition file, `UserInterface.h`, the `--const-inputs` excerpt and every A2L block I checked are byte-for-byte what the tool writes today.
- Template errors name the template, the line and the component, and exit 2 as the spec says.

### Issues

#### Critical

None found. The one candidate (Important 1) needs an error to be explicitly ignored before it is reachable.

#### Important

1. **Dangling references reach both artefacts once `unknown-reference` is ignored, and the A2L backend guards only one of three record kinds**
   - Where: `src/ddd/backends/a2l/model.py:359-367` (`_characteristic` drops a curve/map whose axis is missing, comment "reached under --force"), `:383-392` (`_axis_descr` writes `axis.references.get("input")` unguarded), `:394-407` (`_axis_pts` writes the missing input as the input quantity), `:410-433` (`_group` lists every exported declared name, including those whose record was just dropped); `src/ddd/backends/c/model.py:494-521` (`_view` renders whatever shape the dictionary carries; a curve whose axis is missing has shape `()`); `src/ddd/backends/c/literals.py:91-108` (comment names the missing axis); `SPEC.md:1476-1480` (the rationale: a reference to an absent object "would be an invalid file rather than a smaller one").
   - What: `ddd generate all edge3/project.ddd.json -W unknown-reference=ignore` exits 0, reports only `missing-id` infos, and writes: `const uint16_t Gain = 5U;` for a `curve` and `const uint8_t MapD = 0U;` for a `map` (both scalars; `ddd list` shows shape `-`); an A2L with `AXIS_PTS AxisD` whose input quantity is `MissingMeas`, an `AXIS_DESCR` of `CurveOk` with `COM_AXIS MissingMeas`, and a `GROUP` with `REF_CHARACTERISTIC Gain` and `MapD` although neither record exists. `--force` reaches the same output with exit 1.
   - Why it matters: an A2L with an unresolved input quantity or group reference is refused whole by calibration tools, which is exactly the argument the spec makes for the export closure; and a `curve` compiled as a scalar silently changes the storage the description promised (`SPEC.md:400-402`: `[size of the axis]`). With the check ignored nothing in the run says so.
   - Fix: treat an object with a dangling reference the way `_unresolved()` (`analysis.py:1770-1790`) already treats one referring to a dropped name, so it leaves the dictionary with the finding at the root; or, at least, in the backend fall back to `NO_INPUT_QUANTITY` in `_axis_pts`/`_axis_descr`, filter `_group` to names that produced a record, and have the C backend refuse a curve or map with an empty shape. Section 5 should then say what an ignored `unknown-reference` yields.

2. **`COMPU_METHOD` sharing key: the spec omits the display format**
   - Where: `SPEC.md:1429-1430` ("shared between objects with the same conversion and unit"); `src/ddd/backends/a2l/model.py:495` (`key = (_conversion_key(conversion, unit), _default_format(entry.datatype, conversion))`) and `:585-589`; `docs/generated_artefacts.rst:668` and `:781-784` and `README.md:673-675` (both say conversion, unit and display format).
   - What: EdgeOne, a `uint16` and a `float32` both `{"factor": 2}` in `V`: `CM_LIN_V` (`RAT_FUNC "%8.3"`, claimed by `FloatLin2`, first in name order) and `CM_LIN_V_2` (`RAT_FUNC "%8.0"`), same `COEFFS`. The object's own `a2l.format` is not part of the key; it is emitted as a per-record `FORMAT`.
   - Why it matters: a generator consuming the dictionary, or a reviewer of the A2L, reads the spec and expects one method for the pair; the docs and the README already state the code's rule.
   - Fix: spec 5.2 bullet: "shared between objects with the same conversion, unit and default display format (an integer and a float object scaled alike get one method each)"; and state the `_2` rule precisely: the suffix is added when the generated *name* collides (same unit, different factor or offset; or the same conversion used by objects of both datatype classes), the unsuffixed name going to the method first met in object name order.

3. **Export closure: an axis exported in its own right also pulls the measurement indexing it**
   - Where: `SPEC.md:1476-1480` ("an exported curve or map pulls the axes it refers to ..., and a pulled in axis pulls the measurement indexing it"); `src/ddd/backends/a2l/model.py:281-300` (`_resolve_exported` walks every `references` entry of every exported object, whether initial or pulled) and `src/ddd/analysis.py:561-580` (`_a2l_closure`, the same rule); `docs/generated_artefacts.rst:997-1003` ("starts from the objects marked for export and pulls in whatever they point at, transitively"); `tests/test_hardening.py:79-94` asserts the own-right case.
   - What: EdgeTwo: `AxIn` has `"export": false` and no curve refers to `AxOwn`, yet `AxIn` is in the file because `AxOwn` names it as `input` (`0x00000000 AxIn RL_AXIS_UWORD ...`).
   - Why it matters: the spec is narrower than the code and the test; a reader could conclude that `export: false` on an axis input is honoured when nothing pulls the axis.
   - Fix: spec: "an exported axis, whether exported in its own right or pulled in, pulls the measurement indexing it".

4. **The display-format rule of 5.2 does not describe what is emitted**
   - Where: `SPEC.md:1468-1470` ("the display format defaults to `%8.0` for integral values, that is an integer datatype under an identity or under a linear conversion whose factor and offset are whole numbers, and to `%8.3` otherwise, overridden per object by `format`"); `SPEC.md:371-372` ("`boolean` does not count as an integer datatype"); `src/ddd/backends/a2l/model.py:585-589` (`integral = datatype.is_integer or datatype is Datatype.BOOLEAN`); `project.a2l.jinja:45-53` (the format is a field of the `COMPU_METHOD` only).
   - What: (a) a `boolean` is integral in the code: `BoolUnit` (identity, unit `flag`) gets `IDENTICAL "%8.0" "flag"`, which by the letter of 3.3 plus 5.2 would be `%8.3`; (b) the default lives on the method, so an object under `NO_COMPU_METHOD` (identity, no unit: `FlagA`, `BoolOne`, `ValueI`, `U64` ...) carries no `FORMAT` at all and the tool's own default applies. `docs/generated_artefacts.rst` says "The display format of a generated compu method is ..." and is accurate.
   - Fix: spec: "`%8.0` for an integer or boolean datatype under an identity or under a linear conversion with whole `factor` and `offset`, `%8.3` otherwise; the default is stated on the `COMPU_METHOD`, so an object that has none (`NO_COMPU_METHOD`) carries no format unless `format` is stated".

5. **A JSON `true`/`false` is accepted as the `init` of an integer datatype while `5.0` is refused**
   - Where: `src/ddd/models/objects.py:25` (`InitValue = bool | int | Real | ...`); `src/ddd/backends/c/literals.py:16-38` (`int(value)`); `SPEC.md:405-408` (init "**must** fit the raw range of its datatype"); observed on `edge5`: `IntTrue` (`uint8`, `"init": true`) renders `uint8_t IntTrue = 1U;` with no finding, while `IntFloat` (`"init": 5.0`) is `init-invalid` "written as a fractional number".
   - Why it matters: a boolean written on a counter is almost always a mistake, and the loader is strict about the equally harmless `5.0`; the spec does not say which JSON types an init may have.
   - Fix: decide in 3.3 and mirror the fractional refusal: a JSON boolean is `init-invalid` on any datatype but `boolean` (numbers `0`/`1` on a boolean stay accepted, as today).

6. **The A2L file name and the output directory are not in section 5.2**
   - Where: `src/ddd/backends/a2l/options.py:29-30` (`f"{project}.a2l"`, `project` being `dictionary.name`, the component's name when a component file is the root); `src/ddd/cli.py:420-424` (`-o/--output-dir`, required on `c`, `a2l` and `all`); `SPEC.md` 5.2 says nothing, 7.1:1622-1623 only ("that name becomes the A2L project, module and file name"); `docs/generated_artefacts.rst:620`.
   - Fix: add to 5.2: "the file is `<project>.a2l`, written into the output directory (`-o`) beside the C sources; a component generated alone names it after the component".

7. **`docs/generated_artefacts.rst` names the wrong command for the container's symbol check**
   - Where: `docs/generated_artefacts.rst:394-396` ("compares the symbols of the binary against ``ddd list --format json``"); `docker/compile.sh:53` (`ddd dump "$PROJECT" --format json > "$OUTPUT/dictionary.json"`); `docker/verify_symbols.py:11-16` explains why `ddd list` would be the wrong source (a structured instance is one symbol, `list` shows its leaves). The same wording is in `README.md:852`, `docs/developer_documentation.rst:314` and `docs/build_integration.rst:508` (other passes).
   - Fix: `ddd dump --format json`.

#### Minor

1. **Stale usage message** - `src/ddd/backends/base.py:77`: "rename the component or choose a different prefix"; there is no prefix option any more (`README.md:606-608`, `docs/templates.rst:34-37`). Say "rename the component or the template".
2. **A `float32` init below the subnormal range compiles with a warning** - `edge5`: `"init": 1e-50` on a `float32` passes `init-invalid` (the range check is on magnitude, `SPEC.md:405`) and renders `float F32Tiny = 1e-50F;`, which gcc reports as `floating constant truncated to zero [-Woverflow]`; under the CI set with `-Werror` the file does not compile. Refuse (or warn on) a float32 init whose float32 rounding is zero while the value is not.
3. **A nonexistent template directory is reported as an empty one** - `src/ddd/backends/c/backend.py:93-100`: `-t nowhere` yields "no template to render in '.../nowhere': ..." (exit 2, which is right) without saying the directory does not exist.
4. **`ddd dump --format` help reads "output format"** - `src/ddd/cli.py:502` (shared `_add_policy_arguments`) and `:828-841`: on `dump` the switch selects the format of the diagnostics on stderr only; stdout is the JSON dictionary in both cases. Worth a `dump`-specific help string.
5. **README table row for `ddd_types.h` omits the external includes** - `README.md:616` lists `<stdint.h>`/`<stdbool.h>`, `#define`, `typedef enum`, `typedef struct`; `examples/templates/ddd_types.h.jinja2:12-18` also emits the headers of the external types, and `docs/generated_artefacts.rst:82-84` lists them.
6. **`ResolvedComponent.source` docstring says "Path"** - `src/ddd/ir.py:98`: the dump carries the file name only (`event_logger.ddd.json` for `subsystems/logging/event_logger.ddd.json`), which is also what keeps the banner platform independent; say "file name".
7. **Section 6 says "a JSON number"** - `SPEC.md:1511-1512`; `src/ddd/backends/a2l/options.py:64-84` refuses a non-integer JSON number (`10.0`: "address of 'U64' is not an integer"), strips surrounding whitespace from a string, and reads a `-0x` prefix (refused afterwards for its sign). Say "JSON integer".

### Answers to the questions from pass 1

- **(a)** `%8.0`. `src/ddd/backends/a2l/model.py:585-589` counts `boolean` as integral. But the default is a field of the `COMPU_METHOD` only: `BoolUnit` (identity, unit) yields `IDENTICAL "%8.0" "flag"`, while `FlagA`/`BoolOne` (identity, no unit) are `NO_COMPU_METHOD` and carry no `FORMAT` at all; a boolean under `{"factor": 0.5}` is accepted and gets `%8.3`. The spec should move (Important 4).
- **(b)** Key = (conversion kind and parameters, unit, default display format of the datatype class), `a2l/model.py:495`; the method states that default; the object's own `format` is not in the key and is written per record. `_2`/`_3` (`_unique`, `:555-569`) is applied when the generated *name* collides, and the name is built from the unit alone (`CM_LIN_<unit>`, `CM_IDENT_<unit>`) or the enum name, so two linear conversions in one unit, or one conversion used by an integer and a float object, collide; the unsuffixed name goes to the object met first in name order (`CM_LIN_PCT` is factor 0.5 in the demo because `ValueA` sorts before `ValueH`). The spec should move (Important 2).
- **(c)** `<project>.a2l` (`a2l/options.py:29-30`), into `-o/--output-dir` (required on every `generate` artefact, `cli.py:420-424`); `generate a2l` refuses `-t` ("unrecognized arguments"), `generate all --without a2l --address-map ...` is refused with "--address-map belongs to the a2l artefact, left out by --without" (`cli.py:694`). The spec should gain the sentence (Important 6).
- **(d)** Every exported axis pulls its input, exported in its own right or pulled: `a2l/model.py:281-300` walks `references` of everything in the set, and `analysis.py:561-580` computes the same closure for the checks. Observed on EdgeTwo (`AxIn` present); `tests/test_hardening.py:79-94` asserts it. The spec should move (Important 3).
- **(e)** Every declaration of the component, in any scope, in declaration order, filtered to exported names, then the leaves of every declared instance in path order (`a2l/model.py:410-433`). Demo: `GROUP Controller` lists its inputs `ValueA`, `ValueB`; `GROUP Monitoring` (structures) lists only the leaves of the instance it consumes. `docs/generated_artefacts.rst:1058` says so; `SPEC.md:1436-1437` should say "in any scope" and name the order.
- **(f)** External headers: `sorted(set(authored spellings))` (`c/model.py:377-395`), so angle forms come first (`<` sorts before every letter), then code point; observed `#include <ext_types.h>` before `#include "drv.h"`, and `tests/test_external.py:447-458` covers it. The link-graph include order is CMake's (`cmake/Ddd.cmake`, other pass). CMake `NAME` sanitising: `[^A-Za-z0-9_]` to `_` and a leading digit prefixed with `N` (`cmake/Ddd.cmake:423-426`), the same rule `guard_name` applies (`c/literals.py:113-121`). Record kinds inside `MODULE` (`project.a2l.jinja:13-149`): `MOD_COMMON`, `MOD_PAR`, `RECORD_LAYOUT` (name order), `COMPU_VTAB` (name order), `COMPU_METHOD` (name order), `MEASUREMENT` (plain objects by name, then leaves by path), `AXIS_PTS`, `CHARACTERISTIC` (objects, then leaves), `GROUP` (project order). The spec states none of this; it belongs in 5.2.
- **(g)** The base datatype: `c_type(entry) = C_TYPE[entry.datatype]` (`c/literals.py:63-64`); `uint8_t StateA = 0U;`, `uint8_t Mode;`. The `typedef enum` exists for the enumerators. `docs/generated_artefacts.rst:150-160` explains it; the spec (3.4, 5.1) does not say it and should.
- **(h)** `1`/`0` (`c/literals.py:19-24`, `SPEC.md:363-364` agrees, `tests/test_generation.py:43-64`). JSON `true` on `uint8` is accepted and renders `1U`; `2` on a `boolean` is `init-invalid`; `5.0` on an integer is `init-invalid`. The spec should decide the JSON-type rule (Important 5).
- **(i)** stdout carries the dictionary in both formats; `--format json` puts the `{"diagnostics", "summary"}` document on stderr (`cli.py:828-841`); with errors the dictionary is still printed and the exit is 1. Matches `SPEC.md:1587-1588` and `docs/data_dictionary.rst:60-63`. Nothing needs to move.
- **(j)** A usage error, exit 2, nothing written, no check identifier (`a2l/options.py:40-84`, caught in `cli.py:106-111`): `not valid json: <json message>`, `expected a json object mapping symbol names to addresses`, `address of 'X' is not an integer: 10.0` (also for `true`), `address of 'X' is -16, outside the range 0 .. 0xFFFFFFFF that an a2l address can hold` (also for 4294967296). A non-empty map missing symbols is `address-missing` (warning; under `--strict` an error and nothing is written), with the unknown keys named in a note (`cli.py:620-668`). Consistent with `SPEC.md:1188-1194` and 1.1's "usage error"; section 6 could cross-reference the check.
- **(k)** Format `7` (`ir.py:551`). Top level: `format`, `name`, `description`, `source`, `components`, `objects`, `enums`, `constants`, `rasters`, `types`, `instances`, `leaves`, `plugins`, `extensions`. A component: `name`, `description`, `source`, `declarations[{name, scope, condition}]`. An object: `name`, `id`, `extensions`, `kind`, `datatype`, `description`, `unit`, `conversion` (kind spelled out), `limits{min,max}`, `shape`, `dimensions` (spelling, constant names kept), `init`, `section`, `raster`, `volatile`, `condition`, `references`, `owner`, `consumers`, `local`, `a2l{export,format,display_identifier}` with `export` resolved to a boolean. An instance: `name`, `id`, `extensions`, `type`, `kind`, `description`, `shape`, `dimensions`, `volatile`, `section`, `raster`, `condition`, `owner`, `consumers`, `local`, `a2l`. A leaf: `path`, `instance`, `instance_id`, `kind`, `datatype`, `description`, `unit`, `conversion`, `limits`, `shape`, `dimensions`, `bits`, `volatile`, `section`, `raster`, `condition`, `owner`, `consumers`, `local`, `a2l` (the instance's and the member's export folded into one). A raster: `raster`, `event`, `cycle`, `cycle_ns`, `description`. A struct: `name`, `description`, `members[{name, description, datatype, type, external, header, dimensions, bits}]`. `enums` and `constants` are the description models. Every statement the spec makes about what is recorded checks out: the producer's condition on the object and each declaration's own on the component (3.3.1.4), the best documented enum (3.4, `enums`), the section (3.5), the raster (3.10), the blocks and `plugins` (3.11, leaves carry none), `id`/`instance_id` for pairing (4.1), the format gate (`loading.py:441-447`). `docs/data_dictionary.rst` is accurate, including the schema top level. A short spec section could simply list the above.
- **(l)** Confirmed from the backend side, see Important 1: the C backend has no guard (a curve or map with an empty shape is rendered as a scalar with a comment naming the missing axis); the A2L backend guards `_characteristic` only, so `AXIS_PTS` and `AXIS_DESCR` input quantities dangle and the `GROUP` references the dropped characteristics. `addressed_symbols` (`a2l/model.py:242-260`) at least stays consistent with what is written.

### Spec gaps proven from code

- The A2L file name `<project>.a2l` and the `-o` directory (`a2l/options.py:29-30`, `cli.py:420-424`).
- The order of record kinds inside `MODULE`, and that leaves follow the plain objects of their kind rather than being merged into one sort (`project.a2l.jinja:30-149`, `a2l/model.py:231-249`).
- What a `GROUP` references: every declaration of any scope in declaration order, then the leaves of declared instances (`a2l/model.py:410-433`).
- The `COMPU_METHOD` key includes the datatype's default format, and which colliding method keeps the unsuffixed name (`a2l/model.py:487-500`, `:555-569`).
- An enum-converted object is declared with its base datatype, never the enum typedef (`c/literals.py:63-64`).
- A component header keeps the author's declaration order, while the definition file sorts by name (`c/model.py:523-547` vs `:449-463`).
- Objects no component owns go to a last group `<unresolved>`, and their `owner` renders as that string (`c/model.py:28`, `:344-350`, `:516`).
- `address-missing` in section 6: a warning naming the uncovered symbols, an error under `--strict` that writes nothing, unknown keys named in a note (`cli.py:620-668`, `:728-734`).
- Address map values: non-integer numbers refused, strings whitespace-stripped, `-0x` read then refused for its sign (`a2l/options.py:64-84`).
- The default display format is a property of the `COMPU_METHOD`; a `NO_COMPU_METHOD` record carries none (`project.a2l.jinja:45-53`).
- A `boolean` under a linear conversion is accepted (`edge5`, `BoolLin`) and gets `%8.0`/`%8.3` by the factor's and offset's integrality.
- The `HEADER`, `PROJECT` and `MODULE` comments fall back to the project name when the project has no description (`a2l/model.py:263`).
- `AXIS_PTS` carries `MaxDiff 0` and both layouts use `DIRECT` addressing, the axis layout `INDEX_INCR` (`a2l/model.py:462-471`); 5.2 mentions only `ROW_DIR`.
- Strings also replace DEL (0x7f) by a space (`a2l/model.py:613-623`).
- `--dry-run` creates no directory either (`base.py:84-98`), and a nonexistent template directory is the "no template to render" usage error (`c/backend.py:93-100`).
- What an ignored `unknown-reference` produces in each artefact (Important 1).

### Test gaps

- `MOD_COMMON`: no test asserts the `ALIGNMENT_*` lines (`grep ALIGNMENT_ tests/` is empty); `BYTE_ORDER` is covered (`tests/test_a2l.py:36-38`).
- `HEADER` with `PROJECT_NO` and `VERSION`: no test names them (`test_skeleton`, `tests/test_a2l.py:28-34`, checks `PROJECT`/`MODULE` only).
- The `_2`/`_3` suffix on a name collision: `tests/test_a2l.py:276-287` asserts two methods with different formats but never a suffixed name; no test covers two linear conversions in one unit (`grep CM_LIN_[A-Z]*_2 tests/` is empty).
- `boolean` in the A2L: `UBYTE` with limits `0 1` and its display format appear in no test (`grep boolean tests/test_a2l.py tests/test_calibration.py` is empty).
- The order of records in the A2L (objects by name, member paths by path, kinds in the template's order): only the C side is asserted (`tests/test_structures.py:76`).
- A dangling `input` of an axis and `GROUP` references under `-W unknown-reference=ignore` or `--force`: only the curve case is tested (`tests/test_a2l.py:307-312`).
- `ddd dump --format json` findings on stderr: the dump tests read `.out` only (`tests/test_cli.py:1486`, `:1505`).
- A `float32` init that underflows (Minor 2).

### Assessment

The generated C and A2L conform to sections 5 and 6 in everything I could compile, read or run: four example projects and five edge projects compile warning-free under the CI's strict flag set, every A2L record has the right fields in the right order with the closure, `MATRIX_DIM` and `COEFFS` conventions the spec argues for, and the determinism promise holds on Windows down to the mtime. The findings are on the boundaries: the spec understates the code in three places (`COMPU_METHOD` key, the closure over an axis's input, the display-format rule) and does not state the A2L file name, the record order or what a `GROUP` holds; and the one behavioural hole, dangling references surviving an ignored `unknown-reference`, is guarded for curves and maps but not for axis inputs, `AXIS_DESCR` inputs or group references.

## Pass 5: the tool interface (SPEC.md sections 3.11, 7, 7.1 and 7.2)

### Scope covered

Read in full: `SPEC.md` sections 1, 2, 3.6, 3.11, 4 (opening), 6, 7, 7.1, 7.2; `src/ddd/cli.py`; `src/ddd/plugins.py`; `src/ddd/build_info.py`; `src/ddd/diagnostics.py`; the plugin, block and `sources()` parts of `src/ddd/loading.py`; `src/ddd/identity.py`; `cmake/Ddd.cmake` (all 642 lines); `examples/cmake/CMakeLists.txt`; `examples/plugins/ddd_layout.py`; `examples/layout/project.ddd.json`; all nine files of `src/ddd/lsp/`; `editors/vscode/package.json`, `src/*.ts` (extension, config and both tests), `README.md`, `tsconfig.json`, `.vscodeignore`; `.pre-commit-hooks.yaml`; `docs/command_line_interface.rst`, `docs/build_integration.rst`, `docs/editor_integration.rst`, `docs/plugins.rst`; `README.md` lines 132-236, 463-473, 702-875; `CHANGELOG.md` "Unreleased" and 0.8.0; `tests/test_documentation.py::TestCommands` and `::TestPackaging`; the plugin, standalone and identity tests in `tests/test_cli.py`, `tests/test_plugins.py`, `tests/test_lsp.py`, `tests/test_cmake.py` as far as the claims below needed them.

Ran, with the scratchpad venv (`ddd 0.8.0` from `C:\git\ac11\ddd\src`, CMake 4.4.3, Ninja 1.13.2) and CLion's MinGW gcc 13.1 on PATH:

- `tests/test_cmake.py`: the first run had 8 failures, all because the harness's `compiler()` found no `gcc` (my PATH used `C:/` spellings Git Bash does not resolve) and CMake fell back to a clang in `~/Downloads` without an MSVC runtime; re-run with `/c/` spellings the same 8 tests pass. Not a finding.
- `tests/test_lsp.py`: passes except the known `TestSymlinkedWorkspace` privilege failure (run once with `-x`, then in full with that test deselected).
- `examples/cmake` configured and built by hand into the scratchpad (`-G Ninja -DCMAKE_C_COMPILER=gcc`): configure writes the schemas, the build generates and links `firmware.elf.exe`, a second build is a no-op, `firmware_ddd_check` and `controller.ddd` both pass; I read the collected `DemoDevice.ddd.json`, `ddd-build.json`, the `ninja -t targets` list and the command lines in `build.ninja`.
- Five CLI batches (`PYTHONPATH=src python -m ddd ...` from the repository root) over `examples/demo`, `examples/inconsistent`, `examples/layout`, `examples/pressure`, plus fixtures in the scratchpad: a units file as root, a component with `"id": null`, a non-JSON file, and seven plugin modules (no `PLUGIN`, a malformed name, a reserved name, a raising hook, two modules claiming one name, an unimportable module, a backend claiming a built-in path).
- Five scripted language-server sessions over pipes: a build record whose `severity` names an unknown check, a `workspace/didChangeWatchedFiles` notification, a header block without `Content-Length`, a non-numeric `Content-Length`, a plugin hook raising under a record.

Not covered: the extension was not run inside VS Code and its `npm test` was not run (its behaviour was read from `extension.ts`/`config.ts` and the two tests); the docker section of the docs was read, not executed; the pre-commit hook was not executed. One side effect to note: an `-o` argument of mine escaped MSYS path conversion and created `C:\c\Users\...\pass5\cli\broken.ddd.json\sub\DemoDevice.a2l`; I removed exactly that subtree (`C:\c\Users\lmbsog0\AppData\Local\Temp\claude\C--git-ac11-ddd`) and touched nothing else under `C:\c`, where an unrelated session's files also live. The repository is untouched (`git status` clean).

### Strengths

- The severity machinery is one object end to end: `SeverityPolicy.from_strings` (`src/ddd/diagnostics.py:400-425`) refuses unknown checks, unknown severities, malformed overrides and fixed checks with distinct messages, exit 2 in every command including `build-info`; plugin overrides are held provisionally and verified against what actually loaded (`verify`, 430-437; observed `unknown check 'layout/no-such': no loaded plugin registers it`).
- `--without` subtracts an artefact together with its options and refuses a run left with nothing to write (`cli.py:686-741`); every case in the spec sentence at `SPEC.md:1533-1537` was observed with the stated outcome.
- The standalone policy is derived from the registry flag (`diagnostics.py:251-256`), used identically by `ddd check --standalone`, the CMake per-component target and the language server, and `tests/test_cli.py:47-58` pins that the flag silences exactly the flagged checks.
- The text and JSON diagnostic shapes match `SPEC.md:1575-1590` exactly (path, pointer, line, column, notes of the same shape, summary by severity; ordering severity, path, pointer with numeric indices as numbers - observed on `examples/inconsistent`).
- The CMake module is careful where it counts: the seeded empty map, the a2l-only dependency on the map, `restat`-friendly unchanged writes, `CONFIGURE_DEPENDS` on templates and sources, the tool itself as a dependency, and every refusal (`PLUGINS` beside `PROJECT`, multi-config, no `.c` template, two images propagating headers) with a message that names the fix.
- The server is thin and its protocol handling is right: parse and invalid-request errors do not end the session, a corrupt length does with one line on stderr, unknown requests get `METHOD_NOT_FOUND`, stdout is taken as the wire before any plugin can print to it (`server.py:492-502`).
- The documentation transcripts I re-ran (`docs/command_line_interface.rst:200-211`, `216-222`, the `ddd lsp --help` block in `docs/editor_integration.rst:12-29`) are byte-for-byte what the tool prints today.

### Issues

#### Critical

1. **The spec denies the `--standalone` leniency the command line has and the CMake module relies on**
   - Where: `SPEC.md:1570-1573` ("a component alone is checked with every check, the whole project ones included, because holding them back is the editor's leniency [...], not the command line's"); `src/ddd/cli.py:153-161` (`--standalone` on `check`) and `1159-1170` (`_analyze` prepends `STANDALONE_POLICY`); `cmake/Ddd.cmake:224-249` (the `<target>.ddd` target runs `ddd check <file> --standalone`); `CHANGELOG.md:117-125` (introduced in 0.8.0); `docs/command_line_interface.rst:82-88`; `README.md:219, 721-723`.
   - What: the spec's normative sentence states the opposite of what the tool does. Observed: `ddd check examples/demo/components/controller.ddd.json` -> 2 errors, 5 warnings, exit 1; the same with `--standalone` -> `ok: 12 variables in 1 component are consistent`, exit 0; `ninja controller.ddd` in the example build prints exactly that line.
   - Why it matters: `SPEC.md` is the normative document (1.1: an implementation that behaves otherwise does not conform). An implementer following it would have no `--standalone`, and the module's per-component targets - a public interface the docs and README advertise - would not work. The spec has simply not been updated since 0.8.0.
   - Fix: spec moves. Replace the clause at 1570-1573 with: the root is a project or a single component file; a component alone is checked with every check unless `--standalone` is given, which holds back the ten checks of section 4 (the same set the editor holds back), an explicit `-W` on the same run still winning; and add the per-component target to 7.1 (see Important 5).

#### Important

1. **A build record naming a check the server does not know ends the language server instead of being declined**
   - Where: `src/ddd/lsp/diagnostics.py:51-55` (`analyse` calls `SeverityPolicy.from_strings(info.severity)`), `src/ddd/lsp/discovery.py:44-64` (`load_builds` validates shape and `format` only), `src/ddd/lsp/server.py:149-175` (`run` catches only `MessageError`/`ProtocolError`), `src/ddd/cli.py:99-116` (`main` turns the `UnknownCheckError` into `ddd: unknown check ...`, exit 2); `SPEC.md:700` ("a record it does not understand is one it declines rather than misreads"), `SPEC.md:1714` ("a record that cannot be read is skipped").
   - What: observed with `ddd-build.json` carrying `"severity": ["no-such-check=ignore"]`: on `textDocument/didOpen` the server logs the record, then exits 2 with `ddd: unknown check 'no-such-check'` and publishes nothing. A plugin override in a record (`raiser/nosuch=ignore`) is fine, since the server never calls `verify`.
   - Why it matters: `ddd build-info` refuses such a record when written by the same version, so this needs version skew: a build configured with a newer DDD that has a check the developer's editor `ddd` lacks (the extension README says a server older than the extension "is the case nobody has tried") kills the server on every open and save; the client gives up after a few restarts and the reader sees nothing. `tests/test_lsp.py:280-284` covers unreadable shapes only.
   - Fix: code moves. In `load_builds` (or `analyse`) build the policy inside `try/except UnknownCheckError`, skip the record and announce it in the log the way a record naming a missing project is announced (`server.py:300-312`); add the test.

2. **`ddd sources` and `ddd artefacts` exit 0 with error findings, and `sources` hides them in text mode**
   - Where: `src/ddd/cli.py:1084-1085` (`artefacts` text: `_report` then `EXIT_OK`), `1106-1112` (`sources` text: paths only, no `_report`), `1100-1106` (`sources` JSON carries `diagnostics`); `SPEC.md:1586-1590` (exit code rule, no exception), `SPEC.md:1542-1546, 1557-1561` (the two commands, no mention of tolerance); `docs/command_line_interface.rst:70-72` (exit 1 for `sources` on an unreadable root; `artefacts` not mentioned), `285-289` (`sources` "deliberately more tolerant"); `CHANGELOG.md:57-62` (`artefacts` "tolerant the way `ddd sources` is").
   - What: observed on a project whose second include does not exist: `ddd artefacts` prints `error[file-not-found] ... 1 error` and exits 0; `ddd sources` prints three paths - the missing file among them - and nothing else, exit 0; `ddd sources --format json` carries the `file-not-found` diagnostic. On `examples/inconsistent`, `sources` exits 0 (its diagnostics are empty, since it never runs the analysis).
   - Why it matters: the spec's rule "a findings exit is reserved for findings reported as errors" is contradicted by two commands the build integration calls at configure time, and the same command tells a different story in its two formats. A hand-written `PROJECT` whose include is missing configures silently and fails later inside ninja ("missing and no known rule to make it") rather than with DDD's finding.
   - Fix: spec states the tolerance of both commands (exit 1 only when the root cannot be read, findings still reported); `_command_sources` text mode calls `_report(bag, "text")` after the listing as `artefacts` does; the exit-code table names `artefacts` beside `sources`.

3. **The plugin name grammar, the reserved names and the meaning of "malformed" are unspecified**
   - Where: `src/ddd/plugins.py:36` (`^[a-z][a-z0-9_]*$`), `38-45` (`c`, `a2l`, `all` reserved), `49` (check grammar `^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`), `112-131` (`__post_init__`: name, reserved name, `<name>/<check>` spelling, duplicate registration), `143-156` (`PLUGIN` not a `Plugin`); `SPEC.md:966-970` ("exposes a malformed one"); `docs/plugins.rst:100` ("a lowercase identifier", nothing about the reserved names or the check grammar).
   - What: observed `plugin-invalid: plugin 'bad_name.py' failed to import: plugin name 'Bad-Name' is not a lowercase identifier` and the same for `name="a2l"`. A plugin author has no text telling them `a2l` or `all` cannot be a plugin name, nor that `layout/Duplicate_Key` is refused.
   - Why it matters: a spec gap the code fills with a choice; the identifiers are part of the tool interface (`SPEC.md:1025-1028`), so their grammar belongs in it.
   - Fix: spec 3.11 states the two grammars and the three reserved names and lists the five causes of `plugin-invalid`; `docs/plugins.rst:100` names the reserved three. (Tests exist: `tests/test_plugins.py:158-171, 1517`.)

4. **`ddd checks` does not say which checks need the whole project, but the docs say it does**
   - Where: `src/ddd/cli.py:1115-1141` (text marks `(fixed)` only; JSON carries `check`, `default_severity`, `description`, `overridable`); `docs/build_integration.rst:56-58` ("Which checks those are is declared in the registry - ``ddd checks`` lists them"); `SPEC.md:1039-1043` (the ten checks named in prose), `SPEC.md:1566-1567`.
   - What: observed `ddd checks` output: no marker distinguishes `unknown-type` (held back) from `type-kind` (not); the JSON has no `needs_every_component` or `comparison` field. The only lists a user can consult are the prose in the spec, `docs/editor_integration.rst:108-113` and the README.
   - Why it matters: an inaccurate documentation statement; and a build author choosing what `--standalone` or a per-component target silences has no tool answer, which is what "the authoritative list is the one the tool prints itself" (`SPEC.md:1029-1030`) promises.
   - Fix: add a `(project-wide)` marker (and `(comparison)`) to the text and `needs_every_component`/`comparison` booleans to the JSON, and let the doc sentence stand; or reword `build_integration.rst:56-58` to point at the editor page's list.

5. **Section 7.1 omits three public pieces of the module that the docs describe**
   - Where: `cmake/Ddd.cmake:224-249` (`<target>.ddd` per-component check target), `526-529` (`DDD_A2L` target property), `378-383` (multi-config generators refused); `docs/build_integration.rst:48-59, 342-346, 355-366`; `README.md:784-786`; `SPEC.md:1598-1663` (names `<stem>_ddd_check` only, 1652-1655).
   - What: the spec's inventory of what `ddd_generate`/`ddd_add_component` create is incomplete: a target a CI job is told to run, a property an install step is told to read, and a refusal a project meets at its first configure are all outside the normative text.
   - Why it matters: public interface the spec does not describe; a conforming re-implementation would lack them.
   - Fix: spec 7.1 adds one sentence each: `ddd_add_component` defines an on-demand `<target>.ddd` target running `ddd check --standalone` on each registered component file under the default policy (vocabulary files skipped); `ddd_generate` publishes the a2l path as `DDD_A2L`; multi-config generators are refused.

6. **Where a project-wide vocabulary file goes in the CMake build is stated nowhere, and the spec names only types files**
   - Where: `SPEC.md:1604-1606` ("registers descriptions, component and types files alike"); `cmake/Ddd.cmake:203-210` (any existing `*.ddd.json` is accepted), `152-170` (`_ddd_is_component_file`; the comment at 153 lists "types, units, sections, constants" - rasters is handled by the code but missing from the comment), `242-245` (non-component files skipped by the `.ddd` target), `445` (the image's own `DDD_JSON` is part of what is collected); `docs/build_integration.rst:41-59` (registering "a component").
   - What: units, sections, constants and rasters files register exactly like types files, and a file registered on the image target itself is collected too (the transitive property includes the target's own value), but no page says on which target a vocabulary every image shares belongs, or that the image target is a legitimate home.
   - Why it matters: a documentation omission a user meets on the first project with a shared units file; question (g) of pass 1 exists because the text does not answer it.
   - Fix: spec 1605 says "component and vocabulary files alike"; `docs/build_integration.rst` adds a sentence: register a shared vocabulary on a target every image links (an interface library, or the image itself), it travels like a component's description and is never checked alone; fix the comment at `Ddd.cmake:153`.

7. **The two-run flow's second half - producing the address map - is documented by nobody**
   - Where: `SPEC.md:1628-1637` ("rewriting it after linking is what makes the next build run DDD a second time"), `SPEC.md:1505-1520` (section 6: the map's JSON format; reading the linker output is "planned"), `SPEC.md:124-130`; `cmake/Ddd.cmake:401-411` ("typically extracted from the linked image by a build step"); `docs/build_integration.rst:408-416` ("once the extractor has written the real map"); `docs/concept.rst:399-410` and `docs/faq.rst:492-507` (the map is "extracted from the linker output" - by whom is not said).
   - What: the module seeds `{}`, depends on the file and reads it; nothing in DDD writes it, no page shows a `POST_BUILD` step, a script, or an `nm`/`readelf` recipe, and the module publishes `DDD_A2L` but no analogous hook for the map. `docker/compile.sh:96` uses `nm` for verification only.
   - Why it matters: a user following `docs/build_integration.rst` cannot complete the flow the `ADDRESS_MAP` row describes; "the extractor" reads as if DDD shipped one.
   - Fix: docs move. State plainly that producing the map is the project's step, give one worked `add_custom_command(TARGET <image> POST_BUILD ...)` example writing the JSON of section 6 from the toolchain's symbol lister into the seeded path, and note that `ddd generate` never runs a toolchain tool, so a toolchain without `nm` only means the project writes the map some other way.

#### Minor

1. **`ddd check --baseline` takes neither `--renames` nor `--plugin`, which the spec sentence leaves ambiguous** - `SPEC.md:1524-1528` lists both options in the clause covering "`ddd compare` [...] or `ddd check --baseline`"; `src/ddd/cli.py:141-164` defines neither on `check` (observed: `unrecognized arguments`, exit 2). Fix: spec says they belong to `compare`, `check --baseline` reading its candidate's own plugins and writing no rename list.

2. **The `ok:` line is printed only when there are no findings at all, not on every clean run** - `SPEC.md:1582-1583` ("a clean `ddd check` closes with an `ok:` line") against `SPEC.md:1587-1589` (a warnings-only run "is a clean run") and `src/ddd/cli.py:566` (`not len(bag)`). Observed: `ddd check controller.ddd.json -W missing-producer=ignore` -> `5 warnings`, exit 0, no `ok:`. Fix: spec says "a check without findings" or the code prints the line after a warnings-only summary.

3. **The extension's file watcher feeds a notification the server drops** - `editors/vscode/src/extension.ts:50-53` (comment: "watching them also covers a file changed by a build or by a branch switch") sends `workspace/didChangeWatchedFiles`; `src/ddd/lsp/server.py:204` answers only requests it does not know and ignores unknown notifications (observed: no refresh, no error). Neither doc claims the behaviour, so only the comment and the configuration are wrong. Also `package.json:33-36` activates on any JSON file (`onLanguage:json`). Fix: either handle the notification in `_REFRESHING` (a save from another process is the case the comment names) or drop `synchronize` and the comment; drop `onLanguage:json` or keep it deliberately.

4. **A header block without `Content-Length` ends the session silently with exit 0** - `src/ddd/lsp/protocol.py:65-66` returns `None`, which `Server.run` (`server.py:149-158`) treats as end of stream; `SPEC.md:1719-1721` says a corrupted frame header "ends the session with a message rather than a failure trace". Observed: exit 0, empty stderr. `tests/test_lsp.py:111` pins the `None`. Fix: spec says a header block without a length is read as the end of the conversation, or the reader raises `ProtocolError` like the non-numeric case.

5. **`--standalone` is accepted on a project root and silences the ten checks project-wide** - `src/ddd/cli.py:153-161, 1159-1170`; observed `ddd check examples/demo/demo.ddd.json --standalone` -> `ok: 21 variables in 4 components`. `docs/command_line_interface.rst:86-87` ("judge a component on its own"). Fix: refuse, or warn on stderr, when the root file is a project; state it in the spec once `--standalone` is in it.

6. **`SCHEMA_DIRECTORY` with `PROJECT` closes the schemas over the root file's plugins only** - `cmake/Ddd.cmake:299-316` reads `project.plugins` of that one file; `SPEC.md:955-960` makes the set in play the union over sub-projects, so a plugin a sub-project names is left out of the editor's schema. Fix: comment and docs state the limit, or the module asks the tool (`ddd sources` already imports them; a `ddd artefacts --format json`-style listing of plugin specs would close the gap).

7. **A provisional plugin override is verified only after a clean load** - `src/ddd/cli.py:1164-1167` (`verify` runs only when `not bag.has_errors`); a typo like `-W layout/no-suhc=ignore` on a project with a `schema` error is reported as exit 1 for the findings and the typo surfaces only once the project is fixed. Fix: verify before the early return.

8. **`docs/build_integration.rst:327` says the generation re-runs "when a component changes its declarations and not otherwise"** - it also re-runs on a template, a `PLUGINS` file, the address map, `DEPENDS` entries and the tool itself (`cmake/Ddd.cmake:532-541`). Fix: drop "and not otherwise" or list the dependencies.

9. **The pre-commit hook is a published interface only one page mentions** - `.pre-commit-hooks.yaml` (`ddd-id`, `entry: ddd id --assign`, `files: \.ddd\.json$`) is documented at `docs/build_integration.rst:552-583` and nowhere else (`SPEC.md` section 7, `README.md`: no mention). Fix: one sentence in 7 ("a pre-commit hook `ddd-id` running `ddd id --assign` on the staged description files") and one line in the README's build section.

10. **`-b` paths are relative to the server's working directory, undocumented** - `src/ddd/lsp/discovery.py:29-38` uses the configured paths as given; the extension spawns without `cwd`, so `vscode-languageclient` uses the workspace folder and relative entries work there; `docs/editor_integration.rst:131-137` and `package.json:55-63` do not say relative to what. Fix: one clause ("relative to the workspace folder") in both.

11. **`docs/plugins.rst:148-151` lists the plugin artefact's options as `-o`, `--dry-run` and `--force`** - it also takes `-W`, `--strict` and `--format` (`src/ddd/cli.py:222-227`, observed `--help`). Fix: "and the severity and format options every analysis takes".

### Answers to the questions from pass 1

- **(a) `--standalone`.** Defined on `check` only (`src/ddd/cli.py:153-161`; `generate` rejects it, observed). `_analyze` (`cli.py:1159-1170`) builds the policy from `STANDALONE_POLICY` (`diagnostics.py:251-256`: every `needs_every_component` check as `=ignore` - the ten of `SPEC.md:1039-1043`) followed by the caller's `-W`, so the caller wins: observed `--standalone -W missing-producer=error` reports the two `missing-producer` errors again. The CMake per-component target is `<target>.ddd`, defined by `ddd_add_component` (`cmake/Ddd.cmake:224-249`), one `POST_BUILD` command per registered *component* file (`ddd check <file> --standalone`, line 247; vocabulary files skipped, 242-245), under the default policy - it never sees `STRICT`/`SEVERITY`, which belong to `ddd_generate` - and observed as `ninja controller.ddd` -> `ok: 12 variables in 1 component are consistent`. The spec sentence at `SPEC.md:1570-1573` is wrong and should move (Critical 1); `tests/test_cli.py:36-68` pins the code's behaviour.

- **(b) Plugin names.** Grammar `^[a-z][a-z0-9_]*$` (`src/ddd/plugins.py:36`); reserved `c`, `a2l`, `all` (`38-45, 116-118`) because `ddd generate <name>` selects a plugin by its name and `_plugin_artefact` (`cli.py:117-135`) registers a subcommand for anything matching the grammar that is not built in (observed: `ddd generate Bad-Name` is an argparse "invalid choice"; `ddd generate nosuch <layout project>` -> `'nosuch' is not an artefact of this project; it provides: 'layout'`, exit 2). "Malformed" is: `PLUGIN` missing or not a `Plugin` (`143-156`), a name outside the grammar, a reserved name, a check identifier not `<name>/<check>` with `<check>` matching `^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$` (`49, 120-128`), or a check registered twice (`129-131`); all raise `ValueError` during import and surface as `plugin-invalid: plugin 'x.py' failed to import: <reason>` (observed). Spec and `docs/plugins.rst:100` should state this (Important 3).

- **(c) Orders and exit codes.** `ddd list`: rows sorted by variable name (`src/ddd/ir.py:704-711`; observed `AxisA ... ValueK`). `ddd sources`: sorted absolute POSIX paths, plugin files among them (`loading.py:378-384`; observed `examples/plugins/ddd_layout.py` last). `ddd artefacts`: `c`, `a2l`, then the plugins with a backend in project order (`cli.py:1044-1050`). `ddd checks`: registry definition order (`diagnostics.py:89-249`: errors, warnings, infos, then the comparison checks), then each `--plugin`'s checks in its declared order (`cli.py:1117`). Both `sources` and `artefacts` exit 0 with error findings and 1 only when the root cannot be read (`cli.py:1066, 1084-1085, 1106-1112`; observed on `examples/inconsistent` and on a project with a missing include). `sources` never runs the analysis, so even its JSON diagnostics are load-time only (observed `"diagnostics": []` on `examples/inconsistent`), and its text mode prints no findings at all; `artefacts` prints them. Spec should state the tolerance; `sources` text should report (Important 2).

- **(d) The linkable targets.** `<stem>_ddd_headers` (`cmake/Ddd.cmake:550-552`): an INTERFACE library carrying the output directory as an include directory and a build-order dependency on `<stem>_ddd_generation`; in the collected mode also every registered component's `INTERFACE_INCLUDE_DIRECTORIES`, `INTERFACE_COMPILE_DEFINITIONS` and `INTERFACE_COMPILE_OPTIONS` through `$<TARGET_PROPERTY:...>` (`572-583`), and it is linked into every registered component unless `NO_PROPAGATE_HEADERS` (`615-632`). `<stem>_ddd_globals` (`588-596`): an OBJECT library of every generated `.c` (`definition_files`, `505-512`), PUBLIC-linking `_ddd_headers`, PRIVATE-linking `LINK_LIBRARIES`, linked PRIVATE into the image. Observed: `firmware_ddd_generation`, `firmware_ddd_globals`, `firmware_ddd_check` and the four `<component>.ddd` targets in `ninja -t targets`; the interface library shows as `-I.../ddd/firmware.elf` on every component's compile line. Spec 7.1 names neither; the docs do (`docs/build_integration.rst:316-346`).

- **(e) A vocabulary file as root.** A `file-kind` finding, exit 1, located at the file: `error[file-kind]: this is a unit vocabulary; list it in the 'includes' of the project w[...]` - observed identically for `check`, `list` and `sources` on a units file. Not a usage error, consistent with 1.1 (a violation in description data is a finding); no other identifier. The spec's "a project or a single component file" (`SPEC.md:1570-1571`) is accurate; the docs could name the outcome.

- **(f) Include order in the collected project.** CMake's own evaluation of the transitive `DDD_JSON` property, deduplicated first-occurrence-first by `$<REMOVE_DUPLICATES:$<TARGET_PROPERTY:${image},DDD_JSON>>` (`cmake/Ddd.cmake:445`); the module imposes no order of its own. For the example (`firmware.elf` links `user_interface event_logger`; `user_interface -> controller -> sensor_hub`) the generated `DemoDevice.ddd.json` lists `user_interface, controller, sensor_hub, event_logger`: a depth-first walk of `target_link_libraries` in declaration order. The spec's "the link graph's traversal order, first occurrence kept" (`SPEC.md:1623-1625`) is therefore "CMake's transitive-property order", which the spec could say so that nobody expects a topological one.

- **(g) Vocabulary files and `ddd_add_component`.** Any existing `*.ddd.json` registers (`cmake/Ddd.cmake:203-210`): units, sections, constants and rasters files exactly like types files; only a file whose top-level key is `component` gets a `.ddd` check command (`159-170, 242-245`). A project-wide vocabulary belongs on any target inside the image's link closure - an interface library every component links, or the image target itself, whose own `DDD_JSON` value is part of what `445` collects. Neither the spec (`1604-1606`, "component and types files alike") nor the docs say where; the comment at `153` omits rasters (Important 6).

- **(h) `NO_A2L`, `ddd id`, the artefacts note.** With `NO_A2L` the map is neither seeded, nor a dependency, nor passed (`cmake/Ddd.cmake:395-411, 482-485`); with the a2l it is a dependency of the generation (`address_map_dependency`, `537`), so rewriting it after the link re-runs `ddd generate all`, whose C output is `unchanged` (observed statuses) and whose rule carries `restat = 1`. `ddd id --assign` treats `"id": null` as unstamped and replaces the `null` in place (`src/ddd/identity.py:69-93, 133-147`; observed: 9 removed keys plus one `null` -> `wrote 10 ids`, a second run `wrote 0 ids`); a file it cannot parse is reported as `<path>: not readable as json, skipped`, the others are still stamped, exit 1 (observed; `cli.py:845-860`); a non-component file is a silent no-op. `ddd artefacts` prints, after the listing on stdout and on stderr, `note: the project also names 'quiet', which provides no artefact of its own; the c artefact renders any template reading such a plugin's block` (`cli.py:1071-1083`, observed); in JSON the names are `plugins_without_artefact`.

- **(i) Options of `ddd generate <plugin>`; `check --baseline --renames`.** The plugin artefact takes `project`, `-o/--output-dir`, `--dry-run`, `--force`, `-W/--severity`, `--strict`, `--format` and nothing else (`src/ddd/cli.py:222-227`; observed `--help`); `-t` is refused as `unrecognized arguments`, exit 2, and `ddd generate a2l -t` likewise. `ddd check --baseline` accepts neither `--renames` nor `--plugin` (observed, exit 2); the spec's sentence (`SPEC.md:1524-1528`) should say those belong to `compare` (Minor 1).

- **(j) The real address map.** Nobody in DDD produces it. The module seeds `{}` into a build-tree path that does not exist (`cmake/Ddd.cmake:401-411`), depends on it (`537`), and its comment says the map is "typically extracted from the linked image by a build step"; the docs (`build_integration.rst:408-416`) say "once the extractor has written the real map"; spec section 6 (`1505-1520`) defines the JSON and calls reading the linker output "planned". No extractor, script, `POST_BUILD` example or toolchain command exists anywhere in the repository (`docker/compile.sh:96` uses `nm` for symbol verification only). On a toolchain without `nm`, nothing in DDD is affected - `ddd generate` runs no toolchain tool - the project just has no map and ships the first-run a2l with address 0. Docs should move (Important 7).

- **(k) What the extension contributes.** Two settings `ddd.executable` and `ddd.buildDirectories` (`editors/vscode/package.json:46-66`), one command `ddd.restartServer` (`39-45`, `extension.ts:30-33`), activation on `workspaceContains:**/*.ddd.json` and on any JSON document (`onLanguage:json`, `33-36`), a document selector for `file` + `json` + `**/*.ddd.json` (`extension.ts:48`), a file-system watcher whose notifications the server drops (`50-53`; `server.py:204`), and an error message naming the setting when the executable cannot be spawned (`59-66`). No language, grammar, snippets, `jsonValidation` or schema binding (the `$schema` key inside each file is what binds the schemas), no hover or completion of its own; version `0.8.0` matches the package (pinned by `tests/test_documentation.py:523-529`). "No more than launch the server" (`SPEC.md:1727-1729`) holds in substance: the restart command is part of launching, and the docs list it (`docs/editor_integration.rst:125, 142`); the watcher is dead configuration (Minor 3).

### Spec gaps proven from code

- `ddd check --standalone` exists and is what the CMake per-component target runs (`src/ddd/cli.py:153`; `cmake/Ddd.cmake:247`) - contradicting `SPEC.md:1570-1573`.
- `ddd_add_component` defines an on-demand `<target>.ddd` target per registered target, checking each component file alone, vocabulary files skipped (`cmake/Ddd.cmake:224-249`).
- `ddd_generate` publishes the a2l path as the `DDD_A2L` target property (`cmake/Ddd.cmake:526-529`).
- Multi-config generators are refused at configure time (`cmake/Ddd.cmake:378-383`).
- The tool is found by `find_program` into the cache variable `DDD_EXECUTABLE`, overridable with `-DDDD_EXECUTABLE` (`cmake/Ddd.cmake:40`).
- The tool executable itself is a dependency of the generation (`cmake/Ddd.cmake:537`).
- `ddd_add_component` requires CMake 3.30 in every mode (`cmake/Ddd.cmake:200`), so the `.ddd` targets do not exist for a 3.20-3.29 build even when `PROJECT` is used.
- A registered file not named `*.ddd.json` is a fatal configure error (`cmake/Ddd.cmake:204-207`), although `file-extension` is a relaxable check.
- `SCHEMA_DIRECTORY` beside `PROJECT` closes the schemas over that file's `plugins` only, not the union with sub-projects (`cmake/Ddd.cmake:299-316`).
- `ddd sources` and `ddd artefacts` exit 0 with error findings; `sources` reports no findings in text mode and never the analysis's (`src/ddd/cli.py:1066, 1084-1085, 1106-1112`).
- `ddd artefacts` with neither a project nor `--plugin` lists the two built-in artefacts (observed).
- `ddd generate <plugin>` accepts only the common options; `-t`, `--const-inputs`, `--byte-order`, `--address-map` are refused (`src/ddd/cli.py:222-227`).
- `ddd id --assign` refills an explicit `"id": null`, skips non-component files silently, and exits 1 after stamping the others when one file is not JSON (`src/ddd/identity.py:69-93`; `cli.py:845-860`).
- `ddd checks --format json` carries `overridable` but neither `needs_every_component` nor `comparison` (`src/ddd/cli.py:1118-1130`).
- Plugin name grammar `^[a-z][a-z0-9_]*$`, reserved names `c`/`a2l`/`all`, check grammar `^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$` (`src/ddd/plugins.py:36-49`).
- A plugin module is imported once per process and cached by path digest; an edit takes effect in the next process (`src/ddd/plugins.py:171-190`; `docs/plugins.rst` says so, the spec does not).
- `ddd build-info` records a project path it never checks and accepts a plugin override it cannot verify (observed: a missing project and `-W layout/nosuch=info` both write the record, exit 0).
- The server answers hover and navigation for a project that did not read cleanly (`src/ddd/lsp/hover.py:79-99`).
- The server verifies no provisional plugin override from a record (`src/ddd/lsp/diagnostics.py:51-55` never calls `verify`).
- `-b` directories are relative to the server's working directory and a nonexistent one is silently empty (`src/ddd/lsp/discovery.py:29-38`).
- A record naming a project file that does not exist is announced in the log and not analysed (`src/ddd/lsp/server.py:277-285, 300-312`).
- The containing-project search takes the sorted `*.ddd.json` files of the nearest directory that include the document, the document itself excluded, and stops at the workspace folder (`src/ddd/lsp/navigation.py:231-260`).
- A header block without `Content-Length` ends the session silently with exit 0 (`src/ddd/lsp/protocol.py:65-66`; `server.py:157-158`).
- Unknown notifications are dropped and unknown requests answered `METHOD_NOT_FOUND`; `textDocumentSync.change` is 0 and `didClose` is not handled (`src/ddd/lsp/server.py:177-207, 467-483`).
- The extension contributes a restart command, activates on any JSON file and registers a file watcher (`editors/vscode/package.json:33-45`; `extension.ts:30-33, 50-53`).
- A pre-commit hook `ddd-id` running `ddd id --assign` on staged `*.ddd.json` files is published (`.pre-commit-hooks.yaml`).

### Test gaps

- Language server with a build record whose `severity` names an unknown built-in check (only unreadable shapes and a newer `format` are covered, `tests/test_lsp.py:273-291`).
- The CMake module's `STRICT` and `SEVERITY` reaching the generation command, the `<stem>_ddd_check` target and the build record together (`tests/test_cmake.py` has no `_ddd_check`, `STRICT` or `SEVERITY`; `tests/test_cli.py:1720` inspects the module text for the `NO_A2L` guards only).
- `ADDRESS_MAP`: the seeding of `{}`, the map as a generation dependency, and the second run after rewriting it (no `ADDRESS_MAP` in `tests/`).
- `NAME` defaulting to the sanitised image stem, and `NAME` ignored beside `PROJECT` (no test; `tests/test_cmake.py` always passes `NAME`).
- `DDD_A2L`, `NO_PROPAGATE_HEADERS` and the two-image refusal, `LINK_LIBRARIES`, `CONST_INPUTS`, `BYTE_ORDER`, `OUTPUT_DIRECTORY`, `DEPENDS` through the module (none named in `tests/`; `BYTE_ORDER` appears only in `tests/test_a2l.py` for the CLI option).
- The module's 3.20 and 3.30 floor messages (`cmake/Ddd.cmake:30-53`; nothing in `tests/` runs an older CMake or asserts the messages).
- The `.ddd` target skipping a registered vocabulary file (`tests/test_cmake.py:111` builds `sensor_hub.ddd`, a component).
- `ddd check --standalone` on a project root (no test; behaviour observed above).
- `ddd sources` text mode with load-time findings (no test; the behaviour is absent, Important 2).

### Assessment

The tool interface is implemented with more care than the spec records it: every option, exit code, format and ordering I exercised behaves as the documentation says, the CMake flow completes end to end on this machine, and the language server holds up under malformed input and misbehaving plugins. The conformance problems are almost all on the spec's side - it still denies `--standalone`, names none of the module's per-component targets, `DDD_A2L`, the tolerant exit of `sources`/`artefacts`, or the plugin name grammar - with two code-side items worth fixing: the server dying on a build record with an unknown check, and `ddd sources` hiding in text what it reports in JSON.

## Pass 6: the remaining documentation and the repository machinery

### Scope covered

Read in full, sentence by sentence against the code: `docs/getting_started.rst`, `docs/concept.rst`, `docs/faq.rst`, `docs/data_contracts.rst`, `docs/developer_documentation.rst`, `docs/acronyms.rst`, `docs/index.rst`, `docs/conf.py`; `README.md` whole (lines 1-95 and 876-939 in detail, the rest for disagreements with the pages); `CHANGELOG.md` whole; `SPEC.md` section 2 for the concept page's vocabulary; every file under `examples/` (all nine projects, the plugin, the cmake example, the templates); `docker/Dockerfile`, `docker/compile.sh`, `docker/verify_symbols.py`, `docker-compose.yml`, `.dockerignore`; `.github/workflows/ci.yml`, `docs.yml`, `publish.yml`; `pyproject.toml`, the three `requirements*.txt`, `LICENSE`, `.gitattributes`, `.gitignore`, `assets/logo/README.md`, `editors/vscode/package.json` and `LICENSE`, `docs/_static/js/versions.js`, `docs/_templates/versions.html`; `tests/test_transcripts.py` in full and the relevant parts of `tests/test_documentation.py`, `tests/test_backends.py`, `tests/test_cmake.py`; the deferred and status sections of the four plans and four designs under `docs/superpowers/`; the titles of every finding of passes 1-5 in `docs/superpowers/reviews/2026-09-08-complete-review.md`, so as not to repeat them (the `ddd list`/`ddd dump` naming at `README.md:852` and `docs/developer_documentation.rst:314`, the pre-commit hook, and pass 2's "a calibration tool only reads a measurement" at `docs/acronyms.rst:108-110` / `README.md:332-333` are all left out here).

Ran, from the repository root with the scratchpad venv (Python 3.13.15, ruff 0.16.6, mypy 2.3.1):

- `ruff check .` - **All checks passed!**; `ruff format --check .` - **81 files already formatted**; `mypy` - **Success: no issues found in 46 source files**.
- `pip install -r requirements-docs.txt` then `python -m sphinx -b html docs <scratchpad> -W --keep-going` (Sphinx 9.1.0, autodoc-pydantic 2.2.0, erdantic 1.2.1, graphviz 15.1.1 from the PATH, plantuml 2.18.1 through `JAVA`/`PLANTUML_JAR`) - **build succeeded, exit 0, zero warnings**; 55 figures and 5 plantuml diagrams rendered, every page in the toctree.
- The getting-started walkthrough, followed in order in a scratch directory with the three files exactly as the page shows them: every command printed what the page shows, including the `missing-id` infos, `wrote 2 ids`, the `-t` refusal (exit 2), the five template names, the six `created` then six `unchanged` lines, the three generated files and the two a2l excerpts, the `definition-mismatch` + `limits-out-of-range` pair after the edit (exit 1, no `gen2` directory), `--force` writing six files and exiting 1, and `--const-inputs` declaring the input `extern const volatile`.
- `ddd check` on all nine example projects, `ddd compare` on the pressure deliveries, `ddd list` on the demo, `ddd checks`, `ddd check --standalone`, `ddd artefacts` (text, json, `--plugin`), `ddd sources`, `ddd dump`, `ddd generate` with `--without`, `--dry-run`, three address maps and an empty one, `-W` on an unknown and on a fixed check; the hand-written transcripts of `data_contracts.rst` and of the FAQ reproduced on files written for the purpose.
- `pip wheel . --no-deps` into the scratchpad (`ddd_tool-0.8.0-py3-none-any.whl`, 241 963 bytes), listed, installed into a fresh venv: `ddd cmake-dir` and `ddd templates-dir` resolve to `site-packages/ddd/cmake/Ddd.cmake` and `site-packages/ddd/templates/` (five files); `python -m build --sdist` into the scratchpad, unpacked, its documentation tests and its docs build tried from there.
- `gh`: the CI and Documentation workflows are green on master (run 34220439120: lint, extension and the four matrix cells; run 34220439174); the v0.8.0 release ran Publish (test, build, extension, publish-pypi all success) and Documentation (success); `https://sauci.github.io/ddd/v0.8.0/` answers 200 and `versions.json` lists latest, v0.8.0, v0.7.0, v0.6.0, v0.5.0 with `stable: v0.8.0`; Pages is configured `build_type: legacy`, source `gh-pages` `/`; every release since v0.5.0 carries its `ddd-<version>.vsix`.
- `git diff v0.8.0..HEAD` on `src/ddd/ir.py`, `src/ddd/models/`, `src/ddd/diagnostics.py` and `schemas/`: empty. `DICTIONARY_FORMAT = 7` (`src/ddd/ir.py:568`).

Not covered: the docker services were not run (this machine runs Windows containers; the compose file, the image and the scripts were checked by reading, and pygraphviz's `manylinux_2_28` wheels were confirmed on PyPI so the `docs` service can install erdantic on bookworm); the language server's rename mechanics beyond its refusal message (pass 5's domain); the CANape statements of the developer page; the full test suite was not re-run here (CI ran it on master at `441c600` on both platforms, and the review baseline records the local run).

### Strengths

- The transcripts are real. `tests/test_transcripts.py` re-runs every `$ ddd` command a page runs over the shipped examples and the whole tutorial through `bash`; followed by hand, the tutorial reproduced byte for byte, error path included.
- The changelog is accurate in detail. Every command, option, identifier, refusal message and format number it names exists as described; the Unreleased section claims no format change and there is none.
- The packaging does what the pages say: the wheel carries the cmake module and the example templates under the package, the two `*-dir` commands find them after a clean install, the wheel name in the pages is the one built, `Requires-Python >=3.12` and the two runtime dependencies match the README.
- The release machinery delivered v0.8.0 exactly as `docs.yml`, `publish.yml` and the developer page describe it: docs under the tag's directory, the root redirect to the newest release, the read-back, the `.vsix` on the release, Pages served from the branch.
- The static checks, the docs build with warnings as errors and the coverage gate are all clean on master.

### Issues

#### Critical

None found.

#### Important

1. **The README tells a project with several images to opt out of header propagation on the second call only; the module and both docs pages say both.**
   - Where: `README.md:808-812` ("only one image may hand its `<image>_ddd_headers` to the components automatically - the second call has to opt out and be wired explicitly"); `docs/build_integration.rst:445-454` ("gives `NO_PROPAGATE_HEADERS` to **both** calls ... opting out of only one of the two would leave the same ambiguity in place"); `docs/faq.rst:655-661` (both calls); `cmake/Ddd.cmake:607-621` (the fatal error reads "Give NO_PROPAGATE_HEADERS to *both* ... propagating from only one of the two leaves that same ambiguity in place").
   - What: the module only refuses when *both* calls propagate (`Ddd.cmake:611-620`); a first call that propagates and a second that opts out configures without a word, and the first image's headers reach every registered component, including the ones only the second image links.
   - Why it matters: a reader following the README gets a build that configures cleanly and compiles the second image's components against the wrong headers - the `produced by <unresolved>` case the FAQ itself describes at `docs/faq.rst:647-654`.
   - Fix: rewrite `README.md:808-812` to what the module says: both calls take `NO_PROPAGATE_HEADERS` and each component links the wanted `<image>_ddd_headers` explicitly.

2. **The sdist ships tests and documentation that cannot run from it.**
   - Where: `pyproject.toml:64-79` (the include list carries `/docs` and `/tests` but not `/assets`, `/editors`, `/.github` or `/.pre-commit-hooks.yaml`); `tests/test_documentation.py:36-37` (reads `.github/workflows/docs.yml` and `ci.yml` at import), `:527,546,555,604` (`editors/vscode`), `:1254` (`.github`), `:1415` (`.pre-commit-hooks.yaml`); `docs/conf.py:58-59` (`html_logo`/`html_favicon` under `../assets/logo/`).
   - What: from the unpacked `ddd_tool-0.8.0.tar.gz`, `pytest tests/test_documentation.py` stops at collection with `FileNotFoundError: ... .github/workflows/docs.yml`, and `sphinx-build -b html docs out -W` fails with `WARNING: logo file '../assets/logo/ddd-logo-dark.svg' does not exist` and the same for the favicon (exit 1).
   - Why it matters: the sdist is the "source distribution" `docs/getting_started.rst:50-52` sends an evaluator to, and it carries the tests and the docs on purpose; whoever tries either finds them broken, and `twine check --strict` in `publish.yml:62` cannot see it.
   - Fix: add `/assets`, `/editors/vscode` (sources, `package.json`, `package-lock.json`, `LICENSE`, `icon.png`), `/.github/workflows` and `/.pre-commit-hooks.yaml` to the sdist include list - or drop `/tests` and `/docs` from it and say so in the comment at `pyproject.toml:60-63`.

3. **`data_contracts.rst` promises "the generated reference for every model" and renders 21 of the 31; ten models are rendered nowhere in the documentation.**
   - Where: `docs/data_contracts.rst:52-53` ("and the generated reference for every model"), `:183`, and the directives at `:199-288`; `src/ddd/models/__init__.py` `__all__` exports `ScalarType`, `ExternalType`, `UnitsFile`, `UnitDeclaration`, `SectionsFile`, `SectionDeclaration`, `ConstantsFile`, `ConstantDeclaration`, `RastersFile`, `RasterDeclaration`; a grep of `autopydantic_model::` over `docs/` finds none of the ten on any page.
   - What: the "Structured datatype description" section (`:217-230`) renders `TypesFile`, `StructType` and `Member` only, so the scalar and external types the FAQ (`docs/faq.rst:287-297`) and the types page build on have no field list, no schema and no diagram; four of the seven file kinds named at `:96-98` have no reference at all.
   - Why it matters: this is the page the prose pages send readers to for the exact schema of a field; for a units, sections, constants or rasters file the answer today is only `ddd schema <kind>`.
   - Fix: add `.. autopydantic_model::` directives for the ten (with `:field-show-constraints: False` where an identifier pattern would trip docutils, as the comment at `:193-197` explains), or narrow the claim at `:52-53` and say where the rest lives.

#### Minor

1. **A FAQ address-map transcript is one object stale.**
   - Where: `docs/faq.rst:506-508` shows `'AxisB', 'BlockA', 'CurveA', 'CurveB', 'FlagA' and 10 others`; the same map over the shipped demo prints `'AxisB', 'BlockA', 'CurveA', 'CurveB', 'Diagnosis.faults' and 11 others` (run here). The demo gained `Diagnosis` after the transcript was written (`CHANGELOG.md:98-109`), and because the command names `demo.ddd.json` rather than `examples/demo/demo.ddd.json`, `tests/test_transcripts.py:87-89` reads it as an illustration and does not pin it. The concept page's twin at `docs/concept.rst:409-412` is pinned and current.
   - Fix: update the line, or spell `examples/demo/demo.ddd.json` and `-t examples/templates` so the test owns it.

2. **The FAQ says the per-component cmake target uses "the same two overrides".**
   - Where: `docs/faq.rst:88-91`; `cmake/Ddd.cmake:247` (`check "${description}" --standalone`); `docs/build_integration.rst:53`; `CHANGELOG.md:119-123` ("instead of naming two checks by hand").
   - Fix: "wires exactly this invocation, `ddd check --standalone`, into the `<target>.ddd` target".

3. **The README omits `--without`, the option the changelog names as the migration path, and `TEMPLATES`.**
   - Where: `README.md:660-668` lists the artefacts and "Useful ones: `--dry-run`, `--force`, `--byte-order big`, `--address-map`"; `CHANGELOG.md:45-55` ("should become `ddd generate all --without a2l` if the project names a plugin"); `docs/command_line_interface.rst:109-116` documents it. `README.md:867-870` names `CDEFS`, `GENFLAGS`, `CFLAGS`, `CC` and `INCLUDES` but not `TEMPLATES`, which `docker/compile.sh:11,25` takes and `docs/developer_documentation.rst:318-319` documents.
   - Fix: add both.

4. **The developer page's "Adding an output format" names a tuple that is now derived, says the cmake module generates "all or c", and the module docstring it builds on says "nothing else has to change".**
   - Where: `docs/developer_documentation.rst:176-179` ("Add the name to `BUILT_IN_ARTEFACTS` in `src/ddd/plugins.py`") vs `src/ddd/plugins.py:40-45` (`BUILT_IN_GENERATED = ("c", "a2l")`, `BUILT_IN_ARTEFACTS = (*BUILT_IN_GENERATED, "all")`), `src/ddd/cli.py:469` (`--without` choices from `BUILT_IN_GENERATED`) and `:1047` (`ddd artefacts` lists it); `docs/developer_documentation.rst:185-187` ("`cmake/Ddd.cmake` keeps generating `all` or `c`") vs `cmake/Ddd.cmake:467-473` (`set(artefact all)`, `NO_A2L` appends `--without a2l`); `src/ddd/backends/base.py:6-8` ("adding it to the list `_command_generate` assembles in `ddd.cli`. Nothing else has to change") vs the four steps on the page.
   - Fix: name `BUILT_IN_GENERATED`; say the module always asks for `all` and a new built-in artefact is produced until `--without` leaves it out; point the docstring at the page.

5. **Two Unreleased entries describe successive states of the same script, the later one superseding the earlier.**
   - Where: `CHANGELOG.md:111-115` ("`ddd-compile` counts a structured variable as the one symbol it is ... read ... `ddd list --format json` ... it now takes the instance") and `CHANGELOG.md:70-75` ("It now reads `ddd dump`"); `docker/verify_symbols.py:6,32` reads the dump's `objects` and `instances`.
   - Fix: one entry stating the shipped behaviour.

6. **The changelog header's definition of the public interface is narrower than what the changelog itself treats as interface.**
   - Where: `CHANGELOG.md:7-9` (check identifiers, command names, json file formats; "anything else ... is not") and `README.md:42-43`; migration notes are nevertheless written for command options (`CHANGELOG.md:289-291`), for cmake options (`:42-43`, `:53-55`), for the `--renames` file (`:196-199`) and for the template model (`:303-311`); `docs/developer_documentation.rst:53` calls the template naming rules "part of the interface a project depends on".
   - Fix: extend the sentence to the command options, the `ddd_generate`/`ddd_add_component` signatures, the template model, and the `--renames` and `ddd-build.json` formats.

7. **The version is spelled in thirteen places across the pages and only some are pinned; the release section does not list them.**
   - Where: pinned - `pyproject.toml:11`, `src/ddd/__init__.py:16`, `editors/vscode/package.json` (`tests/test_documentation.py:517-529`), `docs/getting_started.rst:39,57` (the transcript test); not pinned - the wheel file name at `README.md:53` and `docs/getting_started.rst:29`, the banners at `docs/getting_started.rst:399,433,466`, `docs/generated_artefacts.rst:134,516,592,599`, `docs/faq.rst:572`, `docs/templates.rst:180`. The release commit `5b84aad` touched all of them by hand; `docs/developer_documentation.rst:436-501` ("Publishing a release") does not say where the version lives.
   - Fix: a sentence in that section, or a test asserting the pages' wheel name and banners carry `__version__`.

8. **The developer page describes an environment rule the repository's environments do not carry.**
   - Where: `docs/developer_documentation.rst:494-501` ("GitHub creates an environment with its deployments restricted to the default branch ... choose *Selected branches and tags* for each and add a tag rule for `v*`"); `gh api repos/Sauci/ddd/environments` reports `deployment_branch_policy: null` (no restriction) for both `pypi` and `testpypi`, and the v0.8.0 release deployed to `pypi` from its tag with that setting.
   - Fix: describe the state the repository is in; the page is the only record of a setting that lives outside the files.

9. **The Dockerfile installs cmake and ninja twice since the dev requirements gained them.**
   - Where: `docker/Dockerfile:38` (`ninja-build` from apt), `:43-45` (`pip install "cmake>=3.30"`, "the current release comes from pypi"), `:55` (`pip install ".[dev]"`); `requirements-dev.txt:8-13` (`cmake>=3.30`, `ninja>=1.11`, added with `tests/test_cmake.py`). Harmless, but the comment at `:43-44` now explains a step `.[dev]` repeats.
   - Fix: drop `:43-45` and `ninja-build`, move the comment to the `.[dev]` line.

10. **The demo's own description overstates it.**
    - Where: `examples/demo/demo.ddd.json:5` "Demonstration project showing every DDD feature"; the demo uses no units, sections, constants or rasters file (`examples/vocabulary` does) and no plugin (`examples/layout` does). `docs/getting_started.rst:63` says it accurately: "exercises every kind of data object DDD knows".
    - Fix: "showing every kind of data object".

11. **The developer page names four documentation-guarding suites and leaves out the transcript test the README names.**
    - Where: `docs/developer_documentation.rst:263-273` vs `README.md:898-908` and `tests/test_transcripts.py:1-7`; the transcript test is the stronger of the two guards.
    - Fix: one sentence.

### Changelog audit

**Unreleased**

- Renaming a type or a constant from the editor - verified in part: `renameable_at` in `src/ddd/lsp/server.py`, the refusal "spells a base datatype, which a declared type may not be called" at `src/ddd/lsp/navigation.py:433`; the edit mechanics are pass 5's domain.
- Plugins in the build - verified: `ddd sources examples/layout/project.ddd.json` lists `examples/plugins/ddd_layout.py` after the two description files; `ddd generate all --dry-run` lists `ddd_layout.h` after the built-in files; `cmake/Ddd.cmake:355-369` takes `PLUGINS`, `:535` depends on `plugin_files`, `PLUGINS` beside `PROJECT` is refused (`tests/test_cmake.py:335-358`).
- Compile usage travels with `<image>_ddd_headers` - verified: `cmake/Ddd.cmake:571-575` sets the include directories, definitions and options `INTERFACE` on `_ddd_headers` (the diff from v0.8.0 shows them moving off `_ddd_globals PRIVATE`).
- `NO_A2L` / `--without c|a2l` - verified: `--without c --without a2l` is refused with "this run would write nothing ... this project provides none", exit 2; `cmake/Ddd.cmake:470-473`.
- `ddd artefacts` - verified: text and json output, `--plugin` form, `plugins_without_artefact` in the json.
- A structure DDD only carries - verified: `docker/compile.sh:53` runs `ddd dump --format json`, `docker/verify_symbols.py:32` counts objects and instances; the demo dumps 20 objects and 1 instance, which matches the README's "20 of 21 declared variables".
- `--without` subtracts the options - verified: "`--address-map` belongs to the a2l artefact, left out by `--without`" (exit 2), the same for `--byte-order`; `--without c` runs without `-t` and writes the a2l alone.
- Refusal before the gate - verified: the inconsistent project gets the same usage error, not its findings.
- `ddd-compile` finds the headers - verified by reading `docker/compile.sh:32-42` (the walk up to `include/`, `INCLUDES` appended, the derived path kept as one element); not run.
- `NO_A2L` and the address map - verified: `cmake/Ddd.cmake:483` guards the dependency with `NOT arg_NO_A2L`.
- The demo declares an external type - verified: `examples/demo/components/sensor_hub.ddd.json` (`DriverState_t`, `SensorDiagnosis_t`, `Diagnosis`), `examples/demo/include/sensor_hub_driver.h`, `ddd list` shows `Diagnosis.faults` only, `examples/cmake/CMakeLists.txt:37-39` publishes the directory from `sensor_hub`, `tests/test_cmake.py:238-280` builds it.
- `ddd-compile` counts a structured variable as one symbol - superseded by the `ddd dump` entry above (Minor 5).

**0.8.0**

- `--standalone` - verified (`ok: 12 variables in 1 component are consistent`; `cmake/Ddd.cmake:247`); an empty address map raises no `address-missing` - verified.
- Published schemas accept the shorthands, `anyOf` for the conversion - verified through `tests/test_documentation.py:840-930` and the page; the examples carry identities - verified; the transcripts are re-run - verified.
- Quick fixes on `limits` - not re-tested (pass 5).
- Fixes from a whole-project review - spot-checked: the section pattern `^[A-Za-z0-9_.$]+$` (`schemas/ddd_sections.schema.json:24`); `ddd id --assign` fills an explicit `"id": null` and keeps a CRLF file's and a mixed file's endings (tested by byte count: 18 CR before and after; the inserted line follows its neighbour's ending); a plugin named `c`, `a2l` or `all` is refused (`src/ddd/plugins.py:116`); the cmake module passes the a2l options only when the a2l is generated (`cmake/Ddd.cmake:483`); the example plugin reports a key claimed twice in a baseline and honours a condition (`examples/plugins/ddd_layout.py:135-160,254-259`). The a2l, comparison and language-server items are passes 3-5's domain.
- Plugins - verified: the five checks are in `ddd checks`; `--plugin` on `schema`, `compare` and `checks`; `DICTIONARY_FORMAT = 7`; the example plugin.
- `id` - verified: `duplicate-id`, `consumer-identity`, `missing-id` registered; `ddd id --assign` writes and is idempotent (`wrote 2 ids`, then `wrote 0 ids`); the README's "twelve lowercase base32 characters" agrees.
- `ddd id --assign FILE...` - verified.
- `ddd compare --renames PATH` - the option is there; its output is pass 3's.

**Version and format.** `0.8.0` in `pyproject.toml`, `src/ddd/__init__.py` and `editors/vscode/package.json`; `DICTIONARY_FORMAT = 7` and nothing in `ir.py`, the models or the schemas changed since `v0.8.0`, so the Unreleased section is right to claim no format bump. It adds a command and an option, which is a minor-version change at the next release.

**Changes since `v0.8.0` the changelog does not record.** The source changes are all covered (`loading.py`'s `plugin_paths` is the `ddd sources` entry, `plugins.py`'s `plugin_source`/`BUILT_IN_GENERATED` are internal, the lsp change is the rename entry, `cli.py` is `artefacts` and `--without`). Not recorded, and not public interface by the header's definition: the three `examples/pressure` deliveries the comparison page and the README now rely on (`034a395`), `tests/test_cmake.py` with `cmake` and `ninja` in the dev requirements (`5e4f912`), and the review document. Nothing the header's definition requires is missing.

### Untracked follow-ups from the planning documents

Issues are disabled on the repository (`gh issue list`: "has disabled issues"), so nothing outside these documents tracks them:

- `docs/superpowers/specs/2026-09-02-xcp-measurement-rasters-design.md:386-394`: the module-level `DAQ` block (a `daq` key beside `rasters`); `FIXED_EVENT_LIST`; several rasters per variable.
- `docs/superpowers/specs/2026-09-03-object-identity-design.md:374-386`: member renames (an id on a type's member - `docs/superpowers/plans/2026-09-03-object-identity.md:961` calls it a known gap); `ddd id --verify`; renames across a merge of two projects (`duplicate-id` says nothing about which is the original).
- `docs/superpowers/specs/2026-09-04-plugins-design.md:432-452`: extension blocks on a component, member, section or raster; blocks stated by a consumer; a block on a leaf; entry-point discovery; language-server features for a block; positions in the dictionary. "Plugin backends under `all`" in the same list is now done (Unreleased) but still listed as deferred, and the status line at `:4` still says "approved design, not yet implemented" although 0.8.0 shipped it.
- `docs/superpowers/specs/2026-09-05-plugins-in-the-build-design.md:153-157`: declaring a plugin's artefacts as build outputs (via `--dry-run --format json` at configure time); a per-build `PLUGIN_ARTEFACTS` selection. Its status line (`:4`) also says "not yet implemented" although PR #11 merged it, and its section 2 (`:36-38`) says CMake is not run in CI while `tests/test_cmake.py` now does.

### Assessment

The pages of this pass hold up almost sentence for sentence: the tutorial reproduces exactly, the FAQ's answers are true today with one stale number, the developer page describes the repository as it is, and the changelog is reliable in every detail I could exercise; the static checks, the docs build and the release machinery are all clean and did what they promise for v0.8.0. What remains is at the edges - a README paragraph that contradicts the module it summarises, an sdist whose shipped tests and docs cannot run, a reference page missing a third of its models, and a handful of sentences the last three features left behind.

## Pass 7: code review of the core

### Scope covered

**Read in full:** `src/ddd/loading.py`, `analysis.py`, `ir.py`, `compare.py`, `identity.py`, `diagnostics.py`, every file of `src/ddd/models/`. Read as far as the core reaches into them: `cli.py` (`main`, `check`, `compare`, `id`, `_analyze`, `_read_dictionary`, `_read_baseline`, `_holds_a_description`), `lsp/ranges.py` (`Document`, `_Scanner`, which `ddd id --assign` relies on), `plugins.resolve_blocks`/`settings_of`, and the two backend copies of rules the analysis also implements (`backends/c/model.py` alignment, `backends/a2l/model.py` export closure). Tests: `conftest.py` and `test_loading.py` in full; `test_analysis.py`, `test_constants.py`, `test_structures.py`, `test_edge_cases.py`, `test_models.py`, `test_hardening.py` in the sections that bear on the findings; `test_compare.py`, `test_types.py`, `test_comparison_tables.py` by structure and names; `test_calibration.py`, `test_external.py`, `test_rasters.py`, `test_sections.py`, `test_units.py` only counted. The suite (1910 tests) was not re-run in full; the 12 reproductions in `test_pass7.py` were run and fail as expected (each failure is a confirmed finding).

**Adversarial inputs** (about 150 cases; the outcome class is the CLI's, run in-process through `ddd.cli.main`):

- *Finding, correctly located:* `interface` a string; `dimensions` entry float / negative / zero / `1e3` / `true` / `"8"`; `size` naming an undeclared constant; two projects including each other through wildcards (`include-cycle`); `bits` 0 / 65 / on `boolean` / on `float32`; limits `min > max`, `"NaN"`, bare `NaN`, `1e400`, a 5000-digit integer (digit limit); `init` list on a scalar, wrong depth, `-0.0` (the known "fractional" wording), a 400-digit integer on `float64`, `2**64` on `uint64`, 400-deep nesting, 5000-deep nesting; `id` uppercase / 11 chars / unicode / containing `i`; enumerator value float / empty mapping / `2**63`; `condition` with `\f#` or `U+2028#`; name of 129 code points, `aé`, `"x\n"`; raster cycle `0ms` / `-1ms` / `1e-12s` / `1.5ms`, two rasters on one event; section alignment 3 / 0; unit with a zero-width space (with a "did you mean"), a lone surrogate; empty file, BOM-only file, UTF-16 file, a directory named `d.ddd.json` in `includes`, `""` include, NUL in an include, a 300-character include name, duplicate keys, `UINT8` as datatype and as typename, an axis whose `input` is itself, a curve whose `axis` is itself, `plugins: [1]`, `extensions: {"x": 1}`, `local` vs `output` of one name; dumped dictionary with `format: 8`, `objects: "x"`, an extra key, `shape: [0]`, an unknown datatype, reversed or NaN limits, a non-identifier name; a directory as baseline; `ddd id --assign` on a file with a trailing comma and on a directory (skipped with a message).
- *Silent / accepted:* a project including itself through `*.ddd.json` (correctly excluded); 300 and 450 nested includes; a 400-deep chain of nested structures; `bits: 64` on `uint64`; **`init: "1"`, `init: "yes"`, `init: "1.5"` on `float32`, `volatile: "yes"` / `1` / `"true"` / `"off"`, `a2l.export: "no"` / `"0"`, `limits: {"min": "0", "max": "10"}`, `factor: "0.5"`, `bits: "3"`** (Important 6); a scalar `init` over `dimensions: [1000000000]` (`check` passes; `generate c` did not finish in 60 s, backend `broadcast`); an enum of 10 000 enumerators; `condition` unbalanced (`defined(X`), a keyword, a trailing backslash (the spec only forbids line breaks, `#` and comment tokens); a 128-code-point name; a component whose `name` differs from the file stem; `x` and `X` (`name-similar`); units `µV` (U+00B5) and `μV` (U+03BC) as two distinct entries; a NUL in a description; a constant of `2**64` as a plain array dimension; a glob matching a directory (skipped); `../`, `**/`, `C.DDD.JSON`, `./c.ddd.json`, `sub/../c.ddd.json` and `C:c.ddd.json` include spellings (all resolve to one file, loaded once); dictionary with `format: "7"` / `0` / `-3` / `7.0`, two objects with one name, one id on two objects (degrades to name pairing as designed), no `objects` key, a declaration naming an object that does not exist, `format: 3` without `dimensions`, an `init` not matching `shape`, a leaf whose `instance` is not a prefix of its `path`, duplicate keys; `ddd id --assign` on a file with a BOM, CRLF, tabs, `component` key last, `"id": null`, a one-line file, run twice (BOM, line endings and indentation preserved in every case, second run writes 0).
- *Usage error where a finding was due:* a top-level key `²` in a project or component file (`ddd: invalid literal for int() with base 10: '²'`, every finding of the run lost; Important 4); a dictionary containing a 5000-digit integer; a non-UTF-8 dictionary as baseline or candidate; `ddd id --assign` on a read-only file (aborts the whole batch).
- *Traceback:* 500 or more nested project includes (`RecursionError`); a chain of 500 or more nested structures (`RecursionError`); a 400-digit integer as a limit on a definition or on a structure member (`OverflowError`); a 400-digit enumerator value on a definition, a member or a scalar type (`OverflowError`); an array of structures of `[100000, 1000]` elements or dimensioned by a constant of `2**40` (`MemoryError`); a 100 000-deep JSON document given as a baseline, as a compare candidate, or to `ddd id --assign` (`RecursionError`).

**Performance** (`perf.py`; synthetic project mixing scalar types, enums, structured arrays over a constant, parameters in a section, axes, curves, value blocks, two consumers per measurement, conditions; components = objects / 10; wall clock including ~0.6 s of interpreter start-up):

| objects | components | `ddd check` | `ddd dump` (size) | `compare` dump vs dump | `compare` dump vs tree |
| --- | --- | --- | --- | --- | --- |
| 500 | 50 | 0.80 s | 0.72 s (1.4 MB) | 0.78 s | 0.81 s |
| 2000 | 200 | 3.39 s | 1.25 s (5.5 MB) | 1.22 s | 1.46 s |
| 5000 | 500 | 6.13 s | 2.24 s (13.7 MB) | 2.35 s | 2.98 s |

Linear in the number of objects; the target of a few seconds at 5000 is met. The one cliff is arrays of structures: a structure of 200 members, each an array of 1000 of a two-member structure (400 000 leaves) takes 16.4 s to check, 20.9 s to dump into a 271 MB file, and 50 s to compare against itself; ten times more elements is a `MemoryError` (Important 5).

**Not covered:** symlink loops under `**` (no privilege to create symlinks on this host), POSIX path behaviour (Windows host only; the case-insensitive dedupe was verified here, the case-sensitive side only by reading), the backends and the language server beyond the points named above, the plugin loader.

### Strengths

- The loader keeps its promise that every failure is a located finding: NUL bytes, directories, non-UTF-8, BOMs, duplicate keys, the 4300-digit limit, deep nesting, unreadable and vanished files all come back as `json-syntax` / `file-not-found` / `file-kind` with a pointer (`loading.py:546-584`, `1037-1076`), and `_meaningful` / `_one_per_place` keep one mistake at one finding.
- The contract catches the cheap mistakes where they are typed: `Dimension` strict so `"8"` stays a string, NaN and infinity refused everywhere a number is read, the `condition` injection guard, the id alphabet, storage named exactly once, restating a named type refused, the enum-on-integer rule shared across definition, member and scalar type.
- `ddd id --assign` is careful: raw bytes in, raw bytes out, BOM, CRLF, tabs and one-line files preserved, `null` replaced in place, idempotent, unreadable files skipped with a message.
- Determinism is designed in, not hoped for: names, enums, leaves, consumers, plugins and glob matches are sorted; the enum variant chosen does not depend on include order; the Windows case-insensitive path comparison makes `C.DDD.JSON` and `c.ddd.json` one file.
- `compare` degrades safely on a hand-edited baseline: a colliding id falls back to name pairing rather than dropping an object; a pre-format-4 baseline compares by values only.
- Throughput is linear and comfortably inside budget.
- The tests are behaviour tests against real files with almost no mocking; `test_comparison_tables.py` guards both field tables against silently falling behind the models.

### Issues

#### Critical

None. Nothing I could construct made the tool misjudge a realistic project, corrupt a file, or produce a different answer on two runs. The closest candidates are Important 1 (a false error in a second file after a real one) and Important 6 (the loader accepting what the published schema refuses).

#### Important

1. **A dropped declaration makes the ownership checks lie about the other components.**
   - Where: `analysis.py:1476` and `1486` (a declaration whose type or constant did not resolve is left out of `_refs`), `analysis.py:1758-1765` (`missing-producer`), `analysis.py:1860-1869` (`unused-output`).
   - What: with `A` producing `x` as `typename: "Nope_t"` and `B` reading `x`, the run reports `unknown-type` at `a.ddd.json` and then `error[missing-producer]: 'x' is read by component 'B' but no component declares it as output` at `b.ddd.json` (`cases/producer_dropped_unknown_type`). The second statement is false: A declares it as output. With `-W unknown-type=ignore` the false error is all that remains beside the `incomplete-project` info. The mirror case, a consumer dropped for an unknown constant, produces `warning[unused-output]: 'x' is written by component 'A' but read by nobody` (`cases/consumer_dropped_unknown_constant`). Same root as the already-found `incomplete-project` gaps: the drop erases the declaration from every census, not only from resolution. Reproduced by `test_pass7.py::TestDroppedDeclarationsDoNotInventFindings` (both fail).
   - Why it matters: the false finding points at a file another team owns and tells them to add a producer that exists; when the real cause is relaxed it is the only error left. No test covers a dropped declaration with a surviving counterpart in another component (all drop tests use one component with `local` scopes).
   - Fix: keep dropped declarations in `_refs` marked unresolved (a `DeclarationRef.unresolved: bool` or a parallel `self._dropped_refs: dict[str, list[DeclarationRef]]`), exclude them from resolution and from `kept`, but let `_select_producer` and `_check_unused` see them: a dropped producer means "not a missing producer", a dropped consumer means "not unused". Then `_unresolved` and the `incomplete-project` reporting can read the same structure.

2. **Integers beyond the float range crash the run with `OverflowError`.**
   - Where: `analysis.py:2256-2261` (`_below`/`_above` call `math.isclose`, which converts to float), `models/conversion.py:220-222` (`physical_range` calls `float(min(values))` on enumerator values). Contract side: `Limits.min/max` are `Number = int | Real` (`models/objects.py:79-96`, `common.py:266`) and `Enumerator.value` is an unbounded strict int (`conversion.py:45`); Python's JSON reader accepts up to 4300 digits.
   - What: `"limits": {"min": 0, "max": <309+ digits>}` on a definition or a member, or such an enumerator value on a definition, a member or a scalar type, ends `ddd check` with a traceback (`cases/limits_bigint_400digits`, `limits_bigint_member`, `enum_value_10pow400`, `enum_on_member_10pow400`, `scalar_type_enum_10pow400`; `test_pass7.py::TestBigIntegersDoNotCrash`). A 20-digit value like `2**64` is handled correctly.
   - Why it matters: unlikely to be typed, but it is a traceback from validated input, and it reaches the language server on every keystroke of such a file.
   - Fix: bound the two contracts to what any datatype could hold, `Field(strict=True, ge=-(2**63), le=2**64 - 1)` on `Enumerator.value` and on the integer side of `Number`; nothing DDD can store lies outside, the spec's tighter bounds still apply as `init-invalid` / `limits-out-of-range`, and every later `float()` becomes safe. Add the two reproductions.

3. **Recursion depth is unbounded in three places and only one reader guards it.**
   - Where: `loading.py:811-838` ↔ `995-1029` (`_load_project` / `_load_include` recurse once per include level, about three frames each plus pydantic's); `analysis.py:384-408` (`_nesting_cycle`), `979-993` (`_members_resolve`), `861-875`, `831-859`, `335-364`, `1937-1997` (every walk over nested structures recurses); `loading.py:436-438` (`_dictionary_format_is_supported` catches `ValueError` only), `cli.py:1223-1227` (`_holds_a_description`), `lsp/ranges.py:46-48` (`Document.__init__`), whereas `_read_json` does catch `RecursionError` (`loading.py:568`).
   - What: 450 nested includes load, 500 crash (`RecursionError` inside pathlib); 400 nested structures resolve, 500 crash inside `_nested_types`; a 100 000-deep JSON document is refused as `json-syntax` by `ddd check` but tracebacks as a baseline, as a compare candidate and under `ddd id --assign` (`cases/nested_includes_500`, `type_chain_probe`, `roundtrip/deep.json`, `id_assign/deep.ddd.json`; `test_pass7.py::TestRecursionIsBounded`).
   - Why it matters: none of these is a plausible project, but a fuzzed or corrupted archive reaching `ddd compare` in CI should fail with a finding, and the two walks over structures have no natural bound today.
   - Fix: one `read_json_text` helper shared by the four readers, catching `(ValueError, RecursionError)`; an explicit stack in `_load_include` (or a depth cap reported as `include-cycle`-style finding); a nesting-depth cap in `_check_types` (64 is generous for C) reported as a located finding, after which the recursive walks are safe.

4. **A JSON key made of non-decimal digits breaks the sorting of every report.**
   - Where: `diagnostics.py:273-286`, line 283: `int(part)` is guarded by `part.isdigit()`, which is true for `²`, `³`, `①`… while `int()` accepts only decimal digits.
   - What: a component or project file with a top-level key `"²"` yields one `schema` finding; sorting it in `bag.sorted` raises `ValueError`, `main` prints `ddd: invalid literal for int() with base 10: '²'` and exits 2 with **no finding printed** (`cases/toplevel_key_superscript2`, `project_key_superscript2`; `test_pass7.py::TestPointerOrder`). The same sort runs in the JSON output, in `_read_baseline` and in the language server (`lsp/diagnostics.py:135`), where the request fails instead of underlining the key. Any pointer whose first segment is such a key triggers it; a key nested deeper is safe only because the dotted prefix stops `isdigit()`.
   - Fix: `re.split` with a capturing group returns the indices at the odd positions; use that instead of guessing from the text: `((False, int(p)) if i % 2 else (True, p)) for i, p in enumerate(re.split(...)) if p`. Add the reproduction to `test_findings_of_one_file_are_ordered_by_declaration`'s neighbourhood.

5. **Arrays of structures are expanded element by element, without a bound.**
   - Where: `analysis.py:322-332` (`_element_paths` builds every index path), `1920-1921` and `1996-1997` (`_flatten` is called once per element, producing one `ResolvedLeaf` per element per member), `ir.py:641-647` (`leaves` is written out whole), `compare.py:301-303` (both sides expanded again).
   - What: 200 members × `[1000]` × 2 leaves (400 000 leaves) checks in 16.4 s, dumps 271 MB in 20.9 s and compares in 50 s; `dimensions: [100000, 1000]` on a structured variable, or a dimension spelled by a constant of `2**40`, ends in a `MemoryError` traceback (`cases/struct_200x1000`, `constant_2pow64_struct_array`). Nothing warns before the expansion; a plain value array of `[1000000000]` with a scalar `init` passes `check` and then hangs `generate c` in the backend's `broadcast` (`backends/c/literals.py:71`), because the IR keeps the scalar and every consumer broadcasts it.
   - Why it matters: this is the only super-linear path in the core, it is reachable by editing one number, and the failure mode is memory exhaustion rather than a finding. Large arrays of structures are not typical, but a `[64][64]` table of a 20-member structure is 80 000 leaves and already a 50 MB dump.
   - Fix: compute `math.prod(shape) * leaf_count` before flattening and refuse above a limit (say 10⁵ leaves) with a located finding; longer term, record the element shape once on the leaf (`shape` of the instance beside the member's) and let the a2l backend enumerate, which is also what would make `renamed-object` per member (already found) go away.

6. **The loader accepts quoted numbers and booleans that the published schema refuses.**
   - Where: `models/objects.py:25` (`InitValue`), `79-96` (`Limits` over `Number`), `106` (`A2lObjectOptions.export`), `360` (`volatile`), `models/conversion.py:71-75` (`factor`, `offset`), `models/types.py:147` (`bits: PositiveInt`); all under the default lax mode of `_Frozen`. Compare the five fields that are strict on purpose: `Dimension` (`objects.py:31-38`), `Enumerator.value`, `ConstantDeclaration.value`, `SectionDeclaration.alignment`, `RasterDeclaration.event`, and `tests/test_models.py:354-377` (`TestQuotedNumbers`: "The published schema says integer; a quoted number is refused where it is written").
   - What: `"init": "yes"` resolves to `"init": true` in the dump, `"init": "1"` to `1`, `"init": "1e3"` to `1000.0`, `"volatile": "off"` drops the qualifier, `"a2l": {"export": "0"}` keeps the object out of the a2l, `"limits": {"min": "0", "max": "10"}` and `"conversion": {"factor": "0.5"}` and `"bits": "3"` are all taken as numbers (`cases/init_str_yes`, `volatile_yes`, `export_no`, `limits_string`, `factor_string`; `test_pass7.py::TestQuotedValuesAreRefusedEverywhere`, six failures). The published schema (`ddd schema component`) says `boolean | integer | number | array` for `init` and `boolean` for `volatile`, so an editor bound to it flags what the build accepts, contradicting `models/schema.py`'s stated invariant that the schema and the loader cannot disagree about whether a file is valid.
   - Why it matters: the strictness argument the models make for `dimensions` ("the file would say something its author did not write") applies verbatim; `"yes"` → `1` is a wrong value, the others are silent normalisation that the schema, the LSP and the build will disagree about.
   - Fix: `ConfigDict(strict=True)` on the `_Frozen` bases of `objects.py`, `conversion.py`, `types.py` (and `ir.py`, which also accepts `"format": "7"`). Pydantic's strict mode still accepts an int where a float is annotated, the `BeforeValidator` shorthands (units, enum mapping, `kind` inference) run before the strict check, and `InitValue` keeps `bool` first. Extend `TestQuotedNumbers` with the six fields.

7. **Findings about a scalar type are anchored at keys its users do not have, once per user.**
   - Where: `analysis.py:1386-1396` (`_resolve_type` copies the type's `datatype`, `unit`, `conversion`, `limits` into the declaration), then `analysis.py:1565` → `1604-1617` (`_check_limits` reports at `ref.location("definition.limits")`) and `1567-1573` (`_register_enum` at `ref.location("definition.conversion")`).
   - What: a scalar type `Pct_t` (`uint8`, limits `[0, 300]`) named by A and B yields two `limits-out-of-range` warnings at `a.ddd.json#component.interface[0].definition.limits` and `b.ddd.json#…definition.limits`, keys neither file contains, and none at `t.ddd.json#types[0].limits` (`cases/scalar_type_limits`). A scalar type with an enum yields `reserved-identifier` and `enum-duplicate-value` at `a.ddd.json#…definition.conversion` (`cases/scalar_type_enum`); the type itself is only checked through whichever declaration sorts first, and a scalar type nobody names is not checked at all. `test_pass7.py::TestScalarTypeLimitsAreReportedAtTheType` fails.
   - Why it matters: 50 consumers of one type get 50 warnings pointing at nothing; the language server has no range to underline, so `Document._resolve` falls back to the whole definition; and the one place the author can fix it is not named.
   - Fix: check scalar types where they are declared, in `_check_types` beside `_check_member_limits` / `_register_member_enums` (the logic exists for members; add the `ScalarType` branch at `entry.location("limits")` / `entry.location("conversion")`), and skip `_check_limits` and enum registration for a `DeclarationRef` whose `resolved` came from a type. This also removes one of the two copies of the limits rule (Minor 3c).

8. **Two readers turn malformed dictionaries and descriptions into usage errors.**
   - Where: `cli.py:1217-1229` (`_holds_a_description` catches `OSError` and `JSONDecodeError`, not `UnicodeDecodeError` nor the digit-limit `ValueError`), `loading.py:429-450` and `cli.py:99-115`.
   - What: `ddd compare` with a non-UTF-8 file on either side prints `ddd: 'utf-8' codec can't decode byte 0xff…` and exits 2 without a location; a dictionary containing a 5000-digit integer likewise (`cases/roundtrip/notutf8.json`, `bigint.json`). The same inputs given to `ddd check` are proper `json-syntax` findings.
   - Fix: the shared reader of Important 3 (`_read_text` + `_read_json` already do the right thing; `_holds_a_description` should sniff through them or catch `ValueError`).

#### Minor

1. **A trailing backslash in `condition` splices the next generated line into the `#if`.** `models/component.py:58-82` refuses line breaks, `#` and comment tokens; `"condition": "defined(X) \\"` passes and is emitted as `#if defined(X) \` followed by the declaration, which the preprocessor joins into one directive. The build fails loudly rather than silently, so this is a completeness nit of the same guard: refuse a backslash at the end of the stripped text.
2. **Leaves are sorted as text, so element order is `[0], [10], [11], [1], [2]…`** (`analysis.py:548-550`, `ir.py:710`, `cli.py:1274`; `cases/leaf_order`). `ddd list`, the dump and the a2l record order all show it. A natural key that splits on `[n]` (the `_pointer_order` shape, corrected per Important 4) fixes all three.
3. **Rules implemented twice, some already diverged.** (a) Alignment: `analysis.py:831-859` returns `None` for a structure reaching an external member (no `section-alignment` finding), `backends/c/model.py:286-304` ignores the external member and answers the strictest of the rest, so the finding and the section ordering answer differently for the same structure. (b) A member's raw range: `analysis.py:2208-2213`, an inline copy at `966-970`, and `models/types.py:192-196`. (c) `limits-out-of-range`: `analysis.py:1604-1617` and `602-625`, same text, two implementations. (d) What a scalar type fixes: `analysis.py:1386-1396` (`model_copy`) and `2004-2016` (`_member_meaning`). (e) The export closure: `analysis.py:560-580` and `backends/a2l/model.py:281-300` (identical today). (f) `_condition` renders an absent condition as "no condition" in `analysis.py:2231` and as "none" in `compare.py:589`; `_describe_references` is copied verbatim (`analysis.py:83`, `compare.py:75`).
4. **`DataDictionary` validates fields but no invariant between them.** `ir.py:578-666`: two objects (or an object and a leaf) with one name collapse silently in `comparable`/`by_name` (`669-683`; `cases/roundtrip/dup_names.json` compares clean), a declaration naming an object no list carries is accepted (`component_decl_orphan.json`), an `init` that does not match `shape` is accepted (`init_wrong_shape.json`; a backend would render it as written), references to absent names are accepted, and `format` (`ir.py:588`; `loading.py:441-443` only refuses a *higher* one) accepts `"7"`, `0`, `-3`, `7.0`. The module's docstring promises that a bug in the analysis surfaces here; a few `model_validator`s (unique names across `objects`+`instances`+`leaves`, `check_shape(init, shape)`, `references ⊆ names`, `format >= 1` strict) would make that true for a hand-edited archive too.
5. **One wrong nested `init` produces one finding per nesting level** (100 for a 400-deep list; `loading.py:1099-1138` dedupes per place and every level is a place). Report only the shallowest location of a union failure under `init`.
6. **`ddd id --assign` aborts the batch on the first unwritable file.** `identity.py:182` (`write_bytes` raises `PermissionError`), not caught in `assign` (`153-183`) nor in `_command_id` (`cli.py:845-857`); `main` turns it into `ddd: [Errno 13] …` and the remaining files are not touched, unlike an unreadable file, which is skipped and named. Catch `OSError` around the write and report it like `UNREADABLE`.
7. **Under a `local`/`output` conflict the owner follows include order.** `analysis.py:1737-1767` returns `producers[0]`; including `a` before `b` gives `('x', 'A', local=True)`, the other order `('x', 'B', local=False)` (`cases/two_locals_same_name`, `local_and_output_reversed`). Only visible with `local-conflict` relaxed, but then the generated files depend on include order. Prefer the `local` declaration, or sort producers by component name.
8. **A member's `unknown-type` is located at `members[i]`** (`analysis.py:906`) while a declaration's points at `definition.typename` (`analysis.py:1349`); use `members[i].typename`.
9. **The enum registry's location moves to the better-documented variant** (`analysis.py:1639-1643`), so the "first defined as" note of a later `enum-conflict` (`1636`) can point at a declaration that was not first. Keep the first location and the best-documented conversion separately.

### Design notes

1. *Dropping versus marking.* The analysis expresses "this declaration cannot resolve" by leaving it out of `_refs`, and then four different censuses (ownership, readers, identities, similar names) and the `incomplete-project` machinery each have to remember what was left out. A `DeclarationRef` that stays in the list with an `unresolved` flag, skipped by resolution alone, would settle Important 1, the already-found `incomplete-project` gaps and the untested `duplicate-id` on a dropped producer at one edit site.
2. *Types are checked through their users.* `_resolve_type` copies a scalar type into every declaration naming it and lets the declaration checks run on the copy, which is why Important 7 happens and why an unused scalar type is never checked. Checking a type once at its declaration and treating a filled-in definition as already checked is the smaller design, and it is what structure members already get.
3. *Strict by default.* Five fields opt into strictness one by one and the rest are lax; the mismatch with the published schema (Important 6) is the visible cost. `strict=True` on the shared `_Frozen` bases, with the existing `BeforeValidator` shorthands as the deliberate lax spots, makes the contract say once what the schema already says.
4. *`_Analysis.run` carries an implicit phase order.* `_poisoned_types` must be complete before `_resolve_type`, `_effective` before `_resolve_shape`, `_check_similar_names` after collection (`analysis.py:473-558`, `1451-1501`); every field's docstring says what it is, nothing enforces when it is valid. Two or three phase objects (collected → owned → resolved), or asserts on entry, would let the next check be added without rereading `run`.
5. *The IR is the a2l's shape.* `leaves` exists so that a consumer never repeats resolution, but it also means the dictionary grows with the element count of every array of structures (Important 5) and that a scalar `init` is carried unexpanded (`ResolvedObject.init`, `ir.py:186-187`, says "nested to match shape"; the backends broadcast it themselves). Either normalise `init` in the analysis and record element shapes once, or document both as consumer obligations.

### Test review

- `tests/conftest.py:92-100` silences `missing-id` for every fixture; `tests/test_structures.py:850` relaxes `missing-producer` to generate unowned objects; `tests/test_constants.py:286-342` relax `unknown-constant` to test the relaxation itself. All three are deliberate and documented; nothing else in the listed files silences a check by default.
- `tests/test_edge_cases.py:307-321` (`test_a_map_whose_axes_are_unknown_has_no_shape`, asserting `shape == ()`) and `:324-338` (`test_a_curve_whose_axis_is_missing_is_left_out`) pin the already-found dangling-reference behaviour; they will need rewriting with that fix.
- `tests/test_models.py:354-377` (`TestQuotedNumbers`) states the rule "a quoted number is refused where it is written" and tests three of the nine numeric/boolean fields; the other six accept quoted values (Important 6).
- No test has a dropped producer with a surviving consumer or the reverse (`tests/test_constants.py:217-261`, `tests/test_structures.py:264-291` all use one component); Important 1 is untested rather than pinned.
- `tests/test_hardening.py:562` covers deep JSON for the loader only; the dictionary reader, `_holds_a_description` and `Document` have no such test (Important 3, 8). `tests/test_hardening.py:512` covers `_pointer_order` for ASCII pointers only (Important 4).
- `tests/test_analysis.py:174` (`test_fractional_init_for_an_integer`) uses `1.5`; nothing states what `1.0` does, so the known "whole float refused as fractional" issue is neither pinned nor guarded.
- About 170 assertions across the fifteen files check message text (`in messages(bag)` / `in rendered`; `test_constants.py` 25, `test_structures.py` 24, `test_hardening.py` 24, `test_analysis.py` 20). Most pin the load-bearing phrase, which is defensible since the message is the product; a few pin a whole rendered fragment (`tests/test_analysis.py:106`, `conversion: linear(factor=0.25, offset=0) != linear(factor=0.5`).
- About 220 assertions are `checks(bag) == [...]`, which pins the bag's insertion order; the promised order is `bag.sorted`. Harmless while the analysis is deterministic, but a benign reordering of `_Analysis.run` would fail a few hundred tests without any behaviour change; `sorted(checks(bag))` or a `Counter` would pin the behaviour and not the schedule.
- `tests/test_hardening.py:893-945` monkeypatch `Path.resolve`, `Path.read_text` and `Path.glob` to force OS failures; they assert on the finding text, not on the mock, which is the right use of a monkeypatch.
- The loader's OS-level cases that can be produced without mocking on this host (a directory in `includes`, a read-only file for `id --assign`, a NUL byte, `..` and `**` patterns, case-variant spellings) have no tests in `test_loading.py`; all behave correctly today (Scope), so they are cheap to pin.

### Assessment

The core is careful and, on realistic projects, correct: the contract, the loader's failure handling, the determinism and the throughput are all better than typical, and I found no wrong verdict on a project a team would plausibly write. What remains is the edge of the input space, where three families of crash (huge integers, recursion depth, per-element expansion) and one contract inconsistency (strictness) survive because each is guarded in one place and not in the others, plus two analysis habits, dropping declarations and checking types through their users, that produce findings pointing at the wrong file or at keys that do not exist. All of it is fixable locally; the two design notes on marking rather than dropping and on checking types at the type are where the next pass of bugs of this kind would stop appearing.

## Pass 8: code review of the periphery

### Scope covered

Read in full: `src/ddd/cli.py`, `__main__.py`, `plugins.py`, `examples/plugins/ddd_layout.py`, `backends/base.py`, `backends/c/{backend,model,literals,options,types}.py`, `backends/a2l/{backend,model,options,types}.py` and `templates/project.a2l.jinja`, the four shipped `examples/templates/*.jinja2` plus `_macros.jinja2`, `build_info.py`, all eight `lsp/*.py`, `cmake/Ddd.cmake`, `examples/cmake/CMakeLists.txt`, `editors/vscode/{package.json,.vscodeignore,tsconfig.json,src/*.ts}`, `docker/compile.sh`, `docker/verify_symbols.py`, `docker/Dockerfile`, `docker-compose.yml`, the spec sections named, `docs/plugins.rst` and `docs/editor_integration.rst` (for the trust boundary). Tests: `test_lsp.py` framing, discovery, collect, server and edits sections in full (lines 1-560, 1600-1740, 1860-2130, 2200-2260, 2430-3400) and the rest by test name; `test_plugins.py` fixtures, loading, backend and wire tests; `test_cli.py` generate, sources, build-info, version, templates-dir, output-directory tests; `test_cmake.py`, `test_embedded.py`, `test_transcripts.py`, `test_example_plugin.py` (header part), `test_backends.py` (error reporting), `test_generation.py` (writing), `test_a2l.py` (identifier cap, forced output). Not read line by line: the navigation and hover test bodies of `test_lsp.py` (560-1600).

Adversarial inputs tried, with the outcome class:

| input | outcome |
| --- | --- |
| `didOpen`/`initialize` with the URI VS Code sends on Windows, `file:///c%3A/...` | server exits after the first `didOpen`, "relative path can't be expressed as a file URI" (Critical 1) |
| UNC URI, `%20`, `%23`, `untitled:` URI | no crash |
| rename / prepareRename while the editor's buffer differs from the disk | edits computed from the disk (Critical 2) |
| opening a component whose sibling project file names a plugin | the plugin's module body ran (Critical 3) |
| `codeAction` with `"context": null` | server dies with AttributeError (Minor 1) |
| CRLF file, emoji before the finding on the same line | UTF-16 columns correct |
| plugin with `@dataclass` under `from __future__ import annotations` | `plugin-invalid: 'NoneType' object has no attribute '__dict__'` (Important 1) |
| plugin `backend` hook returning `None` | AttributeError traceback, exit 1 (Important 3) |
| plugin backend returning `Path("ddd_globals.c")` and `out/sub/../ddd_globals.h` | a file written into the working directory; the c backend's `ddd_globals.h` silently overwritten, exit 0 (Important 2) |
| plugin `check` hook calling `sys.exit(0)` | `ddd check` exits 0 printing nothing; the server ends (Important 5) |
| plugin importing a sibling module | `plugin-invalid: No module named 'helpers'` (Minor 7) |
| plugin path spelled in two cases on Windows | one module, correct |
| template `{{ 1 / 0 }}`, `{{ model.groups \| length + 'x' }}` | raw traceback, exit 1 (Important 3) |
| console: default, `PYTHONIOENCODING=cp1252`, `PYTHONLEGACYWINDOWSSTDIO=1`, redirected to a file | `µV`, `°C`, `Größe` printed correctly in all four |
| a unit holding a lone surrogate (the JSON escape `\ud800`) | `ddd list` exits 2 with a codec message after printing the table header (Minor 2) |
| `"init": NaN` / `Infinity` | `json-syntax` finding, refused (correct) |
| `ddd compare ... --renames <directory>` | exit 2, the comparison's findings never printed (Important 4) |
| `-o` where `ddd_globals.h` is a directory | `ddd_globals.c` written, then exit 2 (Important 6) |
| components `Sensor` and `SENSOR` | `name-collision` error; relaxed, refused on Windows by the writer (Minor 4 covers `Sensor`/`Sensor_`) |
| `examples/cmake`: configure, build, no-op rebuild, reconfigure, `sensor_hub.ddd`, `firmware_ddd_check` | all correct; components carry an order-only dependency on the generation |

Not covered: `docker/compile.sh` and `verify_symbols.py` could not be run (no Linux docker here; reviewed by reading), the extension's node tests, Python 3.12, macOS.

### Strengths

- The wire layer is bytes-first and small; a bad body is a JSON-RPC error and the loop goes on (`protocol.py`, `server.py:157-178`), and every handler field goes through `_field`.
- Every text that reaches a C comment is defused in the model, not in the templates (`c/model.py:405-411`, `_group`, `_header`), and `condition` is refused where it could inject (`models/component.py:58-82`); A2L strings go through one escaper (`a2l/model.py:613-623`) and every synthesised identifier is capped at 128 (`_unique`).
- Console output is forced to UTF-8 on both streams (`cli.py:85-102`); the check held up under every Windows console setting tried.
- `stdout` is taken away from plugins under the server (`server.py:492-502`) and the test proves it.
- The CMake module is careful in the places that usually bite: `restat`, `CONFIGURE_DEPENDS` on the templates, `DEPENDS` on the tool itself, the seeded map never overwriting a real one, multi-config refused, the transitive-property floor named.
- `test_transcripts.py` re-runs every documented command; `test_cmake.py` builds rather than reads; `test_embedded.py` proves the two homes of a type render byte-identical.

### Issues

#### Critical

1. **The server cannot decode the URIs VS Code sends on Windows, and dies on the first `didOpen`**
   - Where: `src/ddd/lsp/server.py:85-90` (`uri_to_path`), `src/ddd/lsp/server.py:482-489` (`_publish`); tests `tests/test_lsp.py:152-168`.
   - What: VS Code spells a Windows file as `file:///c%3A/git/x/a.ddd.json` (lower-case drive, colon percent-encoded). `urllib.request.url2pathname('/c%3A/git/x/a.ddd.json')` on the Python 3.13 here returns a path starting with a backslash followed by `c:` (the leading slash is kept because the drive check looks for a literal colon before unquoting), so `uri_to_path` yields `WindowsPath('/c:/git/x/a.ddd.json')`, which is not absolute and names no file. `refresh` then analyses that phantom, and `_publish` calls `path.as_uri()`, which raises `ValueError`. Run end to end (`scratchpad/pass8/lsp_e2e.py`): `ddd lsp` answers `initialize`, logs, and exits with code 2 and `ddd: relative path can't be expressed as a file URI` on stderr. The `rootUri` is mis-decoded the same way, so discovery of `build/` would not work either. Both suite tests feed `Path.as_uri()` output (`file:///C:/...`, colon literal), never the client's spelling, and `launch.test.ts` never opens a document.
   - Why it matters: with the shipped extension on Windows (the platform this repository is developed on) the server dies as soon as a file is opened; the project declares Python 3.12 and 3.13 (`pyproject.toml:14-24`).
   - Fix: stop relying on `url2pathname` for the drive: `path = unquote(parsed.path)`; on Windows, if it matches `^/[A-Za-z]:` strip the leading slash; keep the UNC branch. Add the client spellings (`c%3A`, `C%3A`, `C:`) to `TestRanges`, and make `launch.test.ts` open a document.

2. **Rename and quick-fix edits are computed against the disk while the client applies them to its buffer**
   - Where: `src/ddd/lsp/server.py:212-216` (`_document` reads only `uri`; `didOpen`'s `text`/`version` are dropped), `server.py:412-414` and `449-451` (`read(path, cache)` from disk), `src/ddd/lsp/navigation.py:450-464` (`rename_edits`), `src/ddd/lsp/edits.py:167-246`; capability `change: 0` at `server.py:472`, and the `WorkspaceEdit` is the unversioned `changes` form (`server.py:440`).
   - What: `scratchpad/pass8/lsp_probe.py` (E14): the disk names the object `Speed` on line 7; the `didOpen` carries a buffer with one extra line at the top and the name `Velocity`. `prepareRename` at the buffer's position answers `null`; `rename` answers edits at line 7, columns 19-24 of both files. A client applies those to its buffers unchecked (no `documentChanges` + `version`), so in a dirty buffer the five characters of an unrelated line are replaced. The same holds for every reconcile action and the `missing-id` fix: a dirty `a.ddd.json` receiving the other half of a rename started in a saved `b.ddd.json` is corrupted, and an edit on the same line after the name defeats the `prepareRename` safety net.
   - Why it matters: F2 in one file while another mentioning the object is unsaved is an ordinary editing session; the outcome is a silently corrupted description file. The spec's "reads from disk at open and save" is about the analysis; it says nothing that licenses editing from stale text.
   - Fix: keep a document store: accept full-content `didChange` (`change: 1`) and `didOpen`'s `text`, keep the latest text per URI, and make `read()` consult it before the disk for positions and edits (the analysis can still run only on open and save). Return `documentChanges` with the known `version` so that a client refuses a stale edit. Add a server test that opens a buffer differing from the disk.

3. **Opening a description file in the editor executes Python from the repository, and nothing tells the user**
   - Where: `src/ddd/lsp/navigation.py:214-249` (`containing_projects` loads every `*.ddd.json` from the file's directory up to the workspace root through `_includes` -> `load_workspace`), `navigation.py:193-197` and `src/ddd/lsp/diagnostics.py:103-106` (every build record's project is loaded, wherever the record points), `src/ddd/loading.py:867-877` (`_load_plugin` -> `load_plugin`, i.e. `exec_module`); `docs/editor_integration.rst`, `editors/vscode/README.md`, `SPEC.md:943-1022`, `docs/plugins.rst:159-171` contain no mention of it (grep for plugin/trust/execute in the two editor documents returns nothing).
   - What: `scratchpad/pass8/cases/e50_trust`: a project file naming `evil.py` sits beside `sub/x.ddd.json`; opening `sub/x.ddd.json` (which names no plugin) ran `evil.py`'s module body. The extension activates on any JSON file (`package.json:33-36`, known) so cloning a repository and opening one `*.ddd.json` is enough; there is no confirmation, allowlist or `workspace.isTrusted` check anywhere in `extension.ts`.
   - Why it matters: this is exactly the "an undocumented execution of repository code where a user would not expect it" of the calibration. The CLI has the same boundary, but there the user typed the project's name; the editor loads files the user did not open.
   - Fix: state the boundary in `docs/editor_integration.rst`, the extension README and SPEC 3.11 ("naming a plugin runs it, and the server runs a workspace's plugins when a file is opened"); gate the extension on `vscode.workspace.isTrusted` (`capabilities.untrustedWorkspaces` in `package.json`) and have the server refuse plugins unless the client says the workspace is trusted (an `initializationOptions` flag, defaulting to off for unknown clients).

#### Important

1. **A plugin module runs before it is in `sys.modules`, so a `@dataclass` (and any forward reference through the module) breaks it**
   - Where: `src/ddd/plugins.py:192-200`.
   - What: `exec_module` runs first and `sys.modules[name] = module` happens after. `dataclasses._is_type` does `sys.modules.get(cls.__module__).__dict__` for every string annotation, so a plugin with `from __future__ import annotations` (the very first line of the shipped example) and one `@dataclass` fails: `plugin-invalid: plugin 'plug.py' failed to import: 'NoneType' object has no attribute '__dict__'` (`cases/e1_dataclass`). Anything else that looks a class's module up by name (pydantic forward references to a later class, `typing.get_type_hints`, `pickle`) has the same hole.
   - Why it matters: the message is unrelated to the cause and the idiom is ordinary.
   - Fix: the importlib recipe: register before executing and remove on failure (`sys.modules[name] = module; try: exec_module ... except: sys.modules.pop(name, None); raise`).

2. **"Two artefacts claiming one path" is decided on the spelling, not the path, and nothing keeps a backend inside `-o`**
   - Where: `src/ddd/backends/base.py:100-120` (`produced_by.get(file.path)`), `base.py:123-137` (writes wherever the path says); SPEC 3.11 promises the refusal "before anything is written".
   - What: `cases/e2b_backend_relative`: a backend returning `output_dir / "sub" / ".." / "ddd_globals.h"` overwrote the c backend's `ddd_globals.h` (`wrote out/sub/../ddd_globals.h (updated)`, exit 0), and one returning `Path("ddd_globals.c")` wrote a file into the current working directory. `_GuardedBackend` (`plugins.py:341-363`) guards exceptions only.
   - Why it matters: a plugin defect silently replaces a built-in artefact and the build sees a clean run.
   - Fix: in `render`, normalise every returned path (`Path(os.path.normpath(output_dir / path))` for relative ones, `resolve()` for the comparison), refuse a path outside `output_dir`, and compare the normalised form.

3. **Exceptions a template or a plugin factory can raise escape as tracebacks with the findings exit code**
   - Where: `src/ddd/backends/base.py:168-174` (only `TemplateError` is caught), `src/ddd/plugins.py:337-338` and `355` (`backend.name` and `render`'s iteration of the factory's result sit outside `_call`), `src/ddd/cli.py:106-114` (`main` catches three exception types).
   - What: `{{ 1 / 0 }}` -> `ZeroDivisionError`, `{{ model.groups | length + 'x' }}` -> `TypeError`, a `backend` hook returning `None` -> `AttributeError`, a `generate` returning something not iterable -> `TypeError`; all four end in a Python traceback and exit status 1, which is `EXIT_FINDINGS`.
   - Why it matters: a CI job reading the exit code cannot tell a crash from findings, and the author of a template gets the one message the code went to lengths to avoid.
   - Fix: catch `Exception` in `render_template` and report it through `describe_template_error` (it is the template's code that raised); validate the factory's result with the runtime-checkable `Backend` protocol inside `_call` and check that `generate` returned a list of `GeneratedFile`; give `main` a last-resort `except Exception` that prints one line and returns a code distinct from 1 and 2 (3, say) so a crash is never a "findings" exit.

4. **The run's findings are discarded whenever a step after the analysis fails**
   - Where: `src/ddd/cli.py:603-609` (`--renames` written before `_report`), `cli.py:729` (`load_address_map`), `cli.py:772-779` (`render`, `write`), `cli.py:781-788` (`_report` last); the known "plugin hook that raises discards findings" is the same defect.
   - What: `ddd compare ... --renames <directory>` printed only `ddd: [Errno 13] Permission denied: '...cases'` (exit 2) and none of the comparison's findings; a template failure hid the `missing-id` finding that the same project prints with a working template (`cases/e3b_template_type`, both runs in the transcript); an unreadable address map or an unwritable output directory does the same.
   - Why it matters: the one run that fails is the one whose findings the reader needs; and the `--renames` message does not even name the option.
   - Fix: report the findings before the fallible output steps (or in a `finally`), and prefix the I/O errors with what was being written (`cannot write --renames file '...'`).

5. **`sys.exit` inside a hook is a clean run on the command line and the end of the language server**
   - Where: `src/ddd/plugins.py:366-371` (`except Exception`), `src/ddd/lsp/diagnostics.py:76-82` (catches `PluginError` only), `src/ddd/lsp/server.py:157-178`.
   - What: `cases/e10_sysexit`: a `check` hook calling `sys.exit(0)` makes `ddd check` exit 0 with nothing printed, although the project has an error finding (`Nobody` has no producer); under `ddd generate` it exits 0 without writing. In the server, `SystemExit` escapes `run()` after the `initialize` answer (`lsp_probe`, 708 bytes written), so the client sees the server vanish.
   - Why it matters: an error path written as a script would write it (`sys.exit("...")` is at least exit 1 with a message; a bare `exit()` is exit 0) turns into a clean build.
   - Fix: catch `BaseException` minus `KeyboardInterrupt` in `_call` (`except (Exception, SystemExit)`), and treat it as `PluginError`.

6. **Generation is not atomic: a failing write leaves the earlier artefacts updated and names the wrong thing**
   - Where: `src/ddd/backends/base.py:123-137`, `src/ddd/cli.py:773-779`.
   - What: with `out/ddd_globals.h` a directory, `ddd_globals.c` was created, then `cannot write into '.../out': Permission denied` (exit 2): the message names the directory although the directory is fine and the file is the problem, and `ddd_globals.c` stays behind out of step with the header that was not written.
   - Why it matters: a build that ignores the exit code (a `make` target with `-`), or a person reading "cannot write into <dir>", now compiles a mixed set.
   - Fix: write each file to `name.tmp` beside its target and rename, or check every target path (`is_dir()`, parent writable) before the first write; name the failing file in the message.

#### Minor

1. **`codeAction` with `"context": null` ends the server** - `src/ddd/lsp/server.py:453`: `params.get("context", {})` returns `None` for a stated null and `.get` raises. Use `_field` like every other field.
2. **stderr loses its `backslashreplace` handler and a lone surrogate turns into a usage error** - `src/ddd/cli.py:93-96`: `reconfigure(encoding="utf-8")` resets `errors` to `strict` (checked: `backslashreplace -> strict`). The loader accepts the JSON escape `\ud800`, and `ddd list` on such a unit prints the table header and then exits 2 with a codec message; JSON mode is fine. Pass `errors="backslashreplace"` (or refuse surrogates in the loader).
3. **Hover markdown is not escaped** - `src/ddd/lsp/hover.py:182-187, 214`: a unit containing `|` or a backtick breaks the fact table (rendered output in `lsp_probe`), and descriptions pass through as markdown (links live; HTML is sanitised by VS Code). Escape `|` and backticks in cells.
4. **The include guard is lossy beyond case** - `src/ddd/backends/c/literals.py:347-354`: `Sensor` and `Sensor_` both give `DDD_COMPONENT_SENSOR_H` (`strip("_")`, `__+` collapse), and `name-collision` (`analysis.py:1095-1112`) only covers case. On Linux both headers are written and the second includes as empty. Fold the same normalisation into the check.
5. **Restart race in the extension** - `editors/vscode/src/extension.ts:159-171`: `start()` sets the module-level `client`, awaits `client.start()`, and on rejection sets `client = undefined` even if a concurrent `restartServer` has meanwhile assigned a new client, which then leaks (not stopped on deactivate, a further server on the next restart). Compare against the local instance (`if (client === mine) client = undefined`).
6. **`compile.sh` forwards only the spaced spelling of `-W`** - `docker/compile.sh:52`: the regex `-W [^ ]+` misses `-Wcheck=sev`, so `ddd dump` runs under a different policy than `ddd generate` and, on a component with missing producers, exits 1 and aborts the script.
7. **A plugin cannot import a sibling file, and the process-lifetime cache is asymmetric** - `src/ddd/plugins.py:192-196`: the module is loaded by location without its directory on `sys.path`, so a two-file plugin fails with `No module named 'helpers'`; `docs/plugins.rst:164-167` documents that edits take effect on the next process, but a plugin whose import failed is retried on every save while one that imported is never re-read, so the server's answer depends on whether the first save happened to be clean. Either load the file as a package (its directory on the submodule search path) or say so in the docs; key the server's cache on mtime.
8. **PROJECT mode re-runs configure on every component edit** - `cmake/Ddd.cmake:61-78`: every path `ddd sources` prints is appended to `CMAKE_CONFIGURE_DEPENDS`, so saving any component re-configures the whole build. Register only the directories of wildcard includes (or document the cost).
9. **The example plugin's header is not self-contained and never compiled** - `examples/plugins/ddd_layout.py:234-261` defines a `static const` table in a header and takes `&X` of variables it never declares (`ddd_globals.h` is not included; a `local` object is declared only in its component's header), so a translation unit including it alone does not compile; `tests/test_example_plugin.py:284-298` asserts substrings only, and `compile.sh:67-69` would compile it if the demo named the plugin.
10. **`exit` without `shutdown` returns 0** - `src/ddd/lsp/server.py:187-190`; the protocol asks for 1. Harmless.
11. **The `write` usage message names the directory for a failure inside it** - `src/ddd/cli.py:775-779` (see Important 6).

### Security boundary

- **Plugins are arbitrary code and run on import.** `load_plugin` executes the module (`plugins.py:192-200`); the CLI runs a project's plugins for `check`, `generate`, `list`, `dump`, `sources`, `artefacts`, `compare` and `schema --plugin`, and the server runs them for every project a build record names (records are found by walking `build/`, `out/`, `cmake-build-*` recursively, and a record may point anywhere) and for every `*.ddd.json` between the opened file and the workspace root (`navigation.py:214-249`), whether or not the opened file belongs to it. Demonstrated in Critical 3. Nothing in `SPEC.md` 3.11, `docs/plugins.rst`, `docs/editor_integration.rst` or the extension README says so, and neither the server nor the extension offers a confirmation, an allowlist or a workspace-trust check. `docs/plugins.rst:164` only says a module is "imported once per process".
- **Templates are not sandboxed.** `make_environment` (`base.py:140-149`) builds a plain `jinja2.Environment`, so a template reaches any attribute of the objects it is handed (`{{ ''.__class__.__mro__[1].__subclasses__() }}` and from there `os`). Rendering happens only under `ddd generate` (the server never renders), so this is the same boundary as the plugins - the repository - and is acceptable as long as it is stated next to them; `SandboxedEnvironment` would cost little if the project wants templates to be safer than plugins.
- **Paths a description can reach.** `includes` globs read anywhere the pattern reaches (`..` allowed); a plugin backend writes anywhere (Important 2); the built-in backends write only names derived from template file names, component names and the project name, all of which are C identifiers or files listed from the template directory, so no traversal; `$schema` is not interpreted (`models/common.py:30`), it is VS Code's JSON service that would fetch it.
- **The wire.** `serve()` moves `sys.stdout` to stderr before anything runs, so a plugin cannot inject protocol frames; a plugin can still read stdin, which is the wire, but that is again repository code.

### Design notes

- **Report before you write.** Every CLI command follows "analyse, produce, then `_report`", and the Important findings about lost findings (4), tracebacks (3), partial writes (6) and the known plugin-hook item are one shape: any exception between `_analyze` and `_report` discards the bag. Printing the findings as soon as the analysis is done, then treating every artefact step as its own phase with its own error, removes the whole class.
- **A document store for the server.** The server promises to analyse only on open and save; it does not have to promise that it never sees the buffer. Keeping the last `didOpen`/`didChange` text per URI, and reading positions and edits from it, is a contained change (`ranges.read` already has a cache parameter) and is what makes rename and the quick fixes safe (Critical 2), while `refresh` keeps reading the disk.
- **Three lookups, two implementations.** `collect()` and `workspaces()` both implement "build records, else containing project, else alone" and both call `containing_projects`, so a refresh loads a containing project twice and a hover a third time; the severity policy is assembled in `cli._analyze`, `lsp.diagnostics.analyse`, `analyse_standalone`, `_command_compare` and `_command_build_info`. One `resolve_projects(document) -> [(workspace, policy)]` used by both, and one `policy_for(record | args | standalone)`, would make the "same policy in the editor and the build" claim a property of the code rather than of five call sites.
- **The plugin boundary is thinner than its docstring says.** `_GuardedBackend` guards `generate` but not the factory's result, `render` trusts the returned paths, `_call` catches `Exception` only, and the hooks receive mutable `dict`s (`entry.extensions`, `dictionary.extensions`) inside otherwise frozen models, so a check hook can change what the backends render a moment later. A single `guard(plugin, hook, fn)` that validates the result shape, catches `BaseException` minus interrupts, and hands the hooks read-only views (`MappingProxyType`) would close all of it in one place.
- **Windows is tested through `Path.as_uri()` only.** The URI seam (`uri_to_path`/`as_uri`) and `Path.resolve()` are the only platform-specific code in the server, and every test drives them with the server's own spelling of a URI. A small table of client-shaped URIs (VS Code, Neovim, Emacs, a UNC share) in `TestRanges` would have caught Critical 1 on the Windows CI runner.

### Test review

- `tests/test_lsp.py:152-168` (`test_a_uri_round_trips_...`, `test_a_uri_still_decodes_...`): both send `Path.as_uri()` output; neither sends the `%3A` drive spelling every Windows client uses, so they pass while the server dies (Critical 1). `editors/vscode/src/launch.test.ts:292-304` opens no document.
- `tests/test_lsp.py` server tests send `didOpen` without `text` and never a buffer that differs from the disk, so the disk-versus-buffer contract of rename and the actions is untested (Critical 2).
- `tests/test_plugins.py:1247-1265` (`test_a_backends_generate_that_raises_...`) covers a raising `generate` but not a factory returning something that is not a backend, nor a `generate` returning a non-list (Important 3); no loading test uses a dataclass, a forward reference or a sibling import (Important 1, Minor 7); `tests/test_backends.py:234` (`test_two_backends_claiming_one_path_is_refused`) uses identical spellings only (Important 2).
- `tests/test_cli.py:1371-1391` (`test_an_output_directory_that_is_a_file`) asserts the message and not that nothing was written; there is no test of `--renames` failing to write, of a template raising a non-jinja exception, or of a hook calling `sys.exit` (Important 4-6).
- `tests/test_cli.py:799-815` (`TestGenerate::test_json_output`) checks only that every status is `created`, not the payload's `diagnostics`/`summary` keys or that stdout carries nothing but the document.
- `tests/test_cmake.py` builds the shipped example and three small projects, but never exercises `ADDRESS_MAP` (the seeded map and the two-run flow the spec makes a feature of), `SEVERITY`/`STRICT` reaching both the record and the commands, `NO_PROPAGATE_HEADERS`, `LINK_LIBRARIES`, `DEPENDS`, `BYTE_ORDER`, the `<stem>_ddd_check` target, or a `<target>.ddd` target that fails; `test_it_configures_builds_and_checks_each_component_alone` (line 102) builds `sensor_hub.ddd` only for a component that passes.
- `tests/test_example_plugin.py:284-298` asserts substrings of `ddd_layout.h` and never compiles it (Minor 9).
- `tests/test_embedded.py` verifies: the model accepts `types`/`constants` inside a component (59-95); the loader registers them into the shared registries with component-relative pointers and refuses duplicates across both homes (96-200); the analysis and `ddd list` resolve through embedded types (206-294); the C, the A2L and the dumped dictionary are byte-identical between the embedded and standalone homes (357-372); and the editor's definition, references, hover, rename refusal and diagnostic ranges reach into the embedded lists (396-469). Solid and behavioural; the byte-identity test is the strongest kind of assertion this suite has.
- `tests/test_transcripts.py` runs every documented command, some through `bash` (`SCRIPTS` first on the PATH): it depends on a shell being present and on the installed `ddd` matching the tree, which the module docstring states; a transcript that pins output line by line is also the test most likely to be edited to match a regression rather than to catch one - worth keeping the `echo $?` pins.
- Incidental details pinned: `tests/test_cli.py:1015` and the `PINNED_LIST_PAYLOAD` block pin the whole `ddd list --format json` document (deliberate and documented as the published shape, so acceptable); `tests/test_lsp.py:2079-2110` pins action titles word for word.

### Assessment

The periphery is carefully written where the authors expected trouble - framing, comment injection, console encoding, the CMake dependency graph - and the tests are behavioural rather than mock-driven. Two things undo much of that on the platform the tool is developed on: the server cannot decode a Windows client's URIs and exits on the first opened file, and every editing feature computes edits from the disk while the client applies them to its buffer. Around the plugin boundary the guarantees are narrower than the docstrings claim (path aliasing, the import order, `sys.exit`, factory results), the CLI loses its findings whenever a later step fails, and nothing anywhere tells a user that opening a repository runs its Python. All of these are contained fixes; none of them changes the design.
