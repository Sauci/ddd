## Pass 10: editor integration (SPEC 7.2)

Paths are on the review tree. `t/x.txt` means `SCRATCH/pass-10/transcripts/x.txt`; the probes are `SCRATCH/pass-10/*.py`, driven by `SCRATCH/pass-10/lspc.py` (the real `ddd.exe lsp` on pipes, a client that holds buffers, sends the `file:///c%3A/...` spelling, applies a workspace edit as an editor does: refuses an overlap and a stale version, opens a file it does not hold, keys what it draws on the normalised uri).

### Scope covered

Read in full, line by line: `src/ddd/lsp/__init__.py`, `protocol.py`, `server.py`, `discovery.py`, `diagnostics.py`, `navigation.py`, `ranges.py`, `edits.py`, `hover.py`, `units.py` (4952 lines); `editors/vscode/package.json`, `src/extension.ts`, `src/config.ts`, `src/config.test.ts`, `src/launch.test.ts`, `README.md`, `.vscodeignore`; `docs/editor_integration.rst` (all); `SPEC.md:2341-2476`; `README.md:140-244`; `src/ddd/editing.py:1-790`, `src/ddd/identity.py`, `src/ddd/value_identity.py`, `src/ddd/cli.py:333-357, 1600-1606`, `src/ddd/models/objects.py` (the keys and rules a fix relies on), `src/ddd/analysis.py:1745-1930`; `docs/superpowers/plans/2026-09-16-review-fixes.md:426-479`, `2026-09-25-gui-mismatch-fix.md:1360-1474`; the previous review's pass 6 in full and its other sections by grep. Of `tests/test_lsp.py` (7395 lines): the class list, `:1-200, 2795-2870, 4920-4980, 7315-7396` and greps for what is pinned; pass 22 owns the rest.

Ran:
- `s01`-`s06`, `s12`-`s14`, `s17`, `s19`, `s22`: edit sequences, multi-file renames, unsaved buffers, files changing under the server, broken files, sub-projects, two images, junctions, odd uris.
- `s07`: all five requests at every token of six examples, 29,990 requests. `s09`: each file of three examples broken six ways, 84 variants, six request kinds, 67,368 requests. `s08`, `s21`: malformed messages, odd buffers and files, 1,500 init and shape variants under a hover.
- `s11`: 87 renames of five kinds onto tricky names with `ddd check` as oracle. `s16`: every quick fix between 338 pairs of declarations, 1,688 actions applied, oracle the loader and the analysis. `s18`: 330 unit plans rendered as text edits against `edit_text`.
- `s15`, `s20`: costs on generated projects up to 36,000 declarations.
- `tests/test_lsp.py tests/test_lsp_decisions.py`: one failure, the known symlink one. The extension's seven tests (`config.test.ts`, `launch.test.ts`), compiled in scratch with `gui/node_modules/.bin/tsc`: pass.

What the client does was read, not run, from local copies: `vscode-languageclient` 9.x as bundled in `llvm-vs-code-extensions.vscode-clangd-0.6.0/out/bundle.js` (the lock pins 9.0.1, the bundle declares `^9.0.1`), and `Microsoft VS Code/261c84cb1e/.../workbench.desktop.main.js`.

Not covered: `extension.ts` was neither compiled nor run (no `node_modules` in `editors/vscode`, and no download), so no session in a real VS Code. No other editor. Nothing on Linux or macOS; a `subst` drive was not re-run, its path is the junction's.

### Strengths

- **An edit lands where it should.** Positions and edits come from the buffer: emoji, tabs, CRLF, a BOM, lines typed above, two fixes in a row unsaved (`t/s17_more.txt`, `t/s02_rename_buffers.txt` W); versions are right; no client refusal for an overlap in 1,688 actions.
- **The unit plans are what they claim.** 330 random plans over random layouts, CRLF included, escapes in the spelling: `text_edits` and `edit_text` gave the same bytes every time (`t/s18_unit_diff.txt`). "An editor and `ddd gui` write the same bytes" holds there.
- **The server survives what a project throws at it, nearly.** 97,358 requests over intact and broken projects, zero deaths in `s07` and `s09`; files nested 200,000 levels deep, NaN, 5,000 digits, invalid utf-8, a directory named like a description: all findings or nothing (`t/s08_robust.txt`). What does kill it is I13 and M1.
- **The refusals it has are right.** A moved declaration refuses a rename; a file that did not load refuses a variable's and a unit's rename; duplicated vocabulary entries are refused (`t/s17_more.txt`). `rename_problem` agreed with the next `ddd check` on every name of `s11` but the raster alphabet (I9) and a constant named as a member (pass 2 M6, seen again).
- **P6-C1 is gone in the shape it was filed.** A project file opened alone shows the whole `ddd check` set, opened before or after a component (`t/s12_previous_critical.txt` 1-2).
- The extension is the launcher it says it is, plus one watcher (M8), and its trust gate is as documented.

