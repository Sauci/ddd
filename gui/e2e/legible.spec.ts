import type { Locator, Page } from "@playwright/test";
import { CONTROLLER, drift, driftDatatypeIn, dump, openPanel, SENSOR_HUB, unstamp } from "./demo";
import { expect, test } from "./fixtures";

// What the page draws for keyboard use and a readable canvas (16:I11, 16:I12, 16:M14, 16:M19,
// decision 16.3): the arrows' and the focus ring's contrast, measured from computed styles, the
// selected row's mark, forced colours included, a severity told in a word as well as a colour, and
// the reduced-motion preference. No WCAG level is claimed; 3:1 is what a graphic that carries
// meaning is held to, and what each is measured against here.

/** The contrast the page's graphics keep with their ground (WCAG 1.4.11's 3:1). */
const GRAPHIC = 3;

/** The contrast ratio of two `rgb()` strings read off computed styles, WCAG's own formula. */
function contrast(foreground: string, ground: string): number {
  const luminance = (colour: string) => {
    const [r, g, b] = (colour.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
    const linear = (channel: number) => {
      const value = channel / 255;
      return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * linear(r ?? 0) + 0.7152 * linear(g ?? 0) + 0.0722 * linear(b ?? 0);
  };
  const [light, dark] = [luminance(foreground), luminance(ground)].sort((a, b) => b - a);
  return ((light ?? 0) + 0.05) / ((dark ?? 0) + 0.05);
}

/** What every element a selector matches draws its stroke and its outline in, and what is behind
 * it (the first opaque background up its ancestors), read from computed styles. */
function drawnBy(page: Page, selector: string) {
  return page.locator(selector).evaluateAll((nodes) =>
    nodes.map((node) => {
      let ground = "rgb(255, 255, 255)";
      for (let at: Element | null = node; at !== null; at = at.parentElement) {
        const colour = getComputedStyle(at).backgroundColor;
        if (!/, 0\)$/.test(colour) && colour !== "transparent") {
          ground = colour;
          break;
        }
      }
      const style = getComputedStyle(node);
      return {
        stroke: style.stroke,
        outlineStyle: style.outlineStyle,
        outlineWidth: Number.parseFloat(style.outlineWidth),
        outlineColour: style.outlineColor,
        ground,
      };
    }),
  );
}

/** The one ring a selector matches, outline style, width and colour with its ground. */
async function ringOf(page: Page, selector: string) {
  const [ring, ...others] = await drawnBy(page, selector);
  expect(others).toHaveLength(0);
  if (ring === undefined) throw new Error(`${selector} matches nothing`);
  return ring;
}

/** How far the focused element's outline reaches past the box that clips it, in px: the outline's
 * own box (the element's, grown by its offset and width) against the padding box of every ancestor
 * that clips (an `overflow` other than visible). Zero or less is a ring drawn whole. */
function clippedBy(page: Page): Promise<{ ring: number; clip: number; by: string }> {
  return page.evaluate(() => {
    const node = document.activeElement;
    if (node === null) throw new Error("nothing is focused");
    const style = getComputedStyle(node);
    if (style.outlineStyle === "none") throw new Error("the focused element draws no outline");
    const grown = Number.parseFloat(style.outlineWidth) + Number.parseFloat(style.outlineOffset);
    const box = node.getBoundingClientRect();
    let worst = { ring: grown, clip: Number.NEGATIVE_INFINITY, by: "" };
    for (let at = node.parentElement; at !== null; at = at.parentElement) {
      const around = getComputedStyle(at);
      if (around.overflowX === "visible" && around.overflowY === "visible") continue;
      const edge = at.getBoundingClientRect();
      const inside = {
        left: edge.left + at.clientLeft,
        top: edge.top + at.clientTop,
        right: edge.left + at.clientLeft + at.clientWidth,
        bottom: edge.top + at.clientTop + at.clientHeight,
      };
      const past = Math.max(
        inside.left - (box.left - grown),
        inside.top - (box.top - grown),
        box.right + grown - inside.right,
        box.bottom + grown - inside.bottom,
      );
      if (past > worst.clip)
        worst = { ring: grown, clip: past, by: `${at.tagName}.${at.className}` };
    }
    return worst;
  });
}

for (const forced of [false, true]) {
  const mode = forced ? "forced colours" : "normal colours";

  test(`every arrow of a clean graph keeps 3:1 with the canvas, in ${mode}`, async ({
    page,
    gui,
  }) => {
    await page.emulateMedia({ forcedColors: forced ? "active" : "none" });
    await page.goto(gui.address);
    await expect(page.locator(".react-flow__edge-path").first()).toBeVisible();
    const arrows = await drawnBy(page, ".react-flow__edge-path");
    expect(arrows).toHaveLength(7);
    for (const arrow of arrows) {
      expect(contrast(arrow.stroke, arrow.ground)).toBeGreaterThanOrEqual(GRAPHIC);
    }
    // The heads, drawn by React Flow's marker, are as dark as the strokes they end.
    const heads = await drawnBy(page, ".react-flow__arrowhead polyline");
    expect(heads.length).toBeGreaterThan(0);
    for (const head of heads) {
      expect(contrast(head.stroke, head.ground)).toBeGreaterThanOrEqual(GRAPHIC);
    }
  });

  test(`a button reached by Tab shows an outline of 3:1, in ${mode}`, async ({ page, gui }) => {
    await page.emulateMedia({ forcedColors: forced ? "active" : "none" });
    await page.goto(gui.address);
    await expect(page.getByRole("link", { name: "Graph" })).toBeVisible();
    for (let tabs = 0; tabs < 12; tabs += 1) {
      await page.keyboard.press("Tab");
      if (await page.evaluate(() => document.activeElement?.classList.contains("button"))) break;
    }
    const ring = await ringOf(page, ".button:focus-visible");
    expect(ring.outlineStyle).not.toBe("none");
    expect(ring.outlineWidth).toBeGreaterThanOrEqual(2);
    expect(contrast(ring.outlineColour, ring.ground)).toBeGreaterThanOrEqual(GRAPHIC);
  });

  test(`a chooser's field reached by Tab shows an outline of 3:1, and so does its ▾ where a reader's tool focuses it, in ${mode}`, async ({
    page,
    gui,
  }) => {
    await page.emulateMedia({ forcedColors: forced ? "active" : "none" });
    await page.goto(gui.address);
    // The masthead's go-to, the one chooser of every page.
    const field = page.getByRole("combobox", { name: "Go to a variable" });
    await expect(field).toBeVisible();
    for (let tabs = 0; tabs < 12; tabs += 1) {
      await page.keyboard.press("Tab");
      if (await field.evaluate((node) => node === document.activeElement)) break;
    }
    await expect(field).toBeFocused();
    const ring = await ringOf(page, ".combo[data-focused] .combo-field");
    expect(ring.outlineStyle).not.toBe("none");
    expect(ring.outlineWidth).toBeGreaterThanOrEqual(2);
    expect(contrast(ring.outlineColour, ring.ground)).toBeGreaterThanOrEqual(GRAPHIC);

    // Its ▾ is no stop of Tab's (React Aria keeps it out of the order, and a press leaves the
    // focus in the field), but a screen reader may put the focus on it.
    const show = page.getByRole("button", { name: "Show the choices for Go to a variable" });
    await page.keyboard.press("Tab");
    await expect(show).not.toBeFocused();
    await page.keyboard.press("Shift");
    await show.focus();
    await expect(show).toBeFocused();
    const own = await ringOf(page, ".combo-field .react-aria-Button:focus-visible");
    expect(own.outlineStyle).not.toBe("none");
    expect(own.outlineWidth).toBeGreaterThanOrEqual(2);
    expect(contrast(own.outlineColour, own.ground)).toBeGreaterThanOrEqual(GRAPHIC);
  });

  test(`the choice the arrow keys are on in a chooser's list carries an outline of 3:1, in ${mode}`, async ({
    page,
    gui,
  }) => {
    await page.emulateMedia({ forcedColors: forced ? "active" : "none" });
    await page.goto(gui.address);
    const field = page.getByRole("combobox", { name: "Go to a variable" });
    await field.fill("Value");
    await expect(page.getByRole("listbox")).toBeVisible();
    await field.press("ArrowDown");
    // The list never takes the focus: the field keeps it, and names the choice the keys are on.
    await expect(field).toBeFocused();
    await expect(field).toHaveAttribute("aria-activedescendant", /.+/);
    const ring = await ringOf(page, ".combo-choice[data-focus-visible]");
    expect(ring.outlineStyle).not.toBe("none");
    expect(ring.outlineWidth).toBeGreaterThanOrEqual(2);
    expect(contrast(ring.outlineColour, ring.ground)).toBeGreaterThanOrEqual(GRAPHIC);
  });

  test(`the selected row of a table carries an outline of its own, in ${mode}`, async ({
    page,
    gui,
  }) => {
    drift(gui.directory);
    await page.emulateMedia({ forcedColors: forced ? "active" : "none" });
    await page.goto(gui.address);
    await page.getByRole("link", { name: "Findings" }).click();
    const rows = page.getByRole("row", { name: "definition-mismatch" });
    await rows.first().click();
    await expect(page.getByRole("complementary", { name: "definition-mismatch" })).toBeVisible();
    const ring = await ringOf(page, ".react-aria-Row[data-selected]");
    expect(ring.outlineStyle).not.toBe("none");
    expect(ring.outlineWidth).toBeGreaterThanOrEqual(2);
    expect(contrast(ring.outlineColour, ring.ground)).toBeGreaterThanOrEqual(GRAPHIC);
    // And only the selected one: the other row of the pair draws none.
    await expect(await rows.nth(1).evaluate((node) => getComputedStyle(node).outlineStyle)).toBe(
      "none",
    );
  });

  test(`a link-styled button focused after a key was pressed keeps its outline whole, in ${mode}`, async ({
    page,
    gui,
  }) => {
    drift(gui.directory);
    await page.emulateMedia({ forcedColors: forced ? "active" : "none" });
    await page.goto(gui.address);
    // Controller's name in the Table's own cell, a link-styled button in a clipping cell.
    await page.getByRole("link", { name: "Table" }).click();
    const component = page.getByRole("button", { name: "Controller", exact: true });
    await page.keyboard.press("Shift");
    await component.focus();
    await expect(component).toBeFocused();
    expect((await clippedBy(page)).clip).toBeLessThanOrEqual(0);
    // The measure can see a cut: the same ring pushed 30 px out is past the cell's edge.
    await component.evaluate((node) => {
      node.style.outlineOffset = "30px";
    });
    expect((await clippedBy(page)).clip).toBeGreaterThan(0);
    await component.evaluate((node) => {
      node.style.outlineOffset = "";
    });

    // The unit of a declaration in a component's table, and the finding panel's Open link.
    await component.click();
    const unit = page.getByRole("button", { name: "Set the unit of ValueA" });
    await page.keyboard.press("Shift");
    await unit.focus();
    await expect(unit).toBeFocused();
    expect((await clippedBy(page)).clip).toBeLessThanOrEqual(0);

    await page.goto(gui.address);
    await page.getByRole("link", { name: "Findings" }).click();
    await page
      .getByRole("row", { name: /definition-mismatch/ })
      .first()
      .click();
    const open = page.getByRole("complementary").getByRole("link", { name: /^Open / });
    await page.keyboard.press("Shift");
    await open.focus();
    await expect(open).toBeFocused();
    expect((await clippedBy(page)).clip).toBeLessThanOrEqual(0);
  });
}

test("an info is toned as the Findings tab tones it, and said in a word, wherever it is shown", async ({
  page,
  gui,
}) => {
  // ValueH with no id reports `missing-id`, an info: neutral on the tab, so neutral on the
  // component's page and in its panel, never a warning's amber, with the word beside it.
  unstamp(gui.directory, CONTROLLER, "ValueH");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  const row = page.getByRole("row", { name: /missing-id/ });
  await expect(row.locator(".chip")).toHaveClass(/neutral/);
  await expect(row).toHaveAccessibleName(/missing-id info/);

  const panel = await openPanel(page, gui.address, "ValueH");
  const finding = panel.getByRole("listitem").filter({ hasText: "missing-id" });
  await expect(finding.locator(".chip")).toHaveClass(/neutral/);
  await expect(finding).toContainText("missing-id info");
  const cell = page.getByRole("row", { name: /ValueH/ }).locator(".chip");
  await expect(cell).toHaveClass(/neutral/);
  await expect(page.getByRole("row", { name: /ValueH/ })).toContainText("missing-id info");
});

test("a cell of several findings reads as words, each severity apart from the next chip", async ({
  page,
  gui,
}) => {
  // ValueE without its id and drifted: Controller's row for it holds several findings, `missing-id`
  // among them, side by side, which read "missing-id infodefinition-mismatch error"
  // where the word ran into the next chip.
  unstamp(gui.directory, CONTROLLER, "ValueE");
  drift(gui.directory, "ValueE", "kHz");
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const cell = page
    .getByRole("row", { name: /ValueE/ })
    .getByRole("gridcell")
    .filter({ hasText: "missing-id" });
  await expect.poll(() => cell.locator(".chip").count()).toBeGreaterThanOrEqual(2);
  // Each chip's check, a space, its severity word, then a space and the next: words, however many.
  const words = /^\S+ (?:info|warning|error)(?: \S+ (?:info|warning|error))+$/;
  await expect(cell).toHaveAccessibleName(words);
  // And in the text a reader copies.
  expect((await cell.innerText()).trim()).toMatch(words);
});

test("an error and a warning are said in their words beside their chips", async ({ page, gui }) => {
  drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByRole("row", { name: /definition-mismatch/ }).first()).toHaveAccessibleName(
    /definition-mismatch error/,
  );
});

