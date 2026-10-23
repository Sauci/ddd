# Part 19c: the earlier pre-flight, kept as evidence

This file holds the pre-flight that an earlier plan for part 19c was written from. That plan was `2026-10-13-gui-journeys-every-state.md`, on the local branch `feature/gui-journeys-every-state` (`fd04f59`), never pushed. It was retired on 2026-10-21, by the maintainer's choice, in favour of this branch's spec and plan. Nothing in this file is a task to execute.

- **How the pre-flight was made.** Six read-only agents worked at master `2bc00da`. They read every one of the 88 rows against the code, drafted its journey, and ran the draft ten times on the compiled page. They killed it with a named change made in a scratch copy of the package, and wrote down what each saw. The drafts are the code below.
- **What it is for.** Each task of `2026-10-21-gui-journeys-remaining.md` that writes rows points here (that plan's ruling 18). Before writing a row's journey, read this file's draft for it: its setup, the words it read off the page, and the change that killed it. Then write the journey with that plan's helpers and fixtures. A draft is evidence that a state is reached and can fail, not code to paste.
- **What differs.**
  - "Task N" inside a section below means the retired plan's task. Its Task 1 added `held`, `failing`'s method, `REFUSED`, `moveStamp` and `editJson`.
  - This branch's plan has `held` (with `every` and `onAnswer`) and `restamp` in their place.
  - It has the fixtures `openedGui` and `chainedGui`, where the retired plan wrote `launchedGui` and `writeChain`.
  - The retired plan's rulings (P19c-1 to P19c-23) do not hold here: this branch numbers its own rulings from P19c-1.
  - Line numbers are those of `2bc00da`.
- **What this branch takes from it** (its ruling 18):
  - four contained bugs;
  - nine rows no row had named;
  - the drafts below.

## A. The rows, screen by screen

### A.1 The start page and the app, rows 1 to 8

**Model:** opus, reviewed on opus. It adds the launched browser's fixture, whose proof is a Windows leg, the helper every stopped-server journey of Task 7 stands on, and a change to a server function held to 100 % branch coverage.

**Files:**
- Modify: `gui/e2e/demo.ts`, `gui/e2e/fixtures.ts`, `gui/e2e/start.spec.ts`, `src/ddd/gui/session.py`, `tests/test_gui_session.py`, `docs/developer_documentation.rst`, `CHANGELOG.md`, and this plan's *The inventory*

**Interfaces:**
- Consumes, from Task 1, in `gui/e2e/demo.ts`:
  - `held(page: Page, path: string | RegExp | ((url: URL) => boolean)): Promise<() => void>`;
  - `moveStamp(directory: string, file: string): void`;
  - `failing(page, path, how, times?, method?)`, here without a method, and `SERVER_FAILED`.
- Produces:
  - `writeBuildRecord(directory: string, subdirectory: string, body: object): string`, in `demo.ts`;
  - `stopping(page: Page, directory: string, file?: string): Promise<Outage>`, in `demo.ts`, with `interface Outage { failed: () => number; ends: () => void }`: Task 7 stands on it;
  - the fixture `launchedGui: LaunchedGui`, in `fixtures.ts`, with `interface LaunchedGui extends Gui { opened: () => Promise<string> }`;
  - private to `fixtures.ts`: `LAUNCHER`, the `python -c` program, and `addressIn(file: string): Promise<string>`, which waits for the address a launch writes.

**What the pre-flight found:**
- **The page signs itself in before it draws anything.** `main.tsx` waits for `signInFrom`, whose last step is `GET /api/session`, and only then renders `App`. A hold or a failure registered before the first `goto(address)` meets that ask and not the app's: the page stays blank, with no "Connecting…" (measured, `#root` empty), or fails twice. Rows 5 and 6 therefore sign in first, register afterwards and `reload()`: the address is `/project` then, nothing signs in again, and the app's own ask is the only one.
- **Row 2's project is reached through a build record.** The search for projects lists a `*.ddd.json` only if it parses as an object with an object `project` (`_is_project`, `session.py`), so a description that does not parse is offered only by a record (`find_projects` joins the projects the records name with the ones the search finds). Its name is then null, and the page says "Unnamed project". The journey goes on to press it and meets the server's real refusal, 409 `not-a-project`. A description that parses and states no `name` is listed as unnamed too, with no record; it draws the same line and is not written.
- **Rows 1 and 2 keep a copy each.** Their ablations must not meet: row 2's journey looks at no image.
- **Row 3 needs no extra project.** The demo's list holds two, DemoDevice and its sub-project Logging, which is what "the list's buttons" needs.
- **Row 4 is reached by a launcher, not a browser** (P19c-15). `launchedGui` starts `ddd gui` as a reader does, without `--no-browser`, through `python -c`: a one-line launcher that replaces `webbrowser.open` by a function writing the address it is handed to a file, then runs `ddd.cli.main(["gui", project])`. `run` hands `launched` the `webbrowser.open` it finds when it starts the thread, so the server, the one-time code and the page are the real ones; only the browser is not. The `BROWSER` variable is not used: a Windows `.cmd` recorder is unproven, and the launcher has no platform branch. The first Windows leg proves it.
- **Row 6 is written in its HTTP flavour.** Its network flavour reads "ddd gui is not answering" from the same line, and `network.spec.ts`'s "a GET the network fails every time reads as the server not answering" pins that sentence for `/api/graph`.
- **Row 7 has two draw sites,** the project's tabs and a component's page, hence two journeys. Its slow-first-analysis variant is not written (P19c-14): what `analysed` decides is under Vitest (`updating.test.ts`), and these two pin the draw sites.
- **Row 8 cannot be a real stop and start.** A restarted server hands out another token, so the page would be signed out (401), not recovered. It is reached by `stopping`, which tells the page the server stopped as a network that fails would: every request for the state fails (`failing`) until the journey calls `ends()`, and a project file's stamp is moved at once, so that the long poll in flight is answered and the ask that follows is the one that fails. The page sends a GET once more and asks again 250 ms after an ask that got no answer, so it says the server stopped after the fourth failed request (measured about 1.3 s after the touch), and asks again every 2 s. `ends()` lets the next ask through and moves the stamp once more: that ask is a long poll, answered at once because the server's version has moved past the one the page holds, so the banner is lifted at most 2 s after the call. Every other request goes on to the server. What `followStates` decides is under Vitest (`revisions.test.ts`), so this journey pins the wiring: the banner and the page's write buttons read the same `stopped` state, and the journey ends on a write's button, "Add a declaration", enabled again (Review Focus 5: no screen is left read-only after an outage); its ablation is in `app/`.
- **The bug** (P19c-10): a build record with no image (`ddd build-info` without `--image` writes `"image": ""`, and CMake always passes one) lists `images: [""]`, which the page prints as "built as" with nothing after it; two build trees configured for one image list it twice. The fix is in `find_projects`, with pytest cases, not in the page. The data is wrong at the source: `FoundProject.images` is "the build images a build record names this project for", the page prints what it is given, and a page fix would need a library function and a Vitest case to second-guess a list the server should not have sent. `find_projects` is one function, and the suite holds it at 100 % line and branch. Row 1's journey is red against the bug first.
- **Paths in sentences.** The path in a project's button is `as_posix()` of the resolved description, with forward slashes on Windows too. The path in the refusal of row 2 is `str(Path)` (`Session.open`'s `ValueError(f"{project} is not a project description")`): backslashes on Windows. The journey asserts the whole sentence, the path built with `join` as the server's `str(Path)` writes it, native separators and all (ruling P19c-23). Part 19b's `declarations.spec.ts` not-json journey asserts a sentence of that kind whole on every leg, from a copy under `gui/test-results`, where no short directory name arises.
- **Existing coverage.** `start.spec.ts`'s journeys cover an empty directory, a record in a format too new, "Looking for projects…", the list failing, the open failing, the signed-out view and the long poll's HTTP failure; `skeleton.spec.ts`'s "without a project the start page lists the ones found and opens the one chosen" opens a project and looks at no button while it does; `skeleton.spec.ts`'s "the page says so when the server stops" sees the banner appear and never go.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **a project listed with the images its build records name** (row 1) | `copiedGui("demo", …, { named: false })`, its change writing four format-1 records with `writeBuildRecord`: the demo with image `firmware` (`build/a`), with `tests` (`build/b`), with `firmware` again from a second build tree (`out`), and Logging with no image (`build/c`). | `StartPage.tsx`'s `{project.images.length > 0 && (<span className="quiet">built as {project.images.join(", ")}</span>)}`. The heading "Open a project"; the demo's button holds exactly "built as firmware, tests", each image once and in the records' order; Logging's holds no text starting "built as". Before the fix: "built as firmware, tests, firmware", and "built as" alone. | `StartPage.tsx`'s `{project.images.length > 0 && (` to `{false && (` dies at the demo's text. In `find_projects`, `if info.image and info.image not in named:` to `if info.image:` dies at the demo's text, and to `if info.image not in named:` at Logging's. |
| **a project whose description does not load, listed as an unnamed project** (row 2) | `copiedGui("demo", …, { named: false })`, its change cutting `demo.ddd.json` to its first half and writing a format-1 record that names it, image `bench`. | `StartPage.tsx`'s `<span className="name">{project.name ?? "Unnamed project"}</span>`. The button `/^Unnamed project/` holds "demo.ddd.json"; there is no button `/DemoDevice/`. Pressed: the list stays, and an `alert` ends " is not a project description" and holds "demo.ddd.json" (409 `not-a-project`; the path in it is `str(Path)`). | `{project.name ?? "Unnamed project"}` to `{project.name ?? ""}` dies at the button's name. |
| **a project opening, the list's buttons held until it has** (row 3) | `bareGui`: the demo opened on the start page; its list holds DemoDevice and Logging. | `StartPage.tsx`'s `disabled={open.isPending}` on every button. `held(page, "/api/open")` before the press of DemoDevice. While held: both buttons disabled, the heading "Open a project" still there, no `alert`. Released: the project's page, heading "DemoDevice", button "Controller". | `disabled={open.isPending}` to `disabled={false}` dies at `toBeDisabled`. |
| **signed in by the one-time code `ddd gui` opens its own browser with** (row 4) | `launchedGui`. | No sentence of its own: `signIn.ts`'s `secretOf` takes the `code` of `/open?code=…`, and the page trades it for the token. The address the browser is handed is this server's, at `/open`, with the one key `code` and the printed address's token nowhere in it. Opened by the page: the button "Controller", the address `<origin>/project`, `localStorage["ddd-gui-token"]` equal to the printed token, and the page's own `POST /open` carrying `{"code": …}`. The same address in a browser that kept nothing: a `status` "Open the address ddd gui printed in its terminal.", no "Controller" (the code is spent). | `signIn.ts`'s `if (code) return { code };` to `if (false) return { code };` dies at "Controller". `server.py`'s `launched`: `?code={server.issue_code()}` to `?token={server.token}` dies at the address's keys. |
| **connecting, before the session answers** (row 5) | `gui`. | `App.tsx`'s `if (session.isPending) { page = <p className="quiet">Connecting…</p>; }`. Signed in and reloaded with `held(page, "/api/session")`: the text "Connecting…"; no heading "Open a project" and no "Looking for projects…", which is what the page draws if the branch is skipped. Released: "Controller", and "Connecting…" gone. | `if (session.isPending) {` to `if (false) {` dies at "Connecting…". |
| **the session failing** (row 6) | `gui`. | `App.tsx`'s `} else if (session.isError) { page = <Banner tone="error">{session.error.message}</Banner>; }`. Signed in, `failing(page, "/api/session", "http")`, reloaded: an `alert` reading `SERVER_FAILED` ("ddd gui failed on this request; the terminal it runs in shows why"); no heading "Open a project" (the start page is drawn if the branch is skipped) and no "Controller"; one request failed. | `} else if (session.isError) {` to `} else if (false) {` dies at the alert. |
| **analysing the project, before its first analysis lands** (row 7) | The tabs: `bareGui`. The component's page: `gui`. | `App.tsx`'s `<p className="quiet">Analysing the project…</p>`, twice. The tabs: `held(page, "/api/state")` before the press of DemoDevice (nothing asks the state before a project is open); the line under the heading "DemoDevice" and the `navigation` "Project views", no `region` "Modules". The component's page: on Controller's page, `held(page, "/api/state")` and a reload; the line under the heading "DemoDevice", no "Project views". Released: the canvas, and Controller's heading. | The tabs': `<p className="quiet">Analysing the project…</p>` after `{state === null ? (` to `<></>`. The component's: the `<p>` after the heading's `</div>` in the `else if (state === null)` branch removed. Each dies at its own journey's line. |
| **the server answering again after it stopped** (row 8) | `gui`; Controller's page. | `App.tsx`'s `{stopped && (` banner, `ddd gui has stopped. Start it again and open the address it prints.` (`alert`), lifted when `followStates` hears an answer: `state/revisions.ts`'s `stopped = false; onStopped(false);`, wired by `app/useProjectState.ts`'s `onStopped: setStopped`. "Add a declaration" is enabled. `stopping(page, gui.directory)`: the `alert` with "stopped" reads that sentence, the heading "Controller" stays drawn, and "Add a declaration" is disabled. `outage.ends()`: the alert is gone, the heading stays, and "Add a declaration" is enabled again; the outage failed at least 4 requests. | `useProjectState.ts`'s `onStopped: setStopped,` to `onStopped: (value) => { if (value) setStopped(true); },` dies at the alert's going (Vitest cannot see `app/`); `revisions.ts`'s `onStopped(false);` removed dies there too. |

- [ ] **Step 1: The helpers.**
  - `writeBuildRecord`, `Outage` and `stopping`, at the end of `gui/e2e/demo.ts`:

```ts
/**
 * A build record, `ddd-build.json`, under `subdirectory` of the copy (created if it is not there),
 * written as `ddd build-info` writes one (`build_info_text`, src/ddd/build_info.py): `body` as
 * json with a two-space indent and a final newline. `body` names what a build would, `format`,
 * `project` and `image` among it. Answers the record's path.
 */
export function writeBuildRecord(directory: string, subdirectory: string, body: object): string {
  const folder = join(directory, subdirectory);
  mkdirSync(folder, { recursive: true });
  const record = join(folder, "ddd-build.json");
  writeFileSync(record, `${JSON.stringify(body, null, 2)}\n`, "utf8");
  return record;
}

/** An outage of the server, begun by `stopping`. */
export interface Outage {
  /** How many requests for the state it has failed so far. */
  failed: () => number;
  /** The server answers again, as `stopping` says. */
  ends: () => void;
}

/**
 * Tells the page the server stopped, the way a network that fails does: every request for the
 * state fails (`failing`), until the outage `ends`, and `file`'s stamp is moved at once
 * (`moveStamp`), so that the poll in flight is answered and the ask that follows is the one that
 * fails (P19b-9). The page sends a GET once more (`sentAgain`, client.ts) and asks the state again
 * 250 ms after an ask that got no answer (`PROMPT_RETRY_MS`, state/revisions.ts): it says the
 * server stopped after the fourth failed request, and asks again every 2 s. Every other request
 * goes on to the server, so that a panel already open keeps what it showed. The caller waits for
 * the banner, or for what it wants of the page. When the outage `ends`, the next ask, 2 s at
 * most after, goes through: a long poll, which the stamp moved once more answers at once, and the
 * page lifts its banner.
 */
export async function stopping(page: Page, directory: string, file = CONTROLLER): Promise<Outage> {
  const failed = await failing(page, "/api/state", "network");
  let over = false;
  // Registered after `failing`'s route, it is asked first: while the server is stopped it hands
  // the request on to `failing`, which fails it, and once the outage has ended it sends the
  // request straight to the server, past `failing`.
  await page.route(
    (url) => url.pathname === "/api/state",
    async (route) => {
      if (over) await route.continue();
      else await route.fallback();
    },
  );
  moveStamp(directory, file);
  return {
    failed,
    ends: () => {
      over = true;
      moveStamp(directory, file);
    },
  };
}
```

  - `launchedGui`, in `gui/e2e/fixtures.ts`, in five edits. First, the `node:fs` import gains `existsSync` and `readFileSync`:

```ts
import { cpSync, existsSync, mkdtempSync, readFileSync } from "node:fs";
```

  Second, `start` gains the optional `launch`, a file: given one it starts the server through the launcher. Replace the doc comment and head of `start`, up to the end of its `spawn` call, with the following (the rest of `start` stays as it is):

```ts
/** What `launchedGui` starts `ddd gui` through, as `python -c LAUNCHER FILE [PROJECT]`: `ddd gui`
 * as a reader starts it, without `--no-browser`, except that `webbrowser.open` is replaced by a
 * function that writes the address it is handed to FILE, so that no browser opens. All the rest
 * is the server's own code: `run` hands `launched` the `webbrowser.open` it finds when it starts
 * the thread, and that is this one. The statements are joined by `;`, on one line, so that the
 * argument holds no newline for a command line to quote. */
const LAUNCHER = [
  "import pathlib, sys, webbrowser",
  "webbrowser.open = lambda url, *rest, **named: pathlib.Path(sys.argv[1]).write_text(url, encoding='utf-8')",
  "from ddd.cli import main",
  "sys.exit(main(['gui', *sys.argv[2:]]))",
].join("; ");

/** `ddd gui` over `directory`, already prepared, naming `project` on the command line or opening
 * on the start page where it is empty; stopped by the `Gui`'s own `stop`. The shared head of
 * `serving` and `copiedGui`. With `launch`, a file, it is started as a reader starts it, with a
 * browser to open (`LAUNCHER`), and the address it opens one on is written to that file. */
async function start(directory: string, project: readonly string[], launch?: string): Promise<Gui> {
  // python -m ddd rather than the ddd launcher: on Windows the launcher starts python as a child
  // of its own, which killing the launcher leaves running, holding the port and the copy.
  const child = spawn(
    process.env.DDD_PYTHON ?? "python",
    launch === undefined
      ? ["-m", "ddd", "gui", ...project, "--no-browser"]
      : ["-c", LAUNCHER, launch, ...project],
    {
      cwd: directory,
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
```

  Third, before `export const test = base.extend`, the type of the fixture and the wait for the file:

```ts
/** The demo as a reader's own `ddd gui` serves it: handed a browser to open, which here is a
 * function that records the address it is given (`LAUNCHER`). */
export interface LaunchedGui extends Gui {
  /** The address `ddd gui` handed its browser - the launch address, with its one-time code - once
   * it has: it does so on a thread of its own, a moment after it prints its own. */
  opened: () => Promise<string>;
}

/** The address a launch wrote to `file`, once it has: the launcher writes it in one go, and the
 * file it makes is empty for the moment before. Ten seconds is far longer than the thread that
 * writes it needs. */
async function addressIn(file: string): Promise<string> {
  for (let tries = 0; tries < 400; tries += 1) {
    if (existsSync(file)) {
      const address = readFileSync(file, "utf8");
      if (address !== "") return address;
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`ddd gui handed its browser no address within 10 s: ${file} is empty or absent`);
}
```

  Fourth, `launchedGui: LaunchedGui;` joins the type parameter of `base.extend`, after `copiedGui: CopiedGui;`. Fifth, the fixture itself, in the object `base.extend` is given, just before `copiedGui`:

```ts
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  launchedGui: async ({}, use, testInfo) => {
    const directory = testInfo.outputPath(DEMO.directory);
    cpSync(join(EXAMPLES, DEMO.directory), directory, { recursive: true });
    // Beside the copy, not in it: the copy is the directory `ddd gui` searches for projects.
    const launched = testInfo.outputPath("launched.txt");
    const gui = await start(directory, [join(directory, DEMO.project)], launched);
    try {
      await use({ ...gui, opened: () => addressIn(launched) });
    } finally {
      await gui.stop();
    }
  },
```

  - `start.spec.ts`'s `record` writes its record through `writeBuildRecord`: the import of `mkdirSync` goes with the lines it served, and so does `writeFileSync`, which only `record` used; `writeBuildRecord` joins the import of `./demo`, where Task 1 left `held`. The head of the file becomes

```ts
import { readdirSync, rmSync, utimesSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, failing, held, SERVER_FAILED, writeBuildRecord } from "./demo";
import { expect, test } from "./fixtures";
```

  and `record`, its doc comment staying, loses its body for one line:

```ts
function record(directory: string): void {
  writeBuildRecord(directory, "build", { format: 2, project: join(directory, "demo.ddd.json") });
}
```

  Run `cd gui && npm run lint && npm run typecheck`: Biome formats these as they stand, and `tsc` accepts the unused exports. The journeys that stood in `start.spec.ts` before still pass: after the build, run the file as Step 3 does, without its `-g`.
- [ ] **Step 2: The worked journey, row 1, red first.** At the end of `gui/e2e/start.spec.ts`:

```ts
test("a project is listed with the images its build records name, each once", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui(
    "demo",
    (directory) => {
      const demo = join(directory, "demo.ddd.json");
      // Records are read in the order of their paths, and the images listed in that order.
      // `firmware` is named twice, by two build trees, and listed once.
      writeBuildRecord(directory, "build/a", { format: 1, project: demo, image: "firmware" });
      writeBuildRecord(directory, "build/b", { format: 1, project: demo, image: "tests" });
      writeBuildRecord(directory, "out", { format: 1, project: demo, image: "firmware" });
      // A record that names no image, as `ddd build-info` writes one without `--image`: it offers
      // its project, Logging, and gives it no image to list.
      const logging = join(directory, "subsystems", "logging", "logging.ddd.json");
      writeBuildRecord(directory, "build/c", { format: 1, project: logging });
    },
    { named: false },
  );
  await page.goto(started.address);
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  const demo = page.getByRole("button", { name: /DemoDevice/ });
  await expect(demo.getByText("built as firmware, tests", { exact: true })).toBeVisible();
  const logging = page.getByRole("button", { name: /Logging/ });
  await expect(logging).toBeVisible();
  await expect(logging.getByText(/^built as/)).toHaveCount(0);
});
```

  Read off the running page before asserting: the button's text is the three spans in order (`DemoDevice`, its path, `built as …`), so the images are looked for as a whole text of their own, `getByText(…, { exact: true })`, inside the button. `copiedGui`'s `change` runs before the server starts, and `{ named: false }` starts it on the start page.
- [ ] **Step 3: Run it red, then fix the bug.** Run it after a build: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test start.spec.ts -g "images its build records name" --output=<a path outside the repository>`. Expected: it fails at the demo's text, `toBeVisible` finding no element that holds exactly "built as firmware, tests": the button's last span reads "built as firmware, tests, firmware". Now the pytest cases, in `tests/test_gui_session.py`, in `TestFindingProjects`, after `test_a_project_a_record_names_that_does_not_exist_is_offered_without_a_name`:

```python
    def test_a_record_that_names_no_image_offers_its_project_and_lists_none(
        self, tmp_path: Path
    ) -> None:
        """``ddd build-info`` without ``--image`` writes ``"image": ""``: not an image, and the
        start page printed ``built as`` for it with nothing after."""
        build_record(tmp_path, tmp_path / "gone.ddd.json", image="")
        (found,) = find_projects(tmp_path).projects
        assert (found.path.name, found.images) == ("gone.ddd.json", ())

    def test_an_image_two_records_name_is_listed_once_in_the_order_of_the_records(
        self, shared: Path
    ) -> None:
        """Two build trees configured for one image name it twice, one record each."""
        build_record(shared.parent, shared, image="firmware.elf")
        build_record(shared.parent, shared, image="tests.elf")
        again = shared.parent / "out" / "ddd-build.json"
        again.parent.mkdir()
        payload = {"format": 1, "project": shared.as_posix(), "image": "firmware.elf"}
        again.write_text(json.dumps(payload), encoding="utf-8")
        (found,) = find_projects(shared.parent).projects
        assert found.images == ("firmware.elf", "tests.elf")
```

  Run them red: `.venv/bin/python -m pytest tests/test_gui_session.py::TestFindingProjects --no-cov -p no:cacheprovider`. Expected: the two new cases fail (`('',)` against `()`, and `('firmware.elf', 'tests.elf', 'firmware.elf')` against `('firmware.elf', 'tests.elf')`), the other seven pass. Then the change, in `find_projects` (`src/ddd/gui/session.py`): the line of the `for` loop over `discover(...)` that appends the image becomes three:

```python
    for info in discover(base, build_directories, refused):
        named = images.setdefault(Path(info.project).resolve(), [])
        if info.image and info.image not in named:
            named.append(info.image)
```

  The record still offers its project (the `setdefault` makes the key), and lists no image of an empty name and none it listed already. Run the cases green, then row 1's journey with `--repeat-each=10`. Ablate, in a scratch copy of the package: the page's `{project.images.length > 0 && (` to `{false && (`, and `find_projects`'s `if info.image and info.image not in named:` to `if info.image:` and to `if info.image not in named:` (a Python ablation is made in a scratch copy and run from inside it, with `PYTHONDONTWRITEBYTECODE=1`: see *Global Constraints*). Each must die at the assertion the row names. The two Python ablations kill a pytest case each as well: `if info.image:` kills `test_an_image_two_records_name_is_listed_once_in_the_order_of_the_records`, and `if info.image not in named:` kills `test_a_record_that_names_no_image_offers_its_project_and_lists_none`.
- [ ] **Step 4: The other rows,** each a journey of its own in `start.spec.ts`, after row 1's. They read and write a description (`readFileSync`, `writeFileSync`) and stop the server (`stopping`), so the head of the file becomes

```ts
import { readdirSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, failing, held, SERVER_FAILED, stopping, writeBuildRecord } from "./demo";
import { expect, test } from "./fixtures";
```

  and the journeys follow:

```ts
test("a project whose description does not load is offered as an unnamed project, and opening it says why not", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui(
    "demo",
    (directory) => {
      // Cut in half, as canvas.spec.ts cuts Controller: no longer json. The search for projects
      // skips a file that is no project description (`_is_project`, session.py), so only a build
      // record can offer it.
      const description = join(directory, "demo.ddd.json");
      const bytes = readFileSync(description);
      writeFileSync(description, bytes.subarray(0, Math.floor(bytes.length / 2)));
      writeBuildRecord(directory, "build", { format: 1, project: description, image: "bench" });
    },
    { named: false },
  );
  await page.goto(started.address);
  const unnamed = page.getByRole("button", { name: /^Unnamed project/ });
  await expect(unnamed).toContainText("demo.ddd.json");
  await expect(page.getByRole("button", { name: /DemoDevice/ })).toHaveCount(0);

  await unnamed.click();
  // `Session.open` refuses it, naming the path as `str(Path)` does: native, with backslashes on
  // Windows, as `join` builds it there too (declarations.spec.ts's not-json journey, every leg).
  const refusal = page.getByRole("alert");
  await expect(refusal).toHaveText(
    `${join(started.directory, "demo.ddd.json")} is not a project description`,
  );
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
});

test("the list's buttons are all held while the project chosen is opening", async ({
  page,
  bareGui,
}) => {
  await page.goto(bareGui.address);
  const demo = page.getByRole("button", { name: /DemoDevice/ });
  const logging = page.getByRole("button", { name: /Logging/ });
  await expect(logging).toBeVisible();
  const release = await held(page, "/api/open");
  try {
    await demo.click();
    await expect(demo).toBeDisabled();
    await expect(logging).toBeDisabled();
    await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
});

test("the address ddd gui opens its own browser with signs the page in by a one-time code, spent once used", async ({
  browser,
  page,
  launchedGui,
}) => {
  const printed = new URL(launchedGui.address);
  const token = printed.searchParams.get("token") ?? "";
  expect(token).toHaveLength(43);
  // What the browser is handed: this server's own address, at /open, with one query key, the
  // launch's code - and not the token, which is on no command line.
  const launched = new URL(await launchedGui.opened());
  expect(launched.origin).toBe(printed.origin);
  expect(launched.pathname).toBe("/open");
  expect([...launched.searchParams.keys()]).toEqual(["code"]);
  expect(launched.href).not.toContain(token);

  const posted: (string | null)[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/open" && request.method() === "POST") {
      posted.push(request.postData());
    }
  });
  await page.goto(launched.href);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  // The page signed itself in with the code, kept the token it was answered, and left no secret
  // in its address.
  expect(posted).toEqual([JSON.stringify({ code: launched.searchParams.get("code") })]);
  await expect(page).toHaveURL(`${printed.origin}/project`);
  expect(await page.evaluate(() => localStorage.getItem("ddd-gui-token"))).toBe(token);

  // A code is spent by the first page that presents it: a browser that kept nothing, handed the
  // same address, is signed in by nothing. The server prints its warning for a code presented
  // again (`_CODE_REUSED`) on its stderr, which is only noise in the log.
  const other = await browser.newContext();
  try {
    const stranger = await other.newPage();
    await stranger.goto(launched.href);
    await expect(
      stranger.getByRole("status").filter({ hasText: "printed in its terminal" }),
    ).toHaveText("Open the address ddd gui printed in its terminal.");
    await expect(stranger.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);
  } finally {
    await other.close();
  }
});

test("the page says it is connecting until the session answers", async ({ page, gui }) => {
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  // Held after the sign-in, which asks the session itself and draws nothing before it has: the
  // address is `/project` now, so nothing signs in again, and the only ask is the app's own.
  const release = await held(page, "/api/session");
  try {
    await page.reload();
    await expect(page.getByText("Connecting…")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Open a project" })).toHaveCount(0);
    await expect(page.getByText("Looking for projects…")).toHaveCount(0);
  } finally {
    release();
  }
  await expect(controller).toBeVisible();
  await expect(page.getByText("Connecting…")).toHaveCount(0);
});

test("the session failing shows the server's own error, and no page", async ({ page, gui }) => {
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  // Registered after the sign-in, whose own ask of the session would be failed too. An HTTP
  // answer is not asked for again, so the page's one ask is the one failure.
  const failed = await failing(page, "/api/session", "http");
  await page.reload();
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("heading", { name: "Open a project" })).toHaveCount(0);
  await expect(controller).toHaveCount(0);
  expect(failed()).toBe(1);
});

test("a project opened is analysed before its tabs show anything, and the page says so", async ({
  page,
  bareGui,
}) => {
  await page.goto(bareGui.address);
  const demo = page.getByRole("button", { name: /DemoDevice/ });
  await expect(demo).toBeVisible();
  // Nothing asks the state before a project is open, so this is the first ask after the press.
  const release = await held(page, "/api/state");
  try {
    await demo.click();
    await expect(page.getByText("Analysing the project…")).toBeVisible();
    await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Project views" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Modules" })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(page.getByText("Analysing the project…")).toHaveCount(0);
});

test("a component's page loaded before the first analysis is headed by the project, and says so", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Controller" })).toBeVisible();
  const release = await held(page, "/api/state");
  try {
    await page.reload();
    await expect(page.getByText("Analysing the project…")).toBeVisible();
    await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Project views" })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.getByRole("heading", { name: "Controller" })).toBeVisible();
  await expect(page.getByText("Analysing the project…")).toHaveCount(0);
});

test("a server that stopped answering and answers again lifts its banner, and a write is offered again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const heading = page.getByRole("heading", { name: "Controller" });
  await expect(heading).toBeVisible();
  // A write's button of the page: the one that opens the panel that adds a declaration.
  const add = page.getByRole("button", { name: "Add a declaration" });
  await expect(add).toBeEnabled();
  const outage = await stopping(page, gui.directory);
  const banner = page.getByRole("alert").filter({ hasText: "stopped" });
  await expect(banner).toHaveText(
    "ddd gui has stopped. Start it again and open the address it prints.",
  );
  // The page stays drawn, and offers no write.
  await expect(heading).toBeVisible();
  await expect(add).toBeDisabled();
  outage.ends();
  await expect(banner).toHaveCount(0);
  await expect(heading).toBeVisible();
  await expect(add).toBeEnabled();
  // Two asks, each sent twice, before the page said so; the same again every 2 s it went on.
  expect(outage.failed()).toBeGreaterThanOrEqual(4);
});
```

  Read off the running page before asserting: the refusal of row 2, whole, its path as the page draws it; the sentence of the signed-out view in row 4 (`SignedOutView.tsx`); the banner of row 8. Run the file with `--repeat-each=10`, then ablate each row as the table says. Row 4's ablations: the page's, in a scratch copy of the package; the server's, in a scratch copy of the Python. Rows 5 to 8 need no state of the page beyond what they register: a hold is released in a `finally`, and nothing is held across a `reload()` but the one request it is for. Row 8's outage is ended by the journey, never left to the teardown.
- [ ] **Step 5: The developer documentation and the CHANGELOG.** In `docs/developer_documentation.rst`, after the paragraph on `copiedGui` and `failing` (the one that ends "so a banner it raises reads as the one a real failure raises.", with whatever Task 1 added to it), a paragraph for the three new helpers:

```rst
``launchedGui``, a fixture beside ``copiedGui``, serves the demo as a reader's own ``ddd gui``
serves it: started without ``--no-browser``, through a ``python -c`` launcher that replaces
``webbrowser.open`` by a function writing the address it is handed to a file, so that no
browser opens. The journey reads that address, whose one-time code is what the reader's
browser would sign in with, and presents it to the page. ``writeBuildRecord``, in
``gui/e2e/demo.ts``, writes a ``ddd-build.json`` into a directory of a copy, for a state of
the start page. ``stopping`` tells the page the server stopped, as a network that fails would:
it has ``failing`` fail the page's requests for the state until the outage it answers
``ends``, and moves a project file's stamp so that the poll in flight is answered and the next
ask is the one that fails. A restarted server hands out another token, so a journey cannot
stop the real one and start it again and see the page recover; it ends the outage instead.
```

  In `CHANGELOG.md`, one entry under `## Unreleased`, after the last entry that concerns `ddd gui`'s page (part 19b's last is "A shared entry's panel no longer turns into the form that declares it."; an earlier task of this part may have added after it), in the style around it (a bold lead, two spaces between sentences, no line over 95 columns):

```markdown
* **The start page no longer says "built as" with nothing after it.**  A build record written
  without an image, as `ddd build-info` writes one when `--image` is left out, listed an image
  called nothing: the project's button on the start page read "built as" and stopped there.
  Two build trees configured for one image listed it twice, as "built as firmware, firmware".
  A record that names no image now offers its project and lists none, and each image a
  project's records name is listed once, in the order of the records.
```
- [ ] **Step 6: The inventory.** The eight rows of the start page and the app name their journeys, by file, line and title, as the rows above them do.
- [ ] **Step 7: The gates,** every journey included, and the docs. Commit: one for the helpers, `launchedGui` and `record`'s change; one for the bug, with its pytest cases, row 1's journey and the CHANGELOG entry; one for rows 2 to 8; one for the documentation.

### A.2 A stopped server on every screen, row 9

**Model:** sonnet, reviewed on sonnet. Each journey is the same three moves on a screen whose existing journeys show the setup, and the one fix is a prop.

**Files:**
- Create: `gui/e2e/stopped.spec.ts`
- Modify: `gui/src/screens/ComponentPage.tsx`, `gui/src/components/ValuesGridView.tsx` (a comment), `CHANGELOG.md`, and this plan's *The inventory*

**Interfaces:**
- Consumes:
  - `stopping(page: Page, directory: string, file?: string): Promise<Outage>`, with `interface Outage { failed: () => number; ends: () => void }` (Task 6);
  - from `gui/e2e/demo.ts`, `CONTROLLER`, `chooseUnit`, `openValues`, `paste`, `scrolledIntoView` and `unstamp`;
  - the fixtures `gui`, `vocabularyGui`, `structuresGui` and `copiedGui`.
- Produces, local to `stopped.spec.ts`: `throughAnOutage(page: Page, directory: string, file: string, controls: readonly Locator[], meanwhile?: () => Promise<void>): Promise<void>`.

**What the pre-flight found:**
- **Twenty sites, and a guard** (P19c-7: every site, grouped per screen, each site's ablation killing a journey). `stopped` reaches a control at 17 places that read `busy={stopped || …}` and 3 that read `isDisabled={stopped}` (`ComponentPage.tsx`'s "Add a declaration" and the two buttons of its table's cells, "Show the values of …" and "Set the unit of …"). The values grid's paste guard (`ValuesGridView.tsx`'s `if (readOnly !== null || busy) return;`) reads the same flag.
- **The server is told it stopped, then told it answers again.** `stopping` (Task 6) fails the page's state poll until the outage `ends()`, and the page says `ddd gui has stopped. …`; every other request goes on to the server, so the panel already open keeps what it showed. A real `gui.stop()` disables the same controls (measured on the Undo, Adopt and Compare sites) but ends the server, fails the reads the panel makes after, and cannot be undone: a restarted server would hand out another token.
- **Every screen goes through one outage, and no screen is left read-only after it** (Review Focus 5). `throughAnOutage` (below) asserts each control of the screen enabled, then disabled while the banner shows, then enabled again once the outage has ended and the banner is gone. Enabled first, so that a button disabled for another reason does not pass; enabled again, because the page's `stopped` is read at twenty places and a screen that kept its own copy would stay disabled for good. The pending change each panel offers is made before the outage, because the panel's fields are disabled by it too.
- **One journey per sitting.** The component page's panel and its buttons are one sitting; so are the two Adopt buttons of the Units tab. Panels are open one at a time, so each other panel has a journey of its own: the Shared files tab's three are one loop over constant, section and raster; the Files tab's New file, Add a file and Remove are three journeys.
- **The time.** A journey takes about 4 s (measured 3.7 to 4.2 s on the Linux development PC, the server's start included); up to 2 s of it is the page's wait before it asks the state again once the outage has ended.
- **The component table is virtualised.** "Show the values of CurveA" is drawn once the table is wheeled to it, as `openValues` does with `scrolledIntoView`; the first journey does the same before it asserts the button.
- **The bug** (P19c-10). The table's two buttons (`ComponentPage.tsx`'s `isDisabled={stopped}` inside the `TableBody` render function) stay enabled when the server stops. React Aria caches each rendered row per item (`useCachedChildren`), `rows` is memoised on `[data, byRow]` and not on `stopped`, so a change of `stopped` never reaches them; `TableBody` takes a `dependencies` prop for exactly that. Measured with a really stopped server: all 19 cell buttons drawn stayed `disabled=false` while "Add a declaration", beside the table, was disabled. It is contained (one screen, one attribute). The first journey finds it, so it is written first and run red. The values grid does not have it: `ValuesGridView.tsx` builds fresh row items on every render, so its cells follow `busy`.
- **Recorded for the maintainer, not fixed** (P19c-10). The "Add a declaration" panel loses what was typed when the server stops: its name field is a React Aria `ComboBox` with `isDisabled`, which resets a disabled combobox's text to its chosen item, none, so the name goes with its offer and the panel says "Choose a variable, or type a new name." The journey of that panel asserts the field alone, disabled and enabled again, so that keeping the draft does not fail it.
- **The paste guard's comment is corrected.** `ValuesGridView.tsx` says the `busy` half of its guard is pinned by nothing, because a journey "would have to paste inside the window an apply is in flight, which it cannot open on purpose". A stopped server keeps the grid busy for as long as a journey wants, and the values journey below pastes then. `values.spec.ts` pastes the same table with nothing stopped and sees "Replaces every value of CurveA", so its absence here is the guard's doing. The comment is replaced (Step 4).
- **Compare's field and button are a read, not a write.** They read `busy={stopped || compare.isFetching}` all the same, and the row says every site.
- **Which file's stamp** `stopping` moves does not matter: any file the server watches. The journeys on `vocabularyGui` and `structuresGui` move `project.ddd.json`, the demo's move Controller's.
- **Tasks 2 to 5 may have moved a line** the ablations name. Each is found by its content; where a task changed the expression, the `stopped` operand is dropped wherever it now stands.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it. The inventory has one row for all of them, row 9, *nothing written while the server is stopped: every Apply and every write's button disabled*; each row below is one screen's journey for it, titled "a stopped server disables … until it answers again". In every row the controls named are enabled, then disabled while the `alert` with "stopped" shows (`ddd gui has stopped. Start it again and open the address it prints.`), then enabled again once the outage ends and the alert is gone.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **the component page** | `gui`; Controller's page; "Set the unit of ValueA"; `chooseUnit(page, "rpm")`; the table wheeled to CurveA's row. | The panel's button "Apply to 2 files", combobox "Unit of ValueA" and button "Remove from Controller"; the page's "Add a declaration"; the table's "Set the unit of ValueB" and "Show the values of CurveA". | `VariablePanel.tsx`'s `busy={stopped \|\| apply.isPending \|\| remove.isPending}` without `stopped \|\| `; `ComponentPage.tsx`'s three `isDisabled={stopped}`, the first of "Add a declaration" and the second and third of the cells, each to `isDisabled={false}`; and the red state, `dependencies={[stopped]}` removed from the `TableBody`, which dies at "Set the unit of ValueB". |
| **the declaration panel** | `gui`; Controller; "Add a declaration"; Name `ValueC`, Enter: the offer "Apply to 1 file". | The combobox "Name" only (see the recorded bug). | `DeclarePanel.tsx`'s `busy={stopped \|\| apply.isPending}` without `stopped \|\| `. |
| **the undo strip** | `gui`; ValueA's unit chosen and applied ("Apply to 2 files"); the panel's "Nothing to change" (the analysis has landed, or the strip's preview would be asked again); the button "Undo the unit of ValueA" pressed. | The Undo button and the strip's "Put back 2 files". | `UndoStrip.tsx`'s `busy={stopped \|\| undo.isPending}` without `stopped \|\| `. |
| **the Units tab's adoption** | `gui`; the Units tab; the adoption banner's "Show changes" opens the panel "Adopt a vocabulary". | The two buttons "Adopt 5 units", the banner's and the panel's. | `UnitsPage.tsx`'s two `busy={stopped \|\| adopt.isPending}`, the first of the banner and the second of the panel, each without `stopped \|\| `. |
| **a unit's panel** | `vocabularyGui`; Units; row `rpm`; the textbox "Description" filled. | The button "Save". | `UnitPanel.tsx`'s `busy={stopped \|\| apply.isPending}` without `stopped \|\| `. |
| **a type's panel** | `structuresGui`; Types; row `Temperature_t`; its Limits row; the field "Max" filled with 120. | The button "Apply to 1 file". | `TypePanel.tsx`'s `busy={stopped \|\| apply.isPending}` without `stopped \|\| `. |
| **the Shared files form** | `gui`; Shared files; "Declare an entry"; the vocabulary "constants"; Name `SPARE_SLOTS`, Value `4`. | The button "Apply to 2 files" of the form "Declare a constant". | `SharedPage.tsx`'s `busy={stopped \|\| apply.isPending}` (the form's) without `stopped \|\| `. |
| **a constant's, a section's and a raster's panel** | `vocabularyGui`; Shared files; the row `TREND_SAMPLES`, `.calib` or `100ms`; the field of one region filled: Value 32, Alignment 8, Event 5. | The region's button "Save". | `ConstantPanel.tsx`, `SectionPanel.tsx`, `RasterPanel.tsx`: each `busy={stopped \|\| apply.isPending}` without `stopped \|\| `. Each dies at its own journey. |
| **New file** | `vocabularyGui`; Files; "New file"; Kind `component`, File name `valve`, Component name `Valve`. | The button "Apply to 2 files". | `FilesPage.tsx`'s first `busy={stopped \|\| apply.isPending}` (`NewFile`) without `stopped \|\| `. |
| **Add a file** | `vocabularyGui`, with `extra.ddd.json` written into the copy before the page opens; Files; "Add a file"; Path `extra.ddd.json`. | The button "Apply to 1 file". | `FilesPage.tsx`'s second `busy={stopped \|\| apply.isPending}` (`AddFile`). |
| **Remove** | `vocabularyGui`; Files; the row `units.ddd.json`. | The button "Remove from the includes", in the region of that name. | `FilesPage.tsx`'s third `busy={stopped \|\| apply.isPending}` (`RemoveFile`). |
| **a finding's fix** | `copiedGui("demo", …)` whose change takes ValueH's id off (`unstamp`); Findings; the row `missing-id`; "Give 'ValueH' an id". | The button "Apply to 1 file". | `FindingsPage.tsx`'s `busy={stopped \|\| apply.isPending}` without `stopped \|\| `. |
| **the values grid** | `gui`; `openValues(page, gui.address, "CurveA")`; the textbox "element 3" filled with 7.5: the offer "Sets element 3 of CurveA to 7.5 ms". | "Apply to 1 file" and the cell. While the alert shows, a table pasted (`paste`) draws no "Replaces every value of CurveA", and the cell's offer is still there: the grid takes no paste. | `ValuesPage.tsx`'s `busy={stopped \|\| apply.isPending}` without `stopped \|\| `; `ValuesGridView.tsx`'s `if (readOnly !== null \|\| busy) return;` to `if (readOnly !== null) return;`. |
| **Compare** | `gui`; the Compare tab; the textbox "Baseline" filled with `baseline.json`. | The field and the button "Compare". | `ComparePage.tsx`'s `busy={stopped \|\| compare.isFetching}` without `stopped \|\| `. |

One ablation kills them all: `app/useProjectState.ts`'s `onStopped: setStopped,` to `onStopped: (value) => { if (value) setStopped(true); },` leaves the banner up for good, and every journey dies at the banner's going, before its controls are asked to be enabled again.

- [ ] **Step 1: The worked journey, red first,** in a new `gui/e2e/stopped.spec.ts`: the head of the file with its one helper, and the component page's journey, the one that finds the bug.

```ts
import type { Locator, Page } from "@playwright/test";
import { CONTROLLER, chooseUnit, scrolledIntoView, stopping } from "./demo";
import { expect, test } from "./fixtures";

// A server that stopped answering leaves nothing to write with (spec 2026-10-08 §5; part 19c,
// row 9): every control that would write is disabled, and so is the one that opens a panel that
// would. The server is not really stopped - a restarted one would hand out another token - but
// told so, as a network that fails does (`stopping`): the page's state poll fails, and the page
// says the server stopped. Every other request goes on to the server, so a panel already open
// keeps what it showed. Each journey sets up its screen's pending change first, and goes through
// an outage with the screen's controls (`throughAnOutage`).

/** What the page says while the server has stopped (`App.tsx`'s banner). */
const STOPPED = "ddd gui has stopped. Start it again and open the address it prints.";

/**
 * One outage, through one screen. The `controls` are enabled; the server stops - `file`'s stamp
 * is moved, any file of the project does - and the page says so, and they are disabled, with
 * `meanwhile` run then; the server answers again, and the page lifts its banner, and they are
 * enabled again: a screen left read-only by an outage would stay disabled here.
 */
async function throughAnOutage(
  page: Page,
  directory: string,
  file: string,
  controls: readonly Locator[],
  meanwhile?: () => Promise<void>,
): Promise<void> {
  for (const control of controls) await expect(control).toBeEnabled();
  const outage = await stopping(page, directory, file);
  const banner = page.getByRole("alert").filter({ hasText: "stopped" });
  await expect(banner).toHaveText(STOPPED);
  for (const control of controls) await expect(control).toBeDisabled();
  await meanwhile?.();
  outage.ends();
  await expect(banner).toHaveCount(0);
  for (const control of controls) await expect(control).toBeEnabled();
}

test("a stopped server disables the variable panel's Apply, field and removal, and the component's buttons until it answers again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await chooseUnit(page, "rpm");
  const panel = page.getByRole("complementary", { name: "ValueA" });
  const apply = panel.getByRole("button", { name: "Apply to 2 files" });
  const unit = panel.getByRole("combobox", { name: "Unit of ValueA" });
  const remove = panel.getByRole("button", { name: "Remove from Controller" });
  const add = page.getByRole("button", { name: "Add a declaration" });
  // The table's own buttons: one that opens a panel to write with, another declaration's, and
  // one that opens the values of CurveA, whose row is drawn once the virtualised table is
  // wheeled to it.
  const setUnit = page.getByRole("button", { name: "Set the unit of ValueB" });
  const showValues = page.getByRole("button", { name: "Show the values of CurveA" });
  await scrolledIntoView(page, "Declarations of Controller", showValues);
  await throughAnOutage(page, gui.directory, CONTROLLER, [
    apply,
    unit,
    remove,
    add,
    setUnit,
    showValues,
  ]);
});
```

  Read off the running page before asserting: the names of the panel's controls (a panel of ValueA after `chooseUnit(page, "rpm")` offers "Apply to 2 files", the combobox "Unit of ValueA" and "Remove from Controller"); the banner's words, `ddd gui has stopped. Start it again and open the address it prints.`, which the helper asserts whole, finding the alert by "stopped"; the table's own buttons, "Set the unit of ValueB" and "Show the values of CurveA", which the page draws as buttons of the table's cells.
- [ ] **Step 2: Run it red.** After a build: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test stopped.spec.ts --output=<a path outside the repository>`. Expected: it fails at the fifth of its six controls, the table's "Set the unit of ValueB" (`Expected: disabled`, `Received: enabled`), the four before it having passed. The outage is never ended in this run, so the page stays stopped until the journey is torn down.
- [ ] **Step 3: The fix.** In `gui/src/screens/ComponentPage.tsx`, the `TableBody` of the declarations table, `<TableBody items={rows}>`, becomes

```tsx
          <TableBody
            items={rows}
            // The rows' buttons are disabled with `stopped`, which React Aria's cache of the rows
            // it has rendered does not see change unless told to (`dependencies`).
            dependencies={[stopped]}
          >
```

  Run the journey again, with `--repeat-each=10`: green. The cells follow `stopped` both ways, so the last assertion of the journey, the cells enabled again, passes too. The values grid needs no such prop (see above).
- [ ] **Step 4: The comment of the paste guard.** In `gui/src/components/ValuesGridView.tsx`, in `onPaste`, the last paragraph of the guard's comment, just above `if (readOnly !== null || busy) return;`

```ts
        // The `busy` half is the one arm of this component nothing pins: a journey would have to
        // paste inside the window an apply is in flight, which it cannot open on purpose, and a
        // test that waited for it would be the race this suite refuses to write. It is left here
        // unguarded by any test on purpose, and said so rather than left to be discovered.
```

  becomes

```ts
        // The `busy` half is pinned by `stopped.spec.ts`: a stopped server keeps the grid busy for
        // as long as a journey wants (`ValuesPage`), so the journey pastes then, and finds the
        // offer of the cell it was typing still the only one, with no apply in flight to race.
```
- [ ] **Step 5: The other rows,** each a journey of its own in `stopped.spec.ts`, after the first. They need more of `demo.ts`, the filesystem and the description of the two copies, so the imports at the top of the file become

```ts
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import {
  CONTROLLER,
  chooseUnit,
  openValues,
  paste,
  scrolledIntoView,
  stopping,
  unstamp,
} from "./demo";
import { expect, test } from "./fixtures";
```

  and, after the file's opening comment, the name of that description:

```ts
/** The description of a copy of examples/vocabulary or of examples/structures. */
const PROJECT = "project.ddd.json";
```

  Then the journeys:

```ts
test("a stopped server disables the declaration panel's name field until it answers again", async ({
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
  await expect(adding.getByRole("button", { name: "Apply to 1 file" })).toBeEnabled();
  // The field only: the panel also loses the name typed into it, and with it the offer, when its
  // field is disabled - recorded for the maintainer, not asserted here, so that keeping the draft
  // does not fail this journey.
  await throughAnOutage(page, gui.directory, CONTROLLER, [name]);
});

test("a stopped server disables the undo strip's Undo and Put back until it answers again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await chooseUnit(page, "rpm");
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  // The analysis has landed: the strip's preview is asked once.
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  const undo = page.getByRole("button", { name: "Undo the unit of ValueA" });
  await undo.click();
  const putBack = page
    .getByRole("region", { name: "Undo" })
    .getByRole("button", { name: "Put back 2 files" });
  await throughAnOutage(page, gui.directory, CONTROLLER, [undo, putBack]);
});

test("a stopped server disables both Adopt buttons of the Units tab until it answers again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await banner.getByRole("button", { name: "Show changes" }).click();
  const preview = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  const fromBanner = banner.getByRole("button", { name: "Adopt 5 units" });
  const fromPreview = preview.getByRole("button", { name: "Adopt 5 units" });
  await throughAnOutage(page, gui.directory, CONTROLLER, [fromBanner, fromPreview]);
});

test("a stopped server disables a unit panel's Save until it answers again", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "rpm" });
  await panel.getByRole("textbox", { name: "Description" }).fill("revolutions per minute");
  const save = panel.getByRole("button", { name: "Save" });
  await throughAnOutage(page, vocabularyGui.directory, PROJECT, [save]);
});

test("a stopped server disables a type panel's Apply until it answers again", async ({
  page,
  structuresGui,
}) => {
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  await panel.getByRole("row", { name: "Limits", exact: true }).click();
  await panel.getByLabel("Max", { exact: true }).fill("120");
  const apply = panel.getByRole("button", { name: "Apply to 1 file" });
  await throughAnOutage(page, structuresGui.directory, PROJECT, [apply]);
});

test("a stopped server disables the Shared files form's Apply until it answers again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  await page.getByRole("button", { name: "Declare an entry" }).click();
  await page
    .getByRole("complementary", { name: "Declare an entry" })
    .getByRole("combobox", { name: "Vocabulary" })
    .press("ArrowDown");
  await page.getByRole("option", { name: "constants", exact: true }).click();
  const form = page.getByRole("complementary", { name: "Declare a constant" });
  await form.getByRole("textbox", { name: "Name" }).fill("SPARE_SLOTS");
  await form.getByRole("textbox", { name: "Value" }).fill("4");
  const apply = form.getByRole("button", { name: "Apply to 2 files" });
  await throughAnOutage(page, gui.directory, CONTROLLER, [apply]);
});

// The three panels of the Shared files tab, each with the one field of it that is saved alone.
const ENTRIES = [
  { kind: "constant", entry: /^TREND_SAMPLES/, panel: "TREND_SAMPLES", field: "Value", text: "32" },
  { kind: "section", entry: /^\.calib/, panel: ".calib", field: "Alignment", text: "8" },
  { kind: "raster", entry: /^100ms/, panel: "100ms", field: "Event", text: "5" },
] as const;

for (const { kind, entry, panel, field, text } of ENTRIES) {
  test(`a stopped server disables a ${kind} panel's Save until it answers again`, async ({
    page,
    vocabularyGui,
  }) => {
    await page.goto(vocabularyGui.address);
    await page.getByRole("link", { name: "Shared files", exact: true }).click();
    await page.getByRole("row", { name: entry }).click();
    const saving = page
      .getByRole("complementary", { name: panel })
      .getByRole("region", { name: field });
    await saving.getByRole("textbox", { name: field }).fill(text);
    const save = saving.getByRole("button", { name: "Save" });
    await throughAnOutage(page, vocabularyGui.directory, PROJECT, [save]);
  });
}

test("a stopped server disables New file's Apply until it answers again", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "New file" }).click();
  const creating = page.getByRole("complementary", { name: "New file" });
  const kind = creating.getByRole("combobox", { name: "Kind" });
  await kind.fill("component");
  await kind.press("Enter");
  await creating.getByRole("textbox", { name: "File name" }).fill("valve");
  await creating.getByRole("textbox", { name: "Component name" }).fill("Valve");
  const apply = creating.getByRole("button", { name: "Apply to 2 files" });
  await throughAnOutage(page, vocabularyGui.directory, PROJECT, [apply]);
});

test("a stopped server disables Add a file's Apply until it answers again", async ({
  page,
  vocabularyGui,
}) => {
  writeFileSync(
    join(vocabularyGui.directory, "extra.ddd.json"),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "Add a file" }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  await adding.getByRole("textbox", { name: "Path" }).fill("extra.ddd.json");
  const apply = adding.getByRole("button", { name: "Apply to 1 file" });
  await throughAnOutage(page, vocabularyGui.directory, PROJECT, [apply]);
});

test("a stopped server disables a file's Remove until it answers again", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("row", { name: "units.ddd.json" }).click();
  const remove = page
    .getByRole("complementary", { name: "units.ddd.json" })
    .getByRole("region", { name: "Remove from the includes" })
    .getByRole("button", { name: "Remove from the includes" });
  await throughAnOutage(page, vocabularyGui.directory, PROJECT, [remove]);
});

test("a stopped server disables a finding's fix Apply until it answers again", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", (directory) => {
    unstamp(directory, CONTROLLER, "ValueH");
  });
  await page.goto(started.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await page.getByRole("row", { name: "missing-id" }).click();
  const panel = page.getByRole("complementary", { name: "missing-id" });
  await panel.getByRole("button", { name: "Give 'ValueH' an id" }).click();
  const apply = panel.getByRole("button", { name: "Apply to 1 file" });
  await throughAnOutage(page, started.directory, CONTROLLER, [apply]);
});

test("a stopped server disables the values grid's Apply and cells, and takes no paste, until it answers again", async ({
  page,
  gui,
}) => {
  await openValues(page, gui.address, "CurveA");
  const cell = page.getByRole("textbox", { name: "element 3" });
  await cell.fill("7.5");
  const apply = page.getByRole("button", { name: "Apply to 1 file" });
  const offer = page.getByText("Sets element 3 of CurveA to 7.5 ms");
  await expect(offer).toBeVisible();
  await throughAnOutage(page, gui.directory, CONTROLLER, [apply, cell], async () => {
    // A table pasted now would replace that offer with its own. It is taken by nothing: the grid
    // is busy (`ValuesGridView`'s paste guard), and the offer of the cell stays the only one.
    await paste(page, "12.004\t9.5\t8.5\t8\t7.5\t7");
    await expect(page.getByText("Replaces every value of CurveA")).toHaveCount(0);
    await expect(offer).toBeVisible();
  });
});

test("a stopped server disables Compare's field and button until it answers again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  const baseline = page.getByRole("textbox", { name: "Baseline" });
  await baseline.fill("baseline.json");
  const compare = page.getByRole("button", { name: "Compare" });
  await throughAnOutage(page, gui.directory, CONTROLLER, [baseline, compare]);
});
```

  `tsc` names an import nothing uses, and Biome orders them. Run the file with `--repeat-each=10`.
- [ ] **Step 6: The ablations.** Each of the table's, in a scratch copy of the package (see *Global Constraints*), built and run against the whole file: it must die at the journey the row names, and at no other. The ablations of the first row die at different controls of the same journey: `VariablePanel.tsx`'s at "Apply to 2 files", the "Add a declaration" button's at that button, the second `isDisabled={stopped}`'s at "Show the values of CurveA", the third's at "Set the unit of ValueB", and the cells' cache (`dependencies` removed) at "Set the unit of ValueB" too, the red state of Step 2. Then the one that kills them all, `useProjectState.ts`'s `onStopped: setStopped,` to `onStopped: (value) => { if (value) setStopped(true); },`: all sixteen die at the banner's going.
- [ ] **Step 7: The CHANGELOG.** One entry under `## Unreleased`, after the last entry that concerns `ddd gui`'s page (the one Task 6 added, or part 19b's last, "A shared entry's panel no longer turns into the form that declares it."), in the style around it:

```markdown
* **The component table's buttons are disabled when `ddd gui` has stopped.**  On a component's
  page, the buttons in the table's Shape and Unit cells, which open a variable's values and its
  panel, stayed enabled after the page said that `ddd gui` had stopped, while the page's other
  buttons that write were disabled; the panels they opened could apply nothing.  They are
  disabled with the rest, and enabled again once `ddd gui` answers.
```
- [ ] **Step 8: The inventory.** The row *nothing written while the server is stopped: every Apply and every write's button disabled* names the file's sixteen journeys, by file, line and title.
- [ ] **Step 9: The gates,** every journey included. Commit: one for the fix, the comment, the CHANGELOG entry and the first journey; one for the others.

### A.3 The states that pass, rows 10 to 13

**Model:** sonnet, reviewed on sonnet. It is the same short sitting 22 times, each on a screen whose existing journeys show the setup; the one new helper is a plugin that sleeps.

**Files:**
- Create: `gui/e2e/updating.spec.ts`, `gui/e2e/changes.spec.ts`
- Modify: `gui/e2e/demo.ts` (`SLOW`, `slowAnalyses`), `gui/e2e/undo.spec.ts` (rows 12 and 13), `docs/developer_documentation.rst`, and this plan's *The inventory*

**Interfaces:**
- Consumes:
  - from Task 1, in `gui/e2e/demo.ts`: `held(page: Page, path: string | RegExp | ((url: URL) => boolean)): Promise<() => void>`; `failing(page, path, how, times?, method?: "GET" | "POST")`, here with the method; `editJson(directory: string, file: string, change: (data: any) => void): void`; `SERVER_FAILED`;
  - from `gui/e2e/demo.ts` as it stands: `CONTROLLER`, `chooseUnit`, `openValues` and `unstamp`; the fixtures `gui`, `vocabularyGui`, `structuresGui` and `copiedGui`.
- Produces, in `gui/e2e/demo.ts`: `SLOW`, the name of the file whose presence slows a copy's analyses, and `slowAnalyses(directory: string, project: string, seconds?: number): void`. Only this task uses them.
- Produces, local to their spec files:
  - `updating.spec.ts`: `updatingUntilItLands(page: Page, name: string, whole: (panel: Locator) => Locator): Promise<void>` and `renaming(name: string): (panel: Locator) => Locator`;
  - `changes.spec.ts`: `shownThenHidden(where: Locator | Page, lines: number): Promise<void>`;
  - `undo.spec.ts`: `appliedAndAnalysed(page: Page, address: string): Promise<void>`.

**What the pre-flight found:**
- **An example analyses in a few milliseconds, too fast for a journey to see the findings updating.** On the vocabulary example the analysis of an edit lands about 12 ms after the edit is answered (measured on the requests), before the server handles the page's first ask about the entry it moved to; `values.spec.ts` measured 2.5 to 6.1 ms on the demo. A project plugin slows it honestly: `slowAnalyses` writes `slow.py` into the copy, whose check sleeps while a file named `SLOW` lies in the copy's directory, and names it in the project description's `plugins`. It reports no finding (measured: the counts stay 0). The journey creates `SLOW` just before the press that edits, so that the analyses `ddd gui` starts with are fast. Measured with 1.5, 2 and 3 s; with 3 a journey takes about 4.5 s (70 runs of `updating.spec.ts`, 5.2 minutes), and a journey of `changes.spec.ts` about 1 s.
- **Six panels draw the note alone,** one `if` each: `ConstantPanel.tsx`, `SectionPanel.tsx`, `RasterPanel.tsx`, `TypePanel.tsx`, `UnitPanel.tsx` and `VariablePanel.tsx`, each `if (answer.shown === "updating") { return (<Panel title={name} onClose={onClose}><UpdatingNote updating /></Panel>); }`. `answer` is `panelShows` (`lib/refusals.ts`): the server answered 409 `unreadable` ("'SPARE_SLOTS' is not declared in any file that has not changed since, and demo.ddd.json changed since it was read") while the page is updating and holds no answer of that name. The panel is titled with the entry, holds its Close button and the one line "Updating the findings…", and no field. A rename or a declaration reaches it; the Shared files panels by either, the unit's and the type's by a rename, the variable's by a declaration.
- **The note is looked for in the panel.** The project's heading says "Updating the findings…" too (`large.spec.ts` sees that one), so a page-wide `getByText` is a strict-mode violation. Each journey then asserts that a field only the whole panel has is nowhere to be found, which is what tells the note alone from the panel with a note in it, and that with nothing done the whole panel comes and the note goes.
- **A variable already declared elsewhere never reaches the branch.** The server answers a read of a variable another component produces (ValueC) at once, from its index, and its panel draws whole with the note in it (measured: a journey that declared ValueC survived the ablation). The variable's journey declares a new measurement, `Pressure`, as `declarations.spec.ts` does, and asserts that the keys table, a `grid`, is not there until the analysis lands.
- **Task 2 may add to `panelShows`** (P19c-5): the open unit, type and variable panels whose units read fails say so, and that decision goes into `panelShows` or beside it. The ablation of the shared decision below removes the exemption for the page that is updating, `!(updating && isUnreadable(answer.error))`, alone, wherever the expression then stands.
- **Row 11 is 14 toggles on 13 views, in 13 journeys.** Each is `<Button variant="link" onPress={…(!shown)}>{shown ? "Hide changes" : "Show changes"}</Button>`; the changes are `Changes` (`components/Changes.tsx`), one `<pre class="hunk">` for each hunk of each file. The variable panel has two blocks, each with a pair of its own and independent of the other (measured); they are one journey with two assertions, each killed by its own ablation. No existing journey presses "Hide changes". The journeys count `.hunk` elements, not their lines: what a plan writes is pinned by the planners' own tests and by the journeys that apply it.
- **The adopt panel's "Hide changes" closes its panel** (P19c-16). The banner's "Show changes" opens the panel "Adopt a vocabulary" beside the table, and the panel's button reads "Hide changes" and calls `onClose`: it is not a toggle, the banner's staying as it was. The journey asserts what it does.
- **Rows 12 and 13 wait for "Nothing to change"** in the panel before the strip is opened: the preview is asked under the revision the page holds (`["undo", at, revision]`), so one asked before the analysis of the Apply has landed is asked again when it does: row 12's hold would be spent on the first ask, and the second would answer the strip. `failing`'s method argument makes row 13 independent of the order besides: the route fails the one POST, and the preview, a GET of the same path, goes through.
- **Row 13 fails the undo with a 500.** A POST is never sent again (`sentAgain`), so a network failure of it would read "The undo was refused: ddd gui is not answering" (read off the code, not run); it is not written, and a real failing undo, an unwritable file, is bound to the platform's own words. A failed preview draws the same sentence through another line of the strip (`preview.isError`; measured with `failing(page, "/api/undo", "http", 1)` registered before the strip is opened). It has no row in the inventory, and no journey here.
- **An observation, recorded for the maintainer, not fixed and not a bug of these rows.** With the strip open, every new revision empties the preview for about ten milliseconds (`UndoStrip.tsx`'s query has no `placeholderData`, because its key holds the revision on purpose): the strip says "Reading the files…" and the button "Put back" is withdrawn for one frame (measured: 169 to 179 ms after a project file was touched). A press in that frame is lost, the class of loss `fixtures.ts`'s `analysed` describes for Apply and Show changes. Keeping the previous preview would show files that may have changed since.
- **No bug is fixed in this task.** A journey that finds one follows the rule in *Global Constraints*.
- **Existing coverage.** `undo.spec.ts` covers the strip's successes and the preview refused as changed on disk, and none sees "Reading the files…" or a failed undo. The existing journeys of the panels press "Show changes".

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **a constant just declared, the findings updating** (row 10) | `copiedGui("demo", …)` whose change is `slowAnalyses(directory, "demo.ddd.json")`; Shared files; "Declare an entry"; the vocabulary "constants"; Name `SPARE_SLOTS`, Value `4`; "Apply to 2 files" visible. | `SLOW` created, "Apply to 2 files" pressed. In the `complementary` named `SPARE_SLOTS`: the text "Updating the findings…" and no textbox "Rename SPARE_SLOTS to"; then, with nothing done, the textbox, and the text gone. | `ConstantPanel.tsx`'s `if (answer.shown === "updating") {` to `if (false) {` dies at the text (the constant renamed dies there too); the shared decision, `lib/refusals.ts`'s `if (answer.error !== null && !(updating && isUnreadable(answer.error))) {` to `if (answer.error !== null) {`, dies in all seven journeys of this row at the text, which no panel then says. |
| **a constant, a section and a raster just renamed, the findings updating** (row 10) | `copiedGui("vocabulary", …)` whose change is `slowAnalyses(directory, "project.ddd.json")`; Shared files; the row `TREND_SAMPLES`, `.calib` or `1ms`; the textbox "Rename … to" filled with `TREND_SLOTS`, `.tuning` or `2ms`. | `SLOW` created, then the panel's "Apply to …" pressed. In the `complementary` named by the new name: "Updating the findings…" and no textbox "Rename … to"; then the textbox, and the text gone. | `SectionPanel.tsx`'s and `RasterPanel.tsx`'s `if (answer.shown === "updating") {` to `if (false) {`, each dying at its own journey; the constant's dies at the constant renamed and the constant declared. |
| **a unit just renamed, the findings updating** (row 10) | `copiedGui("vocabulary", …)`, slowed; Units; the row `rpm`; the combobox "Rename rpm to" filled with `rev/min`, Enter. | `SLOW` created, then "Apply to …". In the `complementary` named `rev/min`: the text and no combobox "Rename rev/min to"; then the combobox. | `UnitPanel.tsx`'s `if (answer.shown === "updating") {` to `if (false) {`. |
| **a type just renamed, the findings updating** (row 10) | `copiedGui("structures", …)`, slowed; Types; the row `Temperature_t`; the textbox "Rename Temperature_t to" filled with `Temp_t`. | `SLOW` created, then "Apply to …". In the `complementary` named `Temp_t`: the text and no textbox "Rename Temp_t to"; then the textbox. | `TypePanel.tsx`'s `if (answer.shown === "updating") {` to `if (false) {`. |
| **a variable just declared, the findings updating** (row 10) | `copiedGui("demo", …)`, slowed; Controller's page; "Add a declaration"; Name `Pressure`, Scope `produces`, Kind `measurement`, Volatile of Pressure `false`, Datatype of Pressure `uint8`; "Apply to 1 file" visible. | `SLOW` created, then "Apply to 1 file". In the `complementary` named `Pressure`: the text and no `grid`; then the keys table, a `grid`, and the text gone. | `VariablePanel.tsx`'s `if (answer.shown === "updating") {` to `if (false) {`. |
| **a variable's changes, shown and hidden** (row 11) | `gui`; Controller; "Set the unit of ValueA"; `chooseUnit(page, "rpm")`. | In the region "Settle the key": "Show changes" pressed, 2 `.hunk` (controller.ddd.json and sensor_hub.ddd.json); "Hide changes" pressed, none, and "Show changes" offered again with no "Hide changes". The same in the region "Remove the declaration": 1 hunk. | `VariablePanelView.tsx`'s `onPress={() => props.onChangesShown(!props.changesShown)}` to `onPress={() => props.onChangesShown(true)}` dies at the first pair's hiding; `onPress={() => removal.onShown(!removal.shown)}` to `onPress={() => removal.onShown(true)}` dies at the second's. |
| **a unit's changes, shown and hidden** (row 11) | `vocabularyGui`; Units; the row `rpm`; the textbox "Description" filled. | In the region "Description": 1 hunk shown, then none. | `UnitPanelView.tsx`'s `onPress={() => onShown(!shown)}` to `onPress={() => onShown(true)}`. |
| **a type's changes, shown and hidden** (row 11) | `structuresGui`; Types; the row `Temperature_t`; its Limits row; the field "Max" filled with 120. | In the panel: 1 hunk shown, then none. | `TypePanelView.tsx`'s `onPress={() => props.onChangesShown(!props.changesShown)}` to `onPress={() => props.onChangesShown(true)}`. |
| **a constant's, a section's and a raster's changes, shown and hidden** (row 11) | `vocabularyGui`; Shared files; the row `TREND_SAMPLES`, `.calib` or `100ms`; the field of one region filled: Value 32, Alignment 8, Event 5. | In that region: 1 hunk shown, then none. One journey each, a loop. | `ConstantPanelView.tsx`'s, `SectionPanelView.tsx`'s and `RasterPanelView.tsx`'s `onPress={() => onShown(!shown)}` to `onPress={() => onShown(true)}`, each dying at its own journey. |
| **the changes of an entry being declared, shown and hidden** (row 11) | `gui`; Shared files; "Declare an entry"; the vocabulary "constants"; Name `SPARE_SLOTS`, Value `4`. | In the form "Declare a constant": 2 hunks shown, then none. | `SharedAddView.tsx`'s `onPress={() => props.onChangesShown(!props.changesShown)}` to `onPress={() => props.onChangesShown(true)}`. |
| **the changes of a declaration being added, shown and hidden** (row 11) | `gui`; Controller; "Add a declaration"; Name `ValueC`, Enter. | In the panel "Add a declaration": 1 hunk shown, then none. | `DeclarePanelView.tsx`'s `onPress={() => props.onChangesShown(!props.changesShown)}` to `onPress={() => props.onChangesShown(true)}`. |
| **a finding's fix's changes, shown and hidden** (row 11) | `copiedGui("demo", …)` whose change takes ValueH's id off (`unstamp`); Findings; the row `missing-id`; "Give 'ValueH' an id". | In the panel `missing-id`: 1 hunk shown, then none. | `FindingPanelView.tsx`'s `onPress={() => props.onChangesShown(!props.changesShown)}` to `onPress={() => props.onChangesShown(true)}`. |
| **a file's removal's changes, shown and hidden** (row 11) | `vocabularyGui`; Files; the row `units.ddd.json`; the region "Remove from the includes". | In that region: 1 hunk shown, then none. | `FileActionsView.tsx`'s `onPress={() => onChangesShown(!changesShown)}` to `onPress={() => onChangesShown(true)}`. |
| **a value's changes, shown and hidden** (row 11) | `gui`; `openValues(page, gui.address, "CurveA")`; the textbox "element 3" filled with 7.5. | On the page: 1 hunk shown, then none. | `ValuesGridView.tsx`'s `onPress={() => props.onChangesShown(!changesShown)}` to `onPress={() => props.onChangesShown(true)}`. |
| **an undo's changes, shown and hidden** (row 11) | `gui`; ValueA's unit chosen as `rpm` and applied; "Nothing to change"; "Undo the unit of ValueA" pressed. | In the region "Undo": 2 hunks shown, then none. | `UndoStripView.tsx`'s `onPress={() => props.onChangesShown(!changesShown)}` to `onPress={() => props.onChangesShown(true)}`. |
| **the adoption's changes, shown in a panel of their own** (row 11) | `gui`; the Units tab; the adoption banner's "Show changes". | The panel "Adopt a vocabulary" holds the hunks; its "Hide changes" closes the panel (no `complementary` of that name), and the banner offers "Show changes" again. | `AdoptBannerView.tsx`'s `onPress={onClose}` before "Hide changes" to `onPress={() => undefined}` dies at the panel's going. |
| **the files an undo puts back, being read** (row 12) | `gui`; ValueA's unit chosen as `rpm` and applied; the panel's "Nothing to change"; `held(page, "/api/undo")`. | "Undo the unit of ValueA" pressed: `aria-expanded` `true`; the region "Undo" holds "Reading the files…" and no button. Released: `Puts back 2 files: controller.ddd.json, sensor_hub.ddd.json`, and "Reading the files…" gone. | `UndoStripView.tsx`'s `<p className="quiet">Reading the files…</p>` to `<></>` dies at the text. |
| **an undo the server fails on** (row 13) | As above; `failing(page, "/api/undo", "http", 1, "POST")` registered before the strip is opened; Controller's file read. | Undo, then "Put back 2 files" pressed: the region's `status` reads `The undo was refused: ddd gui failed on this request; the terminal it runs in shows why`, holds no button (an undo is all or nothing), and the Undo button is still offered. One request failed, and Controller's file is byte for byte what the Apply left. The strip closed and opened again reads the preview again, and "Put back 2 files" goes through: the Undo button goes, and the file is not what it was. | `UndoStrip.tsx`'s `onError: (error) => setRefused({ text: refusalOf(error), revision }),` to `onError: () => undefined,` dies at the sentence. |
| **the files an undo puts back, failing to be read** (added, P19c-9) | As row 12, with `failing(page, "/api/undo", "http", 1, "GET")` registered in place of the hold, before the strip is opened. | `UndoStrip.tsx` draws a failed preview with the same words as a failed undo: `preview.isError ? refusalOf(preview.error) : null`, so the strip reads `` `The undo was refused: ${SERVER_FAILED}` ``. Read it whole off the page. Assert it, assert that no "Put back" button is offered, and assert that the file is as it was. | `UndoStrip.tsx`'s `?? (preview.isError ? refusalOf(preview.error) : null)` made `?? null`: the journey dies at the sentence. |

- [ ] **Step 1: The helper.** `SLOW` and `slowAnalyses`, at the end of `gui/e2e/demo.ts`; `editJson` is Task 1's:

```ts
/** The file whose presence in a copy's directory makes its analyses slow (`slowAnalyses`). */
export const SLOW = "slow";

/**
 * Changes a copy, before `ddd gui` starts on it, so that every analysis takes `seconds` more
 * while a file named `SLOW` lies in its directory: a project plugin, `slow.py`, whose check
 * sleeps, named by the project description `project` in the copy's `plugins`. The examples
 * analyse in a few milliseconds, which leaves a journey no moment to see the page between an
 * edit and the analysis that follows it. The journey creates `SLOW` just before the press that
 * edits (`writeFileSync(join(gui.directory, SLOW), "")`), so that the analyses `ddd gui` starts
 * with are fast. The plugin reports no finding.
 */
export function slowAnalyses(directory: string, project: string, seconds = 3): void {
  const plugin = [
    "import time",
    "from pathlib import Path",
    "",
    "from ddd.plugins import Plugin",
    "",
    "",
    "def check(context):",
    `    if Path(__file__).with_name("${SLOW}").exists():`,
    `        time.sleep(${seconds})`,
    "",
    "",
    'PLUGIN = Plugin(name="slow", check=check)',
    "",
  ];
  writeFileSync(join(directory, "slow.py"), plugin.join("\n"), "utf8");
  editJson(directory, project, (data) => {
    data.project.plugins = [...(data.project.plugins ?? []), "slow.py"];
  });
}
```

  Run `cd gui && npm run lint && npm run typecheck`. Nothing uses them yet.
- [ ] **Step 2: The worked journey,** in a new `gui/e2e/updating.spec.ts`: the head of the file with its one helper, and the journey of a constant just declared.

```ts
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { SLOW, slowAnalyses } from "./demo";
import { expect, test } from "./fixtures";

// An entry's panel just after a rename or a declaration (part 19c, row 10). The server answers a
// request about the entry from the analysis it last finished, and that does not know the new
// spelling yet: it refuses with "unreadable" until the analysis of the edit lands. While the page
// knows its findings are updating, the panel does not show that refusal; it shows its title and
// "Updating the findings…" alone (`panelShows`, lib/refusals.ts), and the whole panel once the
// analysis has landed. The examples analyse in a few milliseconds, too fast to see: the copies
// here are slowed (`slowAnalyses`) from the press that edits, by `SLOW` made just before it.

/** The panel named `name` as an entry just renamed or declared draws it: its title and the one
 * line "Updating the findings…", with `whole(panel)`, a field only the whole panel has, nowhere
 * to be found; then, with nothing done meanwhile, the whole panel, and the line gone. The line is
 * looked for in the panel, since the project's heading says the findings are updating too. */
async function updatingUntilItLands(
  page: Page,
  name: string,
  whole: (panel: Locator) => Locator,
): Promise<void> {
  const panel = page.getByRole("complementary", { name });
  await expect(panel.getByText("Updating the findings…")).toBeVisible();
  await expect(whole(panel)).toHaveCount(0);
  await expect(whole(panel)).toBeVisible();
  await expect(panel.getByText("Updating the findings…")).toHaveCount(0);
}

/** The textbox that renames `name`, which the whole panel has. */
const renaming = (name: string) => (panel: Locator) =>
  panel.getByRole("textbox", { name: `Rename ${name} to`, exact: true });

test("a constant just declared shows its panel saying the findings are updating, until the analysis lands", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => slowAnalyses(directory, "demo.ddd.json"));
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  await page.getByRole("button", { name: "Declare an entry" }).click();
  await page
    .getByRole("complementary", { name: "Declare an entry" })
    .getByRole("combobox", { name: "Vocabulary" })
    .press("ArrowDown");
  await page.getByRole("option", { name: "constants", exact: true }).click();
  const form = page.getByRole("complementary", { name: "Declare a constant" });
  await form.getByRole("textbox", { name: "Name" }).fill("SPARE_SLOTS");
  await form.getByRole("textbox", { name: "Value" }).fill("4");
  const apply = form.getByRole("button", { name: "Apply to 2 files" });
  await expect(apply).toBeVisible();

  writeFileSync(join(gui.directory, SLOW), "");
  await apply.click();
  await updatingUntilItLands(page, "SPARE_SLOTS", renaming("SPARE_SLOTS"));
});
```

  Read off the running page before asserting: the sentence "Updating the findings…" (`UpdatingNote.tsx`); the panel's name, which is the new name; the field only the whole panel has. `copiedGui`'s `change` runs before the server starts, so the analyses it starts with are fast; `SLOW` is created in the copy's directory (`gui.directory`) just before the press, and from then on every analysis takes three seconds.
- [ ] **Step 3: Run it** after a build, with `--repeat-each=10`: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test updating.spec.ts --repeat-each=10 --output=<a path outside the repository>`. Then the ablation: `ConstantPanel.tsx`'s `if (answer.shown === "updating") {` to `if (false) {`, in a scratch copy of the package. It must die at "Updating the findings…" (`Expected: visible`, `element(s) not found`), which the panel then never says.
- [ ] **Step 4: The other rows of row 10,** each a journey of its own in `updating.spec.ts`, after the first:

```ts
// Each of the Shared files tab's three panels, renamed from itself.
const RENAMED = [
  { kind: "constant", entry: /^TREND_SAMPLES/, from: "TREND_SAMPLES", to: "TREND_SLOTS" },
  { kind: "section", entry: /^\.calib/, from: ".calib", to: ".tuning" },
  { kind: "raster", entry: /^1ms/, from: "1ms", to: "2ms" },
] as const;

for (const { kind, entry, from, to } of RENAMED) {
  test(`a ${kind} just renamed shows its panel saying the findings are updating, until the analysis lands`, async ({
    page,
    copiedGui,
  }) => {
    const gui = await copiedGui("vocabulary", (directory) =>
      slowAnalyses(directory, "project.ddd.json"),
    );
    await page.goto(gui.address);
    await page.getByRole("link", { name: "Shared files", exact: true }).click();
    await page.getByRole("row", { name: entry }).click();
    const panel = page.getByRole("complementary", { name: from });
    await renaming(from)(panel).fill(to);
    const apply = panel.getByRole("button", { name: /^Apply to/ });
    await expect(apply).toBeVisible();

    writeFileSync(join(gui.directory, SLOW), "");
    await apply.click();
    await updatingUntilItLands(page, to, renaming(to));
  });
}

test("a unit just renamed shows its panel saying the findings are updating, until the analysis lands", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("vocabulary", (directory) =>
    slowAnalyses(directory, "project.ddd.json"),
  );
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "rpm" });
  const picker = panel.getByRole("combobox", { name: "Rename rpm to" });
  await picker.fill("rev/min");
  await picker.press("Enter");
  const apply = panel.getByRole("button", { name: /^Apply to/ });
  await expect(apply).toBeVisible();

  writeFileSync(join(gui.directory, SLOW), "");
  await apply.click();
  await updatingUntilItLands(page, "rev/min", (whole) =>
    whole.getByRole("combobox", { name: "Rename rev/min to" }),
  );
});

test("a type just renamed shows its panel saying the findings are updating, until the analysis lands", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("structures", (directory) =>
    slowAnalyses(directory, "project.ddd.json"),
  );
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  await renaming("Temperature_t")(panel).fill("Temp_t");
  const apply = panel.getByRole("button", { name: /^Apply to/ });
  await expect(apply).toBeVisible();

  writeFileSync(join(gui.directory, SLOW), "");
  await apply.click();
  await updatingUntilItLands(page, "Temp_t", renaming("Temp_t"));
});

test("a variable just declared shows its panel saying the findings are updating, until the analysis lands", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => slowAnalyses(directory, "demo.ddd.json"));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  // A new measurement, as declarations.spec.ts declares one: nothing in the analysis declares it
  // yet. A variable another component produces (ValueC, read into Controller) is known to the
  // analysis already, and its panel never says the findings are updating.
  for (const [field, value] of [
    ["Name", "Pressure"],
    ["Scope", "produces"],
    ["Kind", "measurement"],
    ["Volatile of Pressure", "false"],
    ["Datatype of Pressure", "uint8"],
  ] as const) {
    const input = adding.getByRole("combobox", { name: field });
    await input.fill(value);
    await input.press("Enter");
  }
  const apply = adding.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeVisible();

  writeFileSync(join(gui.directory, SLOW), "");
  await apply.click();
  // The whole panel has the keys table, a grid.
  await updatingUntilItLands(page, "Pressure", (whole) => whole.getByRole("grid"));
});
```

  The loop is the Shared files tab's three panels renamed, each in a copy of `examples/vocabulary`; the unit is renamed in one too, the type in a copy of `examples/structures`, and the variable is declared in a copy of the demo. Run the file with `--repeat-each=10`, then ablate each panel's `if (answer.shown === "updating") {` as the table says: it kills its own journeys, and no other. Then the shared decision, which kills all seven.
- [ ] **Step 5: Row 11,** the whole of a new `gui/e2e/changes.spec.ts`: one helper, and a journey for each view, the set-ups being those of the existing journeys that press "Show changes".

```ts
import type { Locator, Page } from "@playwright/test";
import { CONTROLLER, chooseUnit, openValues, unstamp } from "./demo";
import { expect, test } from "./fixtures";

// The changes a plan makes, shown and then hidden again (part 19c, row 11). Every panel that
// offers an Apply offers the lines it would write behind a button that reads "Show changes",
// and that reads "Hide changes" while they are shown (`Changes`, components/Changes.tsx, one
// `<pre class="hunk">` for each hunk of each file). Each view writes that toggle itself, so each
// has its journey; the existing journeys of the panels press "Show changes" and none presses
// "Hide changes".

/** "Show changes" pressed in `where`: `lines` hunks are shown; "Hide changes" pressed: none is,
 * and "Show changes" is offered again. */
async function shownThenHidden(where: Locator | Page, lines: number): Promise<void> {
  await where.getByRole("button", { name: "Show changes" }).click();
  await expect(where.locator(".hunk")).toHaveCount(lines);
  await where.getByRole("button", { name: "Hide changes" }).click();
  await expect(where.locator(".hunk")).toHaveCount(0);
  await expect(where.getByRole("button", { name: "Show changes" })).toBeVisible();
  await expect(where.getByRole("button", { name: "Hide changes" })).toHaveCount(0);
}

test("a variable's changes are shown and hidden again, the settlement's and the removal's each", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await chooseUnit(page, "rpm");
  const panel = page.getByRole("complementary", { name: "ValueA" });
  // The two blocks of the panel each have a pair of their own, as undone as they are shown.
  await shownThenHidden(panel.getByRole("region", { name: "Settle the key" }), 2);
  await shownThenHidden(panel.getByRole("region", { name: "Remove the declaration" }), 1);
});

test("a unit's changes are shown and hidden again", async ({ page, vocabularyGui }) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const describing = page
    .getByRole("complementary", { name: "rpm" })
    .getByRole("region", { name: "Description" });
  await describing.getByRole("textbox", { name: "Description" }).fill("revolutions per minute");
  await shownThenHidden(describing, 1);
});

test("a type's changes are shown and hidden again", async ({ page, structuresGui }) => {
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  await panel.getByRole("row", { name: "Limits", exact: true }).click();
  await panel.getByLabel("Max", { exact: true }).fill("120");
  await shownThenHidden(panel, 1);
});

// The Shared files tab's three panels, each with the one field of it that is saved alone.
const ENTRIES = [
  { kind: "constant", entry: /^TREND_SAMPLES/, panel: "TREND_SAMPLES", field: "Value", text: "32" },
  { kind: "section", entry: /^\.calib/, panel: ".calib", field: "Alignment", text: "8" },
  { kind: "raster", entry: /^100ms/, panel: "100ms", field: "Event", text: "5" },
] as const;

for (const { kind, entry, panel, field, text } of ENTRIES) {
  test(`a ${kind}'s changes are shown and hidden again`, async ({ page, vocabularyGui }) => {
    await page.goto(vocabularyGui.address);
    await page.getByRole("link", { name: "Shared files", exact: true }).click();
    await page.getByRole("row", { name: entry }).click();
    const saving = page
      .getByRole("complementary", { name: panel })
      .getByRole("region", { name: field });
    await saving.getByRole("textbox", { name: field }).fill(text);
    await shownThenHidden(saving, 1);
  });
}

test("the changes of an entry being declared are shown and hidden again", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  await page.getByRole("button", { name: "Declare an entry" }).click();
  await page
    .getByRole("complementary", { name: "Declare an entry" })
    .getByRole("combobox", { name: "Vocabulary" })
    .press("ArrowDown");
  await page.getByRole("option", { name: "constants", exact: true }).click();
  const form = page.getByRole("complementary", { name: "Declare a constant" });
  await form.getByRole("textbox", { name: "Name" }).fill("SPARE_SLOTS");
  await form.getByRole("textbox", { name: "Value" }).fill("4");
  await shownThenHidden(form, 2);
});

test("the changes of a declaration being added are shown and hidden again", async ({
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
  await shownThenHidden(adding, 1);
});

test("a finding's fix has its changes shown and hidden again", async ({ page, copiedGui }) => {
  const started = await copiedGui("demo", (directory) => {
    unstamp(directory, CONTROLLER, "ValueH");
  });
  await page.goto(started.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await page.getByRole("row", { name: "missing-id" }).click();
  const panel = page.getByRole("complementary", { name: "missing-id" });
  await panel.getByRole("button", { name: "Give 'ValueH' an id" }).click();
  await shownThenHidden(panel, 1);
});

test("a file's changes are shown and hidden again", async ({ page, vocabularyGui }) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("row", { name: "units.ddd.json" }).click();
  const removing = page
    .getByRole("complementary", { name: "units.ddd.json" })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(removing.getByRole("button", { name: "Remove from the includes" })).toBeVisible();
  await shownThenHidden(removing, 1);
});

test("a value's changes are shown and hidden again", async ({ page, gui }) => {
  await openValues(page, gui.address, "CurveA");
  await page.getByRole("textbox", { name: "element 3" }).fill("7.5");
  await shownThenHidden(page, 1);
});

test("an undo's changes are shown and hidden again", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await chooseUnit(page, "rpm");
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  await page.getByRole("button", { name: "Undo the unit of ValueA" }).click();
  await shownThenHidden(page.getByRole("region", { name: "Undo" }), 2);
});

test("the adoption's changes are shown in a panel of their own, which Hide changes closes", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await banner.getByRole("button", { name: "Show changes" }).click();
  // Not a toggle: the banner's "Show changes" opens a panel beside the table, and the panel's
  // "Hide changes" is its way out (`AdoptPanelView`'s `onClose`), the banner's staying as it was.
  const preview = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  await expect(preview.locator(".hunk").first()).toBeVisible();
  await preview.getByRole("button", { name: "Hide changes" }).click();
  await expect(preview).toHaveCount(0);
  await expect(banner.getByRole("button", { name: "Show changes" })).toBeVisible();
});
```

  Read off the running page before asserting: the hunk counts (a hunk is one `<pre class="hunk">` of `Changes`, one for each hunk of each file the plan writes), and, for the adoption, that its "Hide changes" is the panel's own and closes it. Run the file with `--repeat-each=10`, then ablate each toggle as the table says. Each dies at its own journey, the variable panel's two at the two pairs of the same one.
- [ ] **Step 6: Rows 12 and 13,** in `gui/e2e/undo.spec.ts`. The imports of `./demo` become

```ts
import {
  CONTROLLER,
  chooseUnit,
  drift,
  driftIn,
  failing,
  held,
  SERVER_FAILED,
  UNITS,
} from "./demo";
```

  and, at the end of the file, a helper and the two journeys:

```ts
/** An edit of the page's own to undo, and the analysis of it landed: ValueA's unit chosen as
 * `rpm` in Controller's panel and applied. The strip's preview is asked for under the revision
 * the page holds, so one asked before the analysis lands is asked again when it does. */
async function appliedAndAnalysed(page: Page, address: string): Promise<void> {
  await page.goto(address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await chooseUnit(page, "rpm");
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
}

test("the strip says it is reading the files an undo would put back, until it has", async ({
  page,
  gui,
}) => {
  await appliedAndAnalysed(page, gui.address);
  const undo = page.getByRole("button", { name: "Undo the unit of ValueA" });
  const release = await held(page, "/api/undo");
  try {
    await undo.click();
    await expect(undo).toHaveAttribute("aria-expanded", "true");
    await expect(strip(page).getByText("Reading the files…")).toBeVisible();
    await expect(strip(page).getByRole("button")).toHaveCount(0);
  } finally {
    release();
  }
  await expect(
    strip(page).getByText("Puts back 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();
  await expect(strip(page).getByText("Reading the files…")).toHaveCount(0);
});

test("an undo the server fails on is refused in the strip, with nothing put back and the entry kept", async ({
  page,
  gui,
}) => {
  await appliedAndAnalysed(page, gui.address);
  const written = readFileSync(join(gui.directory, CONTROLLER));
  // The undo alone: the preview shares the path, and is a GET.
  const failed = await failing(page, "/api/undo", "http", 1, "POST");
  const undo = page.getByRole("button", { name: "Undo the unit of ValueA" });
  await undo.click();
  const putBack = strip(page).getByRole("button", { name: "Put back 2 files" });
  await putBack.click();
  // The refusal is the whole of the strip: an undo is all or nothing.
  await expect(strip(page).getByRole("status")).toHaveText(
    `The undo was refused: ${SERVER_FAILED}`,
  );
  await expect(strip(page).getByRole("button")).toHaveCount(0);
  expect(failed()).toBe(1);
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(written)).toBe(true);
  await expect(undo).toBeVisible();

  // The way back is to close the strip, which clears the refusal, and open it again: the preview
  // is read again, and the undo, no longer failed, goes through.
  await undo.click();
  await expect(strip(page)).toHaveCount(0);
  await undo.click();
  await putBack.click();
  await expect(undo).toHaveCount(0);
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(written)).toBe(false);
});
```

  The helper waits for "Nothing to change", the reader's sign that the analysis of the Apply has landed (see above). `strip` is the file's own helper for the region "Undo". Run the file with `--repeat-each=10`, then ablate as the table says.
  The added row, "the files an undo puts back, failing to be read", is a journey of its own in `undo.spec.ts`, beside row 13's. It is run with `--repeat-each=10` and killed by its row's change.
- [ ] **Step 7: Bugs.** None of rows 10 to 13 has one to fix. Any bug a journey finds follows the rule in *Global Constraints*; the strip's flash on every revision is recorded, not fixed.
- [ ] **Step 8: The documentation.** In `docs/developer_documentation.rst`, after the paragraph on `copiedGui` and `failing` (the one that ends "so a banner it raises reads as the one a real failure raises.", with whatever earlier tasks of this part added after it), a paragraph for the helper:

```rst
``slowAnalyses``, in ``gui/e2e/demo.ts``, changes a copy before ``ddd gui`` starts on it so
that every analysis takes seconds longer while a file named ``slow`` lies in the copy's
directory: a project plugin, ``slow.py``, whose check sleeps, named in the ``plugins`` of the
project description. An example analyses in a few milliseconds, which leaves a journey no
moment to see the page between an edit and the analysis that follows it. The journey creates
the file just before the press that edits, so that the analyses ``ddd gui`` starts with are
fast. The plugin reports no finding.
```
- [ ] **Step 9: The inventory.** The four rows (*an entry's panel just after a rename or a declaration, saying the findings are updating until the analysis lands*; *the changes a plan makes, shown and then hidden again*; *the files an undo puts back, being read*; *an undo the server fails on*) name their journeys, by file, line and title.
- [ ] **Step 10: The gates,** every journey included, and the docs. Commit: one for the helper and `updating.spec.ts`; one for `changes.spec.ts`; one for the strip's two journeys; one for the documentation.

### A.4 The canvas and the components table, rows 14 and 16 to 22

**Model:** opus, reviewed on opus. Three of the canvas's states cannot be reached by an ordinary change - a layout too deep for dagre, a worker that dies, a focus that has to leave by hand - so this task measures where the code is silent, and writes the three helpers that reach them.

**Files:**
- Modify: `gui/e2e/canvas.spec.ts` (the rows), `gui/e2e/demo.ts` (the three helpers), `gui/e2e/helpers.spec.ts` (their journeys), `docs/developer_documentation.rst`, and this plan's *The inventory*

**Interfaces:**
- Consumes:
  - `failing(page: Page, path: string | RegExp, how: "http" | "network", times?: number, method?: "GET" | "POST"): Promise<() => number>` and `SERVER_FAILED`, in `gui/e2e/demo.ts`;
  - `editJson(directory: string, file: string, change: (data: any) => void): void` (Task 1);
  - `copiedGui` (`gui/e2e/fixtures.ts`), and `drift`, `driftMax`, `CONTROLLER`, `EVENT_LOGGER` (`demo.ts`);
  - in `canvas.spec.ts`, its own `viewportOf`, `moduleOf` and `withoutValueEInEventLogger`.
- Produces, in `gui/e2e/demo.ts`:
  - `tabTo(page: Page, target: Locator, limit?: number): Promise<void>`: presses Tab until `target` is the page's active element, at most `limit` (50) times, and throws, naming the locator, if it never is;
  - `dyingWorker(page: Page): Promise<void>`: serves the layout worker's script, once, with a few lines in front that make the worker throw, uncaught, on the second layout it is asked for;
  - `writeChain(directory: string, count: number): void`: makes a `copiedGui("demo", …)` copy a chain of `count` components, the project naming that chain alone.

**What the pre-flight found:**
- **Row 15, the canvas kept under a failing read of a new revision, is Task 2's.** This task writes none of it, and none of its rows waits on it.
- **Row 14 is written in its HTTP flavour (P19c-13).** `network.spec.ts`'s "a GET the network fails every time reads as the server not answering" is the same state in its network flavour (`ddd gui is not answering`, two sends) and stays; this one shows the server's own sentence, as every other tab's "failing to load" row does. Task 2 moves the decision that draws the alert alone out of `GraphPage.tsx` into a library function, and has by the time this task runs: the ablation below is written against what it left.
- **Row 16 needs a file that parses and breaks its schema.** A truncated file is kind `unknown`, is no component and draws no module at all (measured: the graph holds three), which is why the no-dictionary journey of this file cannot show it. A file that parses and fails its schema is a component that did not load. The canvas names it by the file's stem - `controller (not loaded)` (`api.py`'s `_module`: `file.name if file.loaded and file.name else stem`) - while the Table tab calls it "Controller": deliberate, and no bug.
- **Row 17 is two states and a precedence,** written as one journey in two phases: two warnings alone, then an error beside them, which the badge counts alone. The badge is a `role="img"` span whose text is the bare number and whose name is built ``${badge} ${tone}${badge > 1 ? "s" : ""}`` (`ModuleNode.tsx`): `1 error`, `2 errors`, `1 warning`, `2 warnings`. A module with only notes draws no badge, by the code and not pinned.
- **Row 18 needs an arrow in disagreement,** so ValueA's unit is drifted before the page opens: an agreed arrow says only its objects. The arrow's name is built by `sentenceOf` (``${source} to ${target}: ${count} ${count > 1 ? "variables" : "variable"}, ${state}``), and its description is the tooltip's text, which `FlowEdge.tsx` builds of the objects (`data.objects.join(", ")`) and, for each disagreement, its check and its message. The journey leaves the arrows by a press on the heading and not by Tab: Tab to the next arrow closes the tooltip by opening that arrow's own, and would hide an `onBlur` that closed nothing (measured: with `onBlur` removed, a version of this journey that leaves by Tab passes all the same).
- **Row 19's end stop is an addition,** the only pin of `<ReactFlow minZoom>`. The buttons are React Flow's `Controls`: the journey pins that the page offers them, and their step (1.2), not their logic.
- **Row 20 is reached by a chain 3000 deep, made by `writeChain` (P19c-12).** In Chrome on Linux 900 modules lay out in full and 1000 do not (the worker's dagre overflows its stack: about 908 by the code's own comment). `generatedGui` cannot serve, since its components lie in layers about 30 across and its 666 lay out in full (measured: no note). 3000 is 3.3 times the Linux limit. The Windows limit and the time to write 3000 files there are unmeasured, so the first Windows leg measures them (Step 9).
- **Row 21 is reached by `dyingWorker` (P19c-11),** the layout worker's script served with a prefix that throws on its second layout. It is accepted as an honest reach, an injected failure as `failing` injects one, `{ times: 1 }` (P19b-7): nothing the server can answer makes the real worker fail so, since `layoutOf` rethrows only what is not a `RangeError`, and what dagre meets in a project - the demo's own 2-cycle, a chain too deep - lays out or falls back to ranks. The prefix stops the worker's own listener on that message (`stopImmediatePropagation`): without it the good answer follows the error and clears it (measured: 0 of 6 runs reach the alert).
- **Row 22 is two inputs for one wiring** (`ProjectPage`'s `onRowAction`): one journey with two halves, a different component for each so that one is not read as the other, and one ablation that kills both. React Aria owns what differs between a press and Enter.
- **Paths in sentences:** none of this task's sentences carries one. Row 22's address does: `/component?file=` and the server's `as_posix()` path, percent-encoded (`C%3A%2F…` on Windows), which the pattern in the row matches in either form.
- **Left as Task 1 leaves them:** the two held-request journeys of this file ("the canvas says it is drawing the project until the graph answers", "the canvas says it is laying the project out until the layout comes"), which Task 1 converts to `held`. `units.spec.ts`'s "an arrow in disagreement about two variables asks which, from the keyboard too" keeps its inline Tab loop: converting it would move the citation of every journey under it in that file.
- **What was measured,** in a scratch copy of the repository at `2bc00da` with these drafts in it, Chrome on the Linux development PC: the eight canvas journeys and the two helpers' journeys below passed ten times in a row (`--repeat-each=10`: 80 of 80, and 20 of 20), and all 24 ablations named in this task, applied to the sources and built into a scratch package, died at the assertion each names; none survived.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **the project's graph failing before anything is drawn** | `gui`; `failing(page, "/api/graph", "http")` before `page.goto`. | `GraphPage` draws `<Banner tone="error">{graph.error.message}</Banner>` and nothing else of the canvas: the `alert` reads the server's own sentence, `ddd gui failed on this request; the terminal it runs in shows why` (`SERVER_FAILED`); the region "Modules" and the text "Drawing the project…" both count 0, while the heading "DemoDevice" and the link "Table" stay. `failed()` is 1: an HTTP answer is never sent again. | The line that draws that alert alone while no graph was read - at `2bc00da`, `GraphPage.tsx`'s `if (graph.isError) return <Banner tone="error">{graph.error.message}</Banner>;`, which Task 2 has moved into a library function - made to draw "Drawing the project…" instead: dies at the alert's `toHaveText`. It kills `network.spec.ts`'s journey with it, since both draw `graph.error.message`; what only this one pins is the sentence, which `api/client.ts`'s `message` line decides (made `response.statusText`, the alert reads `Internal Server Error`). |
| **a module whose file does not load, drawn as not loaded** | `copiedGui("demo", withControllerNotLoading)`: Controller's first declaration, ValueA, given the `scope` `"sideways"` with `editJson`. The file parses and breaks its schema. | `.module.unloaded` has count 1 and holds the button `controller (not loaded)` (the file's stem; exact), with `border-top-style` `dashed`; the three other modules keep their names and are `solid`. No `img` (no badge) is drawn in the unloaded one, though its file carries one `schema` error. | Three, each killed alone: `ModuleNode.tsx`'s ``{data.loaded ? data.name : `${data.name} (not loaded)`}`` made `{data.name}` dies at the name; `app.css`'s `.module.unloaded` rule's `border-style: dashed;` made `solid` dies at `toHaveCSS`; `{data.loaded && badge > 0 && (` made `{badge > 0 && (` dies at "no `img`". |
| **a module's badge, counting its errors or its warnings** | `copiedGui("demo", …)` with `driftMax(directory, CONTROLLER, "ValueH", 5000)` and `driftMax(directory, CONTROLLER, "ParameterA", 20000)`: two `limits-out-of-range` warnings on Controller, whose variables are local, so no disagreement. | Phase 1: inside Controller's `.module`, `getByRole("img", { name: "2 warnings", exact: true })` has the text "2" and the class `badge warning`; the other three modules hold no `img`. Phase 2: `drift(gui.directory)` writes ValueA's unit as `rpm`, plainly: Controller's badge becomes `1 error` (text "1", class `badge error`) and is the only `img` there - errors win over the two warnings - and SensorHub, the other end of the disagreement, shows `1 error` too. | Four, each killed alone: `ModuleNode.tsx`'s `const badge = data.errors > 0 ? data.errors : data.warnings;` with the two swapped dies in phase 2; `const tone = data.errors > 0 ? "error" : "warning";` made `"warning"` dies in phase 2; `${badge > 1 ? "s" : ""}` made empty dies in phase 1; `badge > 0 &&` made `badge >= 0 &&` dies at the clean modules' "no `img`". |
| **an arrow reached by the keyboard, saying what is wrong** | `gui`; `drift(gui.directory)` before `page.goto`, so that SensorHub to Controller is in error. | `tabTo` the button `SensorHub to Controller: 2 variables, error` (the 16th Tab). It is focused; `getByRole("tooltip")` has count 1 and contains "definition-mismatch"; and the arrow's accessible description is the whole `ValueA, ValueB definition-mismatch 'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (unit: 'rpm' != '%')`: its objects, its check, its message. A press on the level-1 heading takes the focus off the arrows, and the tooltip count is 0. | Three, each killed alone: `lib/canvas.ts`'s `onFocus: () => onReached(id),` removed dies at the tooltip count (0 for 1); `"aria-describedby": tooltip,` removed dies at the description; `onBlur: () => onReached(null),` removed dies at the last count. |
| **zoomed in and out with the canvas's own buttons** | `gui`. | The buttons "Zoom In" and "Zoom Out" are React Flow's `Controls`; each is asserted visible before it is pressed. Read the viewport as `viewportOf` does (the opening zoom is 1.11494). "Zoom In" takes the zoom to `opening.zoom * 1.2`, at once (`expect.poll`, `toBeCloseTo(…, 3)`); "Zoom Out" brings the viewport back to the opening one (x and y within half a pixel, the zoom to three digits). Then "Zoom Out" is pressed while it is enabled, at most twelve times (five from the opening view): it ends `toBeDisabled()` at zoom 0.5, the canvas's least. | `GraphPage.tsx`'s `<Controls showInteractive={false} showFitView={false} />` removed dies at the buttons' `toBeVisible`; `minZoom={MIN_ZOOM}` made `minZoom={0.1}` dies at `toBeDisabled` (the button is still enabled at 0.5). |
| **laid out in ranks only, for a project too large for the full layout** | `copiedGui("demo", (directory) => writeChain(directory, 3000))`. | `getByText("Laid out in ranks only: the project is too large for the full layout.", { exact: true })` is visible, as a note: `getByRole("alert")` has count 0. The button "C00000" is visible, and the viewport's zoom is 0.5, the canvas having opened on the first rank at its least zoom (`openingViewport`). | Three, each killed alone: `layoutAnswers.ts`'s `note: state.ranksOnly ? RANKS_ONLY_NOTE : null,` made `note: null,` dies at the note; `layout.ts`'s `if (error instanceof RangeError) return { placed: ranked(modules, flows), ranksOnly: true };` with `ranksOnly: false` dies at the note (the canvas still draws: what is pinned is the worker's decision); `canvas.ts`'s `openingViewport`, in its last `getViewportForBounds(boundsOf(firstRank), …)`, the `maxZoom` argument (the second `minZoom`) made `MAX_ZOOM`, dies at zoom 0.5 (received 2). |
| **a later layout failing, the canvas kept** | `gui`, with `dyingWorker(page)` before `page.goto`: the first layout is answered, the second throws. | The button "Controller" is visible and there is no `alert`. Then `withoutValueEInEventLogger(gui.directory)` changes the shape from outside (one arrow fewer), and the worker's second layout throws: the `alert` above the canvas (`getByRole("alert").and(page.locator(":above(section.canvas)"))`) reads `The layout worker stopped; reload the page to try again.`, the button "Controller" is still visible, and "Laying the project out…" has count 0. | Three: `layoutAnswers.ts`'s `if (answer.error !== undefined) return { ...state, error: answer.error };` with `{ ...INITIAL_LAYOUT_STATE, error: answer.error }` empties the canvas and dies at the alert-over-the-canvas locator; `GraphPage.tsx`'s `{screen.errorMessage !== null && <Banner tone="error">{screen.errorMessage}</Banner>}` removed dies at the same locator, with no alert at all; `event.stopImmediatePropagation();` removed from `dyingWorker`'s prefix dies there too. "a layout worker that cannot start says to reload, and a reload draws the canvas" survives all three. |
| **a row pressed beside its name, or Enter on it, opening its component** | `gui`. | On the Table tab, `rowOf(name)` is the row of the grid "Components" holding the button `name`. A press on SensorHub's File cell (its last `gridcell`) opens `/component?file=…sensor_hub.ddd.json` - matched as `/\/component\?file=.*sensor_hub\.ddd\.json$/`, which holds in either path form - with the heading "SensorHub" (level 1); `page.goBack()` returns to the grid. Then `tabTo` Controller's row, the first stop in the grid, and Enter: the address ends `controller.ddd.json` and the heading is "Controller". | `ProjectPage.tsx`'s `onRowAction={(key) => onComponent(String(key))}` removed dies at the first address (received `/project?view=table`). One wiring serves both inputs, so no change to the page kills the Enter half alone. `large.spec.ts`'s "an edit shows at once, and its findings follow", which presses the name button, survives it. |

- [ ] **Step 1: The helpers,** three, added at the end of `gui/e2e/demo.ts`. `Locator`, `Page`, `join`, `mkdirSync`, `readFileSync` and `writeFileSync` are imported there already.

```ts
/**
 * Presses Tab, as a keyboard reader does, until `target` is the page's active element, and
 * throws, in words that say so, if it is not within `limit` presses: a journey that reaches an
 * element by the keyboard then fails here, not at whatever assertion happens to come next. An
 * element already focused is left where it is, with no press made. The element must be on the
 * page when this is called.
 */
export async function tabTo(page: Page, target: Locator, limit = 50): Promise<void> {
  for (let presses = 0; ; presses += 1) {
    if (await target.evaluate((element) => element === document.activeElement)) return;
    if (presses === limit) throw new Error(`${target} was not reached by ${limit} presses of Tab`);
    await page.keyboard.press("Tab");
  }
}
```

```ts
/**
 * What `dyingWorker` puts in front of the layout worker's script: a listener, first among the
 * worker's own, that counts the layouts the worker is asked for and throws, uncaught, on the
 * second. `stopImmediatePropagation` keeps the worker's real listener from answering that
 * message: its good answer would follow the error, and clear it.
 */
const DIES_ON_ITS_SECOND_LAYOUT = `{
  let asked = 0;
  self.addEventListener("message", (event) => {
    asked += 1;
    if (asked !== 2) return;
    event.stopImmediatePropagation();
    throw new Error("the layout worker died on its second layout");
  });
}
`;
```

```ts
/**
 * Serves the page's layout worker with its script behind `DIES_ON_ITS_SECOND_LAYOUT`: the first
 * layout is answered as ever, and the worker then fails, for real and uncaught, on the second, as
 * a worker that died after it started would. An injected failure, as `failing` injects one
 * (ruling P19c-11): no answer the server gives can make the real worker fail so. Once only
 * (`{ times: 1 }`, ruling P19b-7): a route that forwards with `route.fetch` handles its one
 * request and no other.
 */
export async function dyingWorker(page: Page): Promise<void> {
  await page.route(
    "**/assets/layoutWorker-*.js",
    async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, body: DIES_ON_ITS_SECOND_LAYOUT + (await response.text()) });
    },
    { times: 1 },
  );
}
```

```ts
/**
 * A copy of examples/demo made a chain of `count` components: `chain/c00000.ddd.json` and so on,
 * each producing one measurement, `V00000` and so on, and, the first excepted, reading the one
 * before it and stating what its producer states, and the project description naming that chain
 * alone. A chain this deep overflows the stack of dagre's recursion in the layout worker (about
 * 900 modules in Chrome on Linux: 900 lay out in full, 1000 do not, measured), so the canvas is
 * laid out in ranks only; 3000 is 3.3 times that, and the Windows limit is unmeasured (ruling
 * P19c-12). Written in a few milliseconds: 17 for 3000 on the Linux development PC.
 */
export function writeChain(directory: string, count: number): void {
  const chain = join(directory, "chain");
  mkdirSync(chain);
  const declaration = (n: number) => ({
    name: `V${String(n).padStart(5, "0")}`,
    kind: "measurement",
    datatype: "uint16",
    conversion: { kind: "identity" },
    volatile: false,
  });
  for (let n = 0; n < count; n += 1) {
    const interfaced: { scope: string; definition: object }[] = [
      { scope: "output", definition: declaration(n) },
    ];
    if (n > 0) interfaced.push({ scope: "input", definition: declaration(n - 1) });
    writeFileSync(
      join(chain, `c${String(n).padStart(5, "0")}.ddd.json`),
      JSON.stringify({
        component: { name: `C${String(n).padStart(5, "0")}`, interface: interfaced },
      }),
    );
  }
  const project = join(directory, "demo.ddd.json");
  const description = JSON.parse(readFileSync(project, "utf8"));
  description.project.includes = ["chain/*.ddd.json"];
  writeFileSync(project, JSON.stringify(description, null, 2));
}
```

- [ ] **Step 2: The helpers' journeys,** two in `gui/e2e/helpers.spec.ts` (add `tabTo` and `writeChain` to its import from `./demo`). `dyingWorker` has no journey of its own: row 21's is its proof, and its third ablation.

```ts
test("a copy made a chain is served as that many components, each reading the one before", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => writeChain(directory, 6));
  await page.goto(gui.address);
  // Six modules and none of the demo's own, an arrow from each to the next: the first produces and
  // reads nothing, every other reads what the one before states.
  const canvas = page.getByRole("region", { name: "Modules" });
  await expect(canvas.locator(".react-flow__node")).toHaveCount(6);
  await expect(canvas.getByRole("button", { name: "C00000", exact: true })).toBeVisible();
  await expect(canvas.getByRole("button", { name: "C00005", exact: true })).toBeVisible();
  await expect(canvas.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);
  await expect(canvas.getByRole("group")).toHaveCount(5);
  for (const arrow of ["C00000 to C00001", "C00004 to C00005"]) {
    await expect(
      canvas.getByRole("group", { name: `${arrow}: 1 variable, agreed`, exact: true }),
    ).toHaveCount(1);
  }
  // No error anywhere: the one finding that is not a note is the last measurement, which nobody
  // reads.
  await page.getByRole("link", { name: "Table", exact: true }).click();
  await expect(page.locator("p.summary")).toHaveText("0 errors, 1 warning");
});
```

```ts
test("Tab is pressed until a control is reached, and one the keyboard never reaches is reported", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const fit = page.getByRole("button", { name: "Fit", exact: true });
  await expect(fit).toBeVisible();
  await tabTo(page, fit);
  await expect(fit).toBeFocused();
  // Already there: no press is made, and the focus stays.
  await tabTo(page, fit);
  await expect(fit).toBeFocused();
  // A heading takes no focus from Tab, so three presses are spent and the helper says so.
  await expect(tabTo(page, page.getByRole("heading", { level: 1 }), 3)).rejects.toThrow(
    /was not reached by 3 presses of Tab/,
  );
});
```

  Run both after a build, with `--repeat-each=10`. Then the ablations, each in a scratch copy of the package: `writeChain`'s `if (n > 0) interfaced.push(…)` removed dies at the arrows' `toHaveCount(5)`; its `description.project.includes = ["chain/*.ddd.json"];` removed dies at the nodes' `toHaveCount(6)`; `tabTo`'s `throw new Error(…)` made `return` dies at `rejects.toThrow` (the promise resolves); its `await page.keyboard.press("Tab");` removed dies at the first `tabTo`, which throws that Fit was not reached by 50 presses.
- [ ] **Step 3: The worked journey,** row 18's, in `gui/e2e/canvas.spec.ts` (add `tabTo` to its import from `./demo`; Steps 4 and 5 add the rest):

```ts
test("an arrow reached by the keyboard says what is wrong, and says it no longer once focus has left", async ({
  page,
  gui,
}) => {
  drift(gui.directory);
  await page.goto(gui.address);
  const arrow = page.getByRole("button", { name: "SensorHub to Controller: 2 variables, error" });
  await expect(arrow).toBeVisible();

  await tabTo(page, arrow);
  await expect(arrow).toBeFocused();
  // The tooltip is drawn while the arrow is reached, and is its description: what a screen reader
  // reads out on arriving. The objects, then the check, then the message.
  const tooltip = page.getByRole("tooltip");
  await expect(tooltip).toHaveCount(1);
  await expect(tooltip).toContainText("definition-mismatch");
  await expect(arrow).toHaveAccessibleDescription(
    "ValueA, ValueB definition-mismatch 'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (unit: 'rpm' != '%')",
  );

  // Focus leaves the arrows altogether: a press on the project's heading, which takes none. (Tab
  // to the next arrow would close this tooltip by opening that arrow's, and hide a blur that
  // closed nothing.)
  await page.getByRole("heading", { level: 1 }).click();
  await expect(arrow).not.toBeFocused();
  await expect(tooltip).toHaveCount(0);
});
```

  The tooltip's whole sentence is the server's own, so read it off the running page before asserting it, as the draft was.
- [ ] **Step 4: Run it** after a build, with `--repeat-each=10`. Then the ablations of its row, one at a time, in a scratch copy of the package: `onFocus` removed must die at `toHaveCount(1)` of the tooltip, `"aria-describedby"` removed at `toHaveAccessibleDescription`, and `onBlur` removed at the last `toHaveCount(0)`.
- [ ] **Step 5: The other rows,** each a journey of its own in `canvas.spec.ts`, each run with `--repeat-each=10` and ablated as its row says. Add `driftMax`, `dyingWorker`, `editJson`, `failing`, `SERVER_FAILED` and `writeChain` to the file's import from `./demo` as each journey needs it, so that the typecheck never sees one unused; once all are used it reads, in the order `npx biome check --write` gives it (plus `held`, if Task 1 converted this file's two held-request journeys):

```ts
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import {
  CONTROLLER,
  drift,
  driftMax,
  dyingWorker,
  EVENT_LOGGER,
  editJson,
  failing,
  renameValueA,
  SERVER_FAILED,
  tabTo,
  writeChain,
} from "./demo";
import { expect, test } from "./fixtures";
```

```ts
test("the project's graph failing before anything is drawn leaves the server's own error, and no canvas", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, "/api/graph", "http");
  await page.goto(gui.address);
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("region", { name: "Modules" })).toHaveCount(0);
  await expect(page.getByText("Drawing the project…", { exact: true })).toHaveCount(0);
  // The rest of the page stands: the heading, and the tabs that read nothing of the graph.
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Table", exact: true })).toBeVisible();
  // An HTTP answer, a failure included, is never sent again.
  expect(failed()).toBe(1);
});
```

```ts
/**
 * The demo with ValueA's `scope` in Controller's file made "sideways": the file still parses, so
 * it stays a component the canvas draws, and breaks its schema, so it does not load (`schema`:
 * "Input should be 'input', 'output' or 'local' (got: 'sideways')"). A file saved half-written
 * would not do: it parses as nothing, is no component, and draws no module at all.
 */
function withControllerNotLoading(directory: string): void {
  editJson(directory, CONTROLLER, (data) => {
    const first = data.component.interface[0];
    if (first?.definition.name !== "ValueA") {
      throw new Error(`${CONTROLLER} no longer opens on ValueA`);
    }
    first.scope = "sideways";
  });
}
```

```ts
test("a module whose file does not load is drawn as not loaded, with no badge", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", withControllerNotLoading);
  await page.goto(gui.address);
  // Named by the file's stem, not the component's name, which the file did not get to state.
  const unloaded = page.locator(".module.unloaded");
  await expect(unloaded).toHaveCount(1);
  await expect(
    unloaded.getByRole("button", { name: "controller (not loaded)", exact: true }),
  ).toBeVisible();
  await expect(unloaded).toHaveCSS("border-top-style", "dashed");
  // Its file carries one error (`schema`), and a file that did not load shows no count of its own.
  await expect(unloaded.getByRole("img")).toHaveCount(0);
  for (const name of ["SensorHub", "UserInterface", "EventLogger"]) {
    await expect(moduleOf(page, name)).toHaveCSS("border-top-style", "solid");
  }
});
```

```ts
test("a module's badge counts its warnings, and its errors once it has any", async ({
  page,
  copiedGui,
}) => {
  // ValueH and ParameterA are local to Controller, so widening their greatest limits past what
  // their datatypes hold files two `limits-out-of-range` warnings on Controller alone, and no
  // disagreement anywhere.
  const gui = await copiedGui("demo", (directory) => {
    driftMax(directory, CONTROLLER, "ValueH", 5000);
    driftMax(directory, CONTROLLER, "ParameterA", 20000);
  });
  await page.goto(gui.address);
  const controller = moduleOf(page, "Controller");
  const warnings = controller.getByRole("img", { name: "2 warnings", exact: true });
  await expect(warnings).toHaveText("2");
  await expect(warnings).toHaveClass("badge warning");
  for (const name of ["SensorHub", "UserInterface", "EventLogger"]) {
    await expect(moduleOf(page, name)).toBeVisible();
    await expect(moduleOf(page, name).getByRole("img")).toHaveCount(0);
  }

  // A disagreement written from outside: Controller now has an error beside its two warnings,
  // and the badge counts the errors alone; SensorHub, the other end of it, has one too.
  drift(gui.directory);
  const errors = controller.getByRole("img", { name: "1 error", exact: true });
  await expect(errors).toHaveText("1");
  await expect(errors).toHaveClass("badge error");
  await expect(controller.getByRole("img")).toHaveCount(1);
  await expect(
    moduleOf(page, "SensorHub").getByRole("img", { name: "1 error", exact: true }),
  ).toHaveText("1");
});
```

```ts
test("the canvas's own buttons zoom it in and out, and the least zoom stops the way out", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  const opening = await viewportOf(page);
  const zoomIn = page.getByRole("button", { name: "Zoom In", exact: true });
  const zoomOut = page.getByRole("button", { name: "Zoom Out", exact: true });
  await expect(zoomIn).toBeVisible();
  await expect(zoomOut).toBeVisible();

  // One press is a fifth more, or a sixth less (React Flow's own step, 1.2), and at once.
  await zoomIn.click();
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeCloseTo(opening.zoom * 1.2, 3);
  await zoomOut.click();
  await expect
    .poll(() => viewportOf(page))
    .toEqual({
      x: expect.closeTo(opening.x, 0),
      y: expect.closeTo(opening.y, 0),
      zoom: expect.closeTo(opening.zoom, 3),
    });

  // The way out ends at the canvas's least zoom (`MIN_ZOOM`, 0.5), where its button is turned off.
  for (let presses = 0; presses < 12 && (await zoomOut.isEnabled()); presses += 1) {
    await zoomOut.click();
  }
  await expect(zoomOut).toBeDisabled();
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeCloseTo(0.5, 3);
});
```

```ts
test("a project too deep for the full layout is laid out in ranks only, and says so", async ({
  page,
  copiedGui,
}) => {
  // 3000 components, each reading the one before: dagre overflows its stack in the layout worker
  // long before (about 900 modules, in Chrome on Linux), and the worker ranks the modules by hand.
  const gui = await copiedGui("demo", (directory) => writeChain(directory, 3000));
  await page.goto(gui.address);
  await expect(
    page.getByText("Laid out in ranks only: the project is too large for the full layout.", {
      exact: true,
    }),
  ).toBeVisible();
  // A note over a canvas that is drawn, not a failure.
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "C00000", exact: true })).toBeVisible();
  // The canvas opens on the first rank, at the least zoom (`openingViewport`).
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeCloseTo(0.5, 3);
});
```

```ts
test("a layout that fails after one that was drawn leaves the canvas, with the worker's alert over it", async ({
  page,
  gui,
}) => {
  // The worker answers the canvas's first layout, and throws, uncaught, on its second.
  await dyingWorker(page);
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);

  // A shape the worker has not laid out: EventLogger stops reading ValueE, one arrow fewer.
  withoutValueEInEventLogger(gui.directory);
  await expect(page.getByRole("alert").and(page.locator(":above(section.canvas)"))).toHaveText(
    "The layout worker stopped; reload the page to try again.",
  );
  // The canvas is kept, as it was drawn, and nothing says it is being laid out again.
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(page.getByText("Laying the project out…", { exact: true })).toHaveCount(0);
});
```

```ts
test("a row of the components table opens its component, pressed beside its name or on Enter", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table", exact: true }).click();
  const grid = page.getByRole("grid", { name: "Components" });
  const rowOf = (name: string): Locator =>
    grid.getByRole("row").filter({ has: page.getByRole("button", { name, exact: true }) });

  // Beside the name: SensorHub's File cell holds no button, and a press on it still opens the row.
  await rowOf("SensorHub").getByRole("gridcell").last().click();
  await expect(page).toHaveURL(/\/component\?file=.*sensor_hub\.ddd\.json$/);
  await expect(page.getByRole("heading", { name: "SensorHub", level: 1 })).toBeVisible();
  await page.goBack();
  await expect(grid).toBeVisible();

  // On Enter: Tab reaches the first row of the grid, and Enter opens it.
  await tabTo(page, rowOf("Controller"));
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/component\?file=.*controller\.ddd\.json$/);
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();
});
```

  Read each sentence off the running page before asserting it. Row 20 writes 3000 files and runs about a second on the Linux development PC; if the first Windows leg shows it slower than the test's 60 s, or shows no note, say so in the report (Step 9).
- [ ] **Step 6: The documentation.** In `docs/developer_documentation.rst`, after the paragraph that ends "so a banner it raises reads as the one a real failure raises." (the one about `failing`), and beside the lines Task 1 added for its helpers, add:

```rst
``writeChain``, in ``gui/e2e/demo.ts``, makes a ``copiedGui`` copy of ``examples/demo`` a chain
of as many components as it is given, each reading the measurement of the one before it, with the
project naming that chain alone: three thousand are too deep for the dagre the layout worker
runs, so the canvas is laid out in ranks only. ``tabTo`` presses Tab until a control has the
focus, and throws if it never does. ``dyingWorker`` serves the page's layout worker with a few
lines in front that make it throw, uncaught, on its second layout: an injected failure, as
``failing`` injects one, for the canvas that keeps its modules under a layout that failed.
```

- [ ] **Step 7: Bugs.** None is expected of these rows, and the task changes no page: no CHANGELOG entry. A journey that finds a bug follows the rule in *Global Constraints*.
- [ ] **Step 8: The inventory.** Row 15 is Task 2's. The others name these journeys in `canvas.spec.ts`, each by its line and its title, with the task set to 9:
  - the project's graph failing before anything is drawn: "the project's graph failing before anything is drawn leaves the server's own error, and no canvas";
  - a module whose file does not load, drawn as not loaded: "a module whose file does not load is drawn as not loaded, with no badge";
  - a module's badge, counting its errors or its warnings: "a module's badge counts its warnings, and its errors once it has any";
  - an arrow reached by the keyboard, saying what is wrong: "an arrow reached by the keyboard says what is wrong, and says it no longer once focus has left";
  - zoomed in and out with the canvas's own buttons: "the canvas's own buttons zoom it in and out, and the least zoom stops the way out";
  - laid out in ranks only, for a project too large for the full layout: "a project too deep for the full layout is laid out in ranks only, and says so";
  - a later layout failing, the canvas kept: "a layout that fails after one that was drawn leaves the canvas, with the worker's alert over it";
  - a row pressed beside its name, or Enter on it, opening its component: "a row of the components table opens its component, pressed beside its name or on Enter".
- [ ] **Step 9: The gates,** every journey included, and the docs under `-W` in Docker (Global Constraints). No page changed, so the screenshots in compare mode must not move. Row 20's proof on Windows is the controller's full run (P19c-12): read the Windows legs for whether the note shows at 3000 and how long the journey takes, and if a leg draws no note, raise the count in the journey and in `writeChain`'s comment; put both figures in the report. Commit: one for the helpers, with their two journeys and the documentation; one for rows 14, 16 and 17; one for rows 18, 19 and 22; one for rows 20 and 21.

### A.5 Units and Types, rows 23 to 41

**Model:** sonnet, reviewed on sonnet. Each row is a state the two tabs already draw, reached with Task 1's helpers and the fixtures that exist; nothing in the page changes.

**Files:**
- Modify: `gui/e2e/project-units.spec.ts` (the Units rows and the two added), `gui/e2e/types.spec.ts` (the Types rows), and this plan's *The inventory*

**Interfaces:**
- Consumes, from Task 1 (`gui/e2e/demo.ts`):
  - `held(page: Page, path: string | RegExp | ((url: URL) => boolean)): Promise<() => void>`: holds the next matching request, once, until the function it answers is called. A string is a pathname matched exactly. Call the function in a `finally`.
  - `failing(page, path, how, times?, method?)`, `SERVER_FAILED`, and `REFUSED`, which is `` `The change was refused: ${SERVER_FAILED}` ``. Every Apply row here fails `"/api/edit"` with `"http"`, every time: the page's only request to that path is an Apply's `POST`, and no row presses an Apply twice.
  - `editJson(directory: string, file: string, change: (data: any) => void): void`, used as a `copiedGui` change.
- Consumes, as `demo.ts` stands: `driftIn(directory, file, variable, unit)`, `driftDatatypeIn(directory, file, variable, datatype)`, `CONTROLLER`, `PUMP`, `UNITS`. Fixtures: `gui`, `structuresGui`, `copiedGui`.
- Adds, local to `project-units.spec.ts` and used by no other task: `writeEmptyComponent(directory: string): string` (Step 3).

**What the pre-flight found:**
- **The count.** The rows are 23, 24, 26 to 32 and 34 to 41, which is 17; the two added rows make 19; three splits (29, 30 and 38) make 22 journeys, 11 in each file.
- **The examples these rows lean on.**
  - **examples/demo** has no units file and states five units, `%`, `Hz`, `V`, `degC` and `ms`: the Units tab reads `5 units · no units file` and offers "Adopt 5 units". `ms` is stated once, by CurveA in `components/controller.ddd.json`, so its panel reads `stated in 1 place, 1 file` and renaming it changes that one file.
  - **examples/vocabulary**'s `units.ddd.json` lists rpm, Nm, degC and kPa. `pump.ddd.json` states rpm (PumpSpeed), kPa (ManifoldPressure and PressureTrend) and, in its own scalar type `Torque_t` (`component.types`), Nm. Three units are in use; degC is listed and stated by nothing.
  - **examples/structures**'s `types.ddd.json` declares `Temperature_t` (scalar), `DriverStatus_t` (external) and the structures `Sample_t`, `Status_t`, `Sensor_t` and `SensorCal_t`: the Types tab reads `6 types · 1 scalar, 4 structures, 1 external`. Sensing produces `Inlet`, of `Sensor_t`; Monitoring reads it. `Temperature_t` is named by three members: `Sample_t.value`, `SensorCal_t.warnLimit` and `Sensor_t.history`.
- **How each kind of state is reached.**
  - **Loading** (23, 26, 31, 34): the request held by `held`, released in a `finally`.
  - **Failing** (24, 27, 32, 35): `failing(…, "http")`, registered before `goto` for a tab and once the row is drawn for a panel.
  - **An edge project** (28, 29, 29b, the unit listed twice, 40): `copiedGui`, its change made before the server starts.
  - **A banner** (36, 37): the types file written from the journey once the table is drawn, which the watcher sees.
  - **A follow** (38a, 38b, 39, 40): a press, then the address and the panel it leads to.
  - **An Apply the server fails on** (30a, 30b, 41): `failing(page, "/api/edit", "http")`.
- **Rows 25 and 33 are Task 2's,** and so is a panel whose units read fails (P19c-5): the type, variable and, once the table stays, unit panels read "Reading …" for ever when `/api/units` fails, and Task 2 gives them something to say. This task holds and fails `/api/unit` and `/api/type` alone.
- **Row 34's sentence has two causes.** `TypePanel` waits for `/api/type` and for `/api/units`, and says `Reading Temperature_t…` for either. The journey holds the type's own read, `/api/type`.
- **Row 29 is two states, and its negative half needs a record.**
  - **Two states:** `adoptionSentence` has two arms for a count of 0, a project with no units file (29) and a units file that lists none (29b).
  - **The record:** "no plan is asked" is `adoptionAsked`. A page that asks anyway is refused `409` and shows the refusal in the banner, but a few tens of milliseconds after it drew the sentence, so a sentence assertion passes or fails by which arrives first. Measured with the real journey against the ablated page, over ten runs: without the record it survived three and died seven; with it, it died ten, seven of them at the record.
  - **The barrier:** the journey records the page's asks of `/api/unit-plan` from the start and reads the record after the reader has left the tab.
- **Row 30 is two surfaces, and asserts less than it could.**
  - **Two surfaces:** the adoption (`UnitsPage`'s own mutation, shown in the banner: 30a) and a unit's panel, whose four actions (describe, add, remove, rename) share one handler (30b, by a rename).
  - **Less than it could (P19c-6):** each asserts the sentence and the file, and never whether the Apply stays after the refusal. The Units panel keeps its Apply and the Types panel withdraws its own (row 41); Tasks 4 and 5 change a stale refusal, and a non-stale refusal's differences are recorded, not ruled. The same holds for row 41.
- **Row 38 is two follows:** a use by a variable leads to that variable on its component's page (38a), and a use by a structure's member leads to that structure (38b).
- **Row 40 needs a vocabulary.**
  - **Why:** a project with no units file reports no `unknown-unit`, so the setup is `copiedGui("vocabulary")` with `Torque_t`'s unit made one the units file does not list. `driftIn` matches the first `"unit"` after `"name": "Torque_t"`, which is the type's own entry in `pump.ddd.json`, as it matches a variable's.
  - **Why this finding:** most findings inside a type's entry route to the type itself (`finding_routes.py`'s `WITHIN_TYPE`), so following one leads nowhere new. Only the unit and constant checks lead elsewhere.
- **Rows 36 and 37 empty the tab.** Every type of examples/structures is in the broken file, so both read `This project declares no types` and draw no table. They are the Types tab's twins of `shared.spec.ts`'s untold and unreadable banners.
- **Two rows the pre-flight found join this task (P19c-9):** a rename the plan refuses (`' x' has spaces around it`) and a unit listed twice (the `duplicate-unit` chip). Neither had a journey.
- **Recorded for the maintainer, not fixed (P19c-10).**
  - The Types tab names no component file that breaks its schema. In examples/vocabulary, break PumpSpeed's datatype in `pump.ddd.json` and the tab reads `This project declares no types` with no banner, since `TypesPage.tsx`'s `unreadable(state, ["types"])` asks for kind `types` only. Cut in half, the same file is named, as untold.
  - `TypePanelView.tsx` decides where a use leads (`routeOfUse`, with `whatOf` and a second `KIND_WORDS`) in a `.tsx`, with no Vitest. Rows 38 and 39 are pinned by journeys alone.
- **Decisions taken.**
  - **An empty component, not a stripped project, for rows 29 and 29b:** a component with an empty interface, included alone, states no unit in two writes. Removing every `unit` key from examples/structures would take a recursive rewrite of two files.
  - **`"bogus"` for row 37's datatype,** not a same-length spelling: the new text is not the length of the old, so that the watcher cannot miss the write. `driftDatatypeIn` is name-based, like `driftIn`, and reaches a type's `datatype`.
  - **Row 40 is drifted before the server starts,** so that the first revision already holds the finding, as `findings.spec.ts`'s page-of-findings journey drifts its copy.
  - **A listener, not a route, records row 29's asks:** it intercepts nothing, so it cannot leave a request hanging into the teardown (P19b-7).
- **No sentence of these rows carries a path.** Files are named by base name over the posix path the api sends. The one path in an address is row 38a's `file=`, posix and percent-encoded: match it as `[^&]*sensing\.ddd\.json&variable=Inlet$`.
- **Other tasks change the lines the ablations name.** Task 2 rewrites the blocks that draw rows 23, 24, 31 and 32, and Tasks 4 and 5 the stale branches of `UnitsPage.tsx`, `UnitPanel.tsx` and `TypePanel.tsx`. The ablations below are the lines at `2bc00da`: read the code as those tasks left it, and ablate the line that now does the same.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

Units, in `project-units.spec.ts`:

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **23. reading the project's units** | `gui` | Wait for the button "Controller". `const release = await held(page, "/api/units")`, press the link "Units". `UnitsPage`'s `<p className="quiet">Reading the project's units…</p>` shows alone, a paragraph with no role: no `grid`, no `.summary` line. In a `finally`, `release()`; then the row "ms" is drawn and the text is gone. | `UnitsPage.tsx`'s `return <p className="quiet">Reading the project's units…</p>;` made `return null;`. Dies at the text. |
| **24. the units failing to load** | `gui`; `failing(page, "/api/units", "http")` before `goto` | Press the link "Units". `UnitsPage`'s `if (units.isError) return <Banner tone="error">{units.error.message}</Banner>;` draws one `alert` reading `SERVER_FAILED`, alone: no `grid`, no `.summary` line. | That line removed: the tab reads "Reading the project's units…" for ever. Dies at the alert. |
| **26. a unit's panel reading the unit** | `gui`; the Units tab open, the row "ms" drawn | `const release = await held(page, "/api/unit")` (this path alone: the list is read already), then press the row "ms". `UnitPanel`'s `<p className="quiet">Reading {name}…</p>` shows in the `complementary` "ms": `Reading ms…`, and no combobox "Rename ms to". Released, `stated in 1 place, 1 file` shows and the text is gone. | `UnitPanel.tsx`'s `Reading {name}…` made `{name}`. Dies at the text. |
| **27. a unit's panel failing to read the unit** | `gui`; the Units tab open and the row drawn, then `failing(page, "/api/unit", "http")` | Press the row "ms". `UnitPanel`'s `if (answer.shown === "refusal") {` draws `<Banner tone="error">{answer.refusal}</Banner>` in the panel: one `alert` reading `SERVER_FAILED`, the heading "ms" and no combobox "Rename ms to". The table, with its row, stays beside it. | That `if` made `if (false) {`: the panel reads "Reading ms…". Dies at the alert. |
| **28. a units file listing no unit, the units in use adopted into it** | `copiedGui("vocabulary", …)`, its change `editJson(directory, UNITS, (data) => { data.units = []; })`. The project includes the file already. | Step 1. The banner's sentence is `adoptionSentence`'s arm for a project with a units file; the preview names one file; the project description is left as it was. | Page: `lib/projectUnits.ts`'s `"No unit this project states is in its vocabulary. Adopting lists the " +` made `"Adopting lists the " +`. Dies at the banner's sentence. Server, in the scratch copy: `src/ddd/lsp/units.py`'s `if planned.into is not None:` in `adopt_units` made `if False:`; the plan then creates the file and edits the includes. Dies at `Changes 1 file: units.ddd.json`. |
| **29. a project stating no unit, with nothing to adopt** | `copiedGui("demo", …)`: `writeEmptyComponent`, then `editJson(directory, "demo.ddd.json", …)` with `data.project.includes = [empty]`. Before `goto`, `page.on("request", …)` records the page's asks of `/api/unit-plan` | Press "Units". The line reads `0 units · no units file`; the banner (`status`) reads `This project has no units file, so no unit is checked against a vocabulary. It states no unit, so there is nothing to adopt.`; it holds no button; the grid has no `rowheader`. Then press the link "Table", wait for the grid "Components", and see the record empty: a page that asked for a plan asked as the tab opened. | `lib/projectUnits.ts`'s ``if (adoptable === 0) return `${opening} It states no unit, so there is nothing to adopt.`;`` made `if (false) …`. Dies at the sentence. And `adoptionAsked`'s `return units.adoptable !== null && units.adoptable > 0;` made `return units.adoptable !== null;`. Dies at the sentence if the refusal reaches the page before the sentence is checked, and at the record if not; without the record it can survive. |
| **29b. a units file listing none, in a project stating no unit** (a split of 29) | `copiedGui("vocabulary", …)`: `writeEmptyComponent`, the units file emptied, and `project.ddd.json`'s `data.project.includes = [UNITS, empty]` | The line reads `0 units · all in the vocabulary`; the banner reads `This project states no unit, so there is nothing to adopt.`; it holds no button. | `lib/projectUnits.ts`'s `if (adoptable === 0) return "This project states no unit, so there is nothing to adopt.";` made `if (false) …`. Dies at the sentence. |
| **30a. an Apply the server fails on: the adoption** (a split of 30) | `gui`; the Units tab open and the banner offering "Adopt 5 units"; `failing(page, "/api/edit", "http")` | Press "Adopt 5 units" in the banner. `AdoptBannerView`'s `{refusal !== null && <p className="adopt-refusal">{refusal}</p>}` shows `REFUSED` in the banner. `units.ddd.json` does not exist and `demo.ddd.json` is byte-identical to before. | `UnitsPage.tsx`'s `setRefused(refusalOf(error));` made `setRefused(null);`. Dies at the sentence. |
| **30b. an Apply the server fails on: a unit's panel** (a split of 30) | `gui`; the row "ms" open; in the region "Rename", `msec` filled and Enter pressed, so that "Apply to 1 file" is drawn; `failing(page, "/api/edit", "http")` | Press "Apply to 1 file". The region's `status` (`UnitPanelView`'s `<p className="panel-refusal" role="status">{refusal}</p>`) reads `REFUSED`, and `controller.ddd.json` is byte-identical to before. | `UnitPanel.tsx`'s `setFailed({ action, message: refusalOf(error) });` made `setFailed(null);`. Dies at the `status`. (The prefix `The change was refused: ` in `refusalOf` would kill both 30a and 30b.) |
| **a rename the plan refuses** (added, P19c-9) | `gui`; the row "ms" open | Fill the combobox "Rename ms to" with a space and `x`, press Enter. The region "Rename"'s `status` reads `' x' has spaces around it`, the server's refusal of the plan (`ddd.lsp.units._spelling`), and no button named "Apply to …" is drawn. `controller.ddd.json` is byte-identical. | `UnitPanel.tsx`'s `offer`: `: shown.refusal,` made `: null,`. Dies at the sentence; the Apply rows' sentences come from `failed`, so they survive. |
| **a unit listed twice** (added, P19c-9) | `copiedGui("vocabulary", …)`, its change `editJson(directory, UNITS, (data) => { data.units.push({ unit: "rpm", description: "listed a second time" }); })` | The line reads `4 units · all in the vocabulary`. The first `rowheader` is "rpm", for a unit with a finding comes first; its row draws the chip `duplicate-unit`, the only chip on the page. Press the row: the panel's one list item reads `duplicate-unit unit 'rpm' is already declared`. | `lib/projectUnits.ts`'s `findingCheck`: `"duplicate-unit"` made `"duplicate"`. Dies at the chip. |

Types, in `types.spec.ts` (`structuresGui` unless said):

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **31. reading the project's types** | `structuresGui` | Wait for the link "Types". `const release = await held(page, "/api/types")`, press the link. `TypesPage`'s `<p className="quiet">Reading the project's types…</p>` shows alone: no `grid`, no `.summary` line. Released, the row "Temperature_t" shows and the text is gone. | `TypesPage.tsx`'s `return <p className="quiet">Reading the project's types…</p>;` made `return null;`. Dies at the text. |
| **32. the types failing to load** | `structuresGui`; `failing(page, "/api/types", "http")` before `goto` | Press the link "Types". `TypesPage`'s `if (types.isError) return <Banner tone="error">{types.error.message}</Banner>;` draws one `alert` reading `SERVER_FAILED`, alone: no `grid`, no `.summary` line. | That line removed: the tab reads "Reading the project's types…" for ever. Dies at the alert. |
| **34. a type's panel reading the type** | `structuresGui`; the Types tab open and the row "Temperature_t" drawn | `const release = await held(page, "/api/type")`, press the row. `TypePanel`'s `<p className="quiet">Reading {name}…</p>` shows in the `complementary` "Temperature_t": `Reading Temperature_t…`, and no textbox "Rename Temperature_t to". Released, the textbox shows and the text is gone. | `TypePanel.tsx`'s `Reading {name}…` made `{name}`. Dies at the text. |
| **35. a type's panel failing to read the type** | `structuresGui`; the Types tab open and the row drawn, then `failing(page, "/api/type", "http")` | Press the row "Temperature_t". `TypePanel`'s `if (answer.shown === "refusal") {` draws `<Banner tone="error">{answer.refusal}</Banner>` in the panel: one `alert` reading `SERVER_FAILED`, the heading, and no Rename textbox. The table stays. | That `if` made `if (false) {`: the panel reads "Reading Temperature_t…". Dies at the alert. |
| **36. the untold banner** | `structuresGui`; the Types tab open and `6 types · 1 scalar, 4 structures, 1 external` shown | Cut `types.ddd.json` in half (`writeFileSync(path, whole.subarray(0, Math.floor(whole.length / 2)))`): it no longer parses, so it has no kind. The `status` that has "did not load" reads `types.ddd.json did not load, so whatever is declared there is not listed.`; the line reads `This project declares no types`; the row "Temperature_t" is gone. | `TypesTableView.tsx`'s `{untold.length > 0 && (` made `{false && (`. Dies at the sentence. |
| **37. the unreadable banner** | the same | `driftDatatypeIn(structuresGui.directory, TYPES, "Temperature_t", "bogus")`: still json, and plainly a types file, but it fails its model, so it keeps its kind and does not load. The `status` reads `types.ddd.json did not load, so the types declared there are not listed.`; the line reads `This project declares no types`; the row is gone. | `TypesPage.tsx`'s `unreadable(state, ["types"])` made `unreadable(state, [])`. Dies at the sentence. |
| **38a. a type's "Where it is used" followed to the declaration: a variable** (a split of 38) | `structuresGui` | Open the row "Sensor_t". Its uses are the rows `Inlet sensing.ddd.json Sensing · produces` and `Inlet monitoring.ddd.json Monitoring · reads`. Press the button "Inlet" in the first: the address matches `/\/component\?file=[^&]*sensing\.ddd\.json&variable=Inlet$/`, and the heading "Sensing" (level 1) and the `complementary` "Inlet" show. `page.goBack()`, and the second row leads the same way to `monitoring.ddd.json` and "Monitoring". | `TypePanelView.tsx`'s `routeOfUse`: `return { page: "component", file: use.path, variable: use.name };` made `return { page: "component", file: use.path };`. Dies at the address. |
| **38b. … a structure's member** (a split of 38) | `structuresGui` | Open the row "Temperature_t". Its uses are `Sample_t.value types.ddd.json member`, `SensorCal_t.warnLimit …` and `Sensor_t.history …`. Press the button "Sample_t.value": the address matches `/\/project\?view=types&type=Sample_t$/`, the `complementary` "Sample_t" shows, and "Temperature_t" is gone. | `routeOfUse`'s `type: dot === -1 ? use.name : use.name.slice(0, dot)` made `type: use.name`: the panel "Sample_t.value" closes, saying it is no longer declared. Dies at the address. |
| **39. a structure's member followed to its type** | `structuresGui` | Open the row "Sample_t". In its Members table the row "value" holds the button "Temperature_t", and the row "timestamp" holds no button (its type is the datatype `uint32`). Press the button: the address matches `/\/project\?view=types&type=Temperature_t$/`, the `complementary` "Temperature_t" shows, and "Sample_t" is gone. | `TypePanelView.tsx`'s `props.onOpen({ page: "project", view: "types", type: typename })` made `… type: type.name })`. Dies at the address. |
| **40. a finding in a type's panel followed** | `copiedGui("vocabulary", …)`, its change `driftIn(directory, PUMP, "Torque_t", "furlong")` | Press the one row of the Types tab, "Torque_t". The panel's one list item shows the chip `unknown-unit` and the button `'furlong' is not a unit this project declares`. Press it: the address matches `/\/project\?view=units&unit=furlong$/`, the `complementary` "furlong" shows, and "Torque_t" is gone. | `TypePanelView.tsx`'s `<Button variant="link" onPress={() => props.onOpen(route)}>` made `onPress={() => undefined}`. Dies at the address. |
| **41. an Apply the server fails on** | `structuresGui`; Temperature_t open; the textbox "Description" (region "Description") filled with a new sentence, so that "Apply to 1 file" is drawn; `failing(page, "/api/edit", "http")` | Press "Apply to 1 file". The panel's `status` (`TypePanelView`'s `<p className="panel-refusal" role="status">{refusal}</p>`) reads `REFUSED`, and `types.ddd.json`'s entry for Temperature_t is as it was (`entryOf`). | `TypePanel.tsx`'s `setRefused({ kind, message: refusalOf(error) });` made `setRefused(null);`. Dies at the `status`. |

- [ ] **Step 1: The worked journey,** row 28, in `gui/e2e/project-units.spec.ts`, appended after its last journey. It shows an edge project (`copiedGui` and `editJson`), a banner asserted as its whole sentence, a preview read before it is applied, and a write proved by the files on disk. The file's `./demo` import gains `CONTROLLER`, `editJson`, `failing`, `held`, `REFUSED` and `SERVER_FAILED`, which the rows below use, in Biome's order; merge it with what Tasks 1 to 5 left there:

```ts
import {
  CONTROLLER,
  driftIn,
  editJson,
  failing,
  held,
  PUMP,
  REFUSED,
  SERVER_FAILED,
  UNITS,
} from "./demo";

test("a units file that lists no unit is filled with the units in use, and the project is left as it was", async ({
  page,
  copiedGui,
}) => {
  // examples/vocabulary with its units file emptied before the server starts. The project includes
  // the file already, so adopting fills it: nothing is created and no include is added.
  const gui = await copiedGui("vocabulary", (directory) => {
    editJson(directory, UNITS, (data) => {
      data.units = [];
    });
  });
  const units = join(gui.directory, UNITS);
  const project = join(gui.directory, "project.ddd.json");
  const projectBefore = readFileSync(project);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  // A project with a units file is opted in to the check, so each unit it states is outside it.
  await expect(page.getByText("3 units · 3 not in the vocabulary", { exact: true })).toBeVisible();
  await expect(page.locator(".chip").filter({ hasText: "unknown-unit" })).toHaveCount(3);

  // The sentence for a units file that lists nothing, not the one for a project with no file.
  const banner = page.getByRole("status").filter({ hasText: "No unit this project states" });
  await expect(banner.locator("p").first()).toHaveText(
    "No unit this project states is in its vocabulary. Adopting lists the 3 units in use in a units file: nothing is reported that is not reported today.",
  );
  await banner.getByRole("button", { name: "Show changes" }).click();
  const preview = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  await expect(preview.getByText("Changes 1 file: units.ddd.json", { exact: true })).toBeVisible();
  await expect(preview.locator(".hunk .removed")).toHaveText(['-   "units": []']);
  await expect(preview.locator(".hunk .added")).toHaveText([
    '+   "units": [',
    '+     { "unit": "Nm", "description": "" },',
    '+     { "unit": "kPa", "description": "" },',
    '+     { "unit": "rpm", "description": "" }',
    "+   ]",
  ]);
  await preview.getByRole("button", { name: "Adopt 3 units" }).click();

  // The units in use, in code point order, each with an empty description; nothing else written.
  await expect
    .poll(() => (JSON.parse(readFileSync(units, "utf8")) as { units: unknown[] }).units)
    .toEqual(["Nm", "kPa", "rpm"].map((unit) => ({ unit, description: "" })));
  expect(readFileSync(project).equals(projectBefore)).toBe(true);
  await expect(page.getByText("3 units · all in the vocabulary", { exact: true })).toBeVisible();
  await expect(banner).toHaveCount(0);
  await expect(preview).toHaveCount(0);
  await expect(page.locator(".chip").filter({ hasText: "unknown-unit" })).toHaveCount(0);
});
```

  The hunk's lines are measured on the file `editJson` writes (two-space indent, `"units": []` on its third line): the engine lays the three entries out one to a line, so the hunk is `units.ddd.json, line 3` and its removed line begins with three spaces after the sign. A units file written as `{"units": []}` on one line would make a one-line hunk instead. Read the hunk and the sentence off the running page before asserting them.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then two ablations, each in the scratch copy of the package. `lib/projectUnits.ts`'s opening string `"No unit this project states is in its vocabulary. Adopting lists the " +` made `"Adopting lists the " +`: it must die at the banner's `toHaveText`. And the copy's `src/ddd/lsp/units.py`, `if planned.into is not None:` in `adopt_units` made `if False:`: the plan then creates `units.ddd.json` and edits the includes, and it must die at `Changes 1 file: units.ddd.json`.
- [ ] **Step 3: The other rows,** each a journey of its own, titled as a sentence as the file's others are, and appended to the file of its tab: the Units rows to `project-units.spec.ts`, the Types rows to `types.spec.ts`. Each is run with `--repeat-each=10` and ablated as its row says. The Types file's `./demo` import gains `driftDatatypeIn`, `driftIn`, `failing`, `held`, `PUMP`, `REFUSED` and `SERVER_FAILED`; merged with what the earlier tasks left, it reads:

```ts
import {
  driftDatatypeIn,
  driftIn,
  driftMaxUnseen,
  failing,
  held,
  PUMP,
  REFUSED,
  SERVER_FAILED,
} from "./demo";
```

  Three patterns the table cannot show in words:

  **The loading and failing pair** (rows 26 and 27). Rows 23, 31 and 34 repeat the first, and 24, 32 and 35 the second. `held` and `failing` take the path alone, so `"/api/unit"` is not `/api/units`. A loading journey releases in a `finally`: a failed assertion would otherwise leave the request held into the test's teardown (P19b-7).

```ts
test("a unit's panel says it is reading the unit until the answer comes", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  const row = page.getByRole("row", { name: "ms", exact: true });
  await expect(row).toBeVisible();
  // `/api/unit` alone: the list is read already, and `/api/units` is another path.
  const release = await held(page, "/api/unit");
  const panel = page.getByRole("complementary", { name: "ms" });
  try {
    await row.click();
    await expect(panel.getByText("Reading ms…", { exact: true })).toBeVisible();
    await expect(panel.getByRole("combobox", { name: "Rename ms to" })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(panel.getByText("stated in 1 place, 1 file", { exact: true })).toBeVisible();
  await expect(panel.getByText("Reading ms…")).toHaveCount(0);
});

test("a unit's panel whose read fails shows the server's own error", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  const row = page.getByRole("row", { name: "ms", exact: true });
  await expect(row).toBeVisible();
  await failing(page, "/api/unit", "http");
  await row.click();

  const panel = page.getByRole("complementary", { name: "ms" });
  await expect(panel.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(panel.getByRole("heading", { name: "ms" })).toBeVisible();
  await expect(panel.getByRole("combobox", { name: "Rename ms to" })).toHaveCount(0);
  // The table stays beside it.
  await expect(row).toBeVisible();
});
```

  **The empty project and the record** (row 29). The local helper, then the journey. The listener is registered before `goto` and read only after the reader has left the tab, which is what makes an absent request certain.

```ts
/** A component with no variable at all, written beside the copy's project description: a project
 * that includes only it states no unit. Answers the file's name, as an `includes` entry spells it. */
function writeEmptyComponent(directory: string): string {
  const file = "empty.ddd.json";
  const empty = { component: { name: "Empty", interface: [] } };
  writeFileSync(join(directory, file), `${JSON.stringify(empty, null, 2)}\n`, "utf8");
  return file;
}

test("a project stating no unit says there is nothing to adopt, and asks for no plan", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => {
    const empty = writeEmptyComponent(directory);
    editJson(directory, "demo.ddd.json", (data) => {
      data.project.includes = [empty];
    });
  });
  // Every ask for a plan, recorded from the start: the page must make none.
  const asked: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/unit-plan") asked.push(request.url());
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();

  await expect(page.getByText("0 units · no units file", { exact: true })).toBeVisible();
  const banner = page.getByRole("status").filter({ hasText: "nothing to adopt" });
  await expect(banner).toHaveText(
    "This project has no units file, so no unit is checked against a vocabulary. It states no unit, so there is nothing to adopt.",
  );
  await expect(banner.getByRole("button")).toHaveCount(0);
  await expect(page.getByRole("rowheader")).toHaveCount(0);

  // A plan the page asked for would be asked for as the tab opened, and refused a few tens of
  // milliseconds later - after the assertions above had passed. The reader leaves the tab, and
  // whatever it asked for on its way in has been asked by then.
  await page.getByRole("link", { name: "Table", exact: true }).click();
  await expect(page.getByRole("grid", { name: "Components" })).toBeVisible();
  expect(asked).toEqual([]);
});
```

  **The empty project with a units file** (row 29b), the change its journey makes:

```ts
const gui = await copiedGui("vocabulary", (directory) => {
  const empty = writeEmptyComponent(directory);
  editJson(directory, UNITS, (data) => {
    data.units = [];
  });
  editJson(directory, "project.ddd.json", (data) => {
    data.project.includes = [UNITS, empty];
  });
});
```

- [ ] **Step 4: Bugs.** This task fixes none. The two it could have met are recorded (P19c-10): the Types tab names no component file that breaks its schema, and `TypePanelView.tsx` decides where a use leads, in a `.tsx`. A panel whose units read fails is Task 2's (P19c-5). Any other bug a journey finds follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Each row names its journey by file, line and title: the seven Units rows (29 and 30 each by two journeys) and the ten Types rows (38 by two). Add the two rows under Units, owner 10: *a rename the plan refuses* and *a unit listed twice (the `duplicate-unit` chip)*. Rows 25 and 33 read Task 2.
- [ ] **Step 6: The gates,** every journey included. Commit: one commit for the Units rows, the two added with them, and one for the Types rows. No CHANGELOG entry: nothing a reader would notice changes.

### A.6 Shared files and Findings, rows 42 to 51

**Model:** sonnet, reviewed on sonnet. Each row is a state the two screens already draw, reached with Task 1's helpers, and the one fix is a handler that clears a refusal.

**Files:**
- Modify: `gui/e2e/shared.spec.ts`, `gui/e2e/findings.spec.ts`, and this plan's *The inventory*
- Modify, for the bug the retry journey finds (Step 4): `gui/src/screens/FindingsPage.tsx` and `CHANGELOG.md`

**Interfaces:**
- Consumes, from Task 1, in `gui/e2e/demo.ts`:
  - `held(page: Page, path: string | RegExp | ((url: URL) => boolean)): Promise<() => void>`: holds the next request that matches, once only, until the function it answers is called, then lets it through unchanged. A string is a pathname matched exactly. Call the function in a `finally`.
  - `REFUSED`: `` `The change was refused: ${SERVER_FAILED}` ``, the sentence a panel shows when `failing(page, path, "http")` has failed its Apply.
- Consumes, as they stand: the fixtures `gui`, `vocabularyGui` and `copiedGui` (`gui/e2e/fixtures.ts`); `failing(page, path, how, times?)`, which answers how many requests it has failed, and `drift`, `unstamp`, `CONTROLLER` and `SERVER_FAILED` (`gui/e2e/demo.ts`); in `shared.spec.ts`, `FILES`, `entriesOf`, `entryOf`, `openEntry` and `openForm`; in `findings.spec.ts`, `valueH`.

**What the pre-flight found:**
- **Rows 44 and 48 are other tasks'.** Row 44, the table kept under the error, is Task 2's, and row 48, the add form's Apply out of date, is Task 5's. This task leaves both alone, and adds its journeys at the end of `shared.spec.ts`.
- **Each row is reached by one request, held or failed.** The loading rows (42, 45, 50) hold the one read with `held`, registered after `goto` and before the press that asks, and release it in a `finally`. The failing rows (43, 46, 49, 51) register `failing(page, path, "http")` before the request they fail is sent. An HTTP answer is never sent again, so `failed()` counts the one ask.
- **Rows 45 and 46 are three states each,** since the constant's, the section's and the raster's panels are three copies of one shape (`ConstantPanel.tsx`, `SectionPanel.tsx` and `RasterPanel.tsx`), each with its own reading sentence and its own refusal branch. Each row is a loop over the table `PANELS`, one test a kind, so that one copy's ablation kills one test.
- **Row 46's constant case is read by an older journey too.** "a constant whose file does not load keeps its panel, naming the file, until the file loads again" draws the same refusal branch, for a file that did not load, so the constant's ablation kills both. No other journey draws the section's or the raster's.
- **Row 47 needs a contrast.** Only examples/vocabulary has both homes of a constant: `TREND_SAMPLES` in constants.ddd.json, named by plain text, and `PRESSURE_CELLS` in pump.ddd.json's own constants, named by a button that leads to that component's page. The journey asserts both.
- **Row 49 is four mutations:** the add form's, and the constant's, the section's and the raster's own. 49a is the add form, and 49b to 49d are one loop over `SAVES`. They assert the refusal's sentence and the file on disk, never whether the Apply stays (P19c-6): Task 5 changes that for a stale refusal, and what the panels do after any other is recorded for the maintainer, not ruled.
- **Row 50 asserts the placeholders, and not that they cannot be pressed.** A placeholder pressed opens nothing, but `pendingKeys` (`lib/findingsWindow.ts`) made `return []` kills no journey, because `onSelect` already turns a placeholder into `undefined`. It would matter only with a panel open and a page unread, which takes a scrolled box and one page held. The row does not claim it.
- **Row 51 has a bug, the contained one of this task (P19c-10).** After the server fails on a fix's Apply, the panel says so and draws no "Show changes" and no Apply, whichever fix is chosen next, until the finding is pressed again. `FindingsPage.tsx` says its `refused` is "cleared whenever the reader chooses again", but `onChoose` is `setChosen` alone: only `select` and the next Apply, which cannot be pressed, clear it. Step 4 fixes it, red first, with a handler that also clears the refusal. Its retry journey is not row 51's: it asserts the Apply only after the reader chose again, which is what the fix is, and still nothing of the Apply straight after the refusal (P19c-6). A refusal because a file changed on disk is held in `stale`, not `refused`, and is left as it is. Tasks 4 and 5 may edit this file's stale handling: if `setRefused` has gone by then, the handler clears whatever holds the refusal that is not stale.
- **The fix has no Vitest case.** It is the two state setters `select` beside it already calls, in a handler of their own, with no judgement in it (which refusal is shown stays `shownRefusal`'s, in `lib/refusals.ts`), and Vitest covers `src/api`, `src/lib` and `src/state` alone. The journey is its test.
- **As drafted,** every journey below ran green ten times over against the page as it stands (the retry journey with the change), and died under its ablation. The retry journey is red before the change.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **reading the project's shared files** | `vocabularyGui`. After `goto`, and before the tab is pressed, `held(page, "/api/shared")`. | `SharedPage.tsx`, while the list has no data and has not failed, returns `<p className="quiet">Reading the project's shared files…</p>` and nothing else. Pressing the link "Shared files" shows that sentence, with no grid "Shared files" and no button "Declare an entry". Released, the line "2 constants · 3 rasters · 2 sections" is drawn and the sentence is gone. | That sentence made `Reading…`: dies at the sentence's `toBeVisible`. |
| **the shared files failing to load** | `vocabularyGui`. `failing(page, "/api/shared", "http")` before `goto`. | The same branch, with a failure: `if (shared.isError) return <Banner tone="error">{shared.error.message}</Banner>;` draws the server's message alone. The tab shows one `alert` reading `SERVER_FAILED`, and none of the line "2 constants · 3 rasters · 2 sections", no grid and no button "Declare an entry". `failed()` is 1. | That `if (shared.isError) return …` line removed: the reading sentence stays, and it dies at the alert. Task 2 edits this branch, so find the line by its content. |
| **an entry's panel reading the entry** (a loop over the three vocabularies) | `vocabularyGui`. Once the entry's row is drawn, `held(page, path)` for the kind's own read: `/api/constant`, `/api/section` or `/api/raster`. The row is pressed after that. | Each panel returns `<Panel title={name} onClose={onClose}><p className="quiet">Reading {name}…</p></Panel>` while its read has no answer. The complementary named for the entry holds "Reading TREND_SAMPLES…" (".calib", "100ms") and none of its regions ("Value", "Access", "Event"), and the address names the kind and the entry. Released, the region is drawn and the sentence is gone. | Each panel's sentence made `Loading {name}`: kills that kind's test, and no other, at the sentence's `toBeVisible`. |
| **an entry's panel failing to read the entry** (a loop over the three vocabularies) | `vocabularyGui`. `failing(page, path, "http")` before `goto`, for the same three paths. | Each panel's `if (answer.shown === "refusal")` branch returns `<Panel title={name} onClose={onClose}><Banner tone="error">{answer.refusal}</Banner></Panel>`. Pressing the row leaves, in the complementary named for the entry, one `alert` reading `SERVER_FAILED` and no region. The table stays with the row `aria-selected="true"`, and the button "Close TREND_SAMPLES" (".calib", "100ms") closes the panel. | Each branch's condition made `false`: that kind's test, and no other, dies at the alert. The constant's also kills the older journey named above, which reads the same branch. |
| **a constant declared inside a component, its file followed** | `vocabularyGui`. | `ConstantPanelView.tsx` draws "Declared in" and, where `reply.pointer.startsWith("component.")`, the file as a button styled as a link. `TREND_SAMPLES` shows "Declared in constants.ddd.json" and no button, since a constants file is no component. `PRESSURE_CELLS` shows "Declared in pump.ddd.json" and a button "pump.ddd.json", which leads to Pump's page: the address `/component?file=…pump.ddd.json`, the heading "Pump", the row "PumpSpeed", no panel and no "no longer declared". | `const declaredInComponent = reply.pointer.startsWith("component.");` made `false`: dies at the press of the button "pump.ddd.json", which is not drawn. Or the button's `file: reply.file` made `file: reply.pointer`: dies at the address. |
| **an Apply the server fails on** (49a, the add form) | `vocabularyGui`. `openForm(page, vocabularyGui, "constant", "SPARE")`, Value `4`, "Changes 1 file: constants.ddd.json" visible, then `failing(page, "/api/edit", "http")`. | `SharedAdd`'s mutation has `onError: (error) => setRefusal(refusalOf(error))`, which `SharedAddView.tsx` draws as `<p className="panel-refusal" role="status">`. Pressing "Apply to 1 file" shows `REFUSED` in the form's status. `failed()` is 1, and constants.ddd.json still declares only `TREND_SAMPLES`. Nothing is asserted of the Apply (P19c-6). | `SharedAdd`'s `onError: (error) => setRefusal(refusalOf(error))` made `onError: () => undefined`: dies at the form's status. Task 5's journey for row 48 reads the same handler, and the pre-flight's draft of it died here too. |
| **an Apply the server fails on** (49b to 49d: a constant's, a section's and a raster's panel; a loop over `SAVES`) | `vocabularyGui`. `openEntry` for the entry, the region's field filled ("Value" `32`, "Alignment" `8`, "Event" `5`), "Changes 1 file:" and the vocabulary's file (`constants.ddd.json`, `sections.ddd.json`, `rasters.ddd.json`) visible, then `failing(page, "/api/edit", "http")`. | In each panel the apply mutation's `onError`, in its `else` arm, sets `{ action, message: refusalOf(error) }`, which the panel's view draws as a `role="status"` in the region of the field saved. Pressing "Save" shows `REFUSED` in the region. `failed()` is 1, and the entry on disk is as it was. | Each panel's `setFailed({ action, message: refusalOf(error) })` made `setFailed(null)`: kills that kind's test, and no other, at the region's status. |
| **a page of findings still being read** | `copiedGui("demo", (directory) => { drift(directory); })`, so that the first revision already holds two `definition-mismatch` findings. After `goto`, and before the tab is pressed, `held(page, "/api/findings")`. | `FindingsTableView.tsx` draws a row whose page has not arrived as `<Cell className={also("quiet")}>Reading…</Cell>` between two empty cells. The line "2 findings · 2 errors", counted by the state, is visible; two gridcells are named "Reading…" and no row is named `definition-mismatch`. Released, the two rows come and the placeholders go. | That `Reading…` emptied: dies at the two gridcells named "Reading…". |
| **a fix's Apply the server fails on** | `gui`. `unstamp(gui.directory, CONTROLLER, "ValueH")`, then `failing(page, "/api/edit", "http")` before `goto`. | `FindingsPage.tsx`'s apply mutation, in its `else` arm, sets `` `The change was refused: ${error.message}` ``, which `FindingPanelView.tsx` draws as `<p className="panel-refusal" role="status">`. Choosing "Give 'ValueH' an id" and pressing "Apply to 1 file" shows `REFUSED` in the panel `missing-id`. `failed()` is 1, ValueH still has no `id`, and the row `missing-id` is still listed. Nothing is asserted of the Apply (P19c-6). | The ``setRefused(`The change was refused: ${error.message}`)`` of that `else` arm made `setRefused(null)`: dies at the panel's status. The retry journey of Step 4 dies with it. |

- [ ] **Step 1: The worked journey,** the loop of row 45, in `gui/e2e/shared.spec.ts`. Extend its `./demo` import to `import { failing, held, PUMP, REFUSED, SERVER_FAILED, writeUnseen } from "./demo";` (Biome orders the names; the later steps use the others), then add at the end of the file, after Task 2's and Task 5's journeys:

```ts
/** The three vocabularies' panels: the entry a journey opens, the path its panel reads that entry
 * from, and the region the panel draws once it has. */
const PANELS = [
  { kind: "constant", name: "TREND_SAMPLES", path: "/api/constant", region: "Value" },
  { kind: "section", name: ".calib", path: "/api/section", region: "Access" },
  { kind: "raster", name: "100ms", path: "/api/raster", region: "Event" },
] as const;

for (const { kind, name, path, region } of PANELS) {
  test(`a ${kind}'s panel says it is reading ${name} until the entry answers`, async ({
    page,
    vocabularyGui,
  }) => {
    await page.goto(vocabularyGui.address);
    await page.getByRole("link", { name: "Shared files", exact: true }).click();
    const row = page.getByRole("row", { name, exact: true });
    await expect(row).toBeVisible();
    const release = await held(page, path);
    try {
      await row.click();
      const panel = page.getByRole("complementary", { name });
      await expect(panel.getByText(`Reading ${name}…`, { exact: true })).toBeVisible();
      // The panel is drawn and named, and has none of its regions yet.
      await expect(panel.getByRole("region", { name: region })).toHaveCount(0);
      await expect(page).toHaveURL(
        (url) => url.searchParams.get("kind") === kind && url.searchParams.get("name") === name,
      );
    } finally {
      release();
    }
    await expect(
      page.getByRole("complementary", { name }).getByRole("region", { name: region }),
    ).toBeVisible();
    await expect(page.getByText(`Reading ${name}…`)).toHaveCount(0);
  });
}
```

  Read each panel's accessible name, its reading sentence and the name of its first region off the running page before asserting them: a constant's panel draws the regions "Value", "Description", "Rename" and "Remove from the constants", a section's draws "Access" first, and a raster's "Event". A section's name has a dot, so the address is read through its search parameters rather than matched by a pattern. If an earlier task has added a `PANELS` or a `SAVES` to this file, rename these.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`: three tests, 30 passed. Then the ablation, in a scratch copy of the package: `ConstantPanel.tsx`'s `<p className="quiet">Reading {name}…</p>` made `Loading {name}`. It must kill the constant's test, and only that one, at the sentence's `toBeVisible`. The section's line (`SectionPanel.tsx`) and the raster's (`RasterPanel.tsx`) kill theirs alone.
- [ ] **Step 3: The other rows,** each a journey of its own, in the order of the rows. Rows 42, 43, 46, 47 and 49 go in `shared.spec.ts`, after the loop of Step 1:

```ts
test("the Shared files tab says it is reading the shared files until the list answers", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  const tab = page.getByRole("link", { name: "Shared files", exact: true });
  await expect(tab).toBeVisible();
  const release = await held(page, "/api/shared");
  try {
    await tab.click();
    await expect(
      page.getByText("Reading the project's shared files…", { exact: true }),
    ).toBeVisible();
    // Nothing else of the tab is drawn: not the table, and not the way to declare an entry.
    await expect(page.getByRole("grid", { name: "Shared files" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Declare an entry" })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(
    page.getByText("2 constants · 3 rasters · 2 sections", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Reading the project's shared files…")).toHaveCount(0);
});

test("the shared files failing to load leave the server's own error, with no table and no way to declare an entry", async ({
  page,
  vocabularyGui,
}) => {
  const failed = await failing(page, "/api/shared", "http");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();

  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  const summary = page.getByText("2 constants · 3 rasters · 2 sections", { exact: true });
  await expect(summary).toHaveCount(0);
  await expect(page.getByRole("grid")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Declare an entry" })).toHaveCount(0);
  // An HTTP answer is never sent again, so the one ask is the one failed.
  expect(failed()).toBe(1);
});

for (const { kind, name, path } of PANELS) {
  test(`a ${kind}'s panel whose entry fails to read says so, and the table stays`, async ({
    page,
    vocabularyGui,
  }) => {
    await failing(page, path, "http");
    await page.goto(vocabularyGui.address);
    await page.getByRole("link", { name: "Shared files", exact: true }).click();
    const row = page.getByRole("row", { name, exact: true });
    await row.click();

    const panel = page.getByRole("complementary", { name });
    await expect(panel.getByRole("alert")).toHaveText(SERVER_FAILED);
    await expect(panel.getByRole("region")).toHaveCount(0);
    await expect(row).toHaveAttribute("aria-selected", "true");
    await panel.getByRole("button", { name: `Close ${name}` }).click();
    await expect(panel).toHaveCount(0);
  });
}

test("a constant declared inside a component leads, from its panel, to that component's page", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();

  // One in a constants file names that file as text alone: it is no component, with no page.
  await page.getByRole("row", { name: "TREND_SAMPLES", exact: true }).click();
  const filed = page.getByRole("complementary", { name: "TREND_SAMPLES" });
  await expect(filed.getByText("Declared in constants.ddd.json")).toBeVisible();
  await expect(filed.getByRole("button", { name: "constants.ddd.json" })).toHaveCount(0);

  // One in a component's own constants names the component's file, and that file is a link.
  await page.getByRole("row", { name: "PRESSURE_CELLS", exact: true }).click();
  const inline = page.getByRole("complementary", { name: "PRESSURE_CELLS" });
  await expect(inline.getByText("Declared in pump.ddd.json")).toBeVisible();
  await inline.getByRole("button", { name: "pump.ddd.json" }).click();

  await expect(page).toHaveURL(/\/component\?file=[^&]*pump\.ddd\.json$/);
  await expect(page.getByRole("heading", { name: "Pump", level: 1 })).toBeVisible();
  await expect(page.getByRole("row", { name: "PumpSpeed", exact: true })).toBeVisible();
  await expect(page.getByRole("complementary")).toHaveCount(0);
  await expect(page.getByText("no longer declared")).toHaveCount(0);
});

test("a declaration the server fails on shows its refusal in the add form, and writes nothing", async ({
  page,
  vocabularyGui,
}) => {
  const form = await openForm(page, vocabularyGui, "constant", "SPARE");
  await form.getByRole("textbox", { name: "Value" }).fill("4");
  await expect(form.getByText("Changes 1 file: constants.ddd.json")).toBeVisible();

  const failed = await failing(page, "/api/edit", "http");
  await form.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(form.getByRole("status")).toHaveText(REFUSED);
  expect(failed()).toBe(1);
  expect(entriesOf(vocabularyGui.directory, "constants").map((entry) => entry.name)).toEqual([
    "TREND_SAMPLES",
  ]);
});

/** One save from each vocabulary's panel: the field's region, what is typed, and the key of the
 * entry that save would write. */
const SAVES = [
  { vocabulary: "constants", name: "TREND_SAMPLES", region: "Value", text: "32" },
  { vocabulary: "sections", name: ".calib", region: "Alignment", text: "8" },
  { vocabulary: "rasters", name: "100ms", region: "Event", text: "5" },
] as const;

for (const { vocabulary, name, region, text } of SAVES) {
  test(`a save the server fails on shows its refusal in ${name}'s panel, and writes nothing`, async ({
    page,
    vocabularyGui,
  }) => {
    const before = entryOf(vocabularyGui.directory, vocabulary, name);
    const panel = await openEntry(page, vocabularyGui, name);
    const saving = panel.getByRole("region", { name: region });
    await saving.getByRole("textbox", { name: region }).fill(text);
    await expect(saving.getByText(`Changes 1 file: ${FILES[vocabulary].file}`)).toBeVisible();

    const failed = await failing(page, "/api/edit", "http");
    await saving.getByRole("button", { name: "Save" }).click();
    await expect(saving.getByRole("status")).toHaveText(REFUSED);
    expect(failed()).toBe(1);
    expect(entryOf(vocabularyGui.directory, vocabulary, name)).toEqual(before);
  });
}
```

  Rows 50 and 51 go at the end of `findings.spec.ts`. Extend its `./demo` import with `held` and `REFUSED`, which Biome puts after `failing` and after `PUMP`:

```ts
test("a page of findings still being read is drawn as placeholder rows, which its findings replace", async ({
  page,
  copiedGui,
}) => {
  // Drifted before the server starts, so that the first revision already holds the two findings.
  const gui = await copiedGui("demo", (directory) => {
    drift(directory);
  });
  await page.goto(gui.address);
  const tab = page.getByRole("link", { name: "Findings", exact: true });
  await expect(tab).toBeVisible();
  const release = await held(page, "/api/findings");
  try {
    await tab.click();
    // The line above the table is the state's own, counted before any page of findings comes.
    await expect(page.getByText("2 findings · 2 errors", { exact: true })).toBeVisible();
    await expect(page.getByRole("gridcell", { name: "Reading…", exact: true })).toHaveCount(2);
    await expect(page.getByRole("row", { name: /definition-mismatch/ })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.getByRole("row", { name: /definition-mismatch/ })).toHaveCount(2);
  await expect(page.getByRole("gridcell", { name: "Reading…" })).toHaveCount(0);
});

test("a fix the server fails on shows its refusal in its panel, and writes nothing", async ({
  page,
  gui,
}) => {
  unstamp(gui.directory, CONTROLLER, "ValueH");
  const failed = await failing(page, "/api/edit", "http");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page.getByRole("row", { name: "missing-id" }).click();
  const panel = page.getByRole("complementary", { name: "missing-id" });
  await panel.getByRole("button", { name: "Give 'ValueH' an id" }).click();
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect(panel.getByRole("status")).toHaveText(REFUSED);
  expect(failed()).toBe(1);
  // Nothing was written, and the finding is still reported.
  expect(valueH(gui.directory).id).toBeUndefined();
  await expect(page.getByRole("row", { name: "missing-id" })).toHaveCount(1);
});
```

  Run each with `--repeat-each=10` (the loops count three tests each), then ablate each as its row says. Read the panel's accessible name for row 51 off the running page: the finding's check, `missing-id`.
- [ ] **Step 4: The bug,** red first. After a fix the server failed on, the panel keeps saying so and offers no Apply, so the fix cannot be tried again until the finding is pressed again. Add the journey that says it can, at the end of `findings.spec.ts`:

```ts
test("a fix the server failed on can be chosen again, and applied", async ({ page, gui }) => {
  unstamp(gui.directory, CONTROLLER, "ValueH");
  const failed = await failing(page, "/api/edit", "http", 1);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page.getByRole("row", { name: "missing-id" }).click();
  const panel = page.getByRole("complementary", { name: "missing-id" });
  const fix = panel.getByRole("button", { name: "Give 'ValueH' an id" });
  await fix.click();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(panel.getByRole("status")).toHaveText(REFUSED);
  expect(failed()).toBe(1);

  // Choosing the fix off and on again is the reader's next choice: the refusal goes with it, and
  // the fix is offered again, as it was before the server failed on it.
  await fix.click();
  await fix.click();
  await expect(panel.getByRole("status")).toHaveCount(0);
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
  expect(valueH(gui.directory).id).toMatch(/^[abcdefghjkmnpqrstvwxyz0-9]{12}$/);
});
```

  Run it on the page as it is. It fails at `await expect(panel.getByRole("status")).toHaveCount(0)`, expecting 0 and receiving 1: the refusal outlives the reader's next choice. Record that failure in the report. Then the change, in `gui/src/screens/FindingsPage.tsx`: after `select`, a handler for the choice, and `onChoose={choose}` where `onChoose={setChosen}` stood:

```tsx
  // Choosing a fix, or letting it go, is the reader's next choice: a refusal the server gave for
  // an apply goes with it, and the fix is offered again. A refusal because a file changed on disk
  // is not cleared here: it waits for the analysis (`shownRefusal`).
  const choose = (title: string | undefined) => {
    setChosen(title);
    setRefused(null);
  };
```

  Run the journey again with `--repeat-each=10`: 10 passed. Then every other journey of `findings.spec.ts`, which must pass unchanged, and the ablation in a scratch copy: `onChoose={choose}` made `onChoose={setChosen}` again kills the retry journey, and no other.
  - **The CHANGELOG.** One entry under `## Unreleased`, in the file's own style (a bold lead, two spaces between sentences, no line over 95 columns), saying what a reader notices:

```
* **A fix the server failed on can be chosen again.**  On the Findings tab, after the server
  failed on applying a finding's fix - an error of its own, not a file changed on disk - the
  panel went on saying so and drew no Apply, whichever fix was chosen next, until the finding
  was pressed again.  Choosing a fix now takes that refusal away and offers the Apply.  A
  refusal because a file changed on disk is still held until the analysis has caught up.
```

  - **No Ladle reference changes.** The view, `FindingPanelView.tsx`, is untouched, and its `FixChosen` and `Refused` stories already draw the two states the reader moves between. The screenshots in Docker, in compare mode, must show no reference moved.
  - Any other bug a journey finds follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Rows 42, 43, 45, 46, 47, 49a to 49d, 50 and 51 each name their journey, by file and test title; the loops name the title of each of their three tests. Rows 44 and 48 are Task 2's and Task 5's.
- [ ] **Step 6: The gates,** every journey included. Commit: one commit for the Shared files rows, one for rows 50 and 51, and one for the retry journey, the change and the CHANGELOG entry.

### A.7 Files, rows 52 to 62

**Model:** sonnet, reviewed on sonnet. Each row is a state the Files tab already draws, reached with Task 1's helpers and three local ones.

**Files:**
- Modify: `gui/e2e/files.spec.ts`, and this plan's *The inventory*

**Interfaces:**
- Consumes, from Task 1, in `gui/e2e/demo.ts`:
  - `held(page: Page, path: string | RegExp | ((url: URL) => boolean)): Promise<() => void>`: holds the next request that matches, once only, until the function it answers is called, then lets it through unchanged. A string is a pathname matched exactly. Call the function in a `finally`.
  - `REFUSED`: `` `The change was refused: ${SERVER_FAILED}` ``, the sentence a panel shows when `failing(page, path, "http")` has failed its Apply.
  - `editJson(directory: string, file: string, change: (data: any) => void): void`: reads a json file of a copy, applies `change`, and writes it whole (two-space indent, a final newline); it throws if the text did not change. It works as a `copiedGui` change.
- Consumes, as they stand: the fixtures `gui`, `vocabularyGui` and `copiedGui` (`gui/e2e/fixtures.ts`); `failing(page, path, how, times?)`, which answers how many requests it has failed, and `UNITS`, `writeUnseen` and `SERVER_FAILED` (`gui/e2e/demo.ts`); in `files.spec.ts`, `EXTRA`, `PROJECT` and `STALE`.
- Adds three helpers, local to `files.spec.ts` and used by this task alone (P19c-4), each with its code in Step 1:
  - `newFile(page: Page, kind: string, name: string, component?: string): Promise<Locator>`: New file pressed and filled in, answering its panel;
  - `addFile(page: Page, path: string): Promise<Locator>`: Add a file pressed and its path typed, answering its panel;
  - `rewrittenDescription(directory: string): string`: the text of the vocabulary copy's project description with a space taken out and a full stop put in, which keeps its size, for `writeUnseen`.

**What the pre-flight found:**
- **Eleven rows, thirteen journeys, and four more rows.** Rows 53 and 56 are two states each (53a and 53b, 56a and 56b). Row 62 is one journey, by Remove, since all three actions share `useFilesApply`, which that journey pins. The four rows the pre-flight added (P19c-9) are a removal or an add the server could not judge, a removal a pattern keeps in, a plan refused as out of date before any press, and a finding's route followed to a Files row. They are the last four rows of the table.
- **None of rows 52 to 62 is covered already.** The neighbouring journeys are the first (a component created, a file added, two removals), the rows a New file and a Remove hold, the Remove out of date, the errors an Add brings, and the list failing at first and once drawn. This task repeats none of them.
- **A row's state is one `toHaveText` over its cells.** A row's accessible name is its Entry cell's text, and its other three cells are `gridcell`s: Kind, State and Findings. A pattern's child is named by its path relative to the project, which is posix on every platform, as the server's keys are.
- **53 and the held row.** After an Apply the tab holds the new file's row until the analysis has read it, and the held row reads "not read by the last analysis" meanwhile (`lib/filesHold.ts`). `toHaveText` retries to the final cells.
- **54, 55 and 61: the page draws the server's own sentences,** so their ablations are lines of `ddd/file_plans.py`, in the scratch copy of the package. The guard in `Preview` that draws a refusal (`{refusal !== null && (`) also kills 54, 55, 56a, 56b, 61, 62 and the plan refused as out of date, so it is not an ablation of one row.
- **56 has two orders.** A create plan is not judged, so New file's write may be made at any point before the press. An Add's plan, and a Remove's, are judged against the revision and read the files afresh, so a description changed before the plan is asked refuses the plan itself (the third added row): 56b writes after the preview is drawn. Both assert the sentence and the file, never whether the Apply stays (P19c-6).
- **57 to 59 are three ways the last analysis did not take a file.** A half-written file (57) is read and fails. An entry naming a file that is not there (58) has none to read. A file appearing where a pattern matches (59) starts no analysis: measured, no new revision followed it after three seconds.
- **58 and the "unjudged" row share a project.** A project naming a file that is not there is never fully analysed, since its `file-not-found` is an error no build lowers, so every plan on it is still offered, with a sentence saying it could not be judged.
- **59 to 61 and the `kept_by` row use the demo,** whose pattern `components/*.ddd.json` the Files tab has not listed in any journey on Windows: every Files journey so far uses `vocabularyGui`. The page code is platform-free and the server's pattern rows are pinned on Windows by `tests/test_gui_api.py`, so the first Windows leg measures these journeys.
- **The `kept_by` row has two rows of one name.** A literal entry naming a file that a pattern also matches draws its own row and the pattern's child, both keyed by the same path. Pressing either selects both, and the removal is of every entry with that key.
- **No sentence of these rows carries a path outside the project.** "Changes N files" names base names, the Remove refusals name a file's base name and the pattern as written, a child is named by its path relative to the project, and the one address asserted, a finding's route to a row, is matched by its tail.
- **No bug was found on this tab.** A journey that finds one follows the rule in *Global Constraints*.
- **As drafted,** every journey below ran green ten times over against the page as it stands, and died under its ablation.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **reading the project's files** | `vocabularyGui`. After `goto`, and before the tab is pressed, `held(page, "/api/files")`. | `FilesPage.tsx`, while the list has no data and has not failed, returns `<p className="quiet">Reading the project's files…</p>` and nothing else. Pressing the link "Files" shows that sentence, with no grid and neither button "New file" nor "Add a file". Released, the row `units.ddd.json` and the two buttons are drawn and the sentence is gone. | That sentence made `Reading…`: dies at the sentence's `toBeVisible`. |
| **a New file of a vocabulary's own kind: types, units, constants, sections or rasters** (53a, a file of types, created empty) | `vocabularyGui`. | `NewFileView` lists `props.creatable`, the server's `CREATABLE` in its own order (`file_plans.py`): ArrowDown on the combobox "Kind" shows the options component, types, units, constants, sections, rasters. Kind "types" and the name `extra_types` preview "Changes 2 files: extra_types.ddd.json, project.ddd.json"; applied, the row `extra_types.ddd.json` reads `["types", "", "1"]` (Kind, State, Findings: its `empty-vocabulary` note), the file is `{ "types": [] }` and the includes end with it. The other three kinds take the same branch (`_content`'s `return {kind: []}`), so one kind and the list are enough. | `FileActionsView.tsx`'s `choices: props.creatable.map(` made `props.creatable.slice(0, 2).map(`: dies at the options. In the scratch package, `file_plans.py`'s `return {kind: []}` made `return {"units": []}`: dies at the row's cells. |
| **a New file of a vocabulary's own kind** (53b, a first units file listing the units in use) | `gui`: the demo has no units file. | Where no file of the tree is a units file, `_content` lists every unit the project states. `newFile(page, "units", "units")` previews "Changes 2 files: demo.ddd.json, units.ddd.json", and "Show changes" shows a hunk "units.ddd.json, new". Applied, the row `units.ddd.json` reads `["units", "", ""]`, the file lists `%`, `Hz`, `V`, `degC` and `ms`, the includes end with it, and the Findings tab says "Nothing to report". | In the scratch package, `api.py`'s `checks_units=any(file.kind == "units" for file in revision.files)` made `checks_units=True`: the file is created empty, and it dies at the row's cells, `["units", "", ""]`, before the units listed. |
| **New file refused** | `vocabularyGui`. | `Preview` (`FileActionsView.tsx`) draws `<p className="panel-refusal" role="status">{refusal}</p>` in the panel, with no plan and so no Apply. A component named "valve", with no component name, says "a new component needs a name, besides its file's". Kind "constants" and the name "constants" say "constants.ddd.json is there already, beside project.ddd.json". Another name takes the refusal away and previews "Changes 2 files: extra.ddd.json, project.ddd.json" with its Apply. | In the scratch package, `file_plans.py`'s `if (described.parent / filename).exists():` made `if False:`: dies at the second sentence. |
| **Add a file refused** | `vocabularyGui`. | The same `Preview`, in the panel "Add a file". The path `ghost.ddd.json` says "ghost.ddd.json names no file; a file not there yet is created, not added" (a 404, drawn as any refusal) and offers no Apply. `pump.ddd.json` says "pump.ddd.json is part of this project already, as the entry 'pump.ddd.json'", and `project.ddd.json` says "project.ddd.json is this project's own description, which it cannot include". | In the scratch package, `file_plans.py`'s `if not os.path.isfile(added):  # noqa: PTH113` made `if False:  # noqa: PTH113`: dies at the first sentence. |
| **New file's and Add's out-of-date refusal, shown in their own panels** (56a, New file) | `vocabularyGui`. `rewrittenDescription` written with `writeUnseen` once the preview is drawn; a create plan is not judged, so before the form is opened would do as well. | `useFilesApply` (`FilesPage.tsx`) keeps the stale refusal, and `NewFile` hands it to its view in `offer={{ plan: offerPlan, refusal }}`, where `Preview` draws it. "Apply to 2 files" after the write shows `STALE` in the panel's status. `valve.ddd.json` does not exist, and the description is as the outside change left it. Nothing is asserted of the Apply (P19c-6). | `NewFile`'s `offer`, its `refusal` made `null`: dies at the status, and row 54 with it, which draws through the same prop. Or `useFilesApply`'s `setStale({ text: refusalOf(error), revision })` made `setStale(null)`: dies at the status, and 56b's with it, which shares the arm. |
| **New file's and Add's out-of-date refusal, shown in their own panels** (56b, Add) | `vocabularyGui`, with `extra.ddd.json` written into the copy before `goto`. `rewrittenDescription` written with `writeUnseen` only after the preview is drawn: an Add's plan is judged against the revision, so a write before it refuses the plan itself. | The same, through `AddFile`'s `offer`. "Apply to 1 file" after the write shows `STALE` in the panel's status. The description is as the outside change left it, and its includes do not name `extra.ddd.json`. Nothing is asserted of the Apply (P19c-6). | `AddFile`'s `offer`, its `refusal` made `null`: dies at the status, and row 55 and the plan refused as out of date before any press with it. |
| **an entry whose file did not load** | `vocabularyGui`. With the tab open, `units.ddd.json` is cut in half. | `stateOf` (`lib/files.ts`) answers "did not load" for a row whose file the state holds as not loaded, and a file nobody can parse has no kind. The row's gridcells go from `["units", "", ""]` to `["unknown", "did not load", "1"]` (the `json-syntax` error), the other rows are as they were, and written back whole the row returns. | `stateOf`'s `return row.file.loaded ? "" : "did not load";` made `return row.file.loaded ? "" : "";`: the State cell reads empty, and it dies at `toHaveText(["unknown", "did not load", "1"])`. |
| **an entry naming no file** | `copiedGui("vocabulary", …)`, whose change appends `"ghost.ddd.json"` to `project.includes` with `editJson`. | `stateOf` answers "names no file" for an entry that names no file and brings none (`!row.entry.names && row.entry.files.length === 0`). The row `ghost.ddd.json` reads `["", "names no file", "1"]` (the `file-not-found` error at the entry), and `pump.ddd.json` reads `["component", "", ""]`. | That `return "names no file";` made `return "no file";`: dies at the cells. |
| **an entry the last analysis did not read** | `gui`. Before `goto`, `components/extra.ddd.json` written into the copy: the fixture has finished its analyses, and a file appearing starts none. | `/api/files` lists the file under the demo's pattern while the state does not hold it, and `stateOf`'s last return reads "not read by the last analysis". The child row `components/extra.ddd.json` reads `["", "not read by the last analysis", ""]`, and `components/controller.ddd.json` reads `["component", "", ""]`. | That last `return "not read by the last analysis";` made `return "unread";`: dies at the cells. |
| **a pattern entry, the files it matches listed under it** | `gui`. | `rowsOf` (`lib/files.ts`) lists a pattern's own row, then a `child` row for each file it matches. The Entry headers are, in order, `components/*.ddd.json`, `components/controller.ddd.json`, `components/sensor_hub.ddd.json`, `components/user_interface.ddd.json` and `subsystems/logging/logging.ddd.json`, with Kind empty, "component" for the three children and "project" for the last. A child's rowheader has `padding-left` `26px`; the pattern's and the sub-project's, `10px`. | `FilesTableView.tsx`'s `className={also(row.child ? "child" : "")}` made `className={also("")}`: the rows stay and the indent goes, so it dies at the first child's `padding-left`. |
| **a removal refused for a file only a pattern brings in** | `gui`. | Pressing the child `components/controller.ddd.json` asks its removal at once. The server refuses it, naming the pattern, and `Preview` draws the refusal in the region "Remove from the includes" of the panel: "controller.ddd.json has no entry of its own: the pattern 'components/*.ddd.json' brings it in, and only the whole pattern can be removed". The region has no button, and the row is still listed. | In the scratch package, `file_plans.py`'s `if brought_by is not None:` made `if False:`: dies at the sentence. |
| **an Apply the server fails on** | `vocabularyGui`. The units row pressed and its Remove planned ("Changes 1 file: project.ddd.json" visible), then `failing(page, "/api/edit", "http")`. One journey, by Remove, stands for the three actions, which share `useFilesApply`. | `useFilesApply`'s apply mutation, in its `else` arm, sets `setRefused(refusalOf(error))`, which `Preview` draws as the region's status. Pressing "Remove from the includes" shows `REFUSED`. `failed()` is 1, the row `units.ddd.json` is still listed, and the description still includes it. Nothing is asserted of the Apply (P19c-6). | That `setRefused(refusalOf(error))` made `setRefused(null)`: dies at the status. |
| **a removal or an add the server could not judge** (added, P19c-9) | `copiedGui("vocabulary", …)`: `extra.ddd.json` written into the copy, and `"ghost.ddd.json"` appended to the includes with `editJson`. | A project naming a file that is not there is never fully analysed, so no plan on it is judged, and `Preview` draws the server's `preview.unjudged` as `<p className="file-unjudged">`, above the consequence. Pressing the row `ghost.ddd.json` shows in "Remove from the includes": "not every analysis of this project ran to its end, so what removing ghost.ddd.json leaves cannot be judged", with "Changes 1 file: project.ddd.json" and the button. Adding `extra.ddd.json` shows "… so what adding extra.ddd.json brings cannot be judged" and "Apply to 1 file". | `FileActionsView.tsx`'s `{preview.unjudged !== null && <p className="file-unjudged">{preview.unjudged}</p>}` made `{false && …}`: dies at the first sentence. |
| **a removal a pattern keeps in** (added, P19c-9) | `copiedGui("demo", …)`, whose change splices `"components/controller.ddd.json"` into the includes after the pattern, with `editJson`. | The remove plan carries `kept_by`, the pattern, and `keptBy` (`lib/files.ts`) words it as `<p className="file-note">`: "components/controller.ddd.json stays in the project all the same: the pattern 'components/*.ddd.json' brings it in." Two rows are named `components/controller.ddd.json`, the pattern's child and the entry, and pressing the last one shows the sentence and the button. Applied, the entry goes and the file stays: one row of that name is left, and the includes read the pattern and the sub-project. | `FileActionsView.tsx`'s `{preview.kept !== null && <p className="file-note">{preview.kept}</p>}` made `{false && …}`: dies at the sentence. |
| **a plan refused as out of date before any press** (added, P19c-9; the pre-flight's draft 56c) | `vocabularyGui`, with `extra.ddd.json` written into the copy and `rewrittenDescription` written with `writeUnseen`, both before `goto`. | A plan that judges a change reads the files afresh. With the description changed since the analysis the server refuses the plan itself, with the status 409 `stale`, and `Preview` draws it as the panel's status: "project.ddd.json changed since the project was analysed, so the change cannot be judged until the project is analysed again", with no plan and no Apply. It does so in the Add panel for `extra.ddd.json`, and in the Remove region of the row `units.ddd.json` pressed after it. | `AddFile`'s `offer`, its `refusal` made `null`, dies at the Add panel's status, and `RemoveFile`'s at the Remove region's. |
| **a finding's route followed to a Files row** (added, P19c-9) | `copiedGui("vocabulary", …)`: `extra_types.ddd.json`, declaring nothing (`{ "types": [] }`), written into the copy and appended to the includes with `editJson`. | Its `empty-vocabulary` finding's panel offers the link "Open extra_types.ddd.json" (`routeLabel`: the path relative to the project). Following it goes by `routeOf`'s `route.kind === "file"` arm to the address `/project?view=files&path=<the file's path>`. The Files tab is current, the row `extra_types.ddd.json` is `aria-selected="true"`, and its removal is planned at once ("Changes 1 file: project.ddd.json" in the region "Remove from the includes"), with no "Plan its removal" asked, since a move within the page is not an arrival. | `routeOf`'s `if (route.kind === "file" && route.name !== null) {` made to match no kind (`"files"`): the link leads to the component page, and it dies at the address. |

- [ ] **Step 1: The local helpers and the worked journey,** row 57, in `gui/e2e/files.spec.ts`. Extend the file's imports, so that its first lines read:

```ts
import { existsSync, readFileSync, utimesSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { editJson, failing, held, REFUSED, SERVER_FAILED, UNITS, writeUnseen } from "./demo";
import { expect, type Gui, test } from "./fixtures";
```

  Then add at the end of the file the three helpers, and the journey:

```ts
/** New file pressed and filled in as a reader fills it: its kind typed and confirmed with Enter,
 * then the file's name and, for a component, the component's own. Answers the panel. */
async function newFile(
  page: Page,
  kind: string,
  name: string,
  component?: string,
): Promise<Locator> {
  await page.getByRole("button", { name: "New file" }).click();
  const creating = page.getByRole("complementary", { name: "New file" });
  const chooser = creating.getByRole("combobox", { name: "Kind" });
  await chooser.fill(kind);
  await chooser.press("Enter");
  await creating.getByRole("textbox", { name: "File name" }).fill(name);
  if (component !== undefined) {
    await creating.getByRole("textbox", { name: "Component name" }).fill(component);
  }
  return creating;
}

/** Add a file pressed and its path typed. Answers the panel. */
async function addFile(page: Page, path: string): Promise<Locator> {
  await page.getByRole("button", { name: "Add a file" }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  await adding.getByRole("textbox", { name: "Path" }).fill(path);
  return adding;
}

/** A copy of examples/vocabulary's description with a space taken out and a full stop put in: the
 * text a journey writes over it with `writeUnseen`, which keeps the file's size, so that the
 * session's watcher does not see it. */
function rewrittenDescription(directory: string): string {
  const original = readFileSync(join(directory, PROJECT), "utf8");
  const changed = original
    .replace('"name": "PumpDevice"', '"name":"PumpDevice"')
    .replace('names its sizes"', 'names its sizes."');
  expect(changed).not.toBe(original);
  return changed;
}

test("an entry whose file did not load is listed as not loaded, and listed whole again once it loads", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const units = page.getByRole("row", { name: UNITS, exact: true });
  await expect(units.getByRole("gridcell")).toHaveText(["units", "", ""]);

  // Saved half-written, as an editor saves a file being typed into: it no longer parses, so it
  // has no kind, and the analysis files its error on it.
  const path = join(vocabularyGui.directory, UNITS);
  const whole = readFileSync(path);
  writeFileSync(path, whole.subarray(0, Math.floor(whole.length / 2)));
  await expect(units.getByRole("gridcell")).toHaveText(["unknown", "did not load", "1"]);
  const sections = page.getByRole("row", { name: "sections.ddd.json", exact: true });
  await expect(sections.getByRole("gridcell")).toHaveText(["sections", "", ""]);

  writeFileSync(path, whole);
  await expect(units.getByRole("gridcell")).toHaveText(["units", "", ""]);
});
```

  The kind is typed and confirmed with Enter, as the file's first journey does, so that a pick and typing leave the form in one state. `rewrittenDescription` is the change "a Remove applied while the description changed on disk is refused…" makes inline, kept here as a function because three journeys below use it; that older journey keeps its own copy. Read the row's cells off the running page before asserting them: the three `gridcell`s of the row are Kind, State and Findings, and a file half-written reads Kind "unknown", not the kind it had. The cut is a plain write, which the watcher sees, so the table follows the new revision with no reload.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`: 10 passed. Then the ablation, in a scratch copy of the package: `lib/files.ts`'s `stateOf` made to answer `""` for a file that did not load. It must die at `toHaveText(["unknown", "did not load", "1"])`, with the State cell empty, and no other journey of this task dies.
- [ ] **Step 3: The other rows,** each a journey of its own, in the order of the rows. First rows 52 to 56 and 58 to 62, at the end of `files.spec.ts`:

```ts
test("the Files tab says it is reading the project's files until the list answers", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  const tab = page.getByRole("link", { name: "Files", exact: true });
  await expect(tab).toBeVisible();
  const release = await held(page, "/api/files");
  try {
    await tab.click();
    await expect(page.getByText("Reading the project's files…", { exact: true })).toBeVisible();
    // Nothing else of the tab is drawn: not the table, and not the two ways to add a file.
    await expect(page.getByRole("grid")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "New file" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Add a file" })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.getByRole("row", { name: UNITS })).toBeVisible();
  await expect(page.getByRole("button", { name: "New file" })).toBeVisible();
  await expect(page.getByText("Reading the project's files…")).toHaveCount(0);
});

test("New file offers every kind the server creates, and a file of a vocabulary's own kind is created empty", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "New file" }).click();
  const creating = page.getByRole("complementary", { name: "New file" });
  const kind = creating.getByRole("combobox", { name: "Kind" });
  await kind.press("ArrowDown");
  await expect(page.getByRole("option")).toHaveText([
    "component",
    "types",
    "units",
    "constants",
    "sections",
    "rasters",
  ]);

  await kind.fill("types");
  await kind.press("Enter");
  await creating.getByRole("textbox", { name: "File name" }).fill("extra_types");
  await expect(
    creating.getByText("Changes 2 files: extra_types.ddd.json, project.ddd.json"),
  ).toBeVisible();
  await creating.getByRole("button", { name: "Apply to 2 files" }).click();

  // Its kind is read off the file once the analysis has read it, and it declares nothing: one note.
  const row = page.getByRole("row", { name: "extra_types.ddd.json", exact: true });
  await expect(row.getByRole("gridcell")).toHaveText(["types", "", "1"]);
  const created = readFileSync(join(vocabularyGui.directory, "extra_types.ddd.json"), "utf8");
  expect(JSON.parse(created)).toEqual({ types: [] });
  const project = JSON.parse(readFileSync(join(vocabularyGui.directory, PROJECT), "utf8")).project;
  expect(project.includes.at(-1)).toBe("extra_types.ddd.json");
});

test("New file of units, where the project has no units file, lists every unit in use", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const creating = await newFile(page, "units", "units");
  await expect(creating.getByText("Changes 2 files: demo.ddd.json, units.ddd.json")).toBeVisible();
  // The new file is shown as new, with its lines, and not as a change to one.
  await creating.getByRole("button", { name: "Show changes" }).click();
  await expect(
    creating.locator(".hunk .where").filter({ hasText: "units.ddd.json, new" }),
  ).toBeVisible();
  await creating.getByRole("button", { name: "Apply to 2 files" }).click();

  const row = page.getByRole("row", { name: "units.ddd.json", exact: true });
  await expect(row.getByRole("gridcell")).toHaveText(["units", "", ""]);
  const listed = JSON.parse(readFileSync(join(gui.directory, "units.ddd.json"), "utf8")).units;
  expect(listed.map((entry: { unit: string }) => entry.unit)).toEqual([
    "%",
    "Hz",
    "V",
    "degC",
    "ms",
  ]);
  const project = JSON.parse(readFileSync(join(gui.directory, "demo.ddd.json"), "utf8")).project;
  expect(project.includes.at(-1)).toBe("units.ddd.json");
  // A units file switches the unit check on, and every unit in use is listed: nothing is unknown.
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
});

test("New file refused is answered in the server's own words, with nothing to apply", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  // A component needs a name of its own besides its file's, which is said as soon as the file is
  // named: every component created here passes through this refusal.
  const creating = await newFile(page, "component", "valve");
  await expect(creating.getByRole("status")).toHaveText(
    "a new component needs a name, besides its file's",
  );

  // A file there already, under the name the reader gives it.
  const kind = creating.getByRole("combobox", { name: "Kind" });
  await kind.fill("constants");
  await kind.press("Enter");
  const name = creating.getByRole("textbox", { name: "File name" });
  await name.fill("constants");
  await expect(creating.getByRole("status")).toHaveText(
    "constants.ddd.json is there already, beside project.ddd.json",
  );
  await expect(creating.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  // Another name takes the refusal away, and the plan is offered.
  await name.fill("extra");
  await expect(creating.getByRole("status")).toHaveCount(0);
  await expect(
    creating.getByText("Changes 2 files: extra.ddd.json, project.ddd.json"),
  ).toBeVisible();
  await expect(creating.getByRole("button", { name: "Apply to 2 files" })).toBeVisible();
});

test("Add a file refused is answered in the server's own words, with nothing to apply", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const adding = await addFile(page, "ghost.ddd.json");
  await expect(adding.getByRole("status")).toHaveText(
    "ghost.ddd.json names no file; a file not there yet is created, not added",
  );
  await expect(adding.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  const path = adding.getByRole("textbox", { name: "Path" });
  await path.fill("pump.ddd.json");
  await expect(adding.getByRole("status")).toHaveText(
    "pump.ddd.json is part of this project already, as the entry 'pump.ddd.json'",
  );
  await path.fill(PROJECT);
  await expect(adding.getByRole("status")).toHaveText(
    "project.ddd.json is this project's own description, which it cannot include",
  );
});

test("New file applied from a description that changed on disk is refused in its own panel, and creates nothing", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const creating = await newFile(page, "component", "valve", "Valve");
  await expect(
    creating.getByText("Changes 2 files: project.ddd.json, valve.ddd.json"),
  ).toBeVisible();

  // Written where the session's own watcher does not see it (`writeUnseen`), so that only the
  // Apply's own fresh read of the bytes does.
  const changed = rewrittenDescription(vocabularyGui.directory);
  writeUnseen(vocabularyGui.directory, PROJECT, changed);
  await creating.getByRole("button", { name: "Apply to 2 files" }).click();

  await expect(creating.getByRole("status")).toHaveText(STALE);
  expect(existsSync(join(vocabularyGui.directory, "valve.ddd.json"))).toBe(false);
  expect(readFileSync(join(vocabularyGui.directory, PROJECT), "utf8")).toBe(changed);
});

test("Add a file applied from a description that changed on disk is refused in its own panel, and adds nothing", async ({
  page,
  vocabularyGui,
}) => {
  writeFileSync(
    join(vocabularyGui.directory, EXTRA),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const adding = await addFile(page, EXTRA);
  await expect(adding.getByText("Changes 1 file: project.ddd.json")).toBeVisible();

  // Only now, with the preview drawn: an Add's plan is judged against the revision, so a
  // description changed before the plan was asked refuses the plan itself (a journey below).
  const changed = rewrittenDescription(vocabularyGui.directory);
  writeUnseen(vocabularyGui.directory, PROJECT, changed);
  await adding.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect(adding.getByRole("status")).toHaveText(STALE);
  expect(readFileSync(join(vocabularyGui.directory, PROJECT), "utf8")).toBe(changed);
  expect(JSON.parse(changed).project.includes).not.toContain(EXTRA);
});

test("an entry naming no file is listed as naming none, with the error that says so", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("vocabulary", (directory) => {
    editJson(directory, PROJECT, (data) => data.project.includes.push("ghost.ddd.json"));
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  const ghost = page.getByRole("row", { name: "ghost.ddd.json", exact: true });
  await expect(ghost.getByRole("gridcell")).toHaveText(["", "names no file", "1"]);
  const pump = page.getByRole("row", { name: "pump.ddd.json", exact: true });
  await expect(pump.getByRole("gridcell")).toHaveText(["component", "", ""]);
});

test("a file a pattern matches that the last analysis did not read is listed as not read", async ({
  page,
  gui,
}) => {
  // Created after the analysis, where the demo's pattern matches it: a file appearing starts none.
  writeFileSync(
    join(gui.directory, "components", "extra.ddd.json"),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  const unread = page.getByRole("row", { name: "components/extra.ddd.json", exact: true });
  await expect(unread.getByRole("gridcell")).toHaveText(["", "not read by the last analysis", ""]);
  const read = page.getByRole("row", { name: "components/controller.ddd.json", exact: true });
  await expect(read.getByRole("gridcell")).toHaveText(["component", "", ""]);
});

test("a pattern's row is listed with the files it matches beneath it, indented", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  const rows = [
    { entry: "components/*.ddd.json", kind: "", indent: "10px" },
    { entry: "components/controller.ddd.json", kind: "component", indent: "26px" },
    { entry: "components/sensor_hub.ddd.json", kind: "component", indent: "26px" },
    { entry: "components/user_interface.ddd.json", kind: "component", indent: "26px" },
    { entry: "subsystems/logging/logging.ddd.json", kind: "project", indent: "10px" },
  ];
  await expect(page.getByRole("rowheader")).toHaveText(rows.map((row) => row.entry));
  for (const { entry, kind, indent } of rows) {
    const row = page.getByRole("row", { name: entry, exact: true });
    await expect(row.getByRole("gridcell")).toHaveText([kind, "", ""]);
    // A matched file's first cell is indented past its pattern's, which stands at the table's edge.
    await expect(row.getByRole("rowheader")).toHaveCSS("padding-left", indent);
  }
});

test("a removal of a file only a pattern brings in is refused, naming the pattern", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const child = page.getByRole("row", { name: "components/controller.ddd.json", exact: true });
  await child.click();

  const removing = page
    .getByRole("complementary", { name: "components/controller.ddd.json" })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(removing.getByRole("status")).toHaveText(
    "controller.ddd.json has no entry of its own: the pattern 'components/*.ddd.json' brings it " +
      "in, and only the whole pattern can be removed",
  );
  await expect(removing.getByRole("button")).toHaveCount(0);
  await expect(child).toBeVisible();
});

test("a removal the server fails on shows its refusal in its panel, and writes nothing", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("row", { name: UNITS }).click();
  const removing = page
    .getByRole("complementary", { name: UNITS })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(removing.getByText("Changes 1 file: project.ddd.json")).toBeVisible();

  const failed = await failing(page, "/api/edit", "http");
  await removing.getByRole("button", { name: "Remove from the includes" }).click();
  await expect(removing.getByRole("status")).toHaveText(REFUSED);
  expect(failed()).toBe(1);
  await expect(page.getByRole("row", { name: UNITS })).toBeVisible();
  const written = JSON.parse(readFileSync(join(vocabularyGui.directory, PROJECT), "utf8")).project;
  expect(written.includes).toContain(UNITS);
});
```

  Then the four rows the pre-flight added (P19c-9), after row 62's:

```ts
test("a removal or an add the server could not judge says so, and is still offered", async ({
  page,
  copiedGui,
}) => {
  // A project naming a file that is not there is never fully analysed: its error is one no build
  // lowers, so there is no whole analysis to judge a change against.
  const gui = await copiedGui("vocabulary", (directory) => {
    writeFileSync(
      join(directory, EXTRA),
      JSON.stringify({ component: { name: "Extra", interface: [] } }),
      "utf8",
    );
    editJson(directory, PROJECT, (data) => data.project.includes.push("ghost.ddd.json"));
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  await page.getByRole("row", { name: "ghost.ddd.json", exact: true }).click();
  const removing = page
    .getByRole("complementary", { name: "ghost.ddd.json" })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(
    removing.getByText(
      "not every analysis of this project ran to its end, so what removing ghost.ddd.json " +
        "leaves cannot be judged",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(removing.getByText("Changes 1 file: project.ddd.json")).toBeVisible();
  await expect(removing.getByRole("button", { name: "Remove from the includes" })).toBeVisible();

  const adding = await addFile(page, EXTRA);
  await expect(
    adding.getByText(
      "not every analysis of this project ran to its end, so what adding extra.ddd.json " +
        "brings cannot be judged",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(adding.getByRole("button", { name: "Apply to 1 file" })).toBeVisible();
});

test("a removal a pattern keeps in the project says so, and takes the entry out alone", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => {
    editJson(directory, "demo.ddd.json", (data) =>
      data.project.includes.splice(1, 0, "components/controller.ddd.json"),
    );
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  // Two rows name the file, the pattern's child and the entry that names it; each stands for the
  // same key, and the removal is of every entry that has it.
  const rows = page.getByRole("row", { name: "components/controller.ddd.json", exact: true });
  await expect(rows).toHaveCount(2);
  await rows.last().click();
  const removing = page
    .getByRole("complementary", { name: "components/controller.ddd.json" })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(
    removing.getByText(
      "components/controller.ddd.json stays in the project all the same: the pattern " +
        "'components/*.ddd.json' brings it in.",
      { exact: true },
    ),
  ).toBeVisible();
  await removing.getByRole("button", { name: "Remove from the includes" }).click();

  // The entry went and the file stayed: only the pattern's child names it now.
  await expect(rows).toHaveCount(1);
  const written = JSON.parse(readFileSync(join(gui.directory, "demo.ddd.json"), "utf8")).project;
  expect(written.includes).toEqual([
    "components/*.ddd.json",
    "subsystems/logging/logging.ddd.json",
  ]);
});

test("an add or a removal asked for after a file changed on disk is refused as a plan, in its own panel", async ({
  page,
  vocabularyGui,
}) => {
  writeFileSync(
    join(vocabularyGui.directory, EXTRA),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );
  // Before any plan is asked, and unseen by the watcher: the revision the page holds is the one
  // before, and a plan that judges a change reads the file afresh.
  writeUnseen(vocabularyGui.directory, PROJECT, rewrittenDescription(vocabularyGui.directory));
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  const refused =
    "project.ddd.json changed since the project was analysed, so the change cannot be judged " +
    "until the project is analysed again";
  const adding = await addFile(page, EXTRA);
  await expect(adding.getByRole("status")).toHaveText(refused);
  await expect(adding.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  await page.getByRole("row", { name: UNITS }).click();
  const removing = page
    .getByRole("complementary", { name: UNITS })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(removing.getByRole("status")).toHaveText(refused);
  await expect(removing.getByRole("button")).toHaveCount(0);
});

test("an empty vocabulary's finding leads to its row of the Files tab", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("vocabulary", (directory) => {
    writeFileSync(join(directory, "extra_types.ddd.json"), JSON.stringify({ types: [] }), "utf8");
    editJson(directory, PROJECT, (data) => data.project.includes.push("extra_types.ddd.json"));
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page.getByRole("row", { name: "empty-vocabulary" }).click();
  const finding = page.getByRole("complementary", { name: "empty-vocabulary" });
  await finding.getByRole("link", { name: "Open extra_types.ddd.json" }).click();

  // The row's key is the file's own path, which the address carries as `path`.
  await expect(page).toHaveURL(
    (url) =>
      url.searchParams.get("view") === "files" &&
      (url.searchParams.get("path") ?? "").endsWith("/extra_types.ddd.json"),
  );
  await expect(page.getByRole("link", { name: "Files", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(
    page.getByRole("row", { name: "extra_types.ddd.json", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  // Reached by the page's own link, so the removal is planned at once, with no press asked of the
  // reader first.
  const removing = page
    .getByRole("complementary", { name: "extra_types.ddd.json" })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(removing.getByText("Changes 1 file: project.ddd.json")).toBeVisible();
  await expect(page.getByRole("button", { name: "Plan its removal" })).toHaveCount(0);
});
```

  Run each with `--repeat-each=10` and ablate it as its row says. The Python ablations are made in the scratch copy of the package (`ddd/file_plans.py`, `ddd/gui/api.py`), the journeys' server started from it with `PYTHONPATH=<scratch>/pysrc` and `PYTHONDONTWRITEBYTECODE=1`, and the copy's `static_directory()` checked to be its own. Read every sentence off the running page before asserting it, and the cells of every row the way Step 1 says.
- [ ] **Step 4: Bugs.** None is known on this tab. A journey that finds one follows the rule in *Global Constraints*.
- [ ] **Step 5: The inventory.** Rows 52 to 62, with 53a and 53b and 56a and 56b, each name their journey, by file and test title. Add the four rows the pre-flight added under Files, owned by this task, each naming its journey: "a removal or an add the server could not judge", "a removal a pattern keeps in", "a plan refused as out of date before any press", and "a finding's route followed to a Files row".
- [ ] **Step 6: The gates,** every journey included. Commit: one commit for the helpers and rows 52 to 62, and one for the four added rows.

### A.8 Compare, rows 63 to 66

**Model:** sonnet, reviewed on sonnet. Each row is a state the tab already draws, reached with the helpers the suite has; the one fix is a rule of a few lines under Vitest, red first.

**Files:**
- Modify: `gui/e2e/compare.spec.ts`, `gui/src/lib/compare.ts`, `gui/src/lib/compare.test.ts`, `gui/src/screens/ComparePage.tsx`, `CHANGELOG.md`, and this plan's *The inventory*

**Interfaces:**
- Consumes:
  - `dump`, `driftDatatypeIn`, `driftIn`, `editJson` (Task 1), and the constants `CONTROLLER`, `SENSOR_HUB` and `USER_INTERFACE`, in `gui/e2e/demo.ts`;
  - `copiedGui` (`gui/e2e/fixtures.ts`);
  - in `compare.spec.ts`, its own `posixOf` and `startingWith`.
- Produces, in `gui/src/lib/compare.ts`:
  - `interface Ask { readonly baseline: string; readonly number: number }`: the comparison the reader asked for, and the ask's number;
  - `nextAsk(previous: Ask | null, typed: string): Ask`: the ask a press of Compare, or an Enter, makes after `previous`: `typed` trimmed, numbered one more.

**What the pre-flight found:**
- **Rows 64, 66a and 66b share one setup,** the one of "a row of the findings table opens its finding in a panel" in this file: the demo dumped as the baseline, then ValueA widened in SensorHub, so that the first comparison already holds `changed-interface`. They keep separate journeys all the same, and **only row 63 asks with Enter**: its ablation must kill row 63 alone, so rows 64, 65, 66a and 66b ask with the button, as every other journey of this file does.
- **Row 63 pins two things in one line** of `CompareView.tsx`: the key (`Enter`) and the guard (`props.baseline.trim() !== ""`). The journey presses Enter on an empty field and on one of spaces, sees that no request goes out (a list of the requests the page made, read at the end: nothing waits on it), then asks for `  baseline.json  ` and sees the request carry `?baseline=baseline.json`.
- **Sentences built from parts, and paths.** A baseline row's File cell is `` `the baseline's ${name}` `` (`fileLabel`), `name` being `baseName` of the server's posix path: `the baseline's user_interface.ddd.json`. Its message is the server's, behind `in the baseline: ` (`BASELINE_PREFIX`, `deliveries.py`). The one path in a sentence is the refusal of the bug's first journey, `the baseline '<posix path>' is unreadable: <the system's words>`: `compare.py` writes the path with `as_posix()`, and the system's words differ between Linux and Windows, so `posixOf` and `startingWith` (this file's own) assert its start and at least one character after it.
- **Row 64's reason is `compareRouteReason`'s second arm.** `compare` files every finding of its own at the candidate's project file with an empty pointer, so the panel says it is about the whole delivery and offers no "Open …".
- **Row 65 compares the project against itself,** with UserInterface made a second writer of ValueJ, which EventLogger writes: the baseline's own `multiple-producers` errors are then the open project's own, in files that are the open project's own. A separate baseline directory would not do: the case worth pinning is a baseline finding whose file *is* a live component of the open project, which a server that routed by file membership would link (`api.py`'s `_finding(filed, None, cache)`, "never a source for one of these"). The open project is in error in that copy; that is irrelevant to this tab.
- **Row 66 is two states (P19c-8).** 66a is the Close button. 66b is the panel closing by itself when a fresh reply no longer carries its finding (`ComparePage`'s `setSelected(undefined)`): the visible closing is held by `CompareView`'s `row !== undefined` guard, and what `setSelected(undefined)` adds is that the panel does not spring back when the same finding returns (a finding's key is its severity, check, pointer and message, so a finding that comes back has the same key), which only the widen-it-again step pins.
- **The bug (P19c-10): asking again for the same path sends nothing.** `ComparePage` keyed its query on the trimmed path and the revision, so a second press with the same path was the same key, served from the answer the page held. Measured in Chrome on the Linux development PC, at `2bc00da`: a missing `later.json` is refused, the file is made, Compare and then Enter send no request and the refusal stays; and with another delivery written over `baseline.json`, the open project untouched, Compare and Enter send none and `This project can replace the baseline.` stays, though the server's cache (`compare.py`'s `stamped`) is built to notice the change. The second is the worse: a stale "can replace". The fix counts each ask into the key (`nextAsk`, in `lib/compare.ts`, under Vitest); `ComparePage` holds the `Ask` and keys the query on it. Every press is then a query of its own, and the server reads the baseline as it stands.
- **Recorded for the maintainer, not fixed (P19c-10): the Baseline field loses focus when it asks.** The field is `disabled={busy}` (`CompareView.tsx`), `busy` includes `compare.isFetching`, so after an Enter the field is enabled again but not focused (`document.activeElement` is `BODY`, measured), and a keyboard reader must click it to edit the path; with the fix, an Enter pressed again for the same path does the same. It happens too when a revision lands while the reader types: the typed text stays and the keystrokes after it are dropped. Not fixed: this file's "while a comparison is awaited the field and the button are disabled and the earlier verdict is gone" asserts the field is disabled (ruling P19b-5), so a `readOnly` field or a refocus changes recorded behaviour - a design choice. Step 4 gives the text for the plan's *What was left open*.
- **Left alone:** that busy journey's held request, which Task 1 converts to `held`; `hostile.spec.ts`, which asks `/api/compare` by hand; and `CompareView`'s two `trim()` guards, which stay in the view.
- **One inventory row is added** for the bug (Step 5), owned by this task.
- **What was measured,** in a scratch copy of the repository at `2bc00da` with these drafts and the fix in it, Chrome on the Linux development PC: the five rows' journeys and the two bug journeys below passed ten times in a row (`--repeat-each=10`: 70 of 70); the two bug journeys died on the page as it was, and the four Vitest cases with `nextAsk` absent; and each of the ten ablations named in this task died at the assertion it names, none surviving.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **a baseline asked for with Enter** | `gui`; `dump(gui.directory, "demo.ddd.json", "baseline.json")` before `page.goto`. | In the textbox "Baseline" Enter on an empty field and on `   `, with the button "Compare" disabled, send nothing; `  baseline.json  ` and Enter send one request, `?baseline=baseline.json`, and the verdict reads `This project can replace the baseline.` | `CompareView.tsx`'s `if (event.key === "Enter" && props.baseline.trim() !== "") props.onAsk();`, `"Enter"` made `"Escape"`: dies at the verdict; the `&& props.baseline.trim() !== ""` removed: dies at the list of requests (two, the first `?baseline=`). |
| **a finding about the whole delivery, saying why it leads nowhere** | `copiedGui("demo", widenedAfterDump)`. | Compare tab, `baseline.json` asked with the button, the row `changed-interface` pressed. In its panel (`getByRole("complementary", { name: "changed-interface" })`) the text `it is about the whole delivery being compared, not a place in one file` is visible and there is no link. | `compare.ts`'s `compareRouteReason` with its `if (row.finding.pointer === "") { return "it is about the whole delivery being compared, not a place in one file"; }` arm removed: dies at the sentence, the panel saying `demo.ddd.json is a project file, which has no page yet` (measured). |
| **the baseline's own findings, named as the baseline's and leading nowhere** | `copiedGui("demo", withTwoWritersOfValueJ)`. | Compare tab, `demo.ddd.json` asked with the button. The verdict reads `This project cannot replace the baseline.`, the summary `2 findings · 2 errors`; two rows `multiple-producers`, with the File cells `the baseline's user_interface.ddd.json` and `the baseline's event_logger.ddd.json`. In the panel of the first, the message `in the baseline: 'ValueJ' is written by component 'EventLogger' and by component 'UserInterface'; exactly one writer is allowed` and the reason `it is the baseline's own finding, not a place in your project`, and no link. | Three, each killed alone: `compare.ts`'s `if (row.fromBaseline) return "it is the baseline's own finding, not a place in your project";` removed dies at the reason (the panel would say `there is nothing at that place any more`); `fileLabel`'s ``return fromBaseline ? `the baseline's ${name}` : name;`` made `return name;` dies at the File cells; and on the server `api.py`'s `baseline_findings=[_finding(filed, None, cache) for filed in baseline_findings]` with `None` made `derived.files.get(derived.resolve(filed.file))` dies at the reason (the panel offers "Open ValueJ" instead). |
| **a finding's panel closed** (66a: the Close button) | `copiedGui("demo", widenedAfterDump)`. | Asked with the button, the row `changed-interface` pressed (`aria-selected` `true`), the panel visible. The button `Close changed-interface` is pressed: the panel has count 0, the row's `aria-selected` is `false`, and the verdict still reads `This project cannot replace the baseline.` | `CompareView.tsx`'s `onClose={() => props.onSelect(undefined)}` made `onClose={() => {}}` dies at the panel's count (received 1). |
| **a finding's panel closed** (66b: by itself, and not back with the finding) | `copiedGui` with `dump`, then `driftDatatypeIn` kept for its answer, the file as it shipped. | The panel is open. SensorHub is written back as it shipped: the verdict turns to `This project can replace the baseline.` and the panel is gone. `driftDatatypeIn` again: the verdict is `cannot` again, the row `changed-interface` is back, and the panel is not. | `ComparePage.tsx`'s `setSelected(undefined);` removed dies at the last `toHaveCount(0)` (received 1: the panel springs back). |

- [ ] **Step 1: The worked journey,** row 64's, in `gui/e2e/compare.spec.ts`. The file's imports end as below, with `held` too if Task 1 converted this file's busy journey (add the names as each journey needs them, so that the typecheck never sees one unused; `npx biome check --write` gives the order):

```ts
import { cpSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  CONTROLLER,
  driftDatatypeIn,
  driftIn,
  dump,
  editJson,
  renameValueA,
  SENSOR_HUB,
  USER_INTERFACE,
} from "./demo";
import { expect, test } from "./fixtures";
```

  First the setup row 64 shares with 66a and 66b, then the journey:

```ts
/** The setup of the Compare journeys that open a finding: the demo dumped as it ships, as the
 * baseline, and then ValueA's datatype in SensorHub widened, so that the first comparison already
 * holds `changed-interface` (`compare.spec.ts`'s "a row of the findings table opens its finding
 * in a panel"). */
function widenedAfterDump(directory: string): void {
  dump(directory, "demo.ddd.json", "baseline.json");
  driftDatatypeIn(directory, SENSOR_HUB, "ValueA", "uint16");
}
```

```ts
test("a finding about the whole delivery says why it leads nowhere", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", widenedAfterDump);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();
  await page.getByRole("row", { name: "changed-interface" }).click();

  // `compare` files every finding of a comparison at the candidate's project file, with no
  // pointer: it is about the delivery, not a place in one file, so there is no "Open …" to follow.
  const panel = page.getByRole("complementary", { name: "changed-interface" });
  await expect(
    panel.getByText("it is about the whole delivery being compared, not a place in one file", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(panel.getByRole("link")).toHaveCount(0);
});
```

  Read the panel's sentence off the running page before asserting it.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then the ablation: `compareRouteReason`'s `pointer === ""` arm removed, in a scratch copy of the package. It must die at the sentence, `toBeVisible`.
- [ ] **Step 3: The other rows,** each a journey of its own in `compare.spec.ts`, each run with `--repeat-each=10` and ablated as its row says.

```ts
test("a baseline typed is asked for with Enter, once, and a field with nothing in it asks for nothing", async ({
  page,
  gui,
}) => {
  dump(gui.directory, "demo.ddd.json", "baseline.json");
  // Every ask for a comparison the page makes, read at the end: nothing here waits on it.
  const asked: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/compare") asked.push(url.search);
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  const baseline = page.getByRole("textbox", { name: "Baseline" });

  // Nothing typed, then only spaces: Enter asks for nothing, as the button beside it is off.
  await baseline.press("Enter");
  await baseline.fill("   ");
  await expect(page.getByRole("button", { name: "Compare" })).toBeDisabled();
  await baseline.press("Enter");

  // A path with spaces round it is asked for without them.
  await baseline.fill("  baseline.json  ");
  await baseline.press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "replace the baseline" })).toHaveText(
    "This project can replace the baseline.",
  );
  expect(asked).toEqual(["?baseline=baseline.json"]);
});
```

```ts
/** The demo with UserInterface made a second writer of ValueJ, which EventLogger writes: the
 * project then has a `multiple-producers` error of its own, on each of the two files. */
function withTwoWritersOfValueJ(directory: string): void {
  editJson(directory, USER_INTERFACE, (data) => {
    const declaration = data.component.interface.find(
      (entry: { definition: { name: string } }) => entry.definition.name === "ValueJ",
    );
    if (declaration?.scope !== "input") {
      throw new Error(`${USER_INTERFACE} no longer reads ValueJ`);
    }
    declaration.scope = "output";
  });
}
```

```ts
test("the baseline's own findings are named as the baseline's, and lead nowhere", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", withTwoWritersOfValueJ);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  // The project against itself, the first thing a reader compares: the baseline's two errors are
  // the open project's own, in files that are the open project's own.
  await page.getByRole("textbox", { name: "Baseline" }).fill("demo.ddd.json");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByRole("status").filter({ hasText: "replace the baseline" })).toHaveText(
    "This project cannot replace the baseline.",
  );
  await expect(page.getByText("2 findings · 2 errors")).toBeVisible();

  const rows = page.getByRole("row", { name: "multiple-producers" });
  await expect(rows).toHaveCount(2);
  await expect(rows.filter({ hasText: "the baseline's event_logger.ddd.json" })).toHaveCount(1);
  const userInterface = rows.filter({ hasText: "the baseline's user_interface.ddd.json" });
  await expect(userInterface).toHaveCount(1);
  await userInterface.click();

  const panel = page.getByRole("complementary", { name: "multiple-producers" });
  await expect(
    panel.getByText(
      "in the baseline: 'ValueJ' is written by component 'EventLogger' and by component 'UserInterface'; exactly one writer is allowed",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    panel.getByText("it is the baseline's own finding, not a place in your project", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(panel.getByRole("link")).toHaveCount(0);
});
```

```ts
test("a finding's panel is closed by its Close button", async ({ page, copiedGui }) => {
  const gui = await copiedGui("demo", widenedAfterDump);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();
  const row = page.getByRole("row", { name: "changed-interface" });
  await row.click();
  const panel = page.getByRole("complementary", { name: "changed-interface" });
  await expect(panel).toBeVisible();
  await expect(row).toHaveAttribute("aria-selected", "true");

  await panel.getByRole("button", { name: "Close changed-interface" }).click();
  await expect(panel).toHaveCount(0);
  await expect(row).toHaveAttribute("aria-selected", "false");
  // Closing a panel asks nothing again: the comparison stands.
  await expect(page.getByRole("status").filter({ hasText: "replace the baseline" })).toHaveText(
    "This project cannot replace the baseline.",
  );
});
```

```ts
test("a finding's panel closes by itself once a comparison no longer reports it, and stays closed if it returns", async ({
  page,
  copiedGui,
}) => {
  // SensorHub as it ships, kept to put back.
  const shipped: { bytes: Buffer } = { bytes: Buffer.alloc(0) };
  const gui = await copiedGui("demo", (directory) => {
    dump(directory, "demo.ddd.json", "baseline.json");
    shipped.bytes = driftDatatypeIn(directory, SENSOR_HUB, "ValueA", "uint16");
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();
  const verdict = page.getByRole("status").filter({ hasText: "replace the baseline" });
  await expect(verdict).toHaveText("This project cannot replace the baseline.");
  const row = page.getByRole("row", { name: "changed-interface" });
  await row.click();
  const panel = page.getByRole("complementary", { name: "changed-interface" });
  await expect(panel).toBeVisible();

  // SensorHub put back as the baseline has it: the next revision no longer reports the finding,
  // the comparison is asked again for it, and the panel of a finding it no longer holds is gone.
  writeFileSync(join(gui.directory, SENSOR_HUB), shipped.bytes);
  await expect(verdict).toHaveText("This project can replace the baseline.");
  await expect(panel).toHaveCount(0);

  // Widened again, the very same finding comes back, and its panel does not: nobody asked for it.
  driftDatatypeIn(gui.directory, SENSOR_HUB, "ValueA", "uint16");
  await expect(verdict).toHaveText("This project cannot replace the baseline.");
  await expect(row).toBeVisible();
  await expect(panel).toHaveCount(0);
});
```

- [ ] **Step 4: The bug, red first.** Asking again for the same path sends nothing.
  - **4a. The journeys, red.** Two, in `compare.spec.ts`: the refusal that stands after the file is made, and the verdict that stands after the baseline was written over. The second makes its other delivery in a copy of the served directory, with ValueA in `rpm` in both files that name it, so that the copy has no error of its own and dumps (`dump` throws on a non-zero exit, and a widened producer against an unchanged reader is a `definition-mismatch`):

```ts
test("a baseline refused, and then made, is asked for again by the same press", async ({
  page,
  gui,
}) => {
  const root = posixOf(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  const compare = page.getByRole("button", { name: "Compare" });
  await page.getByRole("textbox", { name: "Baseline" }).fill("later.json");
  await compare.click();
  await expect(page.getByRole("alert")).toHaveText(
    startingWith(`the baseline '${root}/later.json' is unreadable: `),
  );

  // The file the refusal names now exists. Neither the field nor the project changed.
  dump(gui.directory, "demo.ddd.json", "later.json");
  await compare.click();
  await expect(page.getByRole("status").filter({ hasText: "replace the baseline" })).toHaveText(
    "This project can replace the baseline.",
  );
  await expect(page.getByRole("alert")).toHaveCount(0);
});
```

```ts
test("a baseline written over is asked for again by the same press, and the verdict follows", async ({
  page,
  gui,
}, testInfo) => {
  dump(gui.directory, "demo.ddd.json", "baseline.json");
  // Another delivery, made from a copy of the demo in which ValueA is in rpm, in the file that
  // produces it and in the one that reads it, so that the copy has no error of its own and dumps.
  const other = testInfo.outputPath("other");
  cpSync(gui.directory, other, { recursive: true });
  driftIn(other, SENSOR_HUB, "ValueA", "rpm");
  driftIn(other, CONTROLLER, "ValueA", "rpm");

  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  const compare = page.getByRole("button", { name: "Compare" });
  const verdict = page.getByRole("status").filter({ hasText: "replace the baseline" });
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await compare.click();
  await expect(verdict).toHaveText("This project can replace the baseline.");

  // The other delivery lands over the baseline's file. The open project is not touched, so no
  // revision comes to ask again: only the press can.
  dump(other, "demo.ddd.json", join(gui.directory, "baseline.json"));
  await compare.click();
  await expect(verdict).toHaveText("This project cannot replace the baseline.");
});
```

  Run both on the page as it is. Expected: both die at the verdict. The first finds no verdict at all (`element(s) not found`: the refusal stands), the second finds `This project can replace the baseline.` where it expects `cannot` (measured). Record the failing lines in the report.
  - **4b. The Vitest cases, red.** In `gui/src/lib/compare.test.ts`, the import from `./compare` becomes the line below, and these cases go at the end of the file:

```ts
import { type CompareRow, compareRouteReason, compareRows, nextAsk } from "./compare";
```

```ts
test("the first ask is numbered one, its baseline trimmed of the spaces round it", () => {
  expect(nextAsk(null, "  baseline.json ")).toEqual({ baseline: "baseline.json", number: 1 });
});

test("a baseline asked for again is a new ask, so that it is sent again", () => {
  const first = nextAsk(null, "baseline.json");
  const again = nextAsk(first, "baseline.json");
  expect(again.baseline).toBe(first.baseline);
  expect(again).not.toEqual(first);
});

test("a baseline typed with spaces round it is the baseline already asked for", () => {
  const first = nextAsk(null, "baseline.json");
  expect(nextAsk(first, "  baseline.json  ").baseline).toBe(first.baseline);
});

test("no ask repeats an earlier one, even when its baseline comes back", () => {
  const first = nextAsk(null, "a.json");
  const second = nextAsk(first, "b.json");
  const third = nextAsk(second, "a.json");
  expect(third.baseline).toBe(first.baseline);
  expect(new Set([first.number, second.number, third.number]).size).toBe(3);
});
```

  Run `npx vitest run src/lib/compare.test.ts`. Expected: the four new cases fail, `TypeError: nextAsk is not a function`, and the five old ones pass.
  - **4c. The rule,** at the end of `gui/src/lib/compare.ts`:

```ts
/**
 * A comparison the reader asked for: the baseline's path, trimmed, and the ask's number, counted
 * from the first ask the page made. `ComparePage` keys its query on this, so that every ask is a
 * query of its own (`nextAsk`).
 */
export interface Ask {
  readonly baseline: string;
  readonly number: number;
}

/**
 * The ask a press of Compare, or an Enter, makes after `previous`: `typed`, trimmed - a path with
 * a stray space at either end is not a path under the root the server would find - and numbered
 * one more than the ask before it, whatever either baseline is.
 *
 * A baseline asked for again is therefore a new query, sent again, and the server reads the file
 * as it now stands: a query keyed on the path alone was served from the answer the page held,
 * and a refusal for a file that did not exist then, or a verdict for a delivery written over
 * since, stood until the path - or the project - changed. A baseline that comes back after
 * another is no exception: no number repeats, so nothing is answered from an older ask.
 */
export function nextAsk(previous: Ask | null, typed: string): Ask {
  return { baseline: typed.trim(), number: (previous?.number ?? 0) + 1 };
}
```

  - **4d. The screen,** `gui/src/screens/ComparePage.tsx`: it holds the `Ask`, keys the query on it, and asks with `getCompare(asked.baseline)`. The whole change:

```diff
@@ -4,5 +4,5 @@
 import type { State } from "../api/types";
 import { CompareView } from "../components/CompareView";
-import { compareRows } from "../lib/compare";
+import { type Ask, compareRows, nextAsk } from "../lib/compare";
 import type { Route } from "../lib/route";
 
@@ -30,12 +30,12 @@
   // What the field shows, typed freely.
   const [baseline, setBaseline] = useState("");
-  // The baseline last asked for, or `null` before the reader has asked at all - what keys the
+  // The comparison last asked for, or `null` before the reader has asked at all - what keys the
   // query, so a later revision re-asks *this* baseline rather than whatever the field shows by
-  // then.
-  const [asked, setAsked] = useState<string | null>(null);
+  // then, and so that asking for it again is a query of its own (`nextAsk`).
+  const [asked, setAsked] = useState<Ask | null>(null);
   const [selected, setSelected] = useState<string | undefined>(undefined);
   const compare = useQuery({
     queryKey: ["compare", asked, revision],
-    queryFn: asked === null ? skipToken : () => getCompare(asked),
+    queryFn: asked === null ? skipToken : () => getCompare(asked.baseline),
   });
   const reply = compare.data ?? null;
@@ -57,9 +57,8 @@
       baseline={baseline}
       onBaseline={setBaseline}
-      // Trimmed here, once, rather than where the field is typed: `CompareView`'s own disabled
-      // check reads the same way (`baseline.trim() === ""`), so the two must agree on what
-      // counts as "nothing typed" - and a path with a stray leading or trailing space is not a
-      // path under the root the server would find.
-      onAsk={() => setAsked(baseline.trim())}
+      // Trimmed in `nextAsk`, once, rather than where the field is typed: `CompareView`'s own
+      // disabled check reads the same way (`baseline.trim() === ""`), so the two must agree on
+      // what counts as "nothing typed".
+      onAsk={() => setAsked((previous) => nextAsk(previous, baseline))}
       reply={reply}
       refusal={compare.isError ? compare.error.message : null}
```

  - **4e. Run them green.** `npm test`: the four new cases pass and every metric stays at 100 %. Then, after a build, the two journeys of 4a and every journey of this file, with `--repeat-each=10`.
  - **4f. Ablations of the fix,** in a scratch copy of the package: `nextAsk`'s `number: (previous?.number ?? 0) + 1` made `number: 1` must kill the cases "a baseline asked for again is a new ask, so that it is sent again" and "no ask repeats an earlier one, even when its baseline comes back", and both journeys of 4a at their verdicts; `typed.trim()` made `typed` must kill "the first ask is numbered one, its baseline trimmed of the spaces round it" and "a baseline typed with spaces round it is the baseline already asked for", and row 63's journey at its verdict (the server refuses a path with the spaces round it).
  - **4g. The CHANGELOG.** One entry under `## Unreleased`, in its own style (a bold lead, two spaces between sentences, no line over 95 columns), beside the other `ddd gui` entries:

```markdown
* **Compare asks again when it is asked again.**  On the Compare tab, pressing Compare, or
  Enter, for the baseline just asked for sent nothing: the answer already on the page stayed -
  a refusal for a file that did not exist yet, or "can replace" for a baseline written over
  since - until the path or the project changed.  Every press now asks the server, which reads
  the baseline file as it stands.
```

  - **4h. The focus, recorded and not fixed.** No code. Give the controller this text for the plan's *What was left open*, under "Found during execution":

```markdown
- **The Compare field loses focus when it asks** (P19c-10). `CompareView.tsx` disables the Baseline
  field while a comparison is awaited (`disabled={busy}`), so after an Enter the field is enabled
  again but not focused: `document.activeElement` is `BODY`, and a keyboard reader must click it to
  edit the path. The same happens, with the keystrokes after it dropped, when a revision lands while
  the reader types, and, since the re-ask fix, when an Enter is pressed again for the same path.
  Not fixed: `compare.spec.ts`'s busy journey asserts the field is disabled (ruling P19b-5), so a
  `readOnly` field or a refocus changes recorded behaviour, which is the maintainer's choice.
```
- [ ] **Step 5: The inventory.** The rows name these journeys in `compare.spec.ts`, each by its line and its title, with the task set to 13:
  - a baseline asked for with Enter: "a baseline typed is asked for with Enter, once, and a field with nothing in it asks for nothing";
  - a finding about the whole delivery, saying why it leads nowhere: "a finding about the whole delivery says why it leads nowhere";
  - the baseline's own findings, named as the baseline's and leading nowhere: "the baseline's own findings are named as the baseline's, and lead nowhere";
  - a finding's panel closed, 66a: "a finding's panel is closed by its Close button"; 66b: "a finding's panel closes by itself once a comparison no longer reports it, and stays closed if it returns".

  Add one row, Compare, owned by 13: "a baseline asked for again, its file made or written over since", naming "a baseline refused, and then made, is asked for again by the same press" and "a baseline written over is asked for again by the same press, and the verdict follows".
- [ ] **Step 6: The gates** (Global Constraints), every journey included, Vitest at 100 %, and the screenshots in Docker in compare mode (no page changed in what it shows: no reference may move). Commit: one for the rows' journeys (63 to 66b); one for the fix, with its Vitest cases, `nextAsk`, `ComparePage`'s change, its two journeys and the CHANGELOG entry.

### A.9 A component, rows 67 to 79

**Model:** sonnet, reviewed on sonnet. Each row is a state the component page or one of its two panels already draws, reached with Task 1's helpers; the one bug it fixes is a single slot in one component.

**Files:**
- Modify: `gui/e2e/declarations.spec.ts` (the page's rows and the add panel's), `gui/e2e/keys.spec.ts` (the variable panel's), and this plan's *The inventory*
- Modify, for the bug (P19c-10, Step 4): `gui/src/ui/ComboBox.tsx`, `gui/src/styles/ui.css`, and `CHANGELOG.md`

**Interfaces:**
- Consumes, from Task 1 (`gui/e2e/demo.ts`):
  - `held(page: Page, path: string | RegExp | ((url: URL) => boolean)): Promise<() => void>`, which holds the next request whose pathname matches, once, until the function it answers is called. Call that function in a `finally`;
  - `failing(page: Page, path: string | RegExp, how: "http" | "network", times?: number, method?: "GET" | "POST"): Promise<() => number>`, with `SERVER_FAILED` and `REFUSED` (`` `The change was refused: ${SERVER_FAILED}` ``);
  - `editJson(directory: string, file: string, change: (data: any) => void): void`, which reads a json file of a copy, applies `change`, and writes it whole.
- Consumes, as they stand: `drift(directory, variable?, unit?)`, `driftIn(directory, file, variable, unit)`, `CONTROLLER`, `SENSOR_HUB` and `PUMP` (`gui/e2e/demo.ts`); the fixtures `gui`, `vocabularyGui` and `copiedGui(example, change, options?)` (`gui/e2e/fixtures.ts`).

**What the pre-flight found:**
- **Every state is reached with a held or a failed request, or a changed copy,** and each journey below was drafted and run at `2bc00da` (ten runs each, about a second a run) and shown to fail under its ablation. None needed an invented condition.
- **`held` matches a pathname, which these reads need.** Each carries a query (`/api/file?path=…`, `/api/findings?file=…`, `/api/variable?name=…`, `/api/declarable?file=…`), and a glob such as `**/api/file` holds none of them (measured). A hold set before `goto` is safe: only a component's page asks for a file, only the page and the Findings tab for findings, only a panel for a variable, only the add panel for what may be declared.
- **Two sentences are drawn twice.** `Reading the file…` is the page's (row 67) and the add panel's (row 76), so row 76 asserts it inside the aside "Add a declaration". `Reading ValueB…` is the variable panel's while either `/api/variable` or `/api/units` is unanswered, one guard (`reply === undefined || units.data === undefined`): row 72 holds `/api/variable` and ablates the sentence, not the guard: without `reply === undefined ||` the page crashes whenever the units read lands before the variable's, a race that the panel a new declaration opens also runs (it killed row 78 in one of two runs).
- **Task 2 changes that guard** (P19c-5): a variable panel whose units read fails now says so, where it read for ever. Read `VariablePanel.tsx` again before ablating row 72. The sentence `Reading {name}…` stays, since a pending read still says it.
- **Row 73's branch is pinned twice.** `units.spec.ts`'s "a file saved half-edited leaves open the panel of a variable only it declares" reaches the same `if (answer.shown === "refusal") {` with a 409, so the branch's ablation kills both journeys (read from its assertion). Row 73's own assertion is a 500 on a first read, the alert reading `SERVER_FAILED`.
- **Rows 74, 75 and 78 need the vocabulary example.** The demo has no units file, so `outsideVocabulary` is false for every unit, and it declares no constants (`declarations.spec.ts`'s "a value block is declared with the shape it is given" says so in a comment).
- **Row 75 is two sentences,** the open list's lower case entry and the field's capitalised note, asserted in one journey with an ablation each. It carries the bug of Step 4, and is written there.
- **Row 79 is three states, three journeys** (P19c-8). Each asserts the sentence and the file, never whether the Apply or the Remove stays after the refusal: the panels differ on that, P19b-24 changes it for a stale refusal, and a non-stale refusal's differences are recorded for the maintainer, not ruled (P19c-6). Tasks 4 and 5 rewrite the stale branches beside these lines, so ablate each by its content, not its place.
- **Row 68 is one state with three breaks in one file.** `Session.read_file` checks no schema, so a file that parses but breaks it is answered with `error: null` and drawn as any other. That is the contrast with `declarations.spec.ts`'s "a component file that stops parsing is shown by its path and the parser's words, and nothing else", which shows an alert alone.
- **Rows 70, 73 and 77 fail a first read.** At a later revision the component page's reads (its findings, a variable's panel, the add panel, its file) drop what they drew; that is recorded for the maintainer, not fixed (P19c-5, P19c-10). So is a nameless component's three names: the canvas button `controller (not loaded)`, the Table tab's absolute path, and the page's `Unnamed component`.
- **Windows:** no sentence of this task carries a path.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **reading its file** (67) | `gui`; `held(page, "/api/file")` before `goto`. | Press "Controller". `main` has the text `Reading the file…` and nothing else, drawn by `ComponentPage.tsx`'s `if (content.isPending) return <p className="quiet">Reading the file…</p>;`. Released, the heading "Controller" (level 1) is drawn and the sentence is gone. | That `return <p …>` made `return null`: dies at the `main` text. |
| **a component file that parses but breaks its schema, drawn as the page draws any file** (68) | `copiedGui("demo", …)` whose change is `editJson` on Controller: `component.name` deleted, ValueB's `definition.name` deleted, ValueA's `datatype` made `"uint7"`. | Press the canvas button "controller (not loaded)" (`ModuleNode.tsx`'s `` `${data.name} (not loaded)` ``, named by the file's stem). The heading "Unnamed component" (level 1), from `ComponentPage.tsx`'s `?.component?.name ?? "Unnamed component"`; the grid "Declarations of Unnamed component", with ValueA's gridcell `uint7` and a `schema` chip in its row, and the rowheader `declaration 2` (``text("definition.name") ?? `declaration ${index + 1}` ``). Under "Findings in this component" three items, each led by `schema` (pydantic words their messages, so assert the chips and their count), and no `alert`. | `?? "Unnamed component"` made `?? ""`: dies at the heading. The `declaration N` fallback made `""`: dies at the rowheader. |
| **reading its findings** (69) | `copiedGui("demo", (directory) => { drift(directory); })`, so that Controller has one finding; `held(page, "/api/findings")` before `goto`. | Press "Controller". The table is drawn, and under the h2 "Findings in this component" the page says `Reading the findings…` (`{listed.isPending && <p className="quiet">Reading the findings…</p>}`); there is no `None.`, no finding link, and no `definition-mismatch` chip in ValueA's row. Released, the link `'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (unit: 'rpm' != '%')` and the chip arrive. | `listed.isPending &&` made `false &&`: dies at the sentence. `{listed.isSuccess && findings.length === 0 && <p className="quiet">None.</p>}` with `listed.isSuccess &&` removed: dies at the absence of `None.`, here and in row 70. |
| **its findings failing to load** (70) | `gui`; `failing(page, "/api/findings", "http")` before `goto`. | Press "Controller". The grid is drawn (the rowheader "ValueA") and one `alert` under the h2 reads `SERVER_FAILED` (`{listed.isError && <Banner tone="error">{listed.error.message}</Banner>}`); `None.` and `Reading the findings…` are absent; `failed()` is 1. | `listed.isError &&` made `false &&`: dies at the alert. |
| **no finding in it** (71) | `gui`. | Press "Controller". Under the h2 the page says `None.` (`exact: true`: the Unit column's lower case `none` does not match), drawn by `{listed.isSuccess && findings.length === 0 && <p className="quiet">None.</p>}`; there is no `ul.findings`. | `findings.length === 0` made `findings.length === 99`: dies at `None.`. |
| **a variable's panel reading the variable** (72) | `gui`; `held(page, "/api/variable")` before `goto`. | The worked journey below. The aside "ValueB" says `Reading ValueB…` (`VariablePanel.tsx`'s `<p className="quiet">Reading {name}…</p>`, in `if (reply === undefined \|\| units.data === undefined) {`) and not `Select a key to settle it on every declaration.`; released, the second arrives and the first goes. | That `Reading {name}…` made `Reading…`: dies at the sentence. Not the guard: without `reply === undefined \|\|` the page crashes whenever the units read lands first, so other journeys die on a race. |
| **a variable's panel failing to read the variable** (73) | `gui`; `failing(page, "/api/variable", "http")` before `goto`. | Press "Controller", then the row ValueB. The aside "ValueB" holds one `alert` reading `SERVER_FAILED`, drawn by `VariablePanel.tsx`'s `if (answer.shown === "refusal") {` (`<Banner tone="error">{answer.refusal}</Banner>`); it holds no keys `grid` (the loaded panel has one) and no `Reading ValueB…`; `failed()` is 1. | That `if (answer.shown === "refusal") {` made `if (false) {`: dies at the alert. It kills `units.spec.ts`'s "a file saved half-edited leaves open the panel of a variable only it declares" too (read from its assertion). |
| **a finding in a variable's panel, followed to what it names** (74) | `copiedGui("vocabulary", (directory) => { driftIn(directory, PUMP, "PumpSpeed", "RPM"); })`: PumpSpeed states a unit the units file does not list, before the server starts. | Press "Pump", then the row PumpSpeed. The aside "PumpSpeed" holds the link named by the whole message, `'RPM' is not a unit this project declares - did you mean 'rpm'?` (`exact: true`; `VariablePanelView.tsx`'s `<a className="button link" href={href}>{finding.message}</a>`), and the page's own findings list carries a second link of that name, so scope it to the aside. Press it: the address ends `/project?view=units&unit=RPM` and the aside "RPM" is visible. | `const href = namesThisVariable(finding, variable.name) ? null : routeHref(finding);` made `const href = null;`: dies at the link. `lib/findings.ts`'s `return { page: "project", view: "units", unit: route.name };` with `view: "types"`: dies at the address. In the scratch copy of the package, `finding_routes.py`'s `UNIT_CHECKS` without `"unknown-unit"`: dies at the link. |
| **a unit outside the project's vocabulary, said to be** (75) | `vocabularyGui`. | Step 4's journey. Press "Pump", then the button "Set the unit of PumpSpeed", and fill the combobox "Unit of PumpSpeed" with `rps`: its open list has one entry, `rps`, whose detail reads `not one of this project's units` (`lib/units.ts`'s `pickerSections`). Enter: under the field stands `Not one of this project's units` (`VariablePanel.tsx`'s `note`), which is also the field's accessible description; `kPa`, which the vocabulary lists, takes the note away. | The note's `? "Not one of this project's units"` made `? undefined`: dies at the note. `lib/units.ts`'s `outsideVocabulary(units, typed) ? "not one of this project's units" : ""` made `""`: dies at the entry's text. Step 4's change undone: dies at the description. |
| **the add panel reading what may be declared** (76) | `gui`; `held(page, "/api/declarable")` set once Controller's page is drawn. | Press "Add a declaration". The aside "Add a declaration" holds `Reading the file…` and no combobox "Name" (`DeclarePanel.tsx`'s `<p className="quiet">Reading the file…</p>` in `if (declarable.data === undefined) {`); scope it to the aside, since row 67's sentence has the same words. Released: `Choose a variable, or type a new name.`, and the comboboxes "Name" and "Scope". | That `<p className="quiet">Reading the file…</p>` made `Reading…`: dies at the sentence. Not the guard: `if (declarable.data === undefined) {` made `if (false) {` also kills rows 77, 78 and 79c. |
| **the add panel failing to read it** (77) | `gui`; `failing(page, "/api/declarable", "http")` before `goto`. | Press "Controller", then "Add a declaration". The aside holds one `alert` reading `SERVER_FAILED` (`DeclarePanel.tsx`'s `if (declarable.isError) {`, `<Banner tone="error">{declarable.error.message}</Banner>`), no combobox "Name" and no `Reading the file…`; `failed()` is 1. | `if (declarable.isError) {` made `if (false) {`: dies at the alert. |
| **a dimension picked from the project's constants** (78) | `vocabularyGui`, the one example that declares constants (`TREND_SAMPLES` in constants.ddd.json, `PRESSURE_CELLS` inline in pump.ddd.json). | Press "Pump", then "Add a declaration"; Name `Spare`, Enter; Kind `value_block`, Enter. "Show the choices for Dimension 1 of Spare" lists `PRESSURE_CELLS` and `TREND_SAMPLES` under "This project's constants" (`DimensionsField.tsx`, fed by `DeclarePanelView.tsx`'s `constants={reply.constants}`). Pick `TREND_SAMPLES`, state Volatile `false` and Datatype `uint8` as "a value block is declared with the shape it is given" does, and press "Apply to 1 file": the aside "Spare" opens, and `pump.ddd.json` contains `"dimensions": ["TREND_SAMPLES"]`. | `constants={reply.constants}` made `constants={[]}`: dies at the option. In the scratch copy of the package, `api.py`'s `constants=tuple(sorted(built.constants)),` made `constants=(),`: likewise. |
| **a key's Apply the server fails on** (79a) | `gui`; `failing(page, "/api/edit", "http")` before `goto`. | Press "Controller", then the button "Set the unit of ValueA"; fill the combobox "Unit of ValueA" with `rpm`, Enter; in the region "Settle the key" the button "Apply to 2 files" is enabled: press it. The region's `status` reads `REFUSED` (`VariablePanel.tsx`'s ``setRefused(`The change was refused: ${error.message}`)``), and both files are as they were. | That `setRefused(…)` made `setRefused(null)`: dies at the status. |
| **a removal the server fails on** (79b) | `gui`; `failing(page, "/api/edit", "http")` before `goto`. | Press "Controller", then the row ValueB; in the region "Remove the declaration" the button "Remove from Controller" is enabled: press it. That region's `status` reads `REFUSED` (``setRemovalRefused(`The change was refused: ${error.message}`)``), and Controller is as it was. | That `setRemovalRefused(…)` made `setRemovalRefused(null)`: dies at the status. |
| **a declaration the server fails on** (79c) | `gui`; `failing(page, "/api/edit", "http")` before `goto`. | Press "Controller", then "Add a declaration"; Name `ValueC`, Enter (`Reads ValueC as SensorHub declares it.`); "Apply to 1 file" is enabled: press it. The aside's `status` reads `REFUSED` (`DeclarePanel.tsx`'s `onError: (error) => setRefusal(refusalOf(error)),`), and Controller is as it was. | That `onError` made `onError: () => undefined`: dies at the status. |

**Titles:** 67 "a component's page says it is reading the file, until the file answers"; 68 "a component file that parses but breaks its schema is drawn as any other, with its findings"; 69 "a component's page says it is reading the findings, until they answer"; 70 "the findings of a component failing leave the server's own error under their heading, and the table drawn"; 71 "a component with no finding says so"; 72 "a variable's panel says it is reading the variable, until it answers"; 73 "a variable that fails to read leaves the server's own error in its panel"; 74 "a finding in a variable's panel leads to the unit it names"; 75 "a unit outside the project's vocabulary is said to be, in the list and under the field"; 76 "the add panel says it is reading the file, until what may be declared answers"; 77 "what may be declared failing leaves the server's own error in the add panel"; 78 "a dimension is picked from the project's constants, and written as the constant's name"; 79a "a key's Apply the server fails on is refused in its panel, and writes nothing"; 79b "a removal the server fails on is refused in its panel, and writes nothing"; 79c "a declaration the server fails on is refused in the add panel, and writes nothing".

- [ ] **Step 1: The worked journey,** in `gui/e2e/keys.spec.ts` (add `held` to its `./demo` import):

```ts
test("a variable's panel says it is reading the variable, until it answers", async ({
  page,
  gui,
}) => {
  const release = await held(page, "/api/variable");
  const panel = page.getByRole("complementary", { name: "ValueB" });
  try {
    await page.goto(gui.address);
    await page.getByRole("button", { name: "Controller", exact: true }).click();
    await page.getByRole("row", { name: /ValueB/ }).click();
    await expect(panel.getByText("Reading ValueB…", { exact: true })).toBeVisible();
    await expect(panel.getByText("Select a key to settle it on every declaration.")).toHaveCount(0);
  } finally {
    release();
  }
  await expect(panel.getByText("Select a key to settle it on every declaration.")).toBeVisible();
  await expect(panel.getByText("Reading ValueB…")).toHaveCount(0);
});
```

  The negative inside the `try` stands beside the positive drawn in the same render, so it waits on nothing. Read the panel's accessible name and the two sentences off the running page before asserting them.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then the ablation, in a scratch copy of the package: `VariablePanel.tsx`'s `<p className="quiet">Reading {name}…</p>` made `Reading…`. It must die at the first `toBeVisible`.
- [ ] **Step 3: The other rows,** all but row 75, each a journey of its own, run with `--repeat-each=10` and ablated as its row says.
  - **`declarations.spec.ts`:** rows 67 to 71, 76 to 78 and 79c. Add `editJson`, `held`, `PUMP` and `REFUSED` to its `./demo` import.
  - **`keys.spec.ts`:** rows 73, 74, 79a and 79b. Add `driftIn`, `failing`, `REFUSED` and `SERVER_FAILED` to its `./demo` import.
  - **Every hold is released in a `finally`,** and every journey whose `failing` is a GET read (70, 73, 77) ends with `expect(failed()).toBe(1)`.
  - **A negative stands only beside a positive** drawn in the same render, as in the rows above.
- [ ] **Step 4: The bug (P19c-10): a note drawn after its field is not the field's description.** Red first.
  1. **The journey, in `keys.spec.ts`,** is row 75's. Run it on the page as it is, after a build: it passes up to the note and dies at `toHaveAccessibleDescription`, received `""` (measured at `2bc00da`).

```ts
test("a unit outside the project's vocabulary is said to be, in the list and under the field", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("button", { name: "Pump", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of PumpSpeed" }).click();
  const panel = page.getByRole("complementary", { name: "PumpSpeed" });
  const picker = panel.getByRole("combobox", { name: "Unit of PumpSpeed" });
  const note = panel.getByText("Not one of this project's units", { exact: true });
  await expect(picker).toHaveValue("rpm");
  await expect(note).toHaveCount(0);

  // Typed: the list's own entry for the text says so, in lower case.
  await picker.fill("rps");
  await expect(page.getByRole("option", { name: /^rps/ })).toHaveText(
    /not one of this project's units/,
  );
  // Confirmed with Enter: the note stands under the field, and is the field's description.
  await picker.press("Enter");
  await expect(picker).toHaveValue("rps");
  await expect(note).toBeVisible();
  await expect(picker).toHaveAccessibleDescription("Not one of this project's units");

  // A unit the vocabulary lists: no note.
  await picker.fill("kPa");
  await picker.press("Enter");
  await expect(picker).toHaveValue("kPa");
  await expect(note).toHaveCount(0);
});
```

  2. **The cause.** React Aria ties a field to its description only if the description's element is there as the field first draws. Measured, a note already there at the first draw is the field's description, and again each time it comes back; a note first drawn after the field drew without one is on screen and not described. `ComboBox.tsx` draws it only `{note !== undefined && (…)}`.
  3. **The change, in `gui/src/ui/ComboBox.tsx`:** the slot is drawn always, and empty while there is no note. Replace

```tsx
      {note !== undefined && (
        <Text slot="description" className="combo-note">
          {note}
        </Text>
      )}
```

     with

```tsx
      {/* Always drawn, empty while there is no note (`.combo-note:empty` takes no room): React
          Aria ties a field to its description only if the description's element is there when
          the field first draws, so a note drawn later was on screen and not the field's
          description. */}
      <Text slot="description" className="combo-note">
        {note ?? ""}
      </Text>
```

  4. **And in `gui/src/styles/ui.css`,** after the `.combo-note` rule:

```css
/* Drawn without a note too (ComboBox.tsx), for the field's description; empty, it takes no room:
   the combo's column would add its gap and this margin under every field. */
.combo-note:empty {
  display: none;
}
```

     Measured without it, every combobox grows by 8 px (57 to 65 in the add panel, whose height grows by 16), since `.combo` is a flex column with a gap and the note has a margin of its own. With it, none does.
  5. **Green.** Run row 75's journey with `--repeat-each=10`, then every journey of `declarations.spec.ts` and `keys.spec.ts`. The ablation, in a scratch copy of the package: the change undone (the conditional back) dies at `toHaveAccessibleDescription`.
  6. **No Vitest case:** Vitest covers `src/api`, `src/lib` and `src/state` only, and the change decides nothing; it draws a slot that was conditional. Run `npm run ladle:build` and the screenshots in Docker in compare mode: no reference may move, since nothing on screen changes.
  7. **The CHANGELOG,** one entry under `## Unreleased`, in its style (a bold lead, two spaces between sentences, no line over 95 columns):

```
* **`ddd gui` reads a field's note with the field.**  The note under a field that offers
  choices - "Not one of this project's units" under a unit typed that the project's units file
  does not list - is now the field's description however late it appears.  It was tied to the
  field only if it was already there as the field first drew, so a note that came as the
  reader typed was on screen and not read with the field by a screen reader.  Nothing changes
  on screen.
```

  Any other bug a journey finds follows the rule in *Global Constraints*.
- [ ] **Step 4b: An oddity to reproduce first (P19c-21).** Pre-flight F, writing a journey of the Add a declaration panel, typed "ValueD" (and "FlagA") into its Name field and found "Diagnosis" there instead. Reproduce it on `gui`: Controller's page, "Add a declaration", type a name no variable has, and read the field and the panel back.
  - If the field keeps what was typed, record the probe in your report: no row.
  - If it does not, it is a bug. Follow the rule in *Global Constraints*: a journey red first, the fix within the panel or its combobox, and a CHANGELOG entry. If the fix reaches further, it is recorded for the maintainer instead.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason. Row 79 becomes three rows (a key's Apply; a removal; a declaration), each naming its own journey.
- [ ] **Step 6: The gates,** every journey included, and the screenshots in Docker in compare mode. Commit: one commit for the page's rows (67 to 71), one for the variable panel's (72 to 74, 79a, 79b), one for the add panel's (76 to 78, 79c), and one for the bug (row 75, `ComboBox.tsx`, `ui.css` and the CHANGELOG).

### A.10 Its values, rows 80 to 88

**Model:** sonnet, reviewed on sonnet. Each row is a state the values page already draws, reached with `openValues` and Task 1's helpers.

**Files:**
- Modify: `gui/e2e/values.spec.ts`, and this plan's *The inventory*

**Interfaces:**
- Consumes, from Task 1 (`gui/e2e/demo.ts`): `held(page: Page, path: string | RegExp | ((url: URL) => boolean)): Promise<() => void>`; `failing(page: Page, path: string | RegExp, how: "http" | "network", times?: number, method?: "GET" | "POST"): Promise<() => number>`; `SERVER_FAILED`; `REFUSED` (`` `The change was refused: ${SERVER_FAILED}` ``); `editJson(directory: string, file: string, change: (data: any) => void): void`.
- Consumes, as they stand: `openValues(page: Page, address: string, variable: string, component = "Controller"): Promise<void>`, `CONTROLLER` and `SENSOR_HUB` (`gui/e2e/demo.ts`); the fixtures `gui` and `copiedGui(example, change, options?)`.
- Defines, local to `values.spec.ts` and added in Step 3: `readOnlyGrid(page: Page, address: string): Promise<Locator>`, which rows 87a and 87b share.

**What the pre-flight found:**
- **Every state is reached with a held or a failed request, a changed copy, or the object itself,** and each journey below was drafted and run at `2bc00da` (ten runs each, about a second a run) and shown to fail under its ablation.
- **A grid is reached with `openValues`,** which presses the component, wheels the Shape cell's button into the box and presses it. Row 80 holds `/api/values` before it: nothing but the grid page asks for a grid. The objects are the demo's own: SensorHub's local ValueD states nothing, UserInterface's CurveB is stated once by the number 200 (SensorHub's ValueB, `init: 0`, is the other), and UserInterface's StateName names no init, so its Shape cell offers the button for a grid that says the producer wrote text. Controller's own StateName and SoftwareLabel state their text in their file, and show a plain `16` with no button there.
- **Rows 81 and 82 share the page's error branch,** which `values.spec.ts`'s "a shape deeper than a grid is shown, not offered, and says so with a way back" already pins for a 409. The branch's ablations kill all three journeys; row 82 alone dies under the server's sentence, in the scratch copy of the package. Row 81's own assertion is a 500, `SERVER_FAILED`.
- **Row 82 is a live deletion.** `placeholderData` keeps the old grid only while the next revision's read is pending; the 404 then replaces it. A bookmark naming a name no file declares reaches the same page with no watcher, and the journey does not need it.
- **Row 83 and the added row take their address from the page.** `ValuesPage` finds its `Back to <name>` by `state.files.find((entry) => entry.path === file)` and reads `Back to component` when no file of the project has that path. A typed address built from `gui.directory` could differ from the server's spelling by a character on Windows, so the journeys take `new URL(page.url())` and set what they need on it (the added row sets `file` to a path it means not to match).
- **Row 87 is two states** (P19c-8): an object nothing produces (`owner` is `null`), and one more than one place produces (an owner is named and `file` is `null`). Their evidence is the sentence, the disabled cells and the absent paste hint. A paste ignored is not asserted: nothing positive follows it, and with the guard removed (`ValuesGridView.tsx`'s `if (readOnly !== null || busy) return;` made `if (busy) return;`) a journey asserting that nothing is offered still passed (measured).
- **Row 88 asserts the sentence and the file, never whether the Apply stays** (P19c-6): the grid keeps its Apply after a refusal where the variable, removal and add panels withdraw theirs, and Task 5 may change it.
- **The cells of a grid that states nothing** carry the class `unstated` (`ValuesGridView.tsx`'s `className={reply.stated === "none" ? "unstated" : undefined}`; `ui.css` draws them in the quiet ink), and the cells of a grid stated once do not.
- **Windows:** only the added row's sentence carries a path, which it asserts as it typed it, with forward slashes, as "an address naming a file the project does not include says so, and shows nothing else" does.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **reading the values** (80) | `gui`; `held(page, "/api/values")` before `openValues(page, gui.address, "CurveA")`. | `main` has the text `Reading the values…` and nothing else: no heading, and no "Back to Controller" button (`ValuesPage.tsx`'s `if (values.isPending) return <p className="quiet">Reading the values…</p>;`). Released, the grid "Values of CurveA" is drawn and the sentence is gone. | That `return <p …>` made `return null`: dies at the `main` text. |
| **the values failing to load** (81) | `gui`; `failing(page, "/api/values", "http")` before `openValues(page, gui.address, "CurveA")`. | The heading "CurveA" (level 1), the button "Back to Controller" and one `alert` reading `SERVER_FAILED`, with no grid (`ValuesPage.tsx`'s `if (values.isError) {` branch: `<h1>{name}</h1>`, `Back to {backTo}`, `<Banner tone="error">{values.error.message}</Banner>`); `failed()` is 1. Press "Back to Controller": the grid "Declarations of Controller". | That `<Banner tone="error">{values.error.message}</Banner>` made `<></>`: dies at the alert. The `Back to {backTo}` button of that branch removed (the no-cell branch has its own): dies at its `toBeVisible`. Both also kill row 82, and the 409 journey named above (read from its assertions). |
| **an object no longer declared, its page saying so, with the way back** (82) | `gui`. | The worked journey below. The alert reads `the project declares no 'CurveA'`, the heading stays, the grid goes, and "Back to Controller" leads to Controller's grid without a CurveA row. | In the scratch copy of the package, `object_values.py`'s `raise ValueRefusalError("not-found", f"the project declares no '{name}'")` made `f"no '{name}' here"`: dies at the alert, alone. |
| **a declaration with no cell, opened by its address** (83) | `gui`. | Press "Controller", then take `new URL(page.url())`, set `variable` to `ValueA` and `view` to `values`, and `goto` it. The heading "ValueA" (level 1), the button "Back to Controller", and ``'ValueA' has no cell for a value to sit in`` (`ValuesPage.tsx`'s ``<p className="quiet">{`'${reply.name}' has no cell for a value to sit in`}</p>`` in `if (!drawable(reply) && reply.stated !== "text") {`); no grid and no `alert`. | That condition made `if (false) {`: dies at the sentence. |
| **an object initialised with text** (84) | `gui`. | `openValues(page, gui.address, "StateName", "UserInterface")`. The heading "StateName", the button "Back to UserInterface", and ``'StateName' is initialised with text, not with a grid`` (`ValuesGridView.tsx`'s ``{reply.stated === "text" ? (<p className="quiet">{`'${reply.name}' is initialised with text, not with a grid`}</p>) : (…)}``); no grid and no "Physical" button. | `{reply.stated === "text" ? (` made `{false ? (`: dies at the sentence. |
| **a grid that states nothing** (85) | `gui`. | `openValues(page, gui.address, "ValueD", "SensorHub")`: ValueD has `dimensions: [8]` and no `init`. The grid "Values of ValueD" with `Nothing is stated.` (`exact: true`; `{reply.stated === "none" && <p className="quiet">Nothing is stated.</p>}`), not `Stated once, for every cell.`; the cells `element 1` and `element 8` read `0` and carry the class `unstated`. | That line made `{false && …}`: dies at the sentence. |
| **a grid stated once for every cell** (86) | `gui`. | `openValues(page, gui.address, "CurveB", "UserInterface")`: the curve's `init` is the number 200. The grid "Values of CurveB" with `Stated once, for every cell.` (`exact: true`; `{reply.stated === "scalar" && <p className="quiet">Stated once, for every cell.</p>}`), not `Nothing is stated.`; the cells `element 1` and `element 6` read `100` (200 times the conversion's 0.5) and do not carry `unstated`. | That line made `{false && …}`: dies at the sentence. |
| **a grid nothing produces, read only** (87a) | `copiedGui("demo", …)` whose change is `editJson` on SensorHub, taking ValueB's declaration out: Controller's and UserInterface's reading of it have no producer. | Press "Controller", then "Show the values of ValueB" (its Shape cell reads `4`). The grid "Values of ValueB" says ``nothing produces '${reply.name}', so it has no values to set`` (here `nothing produces 'ValueB', so it has no values to set`, `exact: true`), drawn by `readOnlyNote` in `lib/objectValues.ts` and `ValuesGridView.tsx`'s `{readOnly !== null && <p className="quiet">{readOnly}</p>}`. Its cells `element 1` to `element 4` are disabled, there is no `Paste 1 row of 4 values from a spreadsheet to replace them all.`, and it also says `Nothing is stated.` | `lib/objectValues.ts`'s `if (reply.owner === null) return` made `if (false) return`: dies at the sentence. The cells' `disabled={reply.file === null \|\| busy}` made `disabled={busy}`: dies at `toBeDisabled`. `{readOnly === null && <p className="quiet values-paste">…}` made `{true && …}`: dies at the hint's absence. The last two also kill 87b. |
| **a grid more than one place produces, read only** (87b) | `copiedGui("demo", …)` whose change is `editJson` on Controller, making ValueB's `scope` `"output"`: SensorHub and Controller both produce it. | Press "Controller", then "Show the values of ValueB" (its Shape cell reads `4`). The grid "Values of ValueB" says ``'${reply.name}' is produced in more than one place, so there is no one file to set it in`` (here `'ValueB' is produced in more than one place, so there is no one file to set it in`, `exact: true`; `readOnlyNote`'s second sentence). Its cells `element 1` to `element 4` are disabled and there is no `Paste 1 row of 4 values from a spreadsheet to replace them all.` | `readOnlyNote`'s second `return` made `return null`: dies at the sentence. |
| **a cell's Apply the server fails on** (88) | `gui`; `failing(page, "/api/edit", "http")` before `openValues(page, gui.address, "CurveA")`. | Fill the textbox "element 3" with `7.5`; "Apply to 1 file" is enabled: press it. The region "Set the cell" holds one `status` reading `REFUSED` (`ValuesPage.tsx`'s `setFailed(refusalOf(error))`), Controller is as it was, the cell still reads `7.5`, and `failed()` is 1. | That `setFailed(refusalOf(error))` made `setFailed(null)`: dies at the status. |
| **a values address naming a file the project does not include** (added) | `gui`; a copy of Controller's file written beside the project description as `retired.ddd.json`, which no include reaches, as "an address naming a file the project does not include says so, and shows nothing else" does. | Press "Controller", then take `new URL(page.url())` and set `file` to the retired file's path as the page spells a file (`${gui.directory.replaceAll("\\", "/")}/retired.ddd.json`), `variable` to `CurveA` and `view` to `values`, and `goto` it. The grid "Values of CurveA" is drawn, since a value is found by its name, and the button reads `Back to component` (`ValuesPage.tsx`'s `const backTo = state.files.find((entry) => entry.path === file)?.name ?? "component";`). Press it: one `alert` reads `<that path> is not a description file of the open project`. | That `?? "component"` made `?? "back"`: dies at the button's `toBeVisible`. |

**Titles:** 80 "the values page says it is reading the values, until they answer"; 81 "the values failing to load leave the heading and the way back, with the server's own error"; 82 "an object no longer declared closes its grid, saying so, with the way back"; 83 "a declaration with no cell is opened by its address, and says so"; 84 "an object initialised with text says so, and draws no grid"; 85 "a grid that states nothing says so"; 86 "a grid stated once for every cell says so"; 87a "a grid nothing produces is read only, and says so"; 87b "a grid produced in more than one place is read only, and says so"; 88 "a cell's Apply the server fails on is refused under the cell, and writes nothing"; added "a values address naming a file the project does not include still draws the grid, and goes back to the component".

- [ ] **Step 1: The worked journey,** in `gui/e2e/values.spec.ts` (add `editJson` to its `./demo` import):

```ts
test("an object no longer declared closes its grid, saying so, with the way back", async ({
  page,
  gui,
}) => {
  await openValues(page, gui.address, "CurveA");
  await expect(page.getByRole("grid", { name: "Values of CurveA" })).toBeVisible();

  // Removed from outside, as an editor would: the watcher sees the write, and the next revision's
  // read of CurveA is answered `not-found`, which replaces the grid the old revision's read drew.
  editJson(gui.directory, CONTROLLER, (data) => {
    data.component.interface = data.component.interface.filter(
      (entry: { definition: { name: string } }) => entry.definition.name !== "CurveA",
    );
  });
  await expect(page.getByRole("alert")).toHaveText("the project declares no 'CurveA'");
  await expect(page.getByRole("heading", { name: "CurveA", level: 1 })).toBeVisible();
  await expect(page.getByRole("grid")).toHaveCount(0);

  const back = page.getByRole("button", { name: "Back to Controller" });
  await expect(back).toBeVisible();
  await back.click();
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "CurveA", exact: true })).toHaveCount(0);
});
```

  The journey waits on the alert, which the watcher's next revision brings within about a second; it never sleeps. Read the sentence off the running page, and Controller's rows off its grid.
- [ ] **Step 2: Run it** after a build, with `--repeat-each=10`. Then the ablation, in the scratch copy of the package: `src/ddd/object_values.py`'s `raise ValueRefusalError("not-found", f"the project declares no '{name}'")` made `f"no '{name}' here"`, with the journeys' server started from that copy. It must die at the alert's `toHaveText`.
- [ ] **Step 3: The other rows,** each a journey of its own in `values.spec.ts`, run with `--repeat-each=10` and ablated as its row says.
  - **Imports:** add `writeFileSync` to its `node:fs` import, `failing`, `held`, `REFUSED` and `SERVER_FAILED` to its `./demo` import, and `Page` to its `@playwright/test` type import.
  - **The helper rows 87a and 87b share,** local to the file, above them:

```ts
/** ValueB's grid, opened from Controller's table, for a read only grid to be read in. */
async function readOnlyGrid(page: Page, address: string): Promise<Locator> {
  await page.goto(address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of ValueB" }).click();
  const grid = page.getByRole("grid", { name: "Values of ValueB" });
  await expect(grid).toBeVisible();
  return grid;
}
```

  - **Row 87a's change:** `editJson(directory, SENSOR_HUB, (data) => { data.component.interface = data.component.interface.filter((entry: { definition: { name: string } }) => entry.definition.name !== "ValueB"); })`. **Row 87b's:** `editJson(directory, CONTROLLER, (data) => { data.component.interface.find((entry: { definition: { name: string } }) => entry.definition.name === "ValueB").scope = "output"; })`.
  - **Release every hold in a `finally`,** and end each `failing` journey with `expect(failed()).toBe(1)`. A negative stands only beside a positive drawn in the same render.
- [ ] **Step 4: Bugs.** A journey that finds a bug follows the rule in *Global Constraints*. The pre-flight met none in these rows. `ValuesGridView.tsx`'s comment on the paste guard is corrected in Task 7, since that task's journey pins the guard.
- [ ] **Step 5: The inventory.** Each row names its journey, or its reason. Row 87 becomes two rows (nothing produces it; more than one place does), and the added row is appended to the Values rows, owned by this task.
- [ ] **Step 6: The gates,** every journey included. Commit: one commit for the loading, failing and gone rows (80 to 82), one for the grid's states (83 to 87b and the added row), and one for the Apply the server fails on (88).

## B. For a later part: P19b-13 and P19b-24

The maintainer left P19b-13 and P19b-24 out of this part on 2026-10-21. The retired plan had designed both, and its pre-flight ran each case red on the page at `2bc00da`, then green with the change in a scratch copy. That work is kept here for whoever takes them up. In a scratch copy holding the fixes as well, the whole suite passed (187 journeys).

### B.1 P19b-13: a type's key left unchanged changes nothing

**Model:** sonnet, reviewed on sonnet. One Python function gains one guard, under a rule the variable panel already settles by, so it needs no judgement beyond the tests.

**Files:**
- Modify:
  - `src/ddd/type_plans.py`, `tests/test_type_plans.py` and `tests/test_gui_api.py`;
  - `gui/e2e/types.spec.ts`;
  - `CHANGELOG.md`.

**Interfaces:**
- Consumes: `same_value(key: str, raw: str) -> str` (`src/ddd/value_identity.py`); the fixture `structuresGui`.

**What the pre-flight found:**
- **Measured on a running `ddd gui`** over a copy of examples/structures at `2bc00da`. `GET /api/type-plan?action=set&name=Temperature_t&key=<k>&raw=<what the panel sends>` answers one change and one `set` operation for every key:

  | Key | `raw` sent | `hunks` |
  | --- | --- | --- |
  | datatype | `"uint16"` | `[]` |
  | unit | `"degC"` | `[]` |
  | conversion | `{"factor": 0.1, "offset": -40}` | the four-line object laid out again on one line |
  | limits | `{ "min": -40, "max": 150 }`, rebuilt from the two fields by `limitsRaw` | the four-line object laid out again on one line |

- **The cause.** `set_key` plans a `set` whenever `raw` is not `None`, and never compares it with what the key states.
  - A variable's settle does compare: `settled_at` (`src/ddd/lsp/edits.py`) returns `None` where `_already(key, stated, raw)` holds. `_already` compares by `ddd.value_identity.same_value`, by what the values mean.
  - The page reads the one change with no hunk as a change: `TypePanelView.tsx`'s `consequence(preview.changes)` says "Changes 1 file: types.ddd.json", and its `preview.changes.length > 0` draws "Show changes" and "Apply to 1 file".
- **The server half alone fixes all four keys.** It stays within `set_key`.
  - With `changes: []`, the panel already says "Nothing to change" (`lib/units.ts`'s `consequence`) and draws no Apply, as the variable panel does (keys.spec.ts's "Nothing to change").
  - **The view half was considered and not taken.** It would make a change with no hunk count as none, in `lib/units.ts`. It fixes the datatype and the unit alone, leaves the re-layout, and adds a second rule beside the server's.
- **`same_value` agrees on every pair the panel can send.** Probed through the venv: the file's four-line conversion against the one-line text; `{"factor": …}` against `{"kind": "linear", …}`; `-40` against `-40.0`. "K", and a maximum of 120, stay different.
- **Nothing else changes.** Every existing type-plan test sets a value that differs. With the change:
  - `test_gui_api.py`, `test_type_plans.py`, `test_gui_hostile.py` and `test_gui_queries.py` answered `1334 passed` (`--no-cov`, a scratch copy);
  - ruff, ruff format and mypy were clean on `type_plans.py`;
  - every journey passed in a scratch copy of the package with Tasks 2 to 5 (187 passed).

  The two journeys below were measured as one journey over the four keys. It failed on today's server at its first key, the datatype, and passed with the change five times out of five. The conversion's and the limits' red comes from the same plan, the measured re-layout.
- **Two existing journeys grow stronger.** Before, the unchanged selection already showed "Changes 1 file" and "Show changes":
  - "a type's unit settled from its panel is written, then undone" could meet its "Changes 1 file: types.ddd.json" before K's plan came;
  - "a type's unit stated as nothing leaves its entry" could press a "Show changes" drawn before the pick.

  Now only the change's own plan draws either.
- **`set_entry` (`src/ddd/shared_plans.py`) still plans an equal value.** Its panels ask only for a draft that differs from the entry's own text, so no reader meets it. Recorded for the maintainer (P19c-10).

**The rows:** none. This task is P19b-13's fix, with the journeys below.

- [ ] **Step 1: The red cases.** In `tests/test_type_plans.py`, class `TestSettingAKey`, before `test_a_key_the_kind_does_not_have_is_refused`:

```python
    @pytest.mark.parametrize(
        ("key", "raw"),
        [
            # As the Types panel asks for each key selected and left as it is: the value its row
            # reads (`TypeReply.keys[].values[0].raw`), a range rebuilt from its two fields.
            ("datatype", '"uint16"'),
            ("unit", '"degC"'),
            ("conversion", '{"factor": 0.1, "offset": -40}'),
            ("limits", '{ "min": -40, "max": 150 }'),
        ],
    )
    def test_a_value_the_key_already_states_is_an_empty_plan(self, built, cache, key, raw) -> None:
        assert set_key(built, "Temperature_t", key, raw, cache) == TypePlan(())

    @pytest.mark.parametrize(
        ("key", "raw"),
        [
            ("conversion", '{"kind": "linear", "factor": 0.1, "offset": -40.0}'),
            ("limits", '{"min": -40.0, "max": 150.0}'),
        ],
    )
    def test_a_value_meaning_the_same_however_spelled_is_an_empty_plan(
        self, built, cache, key, raw
    ) -> None:
        assert set_key(built, "Temperature_t", key, raw, cache) == TypePlan(())

    @pytest.mark.parametrize(
        ("key", "raw"),
        [
            ("datatype", '"sint16"'),
            ("unit", '"K"'),
            ("conversion", '{"factor": 0.2, "offset": -40}'),
            ("limits", '{"min": -40, "max": 120}'),
        ],
    )
    def test_a_value_meaning_something_else_still_plans_its_edit(
        self, built, cache, key, raw
    ) -> None:
        # Review Focus 3: "Nothing to change" never swallows a real change.
        assert set_key(built, "Temperature_t", key, raw, cache) != TypePlan(())
```

  The last four cases are controls: they pass before the change and after it. If a value the change compares as equal ever meant something else, they would fail.

  In `tests/test_gui_api.py`, class `TestTheTypesTab`, after `test_setting_a_unit_is_previewed_then_written`:

```python
    @pytest.mark.parametrize(
        ("key", "raw"),
        [
            ("datatype", '"uint16"'),
            ("unit", '"degC"'),
            ("conversion", '{"factor": 0.1, "offset": -40}'),
            ("limits", '{ "min": -40, "max": 150 }'),
        ],
    )
    def test_a_key_set_to_what_it_already_states_plans_no_change(
        self, structures, key, raw
    ) -> None:
        """What the Types panel asks for a key selected and left as it is: no file to change, so
        the panel says "Nothing to change" and offers no Apply - not a file with no line changed
        (the datatype, the unit), nor a conversion or a range laid out again on one line."""
        api, root = structures
        before = contents(root)
        reply = get(api, "/api/type-plan", action="set", name="Temperature_t", key=key, raw=raw)
        assert (reply.status, reply.body["changes"]) == (200, [])
        assert contents(root) == before
```

  Run `.venv/bin/python -m pytest tests/test_type_plans.py tests/test_gui_api.py --no-cov -k "already_states or however_spelled or what_it_already"`. Expected: 10 failed. Measured in a scratch copy: 6 of 6, and 4 of 4.
- [ ] **Step 2: The change,** in `src/ddd/type_plans.py`.
  - Import `same_value` (`from ddd.value_identity import same_value`).
  - In `set_key`, after the guard answering an empty plan for a key already left out:

```python
    if raw is None and document.value_at(f"{site.pointer}.{key}") is None:
        return TypePlan(())
    stated = document.raw_at(f"{site.pointer}.{key}")
    if raw is not None and stated is not None and same_value(key, stated) == same_value(key, raw):
        return TypePlan(())
```

  - Add one paragraph to its docstring:

    > A value the key already states, by what it means (:func:`ddd.value_identity.same_value`, the rule :func:`ddd.lsp.edits.settled_at` settles a variable's key by), answers no edit either: setting it would change no line, or only lay the value out again, and a reader who has only selected the row must be told there is nothing to change. ``raw`` is trusted to be json: the api reads it as json text (``SetTypeKey.raw``) before asking, as :func:`ddd.shared_plans.set_entry`'s callers do.

  Run the cases of Step 1. Expected: all pass. Then the whole Python gate.
- [ ] **Step 3: The journeys, red first,** in `gui/e2e/types.spec.ts`, two, one per half of the fault:

```ts
test("a type's datatype or unit selected and left as it is changes nothing, and offers no Apply", async ({
  page,
  structuresGui,
}) => {
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types", exact: true }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Temperature_t" });

  // Each row's own value, picked by nothing: the plan once came back with a file and no line
  // changed in it, read as "Changes 1 file" with an Apply (P19b-13).
  for (const [key, value] of [
    ["Datatype", "uint16"],
    ["Unit", "degC"],
  ] as const) {
    await panel.getByRole("row", { name: key, exact: true }).click();
    await expect(panel.getByRole("combobox", { name: `${key} of Temperature_t` })).toHaveValue(
      value,
    );
    await expect(panel.getByText("Nothing to change", { exact: true })).toBeVisible();
    await expect(panel.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Show changes" })).toHaveCount(0);
  }
});
```

  The second, "a type's conversion or limits selected and left as it is changes nothing, and is not laid out again", is the same journey over `["Conversion", "linear ×0.1 -40"]` and `["Limits", "-40 … 150"]`. Its comment says the plan once laid the four-line object out again on one line.
  - Read each field's value off the running page before asserting it.
  - Run both on today's page (built, with today's server). Each must fail at its first key's "Nothing to change". Measured: the panel reads "Changes 1 file: types.ddd.json" over "Show changes" and "Apply to 1 file".
- [ ] **Step 4: Run them** with the change, after a build, with `--repeat-each=10` (measured: 5 of 5 in a scratch copy). Then the ablation, in a scratch `git worktree` of the Python with the page built into it: `set_key`'s `same_value` guard removed. Both journeys must die at "Nothing to change", and the ten cases of Step 1 must fail.
- [ ] **Step 5: Bugs.** This task is P19b-13's fix, red first. Its CHANGELOG entry:

  > **A type's key selected and left as it is changes nothing.** On the Types tab, selecting a type's datatype, unit, conversion or limits without changing it offered "Changes 1 file" and "Apply to 1 file". For the datatype and the unit that was a change with no line changed; for the conversion and the limits, one that laid the value out again on a single line. It now says "Nothing to change" and offers no Apply, as a variable's key already did. A value spelled differently that means the same, such as a conversion naming its kind or a range in decimals, changes nothing either.

  Any other bug a journey finds follows the rule in *Global Constraints*.
- [ ] **Step 6: The inventory.** No row is this task's. *Rulings taken* records P19b-13 as fixed, and records `set_entry` as left (P19c-10).
- [ ] **Step 7: The gates,** every journey included. Commit in two:
  1. the cases and the change;
  2. the journeys and the CHANGELOG.

### B.2 P19b-24, the sweep

**Model:** sonnet, reviewed on sonnet. A mechanical change in thirteen screens, held by the gates as they stand, and by one grep.

**Files:**
- Modify:
  - `gui/src/lib/refusals.ts` and `gui/src/lib/refusals.test.ts`;
  - `gui/src/screens/UnitPanel.tsx`, `TypePanel.tsx`, `ConstantPanel.tsx`, `SectionPanel.tsx`, `RasterPanel.tsx`, `UnitsPage.tsx`, `ValuesPage.tsx`, `FindingsPage.tsx`, `UndoStrip.tsx` and `VariablePanel.tsx`, whose inline stale checks this task replaces;
  - `gui/src/screens/FilesPage.tsx`, `SharedPage.tsx` and `DeclarePanel.tsx`, which import `refusalOf` from `./UnitPanel` today.

**Interfaces:**
- Consumes: `isStale(error: Error): boolean` (`gui/src/lib/refusals.ts`).
- Produces: `refusalOf(error: Error): string`, moved into `gui/src/lib/refusals.ts`. Task 5 uses it in `DeclarePanel` and `SharedAdd`.

**What the pre-flight found:**
- **The stale decision is written inline 13 times in 10 files:** `error instanceof ApiError && error.code === "stale"`. Read at `2bc00da`:
  - `UnitPanel.tsx` twice: its exported `refusalOf`, and its mutation's `onError`;
  - `TypePanel.tsx` twice: an exported copy of `UnitPanel`'s `refusalOf` that nothing imports, and its `onError`;
  - `VariablePanel.tsx` twice: the settle's `onError` and the removal's;
  - once each in `ConstantPanel.tsx`, `SectionPanel.tsx`, `RasterPanel.tsx`, `UnitsPage.tsx` (the adopt), `ValuesPage.tsx` and `FindingsPage.tsx`, each in its `onError`;
  - `UndoStrip.tsx`'s own `refusalOf`, which keeps its own words.

  `lib/refusals.ts` already exports `isStale`, which only `FilesPage.tsx` uses.
- **`refusalOf` is a decision about words** (stale, or the server's reason), and eight screens import it from a screen file. It moves into `lib/refusals.ts`, under Vitest. `TypePanel`'s copy goes.
- **The words do not change.** `VariablePanel` keeps its `STALE` ("The panel now shows…"), `FindingsPage` keeps its own ("The tab now shows the findings…"), and the undo strip keeps its own (the server's sentence, then "Nothing was put back; …").
- **Measured** in a scratch copy at `2bc00da`:
  - after the sweep, `grep 'code === "stale"'` finds `isStale` alone;
  - `tsc` and biome are clean;
  - Vitest runs 953 cases at 100 %.
- **No reader sees a difference,** so no journey is added and no CHANGELOG entry: Task 5's entry covers P19b-24.

**The rows:** none. This task is a refactor, with no row.

- [ ] **Step 1: `refusalOf`'s cases, red first,** in `gui/src/lib/refusals.test.ts`, before "a stale Apply's sentence is shown over any other while its revision stands". Add `refusalOf` to its import:

```ts
test("an Apply refused as stale says so in the panels' own words, and nothing of the server's", () => {
  expect(refusalOf(new ApiError(409, "stale", "a.ddd.json changed on disk"))).toBe(
    "A file changed on disk, so nothing was written. The page now shows the files as they are.",
  );
});

test("an Apply refused for any other reason says so in the server's own words", () => {
  expect(refusalOf(new ApiError(409, "invalid", "'K' is not a unit"))).toBe(
    "The change was refused: 'K' is not a unit",
  );
  expect(refusalOf(new ServerUnreachable(new Error("refused")))).toBe(
    "The change was refused: ddd gui is not answering",
  );
});
```

  Run them. Expected: they fail, since `refusalOf` is not exported from `./refusals`.
- [ ] **Step 2: `refusalOf` moved,** in `gui/src/lib/refusals.ts`, after `isStale`:

```ts
/** What a panel says when an Apply it posted was refused: a stale refusal in the words every panel
 * says it in but the variable's, the Findings tab's and the undo strip's, which keep their own, or
 * the server's own reason. */
export function refusalOf(error: Error): string {
  return isStale(error)
    ? "A file changed on disk, so nothing was written. The page now shows the files as they are."
    : `The change was refused: ${error.message}`;
}
```

  - Delete `UnitPanel.tsx`'s `refusalOf` and `TypePanel.tsx`'s copy.
  - Every importer of `./UnitPanel`'s `refusalOf` (`ConstantPanel`, `SectionPanel`, `RasterPanel`, `UnitsPage`, `ValuesPage`, `FilesPage`, `SharedPage` and `DeclarePanel`) imports it from `../lib/refusals` instead. `UnitsPage` keeps `UnitPanel` and `usePlan` from `./UnitPanel`.
- [ ] **Step 3: The sweep.**
  - Each remaining `error instanceof ApiError && error.code === "stale"` becomes `isStale(error)`, with `isStale` added to that file's `../lib/refusals` import. That covers the `onError` of the unit, type, constant, section and raster panels, the adopt, the values grid and the Findings fix, both of the variable panel's, and `UndoStrip`'s own `refusalOf`.
  - `ApiError` leaves the imports where nothing else reads it: `UnitsPage`, `ValuesPage`, `FindingsPage` and `UndoStrip`. The `not-found` checks keep it elsewhere.
  - The check: `grep -rn 'code === "stale"' gui/src` finds `lib/refusals.ts`'s `isStale` alone.
- [ ] **Step 4: Run it.**
  - `npm run lint && npm run typecheck && npm test`: every case passes, at 100 % on all four metrics.
  - The out-of-date journeys pass unchanged, after a build: `declarations.spec.ts`, `values.spec.ts`, `keys.spec.ts`, `types.spec.ts`, `shared.spec.ts`, `files.spec.ts`, `findings.spec.ts`, `project-units.spec.ts` and `skeleton.spec.ts`.
  - **Ablation:** `isStale` answering `false`, in a scratch copy of the package. `keys.spec.ts`'s "a change refused as stale can be applied again once the analysis has caught up" must die at its sentence (the panel words "The change was refused: …"), which shows the screens now read the one function.
- [ ] **Step 5: Bugs.** None is this task's. Any a journey finds follows the rule in *Global Constraints*.
- [ ] **Step 6: The inventory.** No row is this task's. *Rulings taken* records the sweep under P19b-24.
- [ ] **Step 7: The gates.** One commit: "read every stale refusal through isStale, and refusalOf from the lib".

### B.3 P19b-24, the rule

**Model:** opus, reviewed on opus. One rule across fourteen surfaces, each drawn its own way. A slip leaves an Apply the server refuses again, or a refusal that never goes.

**Files:**
- Modify:
  - `gui/src/lib/refusals.ts` and `gui/src/lib/refusals.test.ts`;
  - `gui/src/screens/UnitPanel.tsx`, `ConstantPanel.tsx`, `SectionPanel.tsx`, `RasterPanel.tsx`, `TypePanel.tsx`, `VariablePanel.tsx` (its removal), `UnitsPage.tsx`, `FilesPage.tsx`, `ValuesPage.tsx`, `DeclarePanel.tsx` and `SharedPage.tsx` (`SharedAdd`);
  - `gui/src/components/FileActionsView.tsx` (one comment);
  - `gui/e2e/declarations.spec.ts`, `values.spec.ts`, `files.spec.ts`, `shared.spec.ts` and `project-units.spec.ts`;
  - `CHANGELOG.md`, and this plan's *The inventory*.

**Interfaces:**
- Consumes:
  - `isStale` and `refusalOf` (Task 4);
  - `shownRefusal` and `Refused` (`gui/src/lib/refusals.ts`);
  - `moveStamp` and `held` (Task 1);
  - `writeUnseen`, `driftMaxUnseen`, `openValues`, `CONTROLLER` and `UNITS` (`gui/e2e/demo.ts`).
- Produces: `offerShown<P>(plan: P | null, stale: Refused | null, refused: string | null, asked: string | null, revision: number | undefined): { plan: P | null; refusal: string | null }`, in `gui/src/lib/refusals.ts`. It replaces `refusalShown`, whose one caller was `FilesPage`.

**What the pre-flight found:**
- **Fourteen surfaces hold a stale refusal, not the three the record named.** Read at `2bc00da`:

  | Surface | Hold today | Its Apply while the refusal stands |
  | --- | --- | --- |
  | Add a declaration (`DeclarePanel`) | until the next edit, and past a new revision until one | hidden (`DeclarePanelView`'s `props.refusal === null && …`) |
  | Shared files' add form (`SharedAdd`) | until the next edit, and past a new revision until one | hidden (`SharedAddView`'s `props.refusal === null && …`) |
  | Files: New file, Add, Remove (`useFilesApply`) | the next revision | **kept** (`FileActionsView`'s `Preview` draws `preview.apply` under the refusal) |
  | Units: the adopt banner and its preview | the next revision | **kept** (`AdoptBannerView`'s Adopt; `AdoptPanelView`'s Adopt shows no refusal at all) |
  | A unit's panel | the next revision, per action | **kept** (`UnitPanelView`'s `Outcome` draws its button whenever there is a plan) |
  | A constant's, a section's and a raster's panels | the next revision, per action | **kept** (each view's own `Outcome`, as the unit's) |
  | The values grid | the next revision | **kept** (`ValuesGridView`'s `plan !== null && plan.changes.length > 0 && (`) |
  | A type's panel | the next revision, per write path | hidden (`TypePanelView`'s `refusal === null && pending && …`) |
  | A variable's panel: settle and removal | the next revision | hidden (`VariablePanelView`'s two `refusal === null` gates) |
  | Findings: a fix | the next revision, per finding | hidden (`FindingPanelView`'s `refusal === null && fix.changes.length > 0 && (`) |
  | The undo strip | the next revision, for any refusal | hidden (the refusal is the whole strip) |

- **The rule, `offerShown`, withholds the plan while a stale refusal stands.**
  - Every view draws its changes and its Apply from its plan alone, so the views are unchanged, and the seven that keep their Apply hide it.
  - A refusal for another reason leaves the plan as it is. It still differs from panel to panel, and that is recorded for the maintainer, not ruled (P19c-6).
- **A latent fault goes with it.** The unit, constant, section and raster offers, and the variable panel's removal, chose with a ternary that did not fall through. Once a stale refusal's revision had passed, they showed nothing, even where the plan's own fetch was refused, until the next Apply. `offerShown` falls through, as `refusalShown` did.
- **P19c-6 decides three points.**
  - **`VariablePanel`'s settle keeps its own expression,** written with `isStale` (Task 4), so that its table's marks stay. `VariableKeysTable` reads the preview, and a withheld plan would take its marks away. It is one rule, written twice.
  - **The adopt's preview beside the table is drawn from the withheld plan.** It is withdrawn while the refusal stands, and comes back by itself once the page catches up, if still asked for.
  - **The non-stale refusal's differences** are recorded, not ruled.
- **`FindingsPage` and `UndoStrip` already hold and hide,** and their offers are not a plan (a fix chooser; a whole-strip refusal). They change only in Task 4.
- **`DeclarePanel`'s comment,** "unlike the other panels, this one always closes on success, so there is no later revision for a stale refusal to wait on", is wrong: a refused Apply does not close it. It is rewritten.
- **The values grid's paste keeps its own sentence first,** as today. A block the parser refused is about what the reader just pasted, not an Apply.
- **Measured** in a scratch copy at `2bc00da`, with Tasks 2 to 4 under it:
  - **Seven drafts were measured:** row 48's, J1's, J2's, J3's, J6's and J7's, and one loop over the constant, the section and the raster, which J4 and J5 below split.
  - **Before the rule,** all seven failed, each at its new assertion. **With it,** all seven passed; J1 and row 48's three times out of three.
  - Vitest ran 954 cases at 100 %.
  - **Row 48's journey, as written below,** was measured red without the rule (at the refusal after Value "5") and green with it, three times out of three.
  - **J1's first draft** typed another name and met the combobox's own pick ("Diagnosis"). The measured J1 clears the name and types it back.
  - **J4's line in `shared.spec.ts:464`** was never run as such. Its red is the measured loop's constant iteration, through the same `Outcome`.
  - **With Tasks 2 to 5 in place,** every journey of the suite passed in that copy, the drafts included: 187 passed in 4.6 minutes. So no journey of 19b's breaks under the rule.

**The rows,** as read at `2bc00da`. Every quoted string is a guide: read the whole sentence off the running page before asserting it.

| Row | Setup | Steps and what the reader sees | Ablation |
| --- | --- | --- | --- |
| **48. Shared files: the add form's Apply refused as out of date** | `vocabularyGui`; the add form for a constant opened at `/project?view=shared&kind=constant&name=SPARE_SLOTS` (`openForm`); Value "4"; "Apply to 1 file" enabled | `constants.ddd.json` rewritten unseen (`writeUnseen`: "sample slots" made "sample cells"), then Apply. A `status` reads "A file changed on disk, so nothing was written. The page now shows the files as they are.", and no Apply is drawn. Value "5" is typed: the refusal stands, still with no Apply. `moveStamp` on the file: the refusal goes by itself, Apply declares SPARE_SLOTS, and its panel opens. | `SharedPage.tsx`'s Value handler clearing `stale` too (as it clears `refusal`) dies at the refusal after the edit; `stale` set with no revision (`shownRefusal` bypassed) dies at its going |

- [ ] **Step 1: The worked case, red first,** in `gui/src/lib/refusals.test.ts`. Replace the five `refusalShown` cases ("a stale Apply's sentence is shown over any other while its revision stands" to "nothing refused shows nothing") with these, and `refusalShown` with `offerShown` in its import:

```ts
describe("what an Apply's offer draws", () => {
  /** A plan the panel holds, and a stale refusal made at revision 7. */
  const PLAN = { revision: 7, changes: ["units.ddd.json"] };
  const STALE = { text: "A file changed on disk, so nothing was written.", revision: 7 };

  test("a stale refusal, while its revision stands, is drawn alone: no plan, so no Apply", () => {
    expect(offerShown(PLAN, STALE, null, null, 7)).toEqual({ plan: null, refusal: STALE.text });
    // Over another Apply's refusal and the plan's own too. No panel sets two Apply refusals at
    // once - setting one clears the other - but the order is the function's own.
    expect(offerShown(PLAN, STALE, "The change was refused: no", "asked", 7)).toEqual({
      plan: null,
      refusal: STALE.text,
    });
  });

  test("once the page has caught up, the plan is offered again, under why it was refused if it was", () => {
    expect(offerShown(PLAN, STALE, null, null, 8)).toEqual({ plan: PLAN, refusal: null });
    expect(offerShown(PLAN, STALE, null, "refused when asked", 8)).toEqual({
      plan: PLAN,
      refusal: "refused when asked",
    });
  });

  test("a stale refusal from before the page knew a revision holds until one arrives", () => {
    const early = { text: STALE.text, revision: undefined };
    expect(offerShown(PLAN, early, null, null, undefined)).toEqual({
      plan: null,
      refusal: STALE.text,
    });
    expect(offerShown(PLAN, early, null, null, 7)).toEqual({ plan: PLAN, refusal: null });
  });

  test("an Apply refused for another reason is drawn over the plan's own refusal, the plan left as it is", () => {
    expect(offerShown(PLAN, null, "The change was refused: no", "asked", 7)).toEqual({
      plan: PLAN,
      refusal: "The change was refused: no",
    });
  });

  test("a plan refused when asked is drawn in the server's own words", () => {
    expect(offerShown(null, null, null, "units.ddd.json is there already", 7)).toEqual({
      plan: null,
      refusal: "units.ddd.json is there already",
    });
  });

  test("nothing refused, the plan is offered, or nothing while none has come", () => {
    expect(offerShown(PLAN, null, null, null, 7)).toEqual({ plan: PLAN, refusal: null });
    expect(offerShown(null, null, null, null, 7)).toEqual({ plan: null, refusal: null });
  });
});
```

  Run them. Expected: they fail, since `offerShown` is not exported.
- [ ] **Step 2: `offerShown`,** in `gui/src/lib/refusals.ts`, in `refusalShown`'s place:

```ts
/**
 * What an Apply's offer draws, one rule for every panel (P19b-24): while a stale refusal's
 * revision stands, that refusal alone - no plan, so neither its changes nor its Apply, since an
 * Apply then would send the very fingerprints just refused; the next revision ends it, the page
 * having caught up with the file. Otherwise the plan, under the Apply's refusal for another
 * reason, else under why the plan itself was refused when asked for (`planShown`'s `refusal`,
 * `lib/typing.ts`).
 *
 * Every panel draws its changes and its Apply from its plan alone, so withholding the plan is
 * what hides them, and no view decides it. A refusal for another reason leaves the plan as it is:
 * what a panel does with its Apply then still differs from panel to panel, which is recorded for
 * the maintainer (P19c-6) and not ruled here.
 */
export function offerShown<P>(
  plan: P | null,
  stale: Refused | null,
  refused: string | null,
  asked: string | null,
  revision: number | undefined,
): { plan: P | null; refusal: string | null } {
  const held = shownRefusal(stale, revision);
  if (held !== null) return { plan: null, refusal: held };
  return { plan, refusal: refused ?? asked };
}
```

  Run `npm test`. Expected: every case passes, at 100 %.
- [ ] **Step 3: The worked journey, red first,** row 48, in `gui/e2e/shared.spec.ts`. Add `moveStamp` to its `./demo` import:

```ts
test("the add form's Apply refused as out of date keeps its refusal while the form is typed into, and declares once the page has caught up", async ({
  page,
  vocabularyGui,
}) => {
  const path = join(vocabularyGui.directory, FILES.constants.file);
  const form = await openForm(page, vocabularyGui, "constant", "SPARE_SLOTS");
  const value = form.getByRole("textbox", { name: "Value" });
  await value.fill("4");
  const apply = form.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();

  // The constants file changes under the plan the form holds, one word for another as long,
  // unseen by the session's watcher (`writeUnseen`): only the Apply's own fresh read sees it.
  const before = readFileSync(path, "utf8");
  writeUnseen(vocabularyGui.directory, FILES.constants.file, before.replace("sample slots", "sample cells"));
  await apply.click();
  const refused = form.getByRole("status");
  await expect(refused).toHaveText(STALE);
  await expect(apply).toHaveCount(0);

  // Typed into again, the form asks for the plan of what it now says - but the page has not
  // caught up with the file, and an Apply would send the fingerprints just refused: the refusal
  // stands, and none is offered (P19b-24).
  await value.fill("5");
  await expect(refused).toHaveText(STALE);
  await expect(form.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  // The stamp moved, the page catches up, and the refusal goes with no edit of the reader's.
  moveStamp(vocabularyGui.directory, FILES.constants.file);
  await expect(refused).toHaveCount(0, { timeout: 15000 });
  await form.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByRole("complementary", { name: "SPARE_SLOTS" })).toBeVisible();
  await expect.poll(() => readFileSync(path, "utf8")).toContain('"SPARE_SLOTS"');
});
```

  Run it on today's page, after a build. It must fail at the refusal's `toHaveText` after Value "5". Measured: the edit cleared it.
- [ ] **Step 4: The call sites.** Each replaces its hand-written choice with `offerShown`, and adds `offerShown` to its `../lib/refusals` import (`shownRefusal` leaves it where nothing else reads it).
  - **The four `Outcome` panels:** `UnitPanel`'s, `ConstantPanel`'s, `SectionPanel`'s and `RasterPanel`'s `offer(action)` return:

```ts
    return {
      ...offerShown(
        shown.plan,
        staleFailed?.action === action ? staleFailed : null,
        failed?.action === action ? failed.message : null,
        shown.refusal,
        revision,
      ),
      pending: shown.pending,
    };
```

  - **`TypePanel.tsx`.** After `shown`:

```ts
  // What the active path's offer draws (`offerShown`, P19b-24): while its Apply's stale refusal
  // stands, that refusal alone, so that no Apply is offered which would only be refused again;
  // else the plan, under its Apply's other refusal, or its own.
  const offered = offerShown(
    shown.plan,
    stale?.kind === active ? stale : null,
    refused?.kind === active ? refused.message : null,
    shown.refusal,
    revision,
  );
```

    The view takes `preview={offered.plan}` and `refusal={offered.refusal}`. With no path active, `shown` is all `null` and neither kind matches, so `offered` is `{ plan: null, refusal: null }`, as the old `active === null ? null` was.
  - **`VariablePanel.tsx`, its removal only** (P19c-6): `removalOffer` becomes `{ ...offerShown(removal.data ?? null, removalStale, removalRefused, removal.error?.message ?? null, revision), pending: false }`. The settle keeps its own expression.
  - **`UnitsPage.tsx`.** Before `preview`:

```ts
  // What the adoption offers (`offerShown`, P19b-24): while an adopt refused because a file
  // changed on disk stands, that refusal alone - no Show changes, no Adopt, and no preview beside
  // the table, which comes back by itself once the page has caught up, if still asked for.
  const offered = offerShown(
    adoption.data ?? null,
    stale,
    refused,
    adoption.error?.message ?? null,
    revision,
  );
  const preview = unit === undefined && previewing ? offered.plan : null;
```

    `AdoptBannerView` takes `plan={offered.plan}` and `refusal={offered.refusal}`.
  - **`FilesPage.tsx`'s `useFilesApply`** returns `plan: offered.plan` and `refusal: offered.refusal`, with `const offered = offerShown(shown.plan, stale, refused, shown.refusal, revision);`.
    - Its comment says that while a stale refusal stands, no plan is offered to apply again.
    - Its docstring names `offerShown` where it named `refusalShown`, and so does `FileActionsView.tsx`'s comment on `FileOffer.refusal`.
  - **`ValuesPage.tsx`:**

```ts
  const offered = offerShown(
    pasting ? (table.data ?? null) : shownCell.plan,
    staleFailed,
    failed,
    pasting ? (table.isError ? table.error.message : null) : shownCell.refusal,
    revision,
  );
  const shownPlan = offered.plan;
  // A pasted block's own sentence comes first, as it always did: it is about what the reader has
  // just pasted, where the others are about an Apply.
  const shownSentence = pasting ? (pasteRefusal ?? offered.refusal) : offered.refusal;
```

    `shownRefusal as staleRefusal` leaves its import.
  - **`DeclarePanel.tsx` and `SharedPage.tsx`'s `SharedAdd`.** Each holds its stale refusal as the other panels do:
    - Add `const [stale, setStale] = useState<Refused | null>(null);` beside `refusal`. The comment says the one refused because a file changed on disk is held until the page has caught up, the next revision, whatever is typed meanwhile.
    - `onError` becomes:

```ts
    // Stale is the one refusal that waits for a later revision rather than clearing; setting one
    // kind clears the other, so the form never shows two different answers to the same Apply.
    onError: (error) => {
      if (isStale(error)) {
        setStale({ text: refusalOf(error), revision });
        setRefusal(null);
      } else {
        setRefusal(refusalOf(error));
        setStale(null);
      }
    },
```

    - After `shown`: `const offered = offerShown(shown.plan, stale, refusal, shown.refusal, revision);`. The view takes `plan={offered.plan}` and `refusal={offered.refusal}`.
    - Their edit handlers keep clearing `refusal` alone, never `stale`.
- [ ] **Step 5: Run the worked journey** after a build, with `--repeat-each=10`. Then the ablation, in a scratch copy of the package: `SharedAdd`'s `onRaw` clearing `stale` as well as `refusal`. It must die at the refusal's `toHaveText` after Value "5".
- [ ] **Step 6: The other journeys,** each red today and each run and ablated as its line says.
  - **J1. Rewrite `declarations.spec.ts`'s "a declaration made from a file that changed on disk is refused, and made once the page has caught up"** as "a declaration refused as out of date keeps its refusal while the form is typed into, and is made once the page has caught up". Its last part becomes:

```ts
  // Typed into again - the name cleared, then typed back - the form asks for its plan once more,
  // but an Apply would still send the fingerprints just refused: the refusal stands, and none is
  // offered.
  await name.fill("");
  await name.fill("ValueC");
  await name.press("Enter");
  await expect(adding.getByText("Reads ValueC as SensorHub declares it.")).toBeVisible();
  await expect(refused).toHaveText(STALE);
  await expect(adding.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  // The stamp moved, the page catches up, and the refusal goes with no edit of the reader's.
  moveStamp(gui.directory, CONTROLLER);
  await expect(refused).toHaveCount(0, { timeout: 15000 });
  await adding.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByRole("complementary", { name: "ValueC" })).toBeVisible();
  expect(declarationOf(gui.directory, CONTROLLER, "ValueC").unit).toBe("degC");
```

    - It replaces the old wait on the disagreement's link and the re-typed name ("the refusal goes with the edit"). `refused` is `adding.getByRole("status")`, held from the press, and `STALE` is the sentence the journey already asserts.
    - Type a name other than ValueC at your peril: measured, "ValueD" and "FlagA" each came back as "Diagnosis", the combobox's own pick.
    - **Red today** at the refusal after the re-typed name (measured).
    - **Ablation:** `DeclarePanel`'s `onTyped` clearing `stale`.
  - **J2. Extend `values.spec.ts`'s "a value applied from a file that changed on disk is refused, and applied once the page has caught up"** with `await expect(apply).toHaveCount(0);` after the refusal's sentence.
    - **Red today** (measured: count 1).
    - **Ablation:** `ValuesPage`'s `offerShown` given `null` for `stale`.
  - **J3. Extend `files.spec.ts`'s "a Remove applied while the description changed on disk is refused, and goes through once the analysis has caught up"** with `await expect(remove).toHaveCount(0);` after `toHaveText(STALE)`.
    - **Red today** (measured: count 1).
    - **Ablation:** `useFilesApply`'s `offerShown` given `null` for `stale`.
  - **J4. Extend `shared.spec.ts`'s "a save made from a constant's panel that is out of date is refused, and nothing is written"** with `await expect(save).toHaveCount(0);` after the sentence. Retitle it "…is refused, nothing is written, and no Save is offered until the page has caught up".
    - It goes on: `moveStamp(vocabularyGui.directory, FILES.constants.file)`, the status gone within 15 s, then Save writes 32.
    - **Ablation:** `ConstantPanel`'s `offer` given `null` for `stale`.
  - **J5. New, in `shared.spec.ts`:** "a save refused as out of date in a section's or a raster's panel offers no Save until the page has caught up". It loops over two cases:
    - `.calib` in `sections.ddd.json`, with "tightly coupled" made "Tightly coupled";
    - `100ms` in `rasters.ddd.json`, with "fast control task" made "Fast control task".

    Each case:
    1. `openEntry`; region "Description" filled with `<entry> described`; Save enabled;
    2. `writeUnseen` the file;
    3. Save: the status reads the sentence, and Save has count 0;
    4. `moveStamp`: the status goes, and Save writes it.

    - **Red today** (measured, as the same loop's constant iteration: count 1).
    - **Ablation:** `SectionPanel`'s `offer`, then `RasterPanel`'s, given `null` for `stale`, each killing its own iteration.
  - **J6. New, in `project-units.spec.ts`:** "a unit's Apply refused as out of date offers no Apply until the page has caught up".
    1. degC's region "Remove from the vocabulary" shows "Changes 1 file: units.ddd.json".
    2. `writeUnseen(vocabularyGui.directory, UNITS, …)`, with kPa's `"pressure"` made `"Pressure"`.
    3. "Remove from the vocabulary": the status reads the sentence, and the button has count 0.
    4. `moveStamp`: the status goes, and the press removes degC (the units file lists rpm, Nm and kPa).

    - **Red today** (measured: count 1).
    - **Ablation:** `UnitPanel`'s `offer` given `null` for `stale`.
    - The out-of-date journey at `project-units.spec.ts:181` stays as it is. Its outside write is seen by the watcher, so its refusal lasts about a poll, and a hidden-button assertion there would race the page's own new ask.
  - **J7. Extend `project-units.spec.ts`'s "an adopt refused because its units file now exists says so in the banner, which goes once the units are read again"** while its units read is held (`held`, after Task 1):

```ts
    await expect(banner.getByText(STALE, { exact: true })).toBeVisible();
    // Neither the banner's Adopt nor its preview is offered while the refusal stands (P19b-24):
    // the preview comes back by itself once the page has caught up, if still asked for (P19c-6).
    await expect(banner.getByRole("button", { name: "Adopt 5 units" })).toHaveCount(0);
    await expect(banner.getByRole("button", { name: "Show changes" })).toHaveCount(0);
    await expect(preview).toHaveCount(0);
```

    - **Red today** (measured: the banner's Adopt, count 1).
    - **Ablation:** `UnitsPage`'s `offerShown` given `null` for `stale`.
  - **Unchanged, already the rule:** `declarations.spec.ts`'s removal (its button already `toHaveCount(0)`), `keys.spec.ts`'s and `types.spec.ts`'s stale journeys, `findings.spec.ts`'s, and `skeleton.spec.ts`'s out-of-date edit.
- [ ] **Step 7: Bugs.** This task is P19b-24's fix, red first. Its CHANGELOG entry:

  > **A change refused because a file changed on disk is held until the page has caught up, everywhere.** Every panel now keeps that refusal until the page has read the file again, and offers no Apply meanwhile, which would only be refused once more. The Units, Constants, Sections, Rasters, Files and values panels and the adopt banner kept offering it. The forms adding a declaration or a shared entry let the refusal go at the next keystroke, but kept it after the page had caught up.

  Any other bug a journey finds follows the rule in *Global Constraints*. A non-stale refusal's differences stay recorded (P19c-6).
- [ ] **Step 8: The inventory.**
  - Row 48 names its journey.
  - The rows of J1 to J7 that 19b closed name their journeys again, with the new assertions.
  - *Rulings taken* records P19b-24 as fixed, with the three points of P19c-6.
- [ ] **Step 9: The gates,** every journey included, and the screenshots in Docker in compare mode (no reference may move). Commit in two:
  1. `offerShown`, its cases and the call sites;
  2. the journeys and the CHANGELOG.
