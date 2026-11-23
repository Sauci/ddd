import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { crowd, dump, held } from "./demo";
import { expect, test } from "./fixtures";

/**
 * Whether `target` sits inside `.findings-window`'s own visible rect - the Findings tab's own
 * hand-rolled box (task 7's `lib/findingsWindow.ts`), scrolled in place of a row rather than
 * anchored to one, never virtualised by React Aria's own `Virtualizer` the way every other long
 * table is (task 9) - so `demo.ts`'s own `withinBox`, which reads the bounds of the `role="grid"`
 * it is given, is the wrong box here: that role names the `<Table>` React Aria renders inside
 * `.findings-window`, sized to every row drawn, above and below the box's own 495px rather than
 * clipped to it.
 */
async function withinFindingsWindow(page: Page, target: Locator): Promise<boolean> {
  const container = await page.locator(".findings-window").boundingBox();
  const rect = await target.boundingBox();
  return (
    container !== null &&
    rect !== null &&
    rect.y >= container.y &&
    rect.y + rect.height <= container.y + container.height
  );
}

/** One frame as a reader saw it: the unit cell's own text, and whether the heading says its
 * findings are updating - the same technique `demo.ts`'s own `watchFrames`/`framesWatched` use
 * for a field and an undo offer, read here for a button and the heading's status region instead,
 * so that two things true at once - the cell already reading the applied unit, the heading still
 * saying "Updating the findings…" - are read off one continuous recording rather than two
 * separate waits in a row, which nothing stops the page from racing (the second settling before
 * the first is even asked for). */
type UnitFrame = readonly [cell: string | null, updating: boolean];

async function watchUnitCell(page: Page): Promise<void> {
  await page.evaluate(() => {
    const frames: UnitFrame[] = [];
    (window as unknown as { watchedUnit: UnitFrame[] }).watchedUnit = frames;
    const each = () => {
      const cell = document.querySelector<HTMLElement>(
        '[aria-label="Set the unit of C00000_O0000"]',
      );
      const status = document.querySelector(".updating-status");
      // Said after what the page wrote, where it says that too (16:I13).
      const updating = status?.textContent?.endsWith("Updating the findings…") === true;
      frames.push([cell?.textContent ?? null, updating]);
      requestAnimationFrame(each);
    };
    requestAnimationFrame(each);
  });
}

/** Every frame `watchUnitCell` has recorded so far, in order. */
function unitFramesWatched(page: Page): Promise<UnitFrame[]> {
  return page.evaluate(() => (window as unknown as { watchedUnit: UnitFrame[] }).watchedUnit);
}

/** One frame of the Findings tab as a reader saw it: what the line beside its filter says, and how
 * many rows its box draws - recorded as `watchUnitCell` records, from one continuous recording. */
type ListingFrame = readonly [line: string, rows: number];

async function watchListing(page: Page): Promise<void> {
  await page.evaluate(() => {
    const frames: ListingFrame[] = [];
    (window as unknown as { watchedListing: ListingFrame[] }).watchedListing = frames;
    const each = () => {
      const line = document.querySelector(".filter-line")?.textContent ?? "";
      frames.push([line, document.querySelectorAll(".findings-window [data-index]").length]);
      requestAnimationFrame(each);
    };
    requestAnimationFrame(each);
  });
}

/** Every frame `watchListing` has recorded so far, in order. */
function listingFramesWatched(page: Page): Promise<ListingFrame[]> {
  return page.evaluate(
    () => (window as unknown as { watchedListing: ListingFrame[] }).watchedListing,
  );
}

/**
 * An edit shows at once, and its findings follow (design doc §5-6, tasks 6 and 8): the component
 * page's own cell already reads the unit just applied while "Updating the findings…" stands in
 * the heading, and once the analysis lands the note is gone and the Findings tab's own line
 * counts what changed.
 *
 * This task's own brief asks for `C00000_O0000` set to `Nm` here, on the reading that its one
 * reader (`C00636`, both generated stating `rpm`) would then disagree with it. Measured by hand
 * instead, against a running `ddd gui` over a project this same generator makes - `GET
 * /api/settle` previewed and then applied, the exact request `VariablePanel.tsx`'s own picker
 * sends (`getSettle`/`POST /api/edit`) - picking a unit always settles *every* declaration of
 * the variable onto it in the same edit: `skeleton.spec.ts`'s own "a unit set from the panel is
 * written as one value in every file declaring it" already pins this for the demo project, and
 * `generate_project.py`'s own declarations agree with their reader by construction (its
 * docstring: "each reader stating what its producer states"), so no pair in a project it
 * generates can be moved into disagreement this way - applying `Nm` left both files reading
 * `Nm`, agreeing, and the error count at zero where the brief expected it to rise. What *does*
 * raise it from zero, through this very same picker, is a unit outside the project's own
 * vocabulary of eight - `unknown-unit`, filed on both files once they agree on one - which is
 * what this journey asks for in `Nm`'s place, keeping everything else the brief names: the Table
 * tab, component `C00000`, its first output `C00000_O0000`, and the sequence of what a reader
 * sees.
 */
