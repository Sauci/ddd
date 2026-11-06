### Verification of pass 2

By a reader who did not find these, on 2026-11-06, on the tree at master 2b4bae6c. Scratch:
`SCRATCH/verify-1-2/`. 21 CONFIRMED. No grade changes.

| id | verdict | grade (was -> now) | duplicate of | evidence | note |
| --- | --- | --- | --- | --- | --- |
| I1 | CONFIRMED | Important -> Important | - | verify-1-2/p2/runtime.txt, p2/graph.txt, p2/commits.txt | measured: 14 root modules and 4 gui modules import ddd.lsp, outside fan-in ranges 15 navigation 13 units 7 edits 6; with ddd.lsp refused all 12 plan and read modules fail to import and edit_text and assign fail on first call; hover 0, protocol 0, server 1 commits since 2026-09-17 against 18/14/12/8 |
| I2 | CONFIRMED | Important -> Important | - | verify-1-2/p2/runtime.txt, p2/trial.txt | measured: import ddd.file_plans or ddd.lsp.ranges loads all 10 ddd.lsp modules, server and protocol among them; trial: identity.py's import moved up makes import ddd.identity fail on a circular import, import order deciding; SCC 9 modules by my count, 12 with the pass's parent model |
| I3 | CONFIRMED | Important -> Important | - | verify-1-2/p2/i3.txt | reproduced: with ddd.gui refused, remove_plan of constants.ddd.json applies and check then fails unknown-constant, and add_plan takes x.py; the api answers 409 to both; the two refusals exist only at gui/api.py:2183 and 2247 |
| I4 | CONFIRMED | Important -> Important | - | verify-1-2/p2/guards.txt | my own 13 mutants in a copy the tests import: 3 controls caught, all 10 realistic violations pass (from ddd import backends, relative imports, deferred imports of analysis, cli, lsp, gui, a backend); KNOWN dropped: a 2026-09-15 test gap no plan took up, still open |
| I5 | CONFIRMED | Important -> Important | - | read off docs/developer_documentation.rst:19-97, src/ddd/__init__.py:3-9, README.md:1033-1041; verify-1-2/p2/i5.txt | confirmed as text: no row for gui/ and 21 root modules, 38 % of the lines; Six smaller modules, cli.py the only module knowing exit codes and streams (gui/server.py prints and returns EXIT_USAGE), lsp a second front end, ir listed above its importers |
| I6 | CONFIRMED | Important -> Important | - | verify-1-2/p2/i6/run.txt; read off src/ddd/identity.py:197-208 against editing.py:919-963 | reproduced on Windows: a duplicated key and a NaN, each json-syntax to check and refused by the engine, are stamped by ddd id --assign, exit 0; the Linux mode half (no _keep_access) read off the lines, not rerun; STAGING_SUFFIX spelled three times |
| I7 | CONFIRMED | Important -> Important | - | verify-1-2/p2/i7.txt | the copies differ today, not only once: a candidate with its own definition-mismatch is cannot replace, exit 1, to ddd compare and check --baseline, and verdict true with no findings to GET /api/compare; the past divergence is recorded at gui/compare.py:19-24 |
| I8 | CONFIRMED | Important -> Important | - | read off src/ddd/finding_routes.py:11-12, 205-224; variable_keys.py:54-75; project_shared.py:105-122; declaration_plans.py:33-37; finding_fixes.py:52 | confirmed as text: tabs, panels, a button, form orders and a row's States cell in root modules, finding_routes called pure while its answer is a screen; the code records the cost itself: the screen list stated twice and pinned by a test, three near-misses |
| I9 | CONFIRMED | Important -> Important | - | verify-1-2/p2/i9.txt | reproduced at 1,200 components of 30 declarations: constant-plan set of one key 1.4 to 2.1 s (median 1.87), unit-plan describe 0.45 s, both about 20 ms at 10 components; project_of alone 1.23 to 1.31 s with a fresh cache, its result unused by set |
| I10 | CONFIRMED | Important -> Important | - | verify-1-2/p2/i10.txt | counted: nine plan handlers, the 409/500 mapping 13 times, the did-not-load sentence 4, six one-field refusal classes, gui/api.py 75 commits since 2026-09-17 against 55 for the next; KNOWN in part holds (2026-09-23-gui-values.md:1502-1505, under Left open) |
| M1 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/graph.txt; read off src/ddd/diagnostics.py:363-365, gui/server.py:70, loading.py:14 | measured: with deferred edges the graph has the SCCs {diagnostics, ir, loading, plugins} and {cli, gui.server}; diagnostics.py says its deferred import is the one thing keeping the graph acyclic |
| M2 | CONFIRMED | Minor -> Minor | - | read off src/ddd/gui/api.py:140-143 | confirmed: gui/api.py imports _name_in, _read_json, _served and _source from gui/session.py |
| M3 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/minors_api.txt | reproduced: the read plan of a variable stated with a literal degree sign, 1e-1 and -4.0e1 writes "\u00b0C", 0.1 and -40.0 into the reader's file; GET /api/type answers the factor as 0.1 |
| M4 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/minors_api.txt | reproduced with a correction: kind_of calls a dumped dictionary types, while the loader refuses dump.json as file-extension rather than file-kind; Upper.DDD.JSON checks clean and find_projects lists nothing |
| M5 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/minors_api.txt | reproduced: value-plan of 18446744073709551616 into a float32 axis answers 200, POST /api/edit writes it, and the component then fails schema, does not fit 64 bits |
| M6 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/minors_api.txt | reproduced: renaming constant OTHER to rpm, a member of Pair_t, is planned and written with no refusal; ddd check then reports name-collision |
| M7 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/minors_counts.txt | reproduced in process: the GUI fix's set puts "id" after the last key ("volatile"), identity.insertions after "name", against finding_fixes.py:8-10 |
| M8 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/minors_counts.txt | counted 34 regex calls in the seven modules and 12 files spelling component.interface; KNOWN in part holds: WITHIN_DECLARATION is still at lsp/navigation.py:50 and lsp/edits.py:142 (2026-09-22-gui-findings.md:2107, Left open) |
| M9 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/m9_citations.txt | confirmed with a smaller count: my patterns find 40 lines in 15 modules, 15 in gui/server.py (Task 2 is the only caller, ruling P19a-14, run 37737377854), not 73 in 25; the count depends on the pattern |
| M10 | CONFIRMED | Minor -> Minor | - | read off src/ddd/lsp/server.py:1-4, variable_keys.py:6-7, finding_routes.py:11-12, lsp/navigation.py:110-111 | confirmed as text: six messages where the server answers about fourteen methods; nothing else reads them, read by declaration_plans.py:30, project_shared.py:33, project_units.py:20; the _BASE_DATATYPES docstring describes constants |
| M11 | CONFIRMED | Minor -> Minor | - | verify-1-2/p2/minors_counts.txt | counted: cache: dict[Path, Document] written 126 times in 18 modules, as the pass says |

