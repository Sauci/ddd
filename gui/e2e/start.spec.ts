import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import {
  CONTROLLER,
  drift,
  failing,
  held,
  restamp,
  SENSOR_HUB,
  SERVER_FAILED,
  scrolledIntoView,
} from "./demo";
import { expect, test } from "./fixtures";

// The start page's own states - no project found, a build record this DDD cannot read, the
// list loading, failing or naming images, a project that does not load, a project opening - and
// the app around every page: signed in by a launch's code, connecting, the session failing,
// signed out, analysing the project, a project another page opened, the banners of a long poll
// that fails and of a server that stopped, what is written while it has, a panel just after the
// edit that made it, and the changes a plan makes (spec 2026-10-08 §5; part 19c); and a page that
// cannot be drawn (15:I5).

/** What the page says while its long poll goes unanswered: `App.tsx`'s `stopped` banner. */
const STOPPED = "ddd gui has stopped. Start it again and open the address it prints.";

/** What a component's page says in its own place once its findings come in a reply it cannot draw
 * (`routesLeftOut`): `undrawnSentence`'s line (lib/undrawn.ts), ending in the words of what was
 * thrown - V8's, for `kind` read off a route the reply left out, which every leg's browser says
 * alike, Chromium and Edge both being V8's (ci.yml). */
const UNDRAWN =
  "This page could not be drawn: Cannot read properties of undefined (reading 'kind')";

/** Answers the page's asks for the findings of the file whose path ends in `/${name}` - a
 * component's page asks for its own file's - with the server's own answer, every finding's `route`
 * taken out of it: a reply the page cannot draw, since it reads where each finding leads off its
 * route (`routeOf`, lib/findings.ts) as it lists it. Every other ask goes through untouched. */
async function routesLeftOut(page: Page, name: string): Promise<void> {
  await page.route(
    (url) =>
      url.pathname === "/api/findings" && (url.searchParams.get("file") ?? "").endsWith(`/${name}`),
    async (route) => {
      const response = await route.fetch();
      const reply = await response.json();
      const findings = reply.findings.map((finding: Record<string, unknown>) =>
        Object.fromEntries(Object.entries(finding).filter(([key]) => key !== "route")),
      );
      await route.fulfill({ response, json: { ...reply, findings } });
    },
  );
}

/** The copy's own contents taken away, its directory left standing: no project description, no
 * build record, nothing - what the start page meets where `ddd gui` was started somewhere
 * holding none of either (`StartPage.tsx`'s own "No project description was found here"). */
function empty(directory: string): void {
  for (const entry of readdirSync(directory)) {
    rmSync(join(directory, entry), { recursive: true });
  }
}

/** A build record, `ddd-build.json`, under `where` in the copy (made if it is not there), written
 * as `ddd build-info` writes one (`build_info_text`, src/ddd/build_info.py): `body` as json with
 * a two-space indent and a final newline. */
function writeRecord(directory: string, where: string, body: object): void {
  const dir = join(directory, where);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "ddd-build.json"), `${JSON.stringify(body, null, 2)}\n`, "utf8");
}

/** A build record under the copy's own `build/`, naming its `demo.ddd.json`, in a format one
 * past what this DDD reads (`BUILD_INFO_FORMAT`, src/ddd/build_info.py, held to by
 * tests/test_documentation.py, which fails when the stamp is not one past it) - read
 * far enough by `_Stamp` (`ddd.lsp.discovery`) to be refused by name, rather than skipped in
 * silence for failing to parse at all. */
function record(directory: string): void {
  writeRecord(directory, "build", { format: 3, project: join(directory, "demo.ddd.json") });
}

/** The demo built as two images: a record for each, in the format this DDD reads (`1`). The
 * fields are those of `BuildInfo` (src/ddd/build_info.py), which forbids any other. */
function builtTwice(directory: string): void {
  const project = join(directory, "demo.ddd.json");
  for (const image of ["firmware", "tests"]) {
    writeRecord(directory, join("build", image), { format: 1, project, image });
  }
}

/** The demo's description cut in half, so that it no longer loads, and a record that names it: the
 * walk for projects lists a description it cannot read as unreadable (`_descriptions`, session.py)
 * unless a record offers it, which then lists it as a project without a name. */
function unreadable(directory: string): void {
  const description = join(directory, "demo.ddd.json");
  writeRecord(directory, "build", { format: 1, project: description, image: "firmware" });
  const bytes = readFileSync(description);
  writeFileSync(description, bytes.subarray(0, Math.floor(bytes.length / 2)));
}

/** The file whose presence in the copy's directory makes the copy's analyses slow
 * (`slowAnalyses`). */
const SLOW = "slow";

/** The file whose presence in the copy's directory holds every analysis of the copy until the
 * journey takes it away (`slowAnalyses`): a window the journey closes itself, once it has seen
 * what it waits for, where `SLOW`'s is a few seconds whatever the journey has seen by then. */
const HELD = "held";

/** The longest an analysis waits on `HELD`, in seconds: far past any stall of a runner, so that a
 * file a journey failed to take away holds a server no longer than this. */
const HELD_SECONDS = 60;

/** The demo changed - or the project `description` names, in `directory` - before `ddd gui`
 * starts on it, so that every analysis takes seconds more while a file named `SLOW` lies in
 * `directory`, and waits while one named `HELD` does: a project plugin, `slow.py`, whose check
 * sleeps, named in the description's `plugins`. The examples analyse in a few milliseconds, which
 * leaves a journey no moment to see the page between an edit and the analysis that follows it.
 * The journey creates either file just before the press that edits or opens, so that the analyses
 * `ddd gui` starts with are fast. The plugin reports no finding.
 *
 * Not `generatedGui`, whose analysis runs for about a second: the panel of a variable just
 * declared there opens only once the add panel's own reads have answered (`DeclarePanel`'s
 * `onSuccess`), the generated project's `declarable` among them, which takes about as long as the
 * analysis does. Measured in Chrome on the Linux development PC, in six runs the panel opened
 * after the analysis had landed and never said the findings were updating. */
