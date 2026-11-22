import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator } from "@playwright/test";
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
// edit that made it, and the changes a plan makes (spec 2026-10-08 §5; part 19c).

/** What the page says while its long poll goes unanswered: `App.tsx`'s `stopped` banner. */
const STOPPED = "ddd gui has stopped. Start it again and open the address it prints.";

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
 * walk for projects keeps only a description that parses (`_descriptions`, `_is_project`,
 * session.py), so only a record can still offer it. */
function unreadable(directory: string): void {
  const description = join(directory, "demo.ddd.json");
  writeRecord(directory, "build", { format: 1, project: description, image: "firmware" });
  const bytes = readFileSync(description);
  writeFileSync(description, bytes.subarray(0, Math.floor(bytes.length / 2)));
}

/** The file whose presence in the copy's directory makes the copy's analyses slow
 * (`slowAnalyses`). */
const SLOW = "slow";

/** The demo changed - or the project `description` names, in `directory` - before `ddd gui`
 * starts on it, so that every analysis takes seconds more while a file named `SLOW` lies in
 * `directory`: a project plugin, `slow.py`, whose check sleeps, named in the description's
 * `plugins`. The examples analyse in a few milliseconds, which leaves a journey no moment to see
 * the page between an edit and the analysis that follows it. The journey creates `SLOW` just
 * before the press that edits, so that the analyses `ddd gui` starts with are fast. The plugin
 * reports no finding.
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

/** A second project in the copy, beside the demo's, under the root the walk for projects searches
 * (`find_projects`, session.py): SecondDevice, of one component of its own, Pump, so that nothing
 * it draws is the demo's - the demo's other project, Logging, is one of DemoDevice's own
 * includes. */
function secondProject(directory: string): void {
  const second = join(directory, SECOND);
  mkdirSync(second);
  const write = (name: string, body: object) =>
    writeFileSync(join(second, name), `${JSON.stringify(body, null, 2)}\n`, "utf8");
  write("pump.ddd.json", { component: { name: "Pump", interface: [] } });
  write(SECOND_DESCRIPTION, { project: { name: "SecondDevice", includes: ["pump.ddd.json"] } });
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
  // The name is the cut file's, which no longer loads: the walk does not find it (`unreadable`),
  // and only the record offers it, so there is no entry under the demo's name. The other project
  // is listed as usual.
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
  try {
    await other.goto(started.address);
    await other.getByRole("button", { name: "Projects", exact: true }).click();
    const second = other.getByRole("button", { name: /^SecondDevice/ });
    await expect(second).toBeVisible();
    // From here on SecondDevice's analyses take seconds, the first one opening it starts among
    // them: the examples analyse in milliseconds, too soon for the page to be seen between.
    const slow = join(started.directory, SECOND, SLOW);
    writeFileSync(slow, "");
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
    rmSync(slow);
    releaseSession();
  } finally {
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
