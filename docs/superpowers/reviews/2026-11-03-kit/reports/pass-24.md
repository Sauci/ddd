## Pass 24: the code sweep

By a reader who wrote none of passes 1 to 23, on 2026-11-06, on the tree at master `2b4bae6c`. Scratch:
`SCRATCH/pass-24/` (every path below is relative to it). Everything ran in copies made fresh from the tree with
`git archive HEAD | tar -x -m`: `t0/` for the Python probes, and for the page `C:/Users/lmbsog0/AppData/Local/Temp/p24-gui/g0`
(a path without a uuid, the tree's `gui/node_modules`, `gui/src/generated` and built `src/ddd/gui/static` copied in,
nothing installed or downloaded). That my copy's code is what ran was checked each time it mattered: `det.txt` and the
CMake transcripts print `ddd.__file__` from `t0/src`, and the page runs started `python -m ddd gui` with `PYTHONPATH`
the copy's `src`. Every server bound `127.0.0.1`; none is left running (`tasklist` at the end: no python, node or
headless Edge of mine).

### Scope covered

**Read first.** `review-brief.md`; `passes.md`, its introduction and Part E; the Scope covered and candidates blocks
of `pass-1.md` to `pass-23.md` and the verdicts blocks of `verify-1.md` to `verify-23.md`, extracted whole into
`digest.txt` (1,724 lines) and read in full; `verify-15.md`'s "seen in passing" note, `verify-19.md`'s M11 text and
its transcripts `verify-17-19/p19_m11*.{py,txt,log}`; `notes/coordinator-todo.md`, its first section only.

**What no pass read closely** (`inventory.txt`, `who_read.txt`: each file against the scopes that name it).
- `src/ddd` (87 modules, 39,534 lines), `editors/vscode/src` (`extension.ts` 82, `config.ts` 47), `cmake/Ddd.cmake`
  (794), `tools/` (4 files), `docker/` (6 files) and `examples/plugins/ddd_layout.py` (327): every file is claimed read
  in full, line by line, by at least one pass. Several by exactly one: `toolbox/*` and `elf.py` (pass 11),
  `lsp/hover.py` and `lsp/protocol.py` (10), `gui/contract.py`, `graph.py`, `findings_by_file.py` (14),
  `gui/server.py` (12), the extension (10), `tools/dev_version.py`, `site_versions.py` and `docker/*` (20).
- `gui/src` (107 files, 16,571 lines outside tests and stories): claimed whole at folder level by passes 3, 15 and 16.
  Three small components were read only in part (pass 3) or as views (pass 16): `components/FlowEdge.tsx` (89),
  `ModuleNode.tsx` (28), `Changes.tsx` (27). I read them whole: nothing to report. I also read `ui/ComboBox.tsx`
  (176), `components/UnitPicker.tsx` (58), `screens/UnitPanel.tsx:57-274`, `screens/UnitsPage.tsx:60-160`,
  `components/UnitPanelView.tsx:40-215` and `lib/projectUnits.ts:107-163` for the first lead.
- **Not read by any pass, nor by me:** `gui/src/stories/fixtures.ts` (3,253) and the 32 story files (2,610 lines by my
  count), which only the screenshot job runs; `gui/src/generated/*.ts` (6,560 lines, git-ignored, generated from the
  schemas and `ddd.gui.queries`).
- Read for the seams and the leads: `src/ddd/backends/base.py:130-397`, `lsp/ranges.py:79-300`, `lsp/server.py:450-500`,
  `gui/src/api/client.ts:150-435`, `gui/contract.py:1618-1666` and its `uses` fields, `gui/queries.py:712-930`,
  `cmake/Ddd.cmake:180-330, 540-690, 760-794`, `docs/build_integration.rst:50-100, 280-315`,
  `docs/developer_documentation.rst:1-110`, `analysis.py:1-80`, `backends/a2l/model.py:355-400`, CPython 3.13's
  `ntpath.py:562-751`, React Aria's `useCloseOnScroll.mjs`.

**Ran.**
- Lead 2: `lead2/det.py` (the real `ddd generate c` in process, CPython's `_getfinalpathname` wrapped to create the
  output directory after its first failure) -> `lead2/det.txt`; `lead2/race_mkdir.py`, 400 real `generate c`
  processes against a plain `os.mkdir` from another process -> `lead2/race_mkdir.txt`.
- Lead 1: eight Playwright scripts in headless Edge (`lead1/*.mjs`) on copies of `examples/demo` and on generated
  "many" projects of 2,000 and 35,000 declarations (`tools/generate_project.py` of my copy): `rename_keys.txt`,
  `rename_keys2.txt`, `trace_key*.txt`, `human.txt`.
