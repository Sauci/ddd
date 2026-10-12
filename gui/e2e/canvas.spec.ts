import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { CONTROLLER, drift, EVENT_LOGGER, renameValueA } from "./demo";
import { expect, test } from "./fixtures";

// The canvas's own actions and states - no dictionary, Fit, the module search and its Enter,
// hovering a module, the undeclared-variable banner reached from an arrow, the drawing and layout
// states and the layout worker failing - and the components table's summary line while the
// findings update (spec 2026-10-08 §4).

/** Where the viewport stands: React Flow's own `translate(x, y) scale(zoom)` on
 * `.react-flow__viewport`, read back as numbers. */
interface Viewport {
  x: number;
  y: number;
  zoom: number;
}

async function viewportOf(page: Page): Promise<Viewport> {
  const transform = await page
    .locator(".react-flow__viewport")
    .evaluate((node) => (node as HTMLElement).style.transform);
  const found = /^translate\((\S+)px, (\S+)px\) scale\((\S+)\)$/.exec(transform);
  if (found === null) throw new Error(`the viewport's transform reads "${transform}"`);
  return { x: Number(found[1]), y: Number(found[2]), zoom: Number(found[3]) };
}

/** A module's own box on the canvas, the one `data-faded` is written on (`ModuleNode.tsx`). */
const moduleOf = (page: Page, name: string): Locator =>
  page.locator(".module").filter({ has: page.getByRole("button", { name, exact: true }) });

/** The middle of what a locator draws, in the page's own pixels. */
async function middleOf(locator: Locator): Promise<{ x: number; y: number }> {
  const box = await locator.boundingBox();
  if (box === null) throw new Error(`${locator} draws no box`);
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

/** How far, in pixels, one module's box sits from the middle of the canvas. */
async function offCentre(page: Page, name: string): Promise<number> {
  const canvas = await middleOf(page.getByRole("region", { name: "Modules" }));
  const module = await middleOf(
    page
      .locator(".react-flow__node")
      .filter({ has: page.getByRole("button", { name, exact: true }) }),
  );
  return Math.hypot(module.x - canvas.x, module.y - canvas.y);
}

/** Each module's name with where it stands on the canvas, in the canvas's own units: React
 * Flow's `translate` on its node, under the viewport's own. */
function placementsOf(page: Page): Promise<[string | null, string][]> {
  return page
    .locator(".react-flow__node")
    .evaluateAll((nodes) =>
      nodes.map((node) => [node.textContent, (node as HTMLElement).style.transform]),
    );
}

/** The mouse wheel turned over the middle of the canvas: a negative `deltaY` zooms in. */
async function wheelOverCanvas(page: Page, deltaY: number): Promise<void> {
  const canvas = await middleOf(page.getByRole("region", { name: "Modules" }));
  await page.mouse.move(canvas.x, canvas.y);
  await page.mouse.wheel(0, deltaY);
}

test("a project with a file that does not load is drawn without arrows, and says why", async ({
  page,
  gui,
}) => {
  // Cut in half, as findings.spec.ts's "a finding that leads nowhere says why" cuts it: no
  // dictionary is resolved while a file of the project does not load (`lsp/diagnostics.py`).
  const path = join(gui.directory, CONTROLLER);
  const bytes = readFileSync(path);
  writeFileSync(path, bytes.subarray(0, Math.floor(bytes.length / 2)));
  await page.goto(gui.address);
  await expect(page.getByRole("status").filter({ hasText: "no dictionary" })).toHaveText(
    "This project has no dictionary, so its modules are drawn without arrows.",
  );
  await expect(page.getByRole("button", { name: "SensorHub", exact: true })).toBeVisible();
  await expect(page.locator(".react-flow__edge")).toHaveCount(0);
});

test("Fit returns the viewport to the one the canvas opened on, and moves no module", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const nodes = page.locator(".react-flow__node");
  await expect(nodes).toHaveCount(4);
  const opening = await viewportOf(page);
  // Where each module stands among the others, in the canvas's own units: the wheel and Fit
  // change the viewport over them, never these.
  const placed = await placementsOf(page);

  // Zoomed in, by the wheel over the canvas: the demo opens below the canvas's own greatest zoom
  // (1.11494 of 2, measured in Chrome on the Linux development PC), so the wheel can go further.
  await wheelOverCanvas(page, -300);
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeGreaterThan(opening.zoom);

  await page.getByRole("button", { name: "Fit", exact: true }).click();
  // The flight takes 300 ms (`FLIGHT`, GraphPage.tsx), waited for by where it lands: within half
  // a pixel and half a thousandth of the zoom the canvas opened on (`openingViewport`,
  // lib/canvas.ts, decides both).
  await expect
    .poll(() => viewportOf(page))
    .toEqual({
      x: expect.closeTo(opening.x, 0),
      y: expect.closeTo(opening.y, 0),
      zoom: expect.closeTo(opening.zoom, 3),
    });
  expect(await placementsOf(page)).toEqual(placed);
});

