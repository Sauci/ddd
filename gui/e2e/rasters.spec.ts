import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { PUMP } from "./demo";
import { expect, test } from "./fixtures";

/** Pump's own `raster` - the component's default, stated once in `component` itself
 * (examples/vocabulary/pump.ddd.json:6) - moved from `"10ms"`, a raster the project declares, to
 * `"20ms"`, one it does not, from outside the page: scoped by the component's own `name` first,
 * the way `sections.spec.ts`'s own `misplacePumpSpeed` and `constants.spec.ts`'s own
 * `breakPressureTrend` write a file, so that PumpSpeed's own `"raster": "1ms"` two lines below
 * stays where it is and the copy keeps exactly one thing wrong with it.
 *
 * The component's own default and not a definition's is the point of this journey (ruling 5,
 * task 9): `Use.kind` gained a second word, `"component"`, for exactly this shape, and breaking
 * PumpSpeed's own `raster` instead would file the very same check through the arm this part did
 * not add - a journey over a definition's would pass whether or not a regression touched the
 * component arm at all. `Analysis._check_rasters` (src/ddd/analysis.py:1236) is what walks
 * `component.raster` first and every definition's own `raster` second; this breaks only the
 * first.
 *
 * Throws where nothing matched, for the reason `misplacePumpSpeed`'s own docstring gives: a
 * replace that found no `raster` key would leave a copy that checks clean, and every assertion
 * below would then be waiting for a finding this journey never made - a failure reported as a
 * timeout on the Findings tab, twenty seconds away from saying what actually happened. */
function breakPumpDefault(directory: string): void {
  const path = join(directory, PUMP);
  const before = readFileSync(path, "utf8");
  const text = before.replace(/("name": "Pump"[\s\S]*?"raster": )"10ms"/, '$1"20ms"');
  if (text === before) throw new Error(`Pump states no '10ms' raster default in ${path}`);
  writeFileSync(path, text, "utf8");
}

test("a finding nobody could act on becomes a raster declared in two clicks", async ({
  page,
  vocabularyGui,
}) => {
  breakPumpDefault(vocabularyGui.directory);

  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  await page.getByRole("row", { name: "unknown-raster" }).click();
  const finding = page.getByRole("complementary", { name: "unknown-raster" });
  await expect(finding.locator(".chip")).toHaveText("error");
  // The subject as well as the check, where the finding is read: which component, and which
  // raster it measures everything it produces in. `_check_rasters`' own sentence for a
  // component's default - "component 'Pump' measures in ..." - is a different sentence from the
  // one it gives a definition, "'PumpSpeed' is measured in ..."; this is the first, because this
  // journey breaks the first.
  await expect(finding).toContainText("component 'Pump' measures in '20ms'");
  await expect(
    finding.getByText("is not a raster any file of this project declares"),
  ).toBeVisible();

  await finding.getByRole("link", { name: "Open 20ms" }).click();

  // The Shared files tab, the add form open and pre-filled: `20ms` names nothing the project
  // declares yet, which is what sends the one route to the form rather than a panel - the same
  // address a declared raster's own panel opens from, and the same shape the sections and
  // constants journeys land on with their own kind. "One route kind, and the page decides" is
  // part 13's design saying it, which this part inherits rather than restates.
  await expect(page).toHaveURL(/\/project\?view=shared&kind=raster&name=20ms$/);
  const form = page.getByRole("complementary", { name: "Declare a raster" });
  await expect(form.getByRole("textbox", { name: "Name" })).toHaveValue("20ms");

  // The one key a raster's `add` requires (`RASTERS.required`): the model defaults `cycle` and
  // `description` both, so an event on its own is a raster whose file loads. `3` is untaken -
  // 1ms, 10ms and 100ms hold events 0, 1 and 2 between them - so nothing here meets
  // `_event_taken`'s own refusal.
  await form.getByRole("textbox", { name: "Event" }).fill("3");

  // The preview, which is also the wait: the sentence naming the file arrives with the plan the
  // Apply button is drawn under, so there is no press to make before the server has said what
  // pressing it would change. It names the project's own rasters file, not a new one - this copy
  // includes one already, and `add` appends to the first of the vocabulary's files.
  await expect(form.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await form.getByRole("button", { name: "Apply to 1 file" }).click();

  // Declared: the tab moves onto the new raster's own panel, holding what was just declared, and
  // the table beside it gains the row - the reader's second click, from a finding nobody could
  // act on. The row arrives already used once: Pump's own default, which measures in something
  // the project declares now, is what the complaint was about, and its Used by row says so as
  // "everything it produces" rather than as a fourth definition - the very distinction this
  // journey exists to exercise (`rasterUseWhat`).
  const panel = page.getByRole("complementary", { name: "20ms" });
  const used = panel.getByRole("row", { name: "Pump" });
  await expect(used).toContainText("everything it produces");
  const row = page.getByRole("row", { name: "20ms" });
  await expect(row).toContainText("rasters");
  await expect(row).toContainText("event 3");
  await expect(row).toContainText("1 place");

  // And the finding itself is gone: examples/vocabulary checks clean, and giving Pump's own
  // default a raster to measure in is the only thing standing between it and clean again.
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
});
