# The GUI's Journeys for the Remaining Reader Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every one of the 88 rows part 19b handed over has a journey or a recorded reason it has none; a screen keeps its last answer when the read of a new revision fails, and never over a refusal; and the page asks for its own script once more when the network fails it.

**Architecture:**
- **Groundwork first.** Task 1 re-checks the rows against today's tree, and adds `held` and `restamp`, which 19b's reviews asked for. Two fixtures come with the tasks that need them: `openedGui` (Task 3) and `chainedGui` (Task 4).
- **The two fixes next, red first** (Task 2), because four of the rows can only be written against the first of them:
  - `kept` and `shown` in `gui/src/lib/kept.ts` decide what a screen shows once a read has failed, and `refusedRead` tells a failure from a refusal; `useKept` in `gui/src/app/useKept.ts` holds the answer; five tabs, the component page and the values grid use it.
  - An inline boot script in `gui/index.html` asks for the page's module once more; the server allows it by its SHA-256, computed at start from the page it serves (`page_policy`, `src/ddd/gui/server.py`).
- **Then one task per group of screens,** each writing its rows' journeys, each journey shown to fail under one named change.

**Tech Stack:**
- **Journeys:** Playwright 1.63, driving the compiled pages served by a real `ddd gui` over a copied example.
- **Page:** React 19 + TypeScript, TanStack Query with `retry: false`, Vitest at 100 % over `src/api`, `src/lib` and `src/state`.
- **Server:** Python 3.12 to 3.14, `http.server`, `html.parser`, `hashlib`; pytest at 100 % line and branch.
- **CI:** part 19a's three legs (ubuntu chromium, windows chromium, windows msedge), with `-f repeat=N` hunts.

**Spec:** `docs/superpowers/specs/2026-10-21-gui-journeys-remaining-design.md`, and through it part 19b's, `docs/superpowers/specs/2026-10-08-gui-journeys-every-action-design.md`, whose §4, §5 and §12 hold here unchanged. Read both before any task. Where this plan departs from them, the departure is a ruling in *Rulings taken* at the end, with its reason.

## Global Constraints

Every task's requirements include this section. It is part 19b's, with this part's branch and leave.

**Running things**

- **The machine.** The work runs on the Linux development PC, in the main checkout `/home/sauci/Documents/Github/ddd`. Docker cannot see the session scratchpad.
- **Interpreters.** There is no `python` on PATH: always use `.venv/bin/python`. Node is not on PATH either; it is at `~/.local/node-v24.21.0/bin`.
- **Never add `-q` to pytest.** `pyproject.toml` already sets it in `addopts`. A second one removes the `N passed` line while pytest-cov still prints its coverage line, so the output looks fine and says nothing.
- **A pipeline reports its last command's exit status.** Capture each tool's own: `.venv/bin/python -m pytest > gate.txt 2>&1; echo "EXIT=$?"; tail -n 3 gate.txt`. A run that finished ends with its **summary line**; a tail ending in a stack trace did not finish, whatever the exit code says.
- **A stale `.coverage` file.** Once it made pytest answer `4445 passed` with exit 3 and **no coverage line**. If the coverage summary is missing, delete `.coverage*` (gitignored) and run again.
- **Journeys:**
  1. Run `cd gui && npm run build` first, because the journeys drive the **compiled** pages in `src/ddd/gui/static`.
  2. Then run `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --output=<a path outside the repository>`. Writing `--output` inside `gui/` fails with `EACCES`.
- **Never run the journeys while the Docker screenshot run is running.** Both drive Playwright over the same `gui/` checkout, and the journeys then fail with "Playwright Test did not expect test() to be called here". Run one after the other.
- **Screenshots and docs** run from the repository root, in Docker:
  - `UPDATE=1 docker compose run --rm gui-screenshots` rewrites the references; without `UPDATE=1` it compares.
  - `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs` builds the docs.
- **Page schemas:** run `cd gui && DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas`. `gui/src/generated/` is gitignored, so grep the generated file and let `npm run typecheck` prove the page agrees.
- **Stopping a server you started.** List its PID by process name, then kill it in a **separate** command:
  1. `ps -eo pid,comm,args | awk '$2 ~ /^python/ && /<pattern>/'`
  2. `kill <pid>`

  Never `pkill -f` and never `pgrep -f`: the shell running the command holds the pattern in its own command line, so `pkill -f` kills that shell, and a `pgrep -f` wait loop never ends. Leave nothing of yours running.
- **Never route around a refusal.** If the permission check refuses a command, stop and say so in your report. Never reach the same effect another way.
- **Delete only what you created,** each by its exact path, and never with a glob outside the session scratchpad.
- **Two `ddd gui` Docker containers on ports 8124 and 8125 belong to other work.** They run `ddd gui` over this checkout, with `PYTHONPATH=/work/src`, so they serve its `src/ddd/gui/static`. Leave them alone, and never build an ablated page into that directory (below).

**Windows, through CI alone**

- **No Windows machine is at hand.** A change whose proof is a Windows leg is pushed to this branch and run there. Each attempt costs about ten minutes, so batch what can be batched.
- **Only the controller pushes, and only this branch,** `feature/gui-journeys-remaining`, under the leave recorded in *Prerequisites*. Never master, never `--force`. An implementer commits locally and reports; the controller pushes, starts the run, and hands the result back.
- **Each task's Windows proof is a full run** (spec 19b §8), started by the controller once the task's commits are pushed, and read before the task's review is closed. Only the final hunt must be clean on all three legs.
- **Starting a run:**
  - a full run of every job: `gh workflow run ci.yml --ref feature/gui-journeys-remaining -f repeat=1`;
  - a hunt: `-f repeat=5`.

  Wait on it once, in the background. Never poll it in short loops.
- **Reading a run:**
  - its jobs: `gh run view <run> --json jobs`;
  - a job's log: `gh run view --job <job> --log`.
- **A failed run's Playwright report** (`gh run download <run> -n playwright-report-<os>-<browser> -D <scratchpad>/<run>`) is downloaded only under the leave recorded in *Prerequisites*. Read each failed test's `error-context.md`, the page's accessibility snapshot at the failure, and the network entries in its trace. Nothing else is downloaded without asking.
- **`ubuntu-latest` is Ubuntu 26** since 2026-10-19. Task 1's baseline run is the first of this repository there.

**Gates**

- **Python:** `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare** (it checks `src/ddd` and `tools`, strictly).
- **Page:** `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`, with Vitest at 100 % on statements, branches, functions **and** lines over `src/api`, `src/lib` and `src/state`.
- No `pragma: no cover`, no skips, no xfails.
- **No commit leaves a gate red.**
- **CI runs more than the development PC does:**
  - Python 3.12, 3.13 and 3.14, on ubuntu **and** windows runners;
  - the journeys on three legs: ubuntu with Chromium, windows with Chromium, windows with the runner's own Edge;
  - **Windows file locks:** Windows refuses to rename over, or delete, a file that another handle holds open (`ddd.editing.REPLACE_TRIES`). `writeUnseen` in `gui/e2e/demo.ts` already tries a rename again while Windows refuses it;
  - **Windows line endings:** the runners check files out with CRLF. Anything this part hashes or compares as text must say what it does with a CR (Task 2, Review Focus 1).

**What the gates cannot see**

- **No journey is vacuous** (spec 19b §5). Each new journey's key assertion is shown to fail under one named change to the page or the server, and the report says which change, and which assertion died.
  - **Ablate the page in a scratch copy, never in place.** Build the ablated page into a copy of the package (`npx vite build --outDir <scratch>/pysrc/ddd/gui/static --emptyOutDir`, the rest of `src/ddd` copied beside it), and start the journeys' server from that copy (`DDD_PYTHON` as usual, `PYTHONPATH=<scratch>/pysrc`, `PYTHONDONTWRITEBYTECODE=1`). Check that the copy's `ddd.gui.server.static_directory()` is its own. The containers on 8124/8125 serve the checkout's static, so the checkout's page only ever holds the real build.
  - **Restore every source ablation by exact edit.** Save `git diff` to a patch first. Compare it after each restore, and run `git status --porcelain <file>` immediately before every restore. Never `git checkout -- <file>` over uncommitted work.
  - **Ablate Python in a scratch `git worktree`,** with pytest run from inside it (`pyproject.toml`'s `pythonpath` beats `PYTHONPATH`), and `PYTHONDONTWRITEBYTECODE=1`.
  - **Confirm one ablation kills something before trusting that another kills nothing.** A survival is believed only after `PYTHONHASHSEED=0`, `1`, `4` and `7` (Python), or `--repeat-each=5` (a journey).
- **A coverage gate cannot see data.** Ablate every new data value (a sentence, a header, a default) and confirm that a **named** test dies.
- **Never conclude what *else* pins something from a narrowed run** (no `-k`, no path argument, no `-g`). That is a whole-suite question; copy the summary line in rather than paraphrasing it.
- **No decision may live in a `.tsx` file.** Every judgement lives in `gui/src/lib`, `gui/src/state` or `gui/src/api`, under the Vitest gate; a `src/app` module is glue only.
- **A refusal or banner is asserted as its whole sentence.** Read every expected sentence off the running code, never out of this plan. This plan's quoted strings were read at `2bc00da` and are a guide.
- **A journey waits on what the reader sees.**
  - Never `page.waitForTimeout`, beyond the recorded exception in `demo.ts`'s `settled()` (P19a-8).
  - Never `page.waitForResponse` to coordinate, beyond the recorded exception in `hostile.spec.ts` (P19a-30's D2).
  - Never a count read with `.all()` before what it counts is drawn.
  - Use `toHaveCount`, `toBeVisible`, `toHaveText`, `toHaveCSS`, or `expect.poll` on what the page shows.
  - A request the journey must see held is held with `held` (Task 1) and let through in a `finally`; a request whose answer the journey must read is held with `held`'s `onAnswer`.
- **An out-of-date refusal is reached by writing before the press:** the file is written unseen (`writeUnseen`, `driftMaxUnseen`) after the page drew its plan and before the reader's press, so no route is needed. A journey that must then see the refusal go uses `restamp` (Task 1).
- **A journey leaves no visible window between a write and its stamp** (`driftMaxUnseen`, `writeUnseen` in `gui/e2e/demo.ts`). A change the watcher must see is written plainly; a change it must not see yet is written unseen.
- **Playwright's `retries` stays 0.** No journey is repeated to pass.
- **The suite forbids skips** (`test_nothing_in_the_suite_skips`).

**Prose**

- **A sentence stating a measurement gets the measurement run as it is written,** against the file it names, with the exit status copied from *that* run.
- **A probe is quoted with the machine, the commit, the project and the run it came from.**
- **Cite by name, not by line number.** Line numbers in this plan were measured at `2bc00da`, and go stale the moment an earlier task edits the file.
- **Before ruling on a trade-off, confirm that both sides of it can actually happen.**

**Conventions**

- **Commits:** a lowercase imperative subject on **one line**, with no `feat:`-style prefix, and a body saying why. The trailer names the model that wrote the commit: `Co-Authored-By: <the model you are> <noreply@anthropic.com>`. A dispatch never tells you which model to name (part 18b's P18b-15). Never `--amend`, never rebase, never push.
- **Every UI pull request carries a screenshot of what it added,** the maintainer's standing rule. A fix that changes what the page shows changes or adds its Ladle reference, made in Docker with `UPDATE=1`, opened and described in words.
- **Reports go where your dispatch says,** to the report file it names.
- **If a brief or this plan is wrong, say so in your report** rather than working around it silently.
- **Bidi characters.** A unicode escape typed through the tools can land as the character itself: a right-to-left override did, twice, in part 18. Write such a character as words ("U+202E"), or build it in code with `chr()`. Before any push, the controller scans the commit messages and the changed files for U+202A to U+202E and U+2066 to U+2069.
- **A bug a journey finds** (spec 19b §12):
  - fixed in its task when the fix stays within one screen, one component or one library function, with the journey red first;
  - otherwise recorded as a ruling for the maintainer, its row naming the bug as the reason it has no journey, with the evidence.

## Prerequisites

1. **The branch.** The work is on `feature/gui-journeys-remaining`, made from master `2bc00da` (part 19b, PR #82). Its first commit is the spec, `7f96986`; then the spec's amendment by the maintainer's answer while planning (§12), and this plan.
2. **The baseline gate.** Run the milestone gate (below) once at this plan's commit, before Task 1, so that every later red is this part's own.
3. **Read both specs.** 19c's says what is new; 19b's §5 says how each kind of state is reached.
4. **The maintainer's leave,** asked for before Task 1 and recorded here with its date:
   - to push `feature/gui-journeys-remaining` alone, for this part's CI runs and hunts;
   - to download the Playwright report of any failed run of this part.

   It was given on 2026-10-13 for part 19c's branch: "Same as 19b", meaning push that branch only, never master and never force, and download any failed run's report without asking. It carried to this branch on 2026-10-21, when the maintainer chose it for part 19c and said go.

## Review Focus

The failure modes the spec implies but no row of the inventory would test on its own, most likely first. Each has its test in the task that owns the code.

1. **The script's hash on Windows.** The runners check `gui/index.html` out with CRLF, and Vite copies the inline script as it finds it. A browser hashes a script after the HTML parser has turned every CRLF and lone CR into LF, so a hash of the raw bytes allows nothing on Windows, and every page there loads with its boot script refused. *(Task 2: a pytest case hashing a page written with CRLF against the hash of its LF text; `units.spec.ts`'s "no page reports a violation of its content security policy" on the windows legs.)*
2. **A kept answer shown for another question.** The canvas's query names the project; a tab of one project must never show another's graph after a failed read. *(Task 2: Vitest cases for `shown` across identities.)*
3. **A refusal is never kept.** A values grid whose object was renamed away must show its refusal alone, never the old grid under it; a kept grid would offer cells of an object the project no longer has. *(Task 2: Vitest's `refusedRead` and `shown` cases; Task 8's row "an object no longer declared…", whose grid must be gone.)*
4. **A first read that fails still shows the error alone.** The fix must not turn "the units failing to load" into an empty table with a banner. *(Task 2: Vitest; Task 5's "the units failing to load" journey.)*
5. **The boot script retries the page's module and nothing else.** A stylesheet's failed load reaches the same capture-phase listener. *(Task 2: 19b's `network.spec.ts` stylesheet journeys keep passing unchanged, and a stylesheet failed every time shows no sentence.)*
6. **The boot script's sentence never covers a page that loaded.** *(Task 2: "the page's script failed once" asserts the sentence has count 0 once the canvas is drawn.)*
7. **An error banner reads as a sentence.** A request the server fails shows the server's own message, never a code. *(Every error-banner journey of Tasks 2 to 8 asserts the whole sentence.)*

## File Structure

| File | Task | What |
| --- | --- | --- |
| `gui/e2e/demo.ts` | 1 | `Matcher`, `held`, `restamp` |
| `gui/e2e/helpers.spec.ts` | 1, 3 | `held`'s and `restamp`'s journeys (1); `openedGui`'s (3) |
| `gui/e2e/start.spec.ts`, `canvas.spec.ts`, `compare.spec.ts`, `files.spec.ts`, `project-units.spec.ts`, `shared.spec.ts` | 1 | the eight held-request copies replaced by `held` |
| `gui/e2e/declarations.spec.ts`, `files.spec.ts`, `keys.spec.ts`, `start.spec.ts`, `types.spec.ts`, `values.spec.ts` | 1 | the seven stamp bumps replaced by `restamp` |
| `gui/src/lib/kept.ts`, `kept.test.ts` | 2 | `Kept`, `kept`, `refusedRead`, `shown`: what a screen shows once a read failed |
| `gui/src/app/useKept.ts` | 2 | the glue holding a tab's last good answer |
| `gui/src/screens/FilesPage.tsx`, `UnitsPage.tsx`, `TypesPage.tsx`, `SharedPage.tsx`, `GraphPage.tsx`, `ComponentPage.tsx`, `ValuesPage.tsx` | 2 | each reads its answer through `useKept` |
| `gui/e2e/kept.spec.ts` | 2 | the seven "kept" journeys |
| `gui/index.html` | 2 | the inline boot script |
| `src/ddd/gui/server.py`, `tests/test_gui_server.py` | 2 | `page_policy`, `GuiServer.policy`, and `_send` carrying it |
| `gui/e2e/network.spec.ts` | 2 | the page's script failed once; failing every time |
| `docs/gui_security.rst`, `CHANGELOG.md` | 2 | the hashed inline script; both fixes |
| `gui/e2e/fixtures.ts` | 3, 4 | `start`'s `browser` option, `recorder` and the `openedGui` fixture (3); `generated`'s shape and size, and the `chainedGui` fixture (4) |
| `gui/e2e/start.spec.ts`, `undo.spec.ts` | 3 | the start page, the app and the undo strip |
| `gui/src/screens/StartPage.tsx`, a `gui/src/lib` module and its test | 3 | the list's buttons held from the press until the start page goes |
| `gui/e2e/canvas.spec.ts` | 4 | the canvas and the components table |
| `tools/generate_project.py`, `tests/test_generate_project.py` | 4 | the `chain` shape |
| `gui/e2e/project-units.spec.ts`, `types.spec.ts` | 5 | Units and Types |
| `gui/e2e/shared.spec.ts` | 6 | Shared files |
| `gui/e2e/files.spec.ts`, `findings.spec.ts`, `compare.spec.ts` | 7 | Files, Findings and Compare |
| `gui/src/screens/FindingsPage.tsx`, `gui/src/lib/findings.ts`, `findings.test.ts` | 7 | a fix the server failed on chosen again |
| `gui/src/screens/CompareView.tsx`, `gui/src/components/FindingPanelView.tsx` | 7 | a baseline's finding named as the baseline's in its panel |
| `gui/e2e/declarations.spec.ts`, `values.spec.ts` | 8 | a component and its values |
| `src/ddd/gui/session.py`, `tests/test_gui_session.py` | 3 | `find_projects` lists no empty image and no image twice (ruling 18) |
| `gui/src/screens/ComponentPage.tsx` | 3 | the declarations table's cells follow a stopped server (ruling 18) |
| `gui/src/lib/compare.ts`, `compare.test.ts`, `gui/src/screens/ComparePage.tsx` | 7 | a baseline asked for again is asked (ruling 18) |
| `gui/src/ui/ComboBox.tsx`, `gui/src/styles/ui.css` | 8 | a note drawn after its combobox is its description (ruling 18) |
| `2026-10-21-gui-journeys-remaining-preflight.md` | 3 to 8 | the earlier pre-flight's drafts of every row, kept as evidence (ruling 18) |
| `docs/developer_documentation.rst` | 1, 3 | `held` and `restamp` (1); `openedGui` (3) |
| this plan's *The inventory* | 1, then every task | each row's journey, or its reason |

A screen's fix, where a journey finds a bug, is in that screen's own files, with its decision in `gui/src/lib` under Vitest.

## Interfaces Between Tasks

- **Task 1 produces,** in `gui/e2e/demo.ts`:
  - `type Matcher = string | RegExp | ((url: URL) => boolean)`: a pathname, a pattern over the pathname, or a test of the whole address.
  - `held(page: Page, matcher: Matcher, options?: { every?: boolean; onAnswer?: (response: APIResponse) => void | Promise<void> }): Promise<() => void>`. It holds the page's next request `matcher` matches (every one, with `every`) until the function it answers is called, then lets it through; with `onAnswer`, the server's answer is fetched and handed to it before the page gets it.
  - `restamp(directory: string, file: string): void`. It moves the file's modification time to now and changes none of its bytes: the watcher's next poll reads a new revision, and the server's pending long poll answers at once (P19b-9).
- **Task 2 produces:**
  - `interface Kept<T> { readonly identity: string; readonly data: T }`, `kept<T>(data: T | undefined, placeholder: boolean, identity: string, before: Kept<T> | null): Kept<T> | null`, `refusedRead(error: unknown): boolean` and `shown<T>(data: T | undefined, identity: string, before: Kept<T> | null, error: unknown): T | undefined`, in `gui/src/lib/kept.ts`;
  - `useKept<T>(query: UseQueryResult<T>, identity: string): T | undefined`, in `gui/src/app/useKept.ts`;
  - `page_policy(page: bytes) -> str` and `GuiServer.policy: str`, in `src/ddd/gui/server.py`;
  - `PAGE_NOT_LOADED`, the boot script's sentence, `"ddd gui could not load this page. Reload it to try again."`, asserted by `network.spec.ts`.

  From Task 2 on, Files, Units, Types, Shared files, the canvas, a component's page and the values grid keep their last answer when a new revision's read fails, with the error banner above it; a refusal (a 4xx) is still shown alone.
- **Task 3 produces,** in `gui/e2e/fixtures.ts`: `start(directory, project, options?: { browser?: string })`, and the fixture `openedGui: OpenedGui`, with `type OpenedGui = Gui & { opened: () => Promise<string> }`. `opened` answers the one-time sign-in address (`/open?code=…`) `ddd gui` handed the browser it opened.
- **Task 4 produces:** the shape `"chain"` in `tools/generate_project.py`'s `SHAPES`; in `gui/e2e/fixtures.ts`, `generated(directory: string, options: readonly string[] = MANY)`, where `MANY` is today's arguments (`--declarations 20000 --shape many --missing-ids 1 --unread 0.5`), and the fixture `chainedGui: Gui`.
- **Tasks 3 to 8 consume the helpers their rows need,** and each adds rows' journeys to its own files.

---

### Task 1: the rows checked, `held` and `restamp`

**Model:** opus, reviewed on opus. The rows need judgement across every screen, and the helpers replace code fifteen journeys stand on.

**Files:**
- Modify: `gui/e2e/demo.ts`, `gui/e2e/helpers.spec.ts`, `docs/developer_documentation.rst`, this plan's *The inventory*
- Modify (the copies): `gui/e2e/start.spec.ts`, `canvas.spec.ts`, `compare.spec.ts`, `files.spec.ts`, `project-units.spec.ts`, `shared.spec.ts`, `declarations.spec.ts`, `keys.spec.ts`, `types.spec.ts`, `values.spec.ts`

**Interfaces:**
- Consumes: 19b's inventory, as this plan's *The inventory* carries it.
- Produces: `Matcher`, `held` and `restamp` (see *Interfaces Between Tasks*).

- [ ] **Step 1: The baseline run.** The controller starts a full run at this plan's commit (`gh workflow run ci.yml --ref feature/gui-journeys-remaining -f repeat=1`) and records, in *Figures*, each gui leg's journeys, failures and time. It is the first run on Ubuntu 26: a failure here is the runner's, and is worked at its cause before any journey is added.
- [ ] **Step 2: The rows.** For each row of *The inventory*, find the code that draws it at this commit and confirm that no journey drives it.
  - A row a journey now drives names it (`file:line` and title), and keeps its task as owner, with no work.
  - A row whose state no longer exists in the code is marked so, with what was read.
  - Nothing is added beyond the five rows the spec adds (§5, §6) and the nine the earlier pre-flight found (ruling 18), all already in the table.
- [ ] **Step 3: `held`'s and `restamp`'s journeys, red first,** appended to `gui/e2e/helpers.spec.ts`, whose `UNASKED` and `askedFromPage` they reuse. Add `held`, `restamp`, `CONTROLLER` to its import from `./demo`, and `statSync`, `utimesSync` to its `node:fs` import:

```ts
test("a request held until released is answered then, and the next goes straight through", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const release = await held(page, UNASKED);
  let answered = false;
  const first = askedFromPage(page, UNASKED).then((asked) => {
    answered = true;
    return asked;
  });
  // The second ask is past the hold, and the server answers it - refused 401, since `fetch` in
  // askedFromPage sends no token - while the first still waits for its release.
  expect(await askedFromPage(page, UNASKED)).toMatchObject({ status: 401 });
  expect(answered).toBe(false);
  release();
  expect(await first).toMatchObject({ status: 401 });
});

test("every request held, with every, until released", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const release = await held(page, /^\/api\/checks$/, { every: true });
  let answers = 0;
  const asks = [askedFromPage(page, UNASKED), askedFromPage(page, UNASKED)].map((ask) =>
    ask.then((asked) => {
      answers += 1;
      return asked;
    }),
  );
  // A third ask of another path is answered while both are held: the page and the server work.
  expect(await askedFromPage(page, "/api/dictionary")).toMatchObject({ status: 401 });
  expect(answers).toBe(0);
  release();
  for (const asked of await Promise.all(asks)) expect(asked).toMatchObject({ status: 401 });
});

test("a held request's answer is read before the page is handed it", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  let read: number | null = null;
  const release = await held(page, (url) => url.pathname === UNASKED, {
    onAnswer: (response) => {
      read = response.status();
    },
  });
  const asked = askedFromPage(page, UNASKED);
  expect(read).toBeNull();
  release();
  expect(await asked).toMatchObject({ status: 401 });
  expect(read).toBe(401);
});

test("a file restamped has a later modification time and the same bytes", async ({ gui }) => {
  const path = join(gui.directory, CONTROLLER);
  const bytes = readFileSync(path);
  // An old stamp first, so that the move is measurable on any file system's resolution.
  const old = new Date(2000, 0, 1);
  utimesSync(path, old, old);
  restamp(gui.directory, CONTROLLER);
  expect(statSync(path).mtimeMs).toBeGreaterThan(old.getTime() + 1000);
  expect(readFileSync(path).equals(bytes)).toBe(true);
});
```

- [ ] **Step 4: Run them to see them fail.** `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test helpers.spec.ts --output=<scratch>/t1-red`. Expected: it fails to compile; `held` and `restamp` do not exist yet.
- [ ] **Step 5: `held` and `restamp`,** at the end of `gui/e2e/demo.ts`. Add `type APIResponse` to its `@playwright/test` import and `utimesSync` to its `node:fs` import:

```ts
/** What `held` matches: a pathname, a pattern over the pathname, or a test of the whole address
 * (a query parameter included). */
export type Matcher = string | RegExp | ((url: URL) => boolean);

function matching(matcher: Matcher): (url: URL) => boolean {
  if (typeof matcher === "string") return (url) => url.pathname === matcher;
  if (matcher instanceof RegExp) return (url) => matcher.test(url.pathname);
  return matcher;
}

/**
 * Holds the page's next request that `matcher` matches until the function it answers is called,
 * then lets it through to the server; any later one goes straight through (`{ times: 1 }`: a
 * route left registered met the teardown on Windows as `ECONNRESET`, P19b-7). With `every`,
 * each one is held until the release, for a journey whose claim is about every answer, not the
 * next one. With `onAnswer`, the server's answer is fetched and handed to it before the page
 * gets it: what a journey reads of an answer the page has not drawn yet. For a state the page
 * shows while it waits (spec 2026-10-08 §5, "Loading states"): release in a `finally`, so that a
 * failed assertion never leaves the page waiting.
 */
