import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { CONTROLLER, drift, driftIn, UNITS } from "./demo";
import { expect, test } from "./fixtures";

/** The strip the Undo button opens. */
function strip(page: Page) {
  return page.getByRole("region", { name: "Undo" });
}

test("a unit settled from a panel is put back exactly as the file was", async ({ page, gui }) => {
  // `drift` answers the file as it was before it drifted - which is what settling gives it
  // back, and so what the undo has to take away again.
  const agreed = drift(gui.directory);
  await page.goto(gui.address);
  // The analysis notices a file changed on disk on its own cadence, a moment after it happens;
  // waiting for the disagreement here is what keeps the settle preview clicked below from being
  // computed against the read from before the drift.
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(() => readFileSync(join(gui.directory, CONTROLLER)).equals(agreed)).toBe(true);

  const undo = page.getByRole("button", { name: "Undo the unit of ValueA" });
  await expect(undo).toBeVisible();
  await undo.click();
  await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await strip(page).getByRole("button", { name: "Show changes" }).click();
  await expect(strip(page).getByText('+ "unit": "rpm",')).toBeVisible();
  await strip(page).getByRole("button", { name: "Put back 1 file" }).click();

  // The drifted file again, and the disagreement with it; nothing left to undo.
  await expect
    .poll(() => readFileSync(join(gui.directory, CONTROLLER)).toString())
    .toContain('"unit": "rpm"');
  await expect(undo).toBeHidden();
  await page.getByRole("button", { name: "DemoDevice" }).click();
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
});

test("an adopted vocabulary is taken away again, file and include", async ({ page, gui }) => {
  const adopted = join(gui.directory, UNITS);
  const described = readFileSync(join(gui.directory, "demo.ddd.json"));
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await banner.getByRole("button", { name: "Adopt 5 units" }).click();
  await expect.poll(() => existsSync(adopted)).toBe(true);

  const undo = page.getByRole("button", { name: "Undo the vocabulary adopted" });
  await undo.click();
  await expect(
    strip(page).getByText("Puts back 2 files: demo.ddd.json, units.ddd.json"),
  ).toBeVisible();
  await strip(page).getByRole("button", { name: "Show changes" }).click();
  await expect(strip(page).getByText("units.ddd.json, removed")).toBeVisible();
  await strip(page).getByRole("button", { name: "Put back 2 files" }).click();

  await expect.poll(() => existsSync(adopted)).toBe(false);
  expect(readFileSync(join(gui.directory, "demo.ddd.json")).equals(described)).toBe(true);
  await expect(page.getByText("5 units · no units file")).toBeVisible();
});

test("an undo of an edit whose file was changed by hand is refused, and keeps its place", async ({
  page,
  gui,
}) => {
  drift(gui.directory);
  await page.goto(gui.address);
  // As above: wait for the drift to be noticed before settling, or the preview settled here can
  // still be the one read before it.
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  const undo = page.getByRole("button", { name: "Undo the unit of ValueA" });
  await expect(undo).toBeVisible();

  // Saved from outside, the file the edit wrote is somebody else's now.
  driftIn(gui.directory, CONTROLLER, "ValueA", "kPa");
  await undo.click();
  await expect(strip(page).getByText(/changed on disk/)).toBeVisible();
  await expect(strip(page).getByRole("button", { name: /^Put back/ })).toHaveCount(0);

  // Nothing was written, and the entry keeps its place: the reader may put the file back and
  // ask again.
  expect(readFileSync(join(gui.directory, CONTROLLER)).toString()).toContain('"kPa"');
  await expect(undo).toBeVisible();
});

test("the control stands beside a component's name too", async ({ page, gui }) => {
  drift(gui.directory);
  await page.goto(gui.address);
  // As above: wait for the drift to be noticed before settling.
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await page
    .getByRole("complementary", { name: "ValueA" })
    .getByRole("button", { name: "Apply to 1 file" })
    .click();
  await expect(page.getByRole("button", { name: "Undo the unit of ValueA" })).toBeVisible();

  // Back to the project and into another component, the way a reader walks there: nothing
  // about the control is one screen's own.
  await page.getByRole("button", { name: "DemoDevice" }).click();
  await page.getByRole("button", { name: "SensorHub", exact: true }).click();
  await expect(page.getByRole("button", { name: "Undo the unit of ValueA" })).toBeVisible();
});
