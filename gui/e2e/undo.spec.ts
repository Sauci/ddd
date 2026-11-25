import { chmodSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import {
  CONTROLLER,
  chooseUnit,
  drift,
  driftIn,
  failing,
  held,
  openPanel,
  placed,
  renameValueA,
  SERVER_FAILED,
  UNITS,
} from "./demo";
import { expect, type Gui, test } from "./fixtures";

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

test("Put back pressed from the keyboard leaves the focus on the page's heading", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await chooseUnit(page, "rpm");
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  const undo = page.getByRole("button", { name: "Undo the unit of ValueA" });
  await undo.click();
  // Put back, and the Undo control beside it, are disabled while the files are put back, and the
  // strip closes after: the focus goes to the heading they stand beside.
  await strip(page).getByRole("button", { name: "Put back 2 files" }).focus();
  await page.keyboard.press("Enter");
  await expect(undo).toBeHidden();
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeFocused();
  // And the heading says what was put back, as it said what Apply wrote.
  await expect(page.locator(".heading").getByRole("status")).toHaveText(
    "Undid the unit of ValueA, putting back 2 files: controller.ddd.json, sensor_hub.ddd.json.",
  );
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
  // The file it takes away is counted apart from the one it puts back, as the heading says them
  // once the undo is answered (16:I13).
  await expect(
    strip(page).getByText("Puts back 1 file: demo.ddd.json, and removes 1 file: units.ddd.json", {
      exact: true,
    }),
  ).toBeVisible();
  await strip(page).getByRole("button", { name: "Show changes" }).click();
  await expect(strip(page).getByText("units.ddd.json, removed")).toBeVisible();
  await strip(page).getByRole("button", { name: "Put back 1 file and remove 1 file" }).click();

  await expect.poll(() => existsSync(adopted)).toBe(false);
  expect(readFileSync(join(gui.directory, "demo.ddd.json")).equals(described)).toBe(true);
  await expect(page.getByText("5 units · no units file")).toBeVisible();
  // The heading says what the undo did to each file, in the strip's own word for the one it took
  // away (16:I13).
  await expect(page.locator(".heading").getByRole("status")).toHaveText(
    "Undid the vocabulary adopted, putting back 1 file: demo.ddd.json, and removing 1 file: units.ddd.json.",
  );
});

