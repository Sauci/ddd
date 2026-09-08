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