- Seams: CMake 4.3.1 (CLion's) and Ninja 1.13.2 with MinGW gcc 15.2 on a two-component project, built under `STRICT`
  and under `SEVERITY` (`seam-cmake/transcript.txt`, `b-*.log`); CMake's `string(JSON)` against the loader on a file
  with a byte order mark (`seam-bom/`); `ddd dump` against `generate --dictionary` with and without `--address-map`
  (`seam-dict/`); the GUI's raster rename, constant rename and Shared files rows through `Api.handle` in process,
  each followed by `ddd check` (`rules/*.txt`); the Units tab's counts beside the dictionary on `demo`, `vocabulary`
  and `structures` (`rules/units_counts.txt`: they agree, the page counting what states a unit and the dictionary
  what resolves to it, as each says); the findings filter's values on both ends (`queries.py:413-433` against
  `client.ts:183-191`: they agree).
- Afterwards: the tree's `git status` (plain and `--ignored`) as before (`status-*.txt`), its four built page files
  hashing as before (`tree-static-before.sha`), no process of mine left.
- The split: `split/graph.py`, the import graph of `src/ddd` read with `ast` (top-level, deferred and
  `TYPE_CHECKING` imports kept apart) -> `split/graph.json`, `split/graph.txt`.

**Not covered.** No real (headful) Edge with smooth scrolling, so the first lead's original trigger rests on the
driver's scroll and on a wheel turn, not on a person's smooth scroll; CMake below 4.3 (the byte-order-mark seam holds on
4.3 only); Linux and macOS for the second lead (it is a Windows path rule); no mutation testing; the C and the A2L of one
object beyond what pass 8's oracle did, which I did not redo.

### Strengths

- **The dictionary has one writer.** `ddd dump -o` and `generate all --dictionary` write byte-identical files for the
  demo, and so does `generate --address-map ... --dictionary` (addresses never enter the dictionary); `compare` reads
  the one as a replacement for the other (`seam-dict/`).
- **Name grammars live once.** `C_IDENTIFIER_PATTERN`, `IDENTIFIER_MAX_LENGTH`, the section, raster and type patterns
  are defined in `models/common.py:57-155` and imported by the language server's rename (`lsp/navigation.py:780`); the
  page holds no copy and leaves the refusal to the server's plan.
- **Positions are counted as the protocol counts them, both ways**: outgoing in UTF-16 code units
  (`lsp/ranges.py:232-245`), incoming the same (`:163-171`, a non-BMP character counted two).
- **The page never builds what it writes.** `POST /api/edit` carries the operations of the server's own plan back
  (`contract.py:1618-1666`, `lib/units.ts:208-216`), the page adding only the label; query types are generated from
  the server's models, and `encodeURIComponent` on the page agrees with `parse_qs` on the server (`server.py:697`).
- **Shared copies where the code shares**: build records are found by one function for the editor and the GUI
  (`gui/session.py:54, 248, 569` call `lsp.discovery.discover`); the checks a lone file holds back are derived once
  from the registry (`diagnostics.py:270-273`) for the command line and the language server.
- **The layer table holds for the modules it names**, measured: no import cycle among top-level imports; `elf.py`
  imports nothing of `ddd`; each backend imports only `backends.base`, `ir` and `models`; `lsp` imports no backend; the
  toolbox only `analysis`, `diagnostics`, `elf`, `loading`; `plugins` reaches a backend for typing alone
  (`split/graph.txt`).
- **Bitfield members are kept out of the A2L** rather than given a guessed mask (`backends/a2l/model.py:355-370`), so
  no record can contradict the C compiler's bit allocation, big-endian included.

### Issues

#### Critical

None.

#### Important