test("an undo of an edit whose file was changed by hand is refused, and the edit leaves the stack once the strip says so", async ({
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

  // Saved from outside, the file the edit wrote is somebody else's now: the edit can never be
  // put back as that file stands, and the server takes it off the stack, which the strip says.
  driftIn(gui.directory, CONTROLLER, "ValueA", "kPa");
  await undo.click();
  // Nothing is left to undo once the state says so, and the control says that for as long as the
  // strip says why - asked only then, the sentence is the one the strip holds, not the preview's
  // own refusal drawn a moment before the state moved.
  const nothing = page.getByRole("button", { name: "Nothing left to undo" });
  await expect(nothing).toHaveAttribute("aria-expanded", "true");
  await expect(strip(page).getByRole("status")).toHaveText(
    "controller.ddd.json changed on disk since it was written, so the unit of ValueA can no " +
      "longer be undone. Nothing was put back; the page shows the files as they are.",
  );
  await expect(strip(page).getByRole("button", { name: /^Put back/ })).toHaveCount(0);

  // Nothing was written, and closing the strip takes the sentence and the control away.
  expect(readFileSync(join(gui.directory, CONTROLLER)).toString()).toContain('"kPa"');
  await nothing.click();
  await expect(strip(page)).toHaveCount(0);
  await expect(nothing).toHaveCount(0);
  await expect(undo).toHaveCount(0);
});

test("an edit whose file was saved from outside leaves the stack, and the strip offers the one before it without being closed", async ({
  page,
  gui,
}) => {
  // The first edit: ValueA's unit settled from Controller's panel, controller.ddd.json alone.
  await settledAndAnalysed(page, gui);
  // The second, of other files: the vocabulary adopted from the Units tab.
  await page.getByRole("button", { name: "DemoDevice" }).click();
  await page.getByRole("link", { name: "Units" }).click();
  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await banner.getByRole("button", { name: /^Adopt \d+ units$/ }).click();
  const undo = page.getByRole("button", { name: "Undo the vocabulary adopted" });
  await expect(undo).toBeVisible();
  await expect(page.locator(".updating-status")).toHaveText(/^Wrote 2 files for the vocabulary/);

  // Saved from outside, a file the second edit wrote is somebody else's now.
  const description = join(gui.directory, "demo.ddd.json");
  writeFileSync(description, `${readFileSync(description, "utf8")}\n`);
  await undo.click();
  // The edit before it is the one to undo now, offered whole in the strip still open, under the
  // sentence that says why the other went - asked once the state names the next, so that it is
  // the sentence the strip holds, not the preview's own refusal drawn a moment before.
  await expect(page.getByRole("button", { name: "Undo the unit of ValueA" })).toBeVisible();
  await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await expect(strip(page).getByRole("status")).toHaveText(
    "demo.ddd.json changed on disk since it was written, so the vocabulary adopted can no " +
      "longer be undone. Nothing was put back; the page shows the files as they are.",
  );
  await strip(page).getByRole("button", { name: "Put back 1 file" }).click();

  // Put back as an undo of it always was; the vocabulary, taken off and not undone, stays.
  await expect.poll(() => unitOfValueA(gui)).toBe("rpm");
  expect(existsSync(join(gui.directory, UNITS))).toBe(true);
  await expect(page.getByRole("button", { name: /^Undo / })).toHaveCount(0);
});

test("a revision landing while an edit's preview is on its way asks it no second time, and its going is said once", async ({
  page,
  gui,
}) => {
  // The newest revision the page has read of the state, from its own answers.
  let newest = 0;
  page.on("response", (response) => {
    if (new URL(response.url()).pathname !== "/api/state") return;
    response
      .json()
      .then((body: { revision: number }) => {
        newest = Math.max(newest, body.revision);
      })
      .catch(() => undefined);
  });
  // Two edits, as above: ValueA's unit settled, then the vocabulary adopted.
  await settledAndAnalysed(page, gui);
  await page.getByRole("button", { name: "DemoDevice" }).click();
  await page.getByRole("link", { name: "Units" }).click();
  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await banner.getByRole("button", { name: /^Adopt \d+ units$/ }).click();
  const undo = page.getByRole("button", { name: "Undo the vocabulary adopted" });
  await expect(undo).toBeVisible();
  await expect(page.locator(".updating-status")).toHaveText(/^Wrote 2 files for the vocabulary/);

  // The first preview of edit 2 held on its way; any later one answered as the server answers an
  // edit it has taken off already, refused as no longer on top - what CI's run of the journey
  // above met, made to happen here on purpose.
  const release = await held(page, "/api/undo");
  let asked = 0;
  await page.route(
    (url) => url.pathname === "/api/undo" && url.searchParams.get("at") === "2",
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      asked += 1;
      if (asked === 1) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ error: "stale", message: "edit 2 is not the one to undo any more" }),
      });
    },
  );
  try {
    await undo.click();
    await expect(strip(page).getByText("Reading the files…", { exact: true })).toBeVisible();
    // Saved from outside: the revision that reads the save lands while the preview is held.
    const before = newest;
    const description = join(gui.directory, "demo.ddd.json");
    writeFileSync(description, `${readFileSync(description, "utf8")}\n`);
    await expect.poll(() => newest, { timeout: 15_000 }).toBeGreaterThan(before);
  } finally {
    release();
  }
  // The held preview, let through, takes edit 2 off; the edit before it is offered, and the
  // strip says once why edit 2 went - in the take-off's words alone.
  await expect(page.getByRole("button", { name: "Undo the unit of ValueA" })).toBeVisible();
  await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await expect(strip(page).getByRole("status").locator("p")).toHaveText([
    "demo.ddd.json changed on disk since it was written, so the vocabulary adopted can no " +
      "longer be undone. Nothing was put back; the page shows the files as they are.",
  ]);
  expect(asked).toBe(1);
});

test("two edits of one file saved from outside both leave the stack, each said in the strip", async ({
  page,
  gui,
}) => {
  // Both write Controller's file: its unit of ValueA settled, then its limits from the same panel.
  await settledAndAnalysed(page, gui);
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("row", { name: /^limits/ }).click();
  await panel.getByLabel("Max").fill("50");
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  const undo = page.getByRole("button", { name: "Undo the limits of ValueA" });
  await expect(undo).toBeVisible();

  // The one save refuses both: the second edit's undo, and then the first's, which would put the
  // file back to what it held before the second.
  driftIn(gui.directory, CONTROLLER, "ValueA", "kPa");
  await undo.click();
  // Once nothing is left, the strip says both, in the order they went: asked only then, neither
  // is a preview's own refusal drawn a moment before the state moved.
  await expect(page.getByRole("button", { name: "Nothing left to undo" })).toBeVisible();
  await expect(strip(page).getByRole("status").locator("p")).toHaveText([
    "controller.ddd.json changed on disk since it was written, so the limits of ValueA can no " +
      "longer be undone. Nothing was put back; the page shows the files as they are.",
    "controller.ddd.json changed on disk since it was written, so the unit of ValueA can no " +
      "longer be undone. Nothing was put back; the page shows the files as they are.",
  ]);
  await expect(strip(page).getByRole("button", { name: /^Put back/ })).toHaveCount(0);
  expect(unitOfValueA(gui)).toBe("kPa");
});

