import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { CONTROLLER, drift, driftMax, EVENT_LOGGER, held, renameValueA } from "./demo";
import { expect, test } from "./fixtures";

// The canvas's own actions and states - no dictionary, Fit, the module search and its Enter,
// hovering a module, the undeclared-variable banner reached from an arrow, the drawing and layout
// states and the layout worker failing, a module not loaded, a module's badge, an arrow reached
// by the keyboard, its own zoom buttons, a layout in ranks only and a later layout failing - and
// the components table's summary line while the findings update, and a row opening its component
// (spec 2026-10-08 §4).

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

test("Fit returns the viewport to the one the canvas opened on", async ({ page, gui }) => {
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
  // Zoomed out first, so that the search starts from a view the reader moved rather than the one
  // the canvas opened on, with SensorHub still off its middle, which the next step pins.
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
  // The first graph the page asks for alone, held until the journey has seen what is shown
  // meanwhile; any later one goes straight through.
  const release = await held(page, "/api/graph");
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
  // The layout worker's own script, the one request between the graph and its layout (`useLayout`
  // starts the worker once the graph is there to lay out): held, the worker never starts, and
  // nothing is laid out until it is let through.
  const release = await held(page, /^\/assets\/layoutWorker-[^/]+\.js$/);
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
  // address that no longer exists (`WORKER_FAILED`, lib/layoutAnswers.ts), and on every request:
  // the page creates a worker that failed to start once more (`createdAgain`), which is answered
  // the same. Taken away before the reload the banner asks for, which is served the worker itself.
  const worker = "**/assets/layoutWorker-*.js";
  let asked = 0;
  await page.route(worker, (route) => {
    asked += 1;
    return route.fulfill({ status: 404, contentType: "text/plain", body: "not found" });
  });
  await page.goto(gui.address);
  await expect(page.getByRole("alert")).toHaveText(
    "The layout worker stopped; reload the page to try again.",
  );
  // Said once the worker created once more failed too: its script asked for twice, no more.
  expect(asked).toBe(2);
  await expect(page.getByText("Laying the project out…", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);

  await page.unroute(worker);
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

/**
 * The demo with a key the component model does not have, added to Controller's `component` block.
 * The model forbids one (`additionalProperties: false`, schemas/ddd_component.schema.json), so
 * the file fails `schema`, one of the checks after which a file did not load (`LOAD_CHECKS`,
 * lsp/navigation.py). It still parses, so it is still a component (`kind_of`, session.py) and
 * the canvas still draws its module. Cut in half, as this file's first journey cuts it, it would
 * be of kind `unknown` and draw no module at all.
 */
function unloaded(directory: string): void {
  const path = join(directory, CONTROLLER);
  const before = readFileSync(path, "utf8");
  const after = before.replace(
    '"name": "Controller",',
    '"name": "Controller",\n    "unexpected": true,',
  );
  if (after === before) throw new Error(`${path} no longer names its component Controller`);
  writeFileSync(path, after, "utf8");
}

test("a module whose file does not load is drawn as not loaded, named by its file", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", unloaded);
  await page.goto(gui.address);
  // Named by its file's stem, as the file did not load far enough to name its component (`_module`,
  // api.py), and said not to have loaded (`ModuleNode.tsx`).
  const module = page.locator(".module.unloaded");
  await expect(
    module.getByRole("button", { name: "controller (not loaded)", exact: true }),
  ).toBeVisible();
  // Its file holds an error, `schema`, which a module that did not load counts in no badge.
  await expect(module.getByRole("img")).toHaveCount(0);
  for (const name of ["SensorHub", "UserInterface", "EventLogger"]) {
    await expect(moduleOf(page, name)).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toHaveCount(0);
  // A project with a file that did not load has no dictionary, so no arrows, and says so.
  await expect(page.getByRole("status").filter({ hasText: "no dictionary" })).toHaveText(
    "This project has no dictionary, so its modules are drawn without arrows.",
  );
});

test("a module's badge counts its warnings, and only its errors once it has any", async ({
  page,
  gui,
}) => {
  // ParameterA is Controller's own calibration, `scope` "local": a uint16 at a quarter of a hertz
  // a count, so it can hold at most 16383.75 Hz. A greatest limit of 99999 is then
  // `limits-out-of-range`, a warning (diagnostics.py), filed on Controller alone. Written plainly,
  // so the watcher sees it: the badge comes with the revision that reads it.
  driftMax(gui.directory, CONTROLLER, "ParameterA", 99999);
  await page.goto(gui.address);
  const controller = moduleOf(page, "Controller");
  // The badge is announced as the one picture it is, named by what it counts (`ModuleNode.tsx`):
  // a number alone would not say whether it counts errors or warnings. Its count is read off the
  // running page.
  const warned = controller.getByRole("img", { name: "1 warning", exact: true });
  await expect(warned).toHaveText("1");
  await expect(warned).toHaveClass("badge warning");
  // The other three modules have no finding, so no badge.
  for (const name of ["SensorHub", "UserInterface", "EventLogger"]) {
    await expect(moduleOf(page, name).getByRole("img")).toHaveCount(0);
  }

  // ValueA read by Controller in another unit than SensorHub produces it: `definition-mismatch`,
  // an error, filed on Controller's reading (analysis.py) and mirrored on SensorHub's declaration,
  // the other side of it (`_mirrors`, lsp/diagnostics.py). The warning stays.
  drift(gui.directory);
  // Errors take the badge while there are any: it counts them alone, and stays one badge.
  const errored = controller.getByRole("img", { name: "1 error", exact: true });
  await expect(errored).toHaveText("1");
  await expect(errored).toHaveClass("badge error");
  await expect(controller.getByRole("img")).toHaveCount(1);

  // One error and one warning read alike, so ValueB is read in another unit too: two errors
  // beside the one warning, and the badge counts the two.
  drift(gui.directory, "ValueB", "mV");
  const errors = controller.getByRole("img", { name: "2 errors", exact: true });
  await expect(errors).toHaveText("2");
  await expect(controller.getByRole("img")).toHaveCount(1);
});

test("an arrow reached by the keyboard says what is wrong, until the keyboard leaves the arrows", async ({
  page,
  gui,
}) => {
  // In disagreement, so that the arrow has something wrong to say: an agreed arrow says only
  // what it carries.
  drift(gui.directory);
  await page.goto(gui.address);
  const arrow = page.getByRole("button", { name: "SensorHub to Controller: 2 variables, error" });
  await expect(arrow).toBeVisible();
  // Reached the way a keyboard reaches it, one Tab at a time, as units.spec.ts's "an arrow in
  // disagreement about two variables asks which, from the keyboard too" reaches it.
  for (let stop = 0; stop < 50; stop += 1) {
    if (await arrow.evaluate((element) => element === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(arrow).toBeFocused();
  // Its tooltip shows while it is reached (`edgesOf`'s `onFocus`, FlowEdge.tsx's `data.active`):
  // what the arrow carries, then each disagreement's check and the analysis's own sentence.
  const tooltip = page.getByRole("tooltip");
  await expect(tooltip.locator(".objects")).toHaveText("ValueA, ValueB");
  await expect(tooltip.getByRole("listitem")).toHaveText([
    "definition-mismatch 'ValueA' is declared differently by component 'Controller' than by " +
      "'SensorHub' (unit: 'rpm' != '%')",
  ]);
  // And it is the arrow's description, through its `aria-describedby`: what a screen reader reads
  // out of an arrow it has reached.
  await expect(arrow).toHaveAccessibleDescription(
    "ValueA, ValueB definition-mismatch 'ValueA' is declared differently by component " +
      "'Controller' than by 'SensorHub' (unit: 'rpm' != '%')",
  );

  // Each next Tab reaches another arrow, whose own tooltip takes this one's place, until the
  // focus leaves the arrows for the first module's name: no tooltip is left then (`onBlur`).
  for (let stop = 0; stop < 10; stop += 1) {
    await page.keyboard.press("Tab");
    if (await page.evaluate(() => document.activeElement?.closest(".react-flow__edge") === null)) {
      break;
    }
  }
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeFocused();
  await expect(tooltip).toHaveCount(0);
});

test("the canvas's own buttons zoom it in and out, and stop zooming out at its least zoom", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  const opening = await viewportOf(page);
  // React Flow's own buttons (`<Controls>`, GraphPage.tsx), named in its own words.
  const zoomIn = page.getByRole("button", { name: "Zoom In", exact: true });
  const zoomOut = page.getByRole("button", { name: "Zoom Out", exact: true });
  await expect(zoomIn).toBeVisible();
  await expect(zoomOut).toBeVisible();

  // A press scales the viewport by 1.2 (React Flow's `zoomIn`), and the other one back: each zoom
  // to three places, within half a thousandth.
  await zoomIn.click();
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeCloseTo(opening.zoom * 1.2, 3);
  await zoomOut.click();
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeCloseTo(opening.zoom, 3);

  // Out, press after press, each waited for by the zoom it lowers, until the button is turned
  // off at the canvas's least zoom (`MIN_ZOOM`, lib/canvas.ts): five presses from the demo's
  // opening zoom of 1.11494 (measured in Chrome on the Linux development PC).
  for (let presses = 0; presses < 10 && (await zoomOut.isEnabled()); presses += 1) {
    const before = (await viewportOf(page)).zoom;
    await zoomOut.click();
    await expect.poll(async () => (await viewportOf(page)).zoom).toBeLessThan(before);
  }
  await expect(zoomOut).toBeDisabled();
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeCloseTo(0.5, 3);
});

test("a project too deep for the full layout is laid out in ranks only, and says so", async ({
  page,
  chainedGui,
}) => {
  await page.goto(chainedGui.address);
  // dagre overflows its stack in the layout worker on the chain `chainedGui` serves, 2,000
  // components deep, and the worker ranks the modules itself (`layoutOf`, lib/layout.ts). Said
  // quietly above the canvas, as a note and not as an alert: the canvas is drawn all the same.
  await expect(
    page.getByText("Laid out in ranks only: the project is too large for the full layout.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  // The canvas opens on its first rank, the chain's first module alone, at its least zoom
  // (`openingViewport`, lib/canvas.ts), within half a thousandth.
  await expect(page.getByRole("button", { name: "C00000", exact: true })).toBeVisible();
  await expect.poll(async () => (await viewportOf(page)).zoom).toBeCloseTo(0.5, 3);
});

test("a layout worker that fails once the canvas is drawn leaves the canvas, with its alert above", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  // Drawn, so the worker has answered once.
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  // No route and no project reaches this state: the worker's script is fetched once per canvas,
  // and its `layoutOf` answers an error only for an input the server never sends. So an error is
  // thrown in the worker's own thread and left uncaught, as a worker that crashed throws one
  // (planning ruling 10): the page's `Worker` hears it as `error` (`useLayout`'s `onerror`). One
  // that has answered is not made again (`createdAgain`, lib/layoutAnswers.ts), so the page says
  // the worker stopped.
  const worker = page.workers().find((each) => /layoutWorker-/.test(each.url()));
  if (worker === undefined) throw new Error("the page runs no layout worker");
  await worker.evaluate(() => {
    setTimeout(() => {
      throw new Error("the layout worker failed");
    });
  });
  const alert = page.getByRole("alert");
  await expect(alert).toHaveText("The layout worker stopped; reload the page to try again.");
  // The canvas is kept as it was drawn: the four modules, and its own tools.
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  await expect(page.getByRole("textbox", { name: "Search modules" })).toBeVisible();
  for (const name of ["Tidy", "Fit"]) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  }
  // The alert stands above it (`layoutScreen`'s `errorMessage`), wholly: within no pixel.
  const canvas = page.getByRole("region", { name: "Modules" });
  await expect
    .poll(async () => {
      const [said, drawn] = await Promise.all([alert.boundingBox(), canvas.boundingBox()]);
      return said !== null && drawn !== null && said.y + said.height <= drawn.y;
    })
    .toBe(true);
});

/** A component's row of the Table tab, by the name its button reads (skeleton.spec.ts's own). */
const componentRow = (page: Page, name: string): Locator =>
  page.getByRole("row").filter({ has: page.getByRole("button", { name, exact: true }) });

test("a row of the components table opens its component, pressed beside its name or on Enter", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table", exact: true }).click();
  // Pressed beside its name: on Controller's Warnings cell, which holds no button of its own.
  await componentRow(page, "Controller").getByRole("gridcell").nth(1).click();
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();
  // The path in the address, percent-encoded or not, ends in the file's own name.
  await expect(page).toHaveURL(/\/component\?file=.*controller\.ddd\.json$/);
  await page.goBack();
  const grid = page.getByRole("grid", { name: "Components" });
  await expect(grid).toBeVisible();

  // By the keyboard: Tab until a row of the table has the focus, ArrowDown to SensorHub's, and
  // Enter on it.
  for (let stop = 0; stop < 50; stop += 1) {
    const onRow = await grid.evaluate(
      (element) =>
        element.contains(document.activeElement) &&
        document.activeElement?.getAttribute("role") === "row",
    );
    if (onRow) break;
    await page.keyboard.press("Tab");
  }
  await expect(grid.locator('[role="row"]:focus')).toHaveCount(1);
  const sensorHub = componentRow(page, "SensorHub");
  for (let step = 0; step < 10; step += 1) {
    if (await sensorHub.evaluate((element) => element === document.activeElement)) break;
    await page.keyboard.press("ArrowDown");
  }
  await expect(sensorHub).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "SensorHub", level: 1 })).toBeVisible();
  await expect(page).toHaveURL(/\/component\?file=.*sensor_hub\.ddd\.json$/);
});