### Issues

#### Critical

None. I1 is the same class as last review's Critical, but `ddd check` and the build still fail, so nothing ships. I9 is literally a corrupted file, but on unusual input and it shows at once. I10 is wrong C with every gate green, on a rare trigger. Each is graded Important below with that said; verification may disagree.

#### Important

- **I1. Findings of every other project are withdrawn at each refresh: a file with a real error reads clean until it is saved again.**
  `src/ddd/lsp/server.py:553-555`, `:436-437`. `refresh` publishes `current | self._published` and treats a file absent from this run's report as fixed, while `collect` (`diagnostics.py:254-277`) only looks at the build records and the one document. With no record covering it, a file outside the document's project gets an empty list.
  Triggers and what is on screen:
  - Two projects, no record: open `a` (`missing-producer`), open `b`: `a`'s finding is gone; save `a`: `b`'s is gone. Both errors are in `ddd check` throughout (`t/s01_withdrawn.txt` 1-5).
  - Two loose components: `duplicate-declaration` on `one` vanishes when `two` is opened (`s01` 6-7).
  - Project file not above its components (`project/p.ddd.json`, `components/*.ddd.json`): project open shows 6 findings; opening a component it lists empties the screen, and the hover says "*No component produces this.*" (`t/s12_previous_critical.txt` 3).
  - A watch event with several documents open: each refresh erases the last, so only the last in sort order keeps its findings (`s01` 5).
  - Nothing open, a pull that changes a file and deletes another: all real findings withdrawn and a phantom `file-not-found` published on the deleted file; `ddd check` says `definition-mismatch` (`t/s03_projects.txt` K, K2).
  Contradicts `docs/editor_integration.rst:8-10` "the editor never disagrees with the build" and `SPEC.md:2345-2346`. This is the surviving half of P6-C1's "opening it withdraws them". Change (S): withdraw only files this run reported on, `self._published & set(reports)`, and do not `refresh` a deleted path.

- **I2. The nearest project answers for the whole project: in the repository's own demo a clean tree shows false errors, and a rename breaks it.**
  `src/ddd/lsp/navigation.py:546-549`, whose comment has it backwards: "one further up as well is a sub-project of it" - the nearer one is the sub-project. Stated by `SPEC.md:2391-2394` and `README.md:239`, against `SPEC.md:2345-2346`.
  Trigger: a copy of `examples/demo`, no record, open `subsystems/logging/event_logger.ddd.json`. `ddd check demo.ddd.json` is exit 0; published: three `missing-producer` errors and an `unused-output`. Hover on `ValueE`: "*No component produces this.*". Definition: `[]`. Rename: touches `event_logger.ddd.json` alone, after which `ddd check demo.ddd.json` is exit 1 (`t/s04_demo_subproject.txt`). The sub-project file itself is checked under the top project, its component under the sub-project, in one session (`t/s03_projects.txt` H, H3).
  Change (S-M): walk to the root and answer from the outermost description that includes the document, which also drops a sub-project found first. Cost: the candidates above are already loaded on a miss. The SPEC sentence changes with it.

- **I3. In a two-image project a rename's reach depends on the file it starts from, and started from a reader it half-renames the other image.**
  `src/ddd/lsp/server.py:743`, `:783`: only projects containing the document are visited.
  Trigger: `writer` in images `one` and `two`, `reader_one` and `reader_two`, two records. F2 on `Speed` in `reader_one`: edits `writer` and `reader_one`. `ddd check two` goes from exit 0 to `missing-producer` on `reader_two`. The same rename from `writer` reaches all three (`t/s03_projects.txt` I, I2).
  Read off the same lines: a section's, a raster's and a unit's rename, and "Apply this unit", have this reach. Contradicts `editors/vscode/README.md:94` "rather than half applied" and `README.md:220-224`; this setup is SPEC 7.2's own example of a shared component.
  Change (M): after computing the edits, take every project containing a touched file, repeat until no new one appears, then rename across them or refuse naming the image.

