import { mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, failing, held, restamp, SERVER_FAILED } from "./demo";
import { expect, test } from "./fixtures";

// The start page's own states - no project found, a build record this DDD cannot read, the
// list loading or failing, opening a project failing - and the app around every page: signed
// out, and the banner an HTTP failure of the long poll raises (spec 2026-10-08 §5).

/** The copy's own contents taken away, its directory left standing: no project description, no
 * build record, nothing - what the start page meets where `ddd gui` was started somewhere
 * holding none of either (`StartPage.tsx`'s own "No project description was found here"). */
function empty(directory: string): void {
  for (const entry of readdirSync(directory)) {
    rmSync(join(directory, entry), { recursive: true });
  }
}

/** A build record under the copy's own `build/`, naming its `demo.ddd.json`, in a format one
 * past what this DDD reads (`BUILD_INFO_FORMAT`, src/ddd/build_info.py, `1` at `205d5a6`) - read
 * far enough by `_Stamp` (`ddd.lsp.discovery`) to be refused by name, rather than skipped in
 * silence for failing to parse at all. */
function record(directory: string): void {
  const dir = join(directory, "build");
  mkdirSync(dir);
  const body = { format: 2, project: join(directory, "demo.ddd.json") };
  writeFileSync(join(dir, "ddd-build.json"), `${JSON.stringify(body, null, 2)}\n`, "utf8");
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
      `${recordPath}: written in format 2 by a newer DDD, and this one understands up to format 1`,
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