**I1, confirmed.** Measured with my own scripts, not the pass's. Statically (`p2/graph_probe.py`, every
import statement classified top level, deferred or `TYPE_CHECKING`): 14 root modules besides `cli`, and
`gui.api`, `gui.compare`, `gui.queries`, `gui.session`, import `ddd.lsp`; from outside the package,
`lsp.ranges` has fan-in 15, `lsp.navigation` 13, `lsp.units` 7, `lsp.edits` 6, as the pass says (its 35
edges count module pairs; I count 72 imported names). At run time (`p2/runtime_probe.py`, a fresh `python
-I` per case and a meta path finder refusing `ddd.lsp`): `variables`, `variable_keys`, `project_units`,
`project_types`, `project_shared`, `type_plans`, `shared_plans`, `declaration_plans`, `object_values`,
`file_plans`, `finding_routes` and `finding_fixes` each raise `ImportError`; `editing` and `identity`
import, and `edit_text` and `assign` raise it on their first call; `loading`, `analysis`, `compare`,
`deliveries`, `ir` and both backends import cleanly. So no edit of a project can be made, by a second
interface or a batch tool, without the language server's package. `git log --since=2026-09-17` up to
`2b4bae6c`: `lsp/hover.py` 0 commits, `lsp/protocol.py` 0, `lsp/server.py` 1; `lsp/edits.py` 18,
`lsp/units.py` 14, `lsp/navigation.py` 12, `lsp/diagnostics.py` 8 (`p2/commits.txt`), so the package has
changed for the GUI, not for its own client.

