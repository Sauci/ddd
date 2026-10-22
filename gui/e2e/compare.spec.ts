import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { drift, driftDatatypeIn, dump, held, renameValueA, SENSOR_HUB } from "./demo";
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
 * begin - an OSError's text or the json parser's, which differ between Linux and Windows - and
 * then at least a character of theirs, on as many lines as they take: a refusal that dropped
 * them all fails. */
function startingWith(words: string): RegExp {
  return new RegExp(`^${words.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[\\s\\S]+`);
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

/** The demo as the Compare journeys that open a finding serve it: dumped before ValueA is widened,
 * and then ValueA's datatype in SensorHub widened, so that the server starts over the widened copy
 * and the comparison it is asked for against `baseline.json` already has its `changed-interface`
 * when the page asks. */
function widenedAfterDump(directory: string): void {
  dump(directory, "demo.ddd.json", "baseline.json");
  driftDatatypeIn(directory, SENSOR_HUB, "ValueA", "uint16");
}

test("a row of the findings table opens its finding in a panel", async ({ page, copiedGui }) => {
  const gui = await copiedGui("demo", widenedAfterDump);
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
    const before = readFileSync(storage, "utf8");
    const moved = before.replace('"key": 12', '"key": 14');
    if (moved === before) throw new Error(`EngineHours carries no key 12 in ${storage}`);
    writeFileSync(storage, moved);
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();
  await page.getByRole("row", { name: "layout/key-changed" }).click();

  const panel = page.getByRole("complementary", { name: "layout/key-changed" });
  const message = "'EngineHours' carried key 12 and now carries 14; its entry under 12 is orphaned";
  await expect(panel.getByText(message, { exact: true })).toBeVisible();
  await panel.getByRole("link", { name: "Open EngineHours", exact: true }).click();

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
  const release = await held(page, "/api/compare");
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

/** Every ask for a comparison (`GET /api/compare`) the page makes from here on, counted as it is
 * asked, before any answer. */
function comparesAsked(page: Page): string[] {
  const asked: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/compare") asked.push(url.search);
  });
  return asked;
}

test("a baseline typed is asked for with Enter, once, and a field with nothing but spaces in it asks for nothing", async ({
  page,
  gui,
}) => {
  dump(gui.directory, "demo.ddd.json", "baseline.json");
  const asked = comparesAsked(page);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  const baseline = page.getByRole("textbox", { name: "Baseline" });

  // Nothing but spaces: the button beside the field is off, and so is Enter.
  await baseline.fill("   ");
  await expect(page.getByRole("button", { name: "Compare", exact: true })).toBeDisabled();
  await baseline.press("Enter");

  // A path, and Enter with no click: asked for, and answered in the verdict's own words.
  await baseline.fill("baseline.json");
  await baseline.press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "replace the baseline" })).toHaveText(
    "This project can replace the baseline.",
  );
  // The spaces' Enter went before the ask that drew the verdict, and asked nothing.
  expect(asked).toEqual(["?baseline=baseline.json"]);
});

test("a finding about the whole delivery says why it leads nowhere", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", widenedAfterDump);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await page.getByRole("row", { name: "changed-interface" }).click();

  // `compare` files every finding of its own at the candidate's description with no pointer: it
  // is about the delivery, not a place in one file, so the panel says so and has no link.
  const panel = page.getByRole("complementary", { name: "changed-interface" });
  await expect(
    panel.getByText("it is about the whole delivery being compared, not a place in one file", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(panel.getByRole("link")).toHaveCount(0);
});

test("the baseline's own findings are named as the baseline's and lead nowhere, though their files are the open project's own", async ({
  page,
  copiedGui,
}) => {
  // The project against itself, which a comparison allows: its drift is a `definition-mismatch`
  // that the baseline's analysis files too, so the baseline's errors refuse the delivery and
  // their files are the open project's own components.
  const gui = await copiedGui("demo", (directory) => {
    drift(directory);
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("demo.ddd.json");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "replace the baseline" })).toHaveText(
    "This project cannot replace the baseline.",
  );

  // The baseline's analysis files the drift on both components, each row's message behind "in
  // the baseline: " (`BASELINE_PREFIX`, deliveries.py), and its File cell names the file as the
  // baseline's: the same display name a file of the open project has.
  const row = page
    .getByRole("row", { name: /definition-mismatch/ })
    .filter({ hasText: "the baseline's controller.ddd.json" });
  await expect(row).toHaveCount(1);
  await expect(row.getByRole("gridcell").nth(0)).toHaveText(
    "in the baseline: 'ValueA' is declared differently by component 'Controller' than by " +
      "'SensorHub' (unit: 'rpm' != '%')",
  );
  await expect(row.getByRole("gridcell").nth(1)).toHaveText("the baseline's controller.ddd.json");
  await row.click();

  const panel = page.getByRole("complementary", { name: "definition-mismatch" });
  await expect(
    panel.getByText("it is the baseline's own finding, not a place in your project", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(panel.getByRole("link")).toHaveCount(0);
});

test("a finding's panel is closed by its Close button, the comparison standing", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", widenedAfterDump);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const row = page.getByRole("row", { name: "changed-interface" });
  await row.click();
  const panel = page.getByRole("complementary", { name: "changed-interface" });
  await expect(panel).toBeVisible();
  await expect(row).toHaveAttribute("aria-selected", "true");

  await panel.getByRole("button", { name: "Close changed-interface", exact: true }).click();
  await expect(panel).toHaveCount(0);
  await expect(row).toHaveAttribute("aria-selected", "false");
  // Closing a panel asks nothing again: the verdict and the table are still drawn.
  await expect(page.getByRole("status").filter({ hasText: "replace the baseline" })).toHaveText(
    "This project cannot replace the baseline.",
  );
  await expect(row).toBeVisible();

  // Pressed again, the row opens its panel again.
  await row.click();
  await expect(panel).toBeVisible();
});

test("a finding's panel closes by itself once a comparison no longer reports the finding, and stays closed when it returns", async ({
  page,
  copiedGui,
}) => {
  // SensorHub as it ships, kept to put back.
  const shipped: { bytes: Buffer } = { bytes: Buffer.alloc(0) };
  const gui = await copiedGui("demo", (directory) => {
    dump(directory, "demo.ddd.json", "baseline.json");
    shipped.bytes = driftDatatypeIn(directory, SENSOR_HUB, "ValueA", "uint16");
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const verdict = page.getByRole("status").filter({ hasText: "replace the baseline" });
  await expect(verdict).toHaveText("This project cannot replace the baseline.");
  const row = page.getByRole("row", { name: "changed-interface" });
  await row.click();
  const panel = page.getByRole("complementary", { name: "changed-interface" });
  await expect(panel).toBeVisible();

  // SensorHub put back as the baseline has it, which the watcher sees: the next revision asks the
  // comparison again, it no longer reports the finding, and the panel of a finding it does not
  // hold is gone.
  writeFileSync(join(gui.directory, SENSOR_HUB), shipped.bytes);
  await expect(verdict).toHaveText("This project can replace the baseline.");
  await expect(panel).toHaveCount(0);

  // Widened again, the very same finding comes back - a finding's key is its severity, check,
  // pointer and message - and its panel does not: nobody asked for it.
  driftDatatypeIn(gui.directory, SENSOR_HUB, "ValueA", "uint16");
  await expect(verdict).toHaveText("This project cannot replace the baseline.");
  await expect(row).toBeVisible();
  await expect(panel).toHaveCount(0);
});
