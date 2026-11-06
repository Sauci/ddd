## Pass 22: the test suite, periphery and GUI server

> **Read this first.** The suite is strong where a guard exists and blind where none does. Every
> guard earlier passes leaned on fires a test when it is removed (81 of 88 guard mutants killed),
> and the stratified campaign kills 83.9 % of 2,520 mutants (the core's, pass 21: 72.5 %). But not
> one of the ten failures passes 10, 13 and 19 found by hand has a test that fails on it, and each
> such test is 10 to 30 lines with the suite's own helpers (I1, probes ready in
> `SCRATCH/pass-22/probe-tree/tests/test_p22_probes.py`). Everything cited lives in
> `SCRATCH/pass-22/`; `notes.md` there is the working log, including one harness defect of mine and
> its repair.

### Scope covered

**Read in full, with line numbers**: `tests/conftest.py` (355), `tests/test_gui_hostile.py` (438),
`tests/test_gui_docs.py` (45). **Read in part**: `tests/test_editing.py:555-835`,
`tests/test_editing_at_once.py:1-140`, `tests/test_gui_session.py:1-460, 596-647`,
`tests/test_gui_server.py:296-535, 1031-1080, 2037-2060`, `tests/test_lsp.py:1-102, 196-235,
4293-4422, 4840-4969`, `tests/test_lsp_decisions.py:1-60`, `tests/test_cli.py:3000-3056`,
`tests/test_gui_api.py:1-40, 488-500, 2636-2652, 3192-3301, 6767-6886`,
`tests/test_type_plans.py:55-100`, `tests/test_variables.py:263-430`,
`tests/test_toolbox_from_elf.py:86-108`, `tests/test_documentation.py:3327-3346`,
`tests/test_transcripts.py:530-545`, `tests/test_plugins.py:2233-2242`; every class and test name of
`test_gui_server`, `test_lsp`'s `TestServer`, `test_gui_api`, `test_cli`, `test_plugins`,
`test_documentation`, `test_cmake`, `test_gui_depth`, `test_gui_derived`, `test_gui_contract`,
`test_elf`, `test_toolbox_from_elf`, `test_addresses`. Code read where a probe or a survivor needed
it: `src/ddd/editing.py:760-981`, `src/ddd/gui/server.py:160-935`, `src/ddd/gui/queries.py:60-274`,
`src/ddd/gui/session.py:440-589, 800-930`, `src/ddd/lsp/server.py:425-445, 540-560, 715-790`,
`src/ddd/cli.py:115-160, 322-331, 872-890, 1180-1228, 1471-1485`, the line of each of the 405
survivors and the context of about sixty of them.

**Not read**: the other 54,000 or so of the 57,194 lines of the 38 files (5,487 tests). They were
measured instead, by the guard mutants, the probes and the campaign, which asks every in-scope test
that reaches a mutated line. `tests/test_gui_api.py` (10,266 lines, 860 tests) was sampled by
mutating what it tests (`gui/api.py`, `contract.py`, `queries.py`: 308 mutants) and read at five
places only.

**Ran** (all on copies under `SCRATCH/pass-22/`; the suite ran twice in `base/`, and `diff -rq` of the
tree against `base/` afterwards shows no difference, so it writes nothing into its tree):

- The whole suite as a contributor runs it, one process: with the default options (coverage and its
  gate) 674 s wall (`timing/serial.txt`); with `--no-cov` 562 s, per file (`timing/nocov.xml`,
  `timing/per-file.txt`). Both runs had at most two mutation workers beside them.
- 36 null mutants under load: all survived, no false kill (`results-null.jsonl`).
- 88 hand-written guard mutants, one per guard earlier passes leaned on (`mkplanned.py`,
  `results-planned.jsonl`).
- Ten probe tests, one per hand-found defect (`probe-tree/tests/test_p22_probes.py`,
  `probes-run1.txt`); three of them again against crude fixes in a copy (`probe-fix/`).