test("an edit shows at once, and its findings follow", async ({ page, generatedGui }) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.locator(".summary")).not.toContainText("error");

  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "C00000", exact: true }).click();
  const cell = page.getByRole("button", { name: "Set the unit of C00000_O0000" });
  await cell.click();

  const panel = page.getByRole("complementary", { name: "C00000_O0000" });
  const picker = panel.getByRole("combobox", { name: "Unit of C00000_O0000" });
  await picker.fill("XYZ");
  await picker.press("Enter");
  await expect(panel.getByText("Changes 2 files", { exact: false })).toBeVisible();

  // Armed before Apply, not after: the two things a reader sees - the cell already reading the
  // applied unit, the heading still saying "Updating the findings…" - can land in either order
  // from here, so this records every frame rather than asking for them one after the other,
  // which nothing stops the second settling before the first is even asked for (review fix
  // round 1). The panel's own `.panel-refusal` also carries a `role="status"`, once Apply has
  // written the files and this re-asks its own settlement against them before the analysis has
  // landed - "an edit that wrote c00000.ddd.json has not been analysed yet, so this change can
  // be planned once it has" - which is why the heading's own region is read by its class here,
  // not its role.
  await watchUnitCell(page);
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();

  // A frame where the cell already reads XYZ while the heading still says the findings are
  // updating - proving the one shows at once and the other lags, not merely that both happen
  // somewhere in the run - followed, once settled, by the cell holding XYZ with nothing left
  // updating. Fails outright, rather than racing, if either never happens.
  await expect
    .poll(async () => {
      const frames = await unitFramesWatched(page);
      const shownWhileUpdating = frames.some(([unit, updating]) => unit === "XYZ" && updating);
      const last = frames.at(-1);
      return shownWhileUpdating && last?.[0] === "XYZ" && last[1] === false;
    })
    .toBe(true);

  // The component's own page carries no tabs of its own (spec 5.4): back to the project through
  // the masthead's own link, named "Generated" - `generate_project.py`'s own fixed project name -
  // before the Findings tab is there to follow.
  await page.getByRole("button", { name: "Generated" }).click();
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.locator(".summary")).toContainText("errors");
});

/**
 * The Findings table scrolled to its end (task 7's paging, task 9's window): the tab's line
 * counts every finding the project has, and the box's own 495px, scrolled to its bottom - one
 * large wheel rather than the many small ones `demo.ts`'s own `scrolledIntoView` sends a short
 * table, which would need thousands of them to cross a list this long - shows the last row,
 * `data-index="24999"` of 25,000, which is one of the last component's own `c00665.ddd.json`
 * (confirmed against this fixture's own generated project: findings sort worst first and,
 * within one severity, by file, so the last of the 15,000 `missing-id` notes - info, the
 * mildest severity this clean a project carries, which is why they sort after `unused-output`'s
 * warnings rather than before them - are this file's). `data-index`, not the file name alone:
 * `c00665.ddd.json` also names rows 9985-9999, where that same file's own `unused-output`
 * warnings end, so the name by itself cannot tell the table's middle from its end.
 */
test("the Findings table scrolled to its end", async ({ page, generatedGui }) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.locator(".summary")).toContainText("25000 findings");

  const box = page.locator(".findings-window");
  const bounds = await box.boundingBox();
  if (bounds === null) throw new Error("no .findings-window to scroll");
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.wheel(0, 2_000_000);

  const last = page.locator('[data-index="24999"]');
  await expect(last).toBeVisible();
  await expect(last).toContainText("c00665.ddd.json");
});

/**
 * Close in the Findings tab's own window after a scroll (16:I13): Enter on the first of the
 * generated project's 25,000 findings opens its panel, and the wheel takes the box thousands of
 * rows on, the window letting the first row go. Close pressed from the keyboard scrolls the window
 * back to the finding and gives the focus to its own row, once drawn - not to a row of the window's
 * the reader never touched.
 */