/** The widest finding a table's Check column is asked to hold: the longest name among the checks
 * the server knows - ddd's own, then the open project's plugins' - filed under the longest word a
 * severity is said in that it can carry, any of the three where a project may change its severity.
 * Asked of the server as `analysed` (fixtures.ts) asks it, so that a check added with a longer name
 * is the one measured. */
async function widestFinding(address: string): Promise<{ check: string; severity: string }> {
  const token = new URL(address).searchParams.get("token");
  const response = await fetch(new URL("/api/checks", address), {
    headers: { authorization: `Bearer ${token}` },
  });
  const { checks } = (await response.json()) as {
    checks: { check: string; default_severity: string; overridable: boolean }[];
  };
  const [widest] = [...checks].sort((a, b) => b.check.length - a.check.length);
  if (widest === undefined) throw new Error("the server knows no check");
  const words = widest.overridable ? ["error", "warning", "info"] : [widest.default_severity];
  const [severity = widest.default_severity] = words.sort((a, b) => b.length - a.length);
  return { check: widest.check, severity };
}

/** Every reply to `path` the page reads from now on, its first finding filed as `widest` says. */
async function filedAs(page: Page, path: string, widest: { check: string; severity: string }) {
  await page.route(
    (url) => url.pathname === path,
    async (route) => {
      const response = await route.fetch();
      const reply = (await response.json()) as { findings: { check: string; severity: string }[] };
      const [first] = reply.findings;
      if (first !== undefined) Object.assign(first, widest);
      await route.fulfill({ response, json: reply });
    },
  );
}