- **I4. A rename sees the disk: what a buffer added is invisible, so it half-renames, merges, or quietly does nothing.**
  `src/ddd/lsp/server.py:740-763`, `navigation.py:885-900`, `units.py:547-566`. The drift check asks only whether each disk site still holds the name.
  - An unsaved new mention keeps the old name: an axis with `"input": "Speed"` typed and unsaved, F2 to `Velocity`, accepted; after the save `unknown-reference` (`t/s02_rename_buffers.txt` D). A new unsaved stating of a unit likewise (`t/s06_units.txt` "unsaved extra stating").
  - F2 on a name only the buffer holds: `prepareRename` opens the box, `rename` answers `{"documentChanges": []}`. This is the second of two renames in a row whenever the first stayed unsaved, and VS Code auto-saves a refactoring only past one file (`u.length>1` in its bulk edit), so every local variable. An empty edit is applied silently (`t.length===0` returns `isApplied:false`). `server.py:720-721` calls this exactly what a refusal exists to prevent (`s02` E). With no subject under the caret and no prepare, the same empty answer (`s02` Y).
  - F2 onto a name only a buffer declares passes `rename_problem`; the result is a `duplicate-declaration`, and with an input in another file it is the silent merge `SPEC.md:2357-2358` refuses (`s02` F).
  `docs/editor_integration.rst:124-128` promises the refusal only for moved declarations, so this is a hole in the guard rather than a broken sentence, except for the empty edit.
  Change (S): refuse while any open document of the project parses to something other than its file on disk, naming it, and turn an empty answer into a refusal.

- **I5. With no project known, F2 on a shared variable rewrites one file and says nothing.**
  `src/ddd/lsp/navigation.py:459-462`, `server.py:743-763`.
  Trigger: `writer` and `reader` in one folder with no project file, or a fresh clone of a collected CMake project before its first configure, or a build directory not named `build`, `out` or `cmake-build-*`. F2 on an `output`: one edit in `writer` (`t/s02_rename_buffers.txt` Q). The only trace is the log line "no ddd-build.json found", which does not mention edits.
  Contradicts `docs/editor_integration.rst:82-83` "across as many files as that takes". Change (S): in the alone case refuse any rename but a `local`'s, saying no project is known.

- **I6. While a file of the project does not load, every caret move in every description raises an error toast, and the reason never reaches it.**
  `src/ddd/lsp/server.py:854-855` answers `textDocument/codeAction` with `REQUEST_FAILED`, and the comment at `:847-849` knows a client asks at every move of the caret. Reproduced: error at every position, in the broken file and the others (`t/s05_quickfix.txt` last block); `examples/layout` with its plugin not importable answers 228 of 228 that way (`t/s07_sweep.txt`), though "stopped the project reading it" is untrue of those files.
  Read off the client: `handleFailedRequest(ui.CodeActionRequest.type,h,w,null)` takes `showNotification` by default, unlike rename's `!1`, and `error()` calls `showErrorMessage("Request textDocument/codeAction failed.", "Go to output")` because `revealOutputChannelOn` defaults to `Error` and `extension.ts:48-55` does not set it. So the user fixing a schema error gets a toast per caret move, naming no file; the sentence the docs promise (`docs/editor_integration.rst:124-128` "naming the file") is in the output channel only.
  `tests/test_lsp.py:4967` pins the error. Change (S): answer `[]` and say it once with `window/logMessage`, or `window/showMessage` when a finding was sent.

- **I7. A quick fix can write a file the loader refuses, often the preferred one, and then the project stops being analysed and every further fix is refused.**
  `src/ddd/lsp/edits.py:541-560` (`settled_at` knows storage and kind, and no rule between keys).
  Reproduced by applying every action: 143 of 1,688 (8.5 %) leave a `schema` error (`t/s16_fix_matrix.txt`). Example: writer `float32`/identity, reader `uint8`/enum: the preferred "Use the datatype declared in w" gives "enum conversion 'Mode_t' requires an integer datatype"; step 1 is then "code action refused" (`t/s05_quickfix.txt` s05b). Likewise "Apply this conversion" onto a float writer, string conversions against a unit, limits, non-byte datatype or missing dimensions, and "Remove this dimensions" on a string.
  Contradicts `src/ddd/models/objects.py:953-955` "what stops it offering an edit that produces a file the loader then refuses". The plan's ruling (`2026-09-25-gui-mismatch-fix.md:1466-1473`) closed only the storage half. `settled_at` is shared with `ddd gui`'s fix; `variables.py:304` guards storage alone, for pass 14 to try there.
  Change (S-M): validate the definition with the key applied before answering `Settled`; withhold otherwise.