test("Close in the Findings window after a scroll gives the focus back to the finding's own row", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  const box = page.locator(".findings-window");
  const first = box.locator('[role="row"][data-index="0"]');
  await expect(first.locator(".chip")).toBeVisible();
  const words = await first.textContent();
  await first.focus();
  await page.keyboard.press("Enter");
  const panel = page.getByRole("complementary");
  await expect(panel).toBeVisible();

  const bounds = await box.boundingBox();
  if (bounds === null) throw new Error("no .findings-window to scroll");
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  for (let turns = 0; turns < 10; turns += 1) await page.mouse.wheel(0, 1500);
  await expect.poll(() => box.evaluate((node) => node.scrollTop)).toBeGreaterThan(10_000);
  await expect(first).toHaveCount(0);

  await panel.getByRole("button", { name: /^Close / }).focus();
  await page.keyboard.press("Enter");
  await expect(panel).toHaveCount(0);
  await expect.poll(() => rowFocused(page)).toBe(words);
  await expect(first).toBeFocused();
  await expect(first).toBeInViewport();
});

/**
 * The declare form's Name list, over the generated project's names (16:I7): React Aria
 * draws every entry of a list it is handed, so the list is narrowed by what is typed, as the unit
 * picker's is, and drawn to fifty (`NAMES_SHOWN`, lib/declarations.ts), its foot saying how many
 * more match. Opened on C00000 with nothing typed, it draws fifty of every name it could read;
 * typed key by key, `C00500_O` narrows it to that component's 15 outputs of the name, the first of
 * them first, all drawn, with nothing more to say.
 */
test("the declare form's Name list is narrowed by what is typed, and drawn to a cap", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "C00000", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  await adding.getByRole("button", { name: "Show the choices for Name" }).click();

  const options = page.getByRole("listbox").getByRole("option");
  await expect(options).toHaveCount(50);
  // The names are the server's, sorted, without the component's own (`declarable`).
  await expect(options.first()).toHaveAccessibleName("C00001_O0000");
  // 14,968 names, measured before the cap: every one was drawn.
  await expect(
    page.getByText("14,918 more names match: type to narrow the list.", { exact: true }),
  ).toBeVisible();

  await adding.getByRole("combobox", { name: "Name" }).pressSequentially("C00500_O");
  await expect(options).toHaveCount(15);
  await expect(options.first()).toHaveAccessibleName("C00500_O0000");
  await expect(options.last()).toHaveAccessibleName("C00500_O0014");
  await expect(page.getByText(/more names? match/)).toHaveCount(0);
});

/**
 * The keyboard walks past the rows drawn (task 9's window, MARGIN included): a row selected -
 * focusing it, the way React Aria's own table always does - then ArrowDown sixty times, well past
 * both the box's own dozen-odd rows in view and the MARGIN of twenty drawn beyond them
 * (`findingsWindow.ts`), so the row that stood first is no longer in the document at all, and the
 * one now focused, sixty rows on, is the one the box has followed into view.
 */
test("the keyboard walks past the rows drawn", async ({ page, generatedGui }) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  const first = page.locator('[data-index="0"]');
  // Visible alone is not enough to select: its page of findings may not have arrived yet, and
  // the row drawn meanwhile - a "Reading…" placeholder, not selectable - carries no check chip
  // (review fix round 1). Waiting for the chip is waiting for the row that selecting it, next,
  // actually needs.
  await expect(first.locator(".chip")).toBeVisible();
  await first.click();
  for (let step = 0; step < 60; step += 1) await page.keyboard.press("ArrowDown");

  const focused = page.locator('[data-index="60"]');
  await expect.poll(() => withinFindingsWindow(page, focused)).toBe(true);
  await expect(first).toHaveCount(0);
});

/**
 * Compare's table of a verdict filing two thousand findings (16:M1): drawn through `LongTable`, as
 * every long table but the Findings one is, it holds the rows in view, not the 2,000 the reply
 * carries - every one of which was in the document before - and scrolled to its end it draws the
 * last of them. The baseline is a dump of the chained project, whose analysis files nothing (the
 * generated project's 25,000 findings would overflow the dump's captured output), with every unit
 * it states spelled otherwise: each of its 2,000 objects is then no longer the same object.
 */
test("Compare's table draws the rows in view, of a verdict filing two thousand findings", async ({
  page,
  chainedGui,
}) => {
  dump(chainedGui.directory, "project.ddd.json", "baseline.json");
  const baseline = join(chainedGui.directory, "baseline.json");
  const text = readFileSync(baseline, "utf8");
  writeFileSync(baseline, text.replaceAll('"unit": "', '"unit": "x'), "utf8");

  await page.goto(chainedGui.address);
  await page.getByRole("link", { name: "Compare" }).click();
  await page.getByRole("textbox", { name: "Baseline" }).fill("baseline.json");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByText("2000 findings · 2000 errors")).toBeVisible();

  const table = page.getByRole("grid", { name: "Findings" });
  await expect(table.getByRole("row", { name: "changed-interface" }).first()).toBeVisible();
  // The header and the rows of the box's 60vh, with React Aria's margin: 19 rows measured, where
  // all 2,001 were in the document. The table still tells assistive technology of every row.
  expect(await table.getByRole("row").count()).toBeLessThan(50);
  await expect(table).toHaveAttribute("aria-rowcount", "2001");

  // The box is the table itself (`.long`, ui.css): one large wheel takes it to its end.
  const bounds = await table.boundingBox();
  if (bounds === null) throw new Error("no table to scroll");
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.wheel(0, 200_000);
  const last = table.locator('[aria-rowindex="2001"]');
  await expect(last).toBeVisible();
  await expect(last).toContainText("'C01999_O0000' is not the same object any more");
  expect(await table.getByRole("row").count()).toBeLessThan(50);
});

