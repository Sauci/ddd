## Pass 13: the web GUI, the edit engine and the plans

### Scope covered

Read in full, with line numbers: `src/ddd/editing.py` 1-982, `src/ddd/gui/session.py` 1-1039, `src/ddd/declaration_plans.py` 1-322, `src/ddd/type_plans.py` 1-117, `src/ddd/shared_plans.py` 1-612, `src/ddd/file_plans.py` 1-640, `src/ddd/lsp/units.py` 1-624, `src/ddd/lsp/edits.py` 1-954, `src/ddd/object_values.py` 1-507, `src/ddd/identity.py` 1-209, `src/ddd/file_names.py` 1-111, `src/ddd/pointers.py` 1-29. Read because the scope stands on them: `src/ddd/lsp/ranges.py` 1-395, `src/ddd/lsp/navigation.py` 1-930, `src/ddd/variables.py` 1-357, `src/ddd/finding_fixes.py`, `src/ddd/variable_keys.py`, `src/ddd/gui/derived.py`, `src/ddd/gui/queries.py`, `src/ddd/gui/api.py` 1-2486 (the plan and edit routes; its answers are pass 14's), `src/ddd/project_shared.py` 1-400, the "left open" sections of the GUI plans (`SCRATCH/pass-13/left-open.txt`), the spec's writing and verification sections (`2026-09-17-web-gui-design.md:360-394`).

Ran, all under `SCRATCH/pass-13/`, each transcript beside its script:

- `fuzz_engine.py`: random documents and batches against an oracle of its own (its own json reader keeping every literal and key as spelled, its own pointer grammar and application). Seeds 2, 3, 4: 180,000 documents, 127,263 batches, 122,179 written (`fuzz_engine_{2,3,4}.txt`).
- `plan_fuzz.py`: generated projects (CRLF, BOM, tabs, one-line containers, `\u` keys, non-ASCII, sub-projects, explicit nulls, repeated declarations) and every plan route through `Api.handle`, the outcome compared with the oracle's parse-modify of the same files, then the loader asked, then the undo compared byte for byte. Seeds 11-13: 18,000 actions asked, 7,612 applied (`plan_fuzz_{11,12,13}.txt`). `plan_fuzz_examples.py` over every example, as it is and CRLF: 515 applied.
- Real concurrency: `p03_stale_index.py` (Session threads), `p13_stale_http.py`, `p09_tabs.py`, `p08_killed.py` (a real `ddd gui` over real connections), `p04_lost_save.py`, `p05_two_writers.py`, `p06_same_instant.py`, `p07_two_guis.py`, `p16_id_and_gui.py` (separate processes), `p17_stress.py` (everything at once on one session).
- Files as they are met: `p01_readonly.py` (Windows), `p02_linux_files.py`, `p02b_id_link.py` (Linux through WSL; there is no pydantic in WSL, so these run the tree's own `editing`, `identity`, `ranges`, `pointers` and `file_names` with the models stubbed, `wsl_stub.py`), `p10_fix_matrix.py`, `p11_cases.py`, `p12_unloaded.py`, `p14_sizes.py`, `p15_more.py`, `p18_last.py`.

Not covered: a file symlink on Windows (no privilege here; junctions were); a real `ddd gui` on Linux (engine and `ddd id` only, as above); a power cut (M1 is read off the line); projects with several build records (one run per probe); what the page does with these answers (passes 15, 16); `test_gui_api.py` beyond grep (pass 22).

### Strengths

- **The text engine does what it says.** 122,179 random edits read back as the independent oracle's tree, every untouched literal and key as spelled: 0 wrong, 0 written where the oracle says the operation names nothing, and for a single set no byte changed outside the value it replaces (`fuzz_engine_*.txt`). Depth: answers up to 490 levels, refuses cleanly past it, to 100,000 levels on a request's thread (`p14_sizes_ladder_long.txt`). Duplicate keys, `NaN`: `409 unreadable`, file untouched (`p18_last.txt`).
- **The plans reach what they should.** 7,612 applied plans and 515 on the examples: the oracle's reach, spelling and values hold for every unit, type, constant, section, raster, declaration and file plan, a `\u` key and an escaped unit included. No plan's edit was refused after a 200, no 500, no BOM or final newline lost. The three classes of difference are M2, pass 2 M5 and pass 3 I2.
- **Undo is byte exact.** Every undo of every run restored every byte, created files removed; 66 undone at the end of the concurrent run compared equal (`p09_tabs.txt`).
- **One server serialises its writers.** Four tabs posting one plan: `[200, 409, 409, 409]`, 8 of 8; four files at once: all 200; three undos of one edit: `[200, 409, 409]`, 40 of 40. A minute of saves, half-saved files, plans, edits, undos and re-opens: 581 revisions, no thread stuck, settled at once, every fingerprint the disk's, findings equal a fresh session's (`p17_stress.txt`).
- **Rollback is real.** An edit whose second file is held open, a create whose description is held open, an undo with one file held: all refused after a second, the others back or forward, the undo entry kept and working once released (`p15_more.txt`). Ctrl-C during an edit lets it finish: `Session.stop` needs the lock the edit holds, 300 of 300 written (`p15_more.txt` 6).
- **Links and confinement in the GUI.** A file reached through a junction is written at its target and the junction stays (`p11_cases.txt` J); a rename reaching a file outside what is served is refused whole, nothing written (`p11_cases.txt` I).

### Issues

#### Critical

- **C1. A save during an analysis makes a revision that fingerprints the new bytes and points by the old ones, so a plan passes the stale check and lands on the wrong entry.** `src/ddd/gui/session.py:914`, `:926`, read at `:582`, after the analysis at `:572`.
  `_described` reads each file again once the analysis is over, and that hash becomes `SourceFile.fingerprint`. The index comes from what the loader read earlier. The claims it breaks: `session.py:4` "the files it read with a fingerprint of each", `src/ddd/variables.py:73` "What the analysis read the file at", `src/ddd/gui/derived.py:56`, `src/ddd/gui/api.py:1516`, `src/ddd/type_plans.py:11-13` "a file that changed since is refused by the fingerprint the edit carries", spec `2026-09-18-gui-units-design.md:197-199`. `session.py:699-707` records this same hazard for the stamps, and fixed it there alone.
  Trigger: a person's editor saves a component with a declaration added at its top, while an analysis runs; a plan is asked when the revision lands. No patching.
  - Real server, `GET /api/value-plan?name=Injection&at=[1]&raw=999`: plan `set component.interface[0].definition.init[1]`, `POST /api/edit` 200, afterwards `{'Ignition': [1, 999, 3], 'Injection': [100, 200, 300]}`; 6 of 6. The state at that moment says `analysing: false`; findings after it: 0 errors (`p13_stale_http.txt`).
  - Real server, removing section `.unused` while `.new` was saved above it: the person's just-saved `.new` is what goes; 6 of 6.
  - Session threads, a unit rename: `Gamma` goes `kg` to `krpm`, `Alpha` keeps `rpm`; 12 of 12 (`p03_stale_index.txt`).
  Window: the save lands anywhere from the loader's read of that file to the end of the analysis, then the plan any time up to the next revision: a poll (1 s) plus an analysis (3.8 to 6.0 s at 100,000 declarations, by `docs/command_line_interface.rst`'s own measure; about 1 s in these probes). A person saving twice inside one analysis is enough. The preview shows the true lines of the wrong declaration, without its name.
  Exposed (index pointer, no check of what sits there): `rename_unit`, `describe_unit`, `remove_unit`, `rename_type`, `set_entry`, `rename_entry`, `remove_entry`, `set_cell`, `set_values`, `read_object`. Safe: `settle` and its fixes (`lsp/edits.py:540`, `_at_site`), `set_key` (`project_types.py:233`), `remove_declaration`. `unit_drift` (`lsp/units.py:547`) exists and only the language server asks it; the read routes ask `type_in_place`, `entry_in_place`, `listed_in_place`.
  Change (S): fingerprint the bytes the analysis read, recorded by the loader or taken with the stamps before it reads (then a save in between refuses, the safe way); and have the plans ask the in-place question the read routes ask. `tests/test_gui_session.py`'s `saving_while_analysing` already makes the trigger.

- **C2. Every writer stages under one fixed name beside the file, so two writers can delete the file: on Windows the description is gone, nothing left beside it.** `src/ddd/editing.py:922`, the unlink at `:928-931`; `src/ddd/identity.py:198-208`; `src/ddd/file_names.py:16-18`; the reasoning at `identity.py:69-73` ("a leftover of a run that died is ours by construction").
  Trigger: two processes applying one change each to one file at one instant, once a round: two `ddd gui` over one project, or one and a `ddd id --assign` hook. Reproduced on Windows, the tree's own code:
  - 128 KB: THE FILE IS GONE 12 of 1,500, 11 of 2,000; 2 MB: 2 of 300; 16 KB: 0 of 1,500. One told written, the other `Permission denied` on the stage, the directory empty (`p06_same_instant_windows.txt`, `p06_again.txt`).
  - With the real `identity.assign` against an edit: 1 of 2,000; `assign` answered 1, the edit `unwritable`, directory empty (`p16_id_and_gui.txt`).
  - The cause named by mutation in a process of its own: the failure path's `staging.unlink()` taken out, 0 of 2,000; a stage name per process, 0 of 2,000 and no false refusal (`p06b_no_unlink.txt`, `p06b_unique.txt`).
  On Linux the file survives and the answers are false: the writer whose bytes are there was told it failed, 1,067 of 1,500 at 16 KB (`p06_same_instant_linux.txt`); 1,013 of 515,190 reads of the file were not json, the first of them empty, and the other engine answered `unreadable` on 497 of its reads (`p05_two_writers_linux.txt`, both writers hammering).
  Rare: two writers in one millisecond. Graded for what it costs: a person's uncommitted description, no trace, and an undo that answers the file can no longer be read.
  Change (S): a stage name of its own per write (`tempfile.mkstemp` beside the file); `CREATED_NAME_MAX` and the test pinning the suffix follow.

#### Important

- **I1. The fingerprint is checked once, before anything is written, so a save landing during an edit is overwritten, the edit answering written.** `src/ddd/editing.py:803`, written at `:811`; spec `2026-09-17-web-gui-design.md:383-386`; the docstring at `editing.py:793-794`.
  Trigger: another process saves a file at a random moment of `apply_changes`. Given a save inside the edit: 273 of 300 lost at 50 declarations (the edit takes 8 ms), 198 of 200 at 500 (43 ms), 27 of 40 for the first of 100 files (578 ms) (`p04_lost_save.txt`). The window of the first file is the whole in-memory phase of the batch: 1,200 files, 3.07 s, whole edit 6.33 s (`p14b_window.txt`). Two `ddd gui`: both 200, one change gone, 1,179 of 1,200 (`p07_two_guis.txt`). `assign` answered 1 and the id is gone, 1,993 of 2,000 (`p16_id_and_gui.txt`). `Written.before` holds the bytes from before the save, so the undo cannot bring it back either.
  Graded below C1 only because the common window is milliseconds; a pull or a branch switch during a large rename has seconds. It is the same class of loss.
  Change (S): compare the file's bytes with `original` again immediately before each rename, refusing `stale` and putting back. Tried at run time: 273 of 300 becomes 35 (the stage's own write is still inside; check after staging), 27 of 40 becomes 0 (`p04b_recheck.txt`).

