import { failing } from "./demo";
import { expect, test } from "./fixtures";

// The page's own loads, failed by the network once or every time (spec 2026-10-08 §6): a
// stylesheet is asked for once more before the page draws, and a GET of the API is sent once
// more, while a second failure reads as one did before either was.

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