/**
 * A rename reaching every file of the generated project (16:M17): `rpm`, which every one of its
 * 666 components states. While the plan is asked for, the Rename section says "Planning…" where it
 * said nothing, looking as it had before Enter; once the plan has come, its sentence names three
 * of the files it writes and counts the rest, where it named every one of them above Apply.
 */
test("a rename reaching every file says it is planning, then names three files and counts the rest", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const renaming = page
    .getByRole("complementary", { name: "rpm" })
    .getByRole("region", { name: "Rename" });
  const picker = renaming.getByRole("combobox", { name: "Rename rpm to" });
  await picker.clear();
  await picker.pressSequentially("revs");

  const release = await held(page, "/api/unit-plan");
  try {
    await picker.press("Enter");
    await expect(renaming.getByText("Planning…", { exact: true })).toBeVisible();
  } finally {
    release();
  }
  await expect(renaming.getByText("Planning…")).toHaveCount(0);
  await expect(
    renaming.getByText(
      "Changes 667 files: c00000.ddd.json, c00001.ddd.json, c00002.ddd.json and 664 more. " +
        "rpm is renamed in units.ddd.json too.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(renaming.getByRole("button", { name: "Apply to 667 files" })).toBeEnabled();
});

/**
 * The Table tab's filter (16:I14): of the generated project's 666 components the table draws the
 * rows in view, so `C00500` is not in the document and no find of the browser's reaches it. Typed
 * into the filter, the table holds that one row, the line beside the field says so, and the line
 * above the table still counts the project's statements. A filter nothing matches says so, and no
 * table is drawn under it.
 */
test("the Table tab's filter finds a component the table does not draw", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Table" }).click();
  const table = page.getByRole("grid", { name: "Components" });
  await expect(table.getByRole("button", { name: "C00000", exact: true })).toBeVisible();
  await expect(table.getByRole("button", { name: "C00500", exact: true })).toHaveCount(0);

  const filter = page.getByRole("textbox", { name: "Filter components" });
  await filter.fill("nothing like it");
  await expect(filter).toHaveAccessibleDescription("no component matches");
  await expect(table).toHaveCount(0);

  await filter.fill("c00500");
  await expect(filter).toHaveAccessibleDescription("1 of 666 components");
  // A status: a screen reader hears the count as it changes.
  await expect(page.getByRole("status").filter({ hasText: "1 of 666 components" })).toBeVisible();
  await expect(table.getByRole("row")).toHaveCount(2);
  await expect(page.locator("p.summary")).toHaveText("0 errors, 10000 warnings");
  await table.getByRole("button", { name: "C00500", exact: true }).click();
  await expect(page.getByRole("heading", { name: "C00500", level: 1 })).toBeVisible();
});

/**
 * A component page's filter (16:I14): C00000's 32 declarations are more than its table draws, so
 * its last, `C00000_X0015`, is not in the document until the filter leaves it, whose row then
 * opens its panel as any row does. The filter is that component's: another component's page,
 * reached from the go-to without leaving the page, starts with none.
 */
test("a component page's filter finds a declaration its table does not draw", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "C00000", exact: true }).click();
  const table = page.getByRole("grid", { name: "Declarations of C00000" });
  await expect(table.getByRole("row", { name: /C00000_O0000/ })).toBeVisible();
  await expect(table.getByRole("row", { name: /C00000_X0015/ })).toHaveCount(0);

  const filter = page.getByRole("textbox", { name: "Filter declarations" });
  await filter.fill("x00");
  await expect(filter).toHaveAccessibleDescription("8 of 32 declarations");
  await expect(table.getByRole("row")).toHaveCount(9);
  await filter.fill("X0015");
  await expect(filter).toHaveAccessibleDescription("1 of 32 declarations");
  await table.getByRole("row", { name: /C00000_X0015/ }).click();
  await expect(page.getByRole("complementary", { name: "C00000_X0015" })).toBeVisible();

  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  await goTo.pressSequentially("C00530_O0000");
  // The name itself, not a count: while the names are on their way, the list's one row is its
  // sentence saying so.
  await expect(
    page.getByRole("listbox").getByRole("option", { name: "C00530_O0000", exact: true }),
  ).toBeVisible();
  await goTo.press("Enter");
  await expect(page.getByRole("heading", { name: "C00530", level: 1 })).toBeVisible();
  await expect(filter).toHaveValue("");
  await expect(filter).toHaveAccessibleDescription("");
  await expect(page.getByRole("grid", { name: "Declarations of C00530" })).toBeVisible();
});

