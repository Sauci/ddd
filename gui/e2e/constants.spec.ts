import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { openPanel, PUMP } from "./demo";
import { expect, test } from "./fixtures";

/** PressureTrend's own `dimensions` in a copy of examples/vocabulary's pump.ddd.json, broken so
 * it names a constant the project does not declare - `TREND_SLOTS` rather than the
 * `TREND_SAMPLES` the file ships with - from outside the page, the way e2e/demo.ts's own helpers
 * write a file (`datatypeOf`'s own regex, scoped by the declaration's name first). */
function breakPressureTrend(directory: string): void {
  const path = join(directory, PUMP);
  const text = readFileSync(path, "utf8").replace(
    /("name": "PressureTrend"[\s\S]*?"dimensions": )\["TREND_SAMPLES"\]/,
    '$1["TREND_SLOTS"]',
  );
  writeFileSync(path, text, "utf8");
}

test("a finding nobody could act on becomes a constant declared in two clicks", async ({
  page,
  vocabularyGui,
}) => {
  breakPressureTrend(vocabularyGui.directory);

  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  await page.getByRole("row", { name: "unknown-constant" }).click();
  const finding = page.getByRole("complementary", { name: "unknown-constant" });
  await expect(finding.locator(".chip")).toHaveText("error");
  await expect(
    finding.getByText("is not a constant any file of this project declares"),
  ).toBeVisible();

  await finding.getByRole("link", { name: "Open TREND_SLOTS" }).click();

  // The Shared files tab, the add form open and pre-filled: TREND_SLOTS names nothing the
  // project declares yet, which is what sends the one route to the form rather than a panel
  // (design §2, "the page decides").
  await expect(page).toHaveURL(/\/project\?view=shared&kind=constant&name=TREND_SLOTS$/);
  const form = page.getByRole("complementary", { name: "Declare a constant" });
  await expect(form.getByRole("textbox", { name: "Name" })).toHaveValue("TREND_SLOTS");

  await form.getByRole("textbox", { name: "Value" }).fill("12");
  await expect(form.getByText("Changes 1 file: constants.ddd.json")).toBeVisible();
  await form.getByRole("button", { name: "Apply to 1 file" }).click();

  // Declared: the tab moves onto the new constant's own panel, and the table beside it gains
  // the row - the reader's second click, from a finding nobody could act on.
  await expect(page.getByRole("complementary", { name: "TREND_SLOTS" })).toBeVisible();
  await expect(page.getByRole("row", { name: "TREND_SLOTS" })).toBeVisible();

  // And the finding itself is gone: examples/vocabulary checks clean, and declaring the one
  // name this journey broke is the only thing standing between it and clean again.
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();

  // The other way in (spec 5.3, the part this test is named for): PressureTrend's own
  // `dimensions` row still names TREND_SLOTS, and now that it is declared, its link is the
  // second route to the very same panel the finding above led to - not only the finding's own.
  const pumpPanel = await openPanel(page, vocabularyGui.address, "PressureTrend", "Pump");
  await pumpPanel.getByRole("link", { name: "TREND_SLOTS" }).click();
  await expect(page).toHaveURL(/\/project\?view=shared&kind=constant&name=TREND_SLOTS$/);
  await expect(page.getByRole("complementary", { name: "TREND_SLOTS" })).toBeVisible();
});