test("a search typed dims every module whose name does not contain it", async ({ page, gui }) => {
  await page.goto(gui.address);
  const names = ["Controller", "SensorHub", "UserInterface", "EventLogger"];
  for (const name of names) {
    await expect(moduleOf(page, name)).toHaveAttribute("data-faded", "false");
  }
  await page.getByRole("textbox", { name: "Search modules" }).fill("Sensor");
  await expect(moduleOf(page, "SensorHub")).toHaveAttribute("data-faded", "false");
  for (const name of ["Controller", "UserInterface", "EventLogger"]) {
    await expect(moduleOf(page, name)).toHaveAttribute("data-faded", "true");
  }
  // What a reader sees of it: `.module[data-faded="true"]` is drawn at a fifth of its opacity.
  await expect(moduleOf(page, "Controller")).toHaveCSS("opacity", "0.2");
  await expect(moduleOf(page, "SensorHub")).toHaveCSS("opacity", "1");
});

test("a search's Enter centres the first module it finds", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(moduleOf(page, "SensorHub")).toBeVisible();
  const opening = await viewportOf(page);
  // Zoomed out first, so that the flight has a zoom to change as well as a place to go to.
  await wheelOverCanvas(page, 300);
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeLessThan(opening.zoom);
  // Off the middle before the search, or its Enter would have nothing to show: 254 px, zoomed
  // out so (measured in Chrome on the Linux development PC, at 4bf7fa9).
  await expect.poll(() => offCentre(page, "SensorHub")).toBeGreaterThan(100);

  const search = page.getByRole("textbox", { name: "Search modules" });
  await search.fill("Sensor");
  await search.press("Enter");
  // Waited for by where the 300 ms flight lands, within 2 px of the canvas's own middle (0 px
  // measured, on a canvas 1068 by 504).
  await expect.poll(() => offCentre(page, "SensorHub")).toBeLessThanOrEqual(2);
});

/**
 * The demo with ValueE taken out of what EventLogger reads, so that Controller - which writes
 * ValueE - no longer sends anything to EventLogger. The demo's four modules are otherwise each
 * other's neighbours, all six pairs of them joined by its seven arrows (`skeleton.spec.ts`'s
 * `DEMO_ARROWS`), so a hover on the demo as it ships dims nothing at all (measured: every module
 * and every arrow label still `data-faded="false"` with Controller, or EventLogger, hovered).
 * Measured on this copy: six arrows, none in disagreement and no finding on any module, and
 * Controller's neighbours SensorHub (SensorHub to Controller) and UserInterface (Controller to
 * UserInterface) alone.
 */
function withoutValueEInEventLogger(directory: string): void {
  const path = join(directory, EVENT_LOGGER);
  const data = JSON.parse(readFileSync(path, "utf8"));
  const kept = data.component.interface.filter(
    (declaration: { definition: { name: string } }) => declaration.definition.name !== "ValueE",
  );
  if (kept.length !== data.component.interface.length - 1) {
    throw new Error(`${path} no longer reads ValueE, so this copy would change nothing`);
  }
  data.component.interface = kept;
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

test("hovering a module dims every module that is not one of its neighbours", async ({
  page,
  copiedGui,
}) => {
  const started = await copiedGui("demo", withoutValueEInEventLogger);
  await page.goto(started.address);
  const names = ["Controller", "SensorHub", "UserInterface", "EventLogger"];
  for (const name of names) {
    await expect(moduleOf(page, name)).toHaveAttribute("data-faded", "false");
  }

  await moduleOf(page, "Controller").hover();
  await expect(moduleOf(page, "EventLogger")).toHaveAttribute("data-faded", "true");
  for (const name of ["Controller", "SensorHub", "UserInterface"]) {
    await expect(moduleOf(page, name)).toHaveAttribute("data-faded", "false");
  }

  // Away to a corner of the canvas, inside the room the opening view leaves around the modules.
  const canvas = await page.getByRole("region", { name: "Modules" }).boundingBox();
  if (canvas === null) throw new Error("the canvas draws no box");
  await page.mouse.move(canvas.x + 5, canvas.y + 5);
  for (const name of names) {
    await expect(moduleOf(page, name)).toHaveAttribute("data-faded", "false");
  }
});

test("a variable opened from an arrow and then no longer declared closes, and the canvas says so", async ({
  page,
  gui,
}) => {
  drift(gui.directory);
  await page.goto(gui.address);
  // Opened as units.spec.ts's "the same disagreement is resolved from its arrow on the canvas"
  // opens it: the error label of the one arrow in disagreement, SensorHub to Controller.
  await page.locator(".flow-label.error").click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await expect(panel).toBeVisible();
  await expect(page).toHaveURL(/\/project\?variable=ValueA$/);

  renameValueA(gui.directory, "ValueZ");
  await expect(page.getByRole("status").filter({ hasText: "no longer declared" })).toHaveText(
    "ValueA is no longer declared in the open project.",
  );
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\/project$/);
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
});