function slowAnalyses(directory: string, description = "demo.ddd.json"): void {
  const plugin = [
    "import time",
    "from pathlib import Path",
    "",
    "from ddd.plugins import Plugin",
    "",
    "",
    "def check(context):",
    `    if Path(__file__).with_name("${SLOW}").exists():`,
    "        time.sleep(3)",
    `    held = Path(__file__).with_name("${HELD}")`,
    `    deadline = time.monotonic() + ${HELD_SECONDS}`,
    "    while held.exists() and time.monotonic() < deadline:",
    "        time.sleep(0.05)",
    "",
    "",
    'PLUGIN = Plugin(name="slow", check=check)',
    "",
  ];
  writeFileSync(join(directory, "slow.py"), plugin.join("\n"), "utf8");
  const path = join(directory, description);
  const data = JSON.parse(readFileSync(path, "utf8"));
  data.project.plugins = [...(data.project.plugins ?? []), "slow.py"];
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

/** The directory, in the copy, of `secondProject`'s project. */
const SECOND = "second";

/** `secondProject`'s description: the file the page names that project by until the session says
 * its name (`projectName`, lib/session.ts). */
const SECOND_DESCRIPTION = "second.ddd.json";

/** A project in a directory of the copy, `folder`, beside the demo's, under the root the walk for
 * projects searches (`find_projects`, session.py): `name`, described by `<folder>.ddd.json`, of one
 * component of its own, so that nothing it draws is the demo's - the demo's other project, Logging,
 * is one of DemoDevice's own includes. */
function projectOfOne(directory: string, folder: string, name: string, component: string): void {
  const where = join(directory, folder);
  mkdirSync(where);
  const write = (file: string, body: object) =>
    writeFileSync(join(where, file), `${JSON.stringify(body, null, 2)}\n`, "utf8");
  const file = `${component.toLowerCase()}.ddd.json`;
  write(file, { component: { name: component, interface: [] } });
  write(`${folder}.ddd.json`, { project: { name, includes: [file] } });
}

/** A second project in the copy: SecondDevice, of one component, Pump (`projectOfOne`). */
function secondProject(directory: string): void {
  projectOfOne(directory, SECOND, "SecondDevice", "Pump");
}

/** A third project in the copy: ThirdDevice, of one component, Valve (`projectOfOne`). */
function thirdProject(directory: string): void {
  projectOfOne(directory, "third", "ThirdDevice", "Valve");
}

/** Where the canvas draws a module's node: the `transform` React Flow places it by, its position
 * on the canvas whatever the viewport shows of it. */
function placeOf(node: Locator): Promise<string> {
  return node.evaluate((element) => (element as HTMLElement).style.transform);
}

test("an empty directory finds no project, and the start page says so", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", empty, { named: false });
  await page.goto(started.address);
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  // The page shows the server's own `root.as_posix()` (api.py's `_projects`), forward-slashed even
  // on Windows; `started.directory` is native-separated there, so only the separator is swapped,
  // never `path.resolve()`'d, as `files.spec.ts`'s own `key` does for the same comparison.
  const root = started.directory.replaceAll("\\", "/");
  await expect(page.getByText(`Found under ${root}`)).toBeVisible();
  await expect(
    page.getByText("No project description was found here. Start ddd gui with the path of one."),
  ).toBeVisible();
  // Nothing was met that could not be read, so no list of such files is drawn.
  await expect(
    page.getByRole("heading", { name: "Project descriptions that could not be read" }),
  ).toHaveCount(0);
  await expect(page.locator("ul.unreadable")).toHaveCount(0);
});

test("a build record in a format too new is listed as not used, and its project is still offered", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", record, { named: false });
  await page.goto(started.address);
  await expect(
    page.getByRole("heading", { name: "Build records not used", level: 2 }),
  ).toBeVisible();
  // Same posix-only comparison as "no project found" above: `entry.record` is the server's own
  // `.as_posix()` (api.py's `_projects`), never native-separated.
  const recordPath = `${started.directory.replaceAll("\\", "/")}/build/ddd-build.json`;
  await expect(
    page.getByText(
      `${recordPath}: written in format 3 by a newer DDD, and this one understands up to format 2`,
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /DemoDevice/ })).toBeVisible();
});

/** A description beside the demo's that does not parse, `brokenone/broken.ddd.json`: cut off at its
 * first brace, as an editor that crashed leaves one. */
function brokenBeside(directory: string): void {
  const dir = join(directory, "brokenone");
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "broken.ddd.json"), "{", "utf8");
}

test("a description that does not parse is listed with its reason, beside the projects that were found, and a component's is not", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", brokenBeside, { named: false });
  await page.goto(started.address);
  await expect(
    page.getByRole("heading", { name: "Project descriptions that could not be read", level: 2 }),
  ).toBeVisible();
  // The path is the server's own `.as_posix()` (api.py's `_projects`), as "an empty directory" says.
  const broken = `${started.directory.replaceAll("\\", "/")}/brokenone/broken.ddd.json`;
  const listed = page.locator("ul.unreadable li");
  // The reason is the loader's own, which names where the text stops being json.
  await expect(listed).toHaveText([new RegExp(`^${broken}: does not parse: .*line 1 column 2`)]);
  // The demo's components are descriptions that parse and state no project: not on this list.
  await expect(listed).toHaveCount(1);
  await expect(page.getByRole("button", { name: /DemoDevice/ })).toBeVisible();
});

/** Nothing but a description that does not parse, `brokenone/broken.ddd.json`: the only project
 * of the directory is the one that cannot be read. */
function onlyBroken(directory: string): void {
  empty(directory);
  brokenBeside(directory);
}

test("a directory whose only description does not parse says none could be read, and lists it with its reason", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", onlyBroken, { named: false });
  await page.goto(started.address);
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  await expect(
    page.getByText(
      "No project description found here could be read. Each is listed below with why.",
    ),
  ).toBeVisible();
  await expect(page.getByText("No project description was found here")).toHaveCount(0);
  await expect(page.locator("ul.projects")).toHaveCount(0);
  const broken = `${started.directory.replaceAll("\\", "/")}/brokenone/broken.ddd.json`;
  await expect(page.locator("ul.unreadable li")).toHaveText([
    new RegExp(`^${broken}: does not parse: `),
  ]);
});