- **I1. `<target>.ddd`, the module's own component check, ignores the image's `STRICT` and `SEVERITY`: green where the
  build is red, red where it is green.**
  Location: `cmake/Ddd.cmake:322-324` (`check "${description}" --standalone`, no `-W`, no `--strict`), against
  `docs/build_integration.rst:301-305` ("A tool that ignores it reports a different set of findings than the build
  does ... the same working tree would be clean in one place and failing in the other ... the three cannot drift
  apart") and the comment at `cmake/Ddd.cmake:180-181`.
  Trigger: components `sensor` (outputs `Speed` and `SPEED`) and `reader`; `ddd_generate(fw ... STRICT)`: `ninja`
  exit 1, `error[name-similar]`; `ninja sensor.ddd` exit 0, the same finding as a warning. With `_Speed` for `SPEED`
  and `SEVERITY reserved-identifier=warning` instead: `ninja` exit 0 and `fw.exe` runs; `ninja sensor.ddd` exit 1,
  `error[reserved-identifier]`. The build record beside the build says `"strict": true` and
  `"severity": ["reserved-identifier=warning"]` respectively, and the language server and the GUI apply it, so the
  module's own target is the one surface that disagrees with the build (`build.ninja:113` shows its command).
  Evidence: reproduced, `seam-cmake/transcript.txt`, `seam-cmake/b-strict.*.log`, `b-relax.*.log`.
  Consequence: the supplier check the page offers (`build_integration.rst:77-79`) passes a component the
  integrator's ci then rejects, and a project that must relax a check project-wide (pass 6 M11: an external type
  named `size_t`) gets a `<target>.ddd` that can never pass. Fix: `ddd_add_component` takes no `STRICT` or
  `SEVERITY`, and a component can be linked into several images; either give it the keywords, or have the target
  take the policy of a named image's record, or say on the page that it checks under the default policy and drop
  "cannot drift" (S).

#### Minor

- **M1. A run refuses its own files as "outside the output directory" when another process creates that directory
  meanwhile (lead V9 settled).**
  Location: `src/ddd/backends/base.py:228` and `:233-234`; the same resolve-and-compare in `Manifest` at `:148`,
  `:181-184` and `:199-200`.
  Cause: `render` resolves the output directory once and each file again, then compares with `is_relative_to`. On
  Windows CPython's `ntpath.realpath` strips the `\\?\` prefix only if its second `_getfinalpathname` fails with the
  same error as the first (`ntpath.py:745-749`); a directory created between the two calls turns
  `ERROR_PATH_NOT_FOUND` (3) into `ERROR_FILE_NOT_FOUND` (2), the prefix stays, and a `\\?\` path is compared with a
  plain one.
  Trigger: `ddd generate c demo.ddd.json -o out` into a fresh `out` while anything else creates `out`: a second
  `ddd` run (verify-19 M11's 9 of 12 failures), or a parallel build's `mkdir -p`. Exit 2, `ddd: backend 'c' writes
  outside the output directory: //?/<work>/o302/SensorHub.h`, nothing written.
  Evidence: reproduced deterministically, `lead2/det.txt` (winerror 3 then 2 on `out_race/ddd_globals.c`, exit 2;
  the control writes all seven files), and with real processes, `lead2/race_mkdir.txt` (2 of 400 runs refused when my
  `os.mkdir` landed in the window, delays 0.506 and 0.521 s of a 0.61 s run). The `Manifest` copies read off: the same
  race there leaves a written file out of the record, or a stale one in place, in silence. Fix: create the directory
  before resolving it, and compare paths resolved alike (S). Minor: it needs a concurrent creation and fails loud.

- **M2. A scroll while a chooser's list is open throws away what was typed, and the next keys append to the old
  spelling: "km", one wheel notch, "/h" plans `rpm` to `rpm/h` across 67 files (lead V8 settled).**
  Location: `gui/src/ui/ComboBox.tsx:108-112` (`onOpenChange(false)` calls `onClose`), `screens/UnitPanel.tsx:246`
  and `:256` (the field reads `typed ?? to ?? name`; closing drops `typed`); React Aria closes the popover on any
  scroll of an ancestor of the field (`react-aria/dist/private/overlays/useCloseOnScroll.mjs`). Against
  `ComboBox.tsx:45-49`, which lists the list closing "by Enter, Escape, Tab, ▾ or the focus leaving the field" only.
  Trigger: a generated "many" project of 2,000 declarations, Units tab, `rpm`, the `Rename rpm to` field (at y 908 in a
  1280x800 window, below the fold): select all, type `km`, turn the wheel one notch up: the list closes and the field
  reads `rpm`; type `/h`: `rpm/h`; Enter: "Apply to 67 files", whose sentence names the files and not the new
  spelling. V8's `rpmpm2` is the same mechanism: the driver's scroll into view fires about 20 ms after the field
  takes the focus, and a key typed in that window is dropped (`trace_key4.txt`: `rpmr`, list open at 298 ms, scroll
  at 299 ms, list closed and `rpm` back at 322 ms; with a one-second pause the key is kept; nothing is lost when the
  field is already in view, `human.txt`). The typed text equal to the unit's own spelling closes the list too
  (`lib/projectUnits.ts:136` adds no "As typed" entry), harmlessly.
  Evidence: reproduced in Edge, `lead1/human.txt`, `rename_keys2.txt`, `trace_key2.txt` to `trace_key4.txt`. Same root
  as pass 15 I1 (text typed and left is dropped), a trigger it does not have: the reader never left the field. Minor:
  the field shows the composed spelling before Enter, and Undo takes it back. Fix: drop what was typed only on Escape
  or on leaving the field, not on every close React Aria makes (S).