- **I8. A named type is read as silence: the preferred fix removes a key, settles nothing, and its title is untrue.**
  `src/ddd/lsp/edits.py:752-754`, `:805-815`, `:845-848`. Raw text is read where the resolved value is meant.
  - Writer `typename: Speed_t` (type states `rpm`), reader `unit: krpm`: only offer is "Remove this unit, which w does not declare", `isPreferred`, carrying the finding; after it `unit: '' != 'rpm'` (`t/s05_quickfix.txt` s05e).
  - Writer `unit: rpm`, reader `typename` stating `krpm`: "Remove the unit from 1 other declaration", preferred, strips the producer; after it `'krpm' != ''` (`t/s13_misc.txt` b). `_remove_elsewhere`'s docstring says this was fixed; the code checks `changes` and not `unsettled`.
  Change (S): read the producer's key through its type, and offer no removal when `settlement.unsettled` holds a type.

- **I9. A raster rename writes the new name raw between the quotes, so a quote or backslash corrupts every file it touches.**
  `src/ddd/lsp/navigation.py:900` `{"range": span, "newText": name}`; `_raster_problem` admits `RASTER_NAME_PATTERN` (`models/common.py:131`, printable ASCII, stated at `docs/editor_integration.rst:107-108`).
  Reproduced: `a"b`: accepted, `json-syntax` in the rasters file and the components, whole project unanalysed. `a\b`: writes a backspace, `schema`. `a\nb`: a line feed, `schema` (`t/s11_rename_oracle.txt`). A stray quote typed in the box is enough. The unit path escapes (`units.py:507`); this one has no read-back. Tests stop at `rename_problem` (`tests/test_lsp.py:2859-2866`). Change (S): `json.dumps(name, ensure_ascii=False)[1:-1]`.

- **I10. Renaming a constant leaves a `condition` spelling it: the object is compiled out with every gate green.**
  `src/ddd/lsp/navigation.py:744-748`; `SPEC.md:2354` "everywhere the project writes it".
  Trigger: `"condition": "CELLS > 2"`, F2 on `CELLS` to `SLOTS`: two edits, the condition untouched (`t/s13_misc.txt` d). `ddd check` exit 0; `gcc -std=c11 -Wall -Wextra -Werror` passes (`docker/compile.sh` has no `-Wundef`); `#if CELLS > 2` is false, so `Big` is gone from the C while the a2l still names it. Reproduced: `SCRATCH/pass-10/p/s13d/gen/ddd_globals.c:21`. The examples' conditions are only `defined(...)`, so the trigger is rare, and the page's Shared files rename uses the same `rename_sites`.
  Change (S): refuse, or rewrite, when a condition holds the identifier as a word.

- **I11. "VS Code shows the multi-file edit in a preview first, so nothing changes without being seen" is false: it is applied and saved at once.**
  `editors/vscode/README.md:87-88`, and the design reason at `src/ddd/lsp/edits.py:8-10`.
  Read off VS Code's workbench: applying a code action passes `showPreview:t?.preview`, set only for the explicit preview gesture; the bulk edit previews only on that or `needsConfirmation`, which the server never sends; and past one file `files.refactoring.autoSave` (default true) saves them all. So "Apply this unit to 2 other declarations" rewrites and saves two other components unseen.
  Change (S): send `changeAnnotations` with `needsConfirmation` on a multi-file fix, which makes the sentence true, or correct both places.