export async function held(
  page: Page,
  matcher: Matcher,
  options: {
    every?: boolean;
    onAnswer?: (response: APIResponse) => void | Promise<void>;
  } = {},
): Promise<() => void> {
  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  const { every = false, onAnswer } = options;
  await page.route(
    matching(matcher),
    async (route) => {
      await released;
      if (onAnswer === undefined) {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      await onAnswer(response);
      await route.fulfill({ response });
    },
    every ? {} : { times: 1 },
  );
  return release;
}

/**
 * Moves `file`'s modification time to now and changes none of its bytes. The watcher compares a
 * file's `(st_mtime_ns, st_size)` alone (`stamped` and `poll`, session.py), so its next poll
 * reads a new revision, and the server's long poll, which would otherwise wait out its
 * `WAIT_SECONDS`, answers at once (P19b-9). For a journey that needs the next revision now: a
 * held refusal let go, or the page's next state read failed.
 */
export function restamp(directory: string, file: string): void {
  const now = new Date();
  utimesSync(join(directory, file), now, now);
}
```

- [ ] **Step 6: Run the helpers' journeys to see them pass,** after a build: `npx playwright test helpers.spec.ts --repeat-each=10`. Expected: every one passes, 10 times.
- [ ] **Step 7: Ablations,** in place in `demo.ts`, restored by exact edit, each killing a named journey:
  - `every ? {} : { times: 1 }` made `{}`: "a request held until released…" dies at `expect(answered).toBe(false)`;
  - `every ? {} : { times: 1 }` made `{ times: 1 }`: "every request held, with every…" dies at `expect(answers).toBe(0)`;
  - `await onAnswer(response);` removed: "a held request's answer is read…" dies at `expect(read).toBe(401)`;
  - `utimesSync(…)` removed from `restamp`: "a file restamped…" dies at `toBeGreaterThan`.
- [ ] **Step 8: The eight held-request copies.** Replace each `let release … / const released … / page.route(…) / await released / route.continue()` recipe with `held`, keeping its `try … finally { release(); }`:
  - `start.spec.ts`'s "the start page says it is looking for projects…": `held(page, "/api/projects")`. It had no `{ times: 1 }`; the compiled page asks for the list once, so the next one alone is held.
  - `canvas.spec.ts`'s "…drawing the project…": `held(page, "/api/graph")`; "…laying the project out…": `held(page, /^\/assets\/layoutWorker-[^/]+\.js$/)`.
  - `compare.spec.ts`'s busy-state journey: `held(page, "/api/compare")`.
  - `project-units.spec.ts`'s adopt journey: `held(page, "/api/units")`.
  - `shared.spec.ts`'s raster journey: `held(page, (url) => url.pathname === "/api/raster" && url.searchParams.get("name") === "100ms")`.
  - `files.spec.ts`'s "the row a New file makes shows before the tab's next list of entries answers": `held(page, "/api/files", { every: true })`. It had no `{ times: 1 }` on purpose: its claim is about any list the tab asks for before the row shows, and the edit's analysis may ask for more than one.
  - `files.spec.ts`'s "the row a Remove takes out goes before…": `held(page, "/api/files", { onAnswer })`, whose `onAnswer` reads `entries` into `listed` as the copy does today.

  Run each changed file with `--repeat-each=10`. Each journey passes as before; each claim is unchanged. Leave the four routes that write a file on the edit's way through (`files.spec.ts`, `findings.spec.ts`, `project-units.spec.ts`, `skeleton.spec.ts`): they are not the held recipe, and new journeys write before the press instead.
- [ ] **Step 9: The seven stamp bumps.** Replace each `const now = new Date(); utimesSync(path, now, now);` (or its one-line form) with `restamp(<directory>, <file>)`, the two pieces the path was joined from: `declarations.spec.ts` (two), `files.spec.ts`, `keys.spec.ts`, `start.spec.ts`, `types.spec.ts`, `values.spec.ts`. Remove `utimesSync` from an import that no longer uses it. Run each changed file with `--repeat-each=5`.
- [ ] **Step 10: The developer documentation.** In `docs/developer_documentation.rst`'s paragraph on the journeys, beside `failing` and `copiedGui`, say in its own style what `held` holds and lets through, what `every` and `onAnswer` change, and what `restamp` moves and why a journey needs it.
- [ ] **Step 11: The gates:**
  - lint, typecheck, Vitest, build;
  - every journey: the count before this task, plus its four;
  - `tests/test_gui_docs.py` and `tests/test_documentation.py` with `--no-cov -p no:cacheprovider`;
  - the docs under `-W` in Docker, after the journeys and never alongside them.
- [ ] **Step 12: Commit.** One commit for the inventory, one for the helpers and their journeys, one for the copies replaced.

### Task 2: a screen keeps its last answer, and the page asks for its script once more

**Model:** opus, reviewed on opus. It changes what seven screens show, the page's start, and the server's content security policy.

**Files:**
- Create: `gui/src/lib/kept.ts`, `gui/src/lib/kept.test.ts`, `gui/src/app/useKept.ts`, `gui/e2e/kept.spec.ts`
- Modify: `gui/src/screens/FilesPage.tsx`, `UnitsPage.tsx`, `TypesPage.tsx`, `SharedPage.tsx`, `GraphPage.tsx`, `ComponentPage.tsx`, `ValuesPage.tsx`, `gui/index.html`, `gui/e2e/network.spec.ts`, `src/ddd/gui/server.py`, `tests/test_gui_server.py`, `docs/gui_security.rst`, `CHANGELOG.md`, this plan's *The inventory*

**Interfaces:**
- Consumes: `failing`, `SERVER_FAILED` (19b); `restamp` (Task 1); `openPanel`, `chooseUnit`, `openValues`, `CONTROLLER` (`gui/e2e/demo.ts`).
- Produces: `Kept`, `kept`, `refusedRead`, `shown`, `useKept`, `page_policy`, `GuiServer.policy`, `PAGE_NOT_LOADED` (see *Interfaces Between Tasks*).

**Part A: the kept answer.**

- [ ] **Step 1: The journeys, red first.** Create `gui/e2e/kept.spec.ts`. The worked journey:

```ts
import { CONTROLLER, failing, restamp, SERVER_FAILED } from "./demo";
import { expect, test } from "./fixtures";

test("the units failing on a new revision keep the table, with the error above it", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  const ms = page.getByRole("row", { name: "ms", exact: true });
  await expect(ms).toBeVisible();
  // Every read of the units fails from here; the restamp makes a new revision at once (P19b-9),
  // whose units the tab asks for under a new key - the read P19b-20 found dropped the table.
  const failed = await failing(page, "/api/units", "http");
  restamp(gui.directory, CONTROLLER);
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(ms).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});
```

  Then the other six, in the same file, each the same shape. Read each screen's own row names and fixture off the code and off its existing journeys:
  - **"the types failing on a new revision keep the table, with the error above it":** `structuresGui`; the Types tab; `failing(page, "/api/types", "http")`; `restamp` of a file of that project; the alert, and a type's row still drawn.
  - **"the shared files failing on a new revision keep the table, with the error above it":** `vocabularyGui`; the Shared files tab (`exact: true`); `failing(page, "/api/shared", "http")`; the alert, and the `100ms` row still drawn.
  - **"the graph failing on a new revision keeps the canvas, with the error above it":** `gui`; the canvas; `failing(page, "/api/graph", "http")`; the alert, and the module button "Controller" still drawn.
  - **"the files failing on a new revision keep the table, with the error above it":** `vocabularyGui`; the Files tab (`exact: true`); `failing(page, "/api/files", "http")`; the alert, and the units file's row still drawn.
  - **"a component's file failing on a new revision keeps the page and its open panel, with the error above it":** `gui`; Controller's page; `openPanel(page, gui.address, "ValueA")` and `chooseUnit(page, "rpm")`, so that the panel holds a choice not applied; then `failing(page, "/api/file", "http")` and `restamp(gui.directory, CONTROLLER)`. The alert reads `SERVER_FAILED`; the grid "Declarations of Controller" is still drawn; the `complementary` "ValueA" is still open, its combobox "Unit of ValueA" still reading "rpm". Today the alert replaces the page, and the panel's choice is lost with it.
  - **"the values failing on a new revision keep the grid, with the error above it":** `gui`; `openValues(page, gui.address, "CurveA")`; then `failing(page, "/api/values", "http")` and `restamp(gui.directory, CONTROLLER)`. The alert reads `SERVER_FAILED`, under the heading "CurveA"; the grid "Values of CurveA" is still drawn.
- [ ] **Step 2: Run them to see the red,** after a build. Each fails at its last row, module, grid or panel assertion: the screen draws the alert alone (P19b-20). Record each failure's line in the report.
- [ ] **Step 3: The rule, red first.** Create `gui/src/lib/kept.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import { type Kept, kept, refusedRead, shown } from "./kept";

const units: Kept<string[]> = { identity: "units", data: ["ms"] };
const failed = new ApiError(500, "internal", "ddd gui failed on this request");
const refused = new ApiError(404, "not-found", "the project declares no 'CurveA'");

describe("refusedRead", () => {
  test("a refusal is the server's answer about what was asked", () => {
    expect(refusedRead(refused)).toBe(true);
    expect(refusedRead(new ApiError(409, "invalid", "x"))).toBe(true);
  });

  test("a read the server failed on, or that got no answer, is no refusal", () => {
    expect(refusedRead(failed)).toBe(false);
    expect(refusedRead(new ServerUnreachable(new TypeError("fetch failed")))).toBe(false);
    expect(refusedRead(null)).toBe(false);
  });
});

describe("kept", () => {
  test("keeps nothing new while the query holds no answer", () => {
    expect(kept(undefined, false, "units", null)).toBeNull();
    expect(kept(undefined, false, "units", units)).toBe(units);
  });

  test("keeps nothing new from a placeholder carried from the revision before", () => {
    expect(kept(["Hz"], true, "units", units)).toBe(units);
  });

  test("keeps the query's own answer, under its question", () => {
    expect(kept(["Hz"], false, "units", null)).toEqual({ identity: "units", data: ["Hz"] });
    expect(kept(["Hz"], false, "types", units)).toEqual({ identity: "types", data: ["Hz"] });
  });

  test("answers the very object it kept while nothing changed", () => {
    expect(kept(units.data, false, "units", units)).toBe(units);
  });
});

describe("shown", () => {
  test("shows the query's answer whenever it has one", () => {
    expect(shown(["Hz"], "units", units, null)).toEqual(["Hz"]);
    expect(shown(["Hz"], "types", units, refused)).toEqual(["Hz"]);
  });

  test("shows the answer kept for the same question once a read failed", () => {
    expect(shown(undefined, "units", units, failed)).toEqual(["ms"]);
    expect(shown(undefined, "units", units, null)).toEqual(["ms"]);
  });

  test("never shows a kept answer over a refusal: the refusal is about what was asked", () => {
    expect(shown(undefined, "units", units, refused)).toBeUndefined();
  });

  test("never shows another question's answer", () => {
    expect(shown(undefined, "types", units, failed)).toBeUndefined();
  });

  test("shows nothing where nothing was ever answered", () => {
    expect(shown(undefined, "units", null, failed)).toBeUndefined();
  });
});
```

  Run `npx vitest run src/lib/kept.test.ts`. Expected: it fails; `./kept` does not exist.
- [ ] **Step 4: `gui/src/lib/kept.ts`:**

```ts
import { ApiError } from "../api/client";

/** A tab's last good answer, and the question it answered: the tab, and anything else its query
 * names but the revision (spec 2026-10-21 §5). */
export interface Kept<T> {
  readonly identity: string;
  readonly data: T;
}

/**
 * What a tab keeps after this render: its query's answer when the answer is its own, not a
 * placeholder carried from the revision before; otherwise what it kept already. The very object
 * it was given while nothing changed, so that `useKept`, which stores it while rendering, stops
 * there.
 */
export function kept<T>(
  data: T | undefined,
  placeholder: boolean,
  identity: string,
  before: Kept<T> | null,
): Kept<T> | null {
  if (data === undefined || placeholder) return before;
  if (before !== null && before.identity === identity && before.data === data) return before;
  return { identity, data };
}

/** Whether a read's error is the server's answer about what was asked - a refusal, such as an
 * object no longer declared, or a shape no grid can draw - rather than a read that failed: no
 * answer at all (`ServerUnreachable`), or the server failing on it (a 5xx). */
export function refusedRead(error: unknown): boolean {
  return error instanceof ApiError && error.status < 500;
}

/**
 * What a screen shows: its query's answer while it holds one - its own, or the revision before's,
 * carried while the next is read - and, once the next read failed and the query holds nothing,
 * the last good answer kept for the same question (P19b-20: React Query serves a placeholder to
 * a pending read alone, so a failed read of a new revision left the screen with nothing to draw
 * but its error). Never over a refusal (`refusedRead`): it says something about what was asked,
 * and an answer kept from before it would show an object the project no longer has. A screen
 * that never had an answer shows nothing, and its error alone, as before. Never another
 * question's answer: the canvas's names its project, a component's its file.
 */
export function shown<T>(
  data: T | undefined,
  identity: string,
  before: Kept<T> | null,
  error: unknown,
): T | undefined {
  if (data !== undefined) return data;
  if (refusedRead(error)) return undefined;
  return before !== null && before.identity === identity ? before.data : undefined;
}
```

  Run `npm test`. Expected: every case passes, at 100 % on all four metrics.
- [ ] **Step 5: `gui/src/app/useKept.ts`:**

```ts
import type { UseQueryResult } from "@tanstack/react-query";
import { useState } from "react";
import { type Kept, kept, shown } from "../lib/kept";

/** A screen's answer as it should draw it (`shown`, lib/kept.ts): its query's own, or, once the
 * read of a new revision failed, the last good one for the same question. The kept answer is
 * state adjusted while rendering - React's own pattern for state that follows what a render is
 * given - so the render in which the read fails already draws it, with no frame of the error
 * alone. */