### Status of the 2026-09-15 findings in this area

None in this area: the sweep's seams fall in the areas whose passes (9, 10, 13, 14, 19) already tabulated the
2026-09-15 findings.

### Open questions

- **Which policy should `<target>.ddd` apply (I1)?** A component can sit in several images with different `STRICT` and
  `SEVERITY`. "The image's" means a keyword or a record to name the image; "the default" means the page's
  "cannot drift" sentence goes and suppliers are told their check is not the build's; "its own" means
  `ddd_add_component` grows `STRICT` and `SEVERITY`, a second place to keep them in step.
- **May React Aria close a chooser's list behind the reader's back (M2)?** Keeping its close-on-scroll means the page
  must keep the typed text across such closes; turning it off means a list that stays put while the page scrolls under
  it.

### Test gaps

- No test runs `<target>.ddd` under a project with `STRICT` or `SEVERITY` (`tests/test_cmake.py:1642-1725` checks
  components wrong by default only).
- No journey types into a chooser key by key: every one uses `fill()` (`gui/e2e/units.spec.ts:287`,
  `project-units.spec.ts:84, 237, 371`, `shared.spec.ts:158, 177`; no `pressSequentially` or `keyboard.type` in
  `gui/e2e`), and none scrolls while a list is open.
- The confinement of `render` is tested only against real escapes (`tests/test_backends.py:378`,
  `tests/test_plugins.py:2005-2071`), never against an output directory that appears while a run resolves it.

### Assessment

The code that fell between the passes is small: every source file of the scope was claimed read in full by some pass,
and the stories and generated types are the only parts nobody read. So the sweep's weight is in the seams and the
leads, and there the picture is better than the area reports suggest: where two sides share a definition they agree
(one dictionary writer, one name grammar, one record discovery, one held-back set, UTF-16 positions both ways, the
page echoing the server's plans), and the disagreements come where a rule was written twice. Measured, the rules held
twice are: the severity policy (command line, build record, CMake's build-info/check/generate, and the module's own
`<target>.ddd`, the only one that ignores it: I1); the raster rename (the GUI's copy escapes `a"b`, `rules/raster_rename.txt`,
the language server's writes it raw: pass 10 I9); the constant rename (both copies leave a `condition` spelling the old
name); the `*.ddd.json` case rule (pass 5 M14); the kind of a file (pass 2 M4; CMake 4.3 agrees with the loader on a
byte order mark, `seam-bom/`); the unit spelling (pass 15 M10); the number grammar (15 M13); the 4,300-digit guard
(17 M2); the retry on replace (19 M1); the request size (3 I8, 15 I4); and the line break, where `lsp/ranges.py:79`
splits at `\n` alone while the protocol also breaks at a bare `\r` (read off, not run; unnumbered Minor). The import graph
confirms passes 2's account: 87 modules, 363 edges, no cycle among top-level imports, the cycles it names among deferred
ones, and table rows true of the modules they list. Both leads were real and are settled with their causes (M1, M2).
Lines on earlier candidates: **10 I10 is wider**: the GUI's constant rename (`GET /api/constant-plan`, then
`POST /api/edit`) also leaves `"condition": "CELLS > 2"` beside `Big[SLOTS]`, check clean, `#if CELLS > 2` in the C
(`rules/const_rename.txt`), so the rule is wrong in both of its copies. **2 I5 is slightly wider**: `compare.py`, which
the page calls "the second consumer of the contract", is also imported by the analysis at top level
(`analysis.py:18-24`, its field comparison), so the front end depends on it. **19 M11 stands**, its third failure mode
being M1 here.

```candidates
24|I1|cmake/Ddd.cmake:322|<target>.ddd ignores the image's STRICT and SEVERITY: green where the build is red, red where it is green, against cannot drift apart
24|M1|src/ddd/backends/base.py:233|A run refuses its own files as outside the output directory when another process creates that directory meanwhile: //?/ kept by ntpath.realpath
24|M2|gui/src/ui/ComboBox.tsx:108|A scroll while a chooser's list is open drops what was typed and the next keys append: km, a wheel notch, /h plans rpm to rpm/h in 67 files
```
