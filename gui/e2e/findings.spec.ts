import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  CONTROLLER,
  drift,
  driftIn,
  EVENT_LOGGER,
  failing,
  PUMP,
  SERVER_FAILED,
  USER_INTERFACE,
  unstamp,
  writeUnseen,
} from "./demo";
import { expect, test } from "./fixtures";

/** ValueE's own `"unit"` in a file, read back from disk - its own declaration's and no other, so
 * a stray `"unit": "Hz"` elsewhere in the same file (AxisA's, in user_interface.ddd.json) cannot
 * make a fix that wrote nothing look like one that worked. Found through the file's own
 * structure, as `valueH` below is: a regex scoped by "the next unit after the name" would read
 * straight past a ValueE that states none and report the following declaration's instead, which
 * is the one way this assertion could go quiet rather than fail. */
function unitOfValueE(bytes: Buffer): string | undefined {
  const data = JSON.parse(bytes.toString("utf8"));
  const entry = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueE",
  );
  return entry?.definition.unit;
}

/** ValueH's definition in the copy's own controller.ddd.json, read back from disk - the one
 * local declaration `unstamp` below takes an id from. */
function valueH(directory: string): Record<string, never> {
  const data = JSON.parse(readFileSync(join(directory, CONTROLLER), "utf8"));
  const entry = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueH",
  );
  return entry.definition;
}

test("a disagreement leads to its variable", async ({ page, gui }) => {
  // Drifting Controller's own reading disagrees with SensorHub's, so the analysis files
  // `definition-mismatch` twice - once on each file it concerns - both leading to ValueA.
  drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  const row = page
    .getByRole("row", { name: "definition-mismatch" })
    .filter({ hasText: "controller.ddd.json" });
  await row.click();

  const panel = page.getByRole("complementary", { name: "definition-mismatch" });
  await expect(panel.locator(".chip")).toHaveText("error");
  await expect(panel.getByText("is declared differently by component 'Controller'")).toBeVisible();
  await expect(panel.locator(".panel-notes")).toContainText("reference declaration");
  await expect(panel.locator(".panel-notes")).toContainText("sensor_hub.ddd.json");

  await panel.getByRole("link", { name: "Open ValueA" }).click();

  // Controller's own page, with ValueA's panel open on the row that disagrees - part 3's own
  // rule, reached this time by a finding's route rather than by hand.
  await expect(page).toHaveURL(/\/component\?file=.*variable=ValueA$/);
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();
  const variablePanel = page.getByRole("complementary", { name: "ValueA" });
  await expect(variablePanel).toBeVisible();
  await expect(variablePanel.getByRole("combobox", { name: "Unit of ValueA" })).toHaveValue("%");
});

test("a disagreement is settled from the finding that reports it", async ({ page, gui }) => {
  // ValueE is written by Controller and read by UserInterface and EventLogger, all three in
  // Hz - the only demo variable with one producer and two consumers, so drifting one reader's
  // unit shows a fix that reaches one file, and drifting both shows the same button reaching
  // two: the settlement follows the variable, not the finding that happened to report it.
  driftIn(gui.directory, USER_INTERFACE, "ValueE", "kHz");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  const panel = page.getByRole("complementary", { name: "definition-mismatch" });

  const uiRow = page
    .getByRole("row", { name: "definition-mismatch" })
    .filter({ hasText: "user_interface.ddd.json" });
  await uiRow.click();
  await panel.getByRole("button", { name: "Use the unit declared in controller" }).click();
  await expect(panel.getByRole("button", { name: "Apply to 1 file" })).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect(page.getByText("Nothing to report")).toBeVisible();
  expect(unitOfValueE(readFileSync(join(gui.directory, USER_INTERFACE)))).toBe("Hz");

  // Both readers disagree now. The button offered on EventLogger's own finding must still
  // change UserInterface's file too - the reach is the whole variable, not the one file this
  // finding was filed on.
  driftIn(gui.directory, USER_INTERFACE, "ValueE", "kHz");
  driftIn(gui.directory, EVENT_LOGGER, "ValueE", "kHz");

  const eventRow = page
    .getByRole("row", { name: "definition-mismatch" })
    .filter({ hasText: "event_logger.ddd.json" });
  await eventRow.click();
  await panel.getByRole("button", { name: "Use the unit declared in controller" }).click();
  await expect(panel.getByRole("button", { name: "Apply to 2 files" })).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();

  await expect(page.getByText("Nothing to report")).toBeVisible();
  expect(unitOfValueE(readFileSync(join(gui.directory, USER_INTERFACE)))).toBe("Hz");
  expect(unitOfValueE(readFileSync(join(gui.directory, EVENT_LOGGER)))).toBe("Hz");
});

