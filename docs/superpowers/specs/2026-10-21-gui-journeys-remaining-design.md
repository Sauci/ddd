# The GUI's journeys for the remaining reader actions

- **Part:** 19c of the GUI work, in milestone 8: the last of end-to-end breadth (part 19). After it
  come the user guide (part 20), the independent review, the pilot, and removing *preview*.
- **Status:** design approved section by section; to be planned
- **Depends on:** part 19b (pull request #82, merged into master as `2bc00da`)

Part 19b split its inventory. It closed the 71 starting rows, and handed the 88 rows its first task
added to this part, "on the same spec and helpers". This spec is therefore short. Everything 19b's
spec (`2026-10-08-gui-journeys-every-action-design.md`) says holds here unless a section below says
otherwise:
- what counts as a row, and what "done" means (its §4);
- how each kind of state is reached, and the house rules (§5);
- the page sending its loads once more (§6), which this part extends to the page's own script;
- bugs: a fix contained in one screen, component or library function is made here, red first; the
  rest are recorded for the maintainer (§12).

## 1 The problem

- **88 rows of 19b's inventory name no journey.** 79 were added by 19b's Task 1, six by ruling
  P19b-4, three by ruling P19b-27. By screen:

  | screen | rows |
  | --- | --- |
  | The start page | 3 |
  | The app | 8 |
  | The undo strip | 2 |
  | The canvas | 8 |
  | The components table | 1 |
  | Units | 8 |
  | Types | 11 |
  | Shared files | 8 |
  | Findings | 2 |
  | Files | 11 |
  | Compare | 4 |
  | A component | 13 |
  | Values | 9 |
  | **all** | 88 |

- **A failed read of a new revision drops the table** (P19b-20) on five tabs: Files, Units, Types,
  Shared files and the canvas. Four of the 88 rows are "failing once listed, the table kept", and
  today they hold only for a re-read of the same revision.
- **The page's own script refused a socket leaves the page blank** (P19b-22). It happened once, on
  Windows with Chromium (run 38316603646). It is the one load the page cannot ask for again from its
  own code, and the flake most likely to meet this part's final hunt.

## 2 What was read

- **19b's plan** at `2bc00da`: *The inventory* (274 rows, 88 owned by `19c`), *What was left open*,
  and the final review's three recommendations for 19c (a `held` helper, writing before the press,
  a stamp helper).
- **How a tab reads** (`gui/src/screens/UnitsPage.tsx:30-111`). The query's key is the tab and the
  revision. `placeholderData: (previous) => previous` keeps the last answer while the next one is
  pending, but React Query serves a placeholder only to a pending read: once the read fails, `data`
  is `undefined` and the tab returns the error banner alone (`:98`). The comment at `:110`, "A server
  that stopped answering leaves the table as it was", holds only for a re-read of the same revision.
- **How the page starts.**
  - `gui/index.html` loads one module script. The build makes one entry chunk: `gui/src` has no
    dynamic `import()`. The layout worker and the stylesheets are loads of their own, already asked
    for once more by 19b.
  - The server's policy (`src/ddd/gui/server.py:172`) is `default-src 'self'`, so no inline script
    runs today.
  - The server answers a page request by its path alone (`server.py:619` passes `url.path`), so an
    asset asked for with a query string is the same asset.
- **How the browser is opened.** `launched` in `server.py` opens a one-time address with
  `webbrowser.open`, which honours the `BROWSER` environment variable. Every journey's `ddd gui` is
  started with `--no-browser` (`gui/e2e/fixtures.ts:147`), so no journey has seen that sign-in.
- **The canvas's ranks-only layout** (`gui/src/lib/layout.ts:272`) is taken when dagre throws a
  `RangeError` on a graph too large for it. `large.spec.ts`'s `generatedGui` fixture builds its
  project with `tools/generate_project.py`.

## 3 The answer

- **A journey for each of the 88 rows,** or the recorded reason it has none, written screen by
  screen, each shown to fail under one named change.
