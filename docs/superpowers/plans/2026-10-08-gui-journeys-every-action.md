# The GUI's Journeys for Every Reader Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every action a reader can take in `ddd gui`, and every state a reader can meet, has a journey or a recorded reason it has none; and the page sends its own loads once more when the network fails them.

**Architecture:**
- **An inventory first.** Task 1 redoes part 19's survey against today's tree and commits it as this plan's table. Every later task closes its screen's rows.
- **Two helpers carry every state the examples do not have as they stand:**
  - `failing` makes the page's requests to one path fail, with the server's own error answer or with no answer at all;
  - `copiedGui` serves a copy of an example changed before `ddd gui` starts.
- **The page sends its loads once more** (spec §6):
  - `request()` resends a GET whose fetch was rejected, once;
  - `main.tsx` asks again, before drawing, for any stylesheet that failed.
- **Each screen's task** writes its journeys, shows each one fails under a named change, and fixes the contained bugs they find, red first.

**Tech Stack:**
- **Journeys:** Playwright 1.63, driving the compiled pages served by a real `ddd gui` over a copied example. Its `page.route` fails a request in the browser alone.
- **Page:** React 19 + TypeScript, with Vitest at 100 % over `src/api`, `src/lib` and `src/state`, and React Query with `retry: false`.
- **CI:** the three legs part 19a built, ubuntu chromium, windows chromium and windows msedge, with `-f repeat=N` hunts.

**Spec:** `docs/superpowers/specs/2026-10-08-gui-journeys-every-action-design.md`. Read it before any task. Where this plan departs from it, the departure is a ruling in *Rulings taken* at the end, with its reason.

## Global Constraints

Every task's requirements include this section.

**Running things**

- **Interpreters.** There is no `python` on PATH: always use `.venv/bin/python`. Node is not on PATH either; it is at `~/.local/node-v24.21.0/bin`.
- **Never add `-q` to pytest.** `pyproject.toml` already sets it in `addopts`. A second one removes the `N passed` line while pytest-cov still prints its coverage line, so the output looks fine and says nothing.
- **A pipeline reports its last command's exit status.** Capture each tool's own: `.venv/bin/python -m pytest > gate.txt 2>&1; echo "EXIT=$?"; tail -n 3 gate.txt`. A run that finished ends with its **summary line**; a tail ending in a stack trace did not finish, whatever the exit code says.
- **A stale `.coverage` file.** Once it made pytest answer `4445 passed` with exit 3 and **no coverage line**. If the coverage summary is missing, delete `.coverage*` (gitignored) and run again.
- **Journeys:**
  1. Run `cd gui && npm run build` first, because the journeys drive the **compiled** pages in `src/ddd/gui/static`.
  2. Then run `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --output=<a path outside the repository>`. Writing `--output` inside `gui/` fails with `EACCES`.
- **Never run the journeys while the Docker screenshot run is running.** Both drive Playwright over the same `gui/` checkout, and the journeys then fail with "Playwright Test did not expect test() to be called here". Run one after the other.
- **Screenshots and docs** run from the repository root, in Docker, which cannot see the session scratchpad:
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
- **Only the controller pushes, and only this branch.** The maintainer gave leave on 2026-10-09 to push `feature/gui-journeys-every-action` alone, for this part's CI runs and hunts. Never master, never `--force`. An implementer commits locally and reports; the controller pushes, starts the run, and hands the result back.
- **Each task's Windows proof is a full run** (spec §8), started by the controller once the task's commits are pushed, and read before the task's review is closed. Only the final hunt must be clean on all three legs.
- **Starting a run:**
  - a full run of every job: `gh workflow run ci.yml --ref feature/gui-journeys-every-action -f repeat=1`;
  - a hunt: `-f repeat=5`.

  Wait on it once, in the background. Never poll it in short loops.
- **Reading a run:**
  - its jobs: `gh run view <run> --json jobs`;
  - a job's log: `gh run view --job <job> --log`.
- **A failed run's Playwright report** (`gh run download <run> -n playwright-report-<os>-<browser> -D <scratchpad>/<run>`) may be downloaded without asking: the maintainer's leave of 2026-10-09, for any failed run of this part, hunt or single pass. Read each failed test's `error-context.md`, the page's accessibility snapshot at the failure, and the network entries in its trace. Nothing else is downloaded without asking.

**Gates**

- **Python:** `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare** (it checks `src/ddd` and `tools`, strictly).
- **Page:** `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`, with Vitest at 100 % on statements, branches, functions **and** lines over `src/api`, `src/lib` and `src/state`.
- No `pragma: no cover`, no skips, no xfails.
- **No commit leaves a gate red.**
- **CI runs more than the development PC does:**
  - Python 3.12, 3.13 and 3.14, on ubuntu **and** windows runners;
  - the journeys on three legs: ubuntu with Chromium, windows with Chromium, windows with the runner's own Edge;
  - **Windows file locks:** Windows refuses to rename over, or delete, a file that another handle holds open (`ddd.editing.REPLACE_TRIES`). `writeUnseen` in `gui/e2e/demo.ts` already tries a rename again while Windows refuses it.

**What the gates cannot see**

- **No journey is vacuous** (spec §5). Each new journey's key assertion is shown to fail under one named change to the page or the server, and the report says which change, and which assertion died.
  - **Ablate the page in a scratch copy, never in place.** Build the ablated page into a copy of the package (`npx vite build --outDir <scratch>/pysrc/ddd/gui/static --emptyOutDir`, the rest of `src/ddd` copied beside it), and start the journeys' server from that copy (`DDD_PYTHON` as usual, `PYTHONPATH=<scratch>/pysrc`, `PYTHONDONTWRITEBYTECODE=1`). Check that the copy's `ddd.gui.server.static_directory()` is its own. The containers on 8124/8125 serve the checkout's static, so the checkout's page only ever holds the real build.
  - **Restore every source ablation by exact edit.** Save `git diff` to a patch first. Compare it after each restore, and run `git status --porcelain <file>` immediately before every restore. Never `git checkout -- <file>` over uncommitted work.
  - **Ablate Python in a scratch `git worktree`,** with pytest run from inside it (`pyproject.toml`'s `pythonpath` beats `PYTHONPATH`), and `PYTHONDONTWRITEBYTECODE=1`.
  - **Confirm one ablation kills something before trusting that another kills nothing.** A survival is believed only after `PYTHONHASHSEED=0`, `1`, `4` and `7` (Python), or `--repeat-each=5` (a journey).
- **A coverage gate cannot see data.** Ablate every new data value (a sentence, a header, a default) and confirm that a **named** test dies.
- **Never conclude what *else* pins something from a narrowed run** (no `-k`, no path argument, no `-g`). That is a whole-suite question; copy the summary line in rather than paraphrasing it.
- **No decision may live in a `.tsx` file.** Every judgement lives in `gui/src/lib`, `gui/src/state` or `gui/src/api`, under the Vitest gate; a `src/app` module is glue only.
- **A refusal or banner is asserted as its whole sentence.** Read every expected sentence off the running code, never out of this plan. This plan's quoted strings were read at `205d5a6` and are a guide.
- **A journey waits on what the reader sees.**
  - Never `page.waitForTimeout`, beyond the recorded exception in `demo.ts`'s `settled()` (P19a-8).
  - Never `page.waitForResponse` to coordinate, beyond the recorded exception in `hostile.spec.ts` (P19a-30's D2).
  - Never a count read with `.all()` before what it counts is drawn.
  - Use `toHaveCount`, `toBeVisible`, `toHaveText`, `toHaveCSS`, or `expect.poll` on what the page shows.
  - A request the journey must see held is held by its own `page.route`, then let through; a request the journey must see answered is fetched in the route with `route.fetch()`, checked, then `route.fulfill()`ed.
- **A journey leaves no visible window between a write and its stamp** (`driftMaxUnseen`, `writeUnseen` in `gui/e2e/demo.ts`). A change the watcher must see is written plainly; a change it must not see yet is written unseen.
- **Playwright's `retries` stays 0.** No journey is repeated to pass.
- **The suite forbids skips** (`test_nothing_in_the_suite_skips`).

**Prose**

- **A sentence stating a measurement gets the measurement run as it is written,** against the file it names, with the exit status copied from *that* run.
- **A probe is quoted with the machine, the commit, the project and the run it came from.**
- **Cite by name, not by line number.** Line numbers in this plan were measured at `205d5a6`, and go stale the moment an earlier task edits the file.
- **Before ruling on a trade-off, confirm that both sides of it can actually happen.**

**Conventions**

- **Commits:** a lowercase imperative subject on **one line**, with no `feat:`-style prefix, and a body saying why. The trailer names the model that wrote the commit: `Co-Authored-By: <the model you are> <noreply@anthropic.com>`. A dispatch never tells you which model to name (part 18b's P18b-15). Never `--amend`, never rebase, never push.
- **Every UI pull request carries a screenshot of what it added,** the maintainer's standing rule. A fix that changes what the page shows changes or adds its Ladle reference, made in Docker with `UPDATE=1`, opened and described in words.
- **Reports go where your dispatch says,** to the report file it names.
- **If a brief or this plan is wrong, say so in your report** rather than working around it silently.
- **Bidi characters.** A unicode escape typed through the tools can land as the character itself: a right-to-left override did, twice, in part 18. Write such a character as words ("U+202E"), or build it in code with `chr()`. Before any push, the controller scans the commit messages and the changed files for U+202A to U+202E and U+2066 to U+2069.
- **A bug a journey finds** (spec §3, the maintainer's second answer):
  - fixed in its task when the fix stays within one screen, one component or one library function, with the journey red first;
  - otherwise recorded as a ruling for the maintainer, its row naming the bug as the reason it has no journey, with the evidence.

## Prerequisites

1. **The branch.** The work is on `feature/gui-journeys-every-action`, made from master `ff9954e` (part 19a, PR #81). Its first commit is the spec, `205d5a6`. Work in the main checkout `/home/sauci/Documents/Github/ddd`: Docker cannot see the session scratchpad.
2. **The baseline gate.** Run the milestone gate (below) once at this plan's commit, before Task 1, so that every later red is this part's own.
3. **Read the spec,** whose §4 lists the starting rows and whose §5 says how each kind of state is reached.
4. **The maintainer's leave** to push this branch alone, and to download any failed run's report of this part, was given on 2026-10-09.

## Review Focus

The five failure modes the spec implies but no row of the inventory would test on its own, most likely first. Each has its test in the task that owns the code.

1. **A server really gone still reads as gone, at once.** With every GET sent once more, a stopped server must still show the page's stopped banner after the second rejection, never wait or loop. *(Task 2: `skeleton.spec.ts`'s "the page says so when the server stops" keeps passing, and a Vitest case pins two sends, then `ServerUnreachable`.)*
2. **An abort is never resent.** The long poll aborts its own fetch when the page moves on. A resend would start a poll nobody reads. *(Task 2: a Vitest case: one send, then `AbortError`.)*
3. **A `POST` is never resent,** even when its fetch is rejected, since an edit may have been written. *(Task 2: a Vitest case: one send, then `ServerUnreachable`.)*
4. **A stylesheet that fails twice does not hang the page.** It draws as it does today, unstyled, and works. *(Task 2: a journey failing the stylesheet on every request.)*
5. **An error banner reads as a sentence.** A request the server fails shows the server's own message, never a code such as `internal` or `http-500`. *(Every error-banner journey of Tasks 3 to 9 asserts the whole sentence the page shows.)*

## File Structure

| File | Task | What |
| --- | --- | --- |
| `gui/e2e/demo.ts` | 1 | `failing`: the page's requests to one path fail, with the server's error answer or with none |
| `gui/e2e/fixtures.ts` | 1 | `start` split out of `serving`; the fixture `copiedGui` |
| `gui/e2e/files.spec.ts` | 1, 7 | the Remove-ordering journey's `waitForResponse` replaced (1); the Files rows (7) |
| `docs/developer_documentation.rst` | 1 | the two helpers, beside the fixtures it lists |
| `gui/src/api/client.ts`, `client.test.ts` | 2 | `sentAgain`, and `request()` resending a GET once |
| `gui/src/lib/sheets.ts`, `sheets.test.ts` | 2 | `sheetsToAskAgain`: which of the page's stylesheets failed |
| `gui/src/app/sheets.ts` | 2 | `askSheetsAgain`: the glue asking for them once more |
| `gui/src/main.tsx` | 2 | draws once the stylesheets are asked again, as it does once signed in |
| `gui/e2e/network.spec.ts` | 2 | the network rows |
| `CHANGELOG.md` | 2, and any task fixing a bug a reader would notice | |
| `gui/e2e/start.spec.ts` | 3 | the start page and the app around every page |
| `gui/e2e/canvas.spec.ts` | 4 | the canvas rows, and the components table's summary line |
| `gui/e2e/types.spec.ts`, `project-units.spec.ts` | 5 | the Types and Units rows |
| `gui/e2e/shared.spec.ts` | 6 | the Shared files rows |
| `gui/e2e/findings.spec.ts` | 7 | the Findings rows |
| `gui/e2e/compare.spec.ts` | 8 | the Compare rows |
| `gui/e2e/declarations.spec.ts`, `values.spec.ts` | 9 | a component's rows and the values' |
| this plan's *The inventory* | 1, then every task | each row's journey, or its reason |

A screen's fix, where a journey finds a bug, is in that screen's own files, with its decision in `gui/src/lib` under Vitest.

## Interfaces Between Tasks

- **Task 1 produces:**
  - `failing(page: Page, path: string | RegExp, how: "http" | "network", times?: number): Promise<() => number>`, in `gui/e2e/demo.ts`. It fails the page's requests whose pathname is `path` (or matches it), the first `times` of them (every one if omitted), and answers how many it has failed so far. `"http"` answers `500` with the server's own error body; `"network"` aborts with no answer.
  - `SERVER_FAILED`: the sentence `"ddd gui failed on this request; the terminal it runs in shows why"` that `failing`'s `"http"` answers with, the server's own `_INTERNAL` (`src/ddd/gui/server.py`).
  - The fixture `copiedGui: (example: "demo" | "vocabulary" | "structures", change: (directory: string) => void, options?: { named?: boolean }) => Promise<Gui>`, in `gui/e2e/fixtures.ts`. It copies the example under the test's own output directory, runs `change` on the copy, then starts `ddd gui` there, naming the project unless `named` is `false`. Every server it started is stopped when the test ends.
  - The inventory table, in this plan.
- **Task 2 produces:**
  - `sentAgain(method: string | undefined, error: unknown): boolean`, in `gui/src/api/client.ts`;
  - `sheetsToAskAgain(sheets: readonly SheetLoad[]): string[]`, with `SheetLoad = { href: string; loaded: boolean }`, in `gui/src/lib/sheets.ts`;
  - `askSheetsAgain(document: Document): Promise<void>`, in `gui/src/app/sheets.ts`.

  From Task 2 on, a GET the network fails once is recovered. So a journey for a network banner fails its request at least twice (`failing(page, path, "network")`, every time), and the banner shows only then.
- **Tasks 3 to 9 consume both helpers,** and each adds rows' journeys to its own files. None changes another task's spec files, except where a row moved (the inventory says which task owns it).

---

### Task 1: the inventory, the two helpers, and `files.spec.ts`'s wait

**Model:** opus, reviewed on opus. The inventory needs judgement across every screen, and the helpers are what every later task stands on.

**Files:**
- Create: `gui/e2e/helpers.spec.ts`
- Modify: `gui/e2e/demo.ts`, `gui/e2e/fixtures.ts`, `gui/e2e/files.spec.ts`, `docs/developer_documentation.rst`, and this plan's *The inventory*

**Interfaces:**
- Consumes: the spec's §4 starting rows; part 19's survey (summarised in spec §2).
- Produces: `failing`, `SERVER_FAILED` and `copiedGui` (see *Interfaces Between Tasks*), and the inventory table.

- [ ] **Step 1: The inventory.** For each starting row of spec §4, find the code that draws it and every journey that drives it, at this commit.
  - Write one row per action or state into *The inventory* below, replacing its starting list: screen, row, owner task, the journey that covers it (`file:line` and title) or "none yet".
  - **Add** rows the survey missed:
    - any action or state on a screen that no row names;
    - the rows part 19a added (the Files tab's option C, `localhost.spec.ts`, `mapped.spec.ts`).
  - **Mark** rows already covered since the survey with their journey.
  - **Cite by name.** A row is a reader's words ("a constant renamed"), never a component's.
  - The owner task is the screen's (Tasks 3 to 9). A row of no screen goes to Task 3.
- [ ] **Step 2: The helpers' journeys, red first.** Create `gui/e2e/helpers.spec.ts`:

```ts
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { failing, SERVER_FAILED } from "./demo";
import { expect, test } from "./fixtures";