test("a window behind the server names the edit it asked to preview, once another window took it off", async ({
  page,
  gui,
}) => {
  // Two edits of Controller's file in this window: its unit of ValueA settled, then its limits.
  await settledAndAnalysed(page, gui);
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("row", { name: /^limits/ }).click();
  await panel.getByLabel("Max").fill("50");
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  const ours = page.getByRole("button", { name: "Undo the limits of ValueA" });
  await expect(ours).toBeVisible();

  // A second window on the same server, its strip open on the limits, every preview it asks for
  // held: whatever it asks is answered only once this window has emptied the stack.
  const other = await page.context().newPage();
  try {
    await other.goto(gui.address);
    const theirs = other.getByRole("button", { name: "Undo the limits of ValueA" });
    await expect(theirs).toBeVisible();
    const release = await held(other, "/api/undo", { every: true });
    try {
      await theirs.click();
      driftIn(gui.directory, CONTROLLER, "ValueA", "kPa");
      await ours.click();
      await expect(page.getByRole("button", { name: "Nothing left to undo" })).toBeVisible();
      await expect(strip(page).getByRole("status").locator("p")).toHaveCount(2);
    } finally {
      release();
    }
    // Answered now, the other window's preview is refused as of the edit it named, which it says
    // can no longer be undone, where a preview of whatever was on top answered that nothing was
    // left and it said nothing at all.
    await expect(other.getByRole("button", { name: "Nothing left to undo" })).toBeVisible();
    await expect(strip(other).getByRole("status")).toContainText(
      "edit 2 is not the one to undo any more, so the limits of ValueA can no longer be undone. " +
        "Nothing was put back; the page shows the files as they are.",
    );
  } finally {
    await other.close();
  }
});

test("a preview refused after the strip was closed leaves nothing standing beside the name", async ({
  page,
  gui,
}) => {
  await settledAndAnalysed(page, gui);
  const undo = page.getByRole("button", { name: "Undo the unit of ValueA" });
  // The strip opened and closed again while its preview is held: the reader chose before the
  // answer came.
  const release = await held(page, "/api/undo");
  try {
    await undo.click();
    await expect(strip(page).getByText("Reading the files…", { exact: true })).toBeVisible();
    await undo.click();
    await expect(strip(page)).toHaveCount(0);
  } catch (error) {
    release();
    throw error;
  }
  // Saved from outside meanwhile, so that the preview, let through now, is refused and the edit
  // taken off the stack.
  driftIn(gui.directory, CONTROLLER, "ValueA", "kPa");
  const refused = page.waitForResponse(
    (response) => new URL(response.url()).pathname === "/api/undo" && response.status() === 409,
  );
  release();
  await refused;
  // The control goes with the edit, and no word of it is left standing with the strip closed.
  await expect(undo).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Nothing left to undo" })).toHaveCount(0);
});

test("a preview refused for a file that cannot be read is read again from the strip, which then offers the edit", async ({
  page,
  gui,
}) => {
  await settledAndAnalysed(page, gui);
  // The server refuses the preview of a file it cannot read, and keeps the edit (R22). The route
  // answers this one preview as it does, word for word: a mode does not stop a read on Windows,
  // and a journey runs there too. Every later request goes to the server.
  let refused = 0;
  await page.route(
    (url) => url.pathname === "/api/undo",
    async (route) => {
      if (route.request().method() !== "GET" || refused > 0) {
        await route.fallback();
        return;
      }
      refused += 1;
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          error: "stale",
          message: "controller.ddd.json can no longer be read",
        }),
      });
    },
  );
  await page.getByRole("button", { name: "Undo the unit of ValueA" }).click();
  await expect(strip(page).getByRole("status")).toHaveText(
    "controller.ddd.json can no longer be read. Nothing was put back; the page shows the files " +
      "as they are.",
  );
  await expect(strip(page).getByRole("button", { name: /^Put back/ })).toHaveCount(0);

  // The file mended, the strip reads it again, never closed, and offers the edit whole.
  await strip(page).getByRole("button", { name: "Read the files again" }).click();
  await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await expect(strip(page).getByRole("status")).toHaveCount(0);
  await strip(page).getByRole("button", { name: "Put back 1 file" }).click();
  await expect.poll(() => unitOfValueA(gui)).toBe("rpm");
  expect(refused).toBe(1);
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

