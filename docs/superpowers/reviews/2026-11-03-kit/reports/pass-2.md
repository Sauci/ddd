## Pass 2: the split of the Python code

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-2/`. Line numbers are on the review tree.

**The answer, plainly.** Half of it is clean and half of it is not, and the line between the two is where the
editor features arrived. The generator (`models`, `loading`, `analysis`, `ir`, `compare`, `plugins`,
`backends`, `toolbox`) is well split: it runs and passes its tests with `ddd.gui` and `ddd.lsp` refused at
import. The transport is at the edge. The split between UI and backend *inside the editor features* is not
clean: there is a layer of about 9,000 lines that reads and changes a project for an editor, it has no name,
no row in the documentation and no guard, nearly a third of it lives inside the package named after the language
server, and the GUI and fourteen modules at the root of the package import that package to get it. Some of its
rules live in the clients. The guards that "keep the layering from rotting" hold eight rules and let 33 of 33
realistic violations through.

### Scope covered

**Read in full, with line numbers:** `src/ddd/gui/api.py` (1-2486), `gui/session.py` (1-1039), `editing.py`
(1-982), `lsp/navigation.py` (1-930), `lsp/units.py` (1-624), `lsp/edits.py` (1-954), `project_units.py`,
`type_plans.py`, `declaration_plans.py`, as the pass asks; and `lsp/ranges.py`, `lsp/diagnostics.py`,
`lsp/discovery.py`, `variables.py`, `variable_keys.py`, `project_types.py`, `project_shared.py`,
`shared_plans.py`, `file_plans.py`, `object_values.py`, `finding_routes.py`, `finding_fixes.py`, `identity.py`,
`deliveries.py`, `loading.py`, `gui/routes.py`, `gui/derived.py`, `gui/compare.py`, `gui/queries.py`,
`lsp/__init__.py`, `gui/__init__.py`, `ddd/__init__.py`. `docs/developer_documentation.rst` 1-200 and
895-1194; `docs/concept.rst` 510-589; `README.md` 1025-1058; `tests/test_backends.py` 1-289;
`tests/test_file_plans.py` 2124-2142; `tests/test_cli.py` 3726-3751.

**Read in part:** `lsp/server.py` 1-300 and its outline; `gui/server.py` 1-260, 952-1057 and its outline;
`gui/contract.py` 1-120; `gui/depth.py` 1-80; `analysis.py` its outline and 2551-2640; `cli.py` 1-60, 192-215,
822-1011, 1129-1309, 1602-1625, 1878-1918 and its outline; `backends/base.py` 25-54, 255-434; `diagnostics.py`
345-394; `file_names.py` 1-40.

**Docstring and public surface only:** every other module: the first line of its docstring and its public names
(`graph.txt`, last section, for all 87 modules), and the whole docstring of the 27 that bear on the split.

**Measured** (`graph.py`, `edges.py`, `sizes.py`, `closure.py`, `clones.py`, `words.py`, `who_uses.py`,
`parallel.py`): the import graph with top level, lazy and `TYPE_CHECKING` edges kept apart, with and without the
parent package an import runs; fan-in, fan-out, strongly connected components, dependency levels; what a fresh
interpreter really loads for each module, plain and with `ddd.gui` and `ddd.lsp` refused; code against prose per
module; repeated functions and token runs; who uses which symbol of `ddd.lsp`; commits per file since 2026-09-17.

**Probed:** the core with the editor layers refused (`probe_a.txt`); 1,293 core tests the same way
(`core_tests_blocked.txt`); a batch tool with `ddd.gui` refused, against the api, byte for byte (`probe_b.txt`,
`probe_b2.txt`); rules held twice, run against each other (`probe_c.txt`, `probe_d.txt`, `probe_f.txt`); the api
in process with no socket and a 1,200 component project (`probe_e.txt`); `ddd id --assign` against the engine on
Linux under WSL, with the models stubbed and both writers' own code (`wsl_identity.txt`); 40 injected imports
against every layering guard (`mutate.txt`); the first two moves of the target structure on a scratch copy
(`trial.txt`).

**Not covered:** the bodies of `compare.py`, `models/`, `backends/` apart from `base.py`, `toolbox/`, `elf.py` and
`lsp/hover.py`; and the TypeScript under `gui/`, which is pass 3's. Nothing here repeats pass 1's concept findings.

### Strengths

- **The generator does not know the editor.** `models`, `loading`, `ir`, `diagnostics`, `plugins`, `analysis`,
  `compare`, `deliveries`, `addresses`, `elf`, `toolbox/`, `backends/` have no edge to `ddd.gui` or `ddd.lsp`, top
  level or lazy (`graph.txt`). With both refused at import, load, analyse, `ddd check`, `ddd dump`, compare, render
  c and a2l and write all work (`probe_a.txt`), and 1,293 tests of 19 core test files pass (`core_tests_blocked.txt`,
  after three `try`s in `tests/conftest.py`, see Test gaps; `test_elf.py` did not collect, for a helper my copy
  lacked).
- **Every row of the documented layer table holds in the real graph.** Backends reach `ir`, `models` and their own
  package; c and a2l have no edge between them; `plugins` reaches `diagnostics`, `ir` and `names` at runtime;
  `elf` imports no `ddd` module; `models` reaches only `names`; `lsp` and `gui` reach no backend. The problem is what
  the table leaves out (I5), not what it says.
- **Nothing below the GUI imports the GUI.** The one edge into `ddd.gui` from outside it is `cli.py:1612`, lazy.
  `ddd.lsp` has none. The GUI is genuinely on top.
- **No import cycle at module level** once package `__init__` files are set aside (`graph.txt`). The two cycles
  through lazy imports are small (M1).
- **Transport is at the edge.** `http.server` and sockets are in `gui/server.py` alone; json-rpc's framing in
  `lsp/protocol.py` alone. `gui/api.py` answers with no socket: `Api.handle` runs in process (`probe_e.txt` §1), which
  is how `tools/bench_gui.py` already drives it, and `gui/server.py` is a security edge of its own. (The language
  server's *shapes* are another matter: see "Is transport kept at the edge?" under Assessment.)
- **The plan functions really are reusable.** A batch tool with `ddd.gui` refused made thirteen edits through them,
  with no error after any, and left every file byte for byte what the same edits through the api left; it took about
  twenty lines of glue (`probe_b.txt`).
- **Several copied rules agree today.** `lsp/units.py:text_edits` against `editing.edit_text`: 28 of 28 same bytes over
  LF, CRLF, tabs, one line, a merge and neighbouring removals (`probe_c.txt` §5). `rename_problem` against the loader
  and the analysis: 102 of 102 on an empty project, 61 of 64 inside one (`probe_d.txt`, `probe_f.txt`; two of the three
  differences are the edit being stricter, the third is M6). `file_plans._component_name`: 14 of 14 (`probe_f.txt`).
  `object_values._acceptable` against the loader and `_check_init`: 262 of 264, the two being one case (M5). `KINDS`, `SCOPES`, `ROLES`,
  `KEY_ORDER`, `EDITORS`, `SETTABLE`, `REQUIRED` and the `Vocabulary` tables all match the models today (`probe_d.txt`).
- **The engine is one job done well.** `editing.py` is cohesive, verifies each edit against the parsed document, keeps
  access and retries on Windows. It is a module in the wrong place only because of what it imports (I2).

### Issues

#### Critical

None. The split produces no wrong C, a2l or dictionary, and I found no file lost by it. The worst reproduced effects
are in the list below.

#### Important

- **I1. The edit layer has no name and no home, and its dependency runs the wrong way.**
  `src/ddd/lsp/navigation.py:142` (`Index`), `lsp/ranges.py:83` (`Document`), `lsp/units.py:64` (`PlannedEdit`),
  `lsp/edits.py:563` (`settle`), `lsp/diagnostics.py:95` (`run_build`). Everything that reads or changes a project
  for an editor is about 9,000 lines (table under Assessment), split between the package root and `ddd.lsp`. 14 root
  modules import `ddd.lsp` (35 edges) and so do 4 GUI modules (10 edges); from outside the package `ranges` has
  fan-in 15, `navigation` 13, `units` 7, `edits` 6 (`scc_with_parents.txt`). Of `ddd.lsp`'s 4,952 lines about 2,600
  are not about a language client at all: `Index`, `rename_problem`, `settle`, `reconciliations`, the unit plans,
  `Run`, `group_findings`, `discover` (`who_uses.txt`). Since 2026-09-17 `lsp/hover.py` and `lsp/protocol.py` took 0
  commits and `lsp/server.py` 1, while `lsp/edits.py` took 18, `units.py` 14, `navigation.py` 12, `diagnostics.py` 8:
  the language server has stood still and its package has been the GUI's backend. The code says so itself:
  `identity.py:9-10` "happens to live under the language server", `value_identity.py:15-18` on what a value is
  becoming "the language server's to say", `lsp/navigation.py:759-765` choosing where a rule lives by which import
  would cycle, `file_plans.py:533-535`.
  *Trigger:* with `ddd.lsp` refused, `import ddd.variables`, `variable_keys`, `project_units`, `project_types`,
  `project_shared`, `type_plans`, `shared_plans`, `declaration_plans`, `object_values`, `file_plans`,
  `finding_routes`, `finding_fixes` each raise `ImportError`, and `editing.edit_text` and `identity.assign` raise it
  on first call (`probe_a.txt`). *Consequence:* a second interface or a batch tool cannot avoid the language server's
  package, a change for the page lands in a package named for another client, and where a rule goes is decided by
  which import would cycle. *Change:* the target structure, moves 5 to 7 (M each, L together).

- **I2. Importing `ddd.lsp.ranges` loads the whole language server, and two deferred imports hide a 12-module cycle
  behind it.** `src/ddd/lsp/__init__.py:12-15`, `editing.py:22-24, 481, 527`, `identity.py:13-18, 173`.
  `ddd/lsp/__init__.py` re-exports `Server` and `serve`, so any import under `ddd.lsp` loads `server`, `protocol`,
  `hover` and the rest. Counting the parent package an import runs, `{editing, identity, lsp, lsp.*}` is one strongly
  connected component of 12 modules (`scc_with_parents.txt`); the function-level imports are what keep it from
  failing at import, and both docstrings say so. *Trigger:* `import ddd.file_plans`, documented "transport-neutral",
  loads `ddd.lsp.server` and `ddd.lsp.protocol` (`closure.txt`: all 12 plan and read modules do); `ddd id --assign`,
  the pre-commit hook, needs them too and fails without them (`probe_a.txt`). `src/ddd/gui/__init__.py:6-7` already
  states the right rule ("Nothing is imported here"). *Change:* an empty `lsp/__init__.py`, the two imports moved up:
  S. Tried on a scratch copy (`trial.txt`): the plans stop loading `server`, `protocol` and `hover`; one line of a test is
  repointed (`tests/test_plugins.py:52`); over 29 test files and 3,572 tests the same four fail before and after, the
  known symlink one and three that fail in the scratch copy before any change. Moving `ranges.py` out as well
  (60 spellings, `sed`) gives the same four, and `ddd.editing` then loads nothing of `ddd.lsp`.

- **I3. Rules a second client needs live in the clients.** `src/ddd/gui/api.py:2144-2294` (`_addition`, `_removal`,
  `_judged`), `:1791-1850` (`_appeared_since`, `_changed_since`), `:1513` (`_refuse_unanalysed`), `:1957-2006`
  (`_required_keys`, `_declared`), `:2386-2420` (`_number`, `_folded`), `gui/session.py:736-772` (`findings_with`,
  `_runs`), `:847-908` (`_creatable`, `_confined`, `_included`), `:933-945` (`kind_of`), `cli.py:939-1010` (the
  `address-missing` check), `:1129-1296` (assembling a generate run). About 225 code lines of `gui/api.py` are
  project rules, not routes. The core modules point upward at them in prose: `file_plans.py:533-535` says the kind
  rule is one "this module, importing nothing of `ddd.gui`, cannot ask"; `lsp/units.py:146-149` and
  `shared_plans.py:571` shape every plan around "the only creation `ddd.gui.session._confined` allows".
  *Trigger:* `remove_plan` for `constants.ddd.json` of `examples/vocabulary`, applied by the batch tool: written,
  and the project then fails with `unknown-constant`; the same request through the api is `409 ... would leave one
  error more` (`probe_b.txt`, `probe_b2.txt`). `add_plan` takes `x.py`; only `gui/api.py:2180` refuses it. A batch
  tool has `new_errors` and cannot get its `after` without `gui/session.py`. *Consequence:* whatever else makes these
  edits can break a project the GUI would protect, or has to copy the rules. `generate` cannot be reused without
  `ddd.cli`. *Change:* move 8 and 9: file judgement beside `file_plans.py`, `kind_of` into `loading.py`, `Session`
  below the GUI, `_number`, `_folded` and the empty description into their plans, the generate run and the address
  checks out of `cli.py`. M.

- **I4. The guards hold eight rules; "cannot rot silently" is false.** `KNOWN` (2026-09-15, pass 7 test gaps).
  `tests/test_backends.py:32-41, 66-160`, `tests/test_file_plans.py:2124-2142`; the claims at
  `docs/developer_documentation.rst:106-112`, `docs/concept.rst:578-583`, `README.md:1047-1048`. Nothing covers `gui`,
  `lsp`, `editing`, a plan, `compare`, `deliveries`, or `models` importing anything. *Trigger:* forty forbidden imports
  injected one at a time into a scratch copy, every layering test run each time (`mutate.txt`). Caught: the 7
  controls. Not caught: all 33 others, among them the file formats importing a backend or the analysis, the loader or
  the analysis importing the gui's api, `ir` importing the command line, the a2l backend importing the language
  server, the language server importing a backend (the table's own row) or the gui, `editing` importing the session,
  and `file_plans` importing the gui lazily, the one module its guard names. The helper itself has three holes, each
  passing a directly guarded file: `from ddd import backends` in `loading.py`, `from .backends import base` in
  `plugins.py`, `from . import names` in `elf.py` ("imports no ddd module at all"), and `importlib`. Ruff's `TID` rules
  are not on. *Change:* one table-driven test over every module, with a ratchet of today's violations that only shrinks
  ("What the guards should then say", under Assessment): S.

- **I5. The documented layers leave out 39 % of the code, and three sentences about the rest no longer hold.**
  `docs/developer_documentation.rst:19-58, 75, 78-83, 92-97`, `README.md:1033-1041`, `src/ddd/__init__.py:3-9`. This
  page is for "whoever has to change DDD ... before moving something". `gui/` (8,580 lines) and 20 root modules (6,645
  lines: `editing`, every plan and read model, `deliveries`, `graph`) have no row and no statement of what they may
  import; "The browser interface" names some of them as sitting "beside" each other and never says what is below
  what. No longer so: `:75` "Six smaller modules"; `:78-79` "`cli.py` is the only module that knows about ... exit codes and
  where output goes" against `gui/server.py:70, 931-932, 978-993, 1027` and `gui/session.py:546, 686`; `:92-96`
  `ddd.lsp` as "a second front end" against 19 modules importing it. `src/ddd/__init__.py:3-9` says "each knowing only
  what is below it" of a list with `ir` above `loading` and `analysis`, both of which import it. The README table has no
  `lsp`, `gui`, `toolbox`, `elf`, `addresses`. Pass 1 M1 and M2 cover `docs/concept.rst`. *Consequence:* the page that
  should stop the next module landing in the wrong place does not mention where it would go. *Change:* the table of the
  target structure, written last: S.

- **I6. `ddd id --assign` is a second edit engine without the first one's protections.** `src/ddd/identity.py:198-208`
  against `editing.py:919-963, 472-491`. *Trigger, reproduced on Linux with both writers' own code
  (`wsl_identity.txt`):* a file of mode 640 is left 644, 600 is left 644, and a read-only 444 is rewritten and left 644,
  where the engine leaves each as it was. `editing.py:949-956` records this very defect, a read-only file made writable
  and a file left root's in a container, as fixed; `identity.py:57-63` and `docs/command_line_interface.rst:163-165`
  promise a file that cannot be written is reported, and a read-only one on Linux is not. It does not retry on Windows
  (`_patiently`), and it reads by python's parser, so it rewrites a
  file the loader refuses: a key spelled twice, or `NaN`, answers 1 and writes (`probe_c.txt` §4), against "must not
  rewrite one it could not read" (`identity.py:169-171`), where the engine refuses both. It runs as a pre-commit hook on
  every staged description (`.pre-commit-hooks.yaml`), and `docker-compose.yml` mounts the checkout and names no user,
  so run there it also leaves the file root's (read off the line). A third staging writer is
  `backends/base.py:264`, and `STAGING_SUFFIX` is spelled three times (`file_names.py:16`, `identity.py:66`,
  `backends/base.py:33`, pinned by tests). *Change:* `assign` builds its `FileChange`s and calls `apply_changes`, keeping
  its insertion: S. No test checks a mode after `ddd id`.

- **I7. "Load, gate, analyse, keep the plugins" exists six times and "compare, then hooks" three, and the copies have
  already diverged once.** `cli.py:1896-1917`, `deliveries.py:136-146`, `lsp/diagnostics.py:171-177, 201-217`,
  `lsp/hover.py:97-105`, `toolbox/checked.py:89-91`; compare at `cli.py:847-856`, `cli.py:899-908`,
  `gui/compare.py:233-248`. `gui/compare.py:19-24` and `lsp/diagnostics.py:63-68` record the result: the GUI compared
  without the hooks and "answered 'can replace' for a delivery the command exits 1 on". Each comment now says what the
  others do; nothing makes them. They differ legitimately in what a `PluginError` becomes and in the verify step, which
  a parameter can hold. *Consequence:* the next step of the pipeline, or a change in its order, is written six times.
  *Change:* one `resolved_project(path, bag, *, includes)` and one `compare_deliveries(...)` in `deliveries.py`, which
  `cli`, `lsp` and `gui` call: M.

- **I8. The UI's vocabulary is below the UI, and "transport-neutral" is taken to mean "UI-neutral".**
  `src/ddd/finding_routes.py:205-224` (`Route.kind`, "Which screen the page opens"), `variable_keys.py:54-75` (`EDITORS`,
  "Which field the page offers"), `project_shared.py:106-122` (`Vocabulary.keys` "in the order the panel draws them",
  `strings` "so the panel shows them without their quotes", `states` "The row's States cell"), `project_types.py:41-45`,
  `declaration_plans.py:33-37` ("in the order the form offers them"), `finding_fixes.py:52` ("What the button says"),
  `project_units.py:1`, `project_types.py:1`, `project_shared.py:1`, `shared_plans.py:1`, `variables.py:1`,
  `variable_keys.py:1` (each module's first line names a tab or a panel). Counted in prose and identifiers per module in
  `words.txt`. `finding_routes.py:11` says "Pure: no GUI" of a module whose answer is a screen of the page, and
  `:217-224` explains that the list of screens is therefore "stated twice and pinned together" by a test, because
  `contract.FindingRoute.kind` cannot import it. *Consequence:* a change of what the page shows edits a "core" module, and a second interface
  inherits screens it does not have. *Change:* screens and fields to `ddd.gui` (`route_of`, `Route`, `EDITORS`, the
  `states` cell, form orders); what is about the project stays (`ABOUT_THE_DECLARATION`, `UNIT_CHECKS`, `KeyOffer` less
  `editor`, the rows): part of move 7.

- **I9. One rule twice, fixed once: every keystroke in a Shared files panel parses every file of the project, for
  nothing.** `src/ddd/shared_plans.py:113-152` against `lsp/units.py:177-218`; `gui/api.py:1193-1198`. The two functions
  read a project's vocabulary files the same way. `unit_project` learnt not to parse every file (`_may_list_units`,
  `:204-218`, measured there at 1.4 s of 1.5 s, plan `2026-09-30-gui-large-projects`); `project_of` did not, and
  `_shared_plan` calls it unconditionally although "`project` is unused by three of the four" verbs
  (`gui/api.py:1888-1889`), and "a panel asks for a plan on every keystroke" (`project_shared.py:168`). *Trigger, in
  process over 1,200 components of 30 declarations (`probe_e.txt` §6):* `GET /api/unit-plan?action=describe` 570 to 626
  ms; `GET /api/constant-plan?action=set` of one key of a one-entry file 1,727 to 2,212 ms. The two also disagree on
  what an unparsed file means (`untellable` has no counterpart). *Change:* one function; ask it only for `add`: S.

- **I10. Each plan route is the same thirty lines, and each plan the same class.** `KNOWN` in part
  (`2026-09-23-gui-values.md:1503`, then "eight spellings of one idea"). `src/ddd/gui/api.py:797, 921, 1115, 1169, 1219,
  1321, 1402, 1433`: eight handlers differing in about four lines. `409 if refused.code in REFUSALS else 500` is now
  written 12 times, the not-found mapping 8, the "did not load" sentence 3. 1,894 of the file's 13,144 tokens are in
  repeated runs of 50 or more (`clones.txt`). Below it: five one-field plan classes (`lsp/units.py:74`, `type_plans.py:59`,
  `shared_plans.py:90`, `declaration_plans.py:130`, `object_values.py:284`; `project_units.py:254-256` "two different
  dataclasses sharing one shape"), six identical refusal classes (`lsp/units.py:160`, `type_plans.py:42`,
  `shared_plans.py:96`, `declaration_plans.py:141`, `object_values.py:41`, `file_plans.py:239`), and six shapes for what
  one file takes (`PlannedEdit`, `FileEdit`, `Planned`, `FileChange`, `_FilesPlanned`, and the tuples of
  `variables.py:170`, for which my batch tool had to write a class). Exact copies: `_protocol_edit`
  (`lsp/edits.py:949`, `lsp/units.py:618`), `_raw` (`lsp/units.py:504`, `shared_plans.py:550`), `_names`, `_plan`, the
  lookup in `project_shared.py:538, 590, 653` and `project_types.py:186`. *Consequence:* `gui/api.py` is the most changed
  file of the package (75 commits since 2026-09-17, against 54 for the next), and each new route copies its neighbour, drift
  included. *Change:* one `Plan`, one `PlanRefusal`, one `_answered(revision, plan)`: S to M, about 200 lines fewer.

#### Minor

- **M1. Two cycles through lazy imports, and two small inversions.** `diagnostics.py:365` imports `loading.resolve_path`
  (`{diagnostics, ir, loading, plugins}`, and its comment says this line is what keeps the graph acyclic);
  `gui/server.py:70` imports `EXIT_OK` and `EXIT_USAGE` from `ddd.cli` (`{cli, gui.server}`); `loading.py:14` imports
  `ir` only for `load_dictionary`, the reader of the other format. `analysis.py:18` takes its comparison primitives from
  `compare.py`, which the docs call a consumer of the dictionary: documented in `compare.py`, harmless, but the guard does
  not know `compare` sits inside the front end's closure. *Change:* `resolve_path` to a leaf, `EXIT_*` to `names.py`,
  `load_dictionary` to `deliveries.py`: S.
- **M2. `gui/api.py:140-143` imports `_name_in`, `_read_json`, `_served`, `_source` from `gui/session.py`.** The only
  private names reached across modules in the package (`who_uses.txt`); they are the rules of I3 not yet given a name.
- **M3. "Values arrive as json text, never as parsed values" is not what two modules do.** `declaration_plans.py:320`
  (`read_object`, and `declare_object`) and `project_types.py:263` (`fixed_by`), against `editing.py:11-15`,
  `lsp/units.py:504-507` and `shared_plans.py:550-554`, each of which spells out what `ensure_ascii` is for. *Trigger:*
  reading a variable with `"unit": "°C"`, `"factor": 1e-1`, `"min": -4.0e1` writes `"\u00b0C"`, `0.1`, `-40.0` into the
  reader's file (`probe_c.txt` §2). `check` stays clean, so the effect is cosmetic, in the most common non-ascii unit of
  the domain. `GET /api/type` answers `"\u00b0C"` and `{"factor": 0.1}` where its docstring says "as the json text it is
  written as" (`probe_e.txt` §3).
- **M4. What kind of file this is, answered five ways.** `loading.py:67, 734-766` (the rule), `gui/session.py:58, 933-945,
  985-987`, `lsp/diagnostics.py:155-158`, `deliveries.py:210-217`; `session.KINDS` restates `FILE_KINDS` with no test
  pinning them. *Trigger (`probe_c.txt` §1):* a dumped dictionary is `file-kind` to the loader and `types` to `kind_of`, so
  `GET /api/files-plan?action=add` previews it where `gui/api.py:2186` refuses a file of no kind (`probe_e.txt` §4); a file
  with `project` and `component` is `file-kind` and `project`. `Upper.DDD.JSON` loads with no finding, "compared without
  regard to case" (`SPEC.md:194`, `loading.py:727`), and `GET /api/projects` does not list it (`gui/session.py:958`,
  `probe_e.txt` §5); `lsp/navigation.py:540` depends on the platform. *Change:* one public `file_kind(data)` in `loading`.
- **M5. A cell the plan takes and the file refuses.** `object_values.py:501` holds the datatype's rule and not the model's
  `within_64_bits` (`models/common.py:179`). *Trigger:* `GET /api/value-plan?name=A1&at=[1]&raw=18446744073709551616` on a
  float32 axis answers 200, `POST /api/edit` writes it, and the component stops loading with `schema` (`probe_e.txt` §2).
  Undo puts it back. The two checks are otherwise one rule written twice: share one `init_problem(value, datatype)`.
- **M6. `rename_problem` takes a constant named as a structure member, and the next check refuses it.**
  `lsp/navigation.py:792` against `analysis.py:1918-1925`. *Trigger:* renaming constant `OTHER` to `rpm`, a member of a
  structure: no refusal, then `name-collision` (`probe_f.txt`). The class of defect `_occupy`'s docstring
  (`lsp/navigation.py:354-360`) records for enumerators. *Change:* note member names in `Index.occupied` for a constant.
- **M7. One fix, two diffs.** `finding_fixes.py:89` sets `definition.id`, which the engine appends after the last key;
  `identity.py:160` and so the language server and `declaration_plans._stamped` put it after `name` (`probe_c.txt` §3),
  against `finding_fixes.py:8-10` "only how the edit is spelled differs".
- **M8. 31 regular expressions over pointer shapes, in 7 modules, and no module that owns the shapes.**
  `lsp/navigation.py:50-104`, `lsp/edits.py:138, 142`, `finding_routes.py:93-122, 191`, `project_shared.py:235, 241, 551, 603,
  607`, `project_types.py:30`, `toolbox/checked.py:39-40`, `gui/derived.py:36`; `component.interface` is spelled in 12 files.
  Several are pinned to each other by tests rather than shared. `KNOWN` for `WITHIN_DECLARATION`, written twice
  (`2026-09-22-gui-findings.md`, "One pattern, written twice"), still open.
- **M9. 73 citations of planning artefacts in 25 modules.** `part 13`, `part 14's third task` (`project_shared.py:81`,
  `lsp/navigation.py:771`), `Task 2 is the only caller` (`graph.py:5`), `ruling P19a-14`, `run 37737377854`
  (`gui/server.py:129-134`), `Appendix A` (`gui/queries.py:7`), `the branch's final review` (`finding_routes.py:165`). 18 are in
  `gui/server.py`. A future reader cannot resolve most of them from the tree; those that name a measurement should state it.