/** A route the page never asks on its own (no caller in gui/src), so that only the asks below
 * are counted - and one the server answers: refused 401 here, since `fetch` below sends no
 * token. */
const UNASKED = "/api/checks";

type Asked = { status: number; message: string | null } | "no answer";

/** `path` asked from the page's own origin, as its code asks: the answer's status and message,
 * or "no answer" where the fetch was rejected. */
function askedFromPage(page: Page, path: string): Promise<Asked> {
  return page.evaluate(async (path) => {
    try {
      const response = await fetch(path);
      const body: unknown = await response.json().catch(() => null);
      const message =
        typeof body === "object" &&
        body !== null &&
        "message" in body &&
        typeof body.message === "string"
          ? body.message
          : null;
      return { status: response.status, message };
    } catch {
      return "no answer" as const;
    }
  }, path);
}

test("a request failed with the server's own error answer, then let through", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const failed = await failing(page, UNASKED, "http", 1);
  expect(await askedFromPage(page, UNASKED)).toEqual({ status: 500, message: SERVER_FAILED });
  expect(failed()).toBe(1);
  // Past its one failure the ask reaches the server, which refuses it: no token was sent.
  expect(await askedFromPage(page, UNASKED)).toMatchObject({ status: 401 });
  expect(failed()).toBe(1);
});

test("a request failed with no answer, every time, matched by a pattern", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const failed = await failing(page, /^\/api\/checks$/, "network");
  expect(await askedFromPage(page, UNASKED)).toBe("no answer");
  expect(await askedFromPage(page, UNASKED)).toBe("no answer");
  expect(failed()).toBe(2);
});

test("a copy changed before ddd gui starts is the one served", async ({ page, copiedGui }) => {
  const gui = await copiedGui("demo", (directory) => {
    const project = join(directory, "demo.ddd.json");
    const text = readFileSync(project, "utf8");
    writeFileSync(project, text.replace('"name": "DemoDevice"', '"name": "ChangedDevice"'));
  });
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "ChangedDevice", exact: true })).toBeVisible();
});
```

- [ ] **Step 3: Run it to see it fail.**
  - Run: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test helpers.spec.ts --output=<scratch>/t1-red`.
  - Expected: it fails to compile. `failing`, `SERVER_FAILED` and `copiedGui` do not exist yet.
- [ ] **Step 4: `failing` and `SERVER_FAILED`,** at the end of `gui/e2e/demo.ts`:

```ts
/** What `ddd gui` answers a request it failed on (`_INTERNAL`, src/ddd/gui/server.py), and so
 * what `failing`'s `"http"` answers with: a page shows the server's own words for it. */
export const SERVER_FAILED = "ddd gui failed on this request; the terminal it runs in shows why";

/**
 * Makes the page's requests whose path is `path` - or matches it - fail, the first `times` of
 * them, or every one where `times` is left out, and lets the rest through to the server
 * (spec 2026-10-08 §5). `"http"` answers each as the server answers a request it failed on, a
 * `500` with its own error body; `"network"` answers nothing at all, as a dropped connection.
 * Playwright's own route, on this page alone: the server's code is never touched. Answers how
 * many it has failed so far.
 */
export async function failing(
  page: Page,
  path: string | RegExp,
  how: "http" | "network",
  times = Number.POSITIVE_INFINITY,
): Promise<() => number> {
  let failed = 0;
  const matches = (pathname: string) =>
    typeof path === "string" ? pathname === path : path.test(pathname);
  await page.route(
    (url) => matches(url.pathname),
    async (route) => {
      if (failed >= times) {
        await route.fallback();
        return;
      }
      failed += 1;
      if (how === "network") {
        await route.abort("failed");
        return;
      }
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "internal", message: SERVER_FAILED }),
      });
    },
  );
  return () => failed;
}
```

- [ ] **Step 5: `start` and `copiedGui`,** in `gui/e2e/fixtures.ts`.
  - Split `serving` into `start`, which answers the `Gui`, and the callback around it:

```ts
/** `ddd gui` over `directory`, already prepared, naming `project` on the command line or opening
 * on the start page where it is empty; stopped by the `Gui`'s own `stop`. The shared head of
 * `serving` and `copiedGui`. */
async function start(directory: string, project: readonly string[]): Promise<Gui> {
  // python -m ddd rather than the ddd launcher: on Windows the launcher starts python as a child
  // of its own, which killing the launcher leaves running, holding the port and the copy.
  const child = spawn(
    process.env.DDD_PYTHON ?? "python",
    ["-m", "ddd", "gui", ...project, "--no-browser"],
    {
      cwd: directory,
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
  let stopped = false;
  const stop = async () => {
    if (!stopped) {
      stopped = true;
      await terminated(child);
    }
  };
  try {
    const address = await served(child);
    if (project.length > 0) await analysed(address);
    return { address, directory, stop };
  } catch (error) {
    await stop();
    throw error;
  }
}

/** `ddd gui` over `directory`, handed to `use` and stopped after it whatever it did. */
async function serving(
  directory: string,
  project: readonly string[],
  use: (gui: Gui) => Promise<void>,
): Promise<void> {
  const gui = await start(directory, project);
  try {
    await use(gui);
  } finally {
    await gui.stop();
  }
}
```

  - Add the type and the fixture:

```ts
/** The examples a copy can be made of, by the name `copiedGui` takes. */
const EXAMPLES_BY_NAME = { demo: DEMO, vocabulary: VOCABULARY, structures: STRUCTURES } as const;

/** Serves a copy of an example changed before `ddd gui` starts, for a state no example has as it
 * stands: no shared entry, no dictionary, a build record not used (spec 2026-10-08 §5). The
 * copy is under the test's own output directory, as `started` makes one, numbered so that a
 * test can serve two; the project is named unless `named` is `false`. */
export type CopiedGui = (
  example: keyof typeof EXAMPLES_BY_NAME,
  change: (directory: string) => void,
  options?: { named?: boolean },
) => Promise<Gui>;
```

    and, in `test.extend`'s fixtures, beside `mappedGui`:

```ts
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  copiedGui: async ({}, use, testInfo) => {
    const running: Gui[] = [];
    try {
      await use(async (name, change, options) => {
        const example = EXAMPLES_BY_NAME[name];
        const directory = testInfo.outputPath(`${example.directory}-${running.length}`);
        cpSync(join(EXAMPLES, example.directory), directory, { recursive: true });
        change(directory);
        const named = options?.named ?? true;
        const gui = await start(directory, named ? [join(directory, example.project)] : []);
        running.push(gui);
        return gui;
      });
    } finally {
      for (const gui of running) await gui.stop();
    }
  },
```

    with `copiedGui: CopiedGui;` added to `test.extend`'s type parameter.
- [ ] **Step 6: Run the helpers' journeys to see them pass:** `npx playwright test helpers.spec.ts`, after a build. Expected: 3 passed.
- [ ] **Step 7: Ablate each helper's data,** in place, restoring by exact edit:
  - `failing` ignoring `times` (`if (false)`): the first journey dies at its second `askedFromPage`;
  - `"network"` answering `"http"`: the second journey dies;
  - `change(directory)` removed: the third journey dies.
- [ ] **Step 8: `files.spec.ts`'s `waitForResponse`** (P19a-30's D1). In "the row a Remove takes out goes before the tab's next list of entries answers", replace the route, the `listed` promise and its `await` with a route that fetches the server's own next list, checks it, and only then hands it to the page:

```ts
  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  // The server's next list, read here before the page is handed it: the entry Remove took out
  // is not in it, so the row the page drops at once (below) is not drawn again by that answer.
  let listed: string[] | null = null;
  await page.route("**/api/files", async (route) => {
    await released;
    const response = await route.fetch();
    const reply = (await response.json()) as { entries: { entry: string }[] };
    listed = reply.entries.map((each) => each.entry);
    await route.fulfill({ response });
  });
  try {
    await remove.click();
    await expect(unitsRow).toHaveCount(0);
  } finally {
    release();
  }
  await expect.poll(() => listed).not.toBeNull();
  expect(listed).not.toContain(UNITS);
  await expect(unitsRow).toHaveCount(0);
```

  Run it with `--repeat-each=10`: 10 passed. Ablate the page's at-once removal (the hold in `gui/src/lib/filesHold.ts` returning the list as it was), and see it die at the first `toHaveCount(0)`. Restore.
- [ ] **Step 9: The developer documentation.** In `docs/developer_documentation.rst`'s paragraph on the journeys, after the fixtures it names, say in its own style:
  - what `copiedGui` serves;
  - what `failing` fails, and how;
  - that `SERVER_FAILED` is the server's own sentence.
- [ ] **Step 10: The gates:**
  - lint, typecheck, Vitest, build;
  - every journey: the count before this task, plus its three;
  - `tests/test_gui_docs.py` and `tests/test_documentation.py` with `--no-cov -p no:cacheprovider`;
  - the docs under `-W` in Docker, after the journeys and never alongside them.
- [ ] **Step 11: Commit.** One commit for the inventory, one for the helpers and their journeys, one for `files.spec.ts`.

### Task 2: the page sends its loads once more

**Model:** opus, reviewed on opus. It changes how every request of the page fails.

**Files:**
- Modify: `gui/src/api/client.ts`, `gui/src/api/client.test.ts`, `gui/src/main.tsx`, `CHANGELOG.md`
- Create: `gui/src/lib/sheets.ts`, `gui/src/lib/sheets.test.ts`, `gui/src/app/sheets.ts`, `gui/e2e/network.spec.ts`

**Interfaces:**
- Consumes: `failing` (Task 1).
- Produces: `sentAgain`, `sheetsToAskAgain`, `SheetLoad` and `askSheetsAgain` (see *Interfaces Between Tasks*).

- [ ] **Step 1: The journeys, red first.** Create `gui/e2e/network.spec.ts`. The worked journey:

