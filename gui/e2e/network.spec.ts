import type { Page } from "@playwright/test";
import { failing } from "./demo";
import { expect, test } from "./fixtures";

// The page's own loads, failed by the network once or every time (spec 2026-10-08 §6): each
// stylesheet, GET of the API and the layout worker's script is asked for once more, a stylesheet
// before the page draws, while a second failure reads as one did before any was asked again.

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

test("the pressable rule's stylesheet the network failed once is asked for again", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, "/pressable.css", "network", 1);
  await page.goto(gui.address);
  const projects = page.getByRole("button", { name: "Projects", exact: true });
  await expect(projects).toBeVisible();
  expect(failed()).toBe(1);
  // pressable.css's one rule, on every element React Aria presses (gui/public/pressable.css):
  // `pan-x pan-y pinch-zoom`, which the browser computes as the one keyword meaning the same,
  // `manipulation` (read off the page in Chrome). Without the rule, it is `auto`.
  await expect(projects).toHaveCSS("touch-action", "manipulation");
});

test("a stylesheet the network fails every time leaves the page drawn and working", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, STYLESHEET, "network");
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  // Asked for once more, and failed again: the page is drawn all the same, never left waiting.
  expect(failed()).toBe(2);
  // A stylesheet's failure reaches the boot script's listener too, which asks again for a module
  // script of the page's own origin alone: nothing says the page did not load.
  await expect(page.getByText(PAGE_NOT_LOADED, { exact: true })).toHaveCount(0);
  // The browser's own body, transparent: the page is drawn unstyled, as before it asked again.
  await expect(page.locator("body")).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await controller.click();
  await expect(page.getByRole("heading", { name: "Controller" })).toBeVisible();
});

test("a GET the network failed once is sent again, and the page carries on", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, "/api/graph", "network", 1);
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  expect(failed()).toBe(1);
  // The canvas's error banner is an alert (GraphPage.tsx's `Banner tone="error"`), saying the
  // server is not answering: none shows, nor any other alert.
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a GET the network fails every time reads as the server not answering", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, "/api/graph", "network");
  await page.goto(gui.address);
  // The canvas's error banner (GraphPage.tsx), in place of the canvas, saying what the page says
  // of `ServerUnreachable` (client.ts) - once the GET got no answer twice.
  await expect(page.getByRole("alert")).toHaveText("ddd gui is not answering");
  expect(failed()).toBe(2);
});

/** The layout worker's own script, as Vite names it in /assets/ beside the stylesheet. Asked for
 * once more by creating the worker once more (ruling P19b-26 in the plan). */
const LAYOUT_WORKER = /^\/assets\/layoutWorker-[^/]+\.js$/;

test("the layout worker's script the network failed once is asked for again, and the canvas is drawn", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, LAYOUT_WORKER, "network", 1);
  await page.goto(gui.address);
  // The modules, laid out by the worker created once more (`createdAgain`, lib/layoutAnswers.ts):
  // the one that failed never started, and never answered.
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  expect(failed()).toBe(1);
  // A worker that stopped is said in an alert, in place of the canvas (`WORKER_FAILED`): none
  // shows.
  await expect(page.getByRole("alert")).toHaveCount(0);
});

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

/** Appends to the page a module script it never asks for, at `address`, and records from then on
 * the address of each script whose load fails, in order (`failedScripts`). Recorded by a listener
 * of the journey's own, added on the same target and in the same phase as the boot script's but
 * after it, so that it hears each failure once the boot script has acted on it: the reader sees
 * nothing change, so this is what says the failure was met. */
async function unasked(page: Page, address: string): Promise<void> {
  await page.evaluate((src) => {
    const failed: string[] = [];
    Object.assign(window, { failedScripts: failed });
    addEventListener(
      "error",
      (event) => {
        if (event.target instanceof HTMLScriptElement) failed.push(event.target.src);
      },
      true,
    );
    const script = document.createElement("script");
    script.type = "module";
    script.src = src;
    document.head.append(script);
  }, address);
}

/** The address of each script whose load failed since `unasked`, in order. */
function failedScripts(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as unknown as { failedScripts: string[] }).failedScripts);
}

test("a module script of the page's origin that it never asked for, failing once the page is drawn, is asked for once more, and the page stays drawn", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  // A path no file has: the server answers it with the page itself, as html, which the browser
  // runs as no module script (read off the page in Chrome), so its load fails. The boot script
  // asks once more for any module script of the page's own origin, and the copy fails the same.
  const address = new URL("/assets/unasked.js", gui.address).href;
  await unasked(page, address);
  await expect.poll(() => failedScripts(page)).toEqual([address, `${address}?again`]);
  // A copy failing is what the boot script says the page did not load on, but only while #root
  // holds nothing: the page is drawn, so nothing is written over it.
  await expect(page.getByText(PAGE_NOT_LOADED, { exact: true })).toHaveCount(0);
  await expect(controller).toBeVisible();
});

test("a module script of another origin, failing once the page is drawn, is not asked for again, and the page stays drawn", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  // An origin under `.invalid`, which no name resolves in. The policy refuses it before it is
  // fetched - its `script-src` is this origin and the boot script's hash - and its load fails
  // (read off the page in Chrome).
  const address = "https://unasked.invalid/page.js";
  await unasked(page, address);
  await expect.poll(() => failedScripts(page)).toContain(address);
  // The boot script met that failure before the journey heard it, and asked for no copy, which
  // would carry `data-again`: it asks again for a module script of the page's own origin alone.
  await expect(page.locator("script[data-again]")).toHaveCount(0);
  await expect(page.getByText(PAGE_NOT_LOADED, { exact: true })).toHaveCount(0);
  await expect(controller).toBeVisible();
});
