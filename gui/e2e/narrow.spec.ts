import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import {
  drift,
  emptyComponent,
  gainLink,
  held,
  moreComponents,
  moreScalarTypes,
  namingAScalarType,
  PAST_THE_WAITS,
  twoFrames,
  wheelFromFocus,
} from "./demo";
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

/**
 * The masthead's go-to used on the component page it opens on (16:M9, 16:I13, ruling B11-44):
 * ParameterA reached by name from Controller's own page in a window 800 by 600, with no panel open
 * and with ValueA's opened first from its row. The page does not change, but the reader asked for
 * that panel by name: as on a change of page, it is scrolled into view while it reads its variable,
 * its heading taking the focus, and read, it shows itself, its keys and all.
 */
for (const before of ["no panel", "ValueA's panel"] as const) {
  test(`the masthead's go-to used on the page it opens on, ${before} open, in a window 800 by 600, has its panel in view, the focus on its heading`, async ({
    page,
    gui,
  }) => {
    await page.setViewportSize({ width: 800, height: 600 });
    await page.goto(gui.address);
    await page.getByRole("button", { name: "Controller", exact: true }).click();
    const declarations = page.getByRole("grid", { name: "Declarations of Controller" });
    await expect(declarations).toBeVisible();
    if (before === "ValueA's panel") {
      await declarations.getByRole("row", { name: /ValueA/ }).click();
      await expect(
        page
          .getByRole("complementary", { name: "ValueA" })
          .getByRole("grid", { name: "Keys of ValueA" }),
      ).toBeVisible();
    }
    const goTo = page.getByRole("combobox", { name: "Go to a variable" });
    await goTo.pressSequentially("ParameterA");
    await expect(page.getByRole("option", { name: "ParameterA" })).toBeVisible();
    const panel = page.getByRole("complementary", { name: "ParameterA" });
    const heading = panel.getByRole("heading", { name: "ParameterA", level: 2 });
    const release = await held(page, "/api/variable");
    try {
      await goTo.press("Enter");
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
}

/** The address of Controller's page with ParameterA's panel open, as the page writes it once
 * ParameterA's row is selected there. */
async function parameterAddress(page: Page, address: string): Promise<string> {
  await page.goto(address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page
    .getByRole("grid", { name: "Declarations of Controller" })
    .getByRole("row", { name: /ParameterA/ })
    .click();
  await expect(page).toHaveURL(/[?&]variable=ParameterA$/);
  return page.url();
}

/**
 * A page loaded anew at an address naming a selection (16:M9, ruling B11-44): a bookmark or a
 * typed address opening Controller's page on ParameterA, in a window 800 by 600, loaded from
 * another page so that the browser has no scroll of its own to restore. The panel stands under the
 * declarations, out of view: it is scrolled into view once drawn. The focus is left where the
 * browser starts a page it loads, on none of the page's own controls.
 */
test("a page loaded anew at an address naming a variable, in a window 800 by 600, has its panel in view and moves no focus", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  const parameter = await parameterAddress(page, gui.address);
  await page.goto(gui.address);
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
  await page.goto(parameter);
  const panel = page.getByRole("complementary", { name: "ParameterA" });
  await expect(panel.getByRole("grid", { name: "Keys of ParameterA" })).toBeInViewport({
    ratio: 0.5,
  });
  await expect(panel.getByRole("heading", { name: "ParameterA", level: 2 })).toBeInViewport();
  expect(await page.evaluate(() => document.activeElement === document.body)).toBe(true);
});

/**
 * The same address loaded anew while Controller's file is read slowly (16:M9, 16:I13, ruling
 * B11-45): an assistive technology moves the focus on to the masthead's go-to meanwhile, by no key
 * and no pointer. The panel, drawn once the file is read, is left where it stands, out of view:
 * the page stays where the focus was moved.
 */
test("a variable's address loaded anew, the focus moved meanwhile by no key and no pointer, leaves the page where the focus is", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  const parameter = await parameterAddress(page, gui.address);
  await page.goto(gui.address);
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  const release = await held(page, "/api/file");
  try {
    await page.goto(parameter);
    await expect(page.getByText("Reading the file…")).toBeVisible();
    await goTo.focus();
  } finally {
    release();
  }
  const panel = page.getByRole("complementary", { name: "ParameterA" });
  await expect(panel.getByRole("grid", { name: "Keys of ParameterA" })).toBeVisible();
  await twoFrames(page);
  await expect(goTo).toBeFocused();
  await expect(goTo).toBeInViewport();
  await expect(panel.getByRole("heading", { name: "ParameterA", level: 2 })).not.toBeInViewport();
});

/**
 * A tab of the project, its address naming a selection, loaded anew (16:M9, ruling B11-44): the
 * Graph's address of ValueA, in a window 800 by 600. ValueA's panel stands under the canvas, out of
 * view, and is drawn once the tab has drawn its canvas, after the page's heading: it is scrolled
 * into view as it is drawn, and the focus is left where the browser starts a page it loads.
 */
test("the Graph loaded anew at a variable's address, in a window 800 by 600, has its panel in view and moves no focus", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  await page.goto(gui.address);
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
  const graph = new URL(page.url());
  graph.pathname = "/project";
  graph.search = "?variable=ValueA";
  await page.goto(graph.href);
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await expect(panel.getByRole("grid", { name: "Keys of ValueA" })).toBeVisible();
  await twoFrames(page);
  await expect(panel.getByRole("heading", { name: "ValueA", level: 2 })).toBeInViewport();
  expect(await page.evaluate(() => document.activeElement === document.body)).toBe(true);
});

/**
 * The wheel turned before the panel a change of page opens is drawn (16:M9, 16:I13, ruling
 * B11-46): the go-to from the Graph opens ParameterA on Controller's page, in a window 800 by 600,
 * Controller's file held back, and the reader turns the wheel once over the page as it reads - a
 * page still too short to scroll. The focus and the view go together: the panel's heading takes
 * the focus, and the panel is scrolled into view with it.
 */
test("a wheel turned as the go-to's change of page reads its file, in a window 800 by 600, leaves the panel's heading focused in view", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  await page.goto(gui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  await goTo.pressSequentially("ParameterA");
  await expect(page.getByRole("option", { name: "ParameterA" })).toBeVisible();
  const release = await held(page, "/api/file");
  try {
    await goTo.press("Enter");
    await expect(page.getByText("Reading the file…")).toBeVisible();
    await page.mouse.move(400, 400);
    await page.mouse.wheel(0, 200);
  } finally {
    release();
  }
  const panel = page.getByRole("complementary", { name: "ParameterA" });
  const heading = panel.getByRole("heading", { name: "ParameterA", level: 2 });
  await expect(panel.getByRole("grid", { name: "Keys of ParameterA" })).toBeInViewport({
    ratio: 0.5,
  });
  await expect(heading).toBeFocused();
  await expect(heading).toBeInViewport();
});

/**
 * The wheel still turning as the panel a change of page opens is drawn (16:M9, 16:I13, ruling
 * B11-48): the go-to from the Graph opens ParameterA on Controller's page, in a window 800 by 600,
 * Controller's file held back. The reader's wheel turns from the moment the panel's heading takes
 * the focus, through the frames in which the page goes on laying itself out - the declarations'
 * table above the panel sizing its box - and scrolls nothing itself. The heading was shown in the
 * very step it took the focus in, before any of the wheel's events could come: the panel stands in
 * view, its heading focused.
 */
test("a wheel turning as the go-to's change of page draws its panel, in a window 800 by 600, leaves the panel's heading focused in view", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  await page.goto(gui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  await goTo.pressSequentially("ParameterA");
  await expect(page.getByRole("option", { name: "ParameterA" })).toBeVisible();
  const turned = await wheelFromFocus(page, "ParameterA", 30);
  const release = await held(page, "/api/file");
  try {
    await goTo.press("Enter");
    await expect(page.getByText("Reading the file…")).toBeVisible();
  } finally {
    release();
  }
  const panel = page.getByRole("complementary", { name: "ParameterA" });
  const heading = panel.getByRole("heading", { name: "ParameterA", level: 2 });
  await expect(heading).toBeFocused();
  await turned();
  await expect(panel.getByRole("grid", { name: "Keys of ParameterA" })).toBeInViewport({
    ratio: 0.5,
  });
  await expect(heading).toBeFocused();
  await expect(heading).toBeInViewport();
});

/**
 * A change of page whose panel is drawn past a short wait, under a table taller than the window
 * (16:M9, 16:I13, ruling B11-47): GainA's link to Gain_t opens the Types tab of a project with
 * thirty more types, in a window 800 by 600, the project's types held back longer than the page
 * waits for them. Gain_t's panel, drawn at last under the table, stays where it falls: the page's
 * heading keeps the focus it took meanwhile, and the page is not scrolled away from it.
 */
test("a type drawn past a short wait under a table taller than a window 800 by 600 leaves the page and the focus on the page's heading", async ({
  page,
  copiedGui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  const gui = await copiedGui("demo", (directory) => {
    namingAScalarType(directory);
    moreScalarTypes(directory, 30);
  });
  const link = await gainLink(page, gui.address);
  const heading = page.getByRole("heading", { name: "DemoDevice", level: 1 });
  const release = await held(page, "/api/types");
  try {
    await link.click();
    await expect(page.getByText("Reading the project's types…")).toBeVisible();
    await expect(heading).toBeFocused();
    await page.waitForTimeout(PAST_THE_WAITS);
  } finally {
    release();
  }
  await expect(
    page
      .getByRole("complementary", { name: "Gain_t" })
      .getByRole("heading", { name: "Gain_t", level: 2 }),
  ).toBeAttached();
  await twoFrames(page);
  await expect(heading).toBeFocused();
  await expect(heading).toBeInViewport();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});

/**
 * A Files address naming a file the project does not hold yet, loaded anew (16:M9, ruling
 * B11-47): the Files tab of a project with twenty more components, in a window 800 by 600. The
 * file is written past the short time after the tab has drawn its table, and its row's panel,
 * drawn then under the table, stays where it falls: the page is not scrolled to it, and no focus
 * is moved.
 */
test("a Files address whose row comes past a short wait after the tab loaded anew at it leaves the page where it stands", async ({
  page,
  copiedGui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  const gui = await copiedGui("demo", (directory) => moreComponents(directory, 20));
  await page.goto(gui.address);
  await expect(page.getByRole("link", { name: "Files", exact: true })).toBeVisible();
  const late = "components/late.ddd.json";
  const key = `${gui.directory.replaceAll("\\", "/")}/${late}`;
  await page.goto(
    `${new URL(gui.address).origin}/project?view=files&path=${encodeURIComponent(key)}`,
  );
  await expect(page.getByRole("grid", { name: "Files" })).toBeVisible();
  await page.waitForTimeout(PAST_THE_WAITS);
  writeFileSync(join(gui.directory, late), emptyComponent("Late"));
  const panel = page.getByRole("complementary", { name: late });
  await expect(panel).toBeAttached();
  await twoFrames(page);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await expect(panel.getByRole("heading", { name: late, level: 2 })).not.toBeInViewport();
  expect(await page.evaluate(() => document.activeElement === document.body)).toBe(true);
});

/**
 * A page loaded anew whose project is slow to analyse (16:M9, ruling B11-47): Controller's address
 * on ParameterA, in a window 800 by 600, the page's first state held back longer than the short
 * time. The short time counts from when the page first draws its own content, not from the load:
 * ParameterA's panel, drawn once the analysis has landed, is scrolled into view all the same.
 */
test("a page loaded anew at a variable's address while its project is analysed slowly has its panel in view", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 800, height: 600 });
  const parameter = await parameterAddress(page, gui.address);
  await page.goto(gui.address);
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
  const release = await held(page, "/api/state");
  try {
    await page.goto(parameter);
    await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeVisible();
    await page.waitForTimeout(PAST_THE_WAITS);
  } finally {
    release();
  }
  const panel = page.getByRole("complementary", { name: "ParameterA" });
  await expect(panel.getByRole("grid", { name: "Keys of ParameterA" })).toBeInViewport({
    ratio: 0.5,
  });
  expect(await page.evaluate(() => document.activeElement === document.body)).toBe(true);
});