- **A tab keeps its last answer** when the read of a new revision fails (§5).
- **The page asks for its own script once more** when the network fails it (§6).
- **Three helpers** the reviews asked for, before the screens' tasks:
  - `held(page, matcher)`, which replaces the eight copies of the held-request recipe, two of which
    drifted to no `{ times: 1 }`;
  - a stamp helper beside `writeUnseen`, replacing the seven copies of the stamp bump;
  - a fixture option starting `ddd gui` with the browser it opens itself (§4).
- **Out-of-date rows write before the press:** the file is written unseen before the reader's
  press, as five 19b journeys do, so no route is needed.

## 4 How the harder rows are reached

19b's §5 holds. Beyond it:
- **Signed in by the code of the browser `ddd gui` opens.** The fixture gains an option that starts
  `ddd gui` without `--no-browser`, with `BROWSER` naming a small recorder that writes the address it
  is given to a file. The journey opens that address. Task 3 measures it on Linux and Windows; if
  Windows' `webbrowser` will not run the recorder, the row names what was tried.
- **Loading states** are held with `held` until the journey has seen them: connecting, analysing
  before the first analysis lands, a project opening, an undo's files being read, a page of
  findings, and every row that reads "reading" or "being read".
- **The server stopped, then answering again.** `failing` fails `/api/state` on the network every
  time. The journey sees the page say it is stopped, and every Apply and every write's button
  disabled. It then removes the route and sees the page carry on.
- **"An Apply the server fails on"** (seven rows): `failing(page, "/api/edit", "http")`.
- **Edge projects** are `copiedGui` copies changed after copying: a module whose file does not load,
  a component file that parses but breaks its schema, a pattern entry, a grid that states nothing,
  an object initialised with text, a grid nothing produces or more than one place does.
- **Ranks only.** A project generated by `tools/generate_project.py`, large enough for dagre's
  `RangeError` in the worker. Task 4 measures the size. If no size reaches it within the gui job's
  timeouts, the row names what was tried, as 19b's §10 allows.
- **The "table kept" rows** are reached after an edit, so that the read that fails is the new
  revision's. 19b's Files journey "the list failing later", a re-read of the same revision, stays as
  it is.

## 5 A tab keeps its last answer

- **The rule.** When a tab's read of a new revision fails, the tab shows its last good answer, with
  the error banner above it. A tab that never had an answer shows the error alone, as today.
- **The same thing only.** An answer is kept across revisions of the same query, never across names
  or tabs: a query's key less its revision must match. So no panel can ever show one unit's answer
  for another.
- **Where it lives.**
  - The decision is a pure function in `gui/src/lib`, under Vitest at 100 %.
  - A hook in `gui/src/state` holds the last good answer.
  - The five tabs P19b-20 named use it: Files, Units, Types, Shared files and the canvas. The panels
    are not changed: their rows in this part are a first read failing, which the rule leaves as it
    is.
- **Writes from a kept table** are unchanged. If the files changed meanwhile, the server refuses the
  write as out of date, as it refuses any stale write.
- **Rows.** The four "failing once listed, the table kept" rows pin it after an edit. One row is
  added for the Files tab: the list failing on a new revision, the table kept.
- **CHANGELOG:** an entry under the unreleased version.

## 6 The page asks for its own script once more

- **The boot script.** A short classic script, inline in `gui/index.html`'s `<head>`, so that it runs
  before the module does.
  - It listens on `window`, in the capture phase, for an `error` event whose target is one of the
    page's module scripts.
  - On the first, it adds a module script with the same `src` and a query string (`?again`).
    Chromium remembers a failed module's address and would not fetch the same one again; the server
    serves the asset by its path alone (§2).
  - On the second, it writes one sentence into `#root` with `textContent`: "ddd gui could not load
    this page. Reload it to try again." The page is blank today.
- **The policy.** `script-src 'self' 'sha256-…'` beside `default-src 'self'`, allowing that one
  script and no other inline one; never `'unsafe-inline'`.
  - The server reads the page it serves once, at start, and adds the SHA-256 of each inline script
    in it. A page with no inline script keeps today's policy.
  - So the hash cannot drift from the script, whatever the build does to it.
  - pytest pins the header with and without an inline script, at 100 %. The tests asserting the
    policy's text change with it.
- **Testing.** The boot script cannot be under Vitest: it must work when the page's own code did not
  load. Two journeys carry it:
  - the script failed once (`route.abort` on its first request): the page is drawn and signed in;
  - the script failing every time: the sentence is shown.
