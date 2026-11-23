import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  CONTROLLER,
  drift,
  driftIn,
  EVENT_LOGGER,
  failing,
  held,
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

test("a disagreement is counted once above both tables, as ddd check counts it, and listed on each of its files", async ({
  page,
  gui,
}) => {
  // Controller's own reading of ValueA drifted from SensorHub's: one `definition-mismatch`, which
  // `ddd check` reports once and the analysis files on both of the files it concerns.
  drift(gui.directory);
  await page.goto(gui.address);

  // The Table tab's line counts it once, and the row of each of its two files the one filed there.
  await page.getByRole("link", { name: "Table", exact: true }).click();
  await expect(page.locator("p.summary")).toHaveText("1 error, 0 warnings");
  for (const name of ["Controller", "SensorHub"]) {
    const row = page
      .getByRole("row")
      .filter({ has: page.getByRole("button", { name, exact: true }) });
    await expect(row.getByRole("gridcell").first()).toHaveText("1");
  }

  // The Findings tab's line counts it once too, over a row on each of its files.
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await expect(page.getByText("1 finding · 1 error", { exact: true })).toBeVisible();
  await expect(page.getByRole("row", { name: /definition-mismatch/ })).toHaveCount(2);
});

test("Close puts the focus back on the finding's row", async ({ page, gui }) => {
  drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  const row = page
    .getByRole("row", { name: "definition-mismatch" })
    .filter({ hasText: "controller.ddd.json" });
  await row.focus();
  await page.keyboard.press("Enter");
  const panel = page.getByRole("complementary", { name: "definition-mismatch" });
  await panel.getByRole("button", { name: "Close definition-mismatch" }).focus();
  await page.keyboard.press("Enter");
  await expect(panel).toHaveCount(0);
  await expect(row).toBeFocused();
});

test("a row the Findings tab's filter leaves stays selected once the filter is emptied", async ({
  page,
  gui,
}) => {
  // 16:I14: the filter asks the server for the findings a file's name holds, and the row it leaves
  // keeps its key - selected there, it is the one selected once every finding is back.
  drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  const mismatches = page.getByRole("row", { name: "definition-mismatch" });
  await expect(mismatches).toHaveCount(2);

  const filter = page.getByRole("textbox", { name: "Filter findings" });
  await filter.fill("sensor_hub");
  await expect(filter).toHaveAccessibleDescription("1 of 2 findings");
  await expect(mismatches).toHaveCount(1);
  await expect(mismatches).toContainText("sensor_hub.ddd.json");
  await mismatches.click();
  await expect(page.getByRole("complementary", { name: "definition-mismatch" })).toBeVisible();

  await filter.fill("");
  await expect(mismatches).toHaveCount(2);
  const selected = page.getByRole("row", { selected: true });
  await expect(selected).toHaveCount(1);
  await expect(selected).toContainText("sensor_hub.ddd.json");
  // The line above the table counts the one statement the two rows make, filtered or not.
  await expect(page.getByText("1 finding · 1 error", { exact: true })).toBeVisible();
});

test("a filter the server fails on says so above the table", async ({ page, gui }) => {
  drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByRole("row", { name: "definition-mismatch" })).toHaveCount(2);
  await failing(
    page,
    (url) => url.pathname === "/api/findings" && url.searchParams.has("text"),
    "http",
  );
  await page.getByRole("textbox", { name: "Filter findings" }).fill("sensor_hub");
  await expect(page.getByText(SERVER_FAILED, { exact: true })).toBeVisible();
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
  await expect(panel.locator(".chip")).toHaveText("info");
  await expect(panel.getByText("'ValueH' has no 'id'")).toBeVisible();

  await panel.getByRole("button", { name: "Give 'ValueH' an id" }).click();
  await panel.getByRole("button", { name: "Show changes" }).click();
  // Written right after the name, where `ddd id` writes it, so another member follows it.
  const added = panel.locator(".hunk .added").filter({ hasText: '"id":' });
  await expect(added).toHaveText(/^\+\s*"id": "[abcdefghjkmnpqrstvwxyz0-9]{12}",$/);

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
  // Where the parser stopped, as `ddd check` prints it, so the reader need not go to a terminal
  // to find it: the file, then a line inside it and a column on that line.
  const place = await panel.locator(".path").innerText();
  const [, line, column] = /^controller\.ddd\.json:(\d+):(\d+)$/.exec(place) ?? [];
  expect(Number(line)).toBeGreaterThan(0);
  expect(Number(line)).toBeLessThanOrEqual(before.toString("utf8").split("\n").length);
  expect(Number(column)).toBeGreaterThan(0);
});