/** Records each count of rows the grid named `name` says it has (`aria-rowcount`) from here on, as
 * each commit of the page draws it: a MutationObserver sees every change, painted or not, and
 * each record keeps the count it replaced. */
async function watchRowCounts(page: Page, name: string): Promise<void> {
  await page.evaluate((label) => {
    const grid = document.querySelector(`[role="grid"][aria-label="${label}"]`);
    if (grid === null) throw new Error(`no grid named ${label}`);
    const replaced: (string | null)[] = [];
    (window as unknown as { rowCountsReplaced: (string | null)[] }).rowCountsReplaced = replaced;
    new MutationObserver((records) => {
      for (const record of records) replaced.push(record.oldValue);
    }).observe(grid, {
      attributes: true,
      attributeFilter: ["aria-rowcount"],
      attributeOldValue: true,
    });
  }, name);
}

/** Every count the grid `watchRowCounts` watches has said since, in order, the one it says now
 * last. */
async function rowCountsWatched(page: Page, grid: Locator): Promise<(string | null)[]> {
  const replaced = await page.evaluate(
    () => (window as unknown as { rowCountsReplaced: (string | null)[] }).rowCountsReplaced,
  );
  return [...replaced, await grid.getAttribute("aria-rowcount")];
}

/**
 * A unit's filter (16:I14): rpm is stated 2,500 times over the generated project, and its panel's
 * table draws the places in view. Filtered by a file's name, it holds the four that file states.
 * Emptied, every place comes back to the table a thousand at a time, each thousand in a commit of
 * its own (`ROWS_PUT_BACK`, lib/filter.ts): its count of rows goes from the four left, and the
 * header's row, to all 2,500 in three steps.
 */
test("a unit's filter finds the places one file states it", async ({ page, generatedGui }) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "rpm" });
  const places = panel.getByRole("grid", { name: "Where rpm is stated" });
  await expect(places.getByRole("row", { name: /C00000_O0000/ })).toBeVisible();
  await expect(places.getByRole("row", { name: /C00530_O0008/ })).toHaveCount(0);

  const filter = panel.getByRole("textbox", { name: "Filter places" });
  await filter.fill("c00500.ddd.json");
  await expect(filter).toHaveAccessibleDescription("4 of 2,500 places");
  await expect(places.getByRole("row")).toHaveCount(5);
  for (const name of ["C00500_O0002", "C00500_O0010", "C00530_O0000", "C00530_O0008"]) {
    await expect(places.getByRole("row", { name: new RegExp(name) })).toBeVisible();
  }

  await watchRowCounts(page, "Where rpm is stated");
  await filter.fill("");
  await expect(filter).toHaveAccessibleDescription("");
  await expect(places).toHaveAttribute("aria-rowcount", "2501");
  expect(await rowCountsWatched(page, places)).toEqual(["5", "1005", "2005", "2501"]);
});

/**
 * A panel closed while its table's rows come back (16:I13): Controller given 6,000 declarations
 * more, a filter leaves out the last, whose panel is open, and emptied puts the rows back a
 * thousand at a time. Rows put back before the one holding the focus move its place, and React Aria
 * then draws another row where it stood, the focus on that one: Close pressed while they come back
 * gives the focus to the table, and to the panel's row once every row is back - drawn where it
 * stands, out of view, though the table moved its own place to ValueA meanwhile.
 */
