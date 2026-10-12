import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { driftDatatypeIn, dump, renameValueA, SENSOR_HUB } from "./demo";
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
  // says so in its own words, not merely by showing no rows. Picked out by its words: the
  // heading's own status region, which says when the findings are updating, is a status too.
  const verdict = page.getByRole("status").filter({ hasText: "replace the baseline" });
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

/** `path` as the server writes a path into a refusal: absolute, with forward slashes. */
function posixOf(path: string): string {
  return path.replaceAll("\\", "/");
}

/** A whole sentence's start, as a pattern: the page's own words, up to where the system's own
 * begin - an OSError's text or the json parser's, which differ between Linux and Windows. */
function startingWith(words: string): RegExp {
  return new RegExp(`^${words.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`);
}

test("a baseline missing, not json, of the wrong shape or outside the root is refused in words of its own", async ({
  page,
  gui,
}) => {
  writeFileSync(join(gui.directory, "shape.json"), JSON.stringify({ neither: true }));
  const root = posixOf(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  const baseline = page.getByRole("textbox", { name: "Baseline" });
  const compare = page.getByRole("button", { name: "Compare" });
  const refusal = page.getByRole("alert");

  await baseline.fill("missing.json");
  await compare.click();
  await expect(refusal).toHaveText(
    startingWith(`the baseline '${root}/missing.json' is unreadable: `),
  );

  await baseline.fill("include/sensor_hub_driver.h");
  await compare.click();
  await expect(refusal).toHaveText(
    startingWith(`the baseline '${root}/include/sensor_hub_driver.h' is not valid json: `),
  );

  await baseline.fill("shape.json");
  await compare.click();
  await expect(refusal).toHaveText(
    startingWith(`the baseline '${root}/shape.json' is neither a dictionary nor a description: `),
  );

  // Confinement is checked before anything is read: the file need not exist.
  await baseline.fill("../outside.json");
  await compare.click();
  const outside = posixOf(join(gui.directory, "..", "outside.json"));
  await expect(refusal).toHaveText(
    `the baseline '${outside}' is outside the session root '${root}'`,
  );
});

test("a row of the findings table opens its finding in a panel beside it", async ({
  page,
  copiedGui,
}) => {
  // The baseline is dumped before ValueA is widened, and the server starts over the widened copy:
  // the comparison it is asked for already has its finding when the page asks.
  const gui = await copiedGui("demo", (directory) => {
    dump(directory, "demo.ddd.json", "baseline.json");
    driftDatatypeIn(directory, SENSOR_HUB, "ValueA", "uint16");
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();

  // The panel is named for its finding's check, and is not there until its row is pressed.
  const panel = page.getByRole("complementary", { name: "changed-interface" });
  const row = page.getByRole("row", { name: "changed-interface" });
  await expect(row).toBeVisible();
  await expect(panel).toHaveCount(0);
  await row.click();
  const message =
    "'ValueA' is not the same object any more (datatype: uint16 != uint8), read by Controller";
  await expect(panel.getByText(message, { exact: true })).toBeVisible();
});

test("a finding filed on a declaration leads to that declaration from its panel's link", async ({
  page,
  copiedGui,
}) => {
  // The demo's comparison findings are about the whole delivery and lead nowhere. The layout
  // plugin's comparison rule files its own on a declaration: EngineHours, moved from key 12 to
  // 14 after the baseline was dumped, is `layout/key-changed` on storage.ddd.json, routed to the
  // variable.
  const gui = await copiedGui("layout", (directory) => {
    dump(directory, "project.ddd.json", "baseline.json");
    const storage = join(directory, "storage.ddd.json");
    writeFileSync(storage, readFileSync(storage, "utf8").replace('"key": 12', '"key": 14'));
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();
  await page.getByRole("row", { name: "layout/key-changed" }).click();

  const panel = page.getByRole("complementary", { name: "layout/key-changed" });
  const message = "'EngineHours' carried key 12 and now carries 14; its entry under 12 is orphaned";
  await expect(panel.getByText(message, { exact: true })).toBeVisible();
  await panel.getByRole("link", { name: "Open EngineHours" }).click();

  // Storage's own page, with EngineHours' panel open: the same place a finding of the Findings
  // tab leads to.
  await expect(page).toHaveURL(/\/component\?file=.*storage\.ddd\.json&variable=EngineHours$/);
  await expect(page.getByRole("heading", { name: "Storage", level: 1 })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "EngineHours" })).toBeVisible();
});

/** ValueA's id as the copy's sensor_hub.ddd.json states it, where SensorHub produces it: what a
 * comparison pairs the object by when its name changes. */
function idOfValueA(directory: string): string {
  const data = JSON.parse(readFileSync(join(directory, SENSOR_HUB), "utf8")) as {
    component: { interface: { definition: { name: string; id: string } }[] };
  };
  const found = data.component.interface.find((entry) => entry.definition.name === "ValueA");
  if (found === undefined) throw new Error(`${SENSOR_HUB} declares no ValueA`);
  return found.definition.id;
}

test("an object renamed since the baseline is listed with its id, where nothing was renamed before", async ({
  page,
  gui,
}) => {
  const id = idOfValueA(gui.directory);
  dump(gui.directory, "demo.ddd.json", "baseline.json");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByRole("heading", { name: "Renamed objects", level: 2 })).toBeVisible();
  await expect(page.getByText("Nothing was renamed.")).toBeVisible();

  // Renamed from outside, in every file naming it. The page asks again for the revision this
  // brings, and the comparison pairs the two spellings by the id the producer states.
  renameValueA(gui.directory, "ValueZ");
  const renames = page.getByRole("table");
  await expect(renames.getByRole("columnheader")).toHaveText(["Id", "From", "To"]);
  await expect(renames.getByRole("cell")).toHaveText([id, "ValueA", "ValueZ"]);
  await expect(page.getByText("Nothing was renamed.")).toHaveCount(0);
});

test("while a comparison is awaited the field and the button are disabled and the earlier verdict is gone", async ({
  page,
  gui,
}) => {
  dump(gui.directory, "demo.ddd.json", "baseline.json");
  dump(gui.directory, "demo.ddd.json", "other.json");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  const baseline = page.getByRole("textbox", { name: "Baseline" });
  const compare = page.getByRole("button", { name: "Compare" });
  const verdict = page.getByRole("status").filter({ hasText: "replace the baseline" });
  await baseline.fill("baseline.json");
  await compare.click();
  await expect(verdict).toHaveText("This project can replace the baseline.");

  // The answer for the next baseline is held until the page has been seen waiting for it. Once
  // only: nothing else asks for a comparison here, the project not changing.
  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    (url) => url.pathname === "/api/compare",
    async (route) => {
      await released;
      await route.continue();
    },
    { times: 1 },
  );
  try {
    await baseline.fill("other.json");
    await compare.click();
    // Nothing says a comparison is running: the field and the button are what a reader sees
    // turn off, and the verdict of the baseline before it is gone, not left standing.
    await expect(baseline).toBeDisabled();
    await expect(compare).toBeDisabled();
    await expect(verdict).toHaveCount(0);
  } finally {
    release();
  }
  await expect(verdict).toHaveText("This project can replace the baseline.");
  await expect(baseline).toBeEnabled();
  await expect(compare).toBeEnabled();
});