test("an unknown unit leads to its unit", async ({ page, vocabularyGui }) => {
  // A typo `unknown-unit` already knows how to say (the demo's own EngineSpeed states the same
  // RPM/rpm pair) - here on the vocabulary example's own PumpSpeed instead.
  driftIn(vocabularyGui.directory, PUMP, "PumpSpeed", "RPM");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  await page.getByRole("row", { name: "unknown-unit" }).click();
  const panel = page.getByRole("complementary", { name: "unknown-unit" });
  await expect(panel.locator(".chip")).toHaveText("error");
  await expect(panel.getByText("did you mean 'rpm'")).toBeVisible();

  await panel.getByRole("link", { name: "Open RPM" }).click();

  await expect(page).toHaveURL(/\/project\?view=units&unit=RPM$/);
  await expect(page.getByRole("complementary", { name: "RPM" })).toBeVisible();
});

test("a missing id is fixed", async ({ page, gui }) => {
  // ValueH is local to Controller - units.spec.ts's own reason for picking it too - so stripping
  // its id reports `missing-id` with nothing else in play, and the fix touches one file alone.
  unstamp(gui.directory, CONTROLLER, "ValueH");
  expect(valueH(gui.directory).id).toBeUndefined();

  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await page.getByRole("row", { name: "missing-id" }).click();

  const panel = page.getByRole("complementary", { name: "missing-id" });
  await expect(panel.locator(".chip")).toHaveText("note");
  await expect(panel.getByText("'ValueH' has no 'id'")).toBeVisible();

  await panel.getByRole("button", { name: "Give 'ValueH' an id" }).click();
  await panel.getByRole("button", { name: "Show changes" }).click();
  const added = panel.locator(".hunk .added").filter({ hasText: '"id":' });
  await expect(added).toHaveText(/^\+\s*"id": "[abcdefghjkmnpqrstvwxyz0-9]{12}"$/);

  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
  await expect(page.getByRole("row", { name: "missing-id" })).toHaveCount(0);

  expect(valueH(gui.directory).id).toMatch(/^[abcdefghjkmnpqrstvwxyz0-9]{12}$/);
});

test("a finding that leads nowhere says why", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();

  // Saved half-edited, as units.spec.ts's own half-edited journey does to the same file: it no
  // longer parses, and the loader itself files the finding this time - on the file itself,
  // nowhere within it, so there is nowhere for a route to lead.
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  writeFileSync(file, before.subarray(0, Math.floor(before.length / 2)));

  await page.getByRole("row", { name: "json-syntax" }).click();
  const panel = page.getByRole("complementary", { name: "json-syntax" });
  await expect(panel.locator(".chip")).toHaveText("error");
  await expect(panel.getByText("controller.ddd.json did not load")).toBeVisible();
  await expect(panel.getByRole("link", { name: /^Open/ })).toHaveCount(0);
});

test("the tab says when there is nothing to report", async ({ page, vocabularyGui }) => {
  // Served exactly as it ships: checked against the running server that examples/vocabulary's
  // own findings are already empty, so nothing here needs silencing or fixing first.
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
});

test("a finding fixed from outside while its panel is open is no longer reported, and the tab says so", async ({
  page,
  gui,
}) => {
  // Controller's own reading of ValueA drifted, as "a disagreement leads to its variable" drifts
  // it: a definition-mismatch is filed on each file it concerns.
  const before = drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page
    .getByRole("row", { name: /definition-mismatch/ })
    .first()
    .click();
  const panel = page.getByRole("complementary", { name: "definition-mismatch" });
  await expect(panel).toBeVisible();

  // Put back from outside, as somebody fixing it in their editor would: the watcher sees it, the
  // analysis no longer reports the finding, and the tab says so where the panel was.
  writeFileSync(join(gui.directory, CONTROLLER), before);
  await expect(page.getByRole("status").filter({ hasText: "no longer reported" })).toHaveText(
    "This finding is no longer reported.",
  );
  await expect(panel).toHaveCount(0);
});

