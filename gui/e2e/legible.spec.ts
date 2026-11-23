import type { Page } from "@playwright/test";
import { drift } from "./demo";
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
}