/** How far a row's severity word reaches past what its cell shows, in px: the word's own box
 * against its cell's, less the cell's padding. An ellipsis cuts what is drawn, not the box, which is
 * what this measures. Zero or less is a word drawn whole. */
function wordPast(row: Locator): Promise<number> {
  return row.locator(".severity-word").evaluate((word) => {
    const cell = word.closest('[role="rowheader"], [role="gridcell"]');
    if (cell === null) throw new Error("the word stands in no cell");
    const inside = cell.getBoundingClientRect().right;
    const padding = Number.parseFloat(getComputedStyle(cell).paddingRight);
    return word.getBoundingClientRect().right - (inside - padding);
  });
}

for (const width of [1280, 375]) {
  test(`the longest check's severity word is drawn whole in the Findings table and in Compare's, ${width}px wide`, async ({
    page,
    gui,
  }) => {
    const widest = await widestFinding(gui.address);
    // A baseline of the copy as it is served, then two drifts: findings for the Findings tab, and
    // a changed interface for Compare's table (compare.spec.ts).
    dump(gui.directory, "demo.ddd.json", "baseline.json");
    drift(gui.directory);
    driftDatatypeIn(gui.directory, SENSOR_HUB, "ValueA", "uint16");
    await filedAs(page, "/api/findings", widest);
    await filedAs(page, "/api/compare", widest);
    await page.setViewportSize({ width, height: 720 });
    const named = new RegExp(`${widest.check} ${widest.severity}`);

    await page.goto(gui.address);
    await page.getByRole("link", { name: "Findings", exact: true }).click();
    const finding = page.getByRole("row", { name: named });
    await expect(finding).toBeVisible();
    expect(await wordPast(finding)).toBeLessThanOrEqual(0);

    await page.getByRole("link", { name: "Compare" }).click();
    await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
    await page.getByRole("button", { name: "Compare" }).click();
    const compared = page.getByRole("grid", { name: "Findings" }).getByRole("row", { name: named });
    await expect(compared).toBeVisible();
    expect(await wordPast(compared)).toBeLessThanOrEqual(0);
  });
}

test("a search's Enter moves the view at once under reduced motion", async ({ page, gui }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(gui.address);
  await expect(page.locator(".module").first()).toBeVisible();
  const canvas = page.getByRole("region", { name: "Modules" });
  const box = await canvas.boundingBox();
  if (box === null) throw new Error("the canvas draws no box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, 300);
  const search = page.getByRole("textbox", { name: "Search modules" });
  await search.fill("Sensor");
  // The viewport's transform is sampled every frame for 600 ms from the keypress: a flight would
  // pass through several, a jump is one.
  await expect(page.locator(".react-flow__viewport")).toBeVisible();
  const seen = await page.evaluate(async () => {
    const viewport = document.querySelector(".react-flow__viewport") as HTMLElement;
    const transforms = new Set<string>();
    const start = performance.now();
    const sample = () => {
      transforms.add(viewport.style.transform);
      if (performance.now() - start < 600) requestAnimationFrame(sample);
    };
    sample();
    const field = document.querySelector('input[aria-label="Search modules"]') as HTMLElement;
    field.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await new Promise((done) => setTimeout(done, 650));
    return transforms.size;
  });
  expect(seen).toBeLessThanOrEqual(2);
});