**I2, confirmed with a correction of size.** A plain `import ddd.file_plans`, `import ddd.variables` or
`import ddd.lsp.ranges` leaves all ten `ddd.lsp` modules in `sys.modules`, `server`, `protocol` and
`hover` among them (`p2/runtime.txt`). The hidden cycle: in a copy of `src/` (`p2/copy`, fresh
timestamps) I moved `identity.py`'s deferred `from ddd.lsp.ranges import Document` to the top and
changed nothing else; `import ddd.identity` then fails, "cannot import name 'insertions' from partially
initialized module 'ddd.identity' (most likely due to a circular import)", while `import ddd.lsp` or
`import ddd.cli` first still works (`p2/trial.txt`). So the deferred imports are what hold it, as
`editing.py:22-24` and `identity.py:13-18` say, and the import order decides. The correction: counting
deferred edges and an importer's edge to the parent package it runs, the strongly connected component
is 9 modules (`editing`, `identity`, `lsp`, `lsp.diagnostics`, `lsp.edits`, `lsp.hover`,
`lsp.navigation`, `lsp.server`, `lsp.units`); the pass's 12 also counts each submodule as depending on
its own parent. The finding does not depend on which.

**I3, confirmed.** My own batch tool (`p2/i3_batch.py`), with `ddd.gui` refused at import, on a fresh
copy of `examples/vocabulary`: `file_plans.remove_plan` of `constants.ddd.json` plans `remove
project.includes[2]`, `editing.apply_changes` writes it, and `ddd check` then exits 1 with
`error[unknown-constant]: 'PressureTrend' is dimensioned by 'TREND_SAMPLES'`; `add_plan(..., "x.py")`
plans `insert project.includes[4] "x.py"`. Through `ddd gui` on another fresh copy, the same two requests
answer 409: "removing constants.ddd.json would leave one error more than the project has now" and
"x.py is a python file, which a project names among its plugins rather than its includes"
(`p2/i3.txt`). Both sentences exist only in `src/ddd/gui/api.py` (`:2183`, `:2247`), so a second client
gets the edit and loses the guard.

**I4, confirmed; the KNOWN tag is dropped.** My own mutants (`p2/guards.sh`), each applied alone to a
fresh copy of `src/` that the copied guard tests demonstrably import (`PYTHONPATH`, checked), then
`tests/test_backends.py::TestLayering` and `tests/test_file_plans.py::test_the_module_imports_nothing_of_the_gui`
run, 13 tests. Baseline green. Caught, one failure each: the controls, `from ddd.backends.base import
Backend` at the top of `loading.py`, `import ddd.backends.a2l.model` in `backends/c/model.py`, and a
top-level `import ddd.gui.session` in `file_plans.py`. Not caught, all green: `from ddd import backends`
in `loading.py`; `from .backends import base` in `plugins.py`; `from . import names` in `elf.py` (whose
row says it "imports no `ddd` module"); and deferred imports of `ddd.analysis` from `models/objects.py`,
`ddd.cli` from `ir.py`, `ddd.lsp.ranges` from the a2l backend, `ddd.backends.c.model` from `lsp/hover.py`,
`ddd.gui.api` from `analysis.py`, and `ddd.gui.session` from `file_plans.py` and from `editing.py`
(`p2/guards.txt`). The helper only records `node.module` when it starts with `ddd`
(`tests/test_backends.py:32-41`), which is why relative and `from ddd import` spellings vanish. This
contradicts `docs/concept.rst:582` and `README.md:1047-1048` ("cannot rot silently"). The tag: the item
is the 2026-09-15 review's pass 7 test gap (`review-2026-09-15.md:3033-3035`), and neither the 2026-09-16
plan's "Left open by the implementers" nor any other plan mentions it, so it is still open rather than
known-and-left.