test("the start page says it is looking for projects, until the list answers", async ({
  page,
  bareGui,
}) => {
  const release = await held(page, "/api/projects");
  try {
    await page.goto(bareGui.address);
    await expect(page.getByText("Looking for projects…")).toBeVisible();
  } finally {
    release();
  }
  await expect(page.getByRole("button", { name: /DemoDevice/ })).toBeVisible();
});

test("the projects list failing shows the server's own error, with no list drawn", async ({
  page,
  bareGui,
}) => {
  const failed = await failing(page, "/api/projects", "http");
  await page.goto(bareGui.address);
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("heading", { name: "Open a project" })).toHaveCount(0);
  expect(failed()).toBe(1);
});

test("opening a project that fails leaves the start page in place, with the server's own error", async ({
  page,
  bareGui,
}) => {
  await page.goto(bareGui.address);
  const button = page.getByRole("button", { name: /DemoDevice/ });
  await expect(button).toBeVisible();
  const failed = await failing(page, "/api/open", "http");
  await button.click();
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  // An open the server refused gives the list back (`listHeld`, lib/start.ts): the reader may try
  // again, or another project.
  await expect(button).toBeEnabled();
  // One failure is enough regardless of the method: `failing`'s "http" resolves the fetch with
  // a 500, and `sentAgain` (client.ts) is only ever asked from the `.catch` of one that
  // *rejected* - "An HTTP answer, a refusal included, never comes here: `fetch` resolves it",
  // `sentAgain`'s own doc comment, client.ts.
  expect(failed()).toBe(1);
});

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

test("an http failure of the long poll raises its own banner, and leaves the page drawn", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const canvas = page.getByRole("region", { name: "Modules" });
  await expect(canvas).toBeVisible();
  const failed = await failing(page, "/api/state", "http");
  // The ask already in flight when this registers is past the browser's own routing, and would
  // otherwise wait out the server's own long poll (`WAIT_SECONDS`, 25.0, api.py) before
  // answering unchanged - ruling P19b-9. Touching a project file's own stamp instead wakes it at
  // once with a new version (`stamped`/`poll`, session.py, compare `(st_mtime_ns, st_size)`
  // alone, so no byte need change): the ask the page sends *after* that is the one this fails.
  restamp(gui.directory, CONTROLLER);
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  // The page stays drawn: the canvas is still the one up, not replaced by anything else.
  await expect(canvas).toBeVisible();
  // An HTTP answer is no stopped server: that banner is a different one, and does not show.
  await expect(page.getByText("ddd gui has stopped", { exact: false })).toHaveCount(0);
  expect(failed()).toBeGreaterThan(0);
});

test("a project is listed with the images its build records name", async ({ page, copiedGui }) => {
  const started = await copiedGui("demo", builtTwice, { named: false });
  await page.goto(started.address);
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  // The records name the project the walk finds already: one entry (`find_projects`, session.py,
  // joins the two), and it holds both images, in the order the records are read - sorted by
  // path, `build/firmware` before `build/tests` (`build_files`, lsp/discovery.py).
  const demo = page.getByRole("button", { name: /^DemoDevice/ });
  await expect(demo).toHaveCount(1);
  await expect(demo.getByText("built as firmware, tests", { exact: true })).toBeVisible();
  // Logging, which no record names, is listed with no image.
  const logging = page.getByRole("button", { name: /^Logging/ });
  await expect(logging).toBeVisible();
  await expect(logging.getByText(/^built as/)).toHaveCount(0);
});

test("a project whose description does not load is listed as an unnamed project", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", unreadable, { named: false });
  await page.goto(started.address);
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  const unnamed = page.getByRole("button", { name: /^Unnamed project/ });
  // The path is the server's own `as_posix()` (api.py's `_projects`), forward-slashed even on
  // Windows, where only the separator of the copy's is swapped, as "an empty directory" does.
  await expect(unnamed.locator(".path")).toHaveText(
    `${started.directory.replaceAll("\\", "/")}/demo.ddd.json`,
  );
  await expect(unnamed.getByText("built as firmware", { exact: true })).toBeVisible();
  // The name is the cut file's, which no longer loads: it is offered by the record alone, so there
  // is no entry under the demo's name, and no line among the descriptions that could not be read,
  // which a record's project is not listed among. The other project is listed as usual.
  await expect(page.locator("ul.unreadable")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^DemoDevice/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Logging/ })).toBeVisible();
});

test("a project opening holds every button of the list, until the start page goes", async ({
  page,
  bareGui,
}) => {
  await page.goto(bareGui.address);
  const demo = page.getByRole("button", { name: /^DemoDevice/ });
  const logging = page.getByRole("button", { name: /^Logging/ });
  const list = page.getByRole("heading", { name: "Open a project" });
  await expect(demo).toBeVisible();
  const releaseOpen = await held(page, "/api/open");
  // Once the open has answered, `onOpened` (App.tsx) asks for the session again without waiting
  // for it, and the start page is drawn until that answer lands: that ask is held as well.
  const releaseSession = await held(page, "/api/session");
  try {
    await demo.click();
    // The open is asked and held: no button of the list takes another press.
    await expect(demo).toBeDisabled();
    await expect(logging).toBeDisabled();
    await expect(list).toBeVisible();

    releaseOpen();
    // The open answered: the address moves on to the project's (`onOpened`), and the session is
    // held, so the start page is still drawn - with its list still held, since a press now would
    // open another project in place of the one just opened.
    await expect(page).toHaveURL(/\/project$/);
    await expect(list).toBeVisible();
    await expect(demo).toBeDisabled();
    await expect(logging).toBeDisabled();
  } finally {
    releaseOpen();
    releaseSession();
  }
  // The session answered: the start page goes, and the project is drawn.
  await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeVisible();
  await expect(list).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
});