test("Close gives the focus back to the panel's row while a widened filter puts the rows back", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => crowd(directory, 6000));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const table = page.getByRole("grid", { name: "Declarations of Controller" });
  const filter = page.getByRole("textbox", { name: "Filter declarations" });
  const last = table.getByRole("row", { name: /Crowd05999/ });
  await filter.fill("Crowd05999");
  await last.click();
  const panel = page.getByRole("complementary", { name: "Crowd05999" });
  // Its keys drawn: the panel read, never drawn anew by its answer as Close's key goes down.
  await expect(panel.getByRole("grid", { name: "Keys of Crowd05999" })).toBeVisible();
  await filter.fill("ValueA");
  await expect(last).toHaveCount(0);

  // The count of rows the table says it holds as Close's key comes up, when the panel closes.
  await page.evaluate(() => {
    const grid = document.querySelector('[role="grid"][aria-label="Declarations of Controller"]');
    const record = () => {
      (window as unknown as { rowsAtClose: string | null }).rowsAtClose =
        grid?.getAttribute("aria-rowcount") ?? null;
    };
    document.addEventListener("keyup", record, { capture: true, once: true });
  });
  await filter.fill("");
  await panel.getByRole("button", { name: "Close Crowd05999" }).focus();
  await page.keyboard.press("Enter");
  await expect(panel).toHaveCount(0);
  await expect(table).toHaveAttribute("aria-rowcount", "6015");
  await expect(last).toBeFocused();
  // Pressed while the rows came back: the table held fewer than its 6,014 and its header's row.
  const atClose = await page.evaluate(
    () => (window as unknown as { rowsAtClose: string | null }).rowsAtClose,
  );
  expect(Number(atClose)).toBeLessThan(6015);
});

/** The words of the row the focus is in, itself or a control of it: `null` where the focus is in
 * no row. */
function rowFocused(page: Page): Promise<string | null> {
  return page.evaluate(() => document.activeElement?.closest('[role="row"]')?.textContent ?? null);
}

/**
 * The focus in a table while a widened filter puts its rows back before the focused row (16:I14):
 * Controller given 6,000 declarations more, its filter leaves Crowd05999 alone, the last, and Tab
 * takes the focus to its row. Shift+Tab back to the filter, emptied, and Tab at once: the focus is
 * in the table as the rows come back a thousand at a time, every one of them before it. The row
 * the focus stands on is still Crowd05999's once they are all back - the row the table draws
 * focused, the one a screen reader names - and the arrow keys go on from it.
 */
test("the focus stays on its row while a widened filter puts the rows back before it", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => crowd(directory, 6000));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const table = page.getByRole("grid", { name: "Declarations of Controller" });
  const filter = page.getByRole("textbox", { name: "Filter declarations" });
  const last = table.getByRole("row", { name: /Crowd05999/ });
  await filter.fill("Crowd05999");
  await expect(table).toHaveAttribute("aria-rowcount", "2");
  await page.keyboard.press("Tab");
  await expect(last).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(filter).toBeFocused();

  await filter.fill("");
  await page.keyboard.press("Tab");
  await expect(table).toHaveAttribute("aria-rowcount", "6015");
  await expect(table).not.toHaveAttribute("data-rows-to-come");
  await expect.poll(() => rowFocused(page)).toMatch(/Crowd05999/);
  await expect(last).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await expect(table.getByRole("row", { name: /Crowd05998/ })).toBeFocused();
});

/**
 * Tab back into a table whose filter was widened (16:I14): of Controller's 6,000 declarations
 * more, `Crowd059` leaves the hundred last, End takes the focus to the last of them, Crowd05999,
 * and a Backspace in the filter, `Crowd05`, puts nine hundred rows back before it in one commit.
 * Tab goes back to Crowd05999's row, the row the table remembers, and the arrow keys go on from it.
 */
test("Tab back into a table its filter widened goes to the row it left", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => crowd(directory, 6000));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const table = page.getByRole("grid", { name: "Declarations of Controller" });
  const filter = page.getByRole("textbox", { name: "Filter declarations" });
  const last = table.getByRole("row", { name: /Crowd05999/ });
  await filter.fill("Crowd059");
  await expect(table).toHaveAttribute("aria-rowcount", "101");
  await page.keyboard.press("Tab");
  await page.keyboard.press("End");
  await expect(last).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(filter).toBeFocused();

  // The text Tab selects in the field left whole, its last letter taken away.
  await page.keyboard.press("End");
  await page.keyboard.press("Backspace");
  await expect(filter).toHaveValue("Crowd05");
  await expect(table).toHaveAttribute("aria-rowcount", "1001");
  await page.keyboard.press("Tab");
  await expect.poll(() => rowFocused(page)).toMatch(/Crowd05999/);
  await expect(last).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await expect(table.getByRole("row", { name: /Crowd05998/ })).toBeFocused();
});

/**
 * The Findings tab's filter (16:I14): its rows are the server's pages, so the filter asks the
 * server for the findings whose check, words or file's name hold its text. Of the generated
 * project's 25,000, `c00500` leaves the 36 filed on c00500.ddd.json, none of which stood in the
 * document before. Typed with the box scrolled to its last row, the filtered table starts at its
 * top, its first row in view; the line beside the field says how many it leaves, and the line above
 * the table goes on counting the revision's statements. A text no finding holds is said, and the
 * filter emptied brings every finding back.
 */