**I5, confirmed as text.** `docs/developer_documentation.rst:19-58` has rows for `models/`, `loading`,
`analysis`, `ir`, `plugins`, both backends, `lsp/`, `elf`, `addresses` and `toolbox/`; `:75` "Six
smaller modules sit beside them" names `diagnostics`, `compare`, `cli`, `names`, `identity`,
`build_info`. What is in neither: `gui/` (8,580 lines) and 21 root modules (6,655 lines, `editing`,
every plan and read model, `deliveries`, `graph` among them), 38 % of the package's 39,534 lines by my
count (`p2/i5.txt`; the pass's 39 % leaves out `__main__`). `:78-79`, "`cli.py` is the only module that
knows about argument parsing, exit codes and where output goes", against `gui/server.py:70` (`from
ddd.cli import EXIT_OK, EXIT_USAGE`), `:931-932`, `:978-993` (prints to `sys.stderr`, returns
`EXIT_USAGE`) and `:1027`. `:92-96`, `lsp/` "a second front end over the same loader and analysis",
against the 18 modules outside it that import it (I1). `src/ddd/__init__.py:3-9`, "each knowing only
what is below it", lists `ir` after `loading` and `analysis`, both of which import it (`loading.py:14`,
`analysis.py:27`). `README.md:1033-1041` has no row for `lsp`, `gui`, `toolbox`, `elf` or `addresses`.

**I6, confirmed; its Linux half is read off the code.** On Windows (`p2/i6/run.txt`): a component with
`"name"` spelled twice, and one with `"init": NaN`, are each `error[json-syntax]` to `ddd check`;
`ddd id --assign` answers "wrote 1 id", exit 0, and rewrites each, where `editing.edit_text` refuses the
same documents ("the file is not json DDD reads"). That is against `identity.py:169-171`, "this command
must not rewrite one it could not read", since what DDD reads is the loader's json. The access half:
`identity.assign` stages and calls `staging.replace(path)` (`identity.py:197-208`) with neither the
engine's `_keep_access` nor its `_patiently` (`editing.py:919-943`); on a posix system a rename does not
look at the target's mode, so a 444 file is replaced and left with the staging file's umask mode, which
is the pass's WSL transcript, and contradicts `UNWRITABLE`'s docstring (`identity.py:57-63`, "A read-only
file in a checkout ... is reported"). I did not rerun it: that needs Linux, and I did not enter WSL
without knowing its default user is not root. `STAGING_SUFFIX` is defined three times
(`file_names.py:16`, `identity.py:66`, `backends/base.py:33`). Pass 13 I5 (a symlink replaced by a copy)
and pass 19 M1 (no retry) later add triggers through the same writer.

**I7, confirmed, with a wider effect than the pass saw.** The six "load, gate, analyse" sites and the
three "compare, then hooks" sites are where the pass says (read at `cli.py:1896-1917`,
`gui/compare.py:15-26`, `lsp/diagnostics.py:60-68`, whose docstrings record the earlier divergence:
"Running the first half alone answered 'can replace' for a delivery the command exits 1 on"). To test
the stated consequence I ran one comparison through three copies (`p2/i7_compare.py`): a baseline dump of
a clean project, and a candidate that changes nothing the baseline published but whose reader now
disagrees with its producer (`definition-mismatch`). `ddd compare base.json cand/p.ddd.json`: exit 1,
"p.ddd.json cannot replace base.json"; `ddd check cand/p.ddd.json --baseline base.json`: exit 1; `ddd gui`
on the candidate, `GET /api/compare?baseline=base.json`: 200, `"verdict": true, "findings": []`
(`p2/i7.txt`). So the copies disagree on the verdict today. Pass 14 I1 files that effect on its own; it is
the same defect seen from the Compare tab, and the "duplicate of" column names it. The grade stays
Important here, since pass 14 I1 is where the wrong verdict is graded.

**I8, confirmed as text, with the consequence recorded by the code itself.** `finding_routes.py:11`,
"Pure: no GUI and no HTTP", of a module whose `Route.kind` is "Which screen the page opens"
(`:205-209`), a list that `:217-224` says is "stated twice and pinned together" with
`gui.contract.FindingRoute.kind` because neither may import the other, and that "part 13's `constant`,
part 14's `section` and this part's `raster` each came within one test of shipping" as a validation
error on every finding. `variable_keys.py:54-75`, `EDITORS`, "Which field the page offers";
`project_shared.py:105-122`, keys "in the order the panel draws them", strings "so the panel shows them
without their quotes", `states` "The row's `States` cell", whose docstring records that a column header
of the tab was changed here; `declaration_plans.py:33-37`, "in the order the form offers them";
`finding_fixes.py:52`, "What the button says". The first docstring line of `project_units`,
`project_types`, `project_shared`, `shared_plans`, `variables` and `variable_keys` each names a tab or a
panel of `ddd gui`.

**I9, confirmed.** My own generated projects (`p2/i9_timing.py`): one units file, a constants file of
one entry, and 10 or 1,200 components of 30 declarations each, opened in my own `ddd gui` on
`127.0.0.1`. Five requests each: `GET /api/constant-plan?action=set&name=K&key=value&raw=5` takes 12-25 ms
at 10 components and 1,398-2,081 ms (median 1,868) at 1,200; `GET /api/unit-plan?action=describe` takes
7-17 ms and 430-472 ms (median 451). `shared_plans.project_of(CONSTANTS, ...)` alone, with a fresh cache
as `gui/api.py:1192-1198` gives it, takes 1,233-1,306 ms on the large project (`p2/i9.txt`), and the
`set` verb does not use what it returns (`gui/api.py:1888-1889`, "`project` is unused by three of the
four"). The pass's figures (1,727-2,212 ms against 570-626 ms) are of the same size.

**I10, confirmed; the KNOWN-in-part tag holds.** Counted on the tree (`p2/i10.txt`): nine plan
handlers in `gui/api.py` (`:797, 921, 1115, 1160, 1163, 1166, 1321, 1402, 1433`, three of them one-line
dispatchers to a shared one), `409 if refused.code in REFUSALS else 500` written 13 times, the "did not
load" sentence 4 times, and six refusal classes of one shape (`DeclarationRefusalError`,
`FileRefusalError`, `ValueRefusalError`, `SharedRefusalError`, `TypeRefusalError`, `UnitRefusalError`).
`git log --since=2026-09-17` up to `2b4bae6c`: `gui/api.py` 75 commits, `gui/server.py` 55 next. The
plan the tag names leaves it open in so many words, under "## Left open": a conditional "copied verbatim
from seven sibling call sites ... Fixing it here would leave eight spellings of one idea"
(`docs/superpowers/plans/2026-09-23-gui-values.md:1502-1505`), so "drift included" is the plan's own
record of a defect copied with the code. My counts differ from the pass's by one in two places (13
against 12, 4 against 3), which a comment or a new site explains and which changes nothing.

**M4, confirmed with a correction.** `ddd.gui.session.kind_of(path, parsed)` of a dumped dictionary
answers `types` (its top level holds `types` and `constants`); the pass says the loader calls such a file
`file-kind`, but for a dump named `dump.json` the loader's answer is `error[file-extension]`. The second
half holds as filed: `Upper.DDD.JSON` checks clean and `find_projects`, what `GET /api/projects` lists,
returns nothing for its directory (`p2/minors_api.txt`). Pass 5 M14 later files the case half from the
SPEC's side.

**M9, confirmed with a smaller count.** My patterns (part N, Task N, step N, ids like `P19a-14` or
`S-M1`, run ids, Appendix, milestone, design N.N, "the branch's", ruling) find 40 lines in 15 modules,
15 of them in `gui/server.py` (`p2/m9_citations.txt`), against the pass's 73 in 25; the examples it cites
are there ("Task 2 is the only caller", `graph.py:5`; "ruling P19a-14" and "run 37737377854",
`gui/server.py:129-134`). The number depends on what one counts as a citation; that a future reader
cannot resolve them does not.

```verdicts
2|I1|CONFIRMED|Important|Important|-|measured: 14 root modules and 4 gui modules import ddd.lsp, outside fan-in ranges 15 navigation 13 units 7 edits 6; with ddd.lsp refused all 12 plan and read modules fail to import and edit_text and assign fail on first call; hover 0, protocol 0, server 1 commits since 2026-09-17 against 18/14/12/8
2|I2|CONFIRMED|Important|Important|-|measured: import ddd.file_plans or ddd.lsp.ranges loads all 10 ddd.lsp modules, server and protocol among them; trial: identity.py's import moved up makes import ddd.identity fail on a circular import, import order deciding; SCC 9 modules by my count, 12 with the pass's parent model
2|I3|CONFIRMED|Important|Important|-|reproduced: with ddd.gui refused, remove_plan of constants.ddd.json applies and check then fails unknown-constant, and add_plan takes x.py; the api answers 409 to both; the two refusals exist only at gui/api.py:2183 and 2247
2|I4|CONFIRMED|Important|Important|-|my own 13 mutants in a copy the tests import: 3 controls caught, all 10 realistic violations pass (from ddd import backends, relative imports, deferred imports of analysis, cli, lsp, gui, a backend); KNOWN dropped: a 2026-09-15 test gap no plan took up, still open
2|I5|CONFIRMED|Important|Important|-|confirmed as text: no row for gui/ and 21 root modules, 38 % of the lines; Six smaller modules, cli.py the only module knowing exit codes and streams (gui/server.py prints and returns EXIT_USAGE), lsp a second front end, ir listed above its importers
2|I6|CONFIRMED|Important|Important|-|reproduced on Windows: a duplicated key and a NaN, each json-syntax to check and refused by the engine, are stamped by ddd id --assign, exit 0; the Linux mode half (no _keep_access) read off the lines, not rerun; STAGING_SUFFIX spelled three times
2|I7|CONFIRMED|Important|Important|-|the copies differ today, not only once: a candidate with its own definition-mismatch is cannot replace, exit 1, to ddd compare and check --baseline, and verdict true with no findings to GET /api/compare; the past divergence is recorded at gui/compare.py:19-24
2|I8|CONFIRMED|Important|Important|-|confirmed as text: tabs, panels, a button, form orders and a row's States cell in root modules, finding_routes called pure while its answer is a screen; the code records the cost itself: the screen list stated twice and pinned by a test, three near-misses
2|I9|CONFIRMED|Important|Important|-|reproduced at 1,200 components of 30 declarations: constant-plan set of one key 1.4 to 2.1 s (median 1.87), unit-plan describe 0.45 s, both about 20 ms at 10 components; project_of alone 1.23 to 1.31 s with a fresh cache, its result unused by set
2|I10|CONFIRMED|Important|Important|-|counted: nine plan handlers, the 409/500 mapping 13 times, the did-not-load sentence 4, six one-field refusal classes, gui/api.py 75 commits since 2026-09-17 against 55 for the next; KNOWN in part holds (2026-09-23-gui-values.md:1502-1505, under Left open)
2|M1|CONFIRMED|Minor|Minor|-|measured: with deferred edges the graph has the SCCs {diagnostics, ir, loading, plugins} and {cli, gui.server}; diagnostics.py says its deferred import is the one thing keeping the graph acyclic
2|M2|CONFIRMED|Minor|Minor|-|confirmed: gui/api.py imports _name_in, _read_json, _served and _source from gui/session.py
2|M3|CONFIRMED|Minor|Minor|-|reproduced: the read plan of a variable stated with a literal degree sign, 1e-1 and -4.0e1 writes "\u00b0C", 0.1 and -40.0 into the reader's file; GET /api/type answers the factor as 0.1
2|M4|CONFIRMED|Minor|Minor|-|reproduced with a correction: kind_of calls a dumped dictionary types, while the loader refuses dump.json as file-extension rather than file-kind; Upper.DDD.JSON checks clean and find_projects lists nothing
2|M5|CONFIRMED|Minor|Minor|-|reproduced: value-plan of 18446744073709551616 into a float32 axis answers 200, POST /api/edit writes it, and the component then fails schema, does not fit 64 bits
2|M6|CONFIRMED|Minor|Minor|-|reproduced: renaming constant OTHER to rpm, a member of Pair_t, is planned and written with no refusal; ddd check then reports name-collision
2|M7|CONFIRMED|Minor|Minor|-|reproduced in process: the GUI fix's set puts "id" after the last key ("volatile"), identity.insertions after "name", against finding_fixes.py:8-10
2|M8|CONFIRMED|Minor|Minor|-|counted 34 regex calls in the seven modules and 12 files spelling component.interface; KNOWN in part holds: WITHIN_DECLARATION is still at lsp/navigation.py:50 and lsp/edits.py:142 (2026-09-22-gui-findings.md:2107, Left open)
2|M9|CONFIRMED|Minor|Minor|-|confirmed with a smaller count: my patterns find 40 lines in 15 modules, 15 in gui/server.py (Task 2 is the only caller, ruling P19a-14, run 37737377854), not 73 in 25; the count depends on the pattern
2|M10|CONFIRMED|Minor|Minor|-|confirmed as text: six messages where the server answers about fourteen methods; nothing else reads them, read by declaration_plans.py:30, project_shared.py:33, project_units.py:20; the _BASE_DATATYPES docstring describes constants
2|M11|CONFIRMED|Minor|Minor|-|counted: cache: dict[Path, Document] written 126 times in 18 modules, as the pass says
```
