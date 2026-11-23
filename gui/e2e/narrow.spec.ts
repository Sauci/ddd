import type { Page } from "@playwright/test";
import { drift, held } from "./demo";
import { expect, test } from "./fixtures";

// The page in a narrow window (16:M9), whether the window shares its screen, is a phone's, or is
// magnified. Nothing reaches past the window's edge to scroll the page sideways - the masthead
// wraps its go-to onto a line of its own and narrows it, the project's tabs wrap, a long table
// scrolls in its own box - and a panel standing under the table it was opened from, out of view,
// is scrolled into it.

/** How far the page reaches past the window's right edge, in px: what a reader would scroll
 * sideways to see. */
function sideways(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

for (const width of [375, 320]) {
  test(`no page scrolls sideways in a window ${width}px wide`, async ({ page, gui }) => {
    drift(gui.directory);
    await page.setViewportSize({ width, height: 812 });
    const heading = (name: string) => page.getByRole("heading", { name, level: 1 });

    await page.goto(gui.address);
    await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
    // The masthead's go-to on a line of its own, and the tabs on more than one.
    const goTo = page.getByRole("combobox", { name: "Go to a variable" });
    const projects = page.getByRole("button", { name: "Projects" });
    expect((await goTo.boundingBox())?.y).toBeGreaterThan((await projects.boundingBox())?.y ?? 0);
    const graph = await page.getByRole("link", { name: "Graph" }).boundingBox();
    const compare = await page.getByRole("link", { name: "Compare" }).boundingBox();
    expect(compare?.y).toBeGreaterThan(graph?.y ?? 0);
    expect(await sideways(page)).toBe(0);

    await page.getByRole("link", { name: "Table" }).click();
    await expect(page.getByRole("grid", { name: "Components" })).toBeVisible();
    expect(await sideways(page)).toBe(0);

    await page.getByRole("link", { name: "Units" }).click();
    await page.getByRole("grid", { name: "Units" }).getByRole("row", { name: /Hz/ }).click();
    await expect(page.getByRole("complementary", { name: "Hz" })).toBeVisible();
    expect(await sideways(page)).toBe(0);

    // A type's panel and its tables: a structure's members, and where an enumeration is used.
    await page.getByRole("link", { name: "Types" }).click();
    const types: Record<string, number> = {};
    for (const [type, table] of [
      ["SensorDiagnosis_t", "Members"],
      ["DriverState_t", "Where it is used"],
    ] as const) {
      await page.getByRole("grid", { name: "Types" }).getByRole("row", { name: type }).click();
      const panel = page.getByRole("complementary", { name: type });
      await expect(panel.getByRole("heading", { name: table })).toBeVisible();
      types[type] = await sideways(page);
    }
    expect(types).toEqual({ SensorDiagnosis_t: 0, DriverState_t: 0 });

    await page.getByRole("link", { name: "Findings" }).click();
    await page
      .getByRole("row", { name: /definition-mismatch/ })
      .first()
      .click();
    await expect(page.getByRole("complementary", { name: "definition-mismatch" })).toBeVisible();
    expect(await sideways(page)).toBe(0);

    await page.getByRole("button", { name: "Projects" }).click();
    await expect(heading("Open a project")).toBeVisible();
    expect(await sideways(page)).toBe(0);

    // The declarations' table scrolls sideways in its own box, its unit cells past the box's edge:
    // a row opens the panel, as a reader opens it there.
    await page.goto(gui.address);
    await page.getByRole("button", { name: "Controller", exact: true }).click();
    await page
      .getByRole("grid", { name: "Declarations of Controller" })
      .getByRole("row", { name: /ValueA/ })
      .click();
    await expect(page.getByRole("complementary", { name: "ValueA" })).toBeVisible();
    expect(await sideways(page)).toBe(0);

    // Its values by their address, its Shape cell being past the box's edge too.
    const values = new URL(page.url());
    values.searchParams.set("variable", "MapA");
    values.searchParams.set("view", "values");
    await page.goto(values.href);
    await expect(heading("MapA")).toBeVisible();
    expect(await sideways(page)).toBe(0);
  });
}

test("a panel opened under its table, out of view in a window 800 by 600, is scrolled into view", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page
    .getByRole("grid", { name: "Declarations of Controller" })
    .getByRole("row", { name: /ValueB/ })
    .click();
  const panel = page.getByRole("complementary", { name: "ValueB" });
  await expect(panel.getByRole("heading", { name: "ValueB", level: 2 })).toBeInViewport();
  // The panel itself, once it has read its variable: its keys, not its heading alone at the
  // window's foot.
  await expect(panel.getByRole("grid", { name: "Keys of ValueB" })).toBeInViewport({ ratio: 0.5 });
});

/**
 * A change of page that opens a panel (16:M9, 16:I13): the masthead's go-to opens ParameterA on
 * Controller's page, its panel standing under the declarations in a window 800 by 600. The panel
 * is what the reader asked for: it is scrolled into view as soon as it is drawn, while it reads
 * its variable, and its heading takes the focus, where the page's heading takes it on a change of
 * page that opens none; read, the panel shows itself, its keys and all.
 */
test("a variable the masthead's go-to opens in a window 800 by 600 has its panel in view, the focus on its heading", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  await page.goto(gui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  await goTo.pressSequentially("ParameterA");
  await expect(page.getByRole("option", { name: "ParameterA" })).toBeVisible();
  const panel = page.getByRole("complementary", { name: "ParameterA" });
  const heading = panel.getByRole("heading", { name: "ParameterA", level: 2 });
  const release = await held(page, "/api/variable");
  try {
    await goTo.press("Enter");
    await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();
    await expect(panel.getByText("Reading ParameterA…")).toBeVisible();
    await expect(heading).toBeInViewport();
    await expect(heading).toBeFocused();
  } finally {
    release();
  }
  await expect(panel.getByRole("grid", { name: "Keys of ParameterA" })).toBeInViewport({
    ratio: 0.5,
  });
  await expect(heading).toBeFocused();
});