- **M10. Docstrings the code has outgrown.** `lsp/server.py:1, 3-4` ("six messages", "Everything that decides anything lives
  in `lsp.diagnostics` and `lsp.discovery`"), `lsp/protocol.py:4-9`, `variable_keys.py:6-7` and `finding_routes.py:11-12` ("nothing
  else reads them": `declaration_plans.py:30`, `project_shared.py:33`, `project_units.py:20` do), `lsp/navigation.py:110-111`
  (the docstring of `_BASE_DATATYPES` describes something else), `shared_plans.py:48-56` (`CONSTANTS_FILE` kept for tests).
- **M11. The pair of an index and a document cache is threaded by hand.** `cache: dict[Path, Document]` is written 126 times in 18
  modules, and arguments no one reads are kept "for the shape": `lsp/units.py:319-320`, `declaration_plans.py:255-258`,
  `project_shared.py:176`. One small `ProjectView(index, documents, unread)` would carry them. Part of move 5, not urgent.

### Status of the 2026-09-15 findings in this area

| finding | status | where |
| --- | --- | --- |
| Pass 7 test gap, "`compare.py`, `identity.py`, `build_info.py`, `cli.py` and `src/ddd/lsp/` sit outside the import-graph guard" (`review-2026-09-15.md:3033`) | STILL OPEN, and wider: `gui`, `editing` and every plan since | I4 |
| P7-M2, the layer table never names `lsp`, `identity`, `build_info` | FIXED for those (`developer_documentation.rst:47-49, 86-97`); REGRESSED in kind: `gui/` and 20 root modules have no row | I5 |
| P9-M11, the table's wording about the analysis | FIXED on the developer page (`:32-34, 60-64`); STILL OPEN at `README.md:1037` | I5 |
| Pass 10's "outside `cli.py` nothing prints, exits or names a stream" (`review-2026-09-15.md:3932`, a strength then) | No longer true: `gui/server.py`, `gui/session.py` | I5, M1 |

### Open questions

1. **Is a second interface, or a batch tool making these edits, a goal?** If yes, all of the moves are worth making. If no,
   moves 0 to 4 and the documentation remove what hurts, and moves 7 to 9 can wait for the first reason.
2. **Does anything outside this repository import `ddd.lsp.*`, `ddd.editing` or `ddd.gui.*`?** I did not look (ptf is ruled out).
   If something does, each move keeps a shim for a release; if not, the renames are free.
3. **What is the layer called, and is it one package?** I propose `ddd.editing`, today's module becoming `ddd.editing.engine`.
   The answer changes only names.
4. **Is `ddd.gui.api.Api` a supported in-process interface?** It works as one (`probe_e.txt` §1) and is documented as internal
   (`gui/api.py:5-6`). If it becomes supported, `Session` may stay nearer the GUI and a batch tool drives the api; if not, I3 stands.
5. **Where does an id go?** After `name`, as `ddd id` writes it, or where the engine appends it (M7). Either is fine; one is.

### Test gaps

- `tests/conftest.py:28, 31, 32` import `ddd.gui.session`, `ddd.lsp.navigation` and `ddd.lsp.protocol` at module level, so every
  test of the core loads both editor layers and nothing can notice the core coming to depend on them. Three `try`s were all it
  took for 1,293 core tests to pass with both refused. A test file `tests/test_core_alone.py` in a sub-interpreter would pin it.
- Only one module's closure is tested (`test_the_module_imports_nothing_of_the_gui`, for `file_plans`, at import time, so a lazy
  import passes it) and `ddd --version`'s. Its siblings say the same thing in prose and are not held to it.