test("the canvas says it is drawing the project until the graph answers", async ({ page, gui }) => {
  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  // The first graph the page asks for alone, held until the journey has seen what is shown
  // meanwhile; any later one goes straight through.
  await page.route(
    "**/api/graph",
    async (route) => {
      await released;
      await route.continue();
    },
    { times: 1 },
  );
  try {
    await page.goto(gui.address);
    await expect(page.getByText("Drawing the project…", { exact: true })).toBeVisible();
  } finally {
    release();
  }
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(page.getByText("Drawing the project…", { exact: true })).toHaveCount(0);
});

test("the canvas says it is laying the project out until the layout comes", async ({
  page,
  gui,
}) => {
  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  // The layout worker's own script, the one request between the graph and its layout (`useLayout`
  // starts the worker once the graph is there to lay out): held, the worker never starts, and
  // nothing is laid out until it is let through.
  await page.route(
    "**/assets/layoutWorker-*.js",
    async (route) => {
      await released;
      await route.continue();
    },
    { times: 1 },
  );
  try {
    await page.goto(gui.address);
    await expect(page.getByText("Laying the project out…", { exact: true })).toBeVisible();
  } finally {
    release();
  }
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(page.getByText("Laying the project out…", { exact: true })).toHaveCount(0);
});

test("a layout worker that cannot start says to reload, and a reload draws the canvas", async ({
  page,
  gui,
}) => {
  // Answered with what is not its script, as a page left open across a rebuild meets a worker
  // address that no longer exists (`WORKER_FAILED`, lib/layoutAnswers.ts); once only, so that the
  // reload the banner asks for is served the worker itself.
  await page.route(
    "**/assets/layoutWorker-*.js",
    (route) => route.fulfill({ status: 404, contentType: "text/plain", body: "not found" }),
    { times: 1 },
  );
  await page.goto(gui.address);
  await expect(page.getByRole("alert")).toHaveText(
    "The layout worker stopped; reload the page to try again.",
  );
  await expect(page.getByText("Laying the project out…", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

/** Records, from now on and at every frame the page paints, what the components table's summary
 * line reads, as `demo.ts`'s `watchFrames` records a field: a state as short as this one, which a
 * wait on any one moment can step over. Measured in Chrome on the Linux development PC, the line
 * said the findings were updating for 0.85 s, from 0.38 s after the write - not much longer than
 * the 500 ms Playwright's own assertions come to wait between two looks (playwright-core's
 * `retryWithProgressAndBackoff`). Read back with `summariesSeen`. */
async function watchSummary(page: Page): Promise<void> {
  await page.evaluate(() => {
    const frames: (string | null)[] = [];
    (window as unknown as { summaries: typeof frames }).summaries = frames;
    const each = () => {
      frames.push(document.querySelector("p.summary")?.textContent ?? null);
      requestAnimationFrame(each);
    };
    requestAnimationFrame(each);
  });
}

/** Every line `watchSummary` has recorded so far, each once, in the order they were first seen. */
async function summariesSeen(page: Page): Promise<(string | null)[]> {
  const frames = await page.evaluate(
    () => (window as unknown as { summaries: (string | null)[] }).summaries,
  );
  return [...new Set(frames)];
}

test("the components table's summary says the findings are updating while they are", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Table" }).click();
  // The generated project's own counts (`generated`, fixtures.ts), read off the running page.
  const line = "0 errors, 10000 warnings";
  const summary = page.locator("p.summary");
  await expect(summary).toHaveText(line);

  await watchSummary(page);
  // A description changed from outside, written plainly so that the watcher sees it: a new
  // analysis runs, and its findings are the same as before.
  const path = join(generatedGui.directory, "components", "c00000.ddd.json");
  const before = readFileSync(path, "utf8");
  const after = before.replace(
    '"description": "generated measurement 0"',
    '"description": "generated measurement 0, described again"',
  );
  if (after === before) throw new Error(`${path} no longer describes its first measurement so`);
  writeFileSync(path, after, "utf8");

  await expect.poll(() => summariesSeen(page)).toContain(`${line} · updating`);
  await expect(summary).toHaveText(line);
});