- **I2. A rename or removal of a type, constant, section or raster, and a settle, are half performed while one file of the project did not load; only a unit's rename refuses.** `src/ddd/type_plans.py:93`, `src/ddd/shared_plans.py:212`, `:326`, `src/ddd/lsp/edits.py:577`, `src/ddd/gui/api.py:1219`; the guard at `src/ddd/lsp/units.py:235-240` has no sibling; `api.py:1193-1198` hands `unread` to `SharedProject` and only `add_entry` reads it.
  Against `lsp/units.py:13-15` "a rename that cannot see it leaves the old spelling there, in a project the rename said it had rewritten", `lsp/navigation.py:373-377` "An ordinary mid-edit state has to refuse the rename, not half-perform it", `lsp/edits.py:570-572` "a change that reaches only some of its declarations is not the one they chose".
  Trigger (`p12_unloaded.txt`): `b.ddd.json` truncated by a save, or holding one mistyped value, as an editor saves a file being typed in. Unit rename: `409 unreadable`. Type, constant, section, raster rename: plan 200 over the other files, edit 200, `b` untouched; once `b` is repaired, `unknown-type`, `unknown-constant`, `unknown-section`, `unknown-raster`. Settle: `definition-mismatch` once repaired. Removing a constant only `b` names: allowed, `unknown-constant` once repaired; a section or a raster likewise, the panel reading 0 uses.
  Change (S): the refusal `rename_unit` makes, in `_type_plan`, `_shared_plan` for rename and remove, and `_settle`. Which reach a repair would need is question 3.