- No test checks a file's mode after `ddd id --assign` (I6); the engine's is at `tests/test_editing.py:577-580`.
- Nothing pins `gui/session.py:KINDS` to `loading.FILE_KINDS`, nor `type_plans.SETTABLE` and `REQUIRED` or a `Vocabulary`'s
  `keys`, `required`, `strings` to the models' fields. `Vocabulary.__post_init__` checks the record against itself only.
- No differential between `_acceptable` and the loader plus `_check_init` (M5), between `rename_problem` and the analysis's
  collisions (M6), or between `text_edits` and `edit_text` (it holds, and only my probe says so).

### Assessment

The core is split cleanly, the transport is at the edge, and nothing below the GUI imports the GUI; but what was added for the
editors grew without a layer of its own, so the question "UI or backend?" has no clean answer for about 9,000 lines: part of the
backend lives in the language server's package, part at the root with its modules named after tabs, part in `gui/api.py` and
`gui/session.py`, and the guards and the documentation stop where the generator stops. It has already cost: a comparison without
hooks, a permission fix that reached one writer of two, a performance fix that reached one reader of two, and about thirty lines
per route. None of it is hard to mend: the plan functions are reusable as they stand and the moves below are mostly mechanical, the
100 % coverage making them safe to make. A couple of days' work (moves 0 to 4) removes the worst of it.

