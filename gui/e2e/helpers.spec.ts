import { readFileSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { CONTROLLER, failing, held, restamp, SERVER_FAILED } from "./demo";
import { expect, test } from "./fixtures";

/** A route the page never asks on its own (no caller in gui/src), so that only the asks below
 * are counted - and one the server answers: refused 401 here, since `fetch` below sends no
 * token. */
const UNASKED = "/api/checks";

/** The other route the page never asks (spec 2026-10-08 §4), asked beside `UNASKED` to show that
 * `failing` leaves alone a path it was not given: the server refuses it 401 too. */
const BESIDE = "/api/dictionary";

type Asked = { status: number; message: string | null } | "no answer";

/** `path` asked from inside the page, by a plain `fetch` from its own origin that carries no
 * token: the answer's status and message, or "no answer" where the fetch was rejected. */
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
  // A path it was not given reaches the server, which refuses it, and is not counted.
  expect(await askedFromPage(page, BESIDE)).toMatchObject({ status: 401 });
  expect(failed()).toBe(0);
  expect(await askedFromPage(page, UNASKED)).toEqual({ status: 500, message: SERVER_FAILED });
  expect(failed()).toBe(1);
  // Past its one failure the ask reaches the server, which refuses it: no token was sent.
  expect(await askedFromPage(page, UNASKED)).toMatchObject({ status: 401 });
  expect(failed()).toBe(1);
});

test("a request failed with no answer, every time, matched by a pattern", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  // The `g` flag makes a pattern's own `test` go on from where it last stopped: `failing` tries
  // it afresh for every request all the same.
  const failed = await failing(page, /^\/api\/checks$/g, "network");
  expect(await askedFromPage(page, UNASKED)).toBe("no answer");
  expect(await askedFromPage(page, UNASKED)).toBe("no answer");
  expect(failed()).toBe(2);
  // A path the pattern does not match reaches the server, which refuses it, and is not counted.
  expect(await askedFromPage(page, BESIDE)).toMatchObject({ status: 401 });
  expect(failed()).toBe(2);
});

test("the copy served is the one its journey changed, as the server reads it", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => {
    const project = join(directory, "demo.ddd.json");
    const text = readFileSync(project, "utf8");
    writeFileSync(project, text.replace('"name": "DemoDevice"', '"name": "ChangedDevice"'));
  });
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "ChangedDevice", exact: true })).toBeVisible();
});

/** The demo's own name, `DemoDevice`, replaced in its copy by `name`. */
function renamedTo(name: string): (directory: string) => void {
  return (directory) => {
    const project = join(directory, "demo.ddd.json");
    const text = readFileSync(project, "utf8");
    writeFileSync(project, text.replace('"name": "DemoDevice"', `"name": "${name}"`));
  };
}

test("two copies asked for at once are served from two directories, each with its own change", async ({
  page,
  copiedGui,
}) => {
  const [first, second] = await Promise.all([
    copiedGui("demo", renamedTo("FirstDevice")),
    copiedGui("demo", renamedTo("SecondDevice")),
  ]);
  expect(first.directory).not.toBe(second.directory);
  await page.goto(first.address);
  await expect(page.getByRole("button", { name: "FirstDevice", exact: true })).toBeVisible();
  await page.goto(second.address);
  await expect(page.getByRole("button", { name: "SecondDevice", exact: true })).toBeVisible();
});

test("a copy of the layout example is served with the plugin its project names beside it", async ({
  page,
  copiedGui,
}) => {
  // The project loads `../plugins/ddd_layout.py`. A key above the project's `max_key` is a finding
  // only that plugin's own check files, `layout/key-out-of-range`: a copy served with no plugin
  // beside it lists `plugin-not-found` and `unknown-extension` instead, and never this.
  const gui = await copiedGui("layout", (directory) => {
    const storage = join(directory, "storage.ddd.json");
    const before = readFileSync(storage, "utf8");
    const moved = before.replace('"key": 12', '"key": 5000');
    if (moved === before) throw new Error(`EngineHours carries no key 12 in ${storage}`);
    writeFileSync(storage, moved);
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(
    page.getByRole("gridcell", {
      name: "'EngineHours' claims key 5000, above the project's max_key of 4095",
      exact: true,
    }),
  ).toBeVisible();
});

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
