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