#### The real layers, against the documented ones

Measured from the graph (`graph.txt`, `levels.txt`), with the lines of each. A module of `ddd.lsp` is split by symbol
(`who_uses.txt`): what only a language client needs, and the rest.

| real layer | modules | lines | in the layer table? |
| --- | --- | --- | --- |
| leaves, importing nothing of ddd | `names`, `pointers`, `file_names`, `difflib_lock`, `build_info`, `elf` | 1,192 | `names`, `elf`, `build_info` |
| file formats | `models/` | 3,609 | yes |
| one lazy cycle | `diagnostics`, `ir`, `plugins`, `loading` | 3,545 | yes |
| resolution and comparison | `compare`, `analysis`, `deliveries`, `addresses` | 5,308 | not `deliveries` |
| output | `backends/` | 2,621 | yes |
| one-off tools | `toolbox/` | 1,179 | yes |
| **the edit layer, unnamed** | `editing`, `identity`, `value_identity`, `variables`, `variable_keys`, `project_units`, `project_types`, `project_shared`, `type_plans`, `shared_plans`, `declaration_plans`, `object_values`, `file_plans`, `finding_routes`, `finding_fixes`, `findings_by_file`, `graph`, and of `ddd.lsp` the 2,598 lines that are not about a client | 9,040 | `identity`; `lsp` as if it were all client |
| language client | `lsp/server`, `protocol`, `hover`, and 829 lines of `navigation`, `edits`, `units`, `diagnostics`, `ranges` | 2,354 | yes |
| browser | `gui/` | 8,580 | no |
| command line | `cli` | 2,076 | yes |

