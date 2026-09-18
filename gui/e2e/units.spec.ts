import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, drift } from "./demo";
import { expect, test } from "./fixtures";

test("a disagreement written from outside is resolved from the component page", async ({
  page,
  gui,
}) => {
  const before = drift(gui.directory);
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();

  const panel = page.getByRole("complementary", { name: "ValueA" });
  const picker = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await expect(picker).toHaveValue("%");
  // Focusing the unit cell's button opened the picker's own list over what is below it in the
  // panel; accepting the producer's unit as it stands, with nothing chosen from that list,
  // closes it the way a reader leaving the field does, without changing what it holds.
  await picker.press("Escape");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.getByText('"unit": "rpm"')).toBeVisible();

  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(() => readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
  await expect(panel.getByText("Nothing to change")).toBeVisible();

  await page.getByRole("button", { name: "DemoDevice" }).click();
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, agreed")).toBeVisible();
});

test("the picker lists the variable's units, then the project's, narrowed by what is typed", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const picker = page.getByRole("combobox", { name: "Unit of ValueA" });
  await expect(page.getByRole("option", { name: "%", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "Hz", exact: true })).toBeVisible();
  await picker.fill("h");
  await expect(page.getByRole("option", { name: "Hz", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "%", exact: true })).toHaveCount(0);
});

test("a unit cell pressed again, once focus has moved elsewhere, moves it back to the picker", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const cell = page.getByRole("button", { name: "Set the unit of ValueA" });
  const picker = page.getByRole("combobox", { name: "Unit of ValueA" });
  await cell.click();
  await expect(picker).toBeFocused();
  // Open, the picker's own list hides the rest of the page from the accessibility tree (as the
  // CSP journey's neighbour above already works around); close it before reaching the masthead.
  await picker.press("Escape");
  await page.getByRole("button", { name: "DemoDevice" }).focus();
  await expect(picker).not.toBeFocused();
  await cell.click();
  await expect(picker).toBeFocused();
});

test("the address keeps the panel open across a reload", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("row", { name: /ValueB/ }).click();
  await expect(page).toHaveURL(/variable=ValueB/);
  await page.reload();
  await expect(page.getByRole("complementary", { name: "ValueB" })).toBeVisible();
});

test("the same disagreement is resolved from its arrow on the canvas", async ({ page, gui }) => {
  const before = drift(gui.directory);
  await page.goto(gui.address);
  await page.locator(".flow-label.error").click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await expect(panel).toBeVisible();
  await expect(page).toHaveURL(/\/project\?variable=ValueA$/);
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(() => readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, agreed")).toBeVisible();
});

test("no page reports a violation of its content security policy", async ({ page, gui }) => {
  await page.addInitScript(() => {
    const seen: string[] = [];
    Object.assign(window, { violations: seen });
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  await page.goto(gui.address);
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await expect(page.getByRole("option", { name: "%", exact: true })).toBeVisible();
  expect(
    await page.evaluate(() => (window as unknown as { violations: string[] }).violations),
  ).toEqual([]);
});