- **The campaign**: pass 21's generator copied and pointed at 49 files in nine strata (cli with
  build_info and difflib_lock; plugins; lsp; gui-server: server, routes, depth; gui-session: session,
  compare, derived; gui-api: api, contract, queries; editing: editing, the five plan modules,
  object_values, identity; project: project_*, variables, variable_keys, finding_*,
  findings_by_file, graph, deliveries; elf: elf, addresses, toolbox/*): 13,211 sites, pass 21's
  rates and round-robin order (`sample.jsonl`, 7,880 planned, so any prefix is stratified). Each
  mutant asked with `-x` of the in-scope tests reaching its line in pass 21's line map
  (`linemap.pkl`; valid, `base/src` equals pass 21's and the tree's); a line only the import runs is
  asked of every test reaching its file. Twelve workers, stopped at 2,520 mutants with a real outcome
  (`runmut22.py`, `results-scope.jsonl`). Follow-ups: 47 module-level survivors and 12 unreached ones asked of every
  in-scope file naming the module, or a module naming it, whole (`results-importers.jsonl`); 28
  survivors of `cli.py`, `plugins.py` and `build_info.py` asked of `test_transcripts`, whose runs
  reach the tool through a subprocess the line map cannot see (`results-transcripts.jsonl`); 112
  asked of the tests outside the scope that reach their line (`results-rest.jsonl`).
- Effects of four survivors on a copy of the sources (`effect.py`, `eff/*.txt`, `x/pg14.txt`).

**A harness defect of mine, repaired**: from 07:49 to 07:54 a second runner on two spare workers
numbered its threads 0 and 1, so its pytest runs shared base-temp folders and logs with the main
campaign's workers 0 and 1, and a run starting wiped the other's `tmp_path`. That can only make
false kills. Every result of the window (rows 600-900) was asked again in a clean run
(`results-reask.jsonl`): 297 of 301 gave the same outcome, the 4 others were kills that became
survivals (two dataclass flags, `gui/server.py:163`, `type_plans.py:32`), and the new outcomes are
the ones counted. The runner now names every per-worker path by the worker.

**Not covered**: `test_cmake` was asked of no mutant (its 57 tests reach the tool only through
CMake, 228 s a run); 5,360 of the planned sample (the budget, stratified cut); 43 survivors read
but left unclear; a kill matrix without `-x`.

### Strengths

- **Every guard that exists has the test that fires it.** Of the 88 guard mutants, 81 are killed:
  all 11 of the edit engine's (the fingerprint check, the rollback, the stage, its removal, the
  file's access, a created file over an existing one, a file named twice, the retry), all 8 of the
  session's confinement, 9 of the 10 query path rules (network, dot segments, relative, NUL,
  device, sibling prefix, length; case folding survives, M4), 6 of the 7 language-server mutants
  (its refusals and the withdrawal of fixed findings; the cache forget survives, M4), the 3
  closed-pipe and interrupt handlers, and 44 of the 49 server gates - the token,
  the Bearer scheme, the cookie, the launch code spent, expired, compared by prefix, weakened,
  `Sec-Fetch-Site`, `Origin`, the content type, both body limits, `frame-ancestors`, `nosniff`,
  `Referrer-Policy`, the inline hash, every page-path rule, the cap, the lingering close, the IPv6
  hold and both exclusivities.
- **The campaign scores well above the core's**: 83.9 % of 2,520 (84.3 % of those a test reaches);
  every stratum between 77.1 % (cli) and 88.5 % (plugins); negated tests 166 of 167 (the other
  hung), deleted raises
  143 of 144, swapped arguments 141 of 144, comparisons 160 of 166, returns 150 of 157, deleted
  findings 11 of 11.
- **The heavy files earn their time.** `test_gui_api` runs last in every ask, so when it is the first
  to fail no other in-scope file reaching the line failed: it is the only killer of 169 mutants (110
  of the 268 kills in the gui-api stratum). `test_gui_server`, next to last, is the first killer of
  180.
- **Where a rule is written twice, the suite compares the two**, and those comparisons catch what the
  line map cannot select: the route table against the security page (`tests/test_gui_docs.py`, 8
  module-level survivors killed in the follow-up), the toolbox's severities against the guide
  (`tests/test_documentation.py:3341`, 3), `KEY_ORDER` against `PROPAGATED_KEYS`
  (`tests/test_variable_keys.py:92`, 2), every query model published (`tests/test_gui_api.py`, 2).
- **Isolation and hygiene hold**: no false kill among 36 null mutants and 88 guard mutants on twelve
  parallel copies with arbitrary subsets of tests; 297 of 301 re-asked mutants gave the same outcome,
  the four others explained above; one `time.sleep` in the 38 files, inside a deadline loop
  (`tests/test_gui_server.py:2053`); no coverage pragma anywhere in `src/ddd`, so the 100 % branch
  gate is real; the suite writes nothing into its tree.
- **Pass 11b's eighteen findings are fixed but two**, among them both Importants (table below).

### Issues

#### Critical

None. No survivor is a defect of today's code; each is a wrong program the suite would let through.
The defects that are present - passes 10, 13 and 19 - have no test, which is I1.

#### Important

- **I1. The suite pins each guard that exists and none of the hazards a guard misses: every failure
  passes 10, 13 and 19 found by hand fails a test of 10 to 30 lines built from the suite's own
  helpers, and no such test is in the suite.**
  `SCRATCH/pass-22/probe-tree/tests/test_p22_probes.py`, run on a copy of the tree
  (`probes-run1.txt`): 10 failed. Per defect, what the probe observes and the nearest test:

  | defect | probe observes on the tree | nearest test, and what it pins instead |
  | --- | --- | --- |
  | pass 13 C1 | the revision's fingerprint of `b.ddd.json` is that of the bytes saved after the analysis read it; an edit carrying it is not refused (`DID NOT RAISE`) | `tests/test_gui_session.py:368-408` use the same `saving_while_analysing` helper and assert only that the next poll finds the save; `tests/test_gui_api.py:6767-6886` move an entry after the analysis, for the read routes |
  | pass 13 I1 | a save landing between the check and the rename is overwritten: `{"x": 2}` where the other editor wrote `{"x": 9}`, answered written | `tests/test_editing.py:620-630` changes the file before `apply_changes`, the one moment the check covers |
  | pass 13 C2 | with a second writer staging under the one name, the edit answers written with the fingerprint of `{"x": 2}` while the file holds `{"x": 3}` | none has two writers; `tests/test_editing.py:718-719` pins the shared name (M1) |
  | pass 19 I3 | `ddd check examples/inconsistent/project.ddd.json` with both streams closed: exit 0, with and without `--format json` | `tests/test_cli.py:3035-3055` close the pipe on `ddd schema`, which has no verdict |
  | pass 10 I1 | `one/a.ddd.json`'s `missing-producer` is published `[]` once `two/b.ddd.json` is opened | `tests/test_lsp.py:4363-4391`: one project, its project file opened second |
  | pass 10 I2 | the demo's `event_logger.ddd.json` shows three `missing-producer` errors while `ddd check demo.ddd.json` prints `ok: 23 variables` | no server test opens a sub-project's component |
  | pass 10 I3 | F2 from `reader_one` in a two-image project edits `writer` and `reader_one`, not `reader_two` | `test_a_file_in_two_projects_is_edited_once`: two images do not send one edit twice |
  | pass 10 I4 | an open buffer's unsaved `"Speed"` is left out of the rename, answered with two files | the drift tests (`PL02`, `PL05` killed) cover a buffer that moved a declaration, not one that added a mention |

  Three of the probes pass once a crude fix is applied in a copy (`probe-fix/`: a stage name per
  write and the bytes compared again before the rename; withdrawing only the files this run reported
  on), so they test the defect and not something near it.
  Why it is structural: the guards the code has are tested one refusal at a time and every one fires
  (Strengths); what is never built is a second actor - a second writer, a save inside the window, a
  second project, a second image, a buffer that is not the disk, a stream that closes on a run with a
  verdict. Passes 9, 10, 13 and 19 named their own cases in their Test gaps; what this adds is that
  the ten tests are short, need no fixture the suite lacks, run in about a second, and fail today, so
  each fix can land with its test (S, about an hour each).

- **I2. The token exchange and the Host gate are each pinned by one wrong value, so two weakenings of
  the first defence pass the whole scope.**
  `src/ddd/gui/server.py:713` and `:630`; tests `tests/test_gui_server.py:432-434`
  (`{"token": "wrong"}`, the only wrong token `POST /open` is ever sent) and `TestWhoMayAsk` (one
  foreign host, `evil.example`, as pass 12's Test gaps said).
  - Mutant `PG14`, the `/open` token compared as a substring rather than with `compare_digest`:
    survives the 4 tests that reach the line. On a mutated copy (`x/pg14.txt`) an empty or a partial
    token is then accepted while `"wrong"` is still refused. The Bearer header is safe from the same
    weakening because `test_anything_else_is_unauthorised[no-token]` sends an empty one (`PG11`
    killed).
  - Mutant `PG02`, the Host compared by prefix (`127.0.0.1...`, `localhost...`, any port): survives
    all 206 tests that reach the line.
  Consequence: a regression that would hand the token, and with it code execution (pass 12 I2), to
  whatever reaches the port would go out green; the DNS-rebinding layer could weaken in silence.
  Change (S): parametrise the wrong token over the empty string, a prefix, a suffix and the token
  with one character changed; parametrise `Host` over the forms pass 12 tried by hand.

- **I3. What the page is told is pinned on the smallest case, so a first-or-last confusion in it
  passes: an undo offering the bottom of the stack, a doubled per-file warning count, a preview split
  wrongly.**
  - `src/ddd/gui/session.py:555`, the snapshot's undo entry `self._stack[-1]` read as `[0]`:
    survives 161 tests. Effect on a copy (`eff/undo-bottom.txt`): after two edits `GET /api/state`
    offers `{'at': 1, 'label': 'edit first'}`, and pressing it answers `409 stale: edit 1 is not the
    one to undo any more`. The snapshot is tested with an empty stack and with one entry
    (`tests/test_gui_session.py:947`), where first and last are one.
  - `src/ddd/gui/session.py:928`, `warnings=sum(1 ...)` read as `sum(2 ...)`: survives 1,258 tests.
    Effect (`eff/warnings-doubled.txt`): over `examples/inconsistent`, `component_a.ddd.json` is
    answered 2 warnings where `ddd check` has 1, the totals still 1. Only a file's errors are
    asserted (`tests/test_gui_session.py:291-292`); nothing reads its warnings or infos, which the
    Files tab and the module graph show (`src/ddd/gui/api.py:410, 1755`).
  - `src/ddd/variables.py:287-288`, the fast path claimed to answer "what difflib answers ... on every
    pair of texts" (`tests/test_variables.py:263-265`) merging runs on `runs[0]`: survives, because
    the eight hand cases (`:311-359`) never have a run of two lines after another run; no random
    comparison with the difflib oracle the file already holds.
  - The same shape elsewhere, read off the survivors: the first workspace folder answered for all
    (`src/ddd/lsp/server.py:482`, every test has one root; pass 10 M10), the worst of two severities
    on an arrow (`src/ddd/graph.py:59`, `key=` dropped survives 7 tests), a finding's place under an
    array element (`src/ddd/project_shared.py:361`, `src/ddd/project_types.py:226`).
  Pass 21 I6 found square, name-ordered, one-entry fixtures hiding index confusions in the core; this
  is the same on what the reader sees. Change (S): a second edit before the state is read, a file
  with a warning and an info in the state tests, a seeded random comparison against
  `_reference_hunks`.

#### Minor

- **M1. A test pins the shared stage name pass 13 C2 found deletes a description.**
  `tests/test_editing.py:718-719`, `test_edits_stage_under_the_name_every_other_writer_stages_under`:
  `assert STAGING_SUFFIX == ARTEFACT_STAGING_SUFFIX`. The fix pass 13 proposes, a stage name of its
  own per write, has to break this test, which states the hazard as a rule. Change (S): replace it
  with I1's C2 probe.
- **M2. The idle timeout is tested only through tests that replace it.** `src/ddd/gui/server.py:544`
  (`timeout = IDLE_SECONDS`); the three tests that close an idle connection set
  `module._Handler.timeout` to 0.05 or 0.5 first (`tests/test_gui_server.py:1644`, `:2040`, `:2395`)
  and no test reads `IDLE_SECONDS`. `PG35`, `timeout = None`, survives all 293 tests that reach
  `gui/server.py`, and `IDLE_SECONDS = 31` every in-scope file naming the module. The comment at `:2038-2039` says what is asserted
  "is that the socket carries one at all"; the monkeypatch is what gives it one. With the cap at 64
  (`:106`), idle connections would then hold every slot for good (adds to pass 12 M8). Change (S):
  assert `_Handler.timeout == IDLE_SECONDS` once.
- **M3. Several expectations are taken from the code under test.** The suite has a rule for this -
  "Pinned by its literal ... would drift along with any change to it" (`tests/test_gui_server.py:300,
  307, 349, 383, 467`) - applied to the token's strength and the code's lifetime but not to:
  the content security policy (`:1036` checks one substring, `:1053` equals `page_policy(...)`;
  `PG23`, `base-uri 'none'` dropped, survives 293 tests); the JSON-RPC codes
  (`tests/test_lsp.py:56-57, 159-162, 5474` import them; `METHOD_NOT_FOUND = -32600` and
  `REQUEST_FAILED = -32802`, `src/ddd/lsp/protocol.py:122, 141`, survive every in-scope file naming
  the module); `MAX_BODY` (`tests/test_gui_server.py:569`; `1024 * 1025` survives the same); the
  range of a finding on a whole first line (`src/ddd/lsp/diagnostics.py:401-402`: a range without
  its `character` key, or without its `end`, which a client cannot read, survives every importer
  file); the toolbox's
  severities (`tests/test_toolbox_from_elf.py:96-102` is parametrised over the table it tests; only
  the guide's copy, `tests/test_documentation.py:3341`, kills a change). Change (S): literals.
- **M4. Smaller guard survivors.** `PG48` (the 503's drain before closing,
  `src/ddd/gui/server.py:295`; without it the refusal can be lost to a reset, pass 12 M3), `PQ09`
  (`_CASELESS` on Windows, `src/ddd/gui/queries.py:74`: no test spells a served directory in another
  case, 1,177 tests reach it), `PL06` (`self._forget()` after a rename, `src/ddd/lsp/server.py:762`:
  no test asks the server again after a rename without a notification between).
- **M5. Positive paths no test takes, each a refusal or a column the reader would meet.** Setting an
  external type's `header` or a structure's `description` through a type plan
  (`src/ddd/type_plans.py:32-33`: dropping either key from `SETTABLE` survives every in-scope file
  naming the module, and dropping the external kind whole the 33 tests reaching the line;
  `tests/test_type_plans.py:72-84` asserts only the
  refusal's code and that the key is named, which a "not settable" refusal also does); a hover on a
  map's `y_axis` (`src/ddd/lsp/hover.py:43`, likewise); the Types tab's `bits` column
  (`src/ddd/project_types.py:44`, likewise); the Compare reply's renames with an entry
  (`src/ddd/gui/api.py:1501`: `entry["from"]` misspelt survives, since `tests/test_gui_api.py:4054`
  has none, though `tests/test_gui_compare.py:381` has one one level down); a stylesheet served
  (`src/ddd/gui/server.py:163`: `.css` as `text/html`, which under `nosniff` a browser will not
  apply, survives); `file-kind` as a load check (`src/ddd/lsp/navigation.py:113`) and the role words
  of an input (`src/ddd/variables.py:29`), both surviving every importer file; a backend answering a
  list with one stray item (`src/ddd/plugins.py:493`, `all` read as `any`); a dotted plugin whose
  package is missing (`src/ddd/plugins.py:239`); invalid UTF-8 in a DWARF string
  (`src/ddd/elf.py:864`, `errors="replace"` dropped survives 174 tests; adds to pass 11 M2); a
  big-endian DWARF-2 bitfield (`src/ddd/elf.py:787`; adds to pass 11's five). Each S.
- **M6. The command line's own guards.** `ddd id` without `--assign` (`src/ddd/cli.py:325-328`: the
  handler always assigns, `:1471-1485`, so `required=True`, whose help says "so that no run edits a
  file by accident", is the only guard; dropping it survives 426 tests and `test_transcripts`, since
  every `ddd id` test passes `--assign`); `--format` accepting anything (`:748`, choices dropped:
  `ddd check ... --format xml` prints text and exits 1 where the tree refuses it with exit 2,
  reproduced with `effect.py`); the byte order `generate a2l` writes with neither `--byte-order` nor
  `--image` (`:1224`, `BYTE_ORDERS[0]` read as `[-1]` survives 59 tests and `test_transcripts`;
  `tests/test_cli.py:3772-3773` pins the constant, `:4533, 4561` the image's order); port 65535
  (`:1627`).
- **M7. What only a separate process shows is pinned by nothing in the suite.** stdout reconfigured
  to UTF-8 (`src/ddd/cli.py:123`): deleting it survives 420 in-process tests, which replace the
  stream, and `test_transcripts`, which runs every documented command with `PYTHONUTF8=1`
  (`tests/test_transcripts.py:340`) - the one setting that makes the reconfigure redundant. The
  flush of `ddd gui`'s address line (`src/ddd/gui/server.py:1027`, `flush=True` dropped survives 16
  tests): the commits closing part 19c's hang (`a9405e57`, `2b704a7e`) are about this line reaching
  its reader, and only the journeys read it through a pipe. Change (S): one subprocess test per behaviour, without `PYTHONUTF8`.
- **M8. Two tests of `tests/test_gui_api.py` fail on a Windows without long paths, the default, so
  the gate is red out of the box with three failures here.** `tests/test_gui_api.py:2646-2651` and
  `:8515-8521` create a 243-byte name (`:496`), staged as 255 bytes, under `tmp_path`; with
  `LongPathsEnabled` 0 (this machine, `reg query ...\FileSystem`), any `tmp_path` puts the stage past
  260 characters and the edit is answered `500 unwritable` (`timing/serial.txt:100-134`); pytest's
  own default base directory is about 90 characters, so the two cannot pass on such a machine
  wherever they run; pass 21 saw the same three failures. The developer page names no long-path
  requirement (`docs/developer_documentation.rst:392-415`). Change (S): derive the longest name from
  the parent's length on Windows, or state the requirement.
- **M9. "A couple of minutes" is nine to eleven, two files are two thirds of it, and nothing smaller
  than a file can be asked for.** `docs/developer_documentation.rst:406` (pass 20 M11 found the
  sentence). Measured here, one process: 674 s with the default options, 562 s with `--no-cov`, of
  which `test_cmake` is 228 s (41.7 %, 57 tests) and `test_gui_server` 125 s (22.8 %, 346 tests at
  0.36 s each, spread evenly: 13 tests take over a second, 14 s together, so the cost is the
  fixture - a real server over a freshly analysed project per test - not a few slow tests); the
  other 6,639 tests take 195 s. No marker, no documented way to leave the two out, no
  `pytest-xdist` in `requirements-dev.txt`, and the coverage gate fails any partial run unless
  `--no-cov` is given. The isolation evidence above (twelve parallel copies, no false kill) says the
  suite would likely take to `-n auto`, bounded by `test_cmake`'s longest class (35 s,
  `TestAddressesFromTheImage`). Change (S): a `slow` marker on the two files, the developer page's
  numbers, and the file a module's tests live in (see open question 3).

### Status of the 2026-09-15 findings in this area

Pass 11b's eighteen; only those not plainly fixed:

| id | finding | status | where |
| --- | --- | --- | --- |
| P11B-M12 | core tests import helpers from `test_lsp` | half: `test_external` fixed, `test_constants` remains (pass 21 M8); three new imports between test modules: `test_cmake` from `test_cli`, `test_gui_compare` from `test_gui_api`, `test_lsp` from `test_variable_keys` | `tests/test_constants.py:1296`, `tests/test_cmake.py:44`, `tests/test_gui_compare.py:38`, `tests/test_lsp.py:78` |
| P11B-M14 | `test_cmake` configures the same trees again and again | partly: class-scoped fixtures now (`tests/test_cmake.py:238, 313, 822, 1149, 1498, 1656`); still 228 s, 42 % of the suite (M9) | `tests/test_cmake.py` |

Fixed: I1 (`tests/test_lsp.py:86-100`, publications keyed by the uri string), I2
(`tests/test_lsp.py:4587-4626`, `-b` reaching discovery), M1 (`tests/test_cli.py:184-192`), M2, M3
(`tests/test_lsp.py:204`), M4 (`tests/test_documentation.py:469, 549, 1007, 2001, 2308, 2316, 2323`),
M5 (`tests/test_transcripts.py:534-541`), M6 (`tests/test_documentation.py:397`), M7, M8, M9
(`tests/test_plugins.py:1878`), M10 (`tests/test_plugins.py:2240`), M11, M13
(`tests/test_cmake.py:1918`), M15 (`tests/test_example_plugin.py:38-46`), M16
(`editors/vscode/src/launch.test.ts:64-80`).

### Open questions

1. Is a second actor - a second writer, a save inside an analysis, a second project or image, an
   open buffer, a closed stream on a run with a verdict - something the suite must hold, as a rule?
   I1's probes show it can be done without threads or sleeps. The answer decides whether the fixes of
   passes 10, 13 and 19 land with their tests, and whether M1's test is a rule or a defect.
2. Is a stock Windows, without long paths, a supported development machine (M8)? If yes, two tests
   change; if no, the developer page says so.
3. Should a contributor be able to run "what matters" for a module in seconds - a `slow` marker on
   `test_cmake` and `test_gui_server`, `pytest-xdist`, a map from module to test files (the line map
   used here is one) - or is the whole suite before a commit the intended loop? The developer page's
   timing and advice follow the answer.

### Test gaps

**Mutation, against the 38 in-scope files.** 2,520 mutants with a real outcome of the 7,880 planned
(13,211 sites): 2,108 killed, 7 hung past 600 s (a ci job would hang), 393 survived, 12 reached by no
in-scope test, 0 invalid. Score, killed or hung over what ran: **83.9 %**; over what a test reaches,
**84.3 %**.

| stratum | ran | killed | hung | survived | unreached | score |
| --- | --- | --- | --- | --- | --- | --- |
| cli | 262 | 202 | 0 | 50 | 10 | 77.1 % |
| editing | 324 | 269 | 2 | 52 | 1 | 83.6 % |
| elf | 361 | 313 | 1 | 47 | 0 | 87.0 % |
| gui-api | 308 | 268 | 1 | 39 | 0 | 87.3 % |
| gui-server | 276 | 225 | 2 | 49 | 0 | 82.2 % |
| gui-session | 254 | 215 | 1 | 38 | 0 | 85.0 % |
| lsp | 316 | 253 | 0 | 62 | 1 | 80.1 % |
| plugins | 113 | 100 | 0 | 13 | 0 | 88.5 % |
| project | 306 | 263 | 0 | 43 | 0 | 85.9 % |

By operator, killed share: negated test 100 %, deleted raise 99 %, swapped arguments 98 %,
comparison 96 %, return 96 %, deleted statement 94 %, enum member 93 %, boolean 92 %, arithmetic
92 %, deleted flow 89 %, table entry swapped 86 %, string token 85 %, number 82 %, table entry
dropped 78 %, message 78 %, swapped function 75 %, index 62 %, dropped keyword 56 %, boolean
constant 40 % (the last three mostly flags and first-or-last on one element). Lowest files:
`gui/contract.py` 7 of 17, `type_plans.py` 11 of 16, `lsp/hover.py` 23 of 33, `graph.py` 16 of 22,
`lsp/diagnostics.py` 27 of 36, `lsp/navigation.py` 34 of 45, `cli.py` 203 of 260.

**`tests/test_gui_api.py`, sampled by mutation**: of the 308 mutants of what it tests, 268 killed,
39 survived; `gui/api.py` alone 182 of 206. `test_gui_api` is the first and only in-scope killer of
110 of the stratum's kills (169 across all strata), `test_gui_queries` of 90, the hostile walk of 34.
Its survivors are I3's counts, M5's renames, M3's route codes, and statuses of the 500 branch
(`src/ddd/gui/api.py:943, 1239`: 501 survives).

**The 405 survivors and unreached, each read** (`survivors.tsv`, `labels22.tsv`): 99 dataclass or
model flags; 83 equivalent (an index on one element, a code that is equal, a placeholder the
docstring says cannot matter); 55 help texts and messages; 20 cosmetic (an indent, an icon's type);
18 order (`sorted` dropped on name-ordered or set-derived data); 16 killed in a follow-up (8 by
`test_gui_docs`, 3 by `test_documentation`, 2 each by `test_variable_keys` and `test_gui_api`, 1 by
`test_hardening`); 11 unreached, 10 of them artefacts of the line map (tuple elements and keyword
defaults on lines of their own, `src/ddd/cli.py:255-268` among them, carry no line context, so no
test was asked: the six asked again whole all died, in `test_plugins` and `test_finding_fixes`,
the other six were not asked again); 2 performance only; 2 module-level not asked again; **43 unclear** (mostly
`gui/depth.py`'s walk and the session's wake conditions); **56 real gaps** - I3, M2, M3, M4, M5,
M6, M7, the 500 branch's statuses, and three boundaries (port 65535, a carriage return at offset 0,
`src/ddd/editing.py:136`; the escape of non-ASCII values written, `src/ddd/editing.py:718`, adds to
pass 2 M3).

**Effects reproduced**: the undo of the bottom (`eff/undo-bottom.txt`), the doubled warnings
(`eff/warnings-doubled.txt`), `--format xml` accepted (`effect.py` run, exit 1 against 2), the empty
token accepted under `PG14` (`x/pg14.txt`).

**Follow-ups.** Module-level survivors asked of every in-scope file naming the module or a module
naming it, whole: 47 asked, 16 died (above), 31 survive; then the unreached, 6 asked again before
the run was stopped, all 6 died (line-map artefacts: `test_plugins`, `test_finding_fixes`); the
other 6 were not asked. `cli.py`/`plugins.py` survivors asked of
`test_transcripts`: 28 asked, none died. Survivors asked of the tests outside the scope: 112 asked,
91 reached by none of them (this code is the periphery's own), 1 died (`cli.py:883` in
`test_hardening`), 20 survive.

**Harness caveats**, so the numbers are read right: a mutant was asked only of the in-scope tests
reaching its line, so a test reading a table without running a line of its module is missed until
the follow-up (16 such kills found); `test_cmake` and the subprocess half of `test_transcripts` and
`test_documentation` are invisible to the line map; timeouts are counted apart, not as kills; the
first-killer counts depend on the order files are asked in (cheap first, `test_gui_api` last).

**Gaps found, beyond those passes 9-14 and 19 listed**: the ten probes of I1 (each a ready test);
the wrong values of I2; a second edit, a warning count and a multi-line run (I3); the literals of M3;
the positive paths of M5; `ddd id` without `--assign`, an invalid `--format`, the default byte order
(M6); one subprocess run without `PYTHONUTF8` and one read of the address through a pipe (M7).

### Assessment

The periphery's suite is better than the core's by every measure this pass took: every guard the
code has fires a test when removed, 84 % of mutants die against the core's 72 %, the heavy files
are not redundant, and it is isolated enough to run on twelve copies at once without a false kill.
Its failure is of a different kind, and more serious than a score says: it tests what the code
already refuses, one refusal at a time, and never builds the second actor that every hand-found
defect of passes 10, 13 and 19 needs - a second writer, a save in the window, a second project or
image, a buffer unlike the disk, a closed stream on a failing run. Each of those ten defects fails a
short test written from the suite's own helpers, and none is there; one test even pins the shared
stage name behind pass 13's lost description. Around that, the gaps are the ordinary ones of a large
suite with one-entry fixtures and expectations read from the code under test: an undo that offers
the wrong edit, a doubled warning count, an empty token accepted by a weakened compare, all green.
The runtime is honest but undocumented: nine to eleven minutes in one process, two thirds of it in
two files, and no smaller loop offered. 100 % coverage here means every line ran; it does not mean
the hazards the reader of passes 10 and 13 met were ever tried.

```candidates
22|I1|tests/test_gui_session.py:368|Suite pins every guard that exists, no hazard a guard misses: the ten hand-found failures of passes 10, 13, 19 each fail a 10-30 line probe
22|I2|tests/test_gui_server.py:432|Token exchange and Host gate each pinned by one wrong value: a substring token compare and a prefix Host check pass the whole scope
22|I3|src/ddd/gui/session.py:555|What the page is told pinned on the smallest case: an undo of the stack's bottom, doubled per-file warnings, hunks of two runs pass
22|M1|tests/test_editing.py:718|A test pins the shared stage name pass 13 C2 found deletes a description
22|M2|tests/test_gui_server.py:2040|Idle timeout tested only by tests that replace it: timeout None passes 293 tests
22|M3|tests/test_gui_server.py:1036|Expectations taken from the code under test: CSP, JSON-RPC codes, MAX_BODY, the whole-first-line range, the toolbox severities
22|M4|src/ddd/gui/server.py:295|Smaller guard survivors: the 503 drain, Windows case folding of served paths, the LSP cache after a rename
22|M5|src/ddd/type_plans.py:32|Positive paths no test takes: an external's header, y_axis hover, bits column, Compare renames, a stylesheet, invalid UTF-8 in DWARF
22|M6|src/ddd/cli.py:328|Command-line guards unpinned: ddd id without --assign edits, --format accepts anything, the default a2l byte order
22|M7|src/ddd/cli.py:123|What only a separate process shows is pinned by nothing: stdout's UTF-8 (transcripts set PYTHONUTF8), the address line's flush
22|M8|tests/test_gui_api.py:2646|Two longest-name tests fail on any Windows without long paths, so the gate is red out of the box here
22|M9|docs/developer_documentation.rst:406|A couple of minutes is nine to eleven, two files are two thirds of it, no smaller loop offered
```
