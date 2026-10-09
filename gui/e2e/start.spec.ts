import { mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { failing, SERVER_FAILED } from "./demo";
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
  await expect(page.getByText(`Found under ${resolve(started.directory)}`)).toBeVisible();
  await expect(
    page.getByText("No project description was found here. Start ddd gui with the path of one."),
  ).toBeVisible();
});

test("a build record in a format too new is listed as not used, and its project still opens", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", record, { named: false });
  await page.goto(started.address);
  await expect(
    page.getByRole("heading", { name: "Build records not used", level: 2 }),
  ).toBeVisible();
  const recordPath = resolve(join(started.directory, "build", "ddd-build.json"));
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
  let release = (): void => undefined;
  const released = new Promise<void>((resolve_) => {
    release = resolve_;
  });
  await page.route("**/api/projects", async (route) => {
    await released;
    await route.continue();
  });
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
  // A POST is never resent (Task 2's `sentAgain`), so one failure is enough.
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
  // The request already in flight when this registers is past the browser's own routing, and
  // waits out the server's own long poll (`WAIT_SECONDS`, api.py) before answering unchanged;
  // the one the page sends after it is what this fails, at once (spec 2026-10-08 §6, an HTTP
  // answer unlike a dropped GET).
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED, { timeout: 30_000 });
  // The page stays drawn: the canvas is still the one up, not replaced by anything else.
  await expect(canvas).toBeVisible();
  // An HTTP answer is no stopped server: that banner is a different one, and does not show.
  await expect(page.getByText("ddd gui has stopped", { exact: false })).toHaveCount(0);
  expect(failed()).toBeGreaterThan(0);
});