- **I12. A save costs one analysis plus one per open document, every hover a full analysis, and a rename across N files about 2N.**
  `src/ddd/lsp/server.py:436-437`, `:333`, `:338-339`; `src/ddd/lsp/hover.py:99`. The extension's watcher fires on the editor's own saves, so every save is a `didSave` and a watch event.
  Measured (`t/s15_perf.txt`, `t/s20_perf2.txt`):
  - 6,000 declarations, ten tabs: `didSave` 0.58 s, its watch event 5.91 s.
  - 36,000 declarations, five tabs: `didSave` 3.98 s, watch event 20.13 s; every hover 1.91 s, the first 4.02 s.
  - Rename as VS Code applies it, 61 files: 60 `didOpen` 11.06 s, 61 `didSave` 14.26 s. 201 files: 411 s with the watch batch arriving while the models are open.
  The loop is single threaded, so hovers and renames queue behind it. These are the sizes `tools/bench_gui.py` holds the page to; nothing holds the server.
  Change (S): analyse once per distinct project in a refresh, coalesce queued `didOpen`/`didSave`, keep the resolved dictionary until `_forget`.

- **I13. A hover or a hand-made record ends the session, because there is no net by decision.**
  `src/ddd/lsp/server.py:8-12` ("a thing the design already prevents"), `:265-277`; `hover.py:81-82`, `:60-63`; `server.py:380`.
  - A parameter with `"init": []`: `ddd check` gives one `init-invalid`, a hover gives exit 2 `ddd: range() arg 3 must not be zero` (`t/s21b_init_empty.txt`, 27 cases in `t/s21_hover_inits.txt`).
  - A valid project (`ddd check` exit 0), float64 block with init `[-1.7e308, 1.7e308, 0]`: a hover gives exit 2 `ddd: cannot convert float NaN to integer` (`t/s10_hover_truth.txt`).
  - A record with a relative `project` and an unknown plugin check: exit 2 on the first `didOpen`, `relative path can't be expressed as a file URI` (`t/s13_misc.txt` g); `_uri` calls `as_uri()` even when the client's spelling exists, and a relative record is otherwise accepted.
  The client restarts the server and gives up after five crashes in three minutes, taking every finding with it, and the hover is what kills it again.
  Change (S): wrap each request, answer `-32603`, write the trace to stderr, keep the session. That hides nothing the docstring fears; fix the three triggers besides. Also see the open question.

#### Minor