- **I3. No plan asks the loader what it would leave: the engine verifies json, never the format, so a button or a panel value writes a file that stops loading, against a page promising otherwise.** `src/ddd/variables.py:232`, `src/ddd/editing.py:19-20`; the promises at `docs/command_line_interface.rst:315-316` "unless it would leave the file unable to load", `src/ddd/models/objects.py:953-955`.
  The root of three findings filed from other sides: pass 10 I7, pass 3 I1, pass 2 M5. What this angle adds is the reach in the page. Pass 10's matrix through `GET /api/fix` and the panel's values in play (`p10_fix_matrix.txt`): **84 of 1,002 buttons** and **58 of 882 in-play values** leave a file the loader refuses: `Use the datatype declared in w` on an enum (`requires an integer datatype`), `Remove this dimensions` on a string, `Use the unit declared in w` on a string. Each is previewed as an ordinary change and offered as the fix; undo puts it back.
  Change (S-M): `planned` validates the text it computed with the model of that file's kind, and the answer refuses or says so; which is question 5. What is wrong only in context stays reported, as the spec rules.

- **I4. A read-only file: on Windows the refused edit leaves a read-only stage that blocks every later edit, even once the file is writable again; on Linux it is written through.** `src/ddd/editing.py:926`, `:928-931`, `:949-959`.
  Windows (`p01_readonly.txt`): `_keep_access` makes the stage read-only, the rename is refused after 1.17 s, and `staging.unlink()` is refused too, in a `suppress`: `u.ddd.json.ddd-staging` stays, read-only. The reader clears the flag and asks again: `Permission denied` on the stage, at once, for as long as nobody deletes it. Likewise a read-only stage left by a kill. A created file takes the description's read-only mode, so its rollback fails: `these could not be put back: ...constants.ddd.json`, and the stage stays beside them (`p11_cases.txt` M).
  Linux (`p02_linux_files.txt` 1): a file kept 444 is rewritten and stays 444, no refusal, where `identity.py:59` calls a read-only file one that "could not be written". A read-only checkout's protection is silently passed; nothing says which system does what.
  `tests/test_editing.py:706` pins no leftover with a monkeypatched `Path.replace`, whose stage is not read-only.
  Change (S): refuse a target this process may not write before staging, on every system (question 1); make the stage writable before unlinking it.