test("the address ddd gui opens its own browser with signs the page in by a one-time code, spent once used", async ({
  browser,
  page,
  openedGui,
}) => {
  // The address `launched` (server.py) handed the browser: this server's own, at /open, with a
  // code that is good for `CODE_SECONDS`, or until it is redeemed.
  const address = await openedGui.opened();
  await page.goto(address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  // The page traded the code for its token and wrote the code out of its own address
  // (`signInFrom`, `landingOf`, api/signIn.ts).
  await expect(page).toHaveURL(/\/project$/);

  // A code is spent once (`redeem_code`): a page that kept nothing, handed the same address, is
  // signed in by nothing. The server prints its warning for a code presented again
  // (`_CODE_REUSED`) on its stderr, which is only noise in the log.
  const stranger = await browser.newPage();
  try {
    await stranger.goto(address);
    await expect(
      stranger.getByRole("status").filter({ hasText: "printed in its terminal" }),
    ).toHaveText("Open the address ddd gui printed in its terminal.");
    await expect(stranger.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);
  } finally {
    await stranger.close();
  }
});

test("the page says it is connecting until the session answers", async ({ page, gui }) => {
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  // Held after the sign-in, not on /open: there the first ask of the session is `signInFrom`'s
  // own, made before anything is rendered (main.tsx), and a hold on it leaves a blank page. The
  // address is `/project` now, so a reload signs in again by nothing, and the only ask of the
  // session is the app's own.
  const release = await held(page, "/api/session");
  try {
    await page.reload();
    await expect(page.getByText("Connecting…", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Projects", exact: true })).toBeVisible();
    // No project is known to be open yet: it is the session that says so.
    await expect(page.getByRole("heading", { name: "DemoDevice" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "DemoDevice", exact: true })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeVisible();
  await expect(page.getByText("Connecting…", { exact: true })).toHaveCount(0);
});

test("the session failing shows the server's own error, and no page", async ({ page, gui }) => {
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  // Registered after the sign-in, whose own ask of the session would be failed as well. An HTTP
  // answer is not asked for again (`sentAgain`, client.ts, and `retry: false`, main.tsx), so the
  // page's one ask is the one failure.
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
  const demo = page.getByRole("button", { name: /^DemoDevice/ });
  await expect(demo).toBeVisible();
  // The page asks for no state while no project is open (`useProjectState`), so this is the
  // first ask there is, made once the session says a project is.
  const release = await held(page, "/api/state");
  try {
    await demo.click();
    await expect(page.getByText("Analysing the project…", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Project views" })).toBeVisible();
    // No tab asks the server anything before the first analysis (App.tsx): none is drawn.
    await expect(page.getByRole("region", { name: "Modules" })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(page.getByText("Analysing the project…", { exact: true })).toHaveCount(0);
});

/** What the banner under the masthead says while the demo's Controller does not load (16:I9): a
 * file that does not load stops every check of the project, and the pages show the rest. */
const UNLOADED =
  "controller.ddd.json did not load, so the project's checks wait until it does, and the pages " +
  "show what the files that loaded declare.";

/** The project screen's tab of that name, as its row of tabs draws it: by its exact name, since a
 * file the banner names, `units.ddd.json`, holds a tab's. */
function tab(page: Page, name: string): Locator {
  return page
    .getByRole("navigation", { name: "Project views" })
    .getByRole("link", { name, exact: true });
}

test("a file that does not load is named under the masthead of every page, a component's among them, leading to its finding", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  // Saved half-written, as an editor saves a file being typed into: it no longer parses, and every
  // page is drawn from the files that did load.
  const path = join(gui.directory, CONTROLLER);
  const bytes = readFileSync(path);
  writeFileSync(path, bytes.subarray(0, Math.floor(bytes.length / 2)));
  const banner = page.getByRole("status").filter({ hasText: "project's checks" });
  await expect(banner).toHaveText(UNLOADED);
  for (const name of ["Table", "Units", "Types", "Shared files", "Files", "Findings", "Compare"]) {
    await tab(page, name).click();
    await expect(tab(page, name)).toHaveAttribute("aria-current", "page");
    await expect(banner).toHaveText(UNLOADED);
  }
  // A component's page, which is no tab: SensorHub's, from the Table.
  await tab(page, "Table").click();
  await page.getByRole("button", { name: "SensorHub", exact: true }).click();
  await expect(page.getByRole("heading", { name: "SensorHub", level: 1 })).toBeVisible();
  await expect(banner).toHaveText(UNLOADED);
  // The file's name leads to its finding: the Findings tab, asking for the findings that hold it -
  // the file's own, the one saying why it did not load first among its errors. Followed in the
  // page, as a tab is: a link followed by loading its address starts a new document, where a
  // marker on this one is gone.
  await page.evaluate(() => {
    (window as unknown as { marker: string }).marker = "this document";
  });
  await banner.getByRole("link", { name: "controller.ddd.json", exact: true }).click();
  await expect(page).toHaveURL(/\/project\?view=findings&text=controller\.ddd\.json$/);
  await expect(page.getByRole("textbox", { name: "Filter findings" })).toHaveValue(
    "controller.ddd.json",
  );
  await expect(page.getByRole("row", { name: "json-syntax" })).toBeVisible();
  await expect(banner).toHaveText(UNLOADED);
  const kept = await page.evaluate(() => (window as unknown as { marker?: string }).marker);
  expect(kept).toBe("this document");
  // From the Findings tab itself, its filter holding another text, the link asks for the file's.
  await tab(page, "Findings").click();
  const filter = page.getByRole("textbox", { name: "Filter findings" });
  await expect(filter).toHaveValue("");
  await filter.fill("sensor");
  await banner.getByRole("link", { name: "controller.ddd.json", exact: true }).click();
  await expect(filter).toHaveValue("controller.ddd.json");
  await expect(page.getByRole("row", { name: "json-syntax" })).toBeVisible();
  // The start page is no page of the open project: it lists the projects to open, and no banner.
  await page.getByRole("button", { name: "Projects", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  await expect(banner).toHaveCount(0);
});

test("a project's own description that does not load is named under the masthead, no file it includes read, leading to its finding", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  // Saved half-written once the project is open: a description that does not parse is refused
  // when it is opened, and read no further than itself while it is open.
  const path = join(gui.directory, "demo.ddd.json");
  const bytes = readFileSync(path);
  writeFileSync(path, bytes.subarray(0, Math.floor(bytes.length / 2)));
  const banner = page.getByRole("status").filter({ hasText: "project's checks" });
  await expect(banner).toHaveText(
    "demo.ddd.json did not load, so the project's checks wait until it does, and no file it " +
      "includes is read.",
  );
  // Nothing it includes is drawn: no module is left on the canvas.
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);
  await banner.getByRole("link", { name: "demo.ddd.json", exact: true }).click();
  await expect(page).toHaveURL(/\/project\?view=findings&text=demo\.ddd\.json$/);
  await expect(page.getByRole("row", { name: "json-syntax" })).toBeVisible();
});

/** Saves the demo's Controller half-written in `directory`, as an editor saves a file being typed
 * into, and follows its link under the masthead, whatever the banner's sentence, to the Findings
 * tab asking for the findings that hold its name; returns the link. */
async function followedToControllerFindings(page: Page, directory: string): Promise<Locator> {
  const path = join(directory, CONTROLLER);
  const bytes = readFileSync(path);
  writeFileSync(path, bytes.subarray(0, Math.floor(bytes.length / 2)));
  const link = page
    .getByRole("status")
    .getByRole("link", { name: "controller.ddd.json", exact: true });
  await link.click();
  await expect(page).toHaveURL(/\/project\?view=findings&text=controller\.ddd\.json$/);
  await expect(page.getByRole("row", { name: "json-syntax" })).toBeVisible();
  return link;
}

test("a file's link under the masthead, pressed again once other text was typed, leads to its findings, the text typed a step of its own", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const link = await followedToControllerFindings(page, gui.directory);
  const filter = page.getByRole("textbox", { name: "Filter findings" });
  const cut = page.getByRole("row", { name: "json-syntax" });
  const steps = await page.evaluate(() => window.history.length);
  // Another text, which no finding holds, asked for once typing pauses, and written into the
  // address in place of the file's, as a selection is: typing is no step for Back to walk through.
  await filter.fill("sensor");
  await expect(cut).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=findings&text=sensor$/);
  expect(await page.evaluate(() => window.history.length)).toBe(steps);
  await link.click();
  await expect(filter).toHaveValue("controller.ddd.json");
  await expect(cut).toBeVisible();
  // Back leads to the text typed, and not to the file's findings a second time.
  await page.goBack();
  await expect(page).toHaveURL(/\/project\?view=findings&text=sensor$/);
  await expect(filter).toHaveValue("sensor");
  await expect(cut).toHaveCount(0);
});

test("a file's link under the masthead, pressed again before typing paused, leads to its findings and adds no step to the history", async ({
  page,
  gui,
}) => {
  // The page's clock is stopped while the filter is typed into, so that typing never pauses: the
  // address is still the one the link leads to when it is pressed again.
  await page.clock.install();
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const link = await followedToControllerFindings(page, gui.directory);
  const filter = page.getByRole("textbox", { name: "Filter findings" });
  const steps = await page.evaluate(() => window.history.length);
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 1000));
  await filter.fill("sensor");
  await link.click();
  await expect(filter).toHaveValue("controller.ddd.json");
  expect(await page.evaluate(() => window.history.length)).toBe(steps);
  // The text typed went with the tab drawn anew: the clock going on asks for nothing of it.
  await page.clock.resume();
  await expect(page.getByRole("row", { name: "json-syntax" })).toBeVisible();
  await expect(page).toHaveURL(/\/project\?view=findings&text=controller\.ddd\.json$/);
});

test("a build record this DDD cannot use is named under the masthead of the open project, with its reason", async ({
  page,
  copiedGui,
}) => {
  // In a format past every one this DDD reads, which reads up to format 2 (`BUILD_INFO_FORMAT`,
  // src/ddd/build_info.py), as `tests/test_gui_session.py`'s `build_record(..., format=99)` writes
  // one: under `build/`, where the analysis looks for records (`build_files`, lsp/discovery.py).
  const started = await copiedGui("demo", (directory) =>
    writeRecord(directory, join("build", "ddd", "fw"), {
      format: 99,
      project: join(directory, "demo.ddd.json"),
      image: "fw",
    }),
  );
  await page.goto(started.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  // Named from the project's directory, as the Table tab's File column names a file, in the words
  // the terminal tells it in.
  await expect(page.getByRole("status").filter({ hasText: "ddd-build.json" })).toHaveText(
    "build/ddd/fw/ddd-build.json: written in format 99 by a newer DDD, and this one understands " +
      "up to format 2; this record is ignored, so its severities apply to no analysis.",
  );
});

/** What the banner under the masthead says of a first analysis that failed for `boom`, while the
 * server runs: a failure leaves every file it read stamped unknown (`Session._finished`), so each
 * poll asks for another, a second apart, a file changed on disk or none. */
const FIRST_FAILED =
  "Analysing the project failed: boom. ddd gui tries again about every second, until an analysis " +
  "succeeds.";

/** Answers every ask of the state with the server's own, said to be of an analysis that failed
 * for `reason` (`State.failed`) - the project's first, with no revision to stand, where `first` -
 * until the function it answers is called, from when every answer is the server's own again. The
 * one real trigger, a plugin path holding a NUL, is one a later DDD may mend. A journey ends with
 * `unrouteAll`: the page's long poll always has an ask on its way. */
async function analysesFail(page: Page, reason: string, first: boolean): Promise<() => void> {
  let failing = true;
  await page.route(
    (url) => url.pathname === "/api/state",
    async (route) => {
      // A page that goes elsewhere while its ask waits on the server leaves the ask nowhere to be
      // answered: its fetch or its fulfilment fails then, and nothing is waiting for either.
      try {
        const response = await route.fetch();
        if (!failing) {
          await route.fulfill({ response });
          return;
        }
        const state = await response.json();
        const none = { error: 0, warning: 0, info: 0 };
        const failed = first
          ? {
              ...state,
              revision: 0,
              files: [],
              refused: [],
              counts: none,
              statements: none,
              undoable: null,
              analysing: false,
              edits: 0,
              failed: reason,
            }
          : { ...state, failed: reason };
        await route.fulfill({ response, json: failed });
      } catch {
        // Gone with the page that asked.
      }
    },
  );
  return () => {
    failing = false;
  };
}

test("a first analysis that failed is said under the masthead, never as analysing, until one lands", async ({
  page,
  gui,
}) => {
  const mended = await analysesFail(page, "boom", true);
  try {
    await page.goto(gui.address);
    await expect(page.getByRole("alert")).toHaveText(FIRST_FAILED);
    await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeVisible();
    // Said to be analysing, a failure asked again at every poll read as an analysis never ending.
    await expect(page.getByText("Analysing the project…", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Modules" })).toHaveCount(0);
    // A component's page before any revision says it too.
    await page.goto(
      `${new URL(gui.address).origin}/component?file=${encodeURIComponent(
        join(gui.directory, CONTROLLER).replaceAll("\\", "/"),
      )}`,
    );
    await expect(page.getByRole("alert")).toHaveText(FIRST_FAILED);
    await expect(page.getByText("Analysing the project…", { exact: true })).toHaveCount(0);
    // An analysis that lands lifts it: here the server's own, every answer its own again, which a
    // stamp moved has the long poll answer at once.
    mended();
    restamp(gui.directory, CONTROLLER);
    await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
  } finally {
    await page.unrouteAll({ behavior: "ignoreErrors" });
  }
});

test("an analysis that failed after one landed is said under the masthead, over the pages of the last", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const canvas = page.getByRole("region", { name: "Modules" });
  await expect(canvas).toBeVisible();
  const mended = await analysesFail(page, "boom", false);
  try {
    // The ask already on its way is past the route: a change on disk answers it, and the next.
    restamp(gui.directory, CONTROLLER);
    await expect(page.getByRole("alert")).toHaveText(
      "Analysing the project failed: boom. The pages show the last analysis that finished, and " +
        "ddd gui tries again about every second, until one succeeds.",
    );
    await expect(canvas).toBeVisible();
    mended();
    restamp(gui.directory, CONTROLLER);
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(canvas).toBeVisible();
  } finally {
    await page.unrouteAll({ behavior: "ignoreErrors" });
  }
});

test("an analysis that failed promises no other once the server has stopped", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const canvas = page.getByRole("region", { name: "Modules" });
  await expect(canvas).toBeVisible();
  await analysesFail(page, "boom", false);
  try {
    // The ask already on its way is past the route: a change on disk answers it, and the next.
    restamp(gui.directory, CONTROLLER);
    const failure = page.getByRole("alert").filter({ hasText: "Analysing the project failed" });
    await expect(failure).toBeVisible();
    // Then every ask of the long poll dropped on the network, as a stopped server drops it, over
    // the route above: the last registered answers first. A stamp moved answers the ask in flight,
    // so that the ask after it is the first one dropped.
    await failing(page, "/api/state", "network");
    restamp(gui.directory, CONTROLLER);
    await expect(page.getByRole("alert").filter({ hasText: "has stopped" })).toHaveText(STOPPED);
    // A stopped ddd gui tries nothing again: the banner says what the last state read holds.
    await expect(failure).toHaveText(
      "Analysing the project failed: boom. The pages show the last analysis that finished.",
    );
    await expect(canvas).toBeVisible();
  } finally {
    await page.unrouteAll({ behavior: "ignoreErrors" });
  }
});

test("a project a second page opens is the one the first names over what it draws, by its file until the session answers, and the arrangement made there is its own", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", secondProject, { named: false });
  await page.goto(started.address);
  await page.getByRole("button", { name: /^DemoDevice/ }).click();
  const heading = page.getByRole("heading", { level: 1 });
  const masthead = page.getByRole("banner");
  const canvas = page.getByRole("region", { name: "Modules" });
  await expect(canvas.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(heading).toHaveText("DemoDevice");

  // The next ask of the session this page makes is held: it is the one made once the state this
  // page follows is of another project, and until it is answered the page names that project by
  // its description's file, the state carrying the description's path and no name.
  const releaseSession = await held(page, "/api/session");
  // A second page of the same browser, as a second tab is, signed in by the same address: it
  // opens the other project from the start page, and the server has one project open at a time.
  const other = await page.context().newPage();
  try {
    await other.goto(started.address);
    await other.getByRole("button", { name: "Projects", exact: true }).click();
    await other.getByRole("button", { name: /^SecondDevice/ }).click();
    await expect(other.getByRole("heading", { level: 1 })).toHaveText("SecondDevice");

    // The first page, never reloaded, draws what the state is of now: SecondDevice's one module.
    const pump = canvas
      .locator(".react-flow__node")
      .filter({ has: page.getByRole("button", { name: "Pump", exact: true }) });
    await expect(pump).toBeVisible();
    await expect(canvas.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);
    await expect(heading).toHaveText(SECOND_DESCRIPTION);
    await expect(
      masthead.getByRole("button", { name: SECOND_DESCRIPTION, exact: true }),
    ).toBeVisible();

    // Pump moved on the first page while its session is still held, the session naming DemoDevice.
    const laidOut = await placeOf(pump);
    const box = await pump.boundingBox();
    if (box === null) throw new Error("the Pump node has no bounding box");
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 + 60, { steps: 12 });
    await page.mouse.up();
    const dragged = await placeOf(pump);
    expect(dragged).not.toBe(laidOut);

    // The session answers, and the first page names the project as its description does.
    releaseSession();
    await expect(heading).toHaveText("SecondDevice");
    await expect(masthead.getByRole("button", { name: "SecondDevice", exact: true })).toBeVisible();
    await expect(masthead.getByRole("button", { name: "DemoDevice" })).toHaveCount(0);

    // The arrangement was kept under the project drawn, not the one the session named then: the
    // second page, drawn again, finds Pump where the first put it.
    await other.reload();
    const theirs = other
      .getByRole("region", { name: "Modules" })
      .locator(".react-flow__node")
      .filter({ has: other.getByRole("button", { name: "Pump", exact: true }) });
    await expect(theirs).toBeVisible();
    await expect.poll(() => placeOf(theirs)).toBe(dragged);
  } finally {
    releaseSession();
    await other.close();
  }
});

test("a project a second page opens is the one the first names, on a component's page, while that project's first analysis runs", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui(
    "demo",
    (directory) => {
      secondProject(directory);
      slowAnalyses(join(directory, SECOND), SECOND_DESCRIPTION);
    },
    { named: false },
  );
  await page.goto(started.address);
  await page.getByRole("button", { name: /^DemoDevice/ }).click();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();

  // The session asked again held, as in the journey above: until it answers, the first page has
  // only the state it follows to name the project by.
  const releaseSession = await held(page, "/api/session");
  const other = await page.context().newPage();
  const hold = join(started.directory, SECOND, HELD);
  try {
    await other.goto(started.address);
    await other.getByRole("button", { name: "Projects", exact: true }).click();
    const second = other.getByRole("button", { name: /^SecondDevice/ });
    await expect(second).toBeVisible();
    // From here on SecondDevice's analyses wait until the journey takes `HELD` away, the first
    // one opening it starts among them: the examples analyse in milliseconds, too soon for the
    // page to be seen between, and a wait of a few seconds is one a stalled runner can outlast.
    writeFileSync(hold, "");
    await second.click();
    // While that analysis runs, the first page says so where the component's own page stood,
    // under the name of the project the state is of: the state says which from its first answer,
    // before any revision of that project is analysed. Both are read off one moment of the page,
    // the heading and the line under it: once the analysis lands, the heading alone reads the
    // same whether or not the page named the project before it.
    await expect(
      page
        .locator("section")
        .filter({
          has: page.getByRole("heading", { name: SECOND_DESCRIPTION, exact: true, level: 1 }),
        })
        .filter({ hasText: "Analysing the project…" }),
    ).toBeVisible();
  } finally {
    // Taken away once the page has been seen, or the journey has failed: the analysis lands now.
    rmSync(hold, { force: true });
    releaseSession();
    await other.close();
  }
  // The session answered: the masthead names the project as its description does, and leads to
  // it.
  await page.getByRole("banner").getByRole("button", { name: "SecondDevice", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("SecondDevice");
  await expect(
    page
      .getByRole("region", { name: "Modules" })
      .getByRole("button", { name: "Pump", exact: true }),
  ).toBeVisible();
});

test("a project a second page opens while the first page's ask of the session is on its way is asked for again, and the late answer changes nothing", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui(
    "demo",
    (directory) => {
      secondProject(directory);
      thirdProject(directory);
    },
    { named: false },
  );
  await page.goto(started.address);
  await page.getByRole("button", { name: /^DemoDevice/ }).click();
  const heading = page.getByRole("heading", { level: 1 });
  await expect(
    page
      .getByRole("region", { name: "Modules" })
      .getByRole("button", { name: "Controller", exact: true }),
  ).toBeVisible();

  // The first page's next ask of the session is answered by the server at once, and the answer
  // kept from the page until released: an answer on its way while the server moves on. `held`
  // asks the server only once released, too late to name the project open before.
  let answered = false;
  let delivered = false;
  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    (url) => url.pathname === "/api/session",
    async (route) => {
      const response = await route.fetch();
      answered = true;
      await released;
      await route.fulfill({ response });
      delivered = true;
    },
    { times: 1 },
  );
  const other = await page.context().newPage();
  try {
    await other.goto(started.address);
    const projects = other.getByRole("button", { name: "Projects", exact: true });
    await projects.click();
    await other.getByRole("button", { name: /^SecondDevice/ }).click();
    await expect(other.getByRole("heading", { level: 1 })).toHaveText("SecondDevice");
    // The first page asked which project is open once its state was SecondDevice's, and the
    // server has answered SecondDevice; then the second page opens a third project.
    await expect.poll(() => answered).toBe(true);
    await projects.click();
    await other.getByRole("button", { name: /^ThirdDevice/ }).click();
    await expect(other.getByRole("heading", { level: 1 })).toHaveText("ThirdDevice");

    // The first page's state is ThirdDevice's now: it asks again, and names it once answered.
    await expect(heading).toHaveText("ThirdDevice");
  } finally {
    release();
    await other.close();
  }
  // The answer naming SecondDevice reaches the page last, and the page goes on naming ThirdDevice:
  // read once that answer has come and two frames have been drawn since.
  await expect.poll(() => delivered).toBe(true);
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  await expect(heading).toHaveText("ThirdDevice");
  await expect(
    page.getByRole("banner").getByRole("button", { name: "ThirdDevice", exact: true }),
  ).toBeVisible();
});

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

test("a stopped server disables every control that writes, the component table's cells among them", async ({
  page,
  gui,
}) => {
  // Both flow from SensorHub to Controller in the demo, and Controller reads each in another unit.
  drift(gui.directory, "ValueA", "rpm");
  drift(gui.directory, "ValueB", "mV");
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();

  // An edit of the page's own, so that the Undo is offered: ValueB settled on the unit its
  // producer states.
  await page.getByRole("button", { name: "Set the unit of ValueB" }).click();
  const settled = page.getByRole("complementary", { name: "ValueB" });
  await settled.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(settled.getByText("Nothing to change")).toBeVisible();
  const undo = page.getByRole("button", { name: "Undo the unit of ValueB" });
  await expect(undo).toBeVisible();

  // ValueA's panel, with a change to apply and a declaration to remove.
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  const apply = panel.getByRole("button", { name: "Apply to 1 file" });
  const remove = panel.getByRole("button", { name: "Remove from Controller" });
  const add = page.getByRole("button", { name: "Add a declaration" });
  // The table's own buttons: one that opens another declaration's panel, and one that opens the
  // values of CurveA, whose row is drawn once the virtualised table is wheeled to it.
  const setUnit = page.getByRole("button", { name: "Set the unit of ValueB" });
  const showValues = page.getByRole("button", { name: "Show the values of CurveA" });
  await scrolledIntoView(page, "Declarations of Controller", showValues);
  const controls = [apply, remove, add, setUnit, undo, showValues];
  for (const control of controls) await expect(control).toBeEnabled();
  const written = readFileSync(join(gui.directory, CONTROLLER));

  // The page's state poll fails as a stopped server fails it. A file's stamp moved, no byte
  // changed, answers the poll in flight, so that the ask after it is the first one dropped.
  await failing(page, "/api/state", "network");
  restamp(gui.directory, SENSOR_HUB);
  await expect(page.getByRole("alert").filter({ hasText: "has stopped" })).toHaveText(STOPPED);
  for (const control of controls) await expect(control).toBeDisabled();
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(written)).toBe(true);
});

test("a page that cannot be drawn says why in its own place, under the masthead, at its own address, until the reader goes elsewhere", async ({
  page,
  gui,
}) => {
  // ValueA's unit drifted, so that Controller's page has a finding to list, in a reply it cannot
  // draw.
  drift(gui.directory);
  await routesLeftOut(page, "controller.ddd.json");
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const undrawn = page.getByRole("alert").filter({ hasText: "could not be drawn" });
  await expect(undrawn).toHaveText(UNDRAWN);
  // What is gone is what the page's main region held, and nothing above it: the masthead is drawn,
  // and the address is the component's still.
  const project = page.getByRole("banner").getByRole("button", { name: "DemoDevice", exact: true });
  await expect(project).toBeVisible();
  await expect(page).toHaveURL(/\/component\?file=[^&]*controller\.ddd\.json$/);
  await expect(page.getByRole("heading", { name: "Controller" })).toHaveCount(0);

  // Let go once the reader goes elsewhere: the project's canvas is drawn in its place.
  await project.click();
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
  await expect(undrawn).toHaveCount(0);
  // And back on the component's page, whose reply still cannot be drawn, it is caught again.
  await page.goBack();
  await expect(undrawn).toHaveText(UNDRAWN);
  await page.unrouteAll({ behavior: "wait" });
});

test("a page that cannot be drawn offers a reload while the server answers, none once it has stopped, and is drawn once reloaded", async ({
  page,
  gui,
}) => {
  drift(gui.directory);
  await routesLeftOut(page, "controller.ddd.json");
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const undrawn = page.getByRole("alert").filter({ hasText: "could not be drawn" });
  await expect(undrawn).toHaveText(UNDRAWN);
  const reload = page.getByRole("button", { name: "Reload the page", exact: true });
  await expect(reload).toBeVisible();

  // The server stopping, its long poll dropped as the journeys above drop it: the banner says so
  // above what failed, and no reload is offered, which would lose the page.
  await failing(page, "/api/state", "network");
  restamp(gui.directory, CONTROLLER);
  const stopped = page.getByRole("alert").filter({ hasText: "has stopped" });
  await expect(stopped).toHaveText(STOPPED);
  await expect(undrawn).toHaveText(UNDRAWN);
  await expect(reload).toHaveCount(0);

  // The server answering again, and the findings with their routes: the banner lifts, the reload
  // is offered again, and the page it loads again is drawn.
  await page.unrouteAll({ behavior: "wait" });
  await expect(stopped).toHaveCount(0);
  await expect(reload).toBeVisible();
  await reload.click();
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  await expect(undrawn).toHaveCount(0);
});

test("a variable just declared shows its panel saying the findings are updating, until the analysis lands", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", slowAnalyses);
  await page.goto(started.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  // A new measurement, as declarations.spec.ts declares one: nothing in the analysis declares it
  // yet, which is what its panel is refused for. A variable another component produces is known
  // to the analysis already, and its panel never says the findings are updating.
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
  await expect(
    adding.getByText("Declares Pressure, a measurement this component produces."),
  ).toBeVisible();

  // From here on the analyses take seconds, the one the edit asks for first: the examples' take a
  // few milliseconds, and the panel's first ask would be answered from the analysis of the edit.
  writeFileSync(join(started.directory, SLOW), "");
  await adding.getByRole("button", { name: "Apply to 1 file" }).click();

  // The panel opens on the declaration (`DeclarePanel`'s `onDeclared`) and asks for it: refused
  // `unreadable` until the analysis indexes it (`panelShows`, lib/refusals.ts). For as long as
  // the findings are updating it says only that - its title, Close and the note, no "Reading
  // Pressure…", no keys, no error banner.
  const panel = page.getByRole("complementary", { name: "Pressure" });
  await expect(panel).toHaveText("PressureCloseUpdating the findings…");
  // Once the analysis has landed, the panel draws Pressure's keys, and the note is empty.
  await expect(panel.getByRole("grid")).toBeVisible();
  await expect(panel.locator(".updating-note")).toHaveText("");
});

test("the changes a plan makes are shown, and hidden again", async ({ page, gui }) => {
  drift(gui.directory);
  const drifted = readFileSync(join(gui.directory, CONTROLLER));
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const settling = page
    .getByRole("complementary", { name: "ValueA" })
    .getByRole("region", { name: "Settle the key" });
  await expect(settling.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  // Not shown until asked for.
  const hunks = settling.locator(".hunk");
  await expect(hunks).toHaveCount(0);

  await settling.getByRole("button", { name: "Show changes" }).click();
  await expect(hunks).toHaveCount(1);
  await expect(hunks.getByText('- "unit": "rpm",', { exact: true })).toBeVisible();
  await expect(hunks.getByText('+ "unit": "%",', { exact: true })).toBeVisible();
  await expect(settling.getByRole("button", { name: "Show changes" })).toHaveCount(0);

  await settling.getByRole("button", { name: "Hide changes" }).click();
  await expect(hunks).toHaveCount(0);
  await expect(settling.getByRole("button", { name: "Show changes" })).toBeVisible();
  await expect(settling.getByRole("button", { name: "Hide changes" })).toHaveCount(0);
  // Shown or hidden, nothing was written: the file is the drifted one the journey began with.
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(drifted)).toBe(true);
});