/** What the Findings tab says when a fix's Apply is refused because a file changed under its
 * preview: `FindingsPage.tsx`'s own sentence, held until a later revision. */
const STALE =
  "A file changed on disk, so nothing was written. The tab now shows the findings as they are.";

test("a fix applied while its file changed on disk is refused, and nothing is written", async ({
  page,
  gui,
}) => {
  // ValueH's id taken away, as "a missing id is fixed" takes it: a fix that writes into
  // Controller alone.
  unstamp(gui.directory, CONTROLLER, "ValueH");
  const file = join(gui.directory, CONTROLLER);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page.getByRole("row", { name: "missing-id" }).click();
  const panel = page.getByRole("complementary", { name: "missing-id" });
  await panel.getByRole("button", { name: "Give 'ValueH' an id" }).click();
  await panel.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.locator(".hunk .added").filter({ hasText: '"id":' })).toBeVisible();

  // Controller's description gains its full stop as the Apply goes out, written where the
  // session's own watcher does not see it (`writeUnseen`): seen, it brought a revision of its
  // own, and the tab holds a stale refusal only until the next (`shownRefusal`, lib/refusals.ts),
  // which a journey can miss, as skeleton.spec.ts's out-of-date edit once did. A space taken out
  // and a full stop put in keep the file as long as it was. Written once, then the request goes
  // through to the server, which reads the bytes fresh.
  const original = readFileSync(file, "utf8");
  const changed = original.replace(
    '"description": "Consumes the raw values and produces the derived ones"',
    '"description":"Consumes the raw values and produces the derived ones."',
  );
  expect(changed).not.toBe(original);
  await page.route(
    "**/api/edit",
    async (route) => {
      writeUnseen(gui.directory, CONTROLLER, changed);
      await route.continue();
    },
    { times: 1 },
  );
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(panel.getByRole("status")).toHaveText(STALE);

  // Nothing was written: the file is as the change from outside left it, ValueH still without
  // its id.
  expect(readFileSync(file, "utf8")).toBe(changed);
  expect(valueH(gui.directory).id).toBeUndefined();
});

test("the fixes of a finding failing leave its panel without them, and an alert over it says so", async ({
  page,
  gui,
}) => {
  // The finding "a missing id is fixed" selects, whose panel offers a fix when it can be asked for.
  unstamp(gui.directory, CONTROLLER, "ValueH");
  await failing(page, "/api/fix", "http");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page.getByRole("row", { name: "missing-id" }).click();

  // Said over the panel (`:above()` is Playwright's layout selector: the alert's box lies over the
  // panel's): it is the fixes that failed, and the finding itself is drawn all the same, with the
  // route it leads by.
  const panel = page.getByRole("complementary", { name: "missing-id" });
  await expect(page.getByRole("alert").and(page.locator(":above(.panel)"))).toHaveText(
    SERVER_FAILED,
  );
  await expect(panel.getByText("'ValueH' has no 'id'")).toBeVisible();
  await expect(panel.getByRole("link", { name: "Open ValueH" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Give 'ValueH' an id" })).toHaveCount(0);
});

test("the page of findings failing leaves an alert over a table with nothing to open", async ({
  page,
  copiedGui,
}) => {
  // Drifted before the server starts, so that the first revision the page reads already holds the
  // findings. Drifted after, the page can open on the clean revision, and keep drawing it
  // ("Nothing to report") while the drifted one's page is asked for and fails (`drawnWindow`).
  const gui = await copiedGui("demo", (directory) => {
    drift(directory);
  });
  await failing(page, "/api/findings", "http");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();

  // Over the table: `:above()` is Playwright's layout selector, true of the alert whose box lies
  // over the grid's.
  await expect(page.getByRole("alert").and(page.locator(':above([role="grid"])'))).toHaveText(
    SERVER_FAILED,
  );
  // The state counted the findings all the same, so the line over the table says how many there
  // are, and the table has none of them to open.
  await expect(page.getByText("2 findings · 2 errors", { exact: true })).toBeVisible();
  await expect(page.getByRole("row", { name: /definition-mismatch/ })).toHaveCount(0);
});