/** ValueA's disagreement settled from Controller's panel, and the analysis of that edit landed.
 * The strip's preview is asked under the revision the page holds (`["undo", at, revision]`), so
 * one asked before that analysis lands is asked again when it does: a journey that holds or
 * fails the preview waits for the heading to stop saying the findings are updating first. */
async function settledAndAnalysed(page: Page, gui: Gui): Promise<void> {
  drift(gui.directory);
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  // Analysed: the heading's status says what Apply wrote, and no longer that the findings are
  // updating (16:I13).
  await expect(page.locator(".updating-status")).toHaveText(
    "Wrote 1 file for the unit of ValueA: controller.ddd.json.",
  );
}

/** The unit Controller's file states for ValueA. */
function unitOfValueA(gui: Gui): string | undefined {
  const text = readFileSync(join(gui.directory, CONTROLLER), "utf8");
  return /"name": "ValueA"[\s\S]*?"unit": "([^"]*)"/.exec(text)?.[1];
}

test("the strip says it is reading the files an undo would put back, until it has", async ({
  page,
  gui,
}) => {
  await settledAndAnalysed(page, gui);
  const release = await held(page, "/api/undo");
  try {
    await page.getByRole("button", { name: "Undo the unit of ValueA" }).click();
    await expect(strip(page).getByText("Reading the files…", { exact: true })).toBeVisible();
    await expect(strip(page).getByRole("button", { name: "Put back 1 file" })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await expect(strip(page).getByRole("button", { name: "Put back 1 file" })).toBeVisible();
  await expect(strip(page).getByText("Reading the files…", { exact: true })).toHaveCount(0);
});

test("an undo the server fails on is refused in the strip in its words, and offered again there, each press sent once", async ({
  page,
  gui,
}) => {
  await settledAndAnalysed(page, gui);
  const undo = page.getByRole("button", { name: "Undo the unit of ValueA" });
  await undo.click();
  await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  const putBack = strip(page).getByRole("button", { name: "Put back 1 file" });
  // Only now, with the preview read: the one request it meets is the press's `POST`. The preview
  // is asked again at a new revision only, and none is coming.
  const failed = await failing(page, "/api/undo", "http", 1);
  await putBack.click();
  // The refusal is said, and the entry, still on the stack, is offered again under it, whole: the
  // reader presses again with no need to close the strip (R22).
  await expect(strip(page).getByRole("status")).toHaveText(
    `The undo was refused: ${SERVER_FAILED}`,
  );
  await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await expect(putBack).toBeEnabled();
  // A guard against a write by another path: the POST is answered by `failing`, not the server.
  expect(unitOfValueA(gui)).toBe("%");
  // A `POST` is never sent again of itself (`sentAgain`, client.ts): a press sends each one.
  expect(failed()).toBe(1);
  await putBack.click();
  await expect.poll(() => unitOfValueA(gui)).toBe("rpm");
  await expect(undo).toHaveCount(0);
  expect(failed()).toBe(1);
});

test("an undo refused because a file is read-only is offered again in the strip, and goes through once the file is writable", async ({
  page,
  gui,
}) => {
  await settledAndAnalysed(page, gui);
  const controller = join(gui.directory, CONTROLLER);
  await page.getByRole("button", { name: "Undo the unit of ValueA" }).click();
  const putBack = strip(page).getByRole("button", { name: "Put back 1 file" });
  await expect(putBack).toBeVisible();
  chmodSync(controller, 0o444);
  try {
    await putBack.click();
    await expect(strip(page).getByRole("status")).toHaveText(
      /^The undo was refused: .*controller\.ddd\.json is read-only, so nothing was put back$/,
    );
    // Nothing was written, and the edit stays on the stack, offered again under the sentence.
    expect(unitOfValueA(gui)).toBe("%");
    await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
    await expect(putBack).toBeEnabled();
  } finally {
    chmodSync(controller, 0o644);
  }
  // The file made writable again, the same press goes through, the strip never closed between.
  await putBack.click();
  await expect.poll(() => unitOfValueA(gui)).toBe("rpm");
  await expect(strip(page)).toHaveCount(0);
});

test("an undo refused keeps its sentence for its own entry, and an edit made with the strip open is offered to undo", async ({
  page,
  gui,
}) => {
  await settledAndAnalysed(page, gui);
  await page.getByRole("button", { name: "Undo the unit of ValueA" }).click();
  await expect(strip(page).getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  // The press's `POST` alone fails: the preview the next entry asks for goes through.
  await failing(page, "/api/undo", "http", 1);
  await strip(page).getByRole("button", { name: "Put back 1 file" }).click();
  const refused = strip(page).getByRole("status");
  await expect(refused).toHaveText(`The undo was refused: ${SERVER_FAILED}`);

  // Another edit, from the panel still open, while the strip stays open: the top of the stack is
  // that edit now, and the refusal was of the one before it. The strip offers the new entry - its
  // preview and its Put back - and no longer says what was refused of the old one.
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("row", { name: /^limits/ }).click();
  await panel.getByLabel("Max").fill("50");
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  await expect(page.getByRole("button", { name: "Undo the limits of ValueA" })).toBeVisible();
  await expect(strip(page).getByRole("button", { name: /^Put back/ })).toBeVisible();
  await expect(refused).toHaveCount(0);
});

test("a preview the server fails on is said to have failed in the strip, before any undo was asked", async ({
  page,
  gui,
}) => {
  await settledAndAnalysed(page, gui);
  // Registered before the strip is opened, whose first ask is the preview's `GET`: failed, it
  // leaves no "Put back" to press, so no `POST` follows. Nothing was refused, and no undo asked:
  // the strip says that reading the files failed.
  const failed = await failing(page, "/api/undo", "http");
  await page.getByRole("button", { name: "Undo the unit of ValueA" }).click();
  await expect(strip(page).getByRole("status")).toHaveText(
    `Reading the files failed: ${SERVER_FAILED}.`,
  );
  await expect(strip(page).getByRole("button", { name: /^Put back/ })).toHaveCount(0);
  expect(unitOfValueA(gui)).toBe("%");
  expect(failed()).toBe(1);
});

test("an Undo button of a long label appearing moves neither Add a declaration nor the table", async ({
  page,
  copiedGui,
}) => {
  // A variable of 86 characters: the label of its unit's undo is 100 characters long.
  const variable = "V".repeat(86);
  const gui = await copiedGui("demo", (directory) => renameValueA(directory, variable));
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const add = page.getByRole("button", { name: "Add a declaration" });
  const table = page.getByRole("grid").first();
  await expect(add).toBeVisible();
  const [addBefore, tableBefore] = [await add.boundingBox(), await table.boundingBox()];
  await page.getByRole("button", { name: `Set the unit of ${variable}` }).click();
  const panel = page.getByRole("complementary", { name: variable });
  const picker = panel.getByRole("combobox", { name: `Unit of ${variable}` });
  await picker.fill("rpm");
  await page.getByRole("option", { name: "rpm", exact: true }).first().click();
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  const undo = page.getByRole("button", { name: /^Undo / });
  await expect(undo).toBeVisible();
  await panel.getByRole("button", { name: /^Close/ }).click();
  expect((await add.boundingBox())?.y).toBe(addBefore?.y);
  expect((await table.boundingBox())?.y).toBe(tableBefore?.y);
});

/**
 * The Undo control joins a heading's row after the controls in it, just before the row's status,
 * as the project's own heading has it (16:M23): drawn before Add a declaration and the way back to
 * the tab the page was reached from, it moved both by its width as an Apply's edit reached the
 * state, and a press made on either then opened the strip.
 */
test("Add a declaration and the way back keep their place in a component's heading as the Undo control joins it", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  const add = page.getByRole("button", { name: "Add a declaration" });
  const back = page.getByRole("button", { name: "Back to Graph", exact: true });
  await expect(panel.getByRole("combobox", { name: "Unit of ValueA" })).toBeVisible();
  await expect(back).toBeVisible();
  const before = [await placed(add), await placed(back)];
  await chooseUnit(page, "rpm");
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(page.getByRole("button", { name: "Undo the unit of ValueA" })).toBeVisible();
  expect([await placed(add), await placed(back)]).toEqual(before);
});