- **I5. `ddd id --assign` through a symlink replaces the link with a copy and leaves the file it names unstamped.** `src/ddd/identity.py:198-201`, where `gui/session.py:823` resolves first. Adds to pass 2 I6.
  Reproduced on Linux (`p02b_id_link.txt`): `proj/common.ddd.json -> ../shared/common.ddd.json`, `assign` answers 1; the link is now a regular file holding the id, `shared/common.ddd.json` has none. A description shared between projects by a link is forked in silence, `wrote 1 id`, each project then minting its own identity for one object.
  Change (S): resolve the path first, or take the engine's writer, which closes pass 2 I6 too.

- **I6. Reading another component's local is offered, and writes `local-conflict` into a clean project.** `src/ddd/declaration_plans.py:83-98`, `:101-111`.
  Trigger (`p11_cases.txt` A): `W` holds `Loc` local. `GET /api/declarable` for `R`: `('Loc', ['input'])`; plan 200, edit 200, two errors `'Loc' is local to component 'W' but is also declared as input by component 'R'`. `scopes_for`'s docstring holds `local` back "because `local-conflict` is exactly a local beside another declaration", which an `input` is. Locals are ordinary (every declaration of `examples/vocabulary` is one), the name field lists them with the rest, and for such a name this is the only scope offered.
  Change (S): `declarable` leaves out a name only locals hold, or `scopes_for` answers none and the plan refuses.

#### Minor