test("the Findings tab's filter asks the server for the findings its text finds", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  const rows = page.locator(".findings-window [data-index]");
  await expect(rows.first().locator(".chip")).toBeVisible();
  await expect(rows.filter({ hasText: "c00500.ddd.json" })).toHaveCount(0);
  const bounds = await page.locator(".findings-window").boundingBox();
  if (bounds === null) throw new Error("no .findings-window to scroll");
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.wheel(0, 2_000_000);
  await expect(page.locator('[data-index="24999"]')).toBeVisible();

  const filter = page.getByRole("textbox", { name: "Filter findings" });
  await filter.fill("c00500");
  await expect(filter).toHaveAccessibleDescription("36 of 25,000 findings");
  const first = page.locator('[data-index="0"]');
  await expect(first).toContainText("c00500.ddd.json");
  await expect.poll(() => withinFindingsWindow(page, first)).toBe(true);
  await expect(rows.filter({ hasNotText: "c00500.ddd.json" })).toHaveCount(0);
  await expect(page.locator(".summary")).toHaveText("25000 findings · 10000 warnings, 15000 infos");

  // A listing of more pages than one: each is asked under the filter, the last row of 15,000 the
  // last of c00665.ddd.json's, as in the whole list's own order.
  await filter.fill("missing-id");
  await expect(filter).toHaveAccessibleDescription("15,000 of 25,000 findings");
  await page.mouse.wheel(0, 2_000_000);
  const last = page.locator('[data-index="14999"]');
  await expect(last).toBeVisible();
  await expect(last).toContainText("missing-id");
  await expect(last).toContainText("c00665.ddd.json");

  await filter.fill("nothing like it");
  await expect(filter).toHaveAccessibleDescription("no finding matches");
  await expect(rows).toHaveCount(0);

  await filter.fill("");
  await expect(filter).toHaveAccessibleDescription("");
  await expect(rows.first().locator(".chip")).toBeVisible();
  await expect(rows.filter({ hasText: "c00500.ddd.json" })).toHaveCount(0);

  // Typed again with the box scrolled to its last row, its first page come already: drawn from its
  // first row in the very frame its line says how many it leaves, never that line over no row, as
  // the box's old place would draw it.
  await page.mouse.wheel(0, 2_000_000);
  await expect(page.locator('[data-index="24999"]')).toBeVisible();
  await watchListing(page);
  await filter.fill("c00500");
  await expect(first).toContainText("c00500.ddd.json");
  const frames = await listingFramesWatched(page);
  expect(frames.some(([line]) => line === "36 of 25,000 findings")).toBe(true);
  expect(frames.filter(([line, drawn]) => line === "36 of 25,000 findings" && drawn === 0)).toEqual(
    [],
  );
});

/**
 * The masthead's go-to (16:I14): of the generated project's 20,000 declarations, typed key by key,
 * `C005` holds more names than the go-to lists - fifty, its foot saying how many more and to type
 * to narrow them - and `C00530_O0000` one, which Enter opens on the page of C00530, producing it,
 * its panel open, the field emptied for the next. A name picked from the list opens the same way.
 */
test("the masthead's go-to opens a variable on the page of the component producing it", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  const options = page.getByRole("listbox").getByRole("option");
  await goTo.pressSequentially("C005");
  await expect(options).toHaveCount(50);
  await expect(options.first()).toHaveAccessibleName("C00500_O0000");
  await expect(
    page.getByText("2,200 more names match: type to narrow the list.", { exact: true }),
  ).toBeVisible();

  await goTo.pressSequentially("30_O0000");
  await expect(options).toHaveCount(1);
  await expect(options.first()).toHaveAccessibleName("C00530_O0000");
  await goTo.press("Enter");
  await expect(page).toHaveURL(/\/component\?file=[^&]*c00530\.ddd\.json&variable=C00530_O0000$/);
  await expect(page.getByRole("heading", { name: "C00530", level: 1 })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "C00530_O0000" })).toBeVisible();
  await expect(goTo).toHaveValue("");

  await goTo.pressSequentially("C00500_X00");
  await expect(options).toHaveCount(7);
  await options.filter({ hasText: "C00500_X0013" }).click();
  await expect(page).toHaveURL(/\/component\?file=[^&]*c00500\.ddd\.json&variable=C00500_X0013$/);
  await expect(page.getByRole("heading", { name: "C00500", level: 1 })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "C00500_X0013" })).toBeVisible();
});

/** The go-to's ask of the server for the names holding `text`, `GET /api/names?text=`. */
function namesOf(text: string): (url: URL) => boolean {
  return (url) => url.pathname === "/api/names" && url.searchParams.get("text") === text;
}

/** Every ask of the go-to's names, whatever its text. */
function everyNames(url: URL): boolean {
  return url.pathname === "/api/names";
}