test("a finding that leads nowhere says its pointer where the file has no line to give", async ({
  page,
  gui,
}) => {
  // A boolean that is not one: the file parses, fails `schema`, and so did not load - nowhere
  // for a route to lead, and the loader gave a place inside the document, not a line.
  const file = join(gui.directory, USER_INTERFACE);
  writeFileSync(
    file,
    readFileSync(file, "utf8").replace('"volatile": true', '"volatile": "maybe"'),
  );
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await page.getByRole("row", { name: "schema" }).click();
  const panel = page.getByRole("complementary", { name: "schema" });
  await expect(panel.locator(".path")).toHaveText("component.interface[0].definition.volatile");
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
 * preview: `FindingsPage.tsx`'s own sentence, held until the reader's next choice. */
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
  // session's own watcher does not see it (`writeUnseen`), so that only the Apply's own fresh read
  // of the bytes sees it. A space taken out and a full stop put in keep the file as long as it
  // was. Written once, then the request goes through to the server, which reads the bytes fresh.
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
  // The state counted the findings all the same, so the line over the table says how many
  // statements there are - the one disagreement, as `ddd check` counts it - and the table has
  // neither of its two rows to open.
  await expect(page.getByText("1 finding · 1 error", { exact: true })).toBeVisible();
  await expect(page.getByRole("row", { name: /definition-mismatch/ })).toHaveCount(0);
});

test("a page of findings still being read is drawn as rows saying so, which the findings replace", async ({
  page,
  copiedGui,
}) => {
  // Drifted before the server starts, so that the first revision already holds the two findings
  // and no clean window is drawn first (`drawnWindow`).
  const gui = await copiedGui("demo", (directory) => {
    drift(directory);
  });
  await page.goto(gui.address);
  // The canvas drawn, so that the Findings tab has asked for no page yet: its first page is the
  // first ask of the path, and held, it is the read this journey is about.
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const table = page.getByRole("grid", { name: "Findings" });
  const pending = table.getByRole("row").filter({ hasText: "Reading…" });
  const mismatches = page.getByRole("row", { name: /definition-mismatch/ });
  const release = await held(page, "/api/findings");
  try {
    await page.getByRole("link", { name: "Findings", exact: true }).click();
    // The line above the table is the state's own, counted before any page of findings comes:
    // the one disagreement, as `ddd check` counts it. The table has a row for each file it is
    // filed on, saying that its page is not there yet.
    await expect(page.getByText("1 finding · 1 error", { exact: true })).toBeVisible();
    await expect(pending).toHaveCount(2);
    await expect(mismatches).toHaveCount(0);
  } finally {
    release();
  }
  await expect(mismatches).toHaveCount(2);
  await expect(pending).toHaveCount(0);
});

test("a fix the server fails on shows its refusal in the panel in place of the fix, is sent once, and can be chosen again and applied", async ({
  page,
  gui,
}) => {
  // ValueH's id taken away, as "a missing id is fixed" takes it: a fix that writes into
  // Controller alone.
  unstamp(gui.directory, CONTROLLER, "ValueH");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page.getByRole("row", { name: "missing-id" }).click();
  const panel = page.getByRole("complementary", { name: "missing-id" });
  await panel.getByRole("button", { name: "Give 'ValueH' an id" }).click();
  const fixing = panel.getByRole("region", { name: "Give 'ValueH' an id" });
  await expect(fixing.getByRole("button", { name: "Apply to 1 file" })).toBeVisible();

  // Registered once the fix is drawn: nothing GETs the edit's path, and a POST is never sent
  // again, so the one Apply is the one failed.
  const failed = await failing(page, "/api/edit", "http");
  await fixing.getByRole("button", { name: "Apply to 1 file" }).click();

  // It stays until the reader chooses again, as every refusal of the tab does, and the panel
  // draws it in place of the consequence and the Apply.
  await expect(fixing.getByRole("status")).toHaveText(`The change was refused: ${SERVER_FAILED}`);
  await expect(fixing.getByRole("button", { name: "Apply to 1 file" })).toHaveCount(0);
  // The finding is still reported, and the panel still shows it.
  await expect(panel.getByText("'ValueH' has no 'id'")).toBeVisible();
  // A guard against a write by another path: the POST is answered by `failing`, not the server.
  expect(valueH(gui.directory).id).toBeUndefined();
  expect(failed()).toBe(1);

  // The reader chooses again - the fix pressed off and on - with the server answering as it does:
  // the refusal says nothing of what is chosen now, so it goes with the choice, and the fix is
  // offered as it was before the server failed on it (`choose`, FindingsPage.tsx). Left standing,
  // it withdrew the Apply until the finding was pressed again.
  await page.unrouteAll({ behavior: "wait" });
  const fix = panel.getByRole("button", { name: "Give 'ValueH' an id" });
  await fix.click();
  await fix.click();
  await expect(fixing.getByRole("button", { name: "Apply to 1 file" })).toBeVisible();
  await expect(fixing.getByRole("status")).toHaveCount(0);
  await fixing.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
  expect(valueH(gui.directory).id).toMatch(/^[abcdefghjkmnpqrstvwxyz0-9]{12}$/);
});