- **M1. All-or-nothing holds against a refusal, not against a stop: a killed server leaves half an edit and nothing says so.** `src/ddd/editing.py:806`, `src/ddd/gui/contract.py:1657`, `:1660` "made all at once, or not at all", `src/ddd/gui/server.py:380`. A rename across 400 files, the server killed while writing, as a closed terminal or `kill` does: 6, 49 and 59 files renamed, once a stage left beside them; started over: `error: 0`, nothing to undo (`p08_killed.txt`). Ctrl-C is safe (Strengths). No `fsync` before the rename either (`editing.py:924`), so a power cut can leave an empty file on a file system that reorders (read off the line). Question 4.
- **M2. `at` without brackets plans a key of its own: `init1`.** `src/ddd/object_values.py:472`, `src/ddd/gui/queries.py:1094`. `GET /api/value-plan?name=A&at=1&raw=9`: `_element` strips brackets it never required, the pointer is `...definition.init1`, 200, the edit makes `schema: Extra inputs are not permitted` (`p11_cases.txt` E; 85 load failures with pass 2 M5 in `plan_fuzz_1[123].txt`). The page always sends brackets; a second client meets this.
- **M3. Reading a conditional object drops its condition.** `src/ddd/declaration_plans.py:320`, against `:163-164` "agree with its producer by construction". Producer under `defined(FEATURE)`: `condition-mismatch` on both sides after the plan (`p15_more.txt` 1).
- **M4. A short init's cell past its end is refused in the engine's words.** `src/ddd/object_values.py:332`, against `:197-199` "setting a cell or pasting a table ... is how the page repairs it". `init` of 2 in a shape of 4, `at=[3]`: `409 nothing is written at component.interface[2].definition.init[3]` (`p11_cases.txt` E). Only the paste repairs it.
- **M5. A change the poll cannot see is stale for good.** `src/ddd/gui/session.py:424`, `:1034-1038`. Same size, same modification time (a one-second file system, a tool restoring times): poll false; the plan 200 with the old fingerprint, its edit `409 stale`, every retry the same, until something else changes (`p11_cases.txt` K). A stale refusal asks for no analysis (`p18_last.txt`). `KNOWN` in part: `2026-09-19-gui-units-project.md`, Task 8, "an immediate retry is refused again". Change: a stale refusal asks for an analysis, which closes that too.
- **M6. An edit does not always follow the file's line ending.** `src/ddd/editing.py:134-138`, `:625`, `src/ddd/lsp/units.py:151`. No line break after the place: LF into a CRLF file, `{\r\n ...2,\n    3],\n    "c": 3}` (`p15_more.txt` 7; 6 in `plan_fuzz_1[23].txt`). Bare CR reads as one line, so an addition joins it (`p11_cases.txt` N). A created file is LF and two spaces whatever the project writes (`p11_cases.txt` O). The remainder of P8-M6.
- **M7. The Files tab writes a backslash or an absolute path into `includes`.** `src/ddd/file_plans.py:569`, `src/ddd/lsp/units.py:124`. `sub\x.ddd.json` and `C:/Users/.../y.ddd.json` are written as typed, clean here (`p11_cases.txt` L), a `file-not-found` on any other machine; against `src/ddd/file_names.py:5` "A project is checked out on more than one system".
- **M8. A member added to a file written on one line is quadratic, under the session's lock at Apply.** `src/ddd/editing.py:149`, `:282`, `:634-646`. Whole component on one line: 0.45 s at 1,000 declarations, 39.3 s at 10,000 (1.5 MB); the rename batch 0.88 s, a removal 0.69 s (`p14_sizes_ladder_long.txt`). `_unit_below` walks every entry looking for a line of its own, `indent_of_line_at` copies the rest of the text for each.
- **M9. Keys holding the pointer grammar crash the engine rather than refuse.** `src/ddd/editing.py:643`, `:699-702`. A file with a key `""`, `.`, `[` or `a.` anywhere: member additions raise `AssertionError` or `RecursionError` (942 and 306 in `fuzz_engine_{2,3,4}.txt`), answered 500, nothing written. Only reachable in a plugin's block or by a direct post. `KNOWN` (`2026-09-17-web-gui-skeleton.md`, `2026-09-30-gui-large-projects.md`).

Seen again, not re-filed, with what this angle adds:

| Earlier | In the GUI |
|---|---|
| pass 1 C4 | Reaches every plan that edits the description: `create_plan`, `add_plan`, `remove_plan`, `adopt_units`, `add_entry`'s creating arm (`file_plans.py:420, 569`, `shared_plans.py:584`, `lsp/units.py:385`). A rename or a set does not. |
| pass 2 I6 | Confirmed; I5 and C2 add to it. |
| pass 2 M3, M7 | Confirmed: `"unit": "\u00b0C"`, `-40.0` from `-4.0e1`; the id last, where `ddd id` puts it after `name` (`p11_cases.txt` F). |
| pass 2 M5 | Confirmed: `18446744073709551616` in a float32 cell, `schema` (`p11_cases.txt` E). See I3. |
| pass 3 I1 | Confirmed: `settle` and `type-plan`, six of six values stop the file loading (`p11_cases.txt` H). See I3. |
| pass 3 I2 | Confirmed: `settle` of limits on a variable stating none answers 200 and no change (`p11_cases.txt` G). |
| pass 3 M5 | Refused 400 before anything is touched: no file risk (`p18_last.txt`). |
| pass 10 I7 | Reaches the page: 84 of 1,002, 58 of 882. See I3. |
| pass 10 I8 | Does not reach the page as a wrong press: `_reconciled` drops it, so the finding has no button (`p11_cases.txt` B; 124 of the matrix's 680 findings have none, these among them; `KNOWN`, `2026-09-25-gui-mismatch-fix.md`). |
| pass 10 I9 | Does not reach the page: `shared_plans._raw` escapes; `a"b`, `a\b` load (`p11_cases.txt` D). |
| pass 10 I10 | Reaches the page, and further: a rename leaves `CELLS > 2`, and **removing** `CELLS` is allowed with 0 uses and no finding, the object compiled out (`p11_cases.txt` C). |
| pass 10 M2 | No buffers in the GUI; C1 is the disk's own form of it. |

### Status of the 2026-09-15 findings in this area

Only those not plainly fixed. P8-I1 (`ranges.py:94-115`), P8-M5 (`ranges.py:297`), P5-M4 (`identity.py:199-208`), P6-M14 (the engine counts `\n` alone) are fixed.

| Finding | Status | Note |
|---|---|---|
| P8-M6 | STILL OPEN in part | `editing.py:134-138` fixed the bare CR it was filed on; an LF still enters a CRLF file where no line break follows. M6. |
| P8-M18 | FIXED, with new defects | `identity.py:198-201` stages now; the stage is what C2 and I5 are about, and pass 2 I6 lists what it lost beside the engine. |

### Open questions

1. **May a read-only file be edited?** Today: refused on Windows, written on Linux. If not, a check before staging on every system (I4). If so, Windows has to clear and restore the flag, and the docstrings change. I would refuse.
2. **May two servers serve one project?** A unique stage (C2) stops the deletion, but both still answer written and one change goes (I1). A lock file beside the description refuses the second server, and costs a stale lock after a crash.
3. **A rename while a file does not load: refuse, or reach it by text?** Refusing is what `rename_unit` and the editor do, and it blocks every rename while somebody's file is half saved. Writing into a file nobody can read is not on offer. I would refuse (I2).
4. **Is all-or-nothing meant to survive a kill?** If so a journal beside the project and a recovery at start (M). If not, `contract.py:1657` says refusals, and the page's sentence with it (M1).
5. **Plan that would stop a file loading: refused, or written and reported?** Spec `2026-09-20-gui-other-keys-design.md` 4.2 rules written and reported; `docs/command_line_interface.rst:315-316` and `objects.py:953-955` say otherwise. Refusing loses a path through a bad state; I would refuse a button and warn on a panel's value (I3).

### Test gaps

- No test holds a fingerprint to the bytes the analysis read: `tests/test_gui_session.py:279` compares after the fact, nobody saving; `saving_while_analysing` (`:380`) checks the poll, not the plan. A plan and an edit after that helper's save pins C1.
- No plan test moves a file between the analysis and the plan: the drift tests are the read routes' and the language server's.
- No test has two writers on one file, or a real read-only file: `tests/test_editing.py:706` and `_patiently`'s test monkeypatch `Path.replace`, which is why I4 and C2 stayed green at 100 %.
- `tests/test_unit_plans.py` covers the unread refusal; nothing asks the same of `rename_type`, `rename_entry`, `remove_entry` or `settle` (I2).
- `tests/test_editing_at_once.py:44`'s `oracle` is the engine's own helpers, so it pins at-once against in-turn, not against an independent reading. The independent one here found no difference; `fuzz_engine.py` is a ready start.
- No test asks the loader of what a plan's result is, across kinds of conversion (I3).

### Assessment

Can an edit lose or corrupt a person's file? Yes, three ways, each from one small decision, all reproduced: a fingerprint read after the analysis it is said to describe (C1: the wrong declaration rewritten, a just-saved entry removed, a value in the wrong object, with every gate green), one fixed stage name (C2: the file deleted), and a check made once before all the writing (I1: a save overwritten). Each fix is hours. What surrounds them is better than this makes it sound: the text engine is the strongest thing I have read in this project, 122,179 random edits and 7,612 plans read back exactly by an oracle that shares nothing with it, undo is byte exact everywhere, one server serialises its writers, and rollback works when something refuses. The weakness is the seam between the plans and the disk: the design trusts the fingerprint so completely that the plans dropped the in-place question the read routes and the editor ask, so when the fingerprint lies nothing else stands. Does a plan always produce a file the loader accepts and the change it announced? The change, nearly always; the file, no: about one button in twelve in a matrix of disagreeing declarations stops a file loading, and nothing between the plan and the write asks the loader (I3). Rename also needs the guard the unit rename has (I2). Fix C1, C2, I1 and I2 before anyone edits a real project with this and a text editor side by side.

```candidates
13|C1|src/ddd/gui/session.py:914|A save during an analysis gives a revision fingerprinting the new bytes and pointing by the old: a plan passes stale and rewrites the wrong declaration, value or entry, 12 of 12
13|C2|src/ddd/editing.py:922|One fixed stage name: two writers delete the description on Windows (11 of 2000, also with ddd id --assign), on Linux the answers are false and readers meet an empty file
13|I1|src/ddd/editing.py:803|The fingerprint is checked once before anything is written: a save during an edit is overwritten, answered written, and undo cannot bring it back; seconds on a large rename
13|I2|src/ddd/shared_plans.py:212|Rename or removal of a type, constant, section or raster and settle are half performed while one file did not load; only a unit's rename refuses
13|I3|src/ddd/variables.py:232|No plan asks the loader what it leaves: 84 of 1002 buttons and 58 of 882 in-play values stop a file loading, against unless it would leave the file unable to load
13|I4|src/ddd/editing.py:926|A read-only file: on Windows a read-only stage stays and blocks every later edit, rollback of a create fails; on Linux it is written through
13|I5|src/ddd/identity.py:198|ddd id --assign through a symlink replaces the link with a copy and leaves the file it names unstamped
13|I6|src/ddd/declaration_plans.py:111|Reading another component's local is offered and writes local-conflict into a clean project
13|M1|src/ddd/editing.py:806|A killed server leaves half an edit, error 0 at restart, against made all at once or not at all; no fsync before the rename
13|M2|src/ddd/object_values.py:472|at without brackets plans a key init1 and the file stops loading
13|M3|src/ddd/declaration_plans.py:320|Reading a conditional object drops its condition: condition-mismatch, against agree by construction
13|M4|src/ddd/object_values.py:332|A short init's cell past its end is refused in the engine's words, against setting a cell repairs it
13|M5|src/ddd/gui/session.py:424|A change of the same size and time is stale for good: a stale refusal asks for no analysis (KNOWN in part)
13|M6|src/ddd/editing.py:138|LF into a CRLF file where no line break follows; bare CR reads as one line; a created file ignores the project's layout (remainder of P8-M6)
13|M7|src/ddd/file_plans.py:569|The Files tab writes a backslash or an absolute path into includes, against checked out on more than one system
13|M8|src/ddd/editing.py:149|A member added to a one-line file is quadratic: 39 s at 1.5 MB, under the session lock at Apply
13|M9|src/ddd/editing.py:643|Keys holding the pointer grammar crash the engine rather than refuse: 500, nothing written (KNOWN)
```