export function useKept<T>(query: UseQueryResult<T>, identity: string): T | undefined {
  const [before, setBefore] = useState<Kept<T> | null>(null);
  const after = kept(query.data, query.isPlaceholderData, identity, before);
  if (after !== before) setBefore(after);
  return shown(query.data, identity, after, query.error);
}
```

- [ ] **Step 6: The five tabs.** In each, read the answer through `useKept` right below its `useQuery`, and use it wherever the tab read `<query>.data`:
  - `UnitsPage.tsx`: `const answer = useKept(units, "units");`
  - `TypesPage.tsx`: `useKept(types, "types")`
  - `SharedPage.tsx`: `useKept(shared, "shared")`
  - `FilesPage.tsx`: `useKept(files, "files")`
  - `GraphPage.tsx`: `useKept(graph, JSON.stringify(["graph", project]))`, the query's key less its revision.

  Each tab's early return becomes `if (answer === undefined) { if (<query>.isError) return <Banner …>; return <loading line>; }`, and its banner above the table, `{<query>.isError && <Banner …>}`, stays: with the answer kept, it is now the case its comment names. Change nothing else in the tab.
- [ ] **Step 6b: The component page and the values grid** (the maintainer's answer of 2026-10-21, planning ruling 17). Their reads drop everything on a failure today, an open panel's choice not applied included, against their own comments ("The table stays up while this file is read again…", `ComponentPage.tsx`; "the table stays up while the next revision's answer is read", `ValuesPage.tsx`).
  - `ComponentPage.tsx`: `const answer = useKept(content, JSON.stringify(["file", file]));`. `loaded` and `data` read `answer` (`answer !== undefined && answer.error === null`). The early returns become: `if (answer === undefined) { if (content.isError) return <Banner …>; return <p className="quiet">Reading the file…</p>; }`, then `answer.error`'s banner as today; and above the table, under the heading, `{content.isError && <Banner tone="error">{content.error.message}</Banner>}`, new, as the tabs draw theirs. The findings list's own query (`listed`) is left as it is: its failure shows its own banner under the table, and drops nothing else.
  - `ValuesPage.tsx`: `const answer = useKept(values, JSON.stringify(["values", name]));`, read where `values.data` is (`shown`'s `valuesShown(…, answer)`, and `reply`). The two early returns become `if (answer === undefined) { if (values.isError) return <the refusal's section, as today>; return <p className="quiet">Reading the values…</p>; }`; and, with an answer, `{values.isError && <Banner tone="error">{values.error.message}</Banner>}` under the heading. `appliesOver` already keeps an Apply from being planned over an older revision's answer, so a kept grid offers none (read it, and say so in the report).
  - A refusal is never kept (`refusedRead`): the values page's "the project declares no 'CurveA'" after a rename still shows the refusal's section alone, its grid gone. Task 8's row "an object no longer declared…" pins it end to end; `values.spec.ts`'s "a shape deeper than a grid is shown, not offered, and says so with a way back", a refusal at the first read, must keep passing.
- [ ] **Step 7: Run the journeys to see them pass:** `kept.spec.ts` with `--repeat-each=10`, after a build. Then every journey.
- [ ] **Step 8: Ablations,** each in a scratch copy of the package, each killing a named journey:
  - `shown` answering `data` alone: the seven journeys die at their row, module, grid or panel assertion;
  - `shown`'s `refusedRead` check removed: Vitest's "never shows a kept answer over a refusal" dies. End to end, Task 8's row "an object no longer declared, its page saying so, with the way back" dies too, its old grid kept under the refusal; until Task 8, Vitest is this rule's only pin;
  - `kept` ignoring `placeholder` (keeping a placeholder as its own): Vitest's "keeps nothing new from a placeholder…" dies;
  - `shown`'s identity check removed: Vitest's "never shows another question's answer" dies.

**Part B: the page asks for its own script once more.**

- [ ] **Step 9: The journeys, red first,** appended to `gui/e2e/network.spec.ts`:

```ts
/** The page's own module, as Vite names it in /assets/; a query string does not change the path. */
const SCRIPT = /^\/assets\/index-[^/]+\.js$/;

/** What the boot script in index.html writes once the page's module failed twice. */
const PAGE_NOT_LOADED = "ddd gui could not load this page. Reload it to try again.";

test("the page's script the network failed once is asked for again, and the page is drawn", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, SCRIPT, "network", 1);
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  expect(failed()).toBe(1);
  await expect(page.getByText(PAGE_NOT_LOADED, { exact: true })).toHaveCount(0);
});

test("the page's script the network fails every time says how to try again", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, SCRIPT, "network");
  await page.goto(gui.address);
  await expect(page.getByText(PAGE_NOT_LOADED, { exact: true })).toBeVisible();
  expect(failed()).toBe(2);
});
```

  Also, beside 19b's "a stylesheet the network fails every time leaves the page drawn and working", assert `page.getByText(PAGE_NOT_LOADED, { exact: true })` has count 0 (Review Focus 5).
- [ ] **Step 10: Run them to see the red.** The first fails at "Controller" (the page stays blank); the second at the sentence. Record each line.
- [ ] **Step 11: The server's policy, red first,** in `tests/test_gui_server.py`. Import `page_policy` beside `SECURITY_HEADERS`, and `base64`, `hashlib` at the top:

```python
def _hashed(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


class TestThePagePolicy:
    BASE = SECURITY_HEADERS["Content-Security-Policy"]

    def test_a_page_with_no_inline_script_keeps_the_base_policy(self) -> None:
        page = b'<!doctype html><script type="module" src="/assets/index-a.js"></script>'
        assert page_policy(page) == self.BASE

    def test_each_inline_script_is_allowed_by_its_hash(self) -> None:
        page = b"<html><head><script>one()</script></head><body><script> two(); </script></body>"
        assert page_policy(page) == (
            f"{self.BASE}; script-src 'self' {_hashed('one()')} {_hashed(' two(); ')}"
        )

    def test_a_page_written_with_crlf_is_hashed_as_the_browser_reads_it(self) -> None:
        # Review Focus 1: the windows runners check index.html out with CRLF, and the browser's
        # parser turns every CRLF and lone CR into LF before it hashes a script.
        page = b"<script>\r\n  a();\r  b();\n</script>"
        expected = _hashed("\n  a();\n  b();\n")
        assert page_policy(page) == f"{self.BASE}; script-src 'self' {expected}"

    def test_an_empty_inline_script_is_hashed_too(self) -> None:
        assert page_policy(b"<script></script>") == f"{self.BASE}; script-src 'self' {_hashed('')}"
```

  And, in `TestWhatIsServed`, a case serving a static directory whose `index.html` holds an inline script, in the style of the class's own parametrised stand-ins: `GET /`, `GET /api/session` and a page asset each carry `page_policy` of that page as their `Content-Security-Policy`. `test_every_response_carries_the_security_headers` keeps passing as it stands. Run `.venv/bin/python -m pytest tests/test_gui_server.py --no-cov`: the new cases fail; `page_policy` does not exist.
- [ ] **Step 12: `page_policy`,** in `src/ddd/gui/server.py`, below `SECURITY_HEADERS`. Import `base64`, `hashlib` and `from html.parser import HTMLParser`:

```python
class _InlineScripts(HTMLParser):
    """The text of each script a page holds inline: one with no ``src``, whose text is what
    runs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: list[str] = []
        self._text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and all(name != "src" for name, _ in attrs):
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._text is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._text is not None:
            self.scripts.append("".join(self._text))
            self._text = None


def page_policy(page: bytes) -> str:
    """The content security policy of every answer of a server serving ``page``: the base one in
    :data:`SECURITY_HEADERS`, and, where the page holds a script inline, ``script-src`` allowing
    the server's own scripts and each inline one by its SHA-256 - never ``'unsafe-inline'``
    (spec 2026-10-21 §6). The page's boot script is the one today: it asks for the page's own
    module once more when the network failed it, which no code of that module can do.

    Hashed as a browser reads the script: its parser turns every CRLF, and every lone CR, into LF
    before a script runs, and a checkout on Windows writes index.html with CRLF.
    """
    reader = _InlineScripts()
    text = page.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    reader.feed(text)
    reader.close()
    base = SECURITY_HEADERS["Content-Security-Policy"]
    if not reader.scripts:
        return base
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
        for script in reader.scripts
    )
    return f"{base}; script-src 'self' {hashes}"
```

  Then `GuiServer.__init__`, after `self.static = static.resolve()`:

```python
        # Read once: the pages do not change under a running server, and every answer carries it.
        # `run` refuses to start without an index.html; a test's server may have none.
        page = self.static / "index.html"
        base = SECURITY_HEADERS["Content-Security-Policy"]
        self.policy = page_policy(page.read_bytes()) if page.is_file() else base
```

  Both branches need a test: the `server` fixture's pages (`tests/test_gui_server.py`, built for `GuiServer(api, static, …)`) hold a stand-in `index.html`; if no existing test builds a `GuiServer` over pages without one, add a case that does and reads `server.policy` as the base. Then `_Handler._send`, first line after `own = dict(headers or {})`: `own.setdefault("Content-Security-Policy", self._gui.policy)`. `_refuse`'s 503, written before any handler exists, keeps the base policy: it carries no script. Run the file's tests: they pass. Run the whole suite: 100 % line and branch.
- [ ] **Step 13: The boot script,** in `gui/index.html`'s `<head>`, after the pressable stylesheet's link:

```html
    <!-- Asks once more for the page's own module when the network failed it (P19b-22): the one
         load no code of the page can ask for again, since it is that code. Inline, so that
         nothing need load for it to run; allowed by its hash alone (page_policy, server.py). A
         failed module address is remembered by the browser, so the second ask adds a query,
         which the server ignores. -->
    <script>
      addEventListener(
        "error",
        function (event) {
          var script = event.target;
          if (!(script instanceof HTMLScriptElement) || script.type !== "module") return;
          if (script.hasAttribute("data-again")) {
            document.getElementById("root").textContent =
              "ddd gui could not load this page. Reload it to try again.";
            return;
          }
          var again = document.createElement("script");
          again.type = "module";
          again.crossOrigin = script.crossOrigin;
          again.src = script.src + (script.src.indexOf("?") < 0 ? "?" : "&") + "again";
          again.setAttribute("data-again", "");
          document.head.appendChild(again);
        },
        true,
      );
    </script>
```

  Biome does not read `index.html`; keep its indentation as the file's. Build, and confirm the built `src/ddd/gui/static/index.html` holds the script byte for byte as written, and that `GET /` of a server over it carries one `sha256-` in its policy.
- [ ] **Step 14: Run the journeys to see them pass:** `network.spec.ts` with `--repeat-each=20`, after a build: every one passes. Then every journey: `units.spec.ts`'s "no page reports a violation of its content security policy" must pass unchanged.
- [ ] **Step 15: Ablations,** each in a scratch copy of the package, each killing a named journey:
  - the boot script's `appendChild(again)` removed: "the page's script the network failed once…" dies at "Controller";
  - the `textContent` line removed: "…fails every time says how to try again" dies at the sentence;
  - `own.setdefault("Content-Security-Policy", …)` removed from `_send`, in a scratch worktree: both die, and so does `units.spec.ts`'s policy journey;
  - `page_policy`'s `.replace("\r\n", "\n")` removed, in a scratch worktree: the CRLF pytest case dies.
- [ ] **Step 16: The security page.** In `docs/gui_security.rst`, the bullet "The page's own origin" says the policy's `default-src 'self'` runs no script but one served from this origin. Make it say, in its own style, that it runs no script but one served from this origin and the one inline script the page starts with, allowed by its SHA-256, which asks for the page's module once more; never any other inline script. `SECURITY.md` says nothing of the policy at `2bc00da`, and is left as it is (planning ruling 3).
- [ ] **Step 17: The CHANGELOG.** Two entries under `## Unreleased`, in its own style (a bold lead, two spaces between sentences, no line over 95 columns):
  - a tab, a component's page or a values grid whose next read fails keeps what it showed, with the error above it, where it showed the error alone, and an open panel keeps what the reader chose in it;
  - a page whose own script the network drops once is drawn as if nothing had happened, and one dropped twice says to reload, where it stayed blank.
- [ ] **Step 18: The inventory.** The four "table kept" rows and the five this part adds name their journeys.
- [ ] **Step 19: The gates,** as in Task 1, the whole pytest suite, ruff, format and mypy, and the screenshots in Docker in compare mode (no reference may move). Commit: one commit for the kept answer and its journeys, one for the policy, one for the boot script and its journeys, one for the docs and the CHANGELOG.

### Task 3: the start page, the app around every page, and the undo strip

**Model:** sonnet, reviewed on sonnet. Each row is a state the page already draws; one needs this task's own fixture, and one shows a bug contained in one screen.

**Files:**
- Modify: `gui/e2e/fixtures.ts`, `gui/e2e/helpers.spec.ts`, `gui/e2e/start.spec.ts`, `gui/e2e/undo.spec.ts`, `docs/developer_documentation.rst`, this plan's *The inventory*
- Modify, for the bug in the row "a project opening, the list's buttons held until it has": `gui/src/screens/StartPage.tsx`, a `gui/src/lib` module and its test, `CHANGELOG.md`
- Modify, for the two bugs of Step 6b (ruling 18): `src/ddd/gui/session.py` and `tests/test_gui_session.py`; `gui/src/screens/ComponentPage.tsx`

**Interfaces:**
- Consumes: `held`, `restamp` (Task 1); `failing`, `SERVER_FAILED`, `copiedGui` (19b); `bareGui`, `gui`, `generatedGui`.
- Produces: `start`'s `browser` option, and `openedGui` (see *Interfaces Between Tasks*).

**The earlier pre-flight** (ruling 18) drafted a journey for each of this task's rows, ran it ten times, and killed it with a named change: `2026-10-21-gui-journeys-remaining-preflight.md`, §A.1 to §A.3. Before writing a row's journey, read its draft: its setup, the words it read off the page, and the change that killed it. Then write the journey with this plan's helpers.

- [ ] **Step 1: The fixture `openedGui`, red first.** Its journey, appended to `gui/e2e/helpers.spec.ts`:

```ts
test("the browser ddd gui opens is handed a one-time sign-in address of its own", async ({
  openedGui,
}) => {
  const printed = new URL(openedGui.address);
  const handed = new URL(await openedGui.opened());
  // `launched` (server.py) hands the opener this server's own address with a one-time code of
  // `TOKEN_BYTES`' 43 characters, never the token the printed address carries.
  expect(handed.origin).toBe(printed.origin);
  expect(handed.pathname).toBe("/open");
  expect(handed.searchParams.get("code")).toMatch(/^[A-Za-z0-9_-]{43}$/);
  expect(handed.searchParams.get("token")).toBeNull();
  expect(handed.searchParams.get("code")).not.toBe(printed.searchParams.get("token"));
});
```

  Run it after a build: it fails to compile, since `openedGui` does not exist.
- [ ] **Step 2: `start`'s `browser` option and the fixture,** in `gui/e2e/fixtures.ts`. `start` gains a third parameter, and passes `--no-browser` only without it:

```ts
/** What else `start` is told: `browser`, a program `ddd gui` opens its browser with, through the
 * `BROWSER` variable Python's `webbrowser` reads, in place of `--no-browser`. */
interface StartOptions {
  browser?: string;
}

async function start(
  directory: string,
  project: readonly string[],
  options: StartOptions = {},
): Promise<Gui> {
  // python -m ddd rather than the ddd launcher: on Windows the launcher starts python as a child
  // of its own, which killing the launcher leaves running, holding the port and the copy.
  const child = spawn(
    process.env.DDD_PYTHON ?? "python",
    ["-m", "ddd", "gui", ...project, ...(options.browser === undefined ? ["--no-browser"] : [])],
    {
      cwd: directory,
      stdio: ["ignore", "pipe", "inherit"],
      ...(options.browser === undefined
        ? {}
        : { env: { ...process.env, BROWSER: options.browser } }),
    },
  );
```

  (the rest of `start` unchanged), and, beside `copiedExample`:

```ts
/** A stand-in for the browser `ddd gui` opens: a program that writes the address it is opened
 * with to a file beside it, and a function answering that address once it is there. A shell
 * script, or on Windows a batch file. `webbrowser` runs a `BROWSER` entry with no `%s` as one
 * program, handed the address as its one argument (`GenericBrowser`), so the program's path may
 * hold no whitespace; and a batch file reads it as `%*`, since cmd splits `%1` at the `=` of
 * `?code=`. */
function recorder(directory: string): { program: string; opened: () => Promise<string> } {
  mkdirSync(directory, { recursive: true });
  const file = join(directory, "opened.txt");
  const program = join(directory, process.platform === "win32" ? "record.cmd" : "record.sh");
  if (/\s/.test(program)) {
    throw new Error(`webbrowser cannot run ${program}: it splits BROWSER at whitespace`);
  }
  if (process.platform === "win32") {
    writeFileSync(program, '@echo off\r\n>"%~dp0opened.txt" echo %*\r\n');
  } else {
    writeFileSync(program, '#!/bin/sh\nprintf \'%s\' "$1" > "$(dirname "$0")/opened.txt"\n', {
      mode: 0o755,
    });
  }
  const opened = async () => {
    // `launched` runs on a thread of its own once the address is printed (server.py's `run`).
    await expect
      .poll(() => existsSync(file) && readFileSync(file, "utf8").trim() !== "", {
        timeout: 10_000,
      })
      .toBe(true);
    return readFileSync(file, "utf8").trim();
  };
  return { program, opened };
}

/** `ddd gui` with the browser it opens itself, for the sign-in no other journey sees: every
 * other server is started with `--no-browser`. */
export type OpenedGui = Gui & { opened: () => Promise<string> };
```

  and, in `test.extend`'s fixtures (with `openedGui: OpenedGui;` in its type parameter, and `expect` imported from `@playwright/test` for `opened`):

```ts
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  openedGui: async ({}, use, testInfo) => {
    const directory = testInfo.outputPath(DEMO.directory);
    cpSync(join(EXAMPLES, DEMO.directory), directory, { recursive: true });
    const browser = recorder(testInfo.outputPath("browser"));
    const gui = await start(directory, [join(directory, DEMO.project)], {
      browser: browser.program,
    });
    try {
      await use({ ...gui, opened: browser.opened });
    } finally {
      await gui.stop();
    }
  },
```

  Run Step 1's journey with `--repeat-each=5`: it passes. Ablate `start`'s spread of `--no-browser` to always pass it: the journey dies at `opened()`. The Windows legs are its proof, at this task's full run; if Windows' `webbrowser` will not run the batch file, the row "signed in by the one-time code…" names what was tried, and the fixture's Windows branch is left out with it.
- [ ] **Step 3: The worked journey,** the row "the server answering again after it stopped", in `gui/e2e/start.spec.ts` (its imports merged with the file's own):

```ts
import { CONTROLLER, drift, failing, restamp } from "./demo";
import { expect, test } from "./fixtures";

/** What the page says while its long poll goes unanswered: `App.tsx`'s `stopped` banner. */
const STOPPED = "ddd gui has stopped. Start it again and open the address it prints.";

test("a server that answers again after it stopped lifts the banner, and the page follows the project again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const canvas = page.getByRole("region", { name: "Modules" });
  const controller = canvas.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();

  // Every ask of the long poll dropped on the network, as a stopped server drops it. Each is
  // sent twice (`sentAgain`, client.ts), and the page says it has stopped only once a second ask
  // has gone unanswered too (`followStates`, state/revisions.ts).
  const failed = await failing(page, "/api/state", "network");
  // The ask already in flight was sent before the route existed, and would wait out the server's
  // own long poll (`WAIT_SECONDS`, 25 s, api.py) before it ended. A stamp moved, no byte changed,
  // wakes it at once (ruling P19b-9): the page's next ask is the first one dropped.
  restamp(gui.directory, CONTROLLER);
  const stopped = page.getByRole("alert").filter({ hasText: "has stopped" });
  await expect(stopped).toHaveText(STOPPED);
  // Two asks, each sent twice, before the banner: no fewer.
  expect(failed()).toBeGreaterThanOrEqual(4);
  // What is drawn is still the last revision read (spec 5.6): the canvas stays under the banner.
  await expect(controller).toBeVisible();

  // The server answering again. While stopped, the page asks every 2 s (`retryMs`), and the
  // first answer lifts the banner. That answer comes at once: the stamp's own analysis has
  // published a version newer than the one the page holds, so no long poll waits it out.
  await page.unrouteAll({ behavior: "wait" });
  await expect(stopped).toHaveCount(0);
  // And the page follows the project again: a change saved from outside reaches the canvas.
  drift(gui.directory);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
});
```

- [ ] **Step 4: Run it** after a build, with `--repeat-each=10`, then its ablation in a scratch copy of the package: it must die at `expect(stopped).toHaveCount(0)`.
- [ ] **Step 5: The other rows,** each a journey of its own: the start page's and the app's in `start.spec.ts`, the undo strip's in `undo.spec.ts`. Each is run with `--repeat-each=10` and ablated as its row says. The rows, as read at `2bc00da`:

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **1. The start page: a project listed with the images its build records name** | `copiedGui("demo", builtTwice, { named: false })`. `builtTwice` writes two build records: `build/firmware/ddd-build.json` and `build/tests/ddd-build.json`. Each is `{ "format": 1, "project": join(directory, "demo.ddd.json"), "image": "firmware" }` (or `"tests"`). These are the fields of `BuildInfo` (`src/ddd/build_info.py`), which forbids any other key. `format` is `BUILD_INFO_FORMAT`, which reads `1`. | Heading "Open a project". `getByRole("button", { name: /^DemoDevice/ })` has `toHaveCount(1)`: the project the records name and the description the walk finds are one entry (`find_projects`'s `set(images) \| set(_descriptions(base))`, `session.py`). That button holds `getByText("built as firmware, tests", { exact: true })` (`StartPage.tsx`, the `.quiet` span `built as {project.images.join(", ")}`). The records are read in sorted path order (`build_files`, `lsp/discovery.py`), so firmware comes before tests. The button `{ name: /^Logging/ }` (`subsystems/logging/logging.ddd.json`, which no record names) holds no `getByText(/^built as/)`. | `StartPage.tsx`'s `{project.images.length > 0 && (…)}` made `false`: dies at "built as firmware, tests". |
| **2. The start page: a project whose description does not load, listed as an unnamed project** | `copiedGui("demo", unreadable, { named: false })`. `unreadable` writes `build/ddd-build.json` naming the copy's `demo.ddd.json` (`format` 1, `image` "firmware"), then cuts `demo.ddd.json` in half. The record is needed: the walk keeps only a description that parses (`_descriptions` and `_is_project`, `session.py`). For the record's project, `_read_json` answers `None`, so `_name_in` gives no name. | Heading "Open a project". A button `{ name: /^Unnamed project/ }` (`StartPage.tsx`: `project.name ?? "Unnamed project"`). Its `.path` span reads the copy's forward-slashed path ending in `/demo.ddd.json`, as start.spec.ts's `root` swap spells it. It also holds "built as firmware". There is no button `/^DemoDevice/`, and `/^Logging/` is still listed. | `StartPage.tsx`'s fallback made `project.name ?? ""`: the button's name then starts with the path, and the journey dies at `/^Unnamed project/`. |
| **3. The start page: a project opening, the list's buttons held until it has** | `bareGui`. Once `/^DemoDevice/` shows, `const release = await held(page, "/api/open")`, released in a `finally`. | Press `/^DemoDevice/`. While the open is held, `/^DemoDevice/` and `/^Logging/` are both `toBeDisabled()` (`StartPage.tsx`: `disabled={open.isPending}`), and heading "Open a project" is still drawn. After release, the start page goes: heading `{ name: "DemoDevice", level: 1 }`, then the canvas's `{ name: "Controller", exact: true }`. | `StartPage.tsx`'s `disabled={open.isPending}` removed: dies at the first `toBeDisabled`. The journey's second half is Step 6's: the bug it shows. |
| **4. The app: signed in by the one-time code `ddd gui` opens its own browser with** | `openedGui`. `const address = await openedGui.opened()`, the `/open?code=…` that `launched` (`server.py`) hands `webbrowser.open`. The code is valid for `CODE_SECONDS` (60 s) or until redeemed. For the second half, `browser.newPage()`, a fresh context holding no token. | `page.goto(address)`. The page posts the code to `/open` (`signInFrom`, `api/signIn.ts`) and keeps the token it gets back. The canvas's "Controller" is visible. `toHaveURL(/\/project$/)`: the code has gone from the address (`landingOf`). The same address opened in the fresh page is refused, because a code is spent once (`redeem_code`). That page shows the `status` "Open the address ddd gui printed in its terminal." (`SignedOutView.tsx`). | `server.py`'s `GuiServer.redeem_code` answering `False`, in a scratch worktree: the first page is signed out and dies at "Controller". Twin: `signIn.ts`'s `secretOf` ignoring `code`. |
| **5. The app: connecting, before the session answers** | `gui`. Wait until the canvas shows, so the page is signed in and its address is `/project`. Then `const release = await held(page, "/api/session")` and `page.reload()`. Hold after the sign-in, not on `/open`: there the first `/api/session` is `signInFrom`'s own, asked before anything is rendered (`main.tsx`'s `Promise.allSettled`), and holding it leaves a blank page. | `getByText("Connecting…", { exact: true })` (`App.tsx`, the `session.isPending` branch). The masthead's "Projects" is drawn. There is no heading "DemoDevice" and no masthead button `{ name: "DemoDevice", exact: true }`, because `opened` is still `null`. After release: heading `{ name: "DemoDevice", level: 1 }`, and "Connecting…" `toHaveCount(0)`. | `App.tsx`'s `if (session.isPending) {…}` branch removed: a pending session falls through to `StartPage` (`opened === null`). Dies at "Connecting…". |
| **6. The app: the session failing** | `gui`. Wait until the canvas shows, then `const failed = await failing(page, "/api/session", "http")` and `page.reload()`. | An `alert` with `toHaveText(SERVER_FAILED)` (`App.tsx`'s `session.isError` branch: `<Banner tone="error">{session.error.message}</Banner>`). No heading "Open a project" and no "Controller" (`toHaveCount(0)`). `failed()` is 1: an HTTP answer is never sent again (`sentAgain`, `client.ts`), and queries have `retry: false` (`main.tsx`). | `App.tsx`'s `else if (session.isError)` branch removed: the page draws the start page and no alert. Dies at the alert. |
| **7. The app: analysing the project, before its first analysis lands** | `bareGui`. Once the list shows, `const release = await held(page, "/api/state")`. The page asks for no state while no project is open (`useProjectState(opened !== null)`), so the held request is its first. | Press `/^DemoDevice/`. `_open` answers at once and the server starts its first analysis (`api.py`'s `_open`, `Session.open`). The page shows heading `{ name: "DemoDevice", level: 1 }`, the "Project views" tab links, and `getByText("Analysing the project…", { exact: true })` (`App.tsx`, the `state === null` arm). There is no region "Modules": no tab asks anything before the first analysis (App.tsx's own comment). After release: "Controller", and "Analysing the project…" `toHaveCount(0)`. | `App.tsx`'s project-page "Analysing the project…" paragraph emptied (`<p className="quiet" />`): dies at the sentence. |
| **8. The app: the server answering again after it stopped** | `gui`, the canvas drawn. Then `failing(page, "/api/state", "network")` and `restamp(gui.directory, CONTROLLER)`, then `page.unrouteAll({ behavior: "wait" })`. The worked journey, Step 3. | The `alert` "ddd gui has stopped. Start it again and open the address it prints." (`App.tsx`'s `stopped` banner) shows with the canvas still drawn. Once the route is taken away, the banner goes. A change saved from outside then colours "SensorHub to Controller: 2 variables, error". | `state/revisions.ts`'s `if (stopped) { stopped = false; onStopped(false); }` removed: the banner stays. Dies at its `toHaveCount(0)`. |
| **9. The app: nothing written while the server is stopped: every Apply and every write's button disabled** | `gui`. Before `goto`, `drift(gui.directory, "ValueA", "rpm")` and `drift(gui.directory, "ValueB", "mV")`, as units.spec.ts:237 drifts both. Wait for "SensorHub to Controller: 2 variables, error". Then Controller, "Set the unit of ValueB", its panel's "Apply to 1 file", until that panel reads "Nothing to change" (this edit makes the Undo appear). Then "Set the unit of ValueA": its panel's "Apply to 1 file" and "Remove from Controller" are enabled. Keep Controller's bytes. Then `failing(page, "/api/state", "network")` and `restamp(gui.directory, SENSOR_HUB)`. | The `alert` "ddd gui has stopped. Start it again and open the address it prints.". Then `toBeDisabled()` on: (1) the ValueA panel's "Apply to 1 file" (`VariablePanel.tsx`'s `busy`, which ORs in `stopped`, into `VariablePanelView.tsx`); (2) its "Remove from Controller"; (3) the heading's "Add a declaration" (`ComponentPage.tsx`, `isDisabled={stopped}`); (4) the table's "Set the unit of ValueB" (same); (5) "Undo the unit of ValueB" (`UndoStrip.tsx`'s `busy`, which ORs in `stopped`). Controller's file is unchanged byte for byte. | `VariablePanel.tsx`'s `busy` without `stopped`: dies at the Apply's `toBeDisabled`. |
| **10. The app: an entry's panel just after a rename or a declaration, saying the findings are updating until the analysis lands** | `generatedGui`. Its analysis runs about a second: canvas.spec.ts:329 measured 0.85 s of "updating". Table, then "C00000", then "Add a declaration", declaring "Pressure" as declarations.spec.ts:42 does: Name, Scope "produces", Kind "measurement", "Volatile of Pressure" false, "Datatype of Pressure" uint8. Before the Apply, arm a frame recorder local to the spec, like shared.spec.ts's `watchPanels`, recording the text of `aside[aria-label="Pressure"]` at every frame. | Press "Apply to 1 file". `DeclarePanel`'s `onDeclared` opens the complementary "Pressure". Its first read, `GET /api/variable?name=Pressure`, is refused `unreadable` until the analysis indexes the new declaration (`panelShows`'s doc, `lib/refusals.ts`). While the findings update, the panel says only "Updating the findings…" (`VariablePanel.tsx`'s `answer.shown === "updating"` arm, `UpdatingNote`). `expect.poll` on the frames finds one whose panel holds its title, Close and "Updating the findings…", and nothing else: no "Reading Pressure…", no keys table, no error banner. Once the analysis has landed, the panel draws Pressure's keys, and its `.updating-note` `toHaveText("")`. | `lib/refusals.ts`'s `panelShows` without `!(updating && isUnreadable(answer.error))`, so every error is a refusal: the panel shows the `unreadable` sentence in an error banner instead. Dies at the frames' poll. |
| **11. The app: the changes a plan makes, shown and then hidden again** | `gui`. `drift(gui.directory)`. Wait for the error arrow, then Controller, then "Set the unit of ValueA". | In the panel's region "Settle the key": "Changes 1 file: controller.ddd.json" (`consequence`, `lib/units.ts`). Press "Show changes": one `.hunk` (`Changes.tsx`), containing `- "unit": "rpm",` and `+ "unit": "%",`. The button is now named "Hide changes" (`VariablePanelView.tsx`). Press it: `.hunk` `toHaveCount(0)`, and the button reads "Show changes" again. Controller's file is unchanged. | `VariablePanelView.tsx`'s settle button `onPress={() => props.onChangesShown(!props.changesShown)}` made `onChangesShown(true)`: dies at `.hunk` count 0. |
| **12. The undo strip: the files an undo puts back, being read** | `gui`. `drift(gui.directory)`. Wait for the error arrow, then Controller, "Set the unit of ValueA", "Apply to 1 file". Wait until the panel reads "Nothing to change" and the heading's `.updating-status` `toHaveText("")`: the edit's analysis has landed, so no new revision asks for the preview again under the hold. Then `const release = await held(page, "/api/undo")`. | Press "Undo the unit of ValueA". The region "Undo" reads `getByText("Reading the files…", { exact: true })` (`UndoStripView.tsx`, `preview === null`), with no "Put back 1 file". After release: "Puts back 1 file: controller.ddd.json" (`undoConsequence`, `lib/undo.ts`) and the button "Put back 1 file" (`undoAction`). "Reading the files…" `toHaveCount(0)`. | `UndoStripView.tsx`'s "Reading the files…" paragraph emptied: dies at the sentence. |
| **13. The undo strip: an undo the server fails on** | As row 12, up to the strip open with its preview drawn ("Puts back 1 file: controller.ddd.json"). Only then `const failed = await failing(page, "/api/undo", "http")`, so the one request it meets is the press's `POST`. The preview is asked again only at a new revision, and none is coming. | Press "Put back 1 file". The strip's `status` reads "The undo was refused: ddd gui failed on this request; the terminal it runs in shows why" (`refusalOf`, `UndoStrip.tsx`, around `SERVER_FAILED`). It stands alone: "Put back 1 file" `toHaveCount(0)`. Nothing is put back: Controller's file still states `"unit": "%"` for ValueA. "Undo the unit of ValueA" is still offered and enabled. `failed()` is 1: a POST is never sent again. | `UndoStrip.tsx`'s `onError: (error) => setRefused(…)` made a no-op: the strip draws its preview again. Dies at the status. |

- [ ] **Step 6: The bug, red first** (row "a project opening…"). Once `/api/open` answers, `onOpened` asks for the session again without waiting for it (`App.tsx`), and until that answer lands the start page is still drawn, with `open.isPending` false again, so every project's button is enabled: a press then opens another project in place of the one just opened.
  - The journey's second half holds the session's next read: register `held(page, "/api/session")` after the list shows and before the press, and see every project's button still `toBeDisabled()` once the open has answered and while the session is held. Red today.
  - The fix: the list's buttons stay disabled from the press until the start page goes, the decision a function in `gui/src/lib` under Vitest (the rule in *Global Constraints*), read by `StartPage.tsx`.
  - A CHANGELOG entry under `## Unreleased`.
- [ ] **Step 6b: Two bugs the earlier pre-flight found, each red first** (ruling 18; the drafts are in §A.1 and §A.2 of the companion):
  - **A build record with no image prints "built as" with nothing after it, and one image named twice prints twice** (`StartPage.tsx`'s `{project.images.length > 0 && (`, over `find_projects`' list). It is fixed at the source: `find_projects` (`src/ddd/gui/session.py`) skips an empty image and names each image once. Its pytest cases go in `tests/test_gui_session.py` first, and are watched failing.
  - **The component table's cell buttons stay enabled while the server is stopped.**
    - "Set the unit of ValueA" and "Show the values of CurveA" read `isDisabled={stopped}` inside the declarations table's `TableBody` render function. React Aria caches that function's rows per item, and `rows` does not change with `stopped`.
    - The fix is `<TableBody items={rows} dependencies={[stopped]}>` in `ComponentPage.tsx`.
    - Red first: row 9's journey asserts both cell buttons disabled, beside its five controls. Today it fails with "Expected: disabled, Received: enabled".
  - Each gets a CHANGELOG entry under `## Unreleased`.
- [ ] **Step 7: What the survey found, to confirm on the running page** and record as rulings for the maintainer (not fixed here: each is wording, or a choice of what to show):
  - With the session failed, the masthead's "Projects" changes the address and nothing else (`App.tsx` checks `session.isError` before `route.page === "start"`).
  - Pressing an unnamed project is refused with "<path> is not a project description", its path in native separators (`Session.open`), while the list beside it writes forward slashes (`_projects`'s `as_posix()`).
  - A failed read of the undo's preview reads "The undo was refused: …" before any undo was asked (`refusalOf`, `UndoStrip.tsx`).
  - The row "nothing written while the server is stopped" pins one screen's five write controls. The survey read the same `busy` rule, `stopped` included, in every screen that writes: ComparePage, ConstantPanel, DeclarePanel, FilesPage (three), FindingsPage, RasterPanel, SectionPanel, SharedPage, TypePanel, UndoStrip, UnitPanel, UnitsPage (two), ValuesPage, VariablePanel. The row's citation names that list beside its journey.
- [ ] **Step 8: The developer documentation.** In `docs/developer_documentation.rst`, beside the fixtures it lists, say what `openedGui` starts and what `opened` answers.
- [ ] **Step 9: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 10: The gates,** every journey included. Commit: one commit for the fixture, one for the bug and its journey, one for the other journeys.

### Task 4: the canvas and the components table

**Model:** opus, reviewed on opus. The viewport is measured, a project large enough for ranks only must be made and measured, and one row is reached inside the layout worker.

**Files:**
- Modify: `gui/e2e/canvas.spec.ts`, `gui/e2e/fixtures.ts`, `tools/generate_project.py`, `tests/test_generate_project.py`, `docs/developer_documentation.rst`, this plan's *The inventory*

**Interfaces:**
- Consumes: `copiedGui` (19b); `drift`, `driftMax`, `CONTROLLER`, `EVENT_LOGGER` (`gui/e2e/demo.ts`); `canvas.spec.ts`'s own `moduleOf` and `viewportOf`; `skeleton.spec.ts`'s `componentRow`, copied in.
- Produces: the generator's `chain` shape, and the fixture `chainedGui`.

**The earlier pre-flight** (ruling 18) drafted a journey for each of this task's rows, ran it ten times, and killed it with a named change: `2026-10-21-gui-journeys-remaining-preflight.md`, §A.4. Before writing a row's journey, read its draft: its setup, the words it read off the page, and the change that killed it. Then write the journey with this plan's helpers.

- [ ] **Step 1: The worked journey,** the row "a module's badge, counting its errors or its warnings", added to `gui/e2e/canvas.spec.ts` (its import line becomes the one below; `moduleOf` is the file's own):

```ts
import { CONTROLLER, drift, driftMax, EVENT_LOGGER, renameValueA } from "./demo";
import { expect, test } from "./fixtures";

test("a module's badge counts its warnings, and only its errors once it has any", async ({
  page,
  gui,
}) => {
  // ParameterA is Controller's own calibration, `scope` "local": a uint16 at a quarter of a hertz
  // a count, so it can hold at most 16383.75 Hz. A greatest limit of 99999 is then
  // `limits-out-of-range`, a warning (diagnostics.py), filed on Controller alone. Written plainly,
  // so the watcher sees it: the badge comes with the revision that reads it.
  driftMax(gui.directory, CONTROLLER, "ParameterA", 99999);
  await page.goto(gui.address);
  const controller = moduleOf(page, "Controller");
  // The badge is announced as the one picture it is, named by what it counts (`ModuleNode.tsx`):
  // a number alone would not say whether it counts errors or warnings. Its count is read off the
  // running page.
  const warned = controller.getByRole("img", { name: "1 warning", exact: true });
  await expect(warned).toHaveText("1");
  await expect(warned).toHaveClass("badge warning");
  // The other three modules have no finding, so no badge.
  for (const name of ["SensorHub", "UserInterface", "EventLogger"]) {
    await expect(moduleOf(page, name).getByRole("img")).toHaveCount(0);
  }

  // ValueA read by Controller in another unit than SensorHub produces it: `definition-mismatch`,
  // an error, filed on Controller's reading, not the producer's (analysis.py). The warning stays.
  drift(gui.directory);
  // Errors take the badge while there are any: it counts them alone, and stays one badge.
  const errored = controller.getByRole("img", { name: "1 error", exact: true });
  await expect(errored).toHaveText("1");
  await expect(errored).toHaveClass("badge error");
  await expect(controller.getByRole("img")).toHaveCount(1);
});
```

- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Ablate `ModuleNode.tsx`'s `const badge = data.errors > 0 ? data.errors : data.warnings;` to `const badge = data.errors;` in a scratch copy: it must die at `expect(warned).toHaveText("1")`. A second ablation, `tone`'s two arms swapped, dies at `toHaveClass("badge warning")`.
- [ ] **Step 3: The generator's `chain` shape, red first,** for the row "laid out in ranks only". Today's shapes cannot make a graph deep enough: the "many" shape reads an output 30 components on (`LAYER`), so the depth dagre meets is the components over 30, and reaching the worker's overflow (about 908 deep, `ranked`'s doc in `gui/src/lib/layout.ts`) would take about 817,000 declarations. In `tests/test_generate_project.py`, in the style of its own cases:
  - a chain of 200 declarations has 100 components, each of one output and one input;
  - component `k` reads component `k + 1`'s output, and the last reads the first's: one cycle as long as the project, which dagre breaks into one chain;
  - `--shape chain` is accepted by `main`, and a shape outside `SHAPES` still names all of them in its refusal.

  Then, in `tools/generate_project.py`: `"chain"` added to `SHAPES` and its docstring; `_sizes` answering `_even(declarations, declarations // 2)` for it; `generate`'s `shift` made `1` for it; the refusal's sentence naming it. Run the file's tests, then the whole suite at 100 %.
- [ ] **Step 4: The fixture `chainedGui`,** in `gui/e2e/fixtures.ts`: `generated` takes the generator's options as an argument, defaulting to today's, kept as the constant `MANY`, and `chainedGui` serves `generated(directory, ["--declarations", String(<declarations>), "--shape", "chain"])` as `generatedGui` serves its own. Never `--unread`: it turns inputs into outputs, and the chain would break where it did. Measure first, on the development PC and on all three legs at this task's full run, the smallest chain that reaches ranks only, and use twice that; record the measure in *Figures*. If no chain within the gui job's timeouts reaches it, or the canvas takes longer to draw it than a journey may wait, the row names the sizes tried and their times instead of a journey (spec §10), and `chainedGui` and the shape are left out.
- [ ] **Step 5: The other rows,** each a journey of its own in `canvas.spec.ts`.
  - Every geometric assertion is an `expect.poll` with a stated tolerance. Never a sleep for the 300 ms flight.
  - Each is run with `--repeat-each=10`, because the viewport's animation is the likeliest place for a race.
  - Each is ablated as its row says.

  The rows, as read at `2bc00da`:

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **14. The canvas: the project's graph failing before anything is drawn** | None: already driven. | `network.spec.ts`'s "a GET the network fails every time reads as the server not answering" (line 67 at `2bc00da`) fails `/api/graph` every time and asserts the canvas's alert, "ddd gui is not answering", in place of the canvas. The row cites it; no new journey. | `GraphPage.tsx`'s `if (graph.isError) return <Banner …>` removed: that journey dies at its alert (read, not run: confirm it). |
| **15. The canvas: a module whose file does not load, drawn as not loaded** | `copiedGui("demo", unloaded)`. `unloaded` adds a key the component model does not have to Controller's `component` block: `"name": "Controller",` becomes `"name": "Controller",\n    "unexpected": true,`. The model forbids extra keys (`schemas/ddd_component.schema.json`, `additionalProperties: false`). The file still parses, so it is still a component (`kind_of`, `session.py`). It fails `schema`, one of `LOAD_CHECKS` (`lsp/navigation.py`), so it is not loaded (`_described`). Do not cut it in half: a file that does not parse is of kind `unknown` and draws no module at all (canvas.spec.ts:68's own note). | A button `{ name: "controller (not loaded)", exact: true }`. It is named by its file's stem because it did not load that far (`_module`, `api.py`), and `ModuleNode.tsx` adds " (not loaded)". Its box is `.module.unloaded`, with no badge (`data.loaded && badge > 0`). "SensorHub", "UserInterface" and "EventLogger" are drawn beside it. The `status` "This project has no dictionary, so its modules are drawn without arrows." stands above (`GraphPage.tsx`). There is no button "Controller". | `ModuleNode.tsx`'s `` {data.loaded ? data.name : `${data.name} (not loaded)`} `` made `{data.name}`: dies at "controller (not loaded)". |
| **16. The canvas: a module's badge, counting its errors or its warnings** | `gui`. `driftMax(gui.directory, CONTROLLER, "ParameterA", 99999)` before `goto`, then `drift(gui.directory)` mid-journey. The worked journey, Step 1. | Controller's badge is `getByRole("img", { name: "1 warning", exact: true })`, reading "1", with class `badge warning`. No other module has a badge. After the drift, the badge reads `{ name: "1 error" }`, with class `badge error`, and it is the only badge Controller has. The aria-label is `${badge} ${tone}${badge > 1 ? "s" : ""}` (`ModuleNode.tsx`). Both counts are read off the page. | `ModuleNode.tsx`'s `const badge = data.errors > 0 ? data.errors : data.warnings;` made `data.errors`: dies at the warning badge. |
| **17. The canvas: an arrow reached by the keyboard, saying what is wrong** | `gui`. `drift(gui.directory)` before `goto`. | The button "SensorHub to Controller: 2 variables, error" (`sentenceOf`, `lib/canvas.ts`) is reached one Tab at a time with units.spec.ts:237's bounded loop, then `toBeFocused()`. A `tooltip` shows (`FlowEdge.tsx`, while `data.active`; `edgesOf`'s `onFocus`). Its `.objects` paragraph reads "ValueA, ValueB". It has one item: "definition-mismatch", then the analysis's sentence "'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (…)" (`analysis.py`'s `definition-mismatch`; read the bracket off the page). The arrow's `toHaveAccessibleDescription(/definition-mismatch/)` holds, through its `aria-describedby`. One more Tab and the tooltip `toHaveCount(0)` (`onBlur`). | `lib/canvas.ts`'s `onFocus: () => onReached(id),` removed from `edgesOf`'s `domAttributes`: dies at the tooltip. |
| **18. The canvas: zoomed in and out with the canvas's own buttons** | `gui`. Wait for four `.react-flow__node`, then `const opening = await viewportOf(page)`. | React Flow's own `<Controls showInteractive={false} showFitView={false} />` (`GraphPage.tsx`) draws buttons `{ name: "Zoom In", exact: true }` and `{ name: "Zoom Out", exact: true }` (`defaultAriaLabelConfig`, `@xyflow/system` 0.0.82). Press "Zoom In": `expect.poll` the zoom to `opening.zoom * 1.2`, `closeTo` 3 places, since `zoomIn` scales by 1.2. Press "Zoom Out": back to `opening.zoom`. Press "Zoom Out" again until it is `toBeDisabled()`, at most 10 presses: the zoom stands at 0.5, the canvas's floor (`minZoom={MIN_ZOOM}`, `lib/canvas.ts`). | `GraphPage.tsx`'s `minZoom={MIN_ZOOM}` made `minZoom={0.25}`: dies at the zoom of 0.5. A second ablation, `showZoom={false}` on `<Controls>`, dies at "Zoom In". |
| **19. The canvas: laid out in ranks only, for a project too large for the full layout** | `chainedGui` (Steps 3 and 4): a chain of components, each reading the next one's output, twice as long as the smallest that reaches ranks only on every leg (the survey reads about 2,000 components, 4,000 declarations, off `ranked`'s doc). | Once laid out: "Laid out in ranks only: the project is too large for the full layout." (`RANKS_ONLY_NOTE`, `lib/layoutAnswers.ts`), a quiet `<p>` above the canvas, from `layoutScreen`'s `note`. The canvas opens on its first rank at the minimum zoom (`openingViewport`): the chain's first module's button is visible, and there is no `alert`. | `lib/layout.ts`'s `layoutOf` rethrowing the `RangeError`: the worker answers an error, and the "failed" screen draws no canvas. Dies at the note. |
| **20. The canvas: a later layout failing, the canvas kept** | `gui`, with the canvas drawn, so the worker has answered once. Then fail the worker's own thread: `const worker = page.workers().find((w) => /layoutWorker-/.test(w.url()))`, then `await worker.evaluate(() => { setTimeout(() => { throw new Error("the layout worker failed"); }); })`. The worker does not catch that exception, so the page's `Worker` hears it as `error` (`useLayout.ts`'s `onerror`). Planning ruling 10; Step 6. | `createdAgain({ again: false, answered: true })` is `false`, so no worker is made again. An `alert` "The layout worker stopped; reload the page to try again." (`WORKER_FAILED`, `lib/layoutAnswers.ts`) stands above the canvas (`layoutScreen`'s `errorMessage`). The four modules are still drawn, and so are "Search modules", "Tidy" and "Fit". | `lib/layoutAnswers.ts`'s `withAnswer` error arm made to return `{ ...INITIAL_LAYOUT_STATE, error: answer.error }`: the canvas is replaced by the "failed" screen. Dies at "Controller" still visible. |
| **21. The components table: a row pressed beside its name, or Enter on it, opening its component** | `gui`, the "Table" link. | Press Controller's Warnings cell, `componentRow(page, "Controller").getByRole("gridcell").nth(1)`. Heading `{ name: "Controller", level: 1 }`, `toHaveURL(/\/component\?file=.*controller\.ddd\.json$/)` (`ProjectPage.tsx`'s `onRowAction`). `page.goBack()` returns to the table. Then by keyboard: Tab until a `row` of the grid "Components" has focus (bounded), ArrowDown until SensorHub's row `toBeFocused()` (bounded), Enter: heading "SensorHub", and the address ends in `sensor_hub.ddd.json`. | `ProjectPage.tsx`'s `onRowAction={(key) => onComponent(String(key))}` removed: dies at the heading "Controller". |

- [ ] **Step 6: The row reached inside the worker** (planning ruling 10). "A later layout failing, the canvas kept" cannot be reached from the network or a project: the worker's script is fetched once per canvas, and every later shape goes to that same worker, whose `layoutOf` answers an error only for an input the server never sends. The journey throws an uncaught error in the worker's own thread through `page.workers()` and `worker.evaluate`, as a worker that crashed would. Its comment says so, and cites the ruling.
- [ ] **Step 7: What the survey found, to confirm on the running page** and record as rulings for the maintainer: each arrow's `aria-describedby` names a tooltip that exists only once the arrow is reached (`FlowEdge.tsx`, `data.active`), and `onFocus` sets it as state, so the tooltip mounts a render after focus has landed. A screen reader reading the description at the moment of focus may find nothing. No journey can show it.
- [ ] **Step 8: The developer documentation.** In `docs/developer_documentation.rst`, beside `generatedGui`, say what `chainedGui` serves and why; and in the paragraph on `tools/generate_project.py`, if it has one, the `chain` shape.
- [ ] **Step 9: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 10: The inventory.** Each row names its journey, or its reason. The row "the project's graph failing before anything is drawn" cites `network.spec.ts`'s "a GET the network fails every time reads as the server not answering", which already drives it.
- [ ] **Step 11: The gates,** every journey included, and the whole pytest suite for the generator. Commit: one commit for the generator's shape and its tests, one for the fixture, one for the journeys.

### Task 5: Units and Types

**Model:** sonnet, reviewed on sonnet. Each row is a state the two tabs already draw; the reading and failing rows share one shape.

**Files:**
- Modify: `gui/e2e/project-units.spec.ts` (the Units rows), `gui/e2e/types.spec.ts` (the Types rows), this plan's *The inventory*

**Interfaces:**
- Consumes: `held` (Task 1); `failing`, `SERVER_FAILED`, `copiedGui` (19b); `driftIn`, `PUMP`, `UNITS` (`gui/e2e/demo.ts`); the fixtures `gui`, `vocabularyGui`, `structuresGui`. The kept answer (Task 2): a *first* read that fails still shows the error alone, which rows "the units failing to load" and "the types failing to load" pin (Review Focus 4).

**Read before the rows** (the survey, at `2bc00da`):

- **No panel or tab here was asked for before its tab opens.** `getUnits` is called by
  `UnitsPage`, `UnitPanel`, `TypePanel` and `VariablePanel`; `getTypes` by `TypesPage` alone. From
  the canvas, the first `/api/units` is the Units tab's and the first `/api/types` the Types
  tab's, so `held`'s `{ times: 1 }` holds the read the row is about.
- **A type's panel reads the units too** (`TypePanel`'s `units` query): its reading line stands
  until both `/api/type` and `/api/units` answer. Holding `/api/type` alone is enough.