- **Rows.** Two rows are added under *The network*.
- **Documentation:** the security page and `SECURITY.md` say what the one inline script is and why
  its hash is allowed. The CHANGELOG gets an entry.

## 7 The work

One part, one branch (`feature/gui-journeys-remaining`), one pull request. The plan holds the
inventory, its 88 rows moved from owner `19c` to a task, and the three rows §5 and §6 add. In order:
1. **The groundwork.**
   - The 88 rows checked against today's tree, their citations refreshed, the three new rows added.
   - `held`, replacing the eight copies; the stamp helper, replacing the seven.
   - A baseline full run in CI. GitHub's `ubuntu-latest` moved to Ubuntu 26 on 2026-10-19, and this
     is the first run there.
2. **The two fixes,** each red first: the kept answer (§5) and the boot script (§6), with their
   journeys.
3. **The start page, the app around every page, and the undo strip:** 13 rows, and the fixture's
   browser option.
4. **The canvas and the components table:** 9 rows.
5. **Units and Types:** 19 rows.
6. **Shared files:** 8 rows.
7. **Files, Findings and Compare:** 17 rows.
8. **A component and its values:** 22 rows.
9. **The controller's:** the final hunt, the figures, the milestone gate and the close-out.

Each screen's task checks its rows against the code, writes their journeys, fixes the contained bugs
they find, red first, and records the others as rulings for the maintainer.

## 8 CI and checks

- **The legs.** CI keeps 19b's three legs: ubuntu chromium, windows chromium, windows msedge, and
  their timeouts. 19b's 78 journeys added about 2 minutes a pass; about 95 more should add 2 to 3.
- **Windows.** Each task's Windows proof is a full run (`-f repeat=1`). Only the final hunt
  (`repeat=5`) must be clean on all three legs.
- **The gates** are 19b's milestone gate, unchanged.
- **Agents.** One at a time. Opus implements and reviews Tasks 1, 2 and 4; sonnet the rest. The
  final whole-branch review runs on opus, followed by one fix wave.
- **Pushing.** Only the controller pushes, only this branch, after each finished task.

## 9 Documentation

- **The CHANGELOG:** the two fixes, and each contained bug fixed that a reader would notice.
- **The developer documentation:** `held`, the stamp helper, and the fixture's browser option, beside
  the helpers it already lists.
- **The security page and `SECURITY.md`:** the hashed inline script (§6).
- **The plan's *Figures*:** as 19b's, the inventory by screen before and after, the journeys' time
  per leg, the final hunt.

## 10 Risks

- **Ranks only may have no honest way in.** Its row then names the sizes tried (§4).
- **The browser `ddd gui` opens may not be recordable on Windows.** Its row then names what was
  tried (§4).
- **Ubuntu 26 may bring new flakes.** Task 1's baseline run names them before any journey is added.
- **A kept table may be stale under its error.** The banner says the read failed, and the server
  refuses a stale write as out of date.
- **The boot script's second address is cached apart from the first.** Both are the same immutable
  hashed asset, so nothing differs but a cache entry.

## 11 Out of scope

Recorded for the maintainer in 19b's plan, and left there:
- P19b-11 and P19a-7: how long a stale refusal shows;
- P19b-13: a selection that changes nothing offers a change;
- P19b-18: a bare word in a constant's value answered in the json parser's words;
- P19b-24, and the stale decision made inline in ten `.tsx` files;
- Firefox, Safari and macOS;
- the user guide (part 20).

## 12 Decisions taken

The maintainer's answers while this was designed:
- **P19b-20 is fixed, then pinned,** across the five tabs it names, though it spans five screens.
- **P19b-22 joins the part.** No other recorded item does.
- **One part, shaped like 19b:** groundwork, the two fixes, a task per screen, one pull request and
  one final hunt.

Taken in the design:
- **The boot script is inline behind a hash,** not a same-origin `/boot.js`, which would be one more
  load the network can refuse in the same way.
- **The hash is computed by the server at start,** from the page it serves, not pinned in the source.
- **The kept answer is the tabs' alone;** the panels keep today's behaviour.
- **Compare's four rows join Files and Findings** in Task 7.