- **M1. The server dies on malformed params that `_field` says it refuses.** `src/ddd/lsp/server.py:147` "Every field a handler reads goes through here", against `:846-850` (`diagnostics: null`, `3`, `[1]`), `:325` and `:866-879` (`params: [1]`, `rootUri: 3`, `workspaceFolders: 3`), `ranges.py:165-166` (`line: -1000`, `IndexError`), and `%00` in a uri (`ddd: embedded null character`). All exit with a traceback or exit 2 (`t/s08_robust.txt`). Against `SPEC.md:2450-2452`. VS Code sends none of them; P6-M1 and P6-M2's neighbours.
- **M2. A quick fix under a moved buffer is performed in part, where the SPEC says refused whole.** `SPEC.md:2364-2367`, `README.md:220-222`, `docs/editor_integration.rst:124-127`; `src/ddd/lsp/edits.py:877-898` leaves it out. Trigger: V moved in `r2`'s buffer; at the writer "Apply this unit to 1 other declaration" touching `r1` alone, while the rename beside it is refused (`t/s13_misc.txt` a). The count in the title is honest; the documents or the code should change.
- **M3. In two images every action is offered twice.** `src/ddd/lsp/server.py:852-859`, no `_gather` here. `["Use the unit declared in writer", "Apply this unit...", "Use the unit declared in writer", "Apply this unit..."]`, both preferred (`t/s03_projects.txt` I3).
- **M4. The hover says things the project does not.** `src/ddd/lsp/hover.py:97-103`, `:315-320`. Writer in two images: "read by **ReaderOne**" while references lists `reader_two` too. Reader's file did not load: "read by *nobody*". Writer's file did not load: "*No component produces this.*", definition `[]`. Two writers: "Written by **W1**" (`t/s19_small.txt`, `t/s10_hover_truth.txt`). The remainder of P6-I3; one line naming what did not load would do.
- **M5. Two leftovers of the client's spelling.** `src/ddd/lsp/server.py:378-380`, `:553-555`: through a junction, a file published under its resolved uri and later opened under the junction keeps the old set on screen for good: fixed and saved, `real/r.ddd.json` still holds 2 findings (`t/s14_spelling.txt`). `src/ddd/lsp/edits.py:339` with `server.py:840`: `here` keeps the unresolved path, so it equals no index site: "Remove this unit" is lost at the producer, and the order is computed as a consumer's (`s14` "w's Only"). `path.resolve()` there, and withdraw under the old spelling.
- **M6. A squiggle lands on the wrong key of a dirty buffer.** `src/ddd/lsp/diagnostics.py:251`, `:362`: ranges are the disk's. Five lines typed above, unsaved, then another file saved: `r`'s finding at line 7, which in the buffer is `"name": "R"` (`t/s13_misc.txt` e). Also a restored dirty buffer at `didOpen`. `SPEC.md:2423` says the findings are the disk's, not that they may be drawn elsewhere.
- **M7. `onLanguage:json` starts the server for any json file.** `editors/vscode/package.json:35`: `ddd lsp` runs in every workspace where a json file opens, and with `ddd` missing the error popup appears there. P6-M8's second half, still open.
- **M8. The watcher is the extension's, so other editors go stale, and the record is not watched.** `editors/vscode/src/extension.ts:54`; the server never sends `client/registerCapability`. `README.md:153-154` "works the same either way" and `SPEC.md:2470-2472` "shall do no more than launch": Neovim, Helix and Emacs get no branch-switch refresh and a stale index under a rename (`t/s02_rename_buffers.txt` F2). `**/*.ddd.json` also misses `ddd-build.json`: a configure that writes only the record leaves the old severities until the next save (`t/s19_small.txt`). Register the watcher from the server, including the record. A change of `ddd.buildDirectories` needs a restart, which nothing says.
- **M9. An external type can be renamed.** `src/ddd/lsp/navigation.py:706-707`. `DriverStatus_t` in `examples/structures`: accepted, `ddd check` exit 0, the vendor's header still defines the old name (`t/s13_misc.txt` c). The name is not DDD's to choose; the compiler stops the build.
- **M10. Folders added later are not followed.** `src/ddd/lsp/server.py:885-900` announces no `workspaceFolders`; a document in a folder added after `initialize` gets `missing-id` only, against `missing-producer` and `unused-output`, with no new log line (`t/s03_projects.txt` M). A relative `-b` is read in the first folder alone (the client's `_mainGetRootPath`), where `docs/editor_integration.rst:172-173` says "the workspace folder".
- **M11. Rendering a unit plan is quadratic, and it runs on a caret move.** `src/ddd/lsp/units.py:569-583` rescans per operation, and commit `3ddc8115` fixed the engine's path, not this one. Rename, one file: 500 statings 5.34 s, 2,000 103.57 s, 8,000 no answer in 300 s (`t/s15_perf.txt`). `edits.py:445-446` renders every candidate eagerly: 16.87 s per code action on an unknown unit stated 500 times (`t/s20_perf2.txt`). `codeAction/resolve` would defer it.
- **M12. Small untrue sentences.** "r.ddd.json has unsaved changes that moved a declaration" for a closed file changed on disk before the watch event (`server.py:830`, `t/s22_stale.txt`). Every action of a declaration carries all its mismatch findings, though one key settles one (`edits.py:265-269`, against the docstring at `:112-116`; `t/s05_quickfix.txt` s05d). "the full range of the datatype" on a `uint8` enum reading `0 .. 1` (`hover.py:328-332`). `docs/editor_integration.rst:119` "only while a file ... does not load" omits the moved unit's refusal, and `:124` omits a raster. A fix into a closed CRLF file carries `\n` (`ranges.py:276` reads through universal newlines, `editing.py:126`); VS Code normalises, another client mixes (`t/s17_more.txt`).

Seen again, not re-filed: pass 2 M6 (`t/s11_rename_oracle.txt`, constant to `field`, then `name-collision`), I1, I2, M10; pass 3 I2; pass 4 M10, M11; pass 9 M2.

### Status of the 2026-09-15 findings in this area

Only those not plainly fixed. Fixed and checked: P6-I2 (`navigation.py:541`), I4 (`discovery.py:108-112`), I5 (`navigation.py:60-62`), I6 (`diagnostics.py:304-316`), M3, M4, M5, M6, M7, M9, M10, M11, M12, M14, M15, M16; P8-I1 (`ranges.py:108`).

| id | finding | status | where |
| --- | --- | --- | --- |
| P6-C1 | project file opened with no record: checks silenced, and withdrawn from the components | FIXED as filed (`diagnostics.py:149-151`, `t/s12_previous_critical.txt` 1-2); the withdrawal STILL OPEN in other shapes | I1, I2 |
| P6-I1 | published under the resolved path | FIXED for what is open (`server.py:378-384`); a leftover | M5 |
| P6-I3 | rename and fix computed around a file that did not load | FIXED for rename and fix (`server.py:744`, `:854`), though the refusal reaches a user as I6; the hover's half STILL OPEN | I6, M4 |
| P6-M1 | `codeAction` with `context: null` ends the server | FIXED for `context`; `diagnostics: null` on the next line STILL ends it | M1 |
| P6-M2 | a folder entry without `uri` ends the server | FIXED for that; `rootUri: 3`, `workspaceFolders: 3` STILL end it | M1 |
| P6-M8 | watcher dropped; `onLanguage:json` | watcher FIXED (`server.py:340`); `onLanguage:json` STILL OPEN | M7 |
| P6-M13 | work repeated per save and first request | the double read FIXED (`diagnostics.py:161-177`); a new repetition, per open document | I12 |

### Open questions

1. **A net or no net?** `server.py:8-12` rejects a catch-all because it "would hide" a defect. A guard that answers `-32603` and writes the trace to stderr hides nothing and keeps the reader's findings; three project-side triggers show the premise does not hold. If the answer stays no, the document should say a defect ends the session, and the extension's error handler should say which.
2. **What does a rename mean across images?** Extend to every project holding a touched file, or refuse naming the image? Extending writes files of an image nobody asked about; refusing makes a rename in a shared component impossible from a reader. Decides I3.
3. **Nearest or outermost project?** SPEC says nearest (`SPEC.md:2393`). Outermost fixes I2 but answers with the widest project where a sub-project is sometimes built alone. A record still wins either way.
4. **Should a dirty project refuse edits outright?** "Any open document differing from disk" (I4) is simple and sound, but refuses a rename whenever any tab has an unsaved typo. Indexing from buffers avoids that and is a larger change, since the loader reads files (L).
5. **Should a multi-file quick fix ask?** `needsConfirmation` makes the README true at one extra click on every fix; correcting the README keeps the one press. Decides I11.
6. **Is the watcher a launcher's job?** If the server registers it, SPEC's "shall do no more" holds and other editors gain it, at the cost of a capability the client must support (M8).

### Test gaps

- A second project, a loose file, a project not above its components: what is withdrawn. `tests/test_lsp.py:4363` has only the project-file order; all of I1's triggers are untested. So is `_watched` with two open documents of two projects, and with a deleted path.
- A nested project with no record (I2): nothing runs `examples/demo`'s sub-project through the server, though the sweep over it would have shown the false errors.
- A rename from a non-shared file in two images (I3): `tests/test_lsp.py:5075` pins only that two images do not send one edit twice.
- An unsaved addition, a second rename, a rename onto a buffer's name (I4). A rename with no project (I5).
- `test_a_quick_fix_is_refused_while_a_file_of_the_project_did_not_load` asserts the error the client turns into a toast (I6): the test pins the defect.
- Fixes are tested for titles and single cases; no test applies the whole offer over varied declarations and loads the result. `s16` is under 200 lines and found 143 file-breaking actions (I7, I8); something of that shape in the suite would hold `settled_at`.
- Raster names are tested through `rename_problem` only (`tests/test_lsp.py:2795-2866`); no test applies an edit carrying a character json must escape (I9).
- Hover over `init: []` and over ±1e308 (I13); 100 % coverage of `rows` and `sparkline` did not reach either.
- Nothing bounds the server's cost (I12, M11): no count of analyses per save, no budget like the page's.
- `extension.ts` has no test, `launch.test.ts` still opens no document (carried), and nothing tests the client's reaction to an error answer.

### Assessment

The mechanics are good and getting them right was real work: an edit lands exactly where it should, in every encoding and line ending tried, the unit plans match the engine byte for byte, the server survived nearly 100,000 requests over broken projects, and last review's Critical is gone as filed. What is wrong is one level up, in what the server believes it knows. It assumes one project at a time, so opening a file elsewhere withdraws true findings. It trusts the nearest description, so the repository's own demo shows false errors in the editor, and a rename there breaks a clean project. It computes a rename from the disk and the document's own project, so the result depends on where you pressed F2 and on what you have not saved. And its quick fixes check two rules of the loader where the loader has more, so one in twelve in a deliberately hard matrix breaks the file and shuts off the very fixes that would repair it. Several of these are stated as design in the SPEC, which is why the tests and the documents agree with them; the sentence they contradict is the SPEC's own first paragraph about an editor that disagrees with the build. Most fixes are small, and I would start with I1, I6 and I9, which are a few lines each, then I2 and I13. I would not yet call F2 safe outside a single-image project with everything saved.

```candidates
10|I1|src/ddd/lsp/server.py:553|Findings of every other project are withdrawn at each refresh: open or save elsewhere and a real error reads clean; a deleted file gets a phantom file-not-found
10|I2|src/ddd/lsp/navigation.py:547|The nearest project answers for the whole: examples/demo's event_logger shows 3 false missing-producer, hover says no producer, a rename breaks a clean project
10|I3|src/ddd/lsp/server.py:743|In two images a rename from a reader rewrites the shared writer and leaves the other image's reader; the reach depends on where F2 was pressed
10|I4|src/ddd/lsp/server.py:740|A rename sees the disk: an unsaved mention keeps the old name, a name only a buffer holds gets an empty edit, a name only a buffer declares is merged onto
10|I5|src/ddd/lsp/navigation.py:459|With no project known, F2 on a shared variable rewrites one file and says nothing
10|I6|src/ddd/lsp/server.py:854|While a file does not load every caret move answers an error, which vscode-languageclient shows as a toast naming no file; the reason is only in the output channel
10|I7|src/ddd/lsp/edits.py:541|143 of 1,688 quick fixes write a file the loader refuses, preferred ones included, and then every further fix is refused
10|I8|src/ddd/lsp/edits.py:752|A named type reads as silence: the preferred fix removes a unit, settles nothing, and says the writer does not declare it
10|I9|src/ddd/lsp/navigation.py:900|A raster rename writes the name raw: a quote or backslash the alphabet admits corrupts every file it touches
10|I10|src/ddd/lsp/navigation.py:744|Renaming a constant leaves a condition spelling it: the object is compiled out with check and gcc -Werror green
10|I11|editors/vscode/README.md:87|VS Code shows the multi-file edit in a preview first is false: it is applied and auto-saved at once, and edits.py rests its design on it
10|I12|src/ddd/lsp/server.py:436|A save costs 1+N analyses, every hover one, a rename across N files about 2N: 24 s per save with five tabs at 36,000 declarations, 25 s for a 61 file rename
10|I13|src/ddd/lsp/hover.py:81|A hover on init [] or on float64 at 1e308 ends the session, as does a relative record, because the server has no net by decision
10|M1|src/ddd/lsp/server.py:850|Malformed params the _field docstring says are refused end the server: diagnostics null, rootUri 3, negative line, %00 in a uri
10|M2|src/ddd/lsp/edits.py:877|A quick fix under a moved buffer is performed in part where SPEC says refused whole
10|M3|src/ddd/lsp/server.py:852|In two images every quick fix is offered twice, both preferred
10|M4|src/ddd/lsp/hover.py:97|The hover answers from the first project and from what loaded: read by nobody, no component produces this, one writer of two (remainder of P6-I3)
10|M5|src/ddd/lsp/server.py:380|Through a junction a file published resolved and then opened keeps stale findings for good; here keeps the unresolved path and loses an action
10|M6|src/ddd/lsp/diagnostics.py:362|Ranges are the disk's, so a squiggle lands on the wrong key of a dirty buffer when another file is saved
10|M7|editors/vscode/package.json:35|onLanguage:json starts the server for any json file and pops the error where ddd is missing (P6-M8)
10|M8|editors/vscode/src/extension.ts:54|The watcher is the extension's, so other editors go stale against works the same either way; ddd-build.json is unwatched; a settings change needs an unstated restart
10|M9|src/ddd/lsp/navigation.py:706|An external type can be renamed though a header defines the name
10|M10|src/ddd/lsp/server.py:885|Workspace folders added later are not followed and get the thin answer in silence; a relative -b reads the first folder alone
10|M11|src/ddd/lsp/units.py:569|Rendering a unit plan is quadratic and runs on a caret move: 104 s at 2,000 statings, 17 s per code action at 500
10|M12|src/ddd/lsp/server.py:830|Small untrue sentences: unsaved changes on a closed file, every action claiming all findings, full range of the datatype on an enum, only while in the docs, LF into a closed CRLF file
```