```ts
import { failing } from "./demo";
import { expect, test } from "./fixtures";

/** The page's own stylesheet, as Vite names it in /assets/ - its hash changes with every build. */
const STYLESHEET = /^\/assets\/index-[^/]+\.css$/;

test("a stylesheet the network failed once is asked for again, and the page is drawn styled", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, STYLESHEET, "network", 1);
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  expect(failed()).toBe(1);
  // app.css's own ground on the body (tokens.css's --ground): unstyled, the body is transparent.
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(247, 249, 249)");
});
```

  Then the other four, in the same file:
  - **"the pressable rule's stylesheet the network failed once is asked for again".** `failing(page, "/pressable.css", "network", 1)`. A button React Aria presses (the masthead's "Projects") then has `touch-action` `pan-x pan-y pinch-zoom` (`gui/public/pressable.css`).
  - **"a stylesheet the network fails every time leaves the page drawn and working"** (Review Focus 4). `failing(page, STYLESHEET, "network")`. The canvas still draws "Controller". The body's `background-color` is `rgba(0, 0, 0, 0)`. Pressing "Controller" opens its page, whose heading is "Controller".
  - **"a GET the network failed once is sent again, and the page carries on".** `failing(page, "/api/graph", "network", 1)` before `goto`. The canvas draws "Controller", `failed()` is 1, and no banner shows. Read the graph's error banner's role and text off `GraphPage.tsx`, and assert it has count 0.
  - **"a GET the network fails every time reads as the server not answering".** `failing(page, "/api/graph", "network")`. The page shows the graph's error banner with the whole sentence the page draws for `ServerUnreachable` ("ddd gui is not answering", `client.ts`), and `failed()` is 2.
- [ ] **Step 2: Run them to see the red.** On the page as it is, the first, second, fourth and fifth journeys fail: no stylesheet is asked again, and a GET is sent once. The third passes, since the page today already draws, unstyled, when its stylesheet fails. Record each failure's line in the report.
- [ ] **Step 3: The GET's rule, red first,** in `gui/src/api/client.test.ts`, inside `describe("requests to the server")`:

```ts
  test("a GET whose first fetch got no answer is sent once more, and answered", async () => {
    let sends = 0;
    const fetchImpl = vi.fn(async () => {
      sends += 1;
      if (sends === 1) throw new TypeError("fetch failed");
      return new Response("{}", { status: 200 });
    });
    await expect(request("/api/state", {}, fetchImpl)).resolves.toEqual({});
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  test("a GET whose fetch got no answer twice is unreachable, after two sends", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(request("/api/state", {}, fetchImpl)).rejects.toBeInstanceOf(ServerUnreachable);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  test("a POST whose fetch got no answer is never sent again", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(
      request("/api/edit", { method: "POST", body: "{}" }, fetchImpl),
    ).rejects.toBeInstanceOf(ServerUnreachable);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("an aborted GET is never sent again", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new DOMException("aborted", "AbortError");
    });
    await expect(request("/api/state", {}, fetchImpl)).rejects.toMatchObject({
      name: "AbortError",
    });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("a GET answered with an error is never sent again", async () => {
    const fetchImpl = answering(500, JSON.stringify({ error: "internal", message: "failed" }));
    await expect(request("/api/state", {}, fetchImpl)).rejects.toMatchObject({ status: 500 });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
```

  And `sentAgain`'s own cases, in a `describe("sentAgain")`:
  - `sentAgain(undefined, new TypeError("x"))` and `sentAgain("get", new TypeError("x"))` are `true`;
  - `sentAgain("POST", new TypeError("x"))` is `false`;
  - `sentAgain(undefined, new DOMException("aborted", "AbortError"))` is `false`.

  Run `npx vitest run src/api/client.test.ts`. Expected: the new cases fail (`sentAgain` is not exported; one send each).
- [ ] **Step 4: The GET's rule,** in `gui/src/api/client.ts`.
  - Above `request`:

```ts
/** Whether a request whose fetch was rejected is sent once more (spec 2026-10-08 §6): a GET,
 * which asks and changes nothing, whose fetch got no answer at all. Never an abort, which the
 * page asked for itself, and never another method, whose effect may have happened before the
 * connection failed. An HTTP answer, a refusal included, never comes here: `fetch` resolves it. */
export function sentAgain(method: string | undefined, error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") return false;
  return (method ?? "GET").toUpperCase() === "GET";
}
```

  - In `request`, replace the single `fetchImpl` call:

```ts
  const send = () =>
    fetchImpl(path, {
      ...init,
      credentials: "omit",
      ...(headers === undefined ? {} : { headers }),
    });
  let response: Response;
  try {
    // Once more where the first got no answer at all (`sentAgain`): on Windows a request was seen
    // refused a socket (`net::ERR_NO_BUFFER_SPACE`, part 19a) while the server answered every
    // other, and a second rejection is the server gone.
    response = await send().catch((error: unknown) => {
      if (!sentAgain(init.method, error)) throw error;
      return send();
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ServerUnreachable(error);
  }
```

  Run `npm test`. Expected: every case passes, at 100 % on all four metrics.
- [ ] **Step 5: The stylesheets' rule, red first.** Create `gui/src/lib/sheets.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import { sheetsToAskAgain } from "./sheets";

describe("sheetsToAskAgain", () => {
  test("asks for nothing when every stylesheet loaded", () => {
    expect(sheetsToAskAgain([{ href: "/a.css", loaded: true }])).toEqual([]);
  });

  test("asks again for each stylesheet that failed, in the page's order", () => {
    expect(
      sheetsToAskAgain([
        { href: "/a.css", loaded: false },
        { href: "/b.css", loaded: true },
        { href: "/c.css", loaded: false },
      ]),
    ).toEqual(["/a.css", "/c.css"]);
  });

  test("asks once for an address two failed links name", () => {
    expect(
      sheetsToAskAgain([
        { href: "/a.css", loaded: false },
        { href: "/a.css", loaded: false },
      ]),
    ).toEqual(["/a.css"]);
  });
});
```

  Run it; expected: it fails, since `./sheets` does not exist.
- [ ] **Step 6: `gui/src/lib/sheets.ts`:**

```ts
/** One of the page's stylesheets as the page found it before drawing: its address, and whether
 * it loaded. */
export interface SheetLoad {
  href: string;
  loaded: boolean;
}

/** The addresses of the page's stylesheets to ask for once more before it draws: those that did
 * not load (spec 2026-10-08 §6). On Windows a stylesheet's request was seen refused a socket
 * (`net::ERR_NO_BUFFER_SPACE`, run 37760106344), and the page then drew unstyled. Each address
 * once, in the page's order, however many links name it. */
export function sheetsToAskAgain(sheets: readonly SheetLoad[]): string[] {
  const again: string[] = [];
  for (const sheet of sheets) {
    if (!sheet.loaded && !again.includes(sheet.href)) again.push(sheet.href);
  }
  return again;
}
```

- [ ] **Step 7: The glue,** `gui/src/app/sheets.ts`:

```ts
import { sheetsToAskAgain } from "../lib/sheets";

/** Asks once more for each of the page's stylesheets that failed to load, and resolves once each
 * such ask has loaded or failed (spec 2026-10-08 §6). Run before the page draws: the module
 * script running this waits for the parser's own stylesheets to load or fail, so a link with no
 * sheet here is one that failed. A second failure leaves the page as it would have been. */
export function askSheetsAgain(document: Document): Promise<void> {
  const links = [...document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')];
  const again = sheetsToAskAgain(
    links.map((link) => ({ href: link.href, loaded: link.sheet !== null })),
  );
  return Promise.all(
    again.map(
      (href) =>
        new Promise<void>((resolve) => {
          const link = document.createElement("link");
          link.rel = "stylesheet";
          link.href = href;
          link.addEventListener("load", () => resolve());
          link.addEventListener("error", () => resolve());
          document.head.append(link);
        }),
    ),
  ).then(() => undefined);
}
```

  - **The premise in its comment is measured, not assumed:** the first journey of Step 1 dies without it. If that journey shows a sheet still loading when this runs (passing only sometimes under `--repeat-each=20`), wait for each link with no sheet to fire `load` or `error` before deciding. Say which in the report.
- [ ] **Step 8: `gui/src/main.tsx`.** Render once the sign-in and the stylesheets have both ended:

```ts
// Signed in, and every stylesheet that failed asked for once more, before anything is rendered:
// no ask goes out without the token, and the page is not drawn unstyled for one lost request.
// Rendered however either ends, so that one that throws still draws the page.
void Promise.allSettled([
  signInFrom(window.location, window.history),
  askSheetsAgain(document),
]).then(() => {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
});
```

- [ ] **Step 9: Run the journeys to see them pass:** `network.spec.ts` with `--repeat-each=20`, after a build: 100 passed. Then every journey: the count before this task, plus its five. `skeleton.spec.ts`'s "the page says so when the server stops" must pass unchanged (Review Focus 1).
- [ ] **Step 10: Ablations,** each into a scratch copy of the package (Global Constraints), each killing a named journey:
  - `sentAgain` always `false`: "a GET the network failed once is sent again" dies;
  - `askSheetsAgain` not called: the two stylesheet-once journeys die;
  - `loaded: link.sheet !== null` replaced by `true`: the same two die.
- [ ] **Step 11: The CHANGELOG.** One entry under `## Unreleased`, in its own style (a bold lead, two spaces between sentences, no line over 95 columns). It says what a reader notices: a page whose stylesheet, or one of whose requests, the network drops once is drawn and answered as if nothing had happened, and a second failure reads as it does today.
- [ ] **Step 12: The gates,** as in Task 1, and the screenshots in Docker in compare mode (no reference may move). Commit: one commit for the GET's rule, one for the stylesheets, one for the journeys and the CHANGELOG.

### Task 3: the start page and the app around every page

**Model:** sonnet, reviewed on sonnet. Each row is a state the page already draws; the journeys reach it with Task 1's helpers.

**Files:**
- Create: `gui/e2e/start.spec.ts`
- Modify: this plan's *The inventory*

**Interfaces:**
- Consumes: `copiedGui`, `failing`, `SERVER_FAILED` (Task 1); the GET's resend (Task 2), which leaves an HTTP error unretried.

**The rows,** as read at `205d5a6`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **No project found** | `copiedGui("demo", empty, { named: false })`, where `empty` removes the copy's contents and leaves its directory (`rmSync` of each entry, then nothing) | Heading "Open a project"; "Found under <the copy's path>"; the paragraph "No project description was found here. Start ddd gui with the path of one." | `StartPage.tsx`'s `found.data.projects.length === 0 ? … : …` inverted |
| **A build record not used** | `copiedGui("demo", record, { named: false })`, where `record` writes `build/ddd-build.json` naming the copy's `demo.ddd.json` with a `"format"` one past `BUILD_INFO_FORMAT`. Read `ddd.lsp.discovery.load_builds` for what a record must hold to reach the format check rather than be skipped silently. | Heading "Build records not used"; an item "<the record's path>: written in format 2 by a newer DDD, and this one understands up to format 1". The project is still listed. | `api.py`'s `refused=[…]` in `Api._projects` made `[]` |
| **Looking for projects** (added: the start page's loading state) | `bareGui`; the `/api/projects` request held by a route until the text is seen | "Looking for projects…", then, released, the list with "DemoDevice" | `StartPage.tsx`'s pending line removed |
| **The projects list failing** | `bareGui`; `failing(page, "/api/projects", "http")` before `goto` | An `alert` reading `SERVER_FAILED`; no list, no heading's list. | `StartPage.tsx`'s `if (found.isError) return <Banner …>` removed |
| **Opening a project failing** | `bareGui`; `failing(page, "/api/open", "http")` once the list shows | Pressing "DemoDevice" leaves the start page in place, with an `alert` reading `SERVER_FAILED`. A `POST` is never resent (Task 2), so one failure is enough. | `StartPage.tsx`'s `{open.isError && <Banner …>}` removed |
| **The signed-out view** | `gui` | The worked journey below. | `client.ts`'s `if (response.status === 401)` branch made never to mark the page signed out |
| **The failure banner a broken answer raises** | `gui`; once the canvas shows, `failing(page, "/api/state", "http")` | The page's long poll is answered `500`. An `alert` reading `SERVER_FAILED` shows above the page, which stays drawn. The stopped banner is not shown: an HTTP answer is no stopped server. | `revisions.ts`'s `if (!(error instanceof ServerUnreachable)) throw error;` made to swallow every error |

- [ ] **Step 1: The worked journey,** in a new `gui/e2e/start.spec.ts`:

```ts
import { expect, test } from "./fixtures";

test("a page whose token the server no longer holds says how to sign in again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  // A token this server never issued, where the page keeps its own (`TOKEN_KEY`, api/token.ts):
  // what a page holds after its server was restarted and handed out another. The address is
  // already `/` (the sign-in replaced it), so the reload trades no code or token of its own.
  await page.evaluate(() => localStorage.setItem("ddd-gui-token", "not-the-token-it-was-given"));
  await page.reload();
  const view = page.getByRole("status").filter({ hasText: "printed in its terminal" });
  await expect(view).toHaveText("Open the address ddd gui printed in its terminal.");
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);
});
```

- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then ablate `client.ts`'s `401` branch in a scratch copy of the package: the journey must die at `toHaveText`.
- [ ] **Step 3: The other rows,** each a journey of its own in `start.spec.ts`, each run and ablated as its row says.
- [ ] **Step 4: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 6: The gates,** every journey included. Commit.

### Task 4: the canvas, and the components table's summary

**Model:** opus, reviewed on opus. The viewport's movements are measured, not read off a string, and the loading states need requests held at the right moment.

**Files:**
- Create: `gui/e2e/canvas.spec.ts`
- Modify: this plan's *The inventory*

**Interfaces:**
- Consumes: `copiedGui`, `failing` (Task 1); `drift`, `renameValueA`, `CONTROLLER` (`gui/e2e/demo.ts`).

**The rows,** as read at `205d5a6`:

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **No dictionary** | `gui`; Controller's file cut in half | The worked journey below. | `GraphPage.tsx`'s `{!graph.data.dictionary && (` made false |
| **Fit** | `gui` | Read the viewport's transform (`.react-flow__viewport`'s `transform` style) as the canvas opens. Zoom in with the wheel over the canvas, and see the transform change. Press "Fit": the transform returns to the one the canvas opened with (`expect.poll`). Fit moves the viewport only, never a module (`openingViewport`, `lib/canvas.ts`). | `GraphPage.tsx`'s `if (view !== null) void flow.setViewport(view, { duration: FLIGHT });` removed |
| **The module search, typed** | `gui` | Type "Sensor" into the textbox "Search modules". SensorHub's `.module` has `data-faded="false"`, and Controller's has `data-faded="true"` (`ModuleNode.tsx`; `.module[data-faded="true"]` is drawn at 0.2 opacity). | `lib/canvas.ts`'s `const faded = bright !== null && !bright.has(node.id);` made `false` |
| **The module search's Enter** | `gui`; the canvas zoomed out first, so the match is off-centre | Type "Sensor" and press Enter. SensorHub's module is centred in the canvas: `expect.poll` on its box's centre against the canvas's centre, within a few pixels, once the 300 ms flight has landed. | `GraphPage.tsx`'s `void flow.fitView({ nodes: [{ id: first }], … })` removed |
| **Hovering a module** | `gui` | Hover Controller's module. Every module that is neither Controller nor one of its neighbours has `data-faded="true"`; Controller and its neighbours have `"false"`. Read the neighbours off the demo's arrows. Moving the pointer away brightens every module again. | the same `fadedNodes` line |
| **The undeclared-variable banner, from an arrow** | `gui`; `drift(gui.directory)` | The arrow's error label (`.flow-label.error`) opens ValueA's panel, as `units.spec.ts`'s "the same disagreement is resolved from its arrow on the canvas" does. Then `renameValueA(gui.directory, "ValueZ")`: the panel closes, and a `status` reads "ValueA is no longer declared in the open project." | `VariablePanel.tsx`'s `const undeclared = …` made `false` |
| **Drawing the project** | `gui`; the first `/api/graph` held by a route until the text is seen | "Drawing the project…", then, released, the modules. | `GraphPage.tsx`'s "Drawing the project…" line removed |
| **Laying the project out** | `gui`; the layout worker's script (`**/assets/layoutWorker-*.js`) held by a route until the text is seen | "Laying the project out…", then, released, the modules. | `layoutAnswers.ts`'s `{ kind: "waiting" }` branch removed |
| **The layout worker failing** (added) | `gui`; the worker's script answered with something that is not JavaScript (`route.fulfill` with a `404`) | "The layout worker stopped; reload the page to try again." (`WORKER_FAILED`, `lib/layoutAnswers.ts`) | `useLayout.ts`'s `onerror` handler made a no-op |
| **The components table's summary while the findings update** | `generatedGui` (an analysis long enough to see); the Table tab | Write a change from outside that the watcher sees. The summary line reads "<errors>, <warnings> · updating" while the analysis runs, then loses " · updating". | `lib/findings.ts`'s `tableLine` dropping `UPDATING` |

- [ ] **Step 1: The worked journey,** in a new `gui/e2e/canvas.spec.ts`:

```ts
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER } from "./demo";
import { expect, test } from "./fixtures";

test("a project with a file that does not load is drawn without arrows, and says why", async ({
  page,
  gui,
}) => {
  // Cut in half, as findings.spec.ts's "a finding that leads nowhere says why" cuts it: no
  // dictionary is resolved while a file of the project does not load (`lsp/diagnostics.py`).
  const path = join(gui.directory, CONTROLLER);
  const bytes = readFileSync(path);
  writeFileSync(path, bytes.subarray(0, Math.floor(bytes.length / 2)));
  await page.goto(gui.address);
  await expect(page.getByRole("status").filter({ hasText: "no dictionary" })).toHaveText(
    "This project has no dictionary, so its modules are drawn without arrows.",
  );
  await expect(page.getByRole("button", { name: "SensorHub", exact: true })).toBeVisible();
  await expect(page.locator(".react-flow__edge")).toHaveCount(0);
});
```

  Read the modules the canvas still draws off the running page. A file that does not load may draw no module of its own.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then the ablation: `GraphPage.tsx`'s dictionary banner made never to show, in a scratch copy of the package. It must die at `toHaveText`.
- [ ] **Step 3: The other rows.** Each is a journey of its own in `canvas.spec.ts`.
  - Every geometric assertion is an `expect.poll` with a stated tolerance. Never a sleep for the 300 ms flight.
  - Each is run with `--repeat-each=10`, because the viewport's animation is the likeliest place for a race.
  - Each is ablated as its row says.
- [ ] **Step 4: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 6: The gates,** every journey included. Commit.

### Task 5: Units and Types

**Model:** sonnet, reviewed on sonnet. The panels' mechanisms are the Units panel's, which journeys already drive.

**Files:**
- Modify: `gui/e2e/types.spec.ts`, `gui/e2e/project-units.spec.ts`, and this plan's *The inventory*

**Interfaces:**
- Consumes: `driftMaxUnseen`, `writeUnseen` (`gui/e2e/demo.ts`); `failing` (Task 1) where a row needs it.

**What the pre-flight corrected** (spec §4 assumed otherwise):
- **The keys a scalar type offers.** Exactly four: datatype, unit, conversion and limits (`SCALAR_KEYS`, `src/ddd/project_types.py`).
- **"State nothing".** Datatype and conversion are required (`type_plans.REQUIRED`), so neither offers it. Only unit and limits can be stated as nothing.
- **Saving the description.** The Types panel has no "Save": a changed description shows "Changes 1 file: types.ddd.json" and "Apply to 1 file", where the Units panel has "Save".

**The rows,** as read at `205d5a6`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **A type's range** | `structuresGui`; Temperature_t (`limits` -40 … 150) | The worked journey below. | `TypePanel.tsx`'s `? limitsRaw(range.min, range.max)` making no request |
| **A type's datatype, picked from its list** | `structuresGui`; Temperature_t | Select the row "Datatype" (it reads "uint16"). The combobox "Datatype of Temperature_t" lists "Datatypes". Pick "sint16": "Changes 1 file: types.ddd.json", "Apply to 1 file", and the file then says `"datatype": "sint16"`. | `src/ddd/variable_keys.py`'s `if key == "datatype": return DATATYPES` returning nothing |
| **No "state nothing" for a required key** | `structuresGui`; Temperature_t | Open the choices of "Datatype" and then of "Conversion" (`ArrowDown`, as `keys.spec.ts`'s "a truth value is typed, confirmed with Enter, and cannot be left unstated" opens them). Neither lists an option "state nothing"; "Unit"'s choices do. | `type_plans.py`'s `REQUIRED` without `"datatype"` |
| **A type's description** | `structuresGui`; Temperature_t | Type into the field "Description" (region "Description"): "Changes 1 file: types.ddd.json", "Apply to 1 file". The file then carries the new description. | `TypePanelView.tsx`'s `props.description !== type.description` disjunct removed from `pending` |
| **A type gone** | `structuresGui`; a type's panel open (Sample_t) | Rewrite `types.ddd.json` from outside, valid, without Sample_t's entry. The panel closes, and a `status` reads "Sample_t is no longer declared in the open project." | `TypePanel.tsx`'s `const gone = … code === "not-found"` made `false` |
| **A type's file half-written** | `structuresGui`; Temperature_t's panel open | Cut `types.ddd.json` in half. The panel stays open, titled Temperature_t, with an `alert`: "'Temperature_t' is not declared in any file that loaded, and types.ddd.json did not load" (`api.py`'s `_undeclared`). Writing the file back whole brings the panel back. Model: `project-units.spec.ts`'s "a unit nothing states any longer…" | `api.py`'s `if unread:` branch removed |
| **A type's Apply refused as out of date** (added) | `structuresGui`; Temperature_t's "Max" filled, "Apply to 1 file" enabled | `driftMaxUnseen(structuresGui.directory, "types.ddd.json", "Temperature_t", 999)`, then press Apply. A `status` reads "A file changed on disk, so nothing was written. The page now shows the files as they are." Then `utimesSync`, as `keys.spec.ts` does; the refusal hides; Apply again writes it. | `TypePanel.tsx`'s `if (error instanceof ApiError && error.code === "stale")` branch removed |
| **The adopt refused** | `gui` (no units file); the Units tab's adopt banner, "Show changes" pressed | Create `units.ddd.json` in the copy by hand (`writeFileSync`, any content), then press "Adopt 5 units". The banner's `adopt-refusal` paragraph reads "A file changed on disk, so nothing was written. The page now shows the files as they are." The server refuses a file to be created that exists already (`editing._created`). | `UnitsPage.tsx`'s `onError` setting the stale refusal made a no-op |

- [ ] **Step 1: The worked journey,** in `gui/e2e/types.spec.ts`:

```ts
test("a type's range is settled from its two fields, and written", async ({
  page,
  structuresGui,
}) => {
  const typesFile = join(structuresGui.directory, TYPES);
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  await panel.getByRole("row", { name: /^Limits/ }).click();
  // The two fields the variable's own panel settles a range with (`KeyChooser`), here on a type.
  await expect(panel.getByLabel("Min")).toHaveValue("-40");
  await panel.getByLabel("Max").fill("120");
  await expect(panel.getByText("Changes 1 file: types.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(() => readFileSync(typesFile, "utf8")).toContain('"max": 120');
});
```

  Read the row's accessible name, and the file's spelling after the write, off the running page and the copy before asserting them.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then the ablation: `TypePanel.tsx`'s planned range made `null`, in a scratch copy of the package. It must die at "Changes 1 file".
- [ ] **Step 3: The other rows,** each a journey of its own: the Types rows in `types.spec.ts`, the adopt in `project-units.spec.ts`. Each is run and ablated as its row says.
- [ ] **Step 4: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 6: The gates,** every journey included. Commit: one commit for the Types rows, one for the adopt.

### Task 6: Shared files

**Model:** opus, reviewed on opus. The largest group, with three panels' worth of fields and the two banners that tell an unreadable file from an untold one.

**Files:**
- Create: `gui/e2e/shared.spec.ts`
- Modify: this plan's *The inventory*

**Interfaces:**
- Consumes: `copiedGui` (Task 1); `writeUnseen` (`gui/e2e/demo.ts`).

**What the pre-flight found:**
- **Only examples/vocabulary declares shared entries.** Constants `TREND_SAMPLES` (16, one use) and `PRESSURE_CELLS` (8, inline in pump.ddd.json, one use). Sections `.fast_ram` (two uses) and `.calib` (one use). Rasters `1ms` (one use), `10ms` (Pump's own default) and `100ms`, **used by nothing**.
- **examples/demo and examples/structures declare none,** so `gui` shows "Declare an entry" with no setup at all.
- **Remove is offered only for an entry nothing uses.** `100ms` is the one such entry as shipped. A constant or a section that nothing uses is either declared first by the form (zero uses), or made by a `copiedGui` change that drops its one use.
- **A truncated file is *untold*; a schema-broken one is *unreadable*.**
  - Truncated, a file no longer parses, so its kind is unknown.
  - Schema-broken, it parses but fails its model, for example `sections.ddd.json`'s alignment made 3.

  Each has its own banner.
- **Each shared file names its entries differently.** `driftMaxUnseen` matches a variable's `"max"`. A shared file's stale journey writes its own same-length change through `writeUnseen`, as `constants.spec.ts`, `sections.spec.ts` and `rasters.spec.ts` define their own file helpers.

**The rows,** as read at `205d5a6`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **A raster nothing uses, removed** | `vocabularyGui` | The worked journey below. | `lib/shared.ts`'s `rasterRemovable` answering `false` |
| **"Declare an entry," and the blank form** | `gui` | The Shared files tab offers "Declare an entry" (no entry declared). Pressing it opens the panel "Declare an entry", whose one field is the combobox "Vocabulary", with "Choose a vocabulary, and the fields it is declared with follow." Picking "constants" retitles it "Declare a constant" and shows "Name". Declaring a constant there (name, value, Apply) lists it. | `SharedPage.tsx`'s `setDeclaring(true)` removed |
| **The add form refused: a name taken** | `vocabularyGui`; the form for a section | Type `.fast_ram`: a `status` reads "'.fast_ram' is already a section this project declares", and no Apply is drawn. | `navigation.py`'s `if name in built.sections: return …` removed |
| **The add form refused: a value no constant may state** | `vocabularyGui`; the form for a constant | Name `SPARE`, value `oops`: "oops is not a value a constant may state, so 'SPARE' cannot take it in constants.ddd.json: …", read whole off the page. | `shared_plans.py`'s `judgement.adapter.validate_python(json.loads(raw))` removed |
| **The add form refused: an event taken** | `vocabularyGui`; the form for a raster | Event `0`: "event 0 is already claimed by raster '1ms'". | `shared_plans.py`'s `_event_taken` answering nothing |
| **A constant's value saved** | `vocabularyGui`; `TREND_SAMPLES` | Region "Value": change it, "Save"; the file states the new value, the table's row shows it. | the Value region's `Save` request made `null` in `ConstantPanel.tsx` |
| **A constant's description saved** | `vocabularyGui`; `TREND_SAMPLES` | Region "Description", "Save"; the file carries it. | the Description region's request made `null` |
| **A constant renamed, and refused onto a name taken** | `vocabularyGui`; `TREND_SAMPLES` | The textbox "Rename TREND_SAMPLES to": `PRESSURE_CELLS` is refused ("'PRESSURE_CELLS' is the name of the declared constant 'PRESSURE_CELLS', which shares c's namespace with the variables"); `TREND_SLOTS` is applied ("Apply to 2 files"), and pump.ddd.json's `PressureTrend` names the new name. | `shared_plans.py`'s `rename_entry` refusal removed (refused half); the rename's request `null` (applied half) |
| **A constant removed** | `copiedGui("vocabulary", …)` with `PressureTrend`'s `"dimensions": ["TREND_SAMPLES"]` made `[16]` | `TREND_SAMPLES` offers "Remove from the constants"; removed, its row goes. A used constant shows "1 shape names TREND_SAMPLES, so it cannot be removed." instead. | `ConstantPanel.tsx`'s `entry.uses.length === 0` made `false` |
| **A section's access, alignment and description saved** | `vocabularyGui`; `.calib` | The combobox "Access" ("read-write"/"read-only"), the textbox "Alignment", the textbox "Description", each with its "Save". | each region's request made `null`, one at a time |
| **A section renamed, and removed** | `vocabularyGui`; `.fast_ram` renamed onto `.calib` is refused ("'.calib' is already a section this project declares"); a fresh section declared by the form is removed ("Remove from the sections") | | `SectionPanel.tsx`'s `entry.uses.length === 0` made `false` |
| **A raster's event, cycle and description saved** | `vocabularyGui`; `100ms` | The textboxes "Event" and "Cycle", and "Description", each with "Save". An event another raster holds is refused ("event 0 is already claimed by raster '1ms'"). | each region's request made `null` |
| **A raster renamed** | `vocabularyGui`; `1ms` renamed onto `10ms` is refused ("'10ms' is already a raster this project declares"); renamed to `2ms`, PumpSpeed's raster follows | | the rename's request `null` |
| **A constant's "Used by" followed** | `vocabularyGui`; `TREND_SAMPLES` | Its Used by row (Where, File, What: "PressureTrend", "pump.ddd.json", "Pump"): the link "PressureTrend" opens Pump's page with PressureTrend's panel. | `ConstantPanelView.tsx`'s `if (use.kind === "variable")` route inverted |
| **A raster's "Used by" followed, to a component** | `vocabularyGui`; `10ms` | Its row reads "Pump", "everything it produces". The link opens Pump's page with no variable's panel. | `lib/shared.ts`'s `rasterUseRoute` branches swapped |
| **An Apply refused as out of date** | `vocabularyGui`; `TREND_SAMPLES`'s value changed, "Save" enabled | `constants.ddd.json` rewritten unseen (`writeUnseen`, same length), then "Save": a `status` in region "Value" reads "A file changed on disk, so nothing was written. The page now shows the files as they are." | `editing.py`'s fingerprint check, in a scratch worktree of the Python |
| **An entry gone** | `vocabularyGui`; `100ms`'s panel open | `rasters.ddd.json` rewritten valid without `100ms`. The panel closes; a `status` reads "100ms is no longer declared in the open project." | `RasterPanel.tsx`'s `code === "not-found"` made `false` |
| **An entry's file half-written** | `vocabularyGui`; `TREND_SAMPLES`'s panel open | `constants.ddd.json` cut in half. The panel stays, with an `alert`: "'TREND_SAMPLES' is not declared in any file that loaded, and constants.ddd.json did not load". Written back whole, the panel shows the constant again. | `api.py`'s `if unread:` branch removed |
| **The untold banner** | `vocabularyGui` | `rasters.ddd.json` cut in half. Above the table, a `status`: "rasters.ddd.json did not load, so whatever is declared there is not listed." | `lib/findings.ts`'s `untold` filter made empty |
| **The unreadable banner** | `vocabularyGui` | `sections.ddd.json`'s `"alignment": 4` made `3` (valid json, a broken model). Above the table: "sections.ddd.json did not load, so the entries declared there are not listed." | `lib/findings.ts`'s `own` filter made empty |

- [ ] **Step 1: The worked journey,** in a new `gui/e2e/shared.spec.ts`:

```ts
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "./fixtures";

/** The rasters file of examples/vocabulary, in its copy. */
const RASTERS = "rasters.ddd.json";

test("a raster nothing measures in is removed, row and panel", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  const row = page.getByRole("row", { name: /^100ms/ });
  await row.click();
  const panel = page.getByRole("complementary", { name: "100ms" });
  await expect(panel.getByText("Nothing in the project measures in 100ms.")).toBeVisible();

  const removing = panel.getByRole("region", { name: "Remove from the rasters" });
  await removing.getByRole("button", { name: "Remove from the rasters" }).click();
  await expect(row).toHaveCount(0);
  await expect(panel).toHaveCount(0);
  await expect
    .poll(() => readFileSync(join(vocabularyGui.directory, RASTERS), "utf8"))
    .not.toContain('"100ms"');
});
```

  Read `project-units.spec.ts`'s removal of a unit nothing states before writing it. A Remove may first show its plan and ask for "Apply to 1 file": follow the running page, and assert what it shows.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then the ablation: `rasterRemovable` answering `false`, in a scratch copy of the package. It must die at the region's button.
- [ ] **Step 3: The other rows,** each a journey of its own in `shared.spec.ts`. Group a panel's fields into one journey where a reader would do them in one sitting, but keep one assertion per row, so each row's ablation kills it. Each is run and ablated as its row says.
- [ ] **Step 4: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 6: The gates,** every journey included. Commit: one commit per panel's rows, and one for the banners.

### Task 7: Files and Findings

**Model:** sonnet, reviewed on sonnet. Each row is a state the two tabs already draw.

**Files:**
- Modify: `gui/e2e/files.spec.ts`, `gui/e2e/findings.spec.ts`, and this plan's *The inventory*

**Interfaces:**
- Consumes: `failing`, `SERVER_FAILED` (Task 1); `drift`, `unstamp`, `writeUnseen`, `CONTROLLER`, `UNITS` (`gui/e2e/demo.ts`).

**What the pre-flight corrected:**
- **A file brings errors only, never a warning.** `ddd.file_plans.new_errors` lists errors only, so the preview's chips are always `error`.
- **The Files tab writes only the project description.** Its three actions change `project.ddd.json` alone. So a Files out-of-date journey makes the description change unseen (`writeUnseen`, same length), not a component file.

**The rows,** as read at `205d5a6`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **A finding no longer reported** | `gui`; `drift(gui.directory)` | The worked journey below. | `lib/findings.ts`'s `selectionAfter` answering `gone: false` |
| **A fix's Apply refused as out of date** | `gui`; `unstamp(gui.directory, CONTROLLER, "ValueA")`, as `findings.spec.ts`'s "a missing id is fixed" does | Choose the fix, "Show changes". Then a route on `**/api/edit` writes Controller's file unseen before letting the request through, as `skeleton.spec.ts`'s "an edit made from a page that is out of date is refused, and the file reloaded" does. In the panel, a `status`: "A file changed on disk, so nothing was written. The tab now shows the findings as they are." (`FindingsPage.tsx`'s own `STALE`: "The tab", and "the findings"). | `FindingsPage.tsx`'s `error.code === "stale"` branch removed |
| **The fixes a finding carries failing** | `gui`; `unstamp(…)`; `failing(page, "/api/fix", "http")` before the finding is selected | Beside the panel, an `alert` reading `SERVER_FAILED`. | `FindingsPage.tsx`'s `{fixes.isError && <Banner …>}` removed |
| **The page of findings failing** | `gui`; `drift(…)`; `failing(page, "/api/findings", "http")` before the tab opens | An `alert` reading `SERVER_FAILED` above the table. | `FindingsPage.tsx`'s `unasked` banner removed |
| **A Files action refused as out of date** | `vocabularyGui`; the units row's Remove offered | A route on `**/api/edit` rewrites `project.ddd.json` unseen (`writeUnseen`, one space traded for one character), then lets it through. In region "Remove from the includes", a `status`: "A file changed on disk, so nothing was written. The page now shows the files as they are." | `lib/refusals.ts`'s `isStale` answering `false` |
| **The findings a file would bring** | `vocabularyGui`; before `goto`, a new component file in the copy that reads a variable nothing produces | "Add a file" with its name. The preview lists a `missing-producer` chip, the file, and "'<name>' is read by component '<component>' but no component declares it as output" (`analysis.py`'s own words). | `FileActionsView.tsx`'s `{preview.brought.length > 0 && (` made false |
| **The list failing at first** | `vocabularyGui`; `failing(page, "/api/files", "http")` before the tab opens | Only an `alert` reading `SERVER_FAILED`: no "New file", no table. | `FilesPage.tsx`'s early `if (files.isError) return <Banner …>` removed |
| **The list failing later** | `vocabularyGui`; the tab open, its table drawn; then `failing(page, "/api/files", "http")`, then a change from outside that the watcher sees | The table stays drawn, with an `alert` reading `SERVER_FAILED` above it (`placeholderData` keeps the last list). | `FilesPage.tsx`'s `{files.isError && <Banner …>}` above the table removed |

- [ ] **Step 1: The worked journey,** in `gui/e2e/findings.spec.ts` (add `writeFileSync` to its `node:fs` import, and `drift`, `CONTROLLER` to its `./demo` import if absent):

```ts
test("a finding fixed from outside while its panel is open is no longer reported, and the tab says so", async ({
  page,
  gui,
}) => {
  // Controller's own reading of ValueA drifted, as "a disagreement leads to its variable" drifts
  // it: a definition-mismatch is filed on each file it concerns.
  const before = drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page.getByRole("row", { name: /definition-mismatch/ }).first().click();
  await expect(page.getByRole("complementary")).toBeVisible();

  // Put back from outside, as somebody fixing it in their editor would: the watcher sees it, the
  // analysis no longer reports the finding, and the tab says so where the panel was.
  writeFileSync(join(gui.directory, CONTROLLER), before);
  await expect(page.getByRole("status").filter({ hasText: "no longer reported" })).toHaveText(
    "This finding is no longer reported.",
  );
  await expect(page.getByRole("complementary")).toHaveCount(0);
});
```

  Read the panel's accessible name off the running page, and narrow `complementary` to it.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then the ablation: `selectionAfter` answering `gone: false`, in a scratch copy of the package. It must die at `toHaveText`.
- [ ] **Step 3: The other rows,** each a journey of its own: the Findings rows in `findings.spec.ts`, the Files rows in `files.spec.ts`. Each is run and ablated as its row says.
- [ ] **Step 4: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 6: The gates,** every journey included. Commit: one commit for the Findings rows, one for the Files rows.

### Task 8: Compare

**Model:** sonnet, reviewed on sonnet. The tab's one journey is extended with its finding panel, its renames, its refusals and its busy state.

**Files:**
- Modify: `gui/e2e/compare.spec.ts`, and this plan's *The inventory*

**Interfaces:**
- Consumes: `dump`, `driftDatatypeIn`, `renameValueA`, `SENSOR_HUB` (`gui/e2e/demo.ts`).

**What the pre-flight found:**
- **No busy text.** While a comparison runs, the tab draws no text saying so. The field "Baseline" and the button "Compare" are disabled. With no `placeholderData`, the reply's verdict, table and renames are gone until the answer comes.
- **A refusal holds the system's own words.** Every refusal reads `the baseline '<path>' …` and ends in the system's own words: an `OSError`'s text, or the json parser's. Those words differ between Linux and Windows.

**The rows,** as read at `205d5a6`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **A baseline refused, four ways** | `gui`; `shape.json` (`{"neither": true}`) written into the copy | The worked journey below: not found, not json, of the wrong shape, outside the root. | `CompareView.tsx`'s `{refusal !== null && <Banner …>}` removed |
| **A row opens its finding** | `gui`; `dump(…, "baseline.json")`, then `driftDatatypeIn(gui.directory, SENSOR_HUB, "ValueA", "uint16")`, as the tab's existing journey does | Compare, then press the row "changed-interface" in the table "Findings": a panel opens beside it with the finding's message. | `CompareView.tsx`'s `row = rows.find(…)` never matching |
| **That finding's route followed** | the same | In that panel, the link "Open ValueA" leads to the component page with ValueA's panel open. | `CompareView.tsx`'s `onOpen` made a no-op |
| **The renamed objects** | `gui`; `dump(…)`, then `renameValueA(gui.directory, "ValueZ")` | Compare: under the heading "Renamed objects", a row reading ValueA's id, "ValueA", "ValueZ" (columns "Id", "From", "To"). Before any rename, the heading's paragraph reads "Nothing was renamed." | `CompareView.tsx`'s `reply.renames.length === 0 ? …` inverted |
| **The busy state** | `gui`; `dump(…)`; the `/api/compare` request held by a route | While held, "Baseline" and "Compare" are disabled and no verdict shows. Released, the verdict "This project can replace the baseline." shows and both are enabled again. | `ComparePage.tsx`'s `busy={stopped \|\| compare.isFetching}` made `busy={stopped}` |

- [ ] **Step 1: The worked journey,** in `gui/e2e/compare.spec.ts` (add `writeFileSync` from `node:fs`, `join` and `posix`-separated paths from `node:path`):

```ts
/** `path` as the server writes a path into a refusal: absolute, with forward slashes. */
function posixOf(path: string): string {
  return path.replaceAll("\\", "/");
}

/** A whole sentence's start, as a pattern: the page's own words, up to where the system's own
 * begin - an OSError's text or the json parser's, which differ between Linux and Windows. */
function startingWith(words: string): RegExp {
  return new RegExp(`^${words.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`);
}

test("a baseline missing, not json, of the wrong shape or outside the root is refused in words of its own", async ({
  page,
  gui,
}) => {
  writeFileSync(join(gui.directory, "shape.json"), JSON.stringify({ neither: true }));
  const root = posixOf(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  const baseline = page.getByRole("textbox", { name: "Baseline" });
  const compare = page.getByRole("button", { name: "Compare" });
  const refusal = page.getByRole("alert");

  await baseline.fill("missing.json");
  await compare.click();
  await expect(refusal).toHaveText(
    startingWith(`the baseline '${root}/missing.json' is unreadable: `),
  );

  await baseline.fill("include/sensor_hub_driver.h");
  await compare.click();
  await expect(refusal).toHaveText(
    startingWith(`the baseline '${root}/include/sensor_hub_driver.h' is not valid json: `),
  );

  await baseline.fill("shape.json");
  await compare.click();
  await expect(refusal).toHaveText(
    startingWith(`the baseline '${root}/shape.json' is neither a dictionary nor a description: `),
  );

  // Confinement is checked before anything is read: the file need not exist.
  await baseline.fill("../outside.json");
  await compare.click();
  const outside = posixOf(join(gui.directory, "..", "outside.json"));
  await expect(refusal).toHaveText(
    `the baseline '${outside}' is outside the session root '${root}'`,
  );
});
```

  - Read each sentence off the running page on Linux before asserting it.
  - Check how the server spells the copy's path: it resolves it, so a symlinked `/tmp` may differ. Build `root` from what the page shows if it does.
  - The outside-the-root sentence has no system words, so it is asserted whole.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then the ablation: the refusal's banner removed, in a scratch copy of the package. It must die at the first `toHaveText`.
- [ ] **Step 3: The other rows,** each a journey of its own in `compare.spec.ts`, each run and ablated as its row says.
- [ ] **Step 4: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 6: The gates,** every journey included. Commit.

### Task 9: a component and its values

**Model:** sonnet, reviewed on sonnet. The rows reuse mechanisms other journeys already prove (`driftMaxUnseen`, a truncated file, `failing`).

**Files:**
- Modify: `gui/e2e/declarations.spec.ts` (a component's rows), `gui/e2e/values.spec.ts` (the values' row), and this plan's *The inventory*

**Interfaces:**
- Consumes: `failing`, `SERVER_FAILED` (Task 1); `driftMaxUnseen`, `drift`, `openValues`, `CONTROLLER` (`gui/e2e/demo.ts`).

**The rows,** as read at `205d5a6`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **A dimension removed** | `gui` | Controller, "Add a declaration", a new name, kind `value_block`. Fill "Dimension 1 of <name>", press "Add a dimension", fill "Dimension 2 of <name>", then press "Remove dimension 1 of <name>". The one row left reads the second value, now "Dimension 1 of <name>", and its own "Remove dimension 1 of <name>" is disabled (a shape keeps one). Model: `declarations.spec.ts`'s "a value block is declared with the shape it is given". | `DimensionsField.tsx`'s `onPress={() => onRows(shown.filter((_, at) => at !== index))}` filtering nothing |
| **A finding's link to a variable of the same file, opened in place** | `gui`; `drift(gui.directory)` once the page shows Controller | Controller's page. Under "Findings in this component", the `definition-mismatch` item's message is a link. Before pressing it, set a marker on `window` (`page.evaluate`). Pressing it opens ValueA's panel (`complementary` "ValueA"), the grid "Declarations of Controller" stays drawn, and the marker is still there: the same document, no page load. | `ComponentPage.tsx`'s `const onClick = inThisFile === null ? undefined : followVariable(inThisFile);` made `undefined` (the link then navigates, and the marker is gone) |
| **The component's file not json** | `gui`; Controller's file cut in half (`writeFileSync(path, bytes.subarray(0, Math.floor(bytes.length / 2)))`, as `findings.spec.ts`'s "a finding that leads nowhere says why" does) once the page shows the canvas | Controller's page shows only an `alert`: "<the file's absolute path> is not json: <the parser's words>" (`session.py`'s `read_file`). No heading, no table. | `ComponentPage.tsx`'s `if (content.data.error !== null) return <Banner …>` removed |
| **The component's file failing to load** | `gui`; `failing(page, "/api/file", "http")` before pressing Controller | The page shows only an `alert` reading `SERVER_FAILED`. | `ComponentPage.tsx`'s `if (content.isError) return <Banner …>` removed |
| **A component no longer in the project** (added row: a stale bookmark) | `gui`; open `/component?file=<a path under the copy that no include names>` by its address | The page shows only an `alert`: "<path> is not a description file of the open project" (`session.py`, answered `404`). | the same `content.isError` line |
| **A declaration refused as out of date** | `gui` | The worked journey below. | `DeclarePanel.tsx`'s `onError: (error) => setRefusal(refusalOf(error))` made a no-op |
| **A declaration's removal refused as out of date** | `gui` | Controller, ValueB's row (as `declarations.spec.ts`'s removal journey selects it), wait for "Remove from Controller" to be enabled. `driftMaxUnseen(gui.directory, CONTROLLER, "ValueA", 999)`, press it. Under `region` "Remove the declaration", a `status` reads "A file changed on disk, so nothing was written. The panel now shows the files as they are." (`VariablePanel.tsx`'s `STALE`: "The panel", where the other panels say "The page"). Then `utimesSync`, as `keys.spec.ts` does; the refusal hides within 15 s; press again: ValueB's row is gone. | `VariablePanel.tsx`'s `setRemovalStale({ text: STALE, revision })` made a no-op |
| **A value's Apply refused as out of date** | `gui`; `openValues(page, gui.address, "CurveA")` | Fill "element 3" with a new value, wait for "Apply to 1 file" (as `values.spec.ts`'s "a cell changed is written to the producer's file"). `driftMaxUnseen(...CONTROLLER, "ValueA", 999)`, press Apply. Under `region` "Set the cell", a `status` reads "A file changed on disk, so nothing was written. The page now shows the files as they are." Then `utimesSync`, the refusal hides, Apply again: the cell is written. | `ValuesPage.tsx`'s `setStaleFailed({ text: refusalOf(error), revision })` made a no-op |

- [ ] **Step 1: The worked journey,** in `gui/e2e/declarations.spec.ts` (add `utimesSync` to its `node:fs` import, and `driftMaxUnseen` to its `./demo` import):

```ts
test("a declaration made from a file that changed on disk is refused, and made once the page has caught up", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("ValueC");
  await name.press("Enter");
  await expect(adding.getByText("Reads ValueC as SensorHub declares it.")).toBeVisible();
  const apply = adding.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();

  // Controller changes under the plan the panel holds, unseen by the session's watcher, as
  // keys.spec.ts's own stale journey changes it: only the Apply's own fingerprint check sees it.
  driftMaxUnseen(gui.directory, CONTROLLER, "ValueA", 999);
  await apply.click();
  await expect(adding.getByRole("status")).toHaveText(
    "A file changed on disk, so nothing was written. The page now shows the files as they are.",
  );
  await expect(apply).toHaveCount(0);

  // A stamp moved with no byte touched is what lets the next poll read the drifted file. The
  // analysis landing shows as the disagreement the drift made, in Controller's own findings.
  const path = join(gui.directory, CONTROLLER);
  const now = new Date();
  utimesSync(path, now, now);
  await expect(
    page.getByRole("link", { name: /'ValueA' is declared differently by component 'Controller'/ }),
  ).toBeVisible({ timeout: 15000 });

  // Asked again, against the files as they are now: the refusal goes with the edit, and the
  // declaration is made.
  await name.fill("ValueC");
  await name.press("Enter");
  await adding.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByRole("complementary", { name: "ValueC" })).toBeVisible();
});
```

  The disagreement's link text is read off the running page before it is asserted, and the regex is narrowed to it.
- [ ] **Step 2: Run it** after a build, and with `--repeat-each=10`. Then the ablation: `DeclarePanel.tsx`'s `onError` made a no-op, in a scratch copy of the package. It must die at the `status`'s `toHaveText`.
- [ ] **Step 3: The other rows** of the table, each a journey of its own in the named file, each run, each ablated as its row says.
- [ ] **Step 4: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason.
- [ ] **Step 6: The gates,** every journey included. Commit: one commit for a component's rows, one for the values' row.

### Task 10: the final hunt, the figures, the gate and the close-out

**The controller's own.**

- [ ] **Step 1: The inventory complete.** Every row names a journey or a reason. Count them by screen for *Figures*.
- [ ] **Step 2: Push,** after the bidi scan, and start the final hunt (`-f repeat=5`). It must pass with no failure on all three legs.
  - A failure is worked at its cause, as part 19a's Task 3 worked them, and never retried.
  - Its report may be downloaded, by the maintainer's leave (*Global Constraints*).
- [ ] **Step 3: A full run** (`-f repeat=1`) at the head, with every job green, its six Python legs and three gui legs recorded in *Figures* with the journeys' time per leg.
- [ ] **Step 4: The milestone gate** at the head, each exit status captured.
- [ ] **Step 5: Close the plan out:**
  - an *As built* note under the header;
  - *Figures*;
  - the progress log;
  - *What was left open*;
  - *Rulings taken*.

## The inventory

Every action a reader can take in `ddd gui`, and every state a reader can meet, with the journey that covers it or the reason none does (spec §4). These are the starting rows, from part 19's survey and this plan's pre-flight at `205d5a6`. Task 1 checks each against the tree and adds what the survey missed. Each later task fills in its own rows' journeys.

| Screen | Row | Task | Journey |
| --- | --- | --- | --- |
| The journeys | `files.spec.ts`'s Remove-ordering wait, without `waitForResponse` | 1 | none yet |
| The network | the page's stylesheet failed once | 2 | none yet |
| The network | the pressable rule's stylesheet failed once | 2 | none yet |
| The network | a stylesheet failing every time | 2 | none yet |
| The network | a GET failed once | 2 | none yet |
| The network | a GET failing every time | 2 | none yet |
| The start page | no project found | 3 | none yet |
| The start page | a build record not used | 3 | none yet |
| The start page | looking for projects | 3 | none yet |
| The start page | the projects list failing | 3 | none yet |
| The start page | opening a project failing | 3 | none yet |
| The app | the signed-out view | 3 | none yet |
| The app | the failure banner a broken answer raises | 3 | none yet |
| The canvas | no dictionary | 4 | none yet |
| The canvas | Fit | 4 | none yet |
| The canvas | the module search, typed | 4 | none yet |
| The canvas | the module search's Enter | 4 | none yet |
| The canvas | hovering a module | 4 | none yet |
| The canvas | the undeclared-variable banner, from an arrow | 4 | none yet |
| The canvas | drawing the project | 4 | none yet |
| The canvas | laying the project out | 4 | none yet |
| The canvas | the layout worker failing | 4 | none yet |
| The components table | its summary while the findings update | 4 | none yet |
| Units | the adopt refused | 5 | none yet |
| Types | a type's range | 5 | none yet |
| Types | a type's datatype, picked from its list | 5 | none yet |
| Types | no "state nothing" for a required key | 5 | none yet |
| Types | a type's description | 5 | none yet |
| Types | a type gone | 5 | none yet |
| Types | a type's file half-written | 5 | none yet |
| Types | a type's Apply refused as out of date | 5 | none yet |
| Shared files | a raster nothing uses, removed | 6 | none yet |
| Shared files | "Declare an entry", and the blank form | 6 | none yet |
| Shared files | the add form refused: a name taken | 6 | none yet |
| Shared files | the add form refused: a value no constant may state | 6 | none yet |
| Shared files | the add form refused: an event taken | 6 | none yet |
| Shared files | a constant's value saved | 6 | none yet |
| Shared files | a constant's description saved | 6 | none yet |
| Shared files | a constant renamed, and refused onto a name taken | 6 | none yet |
| Shared files | a constant removed | 6 | none yet |
| Shared files | a section's access, alignment and description saved | 6 | none yet |
| Shared files | a section renamed, and removed | 6 | none yet |
| Shared files | a raster's event, cycle and description saved | 6 | none yet |
| Shared files | a raster renamed | 6 | none yet |
| Shared files | a constant's "Used by" followed | 6 | none yet |
| Shared files | a raster's "Used by" followed, to a component | 6 | none yet |
| Shared files | an Apply refused as out of date | 6 | none yet |
| Shared files | an entry gone | 6 | none yet |
| Shared files | an entry's file half-written | 6 | none yet |
| Shared files | the untold banner | 6 | none yet |
| Shared files | the unreadable banner | 6 | none yet |
| Findings | a finding no longer reported | 7 | none yet |
| Findings | a fix's Apply refused as out of date | 7 | none yet |
| Findings | the fixes a finding carries failing | 7 | none yet |
| Findings | the page of findings failing | 7 | none yet |
| Files | an action refused as out of date | 7 | none yet |
| Files | the findings a file would bring | 7 | none yet |
| Files | the list failing at first | 7 | none yet |
| Files | the list failing later | 7 | none yet |
| Compare | a baseline refused: not found, not json, of the wrong shape, outside the root | 8 | none yet |
| Compare | a row opens its finding | 8 | none yet |
| Compare | that finding's route followed | 8 | none yet |
| Compare | the renamed objects | 8 | none yet |
| Compare | the busy state | 8 | none yet |
| A component | a dimension removed | 9 | none yet |
| A component | a finding's link to a variable of the same file, opened in place | 9 | none yet |
| A component | its file not json | 9 | none yet |
| A component | its file failing to load | 9 | none yet |
| A component | a component no longer in the project | 9 | none yet |
| A component | a declaration refused as out of date | 9 | none yet |
| A component | a declaration's removal refused as out of date | 9 | none yet |
| Values | an Apply refused as out of date | 9 | none yet |

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

### The inventory

Filled in by Task 10: by screen, the rows covered before this part, the rows covered after it, and the rows with a reason instead.

| screen | rows | covered before | covered after | with a reason |
| --- | --- | --- | --- | --- |

### The journeys' time

Before: part 19a's pull request run 37787987752 (ubuntu chromium 93 journeys in 3.6 min, windows chromium 94 in 3.7 min, windows msedge 93 in 3.9 min). After: Task 10's full run.

| leg | journeys before | time before | journeys after | time after |
| --- | --- | --- | --- | --- |

### The final hunt

Filled in by Task 10.

| leg | runs | failures |
| --- | --- | --- |

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |

## What was left open

Filled in as the work goes. Known before execution:
- **Firefox, Safari and macOS** (spec §11).
- **The user guide,** part 20.
- **P19a-7's question,** how long a refusal held stale shows, unless the maintainer answers it.
- **A fix that needs a design decision,** each recorded by the task that found it.

## Rulings taken

Taken while planning; execution adds its own below them.

1. **The inventory lives in this plan, and starts from the pre-flight's rows** (spec §4). The pre-flight read every screen the spec names at `205d5a6` and added rows the survey missed: the start page's loading state, the layout worker failing, a type's Apply out of date, a component no longer in the project, a declaration's removal out of date. Task 1 checks them all again — cost if wrong: none.
2. **Task 2 comes before every screen's task.** A network banner's journey depends on whether a GET is sent again — cost if wrong: none.
3. **An error banner from an HTTP failure is reached with `failing`'s `"http"`,** which answers the server's own error body (`SERVER_FAILED`). A network banner's request fails every time — cost if wrong: a banner shown for a body the server never sends.
4. **A refusal whose sentence ends in the system's own words** (an `OSError`'s text, the json parser's) is asserted whole up to those words, as its start. Those words differ between Linux and Windows — cost if wrong: a change to the system's words goes unpinned, which is not the page's to pin.
5. **The Compare tab's busy state is asserted by what the page does,** the field and the button disabled and the reply gone, since it draws no busy text — cost if wrong: none.
6. **The pre-flight's corrections stand over the spec's rows** (Tasks 5 to 8):
   - a scalar type offers four keys, two of them required;
   - the Types panel applies, where the Units panel saves;
   - a file brings errors only;
   - the Files tab writes the project description alone;
   - a truncated shared file is untold, a schema-broken one unreadable.

   Cost if wrong: none; each was read from the code.
7. **Models:** opus for Tasks 1, 2, 4 and 6, sonnet for 3, 5, 7, 8 and 9. Reviews on opus for 1, 2, 4 and 6, sonnet for the rest. The final whole-branch review on opus — cost if wrong: a cheaper reviewer missing a vacuous journey, which each journey's named ablation guards against.
8. **Only the controller pushes,** and only this branch, by the maintainer's leave of 2026-10-09 — cost if wrong: a slower loop.

### Taken during execution