/** Records the text of each ask of the go-to's names from the page's first script on, as the page
 * makes it. */
async function watchNamesAsked(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const watched = window as unknown as { namesAsked: string[] };
    watched.namesAsked = [];
    const fetching = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const href =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const url = new URL(href, window.location.href);
      if (url.pathname === "/api/names")
        watched.namesAsked.push(url.searchParams.get("text") ?? "");
      return fetching(input, init);
    };
  });
}

/** The texts `watchNamesAsked` has seen asked so far, in order. */
function namesAsked(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as unknown as { namesAsked: string[] }).namesAsked);
}

/**
 * Enter on a name typed faster than its names come (16:I14): the go-to asks for the names of what
 * is typed once typing pauses, so Enter pressed on `C00530_O0000` before then meets no answer
 * holding it - every ask is held here until the page has asked for the name, Enter pressed. Enter
 * is a commit: it asks for the text at once, and goes once the answer holding the name has come.
 */
test("Enter on a name typed faster than its names come goes to it once they come", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  const asked = page.waitForRequest((request) => namesOf("C00530_O0000")(new URL(request.url())));
  const release = await held(page, everyNames, { every: true });
  try {
    await goTo.pressSequentially("C00530_O0000");
    await goTo.press("Enter");
    await asked;
    await expect(page.getByRole("heading", { name: "C00530", level: 1 })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page).toHaveURL(/\/component\?file=[^&]*c00530\.ddd\.json&variable=C00530_O0000$/);
  await expect(page.getByRole("heading", { name: "C00530", level: 1 })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "C00530_O0000" })).toBeVisible();
  await expect(goTo).toHaveValue("");
});

/**
 * Enter asks at once for the names of the text it is pressed on (16:I14), as a commit does, where a
 * text typed is asked for once typing pauses. The page's clock is stopped here while the go-to is
 * typed into, so that no pause ends, and nothing is asked but what Enter asks. A text typed on
 * after Enter, while Enter still waits for its names, waits for a pause again, as every text typed
 * does: it is asked for once the clock goes on, and Enter's names, not its own, go nowhere.
 */
test("Enter asks at once for the names of the text it is pressed on, and typing on waits again", async ({
  page,
  generatedGui,
}) => {
  await watchNamesAsked(page);
  await page.clock.install();
  await page.goto(generatedGui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  await goTo.focus();
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 1000));
  await page.keyboard.type("C00530_O000");
  await expect(goTo).toHaveValue("C00530_O000");
  expect(await namesAsked(page)).toEqual([]);
  await page.keyboard.press("Enter");
  await expect.poll(() => namesAsked(page)).toEqual(["C00530_O000"]);
  await page.keyboard.press("0");
  await expect(goTo).toHaveValue("C00530_O0000");
  expect(await namesAsked(page)).toEqual(["C00530_O000"]);

  await page.clock.resume();
  await expect.poll(() => namesAsked(page)).toEqual(["C00530_O000", "C00530_O0000"]);
  await expect(
    page.getByRole("listbox").getByRole("option", { name: "C00530_O0000", exact: true }),
  ).toBeVisible();
  await expect(goTo).toHaveValue("C00530_O0000");
  await expect(page.getByRole("heading", { name: "C00530", level: 1 })).toHaveCount(0);
});

/**
 * Enter on a text no name spells exactly (16:I14) opens the list on the names its answer holds,
 * where it closed the list and said nothing, the field holding the text as though it had been
 * taken. `c00530_o0000`, Enter pressed before its names have come, holds `C00530_O0000` in another
 * case, which the list then offers, and a pick goes to; `nothing like it`, its answer come, still
 * says that no variable matches once Enter is pressed on it.
 */
test("Enter on a text no name spells exactly opens the list on what its answer holds", async ({
  page,
  generatedGui,
}) => {
  await page.goto(generatedGui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  const offered = page
    .getByRole("listbox")
    .getByRole("option", { name: "C00530_O0000", exact: true });
  await goTo.pressSequentially("c00530_o0000");
  await goTo.press("Enter");
  await expect(offered).toBeVisible();
  await expect(goTo).toHaveValue("c00530_o0000");
  await expect(page.getByRole("heading", { name: "C00530", level: 1 })).toHaveCount(0);
  await offered.click();
  await expect(page).toHaveURL(/\/component\?file=[^&]*c00530\.ddd\.json&variable=C00530_O0000$/);
  await expect(goTo).toHaveValue("");

  const none = page.getByRole("listbox").getByText("no variable matches", { exact: true });
  await goTo.pressSequentially("nothing like it");
  await expect(none).toBeVisible();
  await goTo.press("Enter");
  await expect(none).toBeVisible();
  await expect(goTo).toHaveValue("nothing like it");
});