The documented picture, front end to dictionary to backends, is right for the first six rows. It has nothing to say about the last
four but `lsp` and `cli`, and what it says of `lsp` holds for half of what that row names. Highest fan-in: `diagnostics` 30, `lsp.ranges` 21,
`loading`, `models.common` and `lsp.navigation` 18, `ir` 17; highest fan-out: `gui.api` 30, `cli` 21 (17 lazy), `file_plans` and `gui.session`
11 (`graph.txt`). That two of the five most imported modules of the package sit under `lsp/` says what I1 says. 36 % of the package's lines are prose.

**Directions that run the wrong way:** root modules and the GUI into `ddd.lsp` (I1); `diagnostics` into `loading`, `loading` into `ir`
for a reader that belongs elsewhere, `gui.server` into `cli` (M1); the plans' shape into `gui.session._confined`, in prose (I3);
read models into `finding_routes`, a module about screens (I8). **Modules with more than one reason to change:** `lsp/navigation.py` (the
jumps; the index; what a name may be; finding a document's project), `lsp/edits.py` (the quick fixes; the settlement rule), `lsp/units.py`
(the plans; their text edits; how a file is created), `lsp/diagnostics.py` (a run; drawing it), `gui/api.py` (routes; project rules; caching),
`gui/session.py` (session state; file kinds; project discovery), `cli.py` (the command line; a generate run; the `address-missing` check),
`project_shared.py` (a vocabulary's rules; a row's cells).

**Can the core be used and tested without the editor layers?** Yes, as measured, but for `ddd id`. **Could a second interface or a batch tool be
built without `ddd.gui` or `ddd.lsp`?** Without `ddd.lsp`: no, not one edit (`probe_a.txt`). Without `ddd.gui`: yes, in about twenty lines, and it gets every
byte right and loses every rule of I3 (`probe_b.txt`). With `ddd.gui.api.Api` in process: yes, today, against an api documented as internal.
**Is transport kept at the edge?** HTTP and json-rpc's framing, yes. The language server's shapes, no: `lsp/ranges.py:121-129`, `:232-245`, `lsp/navigation.py:900, 907-910`,
`lsp/edits.py:195-199, 618, 951-954`, `lsp/units.py:621-624`, `lsp/diagnostics.py:364-370` build them in the modules the GUI imports for its rules; the GUI never reads them.

#### Are the large files large because the job is large?

| file | lines | code | prose | verdict |
| --- | --- | --- | --- | --- |
| `analysis.py` | 3,692 | 2,200 | 34 % | The job. One class of 85 methods, most of the 72 registered checks, and three names used from outside it (`analyze`, `close_units`, `PRODUCER_KEYS`). Cohesive around one shared state; splitting it into mixins would move lines, not reasons. Leave. |
| `gui/api.py` | 2,486 | 1,832 | 20 % | Partly. 36 routes is a large job. Of the code, 200 lines are imports, about 240 are I10's boilerplate, about 225 are I3's rules, about 100 are dispatchers. About 1,950 lines once the boilerplate and the rules go. |
| `cli.py` | 2,076 | 1,426 | 23 % | Mostly. 16 commands. `_build_parser` (426 lines) is long because it is a flat declaration of them, and reads well; leave it. `_command_generate` and the address checks are what does not belong. |
| `gui/contract.py` | 1,798 | 548 | 41 % | The job: 76 models, one per shape on the wire. About twenty mirror a dataclass field for field (`parallel.txt`), which is the price of keeping the wire at the edge. Leave. |
| `gui/queries.py` | 1,114 | 454 | 29 % | The job, repetitive: the three vocabularies' `Set`, `Rename` and `Remove` differ by a noun. Declarative and harmless. Leave, or a factory if a fourth vocabulary comes. |
| `gui/session.py` | 1,039 | 532 | 37 % | `Session` itself is one job and a careful one. The file's helpers are I3's. |

#### Rules held in more than one place

| rule | where | state |
| --- | --- | --- |
| writing a description file safely | `editing.py:919`, `identity.py:198`, (`backends/base.py:264`) | **diverged**, reproduced: I6 |
| what a kind of file is; its suffix | `loading.py:67, 727, 734`, `gui/session.py:58, 933, 958, 985`, `lsp/diagnostics.py:155`, `deliveries.py:210`, `file_plans.py:216, 228`, `lsp/navigation.py:540` | **diverged**, reproduced: M4 |
| a project's vocabulary files | `lsp/units.py:177`, `shared_plans.py:113` | **diverged**, reproduced: I9 |
| json text is not re-serialised | `editing.py:11`, `lsp/units.py:504`, `shared_plans.py:550`, `file_plans.py:420`; `declaration_plans.py:320`, `project_types.py:263` | **diverged**, reproduced: M3 |
| a value fits its datatype | `analysis.py:2551`, `models/common.py:179`, `object_values.py:481` | **diverged**, reproduced: M5 |
| which names are taken | `analysis.py:1865` and its siblings, `lsp/navigation.py:751, 353` | **diverged**, reproduced: M6 |
| where an id goes | `identity.py:160`, `declaration_plans.py:269`, `finding_fixes.py:89` | **diverged**, reproduced: M7 |
| load, gate, analyse; compare, then hooks | I7's six and three | diverged once, mended, still six and three |
| a new component's name | `analysis.py:1792`, `file_plans.py:452` | agrees, 14 of 14 |
| an operation becomes an edit | `editing.py:516`, `lsp/units.py:601` | agrees, 28 of 28; the second is not verified |
| pointer shapes | M8's seven modules | partly pinned by tests |
| `KINDS`, `SCOPES`, `ROLES`, `CREATABLE`, `SETTABLE`, `REQUIRED`, `Vocabulary`'s tables | beside the models | agree today, most unpinned |
| what screens exist | `finding_routes.py:205`, `gui/contract.py` `FindingRoute`, the page | pinned by a test, because of I8 |

#### The target structure

```
src/ddd/
  names.py pointers.py file_names.py paths.py build_info.py difflib_lock.py elf.py   leaves; paths.py takes resolve_path; names.py takes EXIT_*
  models/  diagnostics.py  ir.py  plugins.py  loading.py                             as they are; loading.py gains file_kind(), loses load_dictionary
  compare.py  analysis.py  addresses.py  deliveries.py                               deliveries.py gains resolved_project(), compare_deliveries(), load_dictionary
  generating.py                                                                      new: what _command_generate does, less arguments and printing; address checks to addresses.py
  backends/  toolbox/                                                                as they are
  editing/                  no ui word, no transport; imports the above, never backends, lsp, gui, cli
    document.py             lsp/ranges.py, less the protocol's positions (329 lines)
    engine.py               editing.py
    identity.py             identity.py, writing through the engine
    value_identity.py       value_identity.py
    index.py                lsp/navigation.py: Index, Site, UnitSite, index(), LOAD_CHECKS, rename_sites, rename_problem; pointer shapes (about 670)
    runs.py                 lsp/diagnostics.py: Run, run_build, run_project, group_findings, finding_identity; navigation's Loaded, resolve_projects; lsp/discovery.py
    settle.py               lsp/edits.py: settle, settled_at, reconciliations, PROPAGATED_KEYS, DEFERRED_KEYS (about 700)
    plans.py                one Plan, PlannedEdit, PlanRefusal; created_beside, entry_appended; preview (planned, hunks)
    vocabularies.py         project_shared.py: the Vocabulary record and its judges, less the cells
    unit_plans.py type_plans.py shared_plans.py declaration_plans.py value_plans.py     from lsp/units.py, the root, object_values.py
    file_plans.py           today's, plus the judgement of gui/api.py (_addition, _removal, _judged, _appeared_since)
    views/                  variables, variable_keys less EDITORS, project_units, project_types, the rows of project_shared, grid (object_values.py), graph, findings_by_file
    session.py              gui/session.py, in neutral words; find_projects beside it
  lsp/                      the client: server, protocol, hover; queries.py (the jumps, about 260), quick_fixes.py (actions and spelling, text_edits, about 350), published.py (collect, _as_lsp, about 150), positions.py (about 70); an empty __init__
  gui/                      the client: server, api, routes, contract, queries, depth, derived; screens.py (route_of, Route, EDITORS, a row's cells, form orders); compare what is left of it
  cli.py                    the command line, imports the rest lazily, as it does
```

**What the guards should then say.** One test, `tests/test_layers.py`, walks every module of `src/ddd`, reads every import (top level, lazy,
relative, `from ddd import x`, `TYPE_CHECKING` apart) and refuses `importlib.import_module` outside `plugins.py`. A module not in the table fails it, so a new
module has to choose a layer.

| layer | may import |
| --- | --- |
| leaves | nothing of ddd |
| `models` | leaves |
| `diagnostics`, `ir`, `plugins`, `loading` | leaves, `models`, each other in that order; `plugins` names a backend only under `TYPE_CHECKING` |
| `compare`, `analysis`, `addresses`, `deliveries` | the above |
| `backends` | leaves, `models`, `ir`; c never a2l, a2l never c |
| `generating` | the above, and `backends` |
| `toolbox` | `compare` to `deliveries` and below; no backend |
| `editing` | `compare` to `deliveries` and below; no backend, no `toolbox`, no `generating` |
| `lsp`, `gui` | `editing` and below it; never each other, never `cli`, no backend |
| `cli` | anything, lazily |

Beside it: a sub-interpreter test that `import ddd.editing.*` leaves no `ddd.lsp`, `ddd.gui`, `http.server` or `jinja2` in `sys.modules`; a word guard that
`newText`, `as_uri`, `"uri"` occur only under `lsp/` and sockets only in `gui/server.py`; and a ban on tab, panel, page and row in the identifiers of
`ddd.editing`, in the manner of the one `ddd.models` already has for `uint16_t`.

#### The order of the moves

| # | move | removes | size |
| --- | --- | --- | --- |
| 0 | `tests/test_layers.py` as a ratchet: today's violations listed, the list only shrinks. `tests/conftest.py` stops importing the editors at module level | I4 | S |
| 1 | `lsp/__init__.py` empty; `editing.py` and `identity.py` import at the top. Tried on a scratch copy: 3,572 tests, nothing changes (`trial.txt`) | I2 | S |
| 2 | `lsp/ranges.py` to its home; `resolve_path` to a leaf; `EXIT_*` to `names.py`; `load_dictionary` to `deliveries.py`. Tried for `ranges.py`: 60 spellings, nothing changes (`trial.txt`) | M1, the SCCs | S |
| 3 | `identity.assign` through the engine; `file_kind()` in `loading`; `init_problem()`; member names in `occupied`; `ensure_ascii=False` | I6, M3, M4, M5, M6 | S |
| 4 | One `Plan`, one `PlanRefusal`, one `_answered()`; `project_of` and `unit_project` one function, asked only for `add` | I9, I10 | S to M |
| 5 | Split `lsp/navigation.py`, `lsp/diagnostics.py`, `lsp/discovery.py`: about 1,040 lines down, 62 src and 108 test references | I1 | M |
| 6 | Split `lsp/edits.py`, `lsp/units.py`: about 1,230 lines down, 49 src and 49 test references | I1 | M |
| 7 | `ddd/editing/` made; the root's plans and read models moved in (about 4,900 lines, mechanically); their docstrings lose the tabs; screens and fields to `gui/screens.py` | I1, I8 | M |
| 8 | The rules out of `gui/api.py` and `gui/session.py`; `Session` to `editing/session.py` | I3, M2 | M |
| 9 | One `resolved_project`, one `compare_deliveries`, `generating.py`; `gui/compare.py` shrinks to its words | I7, I3 | M |
| 10 | The layer table, the README table, `ddd/__init__.py`, `concept.rst`; the ratchet's list is empty by now and goes | I5 | S |
| 11 | The prose: planning artefacts, stale claims | M9, M10 | S |

About two to three weeks in all, L; moves 0 to 4 are a day or two and stand on their own. Each move is behaviour preserving, and 5 to 7 are mostly `sed`
and a full run. If the answer to open question 1 is no, I would stop after 4 and 10.

#### What I would leave exactly as it is, and why

- **`models/`, `ir.py`, `backends/`, `plugins.py`.** The strongest part of the design, measured clean; a third backend needs nothing changed. `elf.py`, `addresses.py`,
  `toolbox/` likewise: each is held to its row and keeps to it.
- **`analysis.py` as one module**, for the reason in the table.
- **`gui/server.py`** as the separate security edge; only its exit codes and its usage errors go back to `cli.py`.
- **`gui/contract.py`, `gui/queries.py`, `gui/routes.py`, `gui/depth.py`**: the wire, declared once, at the edge.
- **`lsp/protocol.py`, `lsp/hover.py`**: untouched for six weeks, and client through and through.
- **The engine's body** (`editing.py`), and `Session`'s threading: moved, not changed. **`_build_parser`** and `cli.py`'s lazy imports: long and right.
- **The rule that a plan is computed and not written**, every client previewing the same operations. It is the best idea in the edit layer, and the reason this can
  be fixed by moving things.

```candidates
2|I1|src/ddd/lsp/navigation.py:142|The edit layer has no home: 14 root modules and the GUI import ddd.lsp for their domain model, about 2,600 of its lines are not about a client
2|I2|src/ddd/lsp/__init__.py:12|Importing ddd.lsp.ranges loads the language server; two deferred imports hide a 12-module cycle; ddd id needs it
2|I3|src/ddd/gui/api.py:2203|Rules a second client needs live in the clients: file judgement, confinement, kinds, value parsing, generate; a batch removal breaks what the GUI refuses
2|I4|tests/test_backends.py:66|The import guards hold eight rules: 33 of 33 realistic violations pass, against cannot rot silently (KNOWN)
2|I5|docs/developer_documentation.rst:19|The layer table leaves out gui and 20 root modules, 39 % of the code, and three sentences about the rest no longer hold
2|I6|src/ddd/identity.py:198|ddd id --assign is a second edit engine: 600 and 444 left 644 on Linux, and it rewrites a file the loader refuses
2|I7|src/ddd/deliveries.py:136|Load, gate, analyse exists six times and compare then hooks three; the copies have diverged once already
2|I8|src/ddd/finding_routes.py:205|The UI's vocabulary is below the UI: screens, fields, panel orders and row cells in modules called pure and transport-neutral
2|I9|src/ddd/shared_plans.py:136|project_of parses every file on every Shared files keystroke, for nothing: 1.7 to 2.2 s at 1,200 components, where unit_project was fixed
2|I10|src/ddd/gui/api.py:797|Eight plan routes are one route copied, over five identical plan classes and six identical refusal classes (KNOWN in part)
2|M1|src/ddd/diagnostics.py:365|Two cycles through lazy imports and two small inversions: diagnostics to loading, gui.server to cli, loading to ir
2|M2|src/ddd/gui/api.py:140|gui/api.py imports four private names of gui/session.py
2|M3|src/ddd/declaration_plans.py:320|read_object and fixed_by re-serialise: a unit of °C is written \u00b0C, against values arrive as json text
2|M4|src/ddd/gui/session.py:933|What kind of file this is, answered five ways: a dump is types to the page, Upper.DDD.JSON is not listed
2|M5|src/ddd/object_values.py:501|A cell the plan takes and the file refuses: a whole number past 64 bits in a float object stops the component loading
2|M6|src/ddd/lsp/navigation.py:792|rename_problem takes a constant named as a structure member, and the next check refuses it
2|M7|src/ddd/finding_fixes.py:89|One id fix, two diffs: after the last key in the GUI, after name in ddd id and the editor
2|M8|src/ddd/lsp/navigation.py:50|31 regular expressions over pointer shapes in 7 modules, none owning them (KNOWN in part)
2|M9|src/ddd/gui/server.py:129|73 citations of planning artefacts in 25 modules that a future reader cannot resolve
2|M10|src/ddd/lsp/server.py:1|Docstrings the code has outgrown: six messages, nothing else reads them, a wrong docstring on _BASE_DATATYPES
2|M11|src/ddd/lsp/units.py:319|An index and a document cache threaded by hand, 126 annotations in 18 modules, with arguments nobody reads
```
