import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { failing, SERVER_FAILED } from "./demo";
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
