import { driftDatatypeIn, dump, SENSOR_HUB } from "./demo";
import { expect, test } from "./fixtures";

test("a reader can ask whether this delivery replaces the last", async ({ page, gui }) => {
  // The baseline this journey asks against: a dump of the copy exactly as `ddd gui` is already
  // serving it, taken before anything drifts - written under `gui.directory`, the one root a
  // baseline is ever read from, the same way `fixtures.ts` itself starts the server whose binary
  // this reaches. Named without a `.ddd.json` suffix so nothing mistakes an archived dictionary
  // for a description file the project search would offer.
  dump(gui.directory, "demo.ddd.json", "baseline.json");

  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();

  // The sanity case: a copy compared against a dump of itself is a drop-in replacement, and
  // says so in its own words, not merely by showing no rows.
  const verdict = page.getByRole("status");
  await expect(verdict).toHaveText("This project can replace the baseline.");
  await expect(page.getByText("Nothing to report")).toBeVisible();

  // ValueA's *producing* declaration, in SensorHub - not Controller's own reading of it, which
  // is what `drift`/`driftIn` change elsewhere for `definition-mismatch`. Resolution follows the
  // producer's own statement of a field, so widening it here is what actually changes the
  // resolved delivery a comparison reads, the way a real widened storage type would.
  driftDatatypeIn(gui.directory, SENSOR_HUB, "ValueA", "uint16");
  await page.getByRole("button", { name: "Compare" }).click();

  // The verdict turns, in the same words a reader sees it in, and a `changed-interface` finding
  // says what changed - not just that some row now exists.
  await expect(verdict).toHaveText("This project cannot replace the baseline.");
  await expect(page.getByText("1 finding · 1 error")).toBeVisible();
  const row = page.getByRole("row", { name: "changed-interface" });
  await expect(row).toContainText("'ValueA' is not the same object any more");
  await expect(row).toContainText("datatype: uint16 != uint8");
});