- **The type panel's findings are links, the unit panel's are not.** `TypePanelView` draws every
  routed finding as a button (`routeOf`, `lib/findings.ts`); `UnitPanelView` draws them as text.
  Most findings inside a type route to *that type* (`WITHIN_TYPE`, `finding_routes.py`): followed,
  they lead to the panel they are drawn in. The one shipped way out is `unknown-unit`, routed to
  the unit because `route_of` tries `UNIT_CHECKS` before `WITHIN_TYPE`. Row 16 is built on it.
- **examples/vocabulary's units in use** are `Nm` (Torque_t, inline in pump.ddd.json), `kPa`
  (ManifoldPressure, PressureTrend) and `rpm` (PumpSpeed); `degC` is listed and stated by nothing.
  Emptied, its units file makes all three "not in the vocabulary".
- **examples/structures states units in two files only:** `degC` (sensing.ddd.json's
  InletTemperature; types.ddd.json's Temperature_t) and `ms` (Sample_t's `timestamp` member).
- **Row 17 types into the description, not a key row,** so P19b-13's empty plan for a selection
  that changes nothing never enters it.

**The earlier pre-flight** (ruling 18) drafted a journey for each of this task's rows, ran it ten times, and killed it with a named change: `2026-10-21-gui-journeys-remaining-preflight.md`, §A.5. Before writing a row's journey, read its draft: its setup, the words it read off the page, and the change that killed it. Then write the journey with this plan's helpers.

- [ ] **Step 1: The worked journey,** the row "a finding in a type's panel followed", in `gui/e2e/types.spec.ts`. Add `driftIn` and `PUMP` to its `./demo` import:

```ts
test("a finding in a type's panel leads to the unit it names, on the Units tab", async ({
  page,
  copiedGui,
}) => {
  // Torque_t, the scalar Pump declares inline, made to state a spelling examples/vocabulary's units
  // file does not list - before the server starts, so that the first analysis the page reads
  // already files the finding. `unknown-unit` is filed at the type's own `unit` key
  // (`_check_units`, analysis.py), inside the type's entry, so the type's panel lists it
  // (`located_in_type`, project_types.py); and it is routed to the unit rather than to the type,
  // because `route_of` (finding_routes.py) tries UNIT_CHECKS before WITHIN_TYPE. A finding routed
  // to the type itself would lead to the very panel it is drawn in, and nothing would be followed.
  const gui = await copiedGui("vocabulary", (directory) => {
    driftIn(directory, PUMP, "Torque_t", "NM");
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Types", exact: true }).click();
  await page.getByRole("row", { name: "Torque_t", exact: true }).click();

  // The analysis's own sentence is the link, its did-you-mean included: `close_units` answers "Nm"
  // alone for "NM" against this vocabulary. A button styled as a link, as the panel draws every
  // routed finding.
  const panel = page.getByRole("complementary", { name: "Torque_t", exact: true });
  const finding = panel.getByRole("listitem").filter({ hasText: "unknown-unit" });
  await expect(finding.locator(".chip")).toHaveText("unknown-unit");
  await finding
    .getByRole("button", {
      name: "'NM' is not a unit this project declares - did you mean 'Nm'?",
      exact: true,
    })
    .click();

  // The Units tab, on the unit's own panel. `exact: true` on the panel's name: a role's name is
  // otherwise matched without regard to case, and the vocabulary's own "Nm" is a unit too.
  await expect(page).toHaveURL(/\/project\?view=units&unit=NM$/);
  const unit = page.getByRole("complementary", { name: "NM", exact: true });
  await expect(
    unit.getByText("not in the vocabulary · stated in 1 place, 1 file", { exact: true }),
  ).toBeVisible();
  // The one place stating it is the type the reader came from.
  await expect(unit.getByRole("row", { name: "Torque_t", exact: true })).toContainText(
    "scalar type",
  );
});
```

- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Two ablations, each dying at `toHaveURL`: `TypePanelView.tsx`'s finding button's `onPress` made a no-op (a scratch copy of the package), and `finding_routes.py`'s `UNIT_CHECKS` arm moved below `WITHIN_TYPE` (a scratch worktree). Read the finding's whole message, and the name of the row "Where NM is stated" draws for a type (`places_of`, `project_units.py`), off the running page before asserting them.
- [ ] **Step 3: The other rows,** each a journey of its own, run with `--repeat-each=10` and ablated as its row says. The rows, as read at `2bc00da`:

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **1. Units: reading the project's units** | `gui`; the canvas drawn ("Controller" visible); then `held(page, "/api/units")` | Press the link "Units" (`exact: true`). While held: the text "Reading the project's units…" (`UnitsPage.tsx`, `UnitsPage`'s early return). Released (`finally`): the summary "5 units · no units file" (`tabTitle`, `lib/projectUnits.ts`), and the reading line has count 0. Title: "the units tab says it is reading the project's units until they are read". | `UnitsPage.tsx`'s loading line (`return <p className="quiet">Reading the project's units…</p>`) made `return null`: dies at "Reading the project's units…". |
| **2. Units: the units failing to load** | `gui`; `failing(page, "/api/units", "http")` before `goto` | Press "Units". `page.getByRole("alert")` has text `SERVER_FAILED` (`UnitsPage`'s `if (units.isError) return <Banner tone="error">…`). No summary: `page.getByText(/ units · /)` count 0; `page.getByRole("grid", { name: "Units" })` count 0; no "This project has no units file" status. `failed()` ≥ 1. This is Review Focus 3's journey: after Task 2 a *first* read failing still shows the error alone. Title: "the units failing to load leave the server's own error, with no table". | `UnitsPage.tsx`'s `if (units.isError) return <Banner …>` removed (after Task 2, inside `if (answer === undefined)`): the tab says "Reading the project's units…" for good; dies at the alert. |
| **3. Units: a unit's panel reading the unit** | `gui`; Units tab drawn, row "ms" visible; then `held(page, (url) => url.pathname === "/api/unit" && url.searchParams.get("name") === "ms")` | Press the row "ms" (`exact: true`). While held: `complementary` "ms" (`exact: true`) shows "Reading ms…" (`UnitPanel.tsx`, `UnitPanel`'s last early return), and no combobox "Rename ms to". Released: its meta "stated in 1 place, 1 file" (`unitMeta`, `lib/projectUnits.ts`; the demo has no units file, so the line is the places alone); "Reading ms…" count 0. Title: "a unit's panel says it is reading the unit until it is read". | `UnitPanel.tsx`'s reading branch (`<Panel …><p className="quiet">Reading {name}…</p></Panel>`) made `return null`: dies at "Reading ms…". |
| **4. Units: a unit's panel failing to read the unit** | `gui`; `failing(page, "/api/unit", "http")` before `goto` (the pathname is exact: `/api/units` and `/api/unit-plan` go through) | Press "Units", then row "ms". `complementary` "ms": its heading "ms" visible, `panel.getByRole("alert")` has text `SERVER_FAILED` (`UnitPanel`'s `answer.shown === "refusal"` branch, `panelShows` in `lib/refusals.ts`), no combobox "Rename ms to". The table stays: row "ms" visible. No status "ms is no longer stated or listed in the open project." (the error's code is `internal`, not `not-found`). Title: "a unit's panel whose unit fails to load says why, beside the table". | `UnitPanel.tsx`'s `if (answer.shown === "refusal")` branch removed: the panel falls through to "Reading ms…"; dies at the alert. |
| **5. Units: a units file listing no unit, the units in use adopted into it** | `copiedGui("vocabulary", (d) => writeFileSync(join(d, UNITS), '{ "units": [] }\n', "utf8"))`; `project.ddd.json`'s bytes kept | Press "Units". Summary "3 units · 3 not in the vocabulary" (`tabTitle`). The status banner (filter `hasText: "No unit this project states"`) holds the paragraph, `exact: true`: "No unit this project states is in its vocabulary. Adopting lists the 3 units in use in a units file: nothing is reported that is not reported today." (`adoptionSentence`'s `hasUnitsFile` arm, `lib/projectUnits.ts`). Its "Show changes": `complementary` "Adopt a vocabulary" with meta "Changes 1 file: units.ddd.json" (`consequence`, `lib/units.ts`; no "units.ddd.json, new", the file exists). Press "Adopt 3 units" (`adoptLabel`, `AdoptBannerView.tsx`). Poll `entriesOf(units)` to `[{unit:"Nm",description:""},{unit:"kPa",…},{unit:"rpm",…}]` (by code point: `adoption`, `ddd/lsp/units.py`); `project.ddd.json` byte-equal to before (nothing included: `adopt_units`'s `into` arm); summary "3 units · all in the vocabulary"; banner and preview count 0. Title: "a units file listing no unit has the units in use adopted into it, and nothing else written". | Page: `UnitsPage.tsx`'s `hasUnitsFile={hasUnitsFile(units.data)}` on `AdoptBannerView` passed `false`: the banner says "This project has no units file, …"; dies at the paragraph. Server (scratch worktree): `adopt_units`'s `if planned.into is not None:` arm removed, so the plan creates `units.ddd.json` beside the description where it already is; dies at "Changes 1 file: units.ddd.json". |
| **6. Units: a project stating no unit, with nothing to adopt** | `copiedGui("structures", (d) => stateNoUnit(d, ["sensing.ddd.json", "types.ddd.json"]))`, the spec-local helper below | Press "Units". Summary "0 units · no units file" (`tabTitle`). The status banner (filter `hasText: "This project has no units file"`) has text, whole: "This project has no units file, so no unit is checked against a vocabulary. It states no unit, so there is nothing to adopt." (`adoptionSentence`, adoptable `0`; `adoptable` in `ddd/project_units.py` answers `0` where `adoption` answers `None`). In it, buttons "Show changes" and `/^Adopt/` have count 0 (`AdoptBannerView` draws them only under a plan, and `adoptionAsked` asks none for `0`). Title: "a project stating no unit is told there is nothing to adopt, and offered nothing to press". | `lib/projectUnits.ts`'s `adoptionAsked` answering `units.adoptable !== null` (the `> 0` dropped): the plan is asked, the server refuses it ("this project states no unit, so there is nothing to adopt", `adopt_units`), and the banner's `adopt-refusal` paragraph joins its text; dies at the banner's whole text. |
| **7. Units: an Apply the server fails on** | `vocabularyGui`; Units tab; row "degC"; region "Remove from the vocabulary" shows "Changes 1 file: units.ddd.json"; then `const failed = await failing(page, "/api/edit", "http")` | Press the region's button "Remove from the vocabulary". In the region, `getByRole("status")` has text `` `The change was refused: ${SERVER_FAILED}` `` (`refusalOf`, `UnitPanel.tsx`; drawn by `Outcome`, `UnitPanelView.tsx`, above the plan asked for again). Nothing written: `entriesOf(units)`' units still include "degC". `failed()` is exactly 1 (a POST is never resent). The button is still offered. Title: "a removal the server fails on says so in its words, and nothing is written". | `UnitPanel.tsx`'s `onError` else-branch `setFailed({ action, message: refusalOf(error) })` removed: no status; dies at the sentence. |
| **8. Types: reading the project's types** | `structuresGui`; canvas drawn; `held(page, "/api/types")` | Press "Types" (`exact: true`). While held: "Reading the project's types…" (`TypesPage.tsx`, `TypesPage`'s early return). Released: the summary, by `typesTitle` (`lib/projectTypes.ts`) "6 types · 1 scalar, 4 structures, 1 external" (read it off the page), and the reading line count 0. Title: "the types tab says it is reading the project's types until they are read". | `TypesPage.tsx`'s loading line made `return null`: dies at "Reading the project's types…". |
| **9. Types: the types failing to load** | `structuresGui`; `failing(page, "/api/types", "http")` before `goto` | Press "Types". `alert` has text `SERVER_FAILED`; no summary (`page.getByText(/^\d+ types? ·/)` and "This project declares no types" count 0); `grid` "Types" count 0. `failed()` ≥ 1. Title: "the types failing to load leave the server's own error, with no table". | `TypesPage.tsx`'s `if (types.isError) return <Banner …>` removed: "Reading the project's types…" for good; dies at the alert. |
| **10. Types: a type's panel reading the type** | `structuresGui`; Types tab, row "Temperature_t" visible; `held(page, (url) => url.pathname === "/api/type" && url.searchParams.get("name") === "Temperature_t")` | Press row "Temperature_t" (`exact: true`). While held: `complementary` "Temperature_t" shows "Reading Temperature_t…" (`TypePanel.tsx`, `TypePanel`'s last early return), and no textbox "Rename Temperature_t to". Released: that textbox visible, "Reading Temperature_t…" count 0. Title: "a type's panel says it is reading the type until it is read". | `TypePanel.tsx`'s reading branch made `return null`: dies at "Reading Temperature_t…". |
| **11. Types: a type's panel failing to read the type** | `structuresGui`; `failing(page, "/api/type", "http")` before `goto` | Press "Types", then row "Temperature_t". `complementary` "Temperature_t": heading "Temperature_t", `panel.getByRole("alert")` has text `SERVER_FAILED` (`TypePanel`'s `answer.shown === "refusal"` branch), no textbox "Rename Temperature_t to"; row "Temperature_t" still drawn; no status "no longer declared". Title: "a type's panel whose type fails to load says why, beside the table". | `TypePanel.tsx`'s `if (answer.shown === "refusal")` branch removed: "Reading Temperature_t…"; dies at the alert. |
| **12. Types: the untold banner** | `structuresGui`; Types tab drawn, summary of row 8 visible | Write `types.ddd.json` cut in half (`writeFileSync(path, whole.subarray(0, Math.floor(whole.length / 2)))`, seen by the watcher): it no longer parses, so its kind is `unknown` (`kind_of`, `session.py`). `page.getByRole("status").filter({ hasText: "did not load" })` has text "types.ddd.json did not load, so whatever is declared there is not listed." (`TypesTableView.tsx`, the `untold` banner; `unreadable`, `lib/findings.ts`). The summary reads "This project declares no types" (`typesTitle`); row "Temperature_t" count 0; the other banner, `page.getByText("the types declared there are not listed")`, count 0. Title: "a types file saved half-written is named above the table, whatever it declared untold". | `TypesPage.tsx`'s `untold={missing.untold}` passed `untold={[]}`: dies at the banner. |
| **13. Types: the unreadable banner** | `structuresGui`; Types tab drawn | Rewrite `types.ddd.json` plainly with Temperature_t's datatype made `"uint17"` (`/("name": "Temperature_t"[\s\S]*?"datatype": )"uint16"/` to `$1"uint17"`, throwing if nothing matched): still json and still a types file, but `Datatype` is a `StrEnum` (`models/common.py`) and `TypesFile` fails its model. The status (filter `hasText: "did not load"`) has text "types.ddd.json did not load, so the types declared there are not listed." (`TypesTableView.tsx`, the `unreadable` banner); "This project declares no types"; the untold sentence (`"whatever is declared there"`) count 0. Title: "a types file that parses but breaks its model is named above the table, its types missing". | `TypesPage.tsx`'s `unreadable(state, ["types"])` asked with `["type"]`, the entry's singular for the file's plural (the slip `SharedTableView`'s `unreadable` doc warns of): `own` is empty; dies at the banner. |
| **14. Types: a type's "Where it is used" followed to the declaration** | `structuresGui` | Types tab, row "SensorCal_t" (`exact: true`). In `complementary` "SensorCal_t", heading "Where it is used": `panel.getByRole("row", { name: /^InletCal/ })`'s cells have texts `["InletCal", "sensing.ddd.json", "Sensing · local"]` (`TypePanelView.tsx`: `use.name`, `baseName(use.path)`, `whatOf`; the role `local` is `ROLES`, `ddd/variables.py`). Press its button "InletCal". The address matches `/\/component\?file=[^&]*sensing\.ddd\.json&variable=InletCal$/`; heading "Sensing", level 1; `complementary` "InletCal" visible. Title: "a type's Where it is used leads to the variable naming it, on its component's page". | `TypePanelView.tsx`'s `routeOfUse` variable arm answering `{ page: "component", file: use.path }` (no `variable`): Sensing's page opens with no panel and an address ending at the file; dies at the address, before `complementary` "InletCal". |
| **15. Types: a structure's member followed to its type** | `structuresGui` | Types tab, row "Sensor_t". In `complementary` "Sensor_t", heading "Members": `panel.getByRole("row", { name: /^latest/ })`; press its button "Sample_t" (`exact: true`; `memberRows`, `lib/projectTypes.ts`, `typename` drawn as a button in `TypePanelView`). The address matches `/\/project\?view=types&type=Sample_t$/`; `complementary` "Sample_t" (`exact: true`) has its meta "structure · types.ddd.json" (`TypePanelView`'s `meta`, `KIND_WORDS`); `complementary` "Sensor_t" count 0. Title: "a structure's member leads to the panel of the type it names". | `TypePanelView.tsx`'s member button's route `type: typename` made `type: type.name` (the panel's own): the panel stays on Sensor_t; dies at the address. |
| **16. Types: a finding in a type's panel followed** | `copiedGui("vocabulary", (d) => { driftIn(d, PUMP, "Torque_t", "NM"); })`: Torque_t, declared inline in pump.ddd.json, states a spelling the vocabulary does not list, before the server starts | The worked journey, Step 1. Types tab, row "Torque_t". In `complementary` "Torque_t", the list item with chip "unknown-unit"; its button, `exact: true`, "'NM' is not a unit this project declares - did you mean 'Nm'?" (`_check_units` and `_suggesting`, `analysis.py`; `close_units` answers "Nm" alone against rpm, Nm, degC, kPa). Pressed: the address matches `/\/project\?view=units&unit=NM$/`; `complementary` "NM" (`exact: true`) shows "not in the vocabulary · stated in 1 place, 1 file" (`unitMeta`); its row "Torque_t" contains "scalar type" (`placeRole`). Title: "a finding in a type's panel leads to the unit it names, on the Units tab". | Page: `TypePanelView.tsx`'s finding button `onPress={() => props.onOpen(route)}` made `onPress={() => undefined}`: dies at the address. Server (scratch worktree): `finding_routes.py`'s `UNIT_CHECKS` arm moved below `WITHIN_TYPE`: the finding routes to Torque_t itself, the address ends `type=Torque_t`; dies at the address. |
| **17. Types: an Apply the server fails on** | `structuresGui`; Temperature_t's panel; region "Description"'s textbox filled with a new sentence; "Changes 1 file: types.ddd.json" visible; then `const failed = await failing(page, "/api/edit", "http")` | Press "Apply to 1 file". `panel.getByRole("status")` has text `` `The change was refused: ${SERVER_FAILED}` `` (`refusalOf` in `TypePanel.tsx`; `TypePanelView`'s `panel-refusal`). The refusal stands where the plan was: `panel.getByRole("button", { name: /^Apply to/ })` count 0. The field keeps what was typed; `entryOf(directory, "Temperature_t")` equals the entry before; `failed()` is 1. Title: "an apply made from a type's panel that the server fails on says so in its words, and nothing is written". | `TypePanel.tsx`'s `onError` else-branch `setRefused({ kind, message: refusalOf(error) })` removed: dies at the status. |

  The row "a project stating no unit" uses a helper local to `project-units.spec.ts`:

  ```ts
  /** Every `unit` key taken out of the named files of a copy, wherever it is written: on a
   * declaration, a scalar type or a structure member. Rewritten whole, as `typeCurveA` (demo.ts)
   * rewrites a file whose shape changes: a line taken out by text would leave a comma behind where
   * the unit was the last key of its object (Sample_t's `timestamp`). */
  function stateNoUnit(directory: string, files: readonly string[]): void {
    const stripped = (value: unknown): unknown => {
      if (Array.isArray(value)) return value.map(stripped);
      if (value === null || typeof value !== "object") return value;
      return Object.fromEntries(
        Object.entries(value)
          .filter(([key]) => key !== "unit")
          .map(([key, inner]) => [key, stripped(inner)]),
      );
    };
    for (const file of files) {
      const path = join(directory, file);
      const text = JSON.stringify(stripped(JSON.parse(readFileSync(path, "utf8"))), null, 2);
      writeFileSync(path, `${text}\n`, "utf8");
    }
  }
  ```

- [ ] **Step 4: What the survey found, to confirm on the running page** and record as rulings for the maintainer:
  - **A panel whose read of the units fails says it is reading, for good.** `TypePanel.tsx`, `UnitPanel.tsx` and `VariablePanel.tsx` each draw "Reading {name}…" while their `["units", revision]` query holds no answer, and none reads its error. Reachable today: `structuresGui`, `failing(page, "/api/units", "http")`, Temperature_t's panel opened: the type's own read succeeds, and the panel says "Reading Temperature_t…" with no alert. After Task 2 it shows on the Units tab too: a new revision's failed read keeps the table and its alert, while an open unit's panel turns to "Reading ms…". It spans three panels, so it is not fixed here (planning ruling 14).
  - **A type's panel links a finding routed back to the type itself** (most findings inside a type, by `WITHIN_TYPE`), where a variable's panel keeps such a finding as text (`namesThisVariable`, `lib/findings.ts`). The types design allows it; whether a link to the panel it is drawn in should stay text is the maintainer's.
- [ ] **Step 5: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 6: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 7: The gates,** every journey included. Commit: one commit for the Units rows, one for the Types rows.

### Task 6: Shared files

**Model:** sonnet, reviewed on sonnet. The rows are states the tab and its panels already draw, and one refusal written before the press.

**Files:**
- Modify: `gui/e2e/shared.spec.ts`, this plan's *The inventory*

**Interfaces:**
- Consumes: `held` (Task 1); `failing`, `SERVER_FAILED` (19b); `writeUnseen`, `PUMP` (`gui/e2e/demo.ts`); `shared.spec.ts`'s own `FILES`, `entriesOf`, `entryOf`, `openEntry`, `openAt`, `openForm` and `STALE`.

**Read before the rows** (the survey, at `2bc00da`):

- **`getShared` is called by `SharedPage` alone,** and `getConstant` by `ConstantPanel` alone, so
  the first of each is the row's own.
- **Only PRESSURE_CELLS is declared inside a component** (pump.ddd.json's
  `component.constants[0]`). `ConstantPanelView` reads that off the entry's pointer
  (`declaredInComponent`) and draws its "Declared in" file as a button leading to the component's
  page; TREND_SAMPLES's, in constants.ddd.json, is text, since a constants file has no page.
- **The add form and the panels treat an Apply's refusal differently** (P19b-24): `SharedAdd`
  (`SharedPage.tsx`) sets `refusalOf(error)` and draws no plan and no Apply while it stands, until
  the next edit; `ConstantPanel` keeps the plan and its Save under the refusal.
- **The add form's Apply is not held back while its plan is pending:** `SharedAddView` draws the
  Apply only under a plan `planShown` trusts (`lib/typing.ts`), so waiting on the consequence line
  is enough.

**The earlier pre-flight** (ruling 18) drafted a journey for each of this task's rows, ran it ten times, and killed it with a named change: `2026-10-21-gui-journeys-remaining-preflight.md`, §A.6, its Shared files rows. Before writing a row's journey, read its draft: its setup, the words it read off the page, and the change that killed it. Then write the journey with this plan's helpers.

- [ ] **Step 1: The worked journey,** the row "an entry's panel reading the entry", in `gui/e2e/shared.spec.ts`. Its `./demo` import becomes `import { held, PUMP, writeUnseen } from "./demo";`, and the failing rows add `failing` and `SERVER_FAILED`:

```ts
test("an entry's panel says it is reading the entry until it is read", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  const row = page.getByRole("row", { name: "TREND_SAMPLES", exact: true });
  await expect(row).toBeVisible();

  // The panel's own read of the constant, held until the journey has seen the panel wait for it:
  // that read alone, by its name, so the tab's list and the constant's plans go straight through.
  const release = await held(
    page,
    (url) => url.pathname === "/api/constant" && url.searchParams.get("name") === "TREND_SAMPLES",
  );
  const panel = page.getByRole("complementary", { name: "TREND_SAMPLES", exact: true });
  const reading = panel.getByText("Reading TREND_SAMPLES…", { exact: true });
  try {
    await row.click();
    // The panel opens at once, under the entry's name, and offers nothing it has not read yet.
    await expect(reading).toBeVisible();
    await expect(panel.getByRole("textbox")).toHaveCount(0);
  } finally {
    release();
  }

  // Read: the constant's own value, and the reading line gone.
  await expect(panel.getByRole("textbox", { name: "Value" })).toHaveValue("16");
  await expect(reading).toHaveCount(0);
});
```

- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Ablate `ConstantPanel.tsx`'s reading branch (`if (entry === undefined) return <Panel …><p className="quiet">Reading {name}…</p></Panel>`) to `return null`, in a scratch copy of the package: it must die at `toBeVisible` on "Reading TREND_SAMPLES…".
- [ ] **Step 3: The other rows,** each a journey of its own, run with `--repeat-each=10` and ablated as its row says. The rows, as read at `2bc00da`:

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **18. Shared files: reading the project's shared files** | `vocabularyGui`; canvas drawn; `held(page, "/api/shared")` | Press the link "Shared files" (`exact: true`). While held: "Reading the project's shared files…" (`SharedPage.tsx`, `SharedPage`'s early return). Released: the summary "2 constants · 3 rasters · 2 sections" (`tabTitle`, `lib/shared.ts`), and the reading line count 0. Title: "the shared files tab says it is reading the project's shared files until they are read". | `SharedPage.tsx`'s loading line made `return null`: dies at "Reading the project's shared files…". |
| **19. Shared files: the shared files failing to load** | `vocabularyGui`; `failing(page, "/api/shared", "http")` before `goto` | Press "Shared files". `alert` has text `SERVER_FAILED` (`SharedPage`'s `if (shared.isError) return <Banner tone="error">…`). Nothing of the table: "2 constants · 3 rasters · 2 sections" count 0, `grid` "Shared files" count 0, button "Declare an entry" count 0. `failed()` ≥ 1. Title: "the shared files failing to load leave the server's own error, with no table and no way to declare". | `SharedPage.tsx`'s `if (shared.isError) return <Banner …>` removed: "Reading the project's shared files…" for good; dies at the alert. |
| **20. Shared files: an entry's panel reading the entry** | `vocabularyGui`; Shared files tab, row "TREND_SAMPLES" visible; `held(page, (url) => url.pathname === "/api/constant" && url.searchParams.get("name") === "TREND_SAMPLES")` | The worked journey, Step 1. Press the row. While held: `complementary` "TREND_SAMPLES" (`exact: true`) shows "Reading TREND_SAMPLES…" (`ConstantPanel.tsx`, `ConstantPanel`'s `entry === undefined` branch) and no textbox. Released: its textbox "Value" reads "16"; the reading line count 0. Title: "an entry's panel says it is reading the entry until it is read". | `ConstantPanel.tsx`'s reading branch made `return null`: dies at "Reading TREND_SAMPLES…". |
| **21. Shared files: an entry's panel failing to read the entry** | `vocabularyGui`; `failing(page, "/api/constant", "http")` before `goto` (`/api/constant-plan` goes through) | `openEntry(page, vocabularyGui, "TREND_SAMPLES")`. The panel: heading "TREND_SAMPLES", `panel.getByRole("alert")` has text `SERVER_FAILED` (`ConstantPanel`'s `answer.shown === "refusal"` branch), no textbox "Value". The table keeps the row; no `complementary` "Declare a constant" (the table lists the entry, so `opensPanel` draws the panel); no status "no longer declared". Title: "an entry's panel whose entry fails to load says why, beside the table". | `ConstantPanel.tsx`'s `if (answer.shown === "refusal")` branch removed: "Reading TREND_SAMPLES…"; dies at the alert. |
| **22. Shared files: a constant declared inside a component, its file followed** | `vocabularyGui` | `openEntry(…, "TREND_SAMPLES")`: `panel.locator(".panel-meta")` has text "Declared in constants.ddd.json", and `panel.getByRole("button", { name: "constants.ddd.json" })` count 0. Press row "PRESSURE_CELLS" (`exact: true`): its meta reads "Declared in pump.ddd.json" (`ConstantPanelView.tsx`, `baseName(reply.file)`), the file a button. Press the button "pump.ddd.json" (`exact: true`). The address matches `/\/component\?file=[^&]*pump\.ddd\.json$/`; heading "Pump", level 1; row "PumpSpeed" (`exact: true`) visible; `page.getByRole("complementary")` count 0. Title: "a constant declared inside a component leads to that component's page, where one in a constants file names its file alone". | `ConstantPanelView.tsx`'s Declared in button's `onPress` made `() => undefined`: dies at the address. Kept beside it: `declaredInComponent` made `true` dies at the count of the button "constants.ddd.json". |
| **23. Shared files: the add form's Apply refused as out of date** | `vocabularyGui`; `openForm(page, vocabularyGui, "constant", "SPARE")`; textbox "Value" filled "4"; "Changes 1 file: constants.ddd.json" visible, `Apply to 1 file` enabled | Write before the press: `writeUnseen(directory, FILES.constants.file, changed)`, `changed` being the file with "sample slots" made "sample cells" (same length; throw if unchanged), as `shared.spec.ts`'s constant-save stale journey does. Press "Apply to 1 file". `form.getByRole("status")` has text `STALE`, "A file changed on disk, so nothing was written. The page now shows the files as they are." (`refusalOf`, `UnitPanel.tsx`, through `SharedAdd`'s `onError`). While it stands, `form.getByRole("button", { name: /^Apply to/ })` count 0 (`SharedAddView`: the plan and its Apply are drawn only under no refusal). Nothing written: the file reads `changed` exactly, with no SPARE. Title: "the add form's apply that is out of date is refused, and nothing is written". | `SharedPage.tsx`'s `SharedAdd` `onError` made a no-op: no status; dies at the sentence. Server, kept beside it (scratch worktree): `editing.py`'s fingerprint check removed: SPARE is written; dies at the sentence. |
| **24. Shared files: an Apply the server fails on** | `vocabularyGui`; `openEntry(…, "TREND_SAMPLES")`; region "Value"'s textbox filled "32"; "Changes 1 file: constants.ddd.json" visible; then `const failed = await failing(page, "/api/edit", "http")` | Press the region's "Save". `value.getByRole("status")` has text `` `The change was refused: ${SERVER_FAILED}` `` (`refusalOf` through `ConstantPanel`'s `onError`; drawn by `Outcome`, `ConstantPanelView.tsx`). The plan and its Save stay under it. Nothing written: `entryOf(directory, "constants", "TREND_SAMPLES").value` is 16. `failed()` is exactly 1. Title: "a save the server fails on says so in its words, and nothing is written". | `ConstantPanel.tsx`'s `onError` else-branch `setFailed({ action, message: refusalOf(error) })` removed: dies at the status. |

- [ ] **Step 4: What the survey found, to confirm on the running page:** the add form's out-of-date refusal (the row "the add form's Apply refused as out of date") withdraws its Apply, is let go only on the next edit, and is never cleared by a later revision: P19b-24's rule, which `SharedAdd` shares with `DeclarePanel`. *What was left open*'s P19b-24 entry names `SharedAdd` beside it.
- [ ] **Step 5: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 6: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 7: The gates,** every journey included. Commit.

### Task 7: Files, Findings and Compare

**Model:** sonnet, reviewed on sonnet. The rows are states the three tabs already draw; two show bugs, each contained in one screen.

**Files:**
- Modify: `gui/e2e/files.spec.ts` (the Files rows), `gui/e2e/findings.spec.ts` (the Findings rows), `gui/e2e/compare.spec.ts` (the Compare rows), this plan's *The inventory*
- Modify, for the two bugs (Steps 4 and 5): `gui/src/screens/FindingsPage.tsx` and `gui/src/lib/findings.ts` with its test; `gui/src/screens/CompareView.tsx` and `gui/src/components/FindingPanelView.tsx`; `CHANGELOG.md`
- Modify, for the bug of Step 5b (ruling 18): `gui/src/lib/compare.ts` with its test, and `gui/src/screens/ComparePage.tsx`

**Interfaces:**
- Consumes: `held`, `restamp` (Task 1); `failing`, `SERVER_FAILED`, `copiedGui` (19b); `drift`, `driftDatatypeIn`, `dump`, `unstamp`, `writeUnseen`, `CONTROLLER`, `SENSOR_HUB`, `UNITS` (`gui/e2e/demo.ts`); the fixtures `gui`, `vocabularyGui`. The kept answer (Task 2) changes the Files tab's early return, which the row "reading the project's files" names.

**Read before the rows** (the survey, at `2bc00da`): Constants a row reuses: `files.spec.ts`'s own `PROJECT` (`"project.ddd.json"`), `STALE` ("A file changed on disk, so nothing was written. The page now shows the files as they are.") and `EXTRA` (`"extra.ddd.json"`); `findings.spec.ts`'s own `valueH`; `demo.ts`'s `CONTROLLER`, `SENSOR_HUB`, `UNITS`, `SERVER_FAILED`. A Files cell is read as `row.getByRole("gridcell").nth(i)`: Entry is the row header (`isRowHeader`, `FilesTableView.tsx`), so `nth(0)` is Kind, `nth(1)` State, `nth(2)` Findings, as `skeleton.spec.ts`'s `componentRow` reads the components table.

**The earlier pre-flight** (ruling 18) drafted a journey for each of this task's rows, ran it ten times, and killed it with a named change: `2026-10-21-gui-journeys-remaining-preflight.md`, §A.6 (its Findings rows), §A.7 and §A.8. Before writing a row's journey, read its draft: its setup, the words it read off the page, and the change that killed it. Then write the journey with this plan's helpers.

- [ ] **Step 1: The worked journeys,** the row "New file's and Add's out-of-date refusal, shown in their own panels", appended to `gui/e2e/files.spec.ts`. Its imports become the lines below, merged with the file's own (Task 1 replaced its `utimesSync` with `restamp`); `PROJECT`, `STALE` and `EXTRA` are the file's own constants:

```ts
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { failing, held, restamp, SERVER_FAILED, UNITS, writeUnseen } from "./demo";
import { expect, type Gui, test } from "./fixtures";

/** examples/vocabulary's description as somebody saving it from their editor would change it: a
 * space taken out and a full stop put in, so that it keeps its length and `writeUnseen` can write
 * it where the session's own watcher does not see it - the change "a Remove applied while the
 * description changed on disk…" makes. Throws where the text is not there, so that a journey never
 * writes the file it was given back unchanged and calls that a change. */
function withFullStop(original: string): string {
  const changed = original
    .replace('"name": "PumpDevice"', '"name":"PumpDevice"')
    .replace('names its sizes"', 'names its sizes."');
  if (changed === original) throw new Error(`${PROJECT} no longer reads as this journey expects`);
  return changed;
}

/**
 * New file's out-of-date refusal, in New file's own panel (ruling P19b-27): the Remove journey
 * above pins `useFilesApply`, which all three actions share, but not where New file and Add draw
 * what it refused. Written before the press (spec 2026-10-21 §3): the description changes once the
 * panel has drawn its plan, where the watcher does not see it, so no revision comes to take the
 * plan away, and the Apply carries a fingerprint the server no longer finds.
 */
test("a New file applied while the description changed on disk is refused in its own panel, and goes through once the analysis has caught up", async ({
  page,
  vocabularyGui,
}) => {
  const project = join(vocabularyGui.directory, PROJECT);
  const spare = join(vocabularyGui.directory, "spare.ddd.json");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "New file", exact: true }).click();
  const creating = page.getByRole("complementary", { name: "New file" });
  const kind = creating.getByRole("combobox", { name: "Kind" });
  await kind.fill("types");
  await kind.press("Enter");
  await creating.getByRole("textbox", { name: "File name" }).fill("spare");
  // The plan drawn: both files it writes, sorted by path as `create_plan` sorts them.
  await expect(
    creating.getByText("Changes 2 files: project.ddd.json, spare.ddd.json", { exact: true }),
  ).toBeVisible();

  const changed = withFullStop(readFileSync(project, "utf8"));
  writeUnseen(vocabularyGui.directory, PROJECT, changed);
  const apply = creating.getByRole("button", { name: "Apply to 2 files" });
  await apply.click();

  // Refused in the panel the reader pressed in, in the tab's own words (`refusalOf`,
  // UnitPanel.tsx), and nothing written: no new file, and the description as the outside change
  // left it.
  const refused = creating.getByRole("status");
  await expect(refused).toHaveText(STALE);
  expect(existsSync(spare)).toBe(false);
  expect(readFileSync(project, "utf8")).toBe(changed);

  // Held until the analysis has moved past the revision it was refused at (`refusalShown`,
  // lib/refusals.ts). A stamp moved and no byte changed is what the watcher sees: the next
  // revision reads the description as it now is, and in the render it lands the refusal goes and
  // the plan is asked again under it - so the button pressed next is that revision's, carrying the
  // fingerprint that lets the same press go through.
  restamp(vocabularyGui.directory, PROJECT);
  await expect(refused).toHaveCount(0);
  await apply.click();
  await expect(page.getByRole("row", { name: "spare.ddd.json", exact: true })).toBeVisible();
  expect(JSON.parse(readFileSync(spare, "utf8"))).toEqual({ types: [] });
  const written = JSON.parse(readFileSync(project, "utf8")).project;
  expect(written.includes).toEqual([
    "units.ddd.json",
    "sections.ddd.json",
    "constants.ddd.json",
    "rasters.ddd.json",
    "pump.ddd.json",
    "spare.ddd.json",
  ]);
  expect(written.description).toMatch(/names its sizes\.$/);
});

/**
 * Add's out-of-date refusal, in Add's own panel: the same refusal New file's journey above meets,
 * reached the same way. Asked again after it (`onSettled`), Add's plan is itself refused as out
 * of date - it judges the change against the revision (`_judged`, api.py) - so the panel's
 * sentence is the Apply's, which takes precedence (`refusalShown`), and no button is offered.
 */
test("an Add applied while the description changed on disk is refused in its own panel, and nothing is written", async ({
  page,
  vocabularyGui,
}) => {
  // A component the project does not include yet, declaring nothing, so the plan brings no error
  // and its preview is the plain one.
  writeFileSync(
    join(vocabularyGui.directory, EXTRA),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );
  const project = join(vocabularyGui.directory, PROJECT);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "Add a file", exact: true }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  await adding.getByRole("textbox", { name: "Path" }).fill(EXTRA);
  await expect(
    adding.getByText("Changes 1 file: project.ddd.json", { exact: true }),
  ).toBeVisible();

  const changed = withFullStop(readFileSync(project, "utf8"));
  writeUnseen(vocabularyGui.directory, PROJECT, changed);
  await adding.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect(adding.getByRole("status")).toHaveText(STALE);
  expect(readFileSync(project, "utf8")).toBe(changed);
  expect(JSON.parse(changed).project.includes).not.toContain(EXTRA);
});
```

- [ ] **Step 2: Run them** after a build, with `--repeat-each=10`. Ablate, in a scratch copy of the package, `FilesPage.tsx`'s `useFilesApply` to answer `refusal: refusalShown(null, refused, shown.refusal, revision)`: both die at `toHaveText(STALE)` (New file draws no status, or its plan's own refusal; Add draws its plan's own stale sentence, "project.ddd.json changed since the project was analysed, so the change cannot be judged until the project is analysed again"). Twins, one per panel: `NewFile`'s `offer={{ plan: offerPlan, refusal: null }}` kills the first alone, `AddFile`'s the second.
- [ ] **Step 3: The other rows,** each a journey of its own, run with `--repeat-each=10` and ablated as its row says. The rows "a finding about the whole delivery" and "a finding's panel closed" may share one journey, the reason first and then Close, each row's ablation killing its own assertion. Two functions are local to their spec files, not `demo.ts` helpers: `withFullStop` (above; `files.spec.ts`'s "a Remove applied while the description changed on disk…" makes the same change inline, and takes it from here) and `comparesAsked` in `compare.spec.ts`, a `page.on("request")` counter of `/api/compare` shaped like `files.spec.ts`'s `plansAsked`. The rows, as read at `2bc00da`:

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **1. Files: reading the project's files** | `vocabularyGui`. After `goto`, wait for the link `{ name: "Files", exact: true }` to be visible, then `const release = await held(page, "/api/files")`, released in a `finally`. Nothing asks `/api/files` before the tab opens: `FilesPage` is `getFiles`' one caller (`api/client.ts`). | Press the link "Files". While the list is held: `getByText("Reading the project's files…", { exact: true })` is visible (`FilesPage.tsx`, `FilesPage`'s early return while it has no answer and no error; after Task 2 the same paragraph sits in the `answer === undefined` branch). The buttons "New file" and "Add a file" and the grid `{ name: "Files" }` have `toHaveCount(0)`. After release: the row `{ name: "units.ddd.json", exact: true }` is visible, and the sentence has `toHaveCount(0)`. | `FilesPage.tsx`'s loading paragraph emptied (`<p className="quiet" />`): dies at the sentence. |
| **2. Files: a New file of a vocabulary's own kind: types, units, constants, sections or rasters** | `vocabularyGui`, the Files tab. One journey walks the five kinds in turn: `types`, `units`, `constants`, `sections`, `rasters`, each named `spare_<kind>`, so that every name sorts after `project`. | For each kind: press "New file". In `complementary` "New file", press `{ name: "Show the choices for Kind" }` (`ComboBox.tsx`'s ▾). The first time only, `page.getByRole("listbox").getByRole("option")` has `toHaveText(["component", "types", "units", "constants", "sections", "rasters"])`: the server's `CREATABLE` (`file_plans.py`), through `FilesReply.creatable`. Pick `getByRole("option", { name: kind, exact: true })` (`onPick` to `onKindPicked`), then fill the textbox "File name". The panel reads "Changes 2 files: project.ddd.json, spare_<kind>.ddd.json" (`consequence`, `lib/units.ts`; `create_plan` sorts its edits by path). It offers "Apply to 2 files" (`applyOf`, `lib/files.ts`), and the textbox "Component name" has `toHaveCount(0)` (`asksComponentName`, `lib/files.ts`, drawn by `NewFileView`). Press Apply. The panel goes. The Kind cell of row `{ name: "spare_<kind>.ddd.json", exact: true }` reads `<kind>`: it comes from `State.files`, `kind_of` in session.py, so it also waits out the edit's analysis before the next kind. On disk the new file parses `toEqual({ [kind]: [] })` (`_content`, `file_plans.py`). `units` is listed empty too, because the copy has a units file already (`checks_units`). | `lib/files.ts`'s `asksComponentName` answering `true`: the field is drawn for `types`, and the journey dies at its `toHaveCount(0)`. |
| **3. Files: New file refused** | `vocabularyGui`, the Files tab, "New file". Each kind is committed with `fill` then `press("Enter")`, as `files.spec.ts:14` commits `component`. Enter closes the list. While open, the list hides the rest of the page from the accessibility tree (`ComboBox.tsx`'s doc), and a `status` would not be found. | In `complementary` "New file", each refusal is the panel's `status` (`Preview`, `FileActionsView.tsx`; the plan's own refusal through `planShown` and `refusalShown`), with no button `/^Apply/` (`toHaveCount(0)`). The sentences come from `create_plan` and `_component_name` (`file_plans.py`): (a) File name "spare", Kind "widgets": "no file of kind 'widgets' can be created here; the kinds that can are component, types, units, constants, sections and rasters". (b) Kind "types", File name "spare.types": "'spare.types' cannot name a new file: a name is one or more of the letters a to z and A to Z, the digits 0 to 9, '_' and '-', and .ddd.json is added to it". (c) File name "units": "units.ddd.json is there already, beside project.ddd.json". (d) Kind "component", File name "spare", Component name left empty: "a new component needs a name, besides its file's". `fileCreate` sends `component: ""`, which `CreateFile` reads as none. (e) Component name "Pump": "this project has a component called 'Pump' already" (`pump.ddd.json`'s component). Nothing is written: no `spare.ddd.json` in the copy. | `FilesPage.tsx`'s `NewFile` passing `offer={{ plan: offerPlan, refusal: null }}`: dies at (a). |
| **4. Files: Add a file refused** | `gui`: the demo's `components/*.ddd.json` pattern gives the pattern refusal. The Files tab, "Add a file". | In `complementary` "Add a file", fill the textbox "Path" with each path in turn. Each answer is a `status` with no button `/^Apply/`: (a) "missing.ddd.json": "missing.ddd.json names no file; a file not there yet is created, not added" (`add_plan`, answered 404). (b) "demo.ddd.json": "demo.ddd.json is this project's own description, which it cannot include" (`add_plan`). (c) "components/controller.ddd.json": "components/controller.ddd.json is part of this project already: the pattern 'components/*.ddd.json' brings it in" (`add_plan`). (d) "include/sensor_hub_driver.h": "include/sensor_hub_driver.h is no kind of file a project includes: it cannot be read as json, or its top level holds none of project, component, types, units, sections, constants and rasters" (`_addition`, `api.py`; the list is session.py's `KINDS`). (e) "../outside.ddd.json": `` `../outside.ddd.json lies outside what ddd gui serves, ${root}; start it in a directory holding this file to add it here` `` (`outside_served`, `queries.py`). Here `root` is `gui.directory` with forward slashes, compare.spec.ts's `posixOf`, which spells the session root the same on all three legs. Confinement comes first, so the file need not exist. `demo.ddd.json` is unchanged. | `FilesPage.tsx`'s `AddFile` passing `refusal: null`: dies at (a). |
| **5. Files: New file's and Add's out-of-date refusal, shown in their own panels** | `vocabularyGui`; two journeys, one per panel, both writing before the press. Once the panel shows its plan, `writeUnseen(dir, PROJECT, withFullStop(original))`. `withFullStop` makes the same-length change that `files.spec.ts:354` makes inline, and can be factored out of it. The Add journey first writes `EXTRA` into the copy before `goto`, as `files.spec.ts:14` does. The worked journeys, Step 1. | **New file:** Kind "types" and Enter, File name "spare", then "Changes 2 files: project.ddd.json, spare.ddd.json". Write unseen, press "Apply to 2 files". In `complementary` "New file", the `status` reads `STALE` (`refusalOf`, `UnitPanel.tsx`). `useFilesApply` holds it in `stale` until the revision moves (`refusalShown`, `lib/refusals.ts`). `spare.ddd.json` does not exist, and the description is as written. Then `restamp(dir, PROJECT)`: the status has `toHaveCount(0)`, and the same press goes through. The row "spare.ddd.json" shows, the new file is `{ types: [] }`, and the description keeps its full stop. **Add:** Path `EXTRA`, then "Changes 1 file: project.ddd.json". Write unseen, press "Apply to 1 file". In `complementary` "Add a file", the `status` reads `STALE`, and the description is as written, its includes without `extra.ddd.json`. | `useFilesApply`'s `refusalShown(stale, refused, shown.refusal, revision)` made `refusalShown(null, …)`: both die at `toHaveText(STALE)`. New file then shows no status, or the plan's own refusal. Add shows the plan's own stale refusal, "project.ddd.json changed since the project was analysed, so the change cannot be judged until the project is analysed again" (`_judged`, `api.py`). This also kills `files.spec.ts:354`. Per-panel twins: `NewFile`'s or `AddFile`'s `refusal: null`. |
| **6. Files: an entry whose file did not load** | `copiedGui("vocabulary", broken)`. `broken` sets `.calib`'s alignment to 3 in `sections.ddd.json` with `shared.spec.ts`'s own regex, and throws if the text is not there. The file is still json and still a sections file, so its kind stays. It fails `schema`, one of `LOAD_CHECKS` (`lsp/navigation.py`), so `SourceFile.loaded` is false (`_described`, session.py). | The Files tab. In row `{ name: "sections.ddd.json", exact: true }`, Kind reads "sections" and State reads "did not load" (`stateOf`, `lib/files.ts`, its first line). Findings is the schema error's count; read it off the page. Row `{ name: "units.ddd.json", exact: true }` has State "" for contrast. | `lib/files.ts`'s `stateOf` first line made `if (row.file !== null) return "";`: dies at "did not load". |
| **7. Files: an entry naming no file** | `copiedGui("vocabulary", namingNothing)`. `namingNothing` parses `project.ddd.json`, pushes two entries onto `project.includes`, and writes it back with two-space indent. The entries are a plain path naming no file, `"missing.ddd.json"`, and a pattern matching none, `"drafts/*.ddd.json"`. The loader files `file-not-found` and `include-empty` at the entries (`_read_text`, `_expand`, `loading.py`). The project is then not analysed; the tab still lists every entry. | The Files tab. Rows `{ name: "missing.ddd.json", exact: true }` and `{ name: "drafts/*.ddd.json", exact: true }` each have Kind "" and State "names no file" (`stateOf`: `!names && files.length === 0`). They are the last two row headers, with no child row under the pattern. Each Findings cell is the count at its entry (`at_entry`, `derived.py`); read it off the page. | `stateOf`'s `return "names no file"` made `return ""`: dies at the first State cell. |
| **8. Files: an entry the last analysis did not read** | `gui`. The fixture returns once the demo is analysed. Before `goto`, write `components/extra.ddd.json` plainly (`{"component":{"name":"Extra","interface":[]}}`). No revision comes of it: `Session.poll` stamps only the files a revision read, while `_files` (`api.py`) expands the pattern on disk as it stands (its docstring: "a file appearing where a pattern matches starts no analysis"). | The Files tab. Under "components/*.ddd.json" is the child row `{ name: "components/extra.ddd.json", exact: true }`: Kind "", State "not read by the last analysis" (`stateOf`'s last line: a child whose file `State.files` lacks), Findings "". Then `restamp(gui.directory, CONTROLLER)`: the next analysis expands the pattern again and reads the file. The same row's State reads `""` and its Kind "component". | `stateOf`'s last line made `return ""`: dies at "not read by the last analysis". |
| **9. Files: a pattern entry, the files it matches listed under it** | `gui`: the demo's includes are `components/*.ddd.json` and `subsystems/logging/logging.ddd.json`. | The Files tab. `getByRole("grid", { name: "Files" }).getByRole("rowheader")` has `toHaveText(["components/*.ddd.json", "components/controller.ddd.json", "components/sensor_hub.ddd.json", "components/user_interface.ddd.json", "subsystems/logging/logging.ddd.json"])`. That is the pattern's own row, then its matches in the loader's order (`expand_include` sorts by POSIX spelling), each named relative to the description (`cellsOf`, `relativeToProject`). Each match's row `toHaveClass(/\bchild\b/)` (`FilesTableView.tsx`) and has Kind "component". The pattern's own row is not `child`, and its Kind and State are "" (`stateOf`'s pattern arm). The sub-project's row has Kind "project", and nothing is listed under it. | `lib/files.ts`'s `rowsOf` without its `entry.files.forEach(…)` that pushes the children: dies at the row-header list. Twin: `FilesTableView.tsx`'s `also(row.child ? "child" : "")` made `also("")`: dies at `toHaveClass`. |
| **10. Files: a removal refused for a file only a pattern brings in** | `gui`. | The Files tab: press row `{ name: "components/controller.ddd.json", exact: true }`. The `complementary` of that name opens (its title is the row's Entry, `fileRemoval`). In its region "Remove from the includes", the `status` reads "controller.ddd.json has no entry of its own: the pattern 'components/*.ddd.json' brings it in, and only the whole pattern can be removed" (`remove_plan`, `file_plans.py`, naming `path.name`). The region has no button (`getByRole("button")` `toHaveCount(0)`). `demo.ddd.json` is unchanged. | In a scratch worktree, `file_plans.py`'s `remove_plan` without its `if brought_by is not None:` refusal. The key falls through to `not-found`, "no entry of demo.ddd.json's includes names controller.ddd.json, and none of its patterns matches it", and the journey dies at the whole sentence. Page twin: `rowsOf`'s child `key: path` made `key: entry.key`; the panel is then titled "components/*.ddd.json", and the journey dies at the `complementary`. |
| **11. Files: an Apply the server fails on** | `vocabularyGui`. Press the units row and wait for its Remove plan. Only then `const failed = await failing(page, "/api/edit", "http")`: nothing GETs that path, and a POST is never sent again. P19b-27 reaches the three actions' shared `useFilesApply` by Remove. | Region "Remove from the includes" of `complementary` "units.ddd.json" reads "Changes 1 file: project.ddd.json". Press "Remove from the includes". Its `status` reads "The change was refused: ddd gui failed on this request; the terminal it runs in shows why" (`refusalOf`, `UnitPanel.tsx`, around `SERVER_FAILED`). `useFilesApply`'s `onError` takes the non-stale arm, so the refusal stays until the reader chooses again. Row `{ name: "units.ddd.json", exact: true }` is still visible. The region's "Remove from the includes" is still `toBeEnabled()`: `onSettled` asks for the plan again, and `Preview` draws it under the refusal. `project.ddd.json` is unchanged byte for byte, and `failed()` is 1. | `useFilesApply`'s `onError` other arm `setRefused(refusalOf(error))` made `setRefused(null)`: dies at the status. |
| **12. Findings: a page of findings still being read** | `copiedGui("demo", (d) => { drift(d); })`. The drift is made before the server starts, as `findings.spec.ts:280` does, so the first revision already holds its two findings and no clean window is drawn first (`drawnWindow`). After `goto`, wait for the button `{ name: "Controller", exact: true }`. Then `const release = await held(page, "/api/findings")`, released in a `finally`: the tab's first page is its first ask of that path (`getFindings(pageQuery(page))`). | Press the link `{ name: "Findings", exact: true }`. While held, `getByText("2 findings · 2 errors", { exact: true })` is visible: `findingCounts` of the state's counts (`lib/findings.ts`), which needs no page. In the grid "Findings", `getByRole("row").filter({ hasText: "Reading…" })` has `toHaveCount(2)` (`FindingsTableView.tsx`'s pending row, for a row whose page has not come, `windowRows`, `lib/findingsWindow.ts`). `getByRole("row", { name: /definition-mismatch/ })` has `toHaveCount(0)`. After release, the definition-mismatch rows count 2 and "Reading…" counts 0. | `FindingsTableView.tsx`'s pending row's `Reading…` cell emptied: dies at the count of 2. |
| **13. Findings: a fix's Apply the server fails on** | `gui`. Before `goto`, `unstamp(gui.directory, CONTROLLER, "ValueH")`, as `findings.spec.ts:129` does. `failing(page, "/api/edit", "http")` is registered once "Apply to 1 file" is drawn. | Findings, then press the row "missing-id". In `complementary` "missing-id", press "Give 'ValueH' an id". Its region `{ name: "Give 'ValueH' an id" }` (`FindingPanelView.tsx`'s `section`) shows "Apply to 1 file". Register `failing`, then press Apply. The region's `status` reads "The change was refused: ddd gui failed on this request; the terminal it runs in shows why" (`FindingsPage.tsx`, `apply`'s `onError`, non-stale arm). The region's "Apply to 1 file" has `toHaveCount(0)`: `FindingPanelView` draws the refusal in place of the consequence and actions. The panel stays, with "'ValueH' has no 'id'". `valueH(gui.directory).id` is still undefined, and `failed()` is 1. | `FindingsPage.tsx`'s `onError` other arm made `setRefused(null)`: dies at the status. The journey's second half is Step 4's: the bug it shows. |
| **14. Compare: a baseline asked for with Enter** | `gui`; `dump(gui.directory, "demo.ddd.json", "baseline.json")`. A local `comparesAsked(page)` counts each request whose pathname is `/api/compare`, as `files.spec.ts`'s `plansAsked` counts plans. | The Compare tab. In the textbox "Baseline", fill "   " and press Enter: the button `{ name: "Compare", exact: true }` is `toBeDisabled()` (`CompareView.tsx`: nothing typed but spaces). Fill "baseline.json" and press Enter, with no click. The `status` filtered by "replace the baseline" reads "This project can replace the baseline." (`CompareView.tsx`). The counter then holds exactly one request: the spaces' Enter asked nothing (`props.baseline.trim() !== ""`), and it was pressed before the ask that drew the verdict. | `CompareView.tsx`'s `onKeyDown` removed: dies at the verdict. Twin: its `props.baseline.trim() !== ""` removed; the spaces then ask `""`, and the journey dies at the count. |
| **15. Compare: a finding about the whole delivery, saying why it leads nowhere** | `copiedGui("demo", …)` with `dump(…, "baseline.json")`, then `driftDatatypeIn(directory, SENSOR_HUB, "ValueA", "uint16")`, as `compare.spec.ts:94`. Rows 15 and 17 may share one journey, the reason first and then Close, each row's ablation killing its own assertion. | Compare "baseline.json", then press row `{ name: "changed-interface" }`. `complementary` "changed-interface" holds `getByText("it is about the whole delivery being compared, not a place in one file", { exact: true })` (`compareRouteReason`, `lib/compare.ts`: filed at the candidate's description with an empty pointer). `FindingPanelView` draws the reason only where there is no link, and `panel.getByRole("link")` has `toHaveCount(0)`: the route is null, so `routeLabel` gives none. | `compareRouteReason`'s `if (row.finding.pointer === "")` arm removed: `noRouteReason` answers "demo.ddd.json is a project file, which has no page yet" (`SHOWN` lacks `project`), and the journey dies at the reason. |
| **16. Compare: the baseline's own findings, named as the baseline's and leading nowhere** | `copiedGui("demo", (d) => { drift(d); })`. The baseline is the copy's own `demo.ddd.json`: a project may be compared against itself (`compare.py`'s module docstring). The baseline's analysis files the drift's `definition-mismatch`, prefixed "in the baseline: " (`BASELINE_PREFIX`, `read_baseline`, `deliveries.py`), into `baseline_findings`, which `api.py`'s `_compare` answers with `route: None`. Their files are the open project's own: the case `compareRouteReason` answers first. | Compare "demo.ddd.json". The verdict reads "This project cannot replace the baseline.": the baseline's errors refuse it (`compared`'s `verdict`). The row `getByRole("row", { name: /definition-mismatch/ }).filter({ hasText: "the baseline's controller.ddd.json" })` has a Message cell beginning "in the baseline: 'ValueA' is declared differently by component 'Controller'"; read the whole sentence off the page. Its File cell (`gridcell` `nth(1)`) reads "the baseline's controller.ddd.json" (`fileLabel`, `lib/compare.ts`). Press it. `complementary` "definition-mismatch" holds "it is the baseline's own finding, not a place in your project" (exact) and no link, although controller.ddd.json is a loaded component of the open project. | `compareRouteReason`'s `if (row.fromBaseline)` arm removed: `noRouteReason` answers "there is nothing at that place any more", and the journey dies at the reason. Twin: `fileLabel` answering `name` alone: dies at the File cell. The panel's own label is Step 5's: the bug it shows. |
| **17. Compare: a finding's panel closed** | As row 15. | Press row "changed-interface": `complementary` "changed-interface" is visible. Press its `{ name: "Close changed-interface", exact: true }` (`Panel.tsx`'s `` aria-label={`Close ${title}`} ``). The panel has `toHaveCount(0)`, and the row `toHaveAttribute("aria-selected", "false")`. The verdict and the table are still drawn. Pressed again, the row opens its panel again. | `CompareView.tsx`'s `onClose={() => props.onSelect(undefined)}` made `onClose={() => {}}`: dies at the panel's `toHaveCount(0)`. |

- [ ] **Step 4: A fix the server failed on can be chosen again, red first** (the row "a fix's Apply the server fails on"; planning ruling 15). After the failure, `FindingPanelView` withdraws "Apply to 1 file" while the refusal stands, and `refused` (`FindingsPage.tsx`) is cleared only by `onMutate` and by `select`, another row or Close then the row again; the fix's own button is `onChoose={setChosen}`, which leaves it, though the comment over `refused` says it is "cleared whenever the reader chooses again".
  - The journey's second half, red today: once the refusal shows, `page.unrouteAll({ behavior: "wait" })`, press "Give 'ValueH' an id" twice (off, then on), and expect "Apply to 1 file" visible; pressed, the id is written.
  - The fix: choosing a fix clears a refusal that is not stale, the rule a function in `gui/src/lib/findings.ts` under Vitest, read by `FindingsPage.tsx`'s `onChoose`. A stale refusal still goes with the revision.
  - A CHANGELOG entry under `## Unreleased`.
- [ ] **Step 5: A baseline's finding names its file as the baseline's, red first** (the row "the baseline's own findings…"; planning ruling 16). Opened from a baseline row, the finding panel's meta line and its notes name the file plainly ("controller.ddd.json", `baseName` in `FindingPanelView`), where the row's File cell says "the baseline's controller.ddd.json" (`fileLabel`, `lib/compare.ts`), and `compareRows`' own doc warns that a plain name reads as the reader's own file.
  - Confirm it on the running page. The journey's assertion, red today: the panel's meta reads "the baseline's controller.ddd.json".
  - The fix: `FindingPanelView` takes the file's label as a prop, `CompareView` passes `fileLabel`'s for a baseline row, and the Findings tab passes `baseName` as today. The note's files take the same label.
  - Its Ladle story, if `FindingPanelView` has one for a baseline finding, gains the label, and its reference changes in Docker with `UPDATE=1`.
  - A CHANGELOG entry under `## Unreleased`.
- [ ] **Step 5b: A baseline asked for again is asked, red first** (ruling 18; the drafts are in §A.8 of the companion).
  - **The bug.** Pressing Compare, or Enter, again with the same path sends nothing. `ComparePage.tsx` sets the value it already holds, so the query key `["compare", asked, revision]` does not change, and React Query keeps the cached answer. A refused baseline stays refused after its file is made, and a stale "This project can replace the baseline." stays after the file is written over.
  - **Two journeys, red first:** a baseline refused, then made, is asked for again by the same press; a baseline written over is asked for again, and the verdict follows.
  - **The fix** numbers each ask into the key. Its decision goes in `gui/src/lib/compare.ts` under Vitest: `nextAsk(previous, typed)` answers the typed path trimmed, numbered one more.
  - **Its row,** "a baseline asked for again, its file made or written over since", names the two journeys.
  - **A CHANGELOG entry.**
- [ ] **Step 6: What the survey found, beside the rows:** the row "an entry naming no file" leaves a Remove panel this task does not drive. Its project is not analysed, so removing either entry is allowed with the server's `unjudged` sentence ("not every analysis of this project ran to its end, so what removing missing.ddd.json leaves cannot be judged"). No row names it, and this part adds no row beyond spec §5's and §6's: record it in *What was left open*.
- [ ] **Step 7: Bugs.** Any other a journey finds follows the rule in *Global Constraints*.
- [ ] **Step 8: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 9: The gates,** every journey included, and the screenshots in Docker if Step 5 changed a reference. Commit: one commit per tab's journeys, one per bug fixed.

### Task 8: a component and its values

**Model:** sonnet, reviewed on sonnet. Every row is a state the component page, its two panels or the values grid already draw; rows 2, 19 and 21 need a copy changed before the server starts.

**Files:**
- Modify: `gui/e2e/declarations.spec.ts` (rows 1 to 13), `gui/e2e/values.spec.ts` (rows 14 to 22), this plan's *The inventory*
- Modify, for the bug of Step 6b (ruling 18): `gui/src/ui/ComboBox.tsx`, `gui/src/styles/ui.css`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `held`, `restamp` (Task 1); `failing`, `SERVER_FAILED`, `copiedGui`, `vocabularyGui` (19b); `CONTROLLER`, `SENSOR_HUB`, `USER_INTERFACE`, `PUMP`, `drift`, `driftIn`, `openPanel`, `openValues`, `chooseUnit` (`gui/e2e/demo.ts`); `values.spec.ts`'s own `definitionOf` and `expectRow`. The kept answer (Task 2) on the component page and the values grid: the rows here fail a *first* read, which still shows the error alone, and the row "an object no longer declared…" pins that a refusal is never kept.

**Read before the rows:** what the survey found (read at `7f96986`, whose `gui/` and `src/` are master `2bc00da`'s):

- **Each read a row is about is asked by its own screen alone,** so `held`'s `{ times: 1 }` holds the row's own read:
  - `getFile` (`/api/file`) and `getFindings({ file })` (`/api/findings?file=…`) by `ComponentPage` alone (the Findings tab asks `/api/findings` too, but no row here visits it);
  - `getVariable` (`/api/variable`) by `VariablePanel` alone;
  - `getDeclarable` (`/api/declarable`) by `DeclarePanel` alone;
  - `getValues` (`/api/values`) by `ValuesPage` alone. `/api/value-plan` and `/api/values-plan` are other pathnames, so a string matcher or `failing`'s string never reaches them.
  - `VariablePanel` also reads `/api/units`, and says "Reading {name}…" until both answer (planning ruling 14, not re-flagged).
- **Two reading lines say the same sentence.** `ComponentPage` says "Reading the file…" while its file is read, and `DeclarePanel` says "Reading the file…" while `/api/declarable` is read. Row 10's assertion is scoped to the panel (`complementary` "Add a declaration").
- **The three write paths word an Apply the server fails on through two spellings of one sentence.** `VariablePanel` builds `` `The change was refused: ${error.message}` `` itself, in both its `apply` and its `remove` `onError`; `DeclarePanel` and `ValuesPage` call `refusalOf` (`UnitPanel.tsx`). For `failing`'s `"http"`, all read `` `The change was refused: ${SERVER_FAILED}` ``. The inline copy is part of what *What was left open* already records ("the stale decision is made inline").
- **What stays on screen under a refusal that is not stale** (P19b-24's split, seen again here):
  - `VariablePanelView` draws the key's Apply only when `refusal === null`, and the removal's Remove only when `removal.offer.refusal === null`;
  - `DeclarePanelView` draws its Apply only when `props.refusal === null`;
  - `ValuesGridView` keeps its Apply under the refusal (`plan !== null && plan.changes.length > 0`, whatever `refused` is).
  - Rows 13 and 22 assert what each does today, citing P19b-24.
- **`page.getByRole("status")` is ambiguous on these pages.** `UpdatingStatus` (`ui/UpdatingNote.tsx`) is an always-present `role="status"` in the component's and the grid's heading, and a warning `Banner` is a status too. Scope each refusal to its region or panel: "Settle the key", "Remove the declaration", "Set the cell", or `complementary` "Add a declaration". An error `Banner` is `role="alert"`, and is the only alert on each of these pages.
- **A panel is `<aside aria-label={title}>` with an `h2` title** (`ui/Panel.tsx`). So `getByRole("complementary", { name, exact: true })` finds it, and `getByRole("heading", { name })` inside it finds its title.
- **The two ways a finding leads somewhere differ.**
  - The component page's own list opens a variable of the same file in place (`followVariable`).
  - A variable's panel draws a finding whose route names something else as a plain `<a href>` (`VariablePanelView`, `namesThisVariable` and `routeHref` in `lib/findings.ts`), so following it loads the document again. The tab's token is in local storage, so the new document is signed in.
- **A file that did not load has no routes.** `route_of` (`finding_routes.py`) answers `None` when `loaded` is false, and `schema` is one of `LOAD_CHECKS` (`lsp/navigation.py`). So a schema-broken file's findings are drawn as text, and the canvas draws its module as "Controller (not loaded)" (Task 4's row). Row 2 reaches the page through the Table tab, whose button reads the raw file's name (`_name_in`, `session.py`).
- **The values page has three states besides the grid:**
  - the read refused or failed (`ValuesPage`'s `values.isError` branch): the heading, "Back to {backTo}", and the error banner;
  - no cell (`!drawable(reply) && reply.stated !== "text"`): the heading, the way back, and "'{name}' has no cell for a value to sit in";
  - text (`ValuesGridView`, `reply.stated === "text"`): the heading, the meta line, and "'{name}' is initialised with text, not with a grid", with no toggle and no grid.
  - A grid that can be drawn says beneath it "Nothing is stated." (`stated === "none"`), "Stated once, for every cell." (`stated === "scalar"`) or `readOnlyNote`'s sentence (`file === null`, `lib/objectValues.ts`).
- **examples/demo already has two of these states.**
  - **Text:** StateName is produced by Controller (`"init": "OFF"`, string conversion, `dimensions: [16]`) and read by UserInterface, which states no init. Controller's own row offers no Shape button, because `ComponentPage`'s `offered` refuses a text init in the same file. UserInterface's row offers one.
  - **Stated once:** UserInterface's CurveB states `"init": 200`. SensorHub's ValueB states `"init": 0`, which `values.spec.ts:186` opens without asserting it.
  - Nothing in the demo is shaped and states nothing, is produced by nobody, or is produced twice. Rows 19 and 21 change a copy.
- **A failed read of a new revision dropped the component page and the grid** (P19b-20's pattern). Task 2 now keeps their answer over a failed read and never over a refusal (planning ruling 17). Rows 4, 7, 11 and 15 fail the *first* read, which still shows the error alone.
- **`values.spec.ts`'s comment above "a pasted curve replaces every value in one edit"** (lines 352 to 362 at `2bc00da`) says no cell Apply can fail non-stale without "a mechanism of its own". Row 22's journey is that mechanism (`failing` on `/api/edit`). Rewrite the comment to name the journey, or remove it.

**The earlier pre-flight** (ruling 18) drafted a journey for each of this task's rows, ran it ten times, and killed it with a named change: `2026-10-21-gui-journeys-remaining-preflight.md`, §A.9 and §A.10. Before writing a row's journey, read its draft: its setup, the words it read off the page, and the change that killed it. Then write the journey with this plan's helpers.

- [ ] **Step 1: The worked journey,** the row "an object no longer declared, its page saying so, with the way back", in `gui/e2e/values.spec.ts`. Add `writeFileSync` to its `node:fs` import; Task 1 has already replaced its `utimesSync` with `restamp`, and `CONTROLLER` and `openValues` are already in its `./demo` import:

```ts
// An object renamed from outside while its grid is open: the grid's next read, keyed by the new
// revision, asks the server for a name the project no longer has. The page keeps what the reader
// opened - its heading - and says why there is nothing under it, with the way back that the
// heading row always carries (spec 5.4: every refusal keeps the heading and the way back).
test("an object renamed under its open grid is said to be declared no longer, with the way back to its component", async ({
  page,
  gui,
}) => {
  await openValues(page, gui.address, "CurveA");
  const grid = page.getByRole("grid", { name: "Values of CurveA" });
  await expect(grid.getByRole("rowheader")).toHaveText(["CurveA (ms)"]);

  // Written plainly, so that the watcher sees it, under a name of another length: the size moves
  // as well as the stamp (`stamped`, session.py). Nothing else in examples/demo names CurveA, so
  // the project still loads clean and the rename is the only change the next revision brings.
  const path = join(gui.directory, CONTROLLER);
  const text = readFileSync(path, "utf8");
  const renamed = text.replace('"name": "CurveA"', '"name": "CurveGone"');
  if (renamed === text) throw new Error(`${CONTROLLER} names no CurveA`);
  writeFileSync(path, renamed, "utf8");

  // The server's own refusal, in its words (`grid_of`, object_values.py, answered 404 by
  // `Api._values`): the one alert on the page, under the heading the reader opened, with the grid
  // gone - there is nothing left to draw it from.
  await expect(page.getByRole("alert")).toHaveText("the project declares no 'CurveA'");
  await expect(page.getByRole("heading", { name: "CurveA", level: 1, exact: true })).toBeVisible();
  await expect(grid).toHaveCount(0);

  // The way back names the component the grid was opened from - read from the state's own list of
  // files, not from the object, which is gone - and leads to it, where the renamed declaration is.
  await page.getByRole("button", { name: "Back to Controller", exact: true }).click();
  await expect(page).toHaveURL(/\/component\?file=[^&]+$/);
  await expect(page.getByRole("heading", { name: "Controller", level: 1, exact: true })).toBeVisible();
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});
```

- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Three ablations:
  - **Server, in a scratch worktree:** `object_values.py`'s `grid_of` without its `if resolved is None: raise ValueRefusalError("not-found", …)`. The server answers its 500, the alert reads `SERVER_FAILED`, and the journey must die at the alert's `toHaveText`.
  - **Page, in a scratch copy of the package:** the error branch's `<Button variant="link" onPress={onBack}>Back to {backTo}</Button>` removed from `ValuesPage.tsx`: it must die at "Back to Controller" (`values.spec.ts`'s "a shape deeper than a grid…" dies too).
  - **Page:** Task 2's `shown` without its `refusedRead` check: the old grid is kept under the refusal, and it must die at `expect(grid).toHaveCount(0)`.
- [ ] **Step 3: The other rows,** each a journey of its own, run with `--repeat-each=10` and ablated as its row says. The row "a key's Apply, a removal or a declaration the server fails on" is three journeys, one per action, since each has its own `onError`; "a grid nothing produces, or more than one place does" is two, one per sentence of `readOnlyNote`. The rows, as read at `2bc00da`:

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **1. A component: reading its file** | `gui`; the canvas drawn (button "Controller", `exact: true`, visible); then `const release = await held(page, "/api/file")` | Press "Controller". While held (`try`): `page.getByText("Reading the file…", { exact: true })` visible (`ComponentPage`'s first early return, `content.isPending`); `page.getByRole("grid")` count 0. Released (`finally`): heading "Controller" (level 1) and grid "Declarations of Controller" visible; the reading line count 0. File `declarations.spec.ts`. Title: "a component's page says it is reading its file until it is read". | `ComponentPage.tsx`'s `if (content.isPending) return <p className="quiet">Reading the file…</p>;` made `return null`: dies at "Reading the file…". |
| **2. A component: a component file that parses but breaks its schema, drawn as the page draws any file** | `copiedGui("demo", (d) => namelessValueA(d))`, the spec-local helper below the table: Controller's line `"name": "ValueA",` taken out before the server starts. The file is still json, but a definition with no `name` breaks the component schema: one `schema` finding at `component.interface[0].definition.name` (`_report_validation_error`, `loading.py`). Controller is listed `loaded: false`. | Reach the page through the Table tab (the canvas draws "Controller (not loaded)", Task 4's row): link "Table" (`exact: true`), then button "Controller" (`exact: true`). The file is drawn as any file is: `Session.read_file` parses it and checks no schema; `FileContent.data` is `Any` (`contract.py`); P19b-27. Heading "Controller" (level 1); grid "Declarations of Controller"; the nameless declaration named by its place, `page.getByRole("rowheader", { name: "declaration 1", exact: true })` (`ComponentPage`'s `rows`, `` `declaration ${index + 1}` ``). Its row (`getByRole("row", { name: /declaration 1/ })`) contains "input" and the chip "schema" (`findingsByRow`). Under heading "Findings in this component", the one list item (filter `hasText: "schema"`) has text "schema Field required": pydantic's words for a missing key, with no "(got: …)" since its type is `missing`; read it off the page. It is text: `page.getByRole("listitem").filter({ hasText: "schema" }).getByRole("link")` count 0 (`route_of` answers nothing for a file that did not load). `page.getByRole("alert")` count 0. Title: "a component file that breaks its schema is drawn as any file is, its nameless declaration named by its place". | `ComponentPage.tsx`'s row name `` text("definition.name") ?? `declaration ${index + 1}` `` made `?? ""`: the row header is empty; dies at rowheader "declaration 1". |
| **3. A component: reading its findings** | `gui`; the canvas drawn; `held(page, (url) => url.pathname === "/api/findings" && url.searchParams.has("file"))` | Press "Controller". The file is not held: heading "Controller" and the grid are drawn, and heading "Findings in this component" (level 2) is visible. While held: `page.getByText("Reading the findings…", { exact: true })` visible (`ComponentPage`, `listed.isPending`); `page.getByText("None.", { exact: true })` count 0. Released: "None." visible (examples/demo has no finding); the reading line count 0. Title: "a component's page says it is reading its findings until they are read". | `ComponentPage.tsx`'s `{listed.isPending && <p className="quiet">Reading the findings…</p>}` removed: dies at "Reading the findings…". |
| **4. A component: its findings failing to load** | `gui`; `const failed = await failing(page, "/api/findings", "http")` before `goto` (nothing on the way to Controller asks for findings) | Press "Controller". Grid "Declarations of Controller" visible (the file reads). `page.getByRole("alert")` has text `SERVER_FAILED` (`ComponentPage`'s `{listed.isError && <Banner tone="error">…}` under "Findings in this component"). "None." and "Reading the findings…" count 0. `failed()` ≥ 1. Title: "a component's findings failing to load leave the server's own error under its table". | `ComponentPage.tsx`'s `{listed.isError && <Banner tone="error">{listed.error.message}</Banner>}` removed: the list says nothing at all; dies at the alert. |
| **5. A component: no finding in it** | `gui` | Press "Controller". Under "Findings in this component": `page.getByText("None.", { exact: true })` visible (`ComponentPage`, `listed.isSuccess && findings.length === 0`). Then `drift(gui.directory)`, written plainly so the watcher sees it. The link "'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (unit: 'rpm' != '%')" (`exact: true`, as `declarations.spec.ts`'s in-place journey reads it) is visible, and "None." count 0. Title: "a component with no finding says None., until one comes". | `ComponentPage.tsx`'s `{listed.isSuccess && findings.length === 0 && <p className="quiet">None.</p>}` removed: dies at "None.". Kept beside it: `findings.length === 0` dropped from that condition dies at "None." count 0 after the drift. |
| **6. A component: a variable's panel reading the variable** | `gui`; Controller's page, grid drawn; `held(page, (url) => url.pathname === "/api/variable" && url.searchParams.get("name") === "ValueB")` | Press the row `/ValueB/`. While held: `complementary` "ValueB" (`exact: true`) shows `getByText("Reading ValueB…", { exact: true })` (`VariablePanel`'s last early return, `reply === undefined`); region "Remove the declaration" count 0 in it. Released: "Select a key to settle it on every declaration." (`VariablePanelView`; no key of ValueB disagrees, and a row's press asks no focus) and "Removes ValueB from Controller; UserInterface still reads it." (`removalSentence`, `lib/declarations.ts`) visible; the reading line count 0. Title: "a variable's panel says it is reading the variable until it is read". | `VariablePanel.tsx`'s reading branch (`<Panel …><p className="quiet">Reading {name}…</p></Panel>`) made `return null`: dies at "Reading ValueB…". |
| **7. A component: a variable's panel failing to read the variable** | `gui`; `failing(page, "/api/variable", "http")` before `goto` (the pathname is exact: `/api/declaration-plan`, `/api/settle` and `/api/units` go through) | Controller, then the row `/ValueB/`. In `complementary` "ValueB": heading "ValueB" (`Panel`'s `h2`). `panel.getByRole("alert")` has text `SERVER_FAILED` (`VariablePanel`'s `answer.shown === "refusal"` branch; `panelShows`, `lib/refusals.ts`: the code is not `unreadable`). "Select a key…" and region "Remove the declaration" count 0. The table stays: rowheader "ValueB" (`exact: true`) visible. The page's warning "ValueB is no longer declared in the open project." count 0: the code is `internal`, not `not-found`, so `undeclared` stays false. Title: "a variable's panel whose variable fails to load says why, beside the table". | `VariablePanel.tsx`'s `if (answer.shown === "refusal")` branch removed: the panel says "Reading ValueB…" for good; dies at the alert. |
| **8. A component: a finding in a variable's panel, followed to what it names** | `copiedGui("vocabulary", (d) => { driftIn(d, PUMP, "PumpSpeed", "RPM"); })`, before the server starts, so the first analysis files `unknown-unit` at PumpSpeed's own `unit` | `openPanel(page, gui.address, "PumpSpeed", "Pump")`. In `complementary` "PumpSpeed" (`exact: true`), the list item with chip "unknown-unit" (`getByRole("listitem").filter({ hasText: "unknown-unit" })`) holds the link "'RPM' is not a unit this project declares - did you mean 'rpm'?" (`exact: true`; `_check_units`, analysis.py; read off the page). The route is the unit's: `route_of` tries `UNIT_CHECKS` before `WITHIN_DECLARATION`, so `namesThisVariable` is false and `VariablePanelView` draws an `<a href>`. Press it. The address matches `/\/project\?view=units&unit=RPM$/` (a document load). `complementary` "RPM" (`exact: true`) shows "not in the vocabulary · stated in 1 place, 1 file" (`unitMeta`, `lib/projectUnits.ts`, as `project-units.spec.ts`'s rename journey reads it); its row "PumpSpeed" visible (read its name off the page). Title: "a finding in a variable's panel leads to the unit it names, on the Units tab". | `VariablePanelView.tsx`'s `const href = namesThisVariable(finding, variable.name) ? null : routeHref(finding);` made `const href = null;`: the finding is text; dies at the link. Server, kept beside it (scratch worktree): `finding_routes.py`'s `UNIT_CHECKS` arm moved below the `WITHIN_DECLARATION` arm, so the finding routes to PumpSpeed itself and stays text; dies at the link. |
| **9. A component: a unit outside the project's vocabulary, said to be** | `vocabularyGui` | `openPanel(page, vocabularyGui.address, "PumpSpeed", "Pump")`: the unit cell opens the panel on its Unit row with the field focused. Combobox "Unit of PumpSpeed" has value "rpm"; `panel.getByText("Not one of this project's units", { exact: true })` count 0 (units.ddd.json lists rpm). Fill "RPM", press Enter (`enteredUnit` takes text no list holds). The field reads "RPM"; the note "Not one of this project's units" is visible (`VariablePanel`'s `note`: `selected === "unit"` and `outsideVocabulary`, `lib/units.ts`; drawn by `ComboBox` as the field's description, so also `expect(picker).toHaveAccessibleDescription(…)`); "Changes 1 file: pump.ddd.json" visible (said, not refused). Fill "kPa", press Enter: the note count 0. Nothing applied: pump.ddd.json byte-equal. Title: "a unit outside the project's vocabulary is said to be, and still offered". | `VariablePanel.tsx`'s note arm `? "Not one of this project's units" : undefined` made `? undefined : undefined`: dies at the note. |
| **10. A component: the add panel reading what may be declared** | `gui`; Controller's page drawn; `held(page, "/api/declarable")` | Press "Add a declaration". While held: `complementary` "Add a declaration" shows `getByText("Reading the file…", { exact: true })` (`DeclarePanel`'s second early return, `declarable.data === undefined`; scoped to the panel, since the page's own reading line is the same sentence); combobox "Name" count 0. Released: combobox "Name" and "Choose a variable, or type a new name." (`declareSentence`, `lib/declarations.ts`) visible; the panel's reading line count 0. Title: "the add panel says it is reading what may be declared until it is read". | `DeclarePanel.tsx`'s `if (declarable.data === undefined)` branch made `return null`: dies at the panel's "Reading the file…". |
| **11. A component: the add panel failing to read it** | `gui`; `failing(page, "/api/declarable", "http")` before `goto` | Controller, then "Add a declaration". In `complementary` "Add a declaration": `panel.getByRole("alert")` has text `SERVER_FAILED` (`DeclarePanel`'s `declarable.isError` branch); combobox "Name" count 0; button "Close Add a declaration" visible. Grid "Declarations of Controller" stays. Title: "the add panel whose choices fail to load says why, and offers nothing to fill". | `DeclarePanel.tsx`'s `if (declarable.isError)` branch removed: "Reading the file…" for good; dies at the alert. |
| **12. A component: a dimension picked from the project's constants** | `vocabularyGui`. The demo declares no constant. `DeclarableReply.constants` is `sorted(built.constants)` (`Api._declarable`): PRESSURE_CELLS, inline in pump.ddd.json, and TREND_SAMPLES, in constants.ddd.json. | Button "Pump" (`exact: true`), "Add a declaration". Name "TrendB", Enter; Kind "value_block", Enter. Press "Show the choices for Dimension 1 of TrendB" (`ComboBox`'s ▾). Options "PRESSURE_CELLS" and "TREND_SAMPLES" (`exact: true`) visible; the list is a popover at the page's root, under "This project's constants" (`DimensionsField`). Press "TREND_SAMPLES": combobox "Dimension 1 of TrendB" has value "TREND_SAMPLES". Volatile "false", Enter; Datatype "uint16", Enter. Press "Apply to 1 file": `complementary` "TrendB" visible. Poll pump.ddd.json `toContain('"dimensions": ["TREND_SAMPLES"]')` (`dimensionsRaw` keeps a name as a string). Title: "a value block's dimension is picked from the project's constants". | `DeclarePanelView.tsx`'s `constants={reply.constants}` made `constants={[]}`: the list has no entry; dies at the option "TREND_SAMPLES". |
| **13. A component: a key's Apply, a removal or a declaration the server fails on**, (a) a key's Apply. One journey per action: each has its own `onError` (`VariablePanel`'s `apply`, `VariablePanel`'s `remove`, `DeclarePanel`'s `apply`). | `gui`; `const panel = await openPanel(page, gui.address, "ValueA")`; `chooseUnit(page, "rpm")`; "Changes 2 files: controller.ddd.json, sensor_hub.ddd.json" visible; both files' bytes read; then `const failed = await failing(page, "/api/edit", "http")` | Press "Apply to 2 files". In `panel.getByRole("region", { name: "Settle the key" })`, `getByRole("status")` has text `` `The change was refused: ${SERVER_FAILED}` `` (`VariablePanel`'s `apply` `onError` else-branch). `getByRole("button", { name: /^Apply to/ })` count 0 in the region (P19b-24). Combobox "Unit of ValueA" still reads "rpm". Both files byte-equal; `failed()` is exactly 1 (a POST is never resent). Title: "a key's apply the server fails on says so in its words, and nothing is written". | `VariablePanel.tsx`'s `apply` `onError` else-branch `setRefused(…)` removed: dies at the status. |
| **13. A component: a key's Apply, a removal or a declaration the server fails on**, (b) a removal | `gui`; Controller, row `/ValueB/`; `const removing = panel.getByRole("region", { name: "Remove the declaration" })`; its "Remove from Controller" enabled; Controller's bytes read; then `failing(page, "/api/edit", "http")` | Press "Remove from Controller". `removing.getByRole("status")` has text `` `The change was refused: ${SERVER_FAILED}` `` (`VariablePanel`'s `remove` `onError` else-branch). "Remove from Controller" count 0 (P19b-24). Rowheader "ValueB" (`exact: true`) still drawn. Controller byte-equal; `failed()` exactly 1. Title: "a removal the server fails on says so in its words, and the declaration stays". | `VariablePanel.tsx`'s `remove` `onError` else-branch `setRemovalRefused(…)` removed: dies at the status. |
| **13. A component: a key's Apply, a removal or a declaration the server fails on**, (c) a declaration | `gui`; Controller, "Add a declaration"; `adding` = `complementary` "Add a declaration"; Name "ValueC", Enter; "Reads ValueC as SensorHub declares it." visible; "Apply to 1 file" enabled; Controller's bytes read; then `failing(page, "/api/edit", "http")` | Press "Apply to 1 file". `adding.getByRole("status")` has text `` `The change was refused: ${SERVER_FAILED}` `` (`refusalOf`, `UnitPanel.tsx`, through `DeclarePanel`'s `onError`). `adding.getByRole("button", { name: /^Apply to/ })` count 0 (withdrawn until the next edit of the form, P19b-24). Combobox "Name" still "ValueC"; `complementary` "ValueC" count 0 (no `onDeclared`). Controller byte-equal; `failed()` exactly 1. Title: "a declaration the server fails on says so in its words, and nothing is declared". | `DeclarePanel.tsx`'s `onError: (error) => setRefusal(refusalOf(error))` made a no-op: dies at the status. |
| **14. Values: reading the values** | `gui`; `const release = await held(page, "/api/values")` before `openValues` (only `ValuesPage` asks for it) | `openValues(page, gui.address, "CurveA")`. While held: `page.getByText("Reading the values…", { exact: true })` visible (`ValuesPage`'s first early return); heading "CurveA" count 0. Released: grid "Values of CurveA", its rowheaders `["CurveA (ms)"]`; the reading line count 0. File `values.spec.ts`. Title: "the values grid says it is reading the values until they are read". | `ValuesPage.tsx`'s `if (values.isPending) return <p className="quiet">Reading the values…</p>;` made `return null`: dies at "Reading the values…". |
| **15. Values: the values failing to load** | `gui`; `const failed = await failing(page, "/api/values", "http")` before `openValues` | `openValues(page, gui.address, "CurveA")`. Heading "CurveA" (level 1, `exact: true`) and button "Back to Controller" visible. `page.getByRole("alert")` has text `SERVER_FAILED` (`ValuesPage`'s `values.isError` branch). Grid "Values of CurveA" count 0; buttons "Physical" and "Raw" count 0. `failed()` ≥ 1. Title: "the values failing to load leave the server's own error, under the heading and beside the way back". | `ValuesPage.tsx`'s error branch's `<Banner tone="error">{values.error.message}</Banner>` removed: dies at the alert. |
| **16. Values: an object no longer declared, its page saying so, with the way back** | `gui`; `openValues(…, "CurveA")`, grid drawn; then CurveA renamed plainly (seen) to "CurveGone" in Controller's file | The worked journey, Step 1. It also pins that a refusal is never kept (Task 2's `refusedRead`): its grid must be gone. Alert "the project declares no 'CurveA'" (`grid_of`'s not-found refusal, `object_values.py`, answered 404 by `Api._values`); heading "CurveA"; grid count 0. Press "Back to Controller" (`exact: true`): the address matches `/\/component\?file=[^&]+$/`; heading "Controller"; grid "Declarations of Controller"; alert count 0. Title: "an object renamed under its open grid is said to be declared no longer, with the way back to its component". | Server (scratch worktree): `grid_of`'s `if resolved is None: raise ValueRefusalError("not-found", …)` removed. Then `resolved.shape` raises, which the server answers 500 (`_INTERNAL`), and the alert reads `SERVER_FAILED`; dies at the alert's text. Page, kept beside it: the error branch's back button removed; dies at "Back to Controller" (`values.spec.ts:475` dies too). Kept beside them: Task 2's `shown` without its `refusedRead` check keeps the old grid under the refusal; dies at the grid's `toHaveCount(0)`. |
| **17. Values: a declaration with no cell, opened by its address** | `gui`; the canvas drawn; press "Controller"; `await expect(page).toHaveURL(/\/component\?file=[^&]+$/)`; `const component = page.url()` (the file spelt as the page spells it, so `backTo`'s lookup in `state.files` matches) | `page.goto(\`${component}&variable=ValueA&view=values\`)`: the address `hrefOf` writes for a values route (`lib/route.ts`); the tab's token is in local storage. Heading "ValueA" (level 1); `page.getByText("'ValueA' has no cell for a value to sit in", { exact: true })` visible (`ValuesPage`'s `!drawable(reply) && reply.stated !== "text"` branch; the words `set_cell` refuses with). `page.getByRole("grid")` count 0. Press "Back to Controller": heading "Controller", grid "Declarations of Controller". Title: "a shapeless declaration opened by its values address says it has no cell, with the way back". | `ValuesPage.tsx`'s no-cell branch removed: `ValuesGridView` draws a grid of no cell and no sentence; dies at the sentence. |
| **18. Values: an object initialised with text** | `gui` | Press "Controller". Rowheader "StateName" (`exact: true`) visible, and `page.getByRole("button", { name: "Show the values of StateName" })` count 0 (`ComponentPage`'s `offered`: a text init in this very file; its Shape cell reads "16" as text). Then `openValues(page, gui.address, "StateName", "UserInterface")` (offered there: a reader cannot see its producer's init). Heading "StateName" (level 1); `page.getByText("'StateName' is initialised with text, not with a grid", { exact: true })` visible (`ValuesGridView`, `reply.stated === "text"`; `_laid_out`, `object_values.py`). Grid "Values of StateName" count 0; buttons "Physical" and "Raw" count 0; "Back to UserInterface" visible. Title: "an object initialised with text says so on its values page, which only a reader offers". | `ValuesGridView.tsx`'s `reply.stated === "text" ? (<p …>) : (<>…</>)` made to draw its grid branch always: dies at the sentence. |
| **19. Values: a grid that states nothing** | `copiedGui("demo", (d) => stateNothingOfValueB(d))`, spec-local: ValueB's `"init": 0,` taken out of SensorHub, its one producer | `openValues(page, gui.address, "ValueB")` (Controller reads it). Grid "Values of ValueB": `expectRow(grid, ["0", "0", "0", "0"])` (`_filled(0, shape)`); each of "element 1" to "element 4" `toHaveClass("unstated")` (`ValuesGridView`, `stated === "none"`). `page.getByText("Nothing is stated.", { exact: true })` visible. The paste hint "Paste 1 row of 4 values from a spreadsheet to replace them all." visible (`pasteHint`; writable, one producer). Fill "element 2" with "1": "Sets element 2 of ValueB to 1 V" and "Changes 1 file: sensor_hub.ddd.json" visible. Press "Apply to 1 file". Poll `definitionOf(gui.directory, SENSOR_HUB, "ValueB").init` `toEqual([0, 1000, 0, 0])` (`set_cell` writes the whole `init` where none is written). Then "Nothing is stated." count 0. Title: "a grid that states nothing reads zero, greyed, says so, and takes its first values". | `ValuesGridView.tsx`'s `{reply.stated === "none" && <p className="quiet">Nothing is stated.</p>}` removed: dies at "Nothing is stated.". |
| **20. Values: a grid stated once for every cell** | `gui` (UserInterface's CurveB states `"init": 200`) | `openValues(page, gui.address, "CurveB", "UserInterface")`. Grid "Values of CurveB": rowheaders `["CurveB (%)"]`; `expectRow(grid, ["100", "100", "100", "100", "100", "100"])` (200 × 0.5). `page.getByText("Stated once, for every cell.", { exact: true })` visible (`ValuesGridView`, `stated === "scalar"`). Fill "element 3" with "50": "Sets element 3 of CurveB to 50 %" and "Changes 1 file: user_interface.ddd.json". Press "Apply to 1 file". Poll `definitionOf(gui.directory, USER_INTERFACE, "CurveB").init` `toEqual([200, 200, 100, 200, 200, 200])` (`set_cell`'s arm for an init that is no list). Then "Stated once, for every cell." count 0. Title: "a grid stated once for every cell says so, and one cell set writes every value". | `ValuesGridView.tsx`'s `{reply.stated === "scalar" && <p className="quiet">Stated once, for every cell.</p>}` removed: dies at the sentence. |
| **21. Values: a grid nothing produces, or more than one place does, read only**, (a) nothing produces it. Two journeys: `readOnlyNote` (`lib/objectValues.ts`) has a sentence for each cause. | `copiedGui("demo", (d) => producedByNobody(d))`, spec-local: SensorHub's ValueB declaration taken out, the file rewritten whole as `typeCurveA` rewrites one. Controller and UserInterface still read it. It still resolves, with `owner` and `file` null (`test_an_object_nothing_produces_has_no_file_or_pointer`). | `openValues(page, gui.address, "ValueB")`. Grid "Values of ValueB"; `getByRole("textbox", { name: "element 1" })` `toBeDisabled()` (`ValuesGridView`, `disabled` while `reply.file` is null). `page.getByText("nothing produces 'ValueB', so it has no values to set", { exact: true })` visible (`readOnlyNote`'s first sentence, as `set_cell` words it). The paste hint (`getByText(/^Paste /)`) count 0. Title: "a grid nothing produces is read only, and says why". | `ValuesGridView.tsx`'s `{readOnly !== null && <p className="quiet">{readOnly}</p>}` removed: dies at the sentence. |
| **21. Values: a grid nothing produces, or more than one place does, read only**, (b) more than one place | `copiedGui("demo", (d) => producedTwice(d))`, spec-local: UserInterface's ValueB `"scope": "input"` made `"output"`. The regex is anchored on the `"definition": { "name": "ValueB"` that follows it, and throws if nothing matched. SensorHub and UserInterface both produce ValueB: the analysis reads one (`owner` named), `built.producers` holds two, so `file` is null (`test_two_declarations_producing_one_name_leave_the_grid_read_only`). | `openValues(page, gui.address, "ValueB")`. "element 1" `toBeDisabled()`. `page.getByText("'ValueB' is produced in more than one place, so there is no one file to set it in", { exact: true })` visible (`readOnlyNote`'s second sentence). The paste hint count 0. Title: "a grid more than one place produces is read only, and says why". | `lib/objectValues.ts`'s `readOnlyNote` `if (reply.owner === null)` made `if (reply.file === null)`: it says "nothing produces 'ValueB'…"; dies at the sentence. Server, kept beside it (scratch worktree): `grid_of`'s `if len(sites) == 1:` made `if sites:`. A file is answered and the grid is writable; dies at `toBeDisabled`. |
| **22. Values: a cell's Apply the server fails on** | `gui`; `openValues(…, "CurveA")`; "element 3" filled "7.5"; "Sets element 3 of CurveA to 7.5 ms" and "Changes 1 file: controller.ddd.json" visible; Controller's bytes read; then `const failed = await failing(page, "/api/edit", "http")` | Press "Apply to 1 file". `page.getByRole("region", { name: "Set the cell" }).getByRole("status")` has text `` `The change was refused: ${SERVER_FAILED}` `` (`ValuesPage`'s `apply` `onError` else-branch, `refusalOf`). The Apply is still offered and enabled (the grid keeps its Apply, P19b-24). "element 3" still reads "7.5". Controller byte-equal; `failed()` exactly 1. Title: "a cell's apply the server fails on says so in its words, and nothing is written". | `ValuesPage.tsx`'s `onError` else-branch `setFailed(refusalOf(error))` removed: dies at the status. |

  The helpers local to the two spec files, each written whole or by one anchored replace, each throwing when it changed nothing:

  ```ts
  // declarations.spec.ts
  /** ValueA's own `"name"` line taken out of Controller's file, and nothing else: the file still
   * parses, and breaks the component schema, which a definition with no name does (`schema`, filed
   * at `component.interface[0].definition.name`). The first `"name": "ValueA",` of the file is that
   * definition's. */
  function namelessValueA(directory: string): void {
    const path = join(directory, CONTROLLER);
    const text = readFileSync(path, "utf8");
    const changed = text.replace(/\n\s*"name": "ValueA",/, "");
    if (changed === text) throw new Error(`${CONTROLLER} names no ValueA`);
    writeFileSync(path, changed, "utf8");
  }

  // values.spec.ts
  /** ValueB's own `"init": 0,` taken out of SensorHub, the one declaration producing it: a shaped
   * object stating nothing, which the startup code zeroes. */
  function stateNothingOfValueB(directory: string): void {
    const path = join(directory, SENSOR_HUB);
    const text = readFileSync(path, "utf8");
    const changed = text.replace(/("name": "ValueB"[\s\S]*?)\n\s*"init": 0,/, "$1");
    if (changed === text) throw new Error(`${SENSOR_HUB} states no init of ValueB`);
    writeFileSync(path, changed, "utf8");
  }

  /** SensorHub's declaration of ValueB taken out, the file rewritten whole: Controller and
   * UserInterface still read ValueB, and nothing produces it. */
  function producedByNobody(directory: string): void {
    const path = join(directory, SENSOR_HUB);
    const data = JSON.parse(readFileSync(path, "utf8"));
    const kept = data.component.interface.filter(
      (declaration: { definition: { name: string } }) => declaration.definition.name !== "ValueB",
    );
    if (kept.length !== data.component.interface.length - 1) {
      throw new Error(`${SENSOR_HUB} declares ValueB other than once`);
    }
    data.component.interface = kept;
    writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  }

  /** UserInterface's reading of ValueB made a second producing declaration of it, beside
   * SensorHub's. */
  function producedTwice(directory: string): void {
    const path = join(directory, USER_INTERFACE);
    const text = readFileSync(path, "utf8");
    const changed = text.replace(
      /"scope": "input",(\s*"definition": \{\s*"name": "ValueB")/,
      '"scope": "output",$1',
    );
    if (changed === text) throw new Error(`${USER_INTERFACE} reads no ValueB`);
    writeFileSync(path, changed, "utf8");
  }
  ```

- [ ] **Step 4: Read off the running page before asserting them:** the row "a component file that parses but breaks its schema"'s schema message ("Field required" is pydantic's own wording for a missing key); the row "a finding in a variable's panel"'s message, and the name of the unit panel's row for PumpSpeed; the row "a dimension picked from the project's constants"'s consequence sentence, if asserted (a new name's scope defaults to `output`, the first of `SCOPES`); and, for "more than one place", that the analysis still resolves a dictionary on the demo with two producers of ValueB (the python test proves it on a two-file project, not the demo).
- [ ] **Step 5: `values.spec.ts`'s comment** above "a pasted curve replaces every value in one edit" says no cell Apply can fail other than as out of date without a mechanism of its own. The row "a cell's Apply the server fails on" is that mechanism: rewrite the comment to name its journey.
- [ ] **Step 6: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*. Seen again by the survey and already recorded: `VariablePanel.tsx` words its refusal inline (`` `The change was refused: ${error.message}` ``, twice) rather than through `refusalOf`, and the rows "a key's Apply, a removal or a declaration…" and "a cell's Apply…" assert P19b-24's split as it stands (three write paths withdraw their button; the grid keeps its Apply).
- [ ] **Step 6b: A note drawn after its combobox is not its description, red first** (ruling 18; the draft is in §A.9 of the companion).
  - **The bug.** In the row "a unit outside the project's vocabulary, said to be", the field's note ("Not one of this project's units") appears after the field first drew. The combobox then has no `aria-describedby`, so a screen reader does not read the note: `toHaveAccessibleDescription` receives `""`.
  - **The fix,** in `gui/src/ui/ComboBox.tsx`: always render the description slot, and hide an empty one with `.combo-note:empty { display: none; }` in `gui/src/styles/ui.css`. Without that rule every combobox grows 8 px (measured), and the Ladle references move.
  - **Red first:** that row's journey asserts the field's accessible description.
  - **A CHANGELOG entry.**
- [ ] **Step 6c: An oddity to reproduce first.** The earlier pre-flight typed "ValueD" (and "FlagA") into the Add a declaration panel's Name field, and found "Diagnosis" there. Reproduce it on `gui`.
  - If the field does not keep what was typed, it is a bug under the rule in *Global Constraints*.
  - If it does, record the probe in the report.
- [ ] **Step 7: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 8: The gates,** every journey included. Commit: one commit for the component's rows, one for the values'.

### Task 9: the final hunt, the figures, the gate and the close-out

**Model:** the controller's own.

- [ ] **Step 1: The final hunt.** With every task merged into the branch and pushed: `gh workflow run ci.yml --ref feature/gui-journeys-remaining -f repeat=5`. It must be clean on all three legs. A failure is worked at its cause, from its trace (under the leave in *Prerequisites*), and the hunt run again; it is never retried to pass.
- [ ] **Step 2: The final whole-branch review,** on opus, while the hunt runs: the spec, this plan, and the branch's diff from `2bc00da`. One fix wave takes its Important findings and the Minors the controller chooses; a re-review reads the wave. If the wave changes a journey's steps, the hunt runs again after it.
- [ ] **Step 3: The figures,** in *Figures*:
  - the inventory by screen: covered before (at Task 1's close), covered after, with a reason;
  - the journeys' time per leg, before (Task 1's baseline run) and after (the last full run);
  - the full run at the head, every job;
  - the final hunt, every leg.
- [ ] **Step 4: The milestone gate** at the head, below, each exit status captured on its own.
- [ ] **Step 5: The close-out.** *Progress log*, *What was left open* and the rulings taken during execution, filled in; each task's text made true to what was built, its departures as rulings.
- [ ] **Step 6: Commit and push.** The controller asks the maintainer before opening the pull request.

## The inventory

The 88 rows part 19b handed over, with the owner task each now has, and the fourteen rows this part adds (marked *added*). Five come from the spec: two for the page's script (§6), and three for the kept answer on the Files tab, a component's page and the values grid (§5). Nine come from the earlier pre-flight (ruling 18). A row a journey drives names it by `file:line` and title; a row with none names its reason. Every row reads "none yet" until its task fills it in.

Task 1 checked every row at `8366d2a`, whose `gui/` and `src/` are those of `2bc00da`. No journey drives any of them, and every state but Task 2's is drawn where the earlier pre-flight found it. Task 2 owns nine rows: the page's script, and an answer kept under a failed read. No code draws the five the spec adds yet: the page stays blank when its script fails, and a read failing on a new revision drops what the Files tab, a component's page and the values grid drew. The four 19b named, the canvas and the Units, Types and Shared files tables, are kept under a failed read today only when a tab asks again for the answer it holds; a new revision's failed read drops them too. One row's state is reached by a journey in another flavour. The canvas's "the project's graph failing before anything is drawn" is reached with no answer at all by `network.spec.ts`'s "a GET the network fails every time reads as the server not answering", which 19b's inventory counts as *The network*'s "a GET failing every time". The row stays Task 4's, for the server's own sentence, as the earlier pre-flight wrote it.

| Screen | Row | Task | Journey |
| --- | --- | --- | --- |
| The network | the page's script failed once (*added*) | 2 | `network.spec.ts:107`, "the page's script the network failed once is asked for again, and the page is drawn" |
| The network | the page's script failing every time (*added*) | 2 | `network.spec.ts:118`, "the page's script the network fails every time says how to try again" |
| The start page | a project listed with the images its build records name | 3 | `start.spec.ts:230`, "a project is listed with the images its build records name" |
| The start page | a project whose description does not load, listed as an unnamed project | 3 | `start.spec.ts:246`, "a project whose description does not load is listed as an unnamed project" |
| The start page | a project opening, the list's buttons held until it has | 3 | `start.spec.ts:267`, "a project opening holds every button of the list, until the start page goes" |
| The app | signed in by the one-time code `ddd gui` opens its own browser with | 3 | `start.spec.ts:305`, "the address ddd gui opens its own browser with signs the page in by a one-time code, spent once used"; the fixture's own journey is `helpers.spec.ts:251`, "the browser ddd gui opens is handed a one-time sign-in address of its own" |
| The app | connecting, before the session answers | 3 | `start.spec.ts:334`, "the page says it is connecting until the session answers" |
| The app | the session failing | 3 | `start.spec.ts:357`, "the session failing shows the server's own error, and no page" |
| The app | analysing the project, before its first analysis lands | 3 | `start.spec.ts:372`, "a project opened is analysed before its tabs show anything, and the page says so" |
| The app | the server answering again after it stopped | 3 | `start.spec.ts:396`, "a server that answers again after it stopped lifts the banner, and the page follows the project again" |
| The app | nothing written while the server is stopped: every Apply and every write's button disabled | 3 | `start.spec.ts:430`, "a stopped server disables every control that writes, the component table's cells among them": the variable panel's Apply and Remove, the Undo and the component page's three `isDisabled={stopped}` (Add a declaration and the table's two cell buttons). The survey read the same `busy` rule, `stopped` included, in every screen that writes: ComparePage, ConstantPanel, DeclarePanel, FilesPage (three), FindingsPage, RasterPanel, SectionPanel, SharedPage, TypePanel, UndoStrip, UnitPanel, UnitsPage (two), ValuesPage, VariablePanel; the journey drives UndoStrip's and VariablePanel's |
| The app | an entry's panel just after a rename or a declaration, saying the findings are updating until the analysis lands | 3 | `start.spec.ts:474`, "a variable just declared shows its panel saying the findings are updating, until the analysis lands": a declaration on the demo with a slowed analysis (`slowAnalyses`), not on `generatedGui`, where the panel opens after the analysis has landed (measured, six runs) |
| The app | the changes a plan makes, shown and then hidden again | 3 | `start.spec.ts:517`, "the changes a plan makes are shown, and hidden again" |
| The undo strip | the files an undo puts back, being read | 3 | `undo.spec.ts:137`, "the strip says it is reading the files an undo would put back, until it has" |
| The undo strip | an undo the server fails on | 3 | `undo.spec.ts:155`, "an undo the server fails on is refused in the strip, with nothing put back" |
| The undo strip | the files an undo puts back, failing to be read (*added*, pre-flight) | 3 | `undo.spec.ts:180`, "a preview the server fails on is refused in the strip, before any undo was asked" |
| The canvas | the project's graph failing before anything is drawn | 4 | `network.spec.ts:70`, "a GET the network fails every time reads as the server not answering", which already drives it (ruling 12): it fails `/api/graph` every time and reads the canvas's alert in place of the canvas. Without `GraphPage.tsx`'s `if (graph.isError) return <Banner …>` it dies at that alert (read, and run) |
| The canvas | the project's graph failing once drawn, the canvas kept | 2 | `kept.spec.ts:76`, "the graph failing on a new revision keeps the canvas, with the error above it" |
| The canvas | a module whose file does not load, drawn as not loaded | 4 | `canvas.spec.ts:355`, "a module whose file does not load is drawn as not loaded, named by its file" |
| The canvas | a module's badge, counting its errors or its warnings | 4 | `canvas.spec.ts:384`, "a module's badge counts its warnings, and only its errors once it has any": the worked journey, with the earlier pre-flight's second warning (ValueH) before the error, so that its one error stands beside two warnings, and ValueB drifted at its end, so that two errors read 2 (P19c-8) |
| The canvas | an arrow reached by the keyboard, saying what is wrong | 4 | `canvas.spec.ts:432`, "an arrow reached by the keyboard says what is wrong, until the keyboard leaves the arrows": left by Tab past the last arrow, since one more Tab reaches the next arrow, whose own tooltip shows |
| The canvas | zoomed in and out with the canvas's own buttons | 4 | `canvas.spec.ts:476`, "the canvas's own buttons zoom it in and out, and stop zooming out at its least zoom" |
| The canvas | laid out in ranks only, for a project too large for the full layout | 4 | `canvas.spec.ts:508`, "a project too deep for the full layout is laid out in ranks only, and says so": on `chainedGui`, a chain of 2,000 components (*Figures*) |
| The canvas | a later layout failing, the canvas kept | 4 | `canvas.spec.ts:528`, "a layout worker that fails once the canvas is drawn leaves the canvas, with its alert above": reached inside the layout worker (ruling 10) |
| The components table | a row pressed beside its name, or Enter on it, opening its component | 4 | `canvas.spec.ts:571`, "a row of the components table opens its component, pressed beside its name or on Enter" |
| Units | reading the project's units | 5 | `project-units.spec.ts:316`, "the units tab says it is reading the project's units until they are read" |
| Units | the units failing to load | 5 | `project-units.spec.ts:341`, "the units failing to load leave the server's own error, with no table": a first read that fails shows the error alone (Review Focus 4); it also dies when the tab draws an empty table beside the banner |
| Units | the units failing once listed, the table kept | 2 | `kept.spec.ts:29`, "the units failing on a new revision keep the table, with the error above it" |
| Units | a unit's panel reading the unit | 5 | `project-units.spec.ts:359`, "a unit's panel says it is reading the unit until it is read" |
| Units | a unit's panel failing to read the unit | 5 | `project-units.spec.ts:385`, "a unit's panel whose unit fails to load says why, beside the table" |
| Units | a units file listing no unit, the units in use adopted into it | 5 | `project-units.spec.ts:411`, "a units file listing no unit has the units in use adopted into it, and nothing else written": dies under a page that says the project has no units file, and under a server that creates `units.ddd.json` beside the description where it already is |
| Units | a project stating no unit, with nothing to adopt | 5 | `project-units.spec.ts:475`, "a project stating no unit is told there is nothing to adopt, and offered nothing to press": a listener on `/api/unit-plan` is read after the reader has left the tab, since a plan asked for is refused a few tens of milliseconds after the banner's sentence is drawn |
| Units | an Apply the server fails on | 5 | `project-units.spec.ts:512`, "a removal the server fails on says so in its words, and nothing is written": the unit panel keeps its Apply offered after the refusal |
| Units | a rename the plan refuses (*added*, pre-flight) | 5 | `project-units.spec.ts:541`, "a rename the plan refuses says why in the panel, and offers nothing to apply" |
| Units | a unit listed twice, the `duplicate-unit` chip (*added*, pre-flight) | 5 | `project-units.spec.ts:563`, "a unit listed twice is flagged by its chip, and its panel says it is already declared" |
| Types | reading the project's types | 5 | `types.spec.ts:468`, "the types tab says it is reading the project's types until they are read" |
| Types | the types failing to load | 5 | `types.spec.ts:493`, "the types failing to load leave the server's own error, with no table": a first read that fails shows the error alone (Review Focus 4); it also dies when the tab draws an empty table beside the banner |
| Types | the types failing once listed, the table kept | 2 | `kept.spec.ts:46`, "the types failing on a new revision keep the table, with the error above it" |
| Types | a type's panel reading the type | 5 | `types.spec.ts:509`, "a type's panel says it is reading the type until it is read" |
| Types | a type's panel failing to read the type | 5 | `types.spec.ts:537`, "a type's panel whose type fails to load says why, beside the table" |
| Types | the untold banner | 5 | `types.spec.ts:563`, "a types file saved half-written is named above the table, whatever it declared untold" |
| Types | the unreadable banner | 5 | `types.spec.ts:590`, "a types file that parses but breaks its model is named above the table, its types missing" |
| Types | a type's "Where it is used" followed to the declaration | 5 | two journeys, one for each arm of `routeOfUse` (P19c-10): `types.spec.ts:625`, "a type's Where it is used leads to the variable naming it, on its component's page", and `types.spec.ts:651`, "a type's Where it is used leads from a structure's member to the structure holding it", which is the only press of the member arm, in a `.tsx` with no Vitest |
| Types | a structure's member followed to its type | 5 | `types.spec.ts:677`, "a structure's member leads to the panel of the type it names" |
| Types | a finding in a type's panel followed | 5 | `types.spec.ts:698`, "a finding in a type's panel leads to the unit it names, on the Units tab": the worked journey; it dies under a button that follows nothing, and under a server that routes the finding to the type (`UNIT_CHECKS` tried after `WITHIN_TYPE`) |
| Types | an Apply the server fails on | 5 | `types.spec.ts:742`, "an apply made from a type's panel that the server fails on says so in its words, and nothing is written": the type panel withdraws its Apply after the refusal, where the unit panel keeps it |
| Shared files | reading the project's shared files | 6 | `shared.spec.ts:677`, "the shared files tab says it is reading the project's shared files until they are read" |
| Shared files | the shared files failing to load | 6 | `shared.spec.ts:702`, "the shared files failing to load leave the server's own error, with no table and no way to declare": a first read that fails shows the error alone (Review Focus 4); it also dies when the tab draws an empty table beside the banner |
| Shared files | the shared files failing once listed, the table kept | 2 | `kept.spec.ts:61`, "the shared files failing on a new revision keep the table, with the error above it" |
| Shared files | an entry's panel reading the entry | 6 | three journeys, one for each panel, from the one loop over `PANELS` (P19c-10), `shared.spec.ts:754`: "a constant's panel says it is reading the entry until it is read", the worked journey, "a section's panel says it is reading the entry until it is read" and "a raster's panel says it is reading the entry until it is read": each dies under its own panel's reading branch made `return null`, and under no other's |
| Shared files | an entry's panel failing to read the entry | 6 | three journeys, one for each panel, from the one loop over `PANELS` (P19c-10), `shared.spec.ts:788`: "a constant's panel whose entry fails to load says why, beside the table", "a section's panel whose entry fails to load says why, beside the table" and "a raster's panel whose entry fails to load says why, beside the table": each dies under its own panel's refusal branch removed; the constant's branch also kills `shared.spec.ts:480`, "a constant whose file does not load keeps its panel, naming the file, until the file loads again", which reads the same branch |
| Shared files | a constant declared inside a component, its file followed | 6 | `shared.spec.ts:811`, "a constant declared inside a component leads to that component's page, where one in a constants file names its file alone": dies under a Declared in button that follows nothing, and under `declaredInComponent` made `true` (a button for a constants file) or `false` (no button for a component) |
| Shared files | the add form's Apply refused as out of date | 6 | `shared.spec.ts:834`, "the add form's apply that is out of date is refused, and nothing is written": dies under `SharedAdd`'s `onError` made a no-op, under the form drawing its Apply beside the refusal, and under a server that does not check a file's fingerprint, which writes SPARE |
| Shared files | an Apply the server fails on | 6 | three journeys, one for each panel, from the one loop over `SAVES` (P19c-10), `shared.spec.ts:872`: "a save made from a constant's panel that the server fails on says so in its words, and nothing is written", "a save made from a section's panel that the server fails on says so in its words, and nothing is written" and "a save made from a raster's panel that the server fails on says so in its words, and nothing is written": each panel keeps its plan and its Save under the refusal, where the add form withdraws both; each dies under its own panel's `setFailed(…)` removed, and under its own panel's plan withdrawn after a failure |
| Findings | a page of findings still being read | 7 | `findings.spec.ts:306`, "a page of findings still being read is drawn as rows saying so, which the findings replace": on a project drifted before the server starts, so that the first revision already holds its two findings and no clean window is drawn first; the first page held, the line above the table counts the two findings from the state alone and the grid has two "Reading…" rows and no finding; dies under the pending row's `Reading…` cell emptied, at the count of two |
| Findings | a fix's Apply the server fails on | 7 | `findings.spec.ts:337`, "a fix the server fails on shows its refusal in the panel in place of the fix, writes nothing, and can be chosen again and applied": the status draws in place of the consequence and the Apply, the finding stays in its panel, and nothing is written; dies under `FindingsPage`'s `onError` other arm made `setRefused(null)`, at the status. Its second half is the bug of planning ruling 15, red first (the refusal outlived the reader's next choice and withdrew the Apply, so the fix pressed off and on offered none): the fix is `refusalsAfterChoice` (`lib/findings.ts`, under Vitest), read by `onChoose`, and the half dies under `onChoose={setChosen}`, at the Apply |
| Files | reading the project's files | 7 | `files.spec.ts:595`, "the files tab says it is reading the project's files until they are read": dies under the loading paragraph emptied, at the sentence |
| Files | the list failing on a new revision, the table kept (*added*) | 2 | `kept.spec.ts:90`, "the files failing on a new revision keep the table, with the error above it" |
| Files | a New file of a vocabulary's own kind: types, units, constants, sections or rasters | 7 | `files.spec.ts:624`, "a New file of each kind of vocabulary is created empty and added to the includes, and only a component asks for a component's name": one journey walks the five kinds, each named `spare_<kind>`; dies under `asksComponentName` answering `true` (at the Component name's count), under the chooser's list cut to two kinds, and under a server that creates a units file for every kind |
| Files | New file refused | 7 | `files.spec.ts:673`, "a New file the server refuses says why in its own words, with nothing to apply and nothing written": the five refusals in turn, each the panel's status with no Apply; dies under `NewFile`'s `offer` refusal made `null`, at the first sentence |
| Files | Add a file refused | 7 | `files.spec.ts:735`, "an Add the server refuses says why in its own words, with nothing to apply and nothing written": the five refusals in turn, on the demo's pattern; dies under `AddFile`'s `offer` refusal made `null`, at the first sentence |
| Files | New file's and Add's out-of-date refusal, shown in their own panels | 7 | `files.spec.ts:507`, "a New file applied while the description changed on disk is refused in its own panel, and goes through once the analysis has caught up", and `files.spec.ts:567`, "an Add applied while the description changed on disk is refused in its own panel, and nothing is written": two journeys, one per panel, both writing unseen before the press; both die under `useFilesApply`'s `refusalShown(stale, …)` made `refusalShown(null, …)` at `toHaveText(STALE)` (New file draws no status, Add its plan's own stale sentence), and each alone under its own panel's `offer` refusal made `null` |
| Files | an entry whose file did not load | 7 | `files.spec.ts:804`, "an entry whose file did not load is listed as not loaded, its kind still read": dies under `stateOf`'s first line made `if (row.file !== null) return "";`, at "did not load" |
| Files | an entry naming no file | 7 | `files.spec.ts:832`, "an entry naming no file, and a pattern matching none, are listed as naming no file, with nothing beneath them": dies under `stateOf`'s "names no file" made `""`, at the first State cell |
| Files | an entry the last analysis did not read | 7 | `files.spec.ts:862`, "a file a pattern matches that the last analysis did not read is listed as not read, until the next analysis reads it": dies under `stateOf`'s last line made `""`, at "not read by the last analysis" |
| Files | a pattern entry, the files it matches listed under it | 7 | `files.spec.ts:887`, "a pattern's row is listed with the files it matches beneath it, each one a component, and a sub-project's row is one of kind project": dies under `rowsOf` without the children it pushes (at the row-header list), and under `FilesTableView`'s `child` class dropped (at `toHaveClass`) |
| Files | a removal refused for a file only a pattern brings in | 7 | `files.spec.ts:921`, "a removal of a file only a pattern brings in is refused, naming the pattern, with nothing to press": dies under a server whose `remove_plan` lacks its `brought_by` refusal (at the whole sentence, which reads "no entry of demo.ddd.json's includes names controller.ddd.json, and none of its patterns matches it" instead), and under `rowsOf`'s child `key` made the pattern's own (no row is named for the child) |
| Files | an Apply the server fails on | 7 | `files.spec.ts:943`, "an Apply the server fails on is refused in the Remove panel in its words, which still offers the removal, and writes nothing": by Remove, which stands for the three actions since they share `useFilesApply`; dies under its `onError`'s `setRefused(refusalOf(error))` made `setRefused(null)`, at the status |
| Files | a removal or an add the server could not judge (*added*, pre-flight) | 7 | `files.spec.ts:974`, "a removal or an add the server could not judge says so in its words, and is still offered": the server's `unjudged` sentence, on a project never fully analysed (this was Step 6's survey item); dies under `FileActionsView`'s unjudged paragraph dropped |
| Files | a removal a pattern keeps in (*added*, pre-flight) | 7 | `files.spec.ts:1022`, "a removal a pattern keeps in says so, and takes the entry out alone, the file staying": dies under `FileActionsView`'s kept paragraph dropped (at the sentence), and under the child class dropped (at the row left) |
| Files | a plan refused as out of date before any press (*added*, pre-flight) | 7 | `files.spec.ts:1063`, "a plan asked after a file changed on disk is refused as out of date in its own panel, for an Add and for a Remove, with nothing to press": dies under `AddFile`'s `offer` refusal made `null` (at the Add panel's status) and under `RemoveFile`'s (at the Remove region's) |
| Files | a finding's route followed to a Files row (*added*, pre-flight) | 7 | `files.spec.ts:1100`, "a finding about an empty vocabulary leads to its row of the Files tab, whose removal is planned at once": dies under `routeOf`'s `file` arm matching no kind, at the address (the link leads to the component page) |
| Compare | a baseline asked for with Enter | 7 | `compare.spec.ts:243`, "a baseline typed is asked for with Enter, once, and a field with nothing but spaces in it asks for nothing": `comparesAsked` counts the requests: spaces and Enter ask nothing, a path and Enter ask once; dies under `CompareView`'s `onKeyDown` removed (at the verdict), and under its `trim() !== ""` guard removed (at the count: the spaces then ask `?baseline=`) |
| Compare | a finding about the whole delivery, saying why it leads nowhere | 7 | `compare.spec.ts:268`, "a finding about the whole delivery says why it leads nowhere": dies under `compareRouteReason`'s empty-pointer arm removed, at the sentence |
| Compare | the baseline's own findings, named as the baseline's and leading nowhere | 7 | `compare.spec.ts:290`, "the baseline's own findings are named as the baseline's and lead nowhere, though their files are the open project's own": the project against itself, drifted; dies under `compareRouteReason`'s `fromBaseline` arm removed (at the reason) and under the File column's name made the name alone (at the row, found by its File cell's text). Its second half is the bug of planning ruling 16, red first (the panel named the file plainly, "controller.ddd.json", in its heading line and "sensor_hub.ddd.json" in its note, where the table says "the baseline's controller.ddd.json"): `FindingPanelView` takes the file's naming as a prop, `fileName`, which `CompareView` fills with `fileNameIn(row.fromBaseline)` (`lib/compare.ts`, under Vitest) and the Findings tab with `baseName`; the half dies under the panel given the plain naming (at its heading line) and under its notes' files named plainly (at the note) |
| Compare | a finding's panel closed | 7 | `compare.spec.ts:338`, "a finding's panel is closed by its Close button, the comparison standing", and `compare.spec.ts:367`, "a finding's panel closes by itself once a comparison no longer reports the finding, and stays closed when it returns": two journeys (P19c-10), the second drawn by code of its own (`ComparePage`'s `setSelected(undefined)`); the first dies under `CompareView`'s `onClose` made a no-op, at the panel's count; the second under `setSelected(undefined)` removed, at its last count of zero (the panel springs back when the finding returns) |
| Compare | a baseline asked for again, its file made or written over since (*added*, pre-flight) | 7 | `compare.spec.ts:403`, "a baseline refused, and then made, is asked for again by the same press", and `compare.spec.ts:427`, "a baseline written over is asked for again by the same press, and the verdict follows": the bug of planning ruling 18, red first: pressing Compare again with the same path sent nothing, so a refusal stood after its file was made, and "can replace" stood after the baseline was written over; the first journey died at the verdict (the refusal stood), the second at its "cannot replace" (it read "can replace"); `nextAsk` (`lib/compare.ts`, under Vitest) numbers each ask into `ComparePage`'s query key, and both journeys die under its `number` made `1`, at their verdicts, as two of the four Vitest cases do; its `trim()` is pinned by Vitest alone |
| A component | reading its file | 8 | none yet |
| A component | its file failing on a new revision, the page and its open panel kept (*added*) | 2 | `kept.spec.ts:105`, "a component's file failing on a new revision keeps the page and its open panel, with the error above it" |
| A component | a component file that parses but breaks its schema, drawn as the page draws any file | 8 | none yet |
| A component | reading its findings | 8 | none yet |
| A component | its findings failing to load | 8 | none yet |
| A component | no finding in it | 8 | none yet |
| A component | a variable's panel reading the variable | 8 | none yet |
| A component | a variable's panel failing to read the variable | 8 | none yet |
| A component | a finding in a variable's panel, followed to what it names | 8 | none yet |
| A component | a unit outside the project's vocabulary, said to be | 8 | none yet |
| A component | the add panel reading what may be declared | 8 | none yet |
| A component | the add panel failing to read it | 8 | none yet |
| A component | a dimension picked from the project's constants | 8 | none yet |
| A component | a key's Apply, a removal or a declaration the server fails on | 8 | none yet |
| Values | reading the values | 8 | none yet |
| Values | the values failing on a new revision, the grid kept (*added*) | 2 | `kept.spec.ts:149`, "the values failing on a new revision keep the grid, with the error above it" |
| Values | the values failing to load | 8 | none yet |
| Values | an object no longer declared, its page saying so, with the way back | 8 | none yet |
| Values | a declaration with no cell, opened by its address | 8 | none yet |
| Values | an object initialised with text | 8 | none yet |
| Values | a grid that states nothing | 8 | none yet |
| Values | a grid stated once for every cell | 8 | none yet |
| Values | a grid nothing produces, or more than one place does, read only | 8 | none yet |
| Values | a cell's Apply the server fails on | 8 | none yet |
| Values | a values address naming a file the project does not include (*added*, pre-flight) | 8 | none yet |

## Milestone gate

At the head, each exit status captured on its own (`gate.sh` in the session scratchpad runs them in this order):
1. `.venv/bin/python -m pytest`: its summary line, and 100 % line and branch.
2. `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/mypy`.
3. `cd gui`, then `DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas`, then `npm run lint`, `npm run typecheck`, `npm test` (100 % on all four), `npm run build`, `npm run ladle:build`.
4. From the root: `docker compose run --rm gui-screenshots` in compare mode, with no reference moved except those a task changed on purpose, each opened and described.
5. `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`.
6. The journeys, after the build and never alongside Docker: `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --output=<scratch>`.
7. CI: the final hunt clean on all three legs, and a full run green on every job.

## Figures

Filled in by Task 1 (the baseline run) and Task 9.

- **The shortest chain laid out in ranks only** (Task 4, Step 4). Measured on the Linux development PC, in Chrome 155.0.8059.84, at `110accb`, whose page is that of `5cac6e0`. Each chain was the generator's `chain` shape (`tools/generate_project.py DIRECTORY --declarations N --shape chain`), served by `ddd gui` and opened in a page of 1280 by 720.
  - 907 components (1,814 declarations) laid out in full, and 908 (1,816) in ranks only, four times each.
  - Once each, 800, 900, 905 and 906 laid out in full; 909, 910, 915, 920, 925, 930, 950, 970, 990, 1,000, 1,100 and 2,000 in ranks only.
  - `chainedGui` serves 2,000 components (4,000 declarations), more than twice 908. That project was generated in 143 ms, served and analysed in 484 ms, and drawn in ranks only 374 ms after the page was asked for. Its journey ran in 1.1 to 1.2 s, ten times.
  - The three legs' own figures are read off this task's full run.

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |

## What was left open

Known before execution, from 19b's plan and this part's spec §11, each left with the maintainer:
- **P19b-11 and P19a-7:** how long a stale refusal shows.
- **P19b-13:** a selection that changes nothing offers a change.
- **P19b-18:** a bare word in a constant's value answered in the json parser's words.
- **P19b-24,** and the stale decision made inline in ten `.tsx` files, thirteen places. The Shared files tab's add form (`SharedAdd`) follows the declare panel's rule (Task 6's survey).
- **Firefox, Safari and macOS.**
- **The user guide,** part 20.

Found by the surveys while planning, read in the code and not yet seen on a running page: each task confirms its own, and records it as a ruling with its evidence.
- **A panel whose read of the units fails says it is reading, for good** (planning ruling 14).
- **A type's panel links a finding routed back to the type itself,** where a variable's panel keeps such a finding as text (Task 5's survey).
- **After a failed session, the masthead's "Projects" changes the address and nothing else;** an unnamed project's refusal writes its path in native separators beside a list in forward slashes; a failed read of the undo's preview reads "The undo was refused: …" (Task 3's survey). That last is now a row (ruling 18).
- **An arrow's description mounts a render after focus lands** (Task 4's survey).
- **Removing an entry of a project that was never analysed** is allowed with the server's `unjudged` sentence (Task 7's survey). It is now a row, beside the three other Files states the earlier pre-flight found (ruling 18).

Found by the earlier pre-flight (ruling 18), and recorded for the maintainer:
- **The Add a declaration panel loses its typed name when the server stops.** Its combobox, disabled, resets to no choice.
- **Compare's Baseline field loses its focus after an Enter ask,** and drops keystrokes when a revision lands while the reader types.
- **The Types tab names no component file that breaks its schema:** the types that file declares inline vanish, with no banner.
- **A component with no name is named three ways:** its file's stem on the canvas, its path in the Table tab, and "Unnamed component" on its page.
- **`set_entry` (`shared_plans.py`) plans a value equal to the entry's,** which its panels never ask for.
- **`TypePanelView.tsx` decides a use's route in a `.tsx`.**
- **A refusal that is not stale differs across panels:** some keep their Apply, others withdraw it until the reader chooses again.
- **The undo strip blanks its preview for about one frame on every revision.**
- **P19b-13 and P19b-24:** their designs, run red on the page and then green with the change, are in the companion's §B, for whoever takes them up.

Found during execution: filled in by Task 9.

## Rulings taken

Taken while planning; execution adds its own below them.

1. **The hook is `gui/src/app/useKept.ts`, not a hook in `gui/src/state`** as spec §5 has it. `src/state` holds no React: the page's hooks live in `src/app` (`useLayout`, `useProjectState`, `useRoute`), glue only, and the decision is `kept` and `shown` in `src/lib`, under Vitest — cost if wrong: one file in another directory.
2. **The kept answer is state adjusted while rendering,** not a ref nor an effect. An effect would draw one frame of the error alone before the kept table; a ref written while rendering is what React asks code not to do. `kept` answers the very object it was given while nothing changed, so the adjustment stops — cost if wrong: one extra render each time a tab's answer changes.
3. **`SECURITY.md` is left as it is.** It says nothing of the content security policy at `2bc00da`; the security page, `docs/gui_security.rst`, is where the policy is described — cost if wrong: one sentence the maintainer may want there too.
4. **The policy's hash is computed from the page's text with every CRLF and lone CR made LF** (Review Focus 1). That is what a browser hashes — cost if wrong: none; a page with no CR is hashed the same either way.
5. **`held` takes `every` and `onAnswer`,** so that all eight held-request copies are one helper: `files.spec.ts`'s New file journey holds every list on purpose, and its Remove journey reads the list it holds — cost if wrong: two options no new journey may use.
6. **The four "table kept" rows are Task 2's,** not their screens' tasks: they are the kept answer's red-first proof (spec §5) — cost if wrong: none; rows only change task.
7. **Models:** opus implements and reviews Tasks 1, 2 and 4, sonnet Tasks 3, 5, 6, 7 and 8. The final whole-branch review runs on opus (spec §8) — cost if wrong: a cheaper seat missing a vacuous journey, which each journey's named ablation guards against.
8. **One agent at a time,** the maintainer's standing rule for this repository — cost if wrong: a longer part.
9. **Only the controller pushes,** and only this branch, after each finished task — cost if wrong: a slower loop.
10. **"A later layout failing, the canvas kept" is reached inside the layout worker,** by an uncaught error thrown in its thread through Playwright's `worker.evaluate`. No route and no project can reach it: the worker's script is fetched once per canvas, and `layoutOf` answers an error only for an input the server never sends. It is what a worker that crashed does, and no code of the page is changed to reach it, as 19b's signed-out journey plants a token the server never issued — cost if wrong: the row names that reason instead, and the state stays untested.
11. **`tools/generate_project.py` gains a `chain` shape** for the row "laid out in ranks only". Its shapes keep every reader 30 components from its source (`LAYER`), so the depth dagre meets is the components over 30, and the worker's overflow (about 908 deep) would take about 817,000 declarations — cost if wrong: one shape and its tests in a development tool.
12. **The row "the project's graph failing before anything is drawn" cites `network.spec.ts`'s existing journey,** which fails `/api/graph` every time and asserts the canvas's alert. An `"http"` twin would add the server's wording alone — cost if wrong: none.
13. **The start page's buttons enabled again once an open has answered** (Task 3's survey) is fixed in Task 3, red first: the fix is contained in `StartPage.tsx` and one `src/lib` function — cost if wrong: one function and its journey's second half.
14. **A panel whose read of the units fails, saying it is reading for good** (Task 5's survey), is recorded for the maintainer, not fixed. It spans three panels (`TypePanel`, `UnitPanel`, `VariablePanel`), past spec 19b §12's one screen, component or library function, though a fix could be `panelShows` asked of the units query's error with its three callers. Task 2's kept answer makes it easier to meet: the Units tab keeps its table where an open unit's panel turns to "Reading…" — cost if wrong: a reader whose units read failed waits on a panel that never says why, as today.
15. **A fix whose Apply the server failed on can be chosen again** (Task 7's survey), fixed in Task 7, red first: today only another row, or Close and the row again, gives back its Apply, against the comment over `refused` in `FindingsPage.tsx`. The rule is one `lib/findings.ts` function, read by that one screen — cost if wrong: one function and its journey's second half.
16. **A baseline's finding names its file as the baseline's in its panel too** (Task 7's survey), fixed in Task 7, red first, with the words the Compare table's File cell already uses (`fileLabel`). It changes the Compare screen and one prop of `FindingPanelView` — cost if wrong: a prop the Findings tab passes as today.
17. **The kept answer covers the component page and the values grid too,** the maintainer's answer of 2026-10-21 to Task 8's survey: their reads dropped everything on a failure, an open panel's choice included, against their own comments. A refusal (a 4xx) is never kept (`refusedRead`): the values page answers a renamed object, or a shape no grid can draw, with a refusal about the object, and the component page a file no longer in the project, so an answer kept over it would show what the project no longer has. The five tabs follow the same rule, though none of their reads is refused in practice — cost if wrong: a refusal shown alone where a kept answer would have served, or two more screens to revert.
18. **The earlier 19c pre-flight is folded in** (the maintainer's choice of 2026-10-21). An earlier plan for this part was written on another branch, from a pre-flight of every row at `2bc00da`. That branch is retired, and its pre-flight is kept in `2026-10-21-gui-journeys-remaining-preflight.md`. This plan takes from it:
    - **four contained bugs,** each fixed red first:
      - the start page's empty or doubled image (Task 3);
      - the component table's cells under a stopped server (Task 3);
      - Compare asked again for the same baseline (Task 7);
      - a combobox's late note (Task 8).

      Its fifth, a fix that could not be chosen again, this plan already had (ruling 15);
    - **nine rows:**
      - the undo's preview failing (Task 3);
      - a rename the plan refuses, and a unit listed twice (Task 5);
      - four Files states: an unjudged plan, a removal a pattern keeps in, a plan refused as out of date before any press, and a finding's route to a Files row (Task 7);
      - a baseline asked for again (Task 7);
      - a values address naming a file the project does not include (Task 8);
    - **its drafts,** as evidence for every screen task.

    Where it chose otherwise than this plan, this plan stands: rows 14, 20 and 21, row 9's one screen, and the kept answer's design — cost if wrong: nine cheap journeys and four small fixes.

### Taken during execution

Numbered P19c-1 onward; code comments cite them by number.
