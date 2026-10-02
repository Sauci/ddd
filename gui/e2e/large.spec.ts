import type { Locator, Page } from "@playwright/test";
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
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();

  // Written at once: the cell reads the applied unit before the analysis it waits on next. The
  // heading's own status region (`UpdatingStatus`, `.updating-status`) is asked for by that
  // class rather than its role alone: the panel re-asks for its own settlement once Apply has
  // written the files, and until the analysis lands that ask is refused `analysing` - "an edit
  // that wrote c00000.ddd.json has not been analysed yet, so this change can be planned once it
  // has" - which the panel shows in a `role="status"` of its own (`.panel-refusal`), found
  // alongside the heading's while both stand.
  const status = page.locator("p.updating-status");
  await expect(cell).toHaveText("XYZ");
  await expect(status).toHaveText("Updating the findings…");
  await expect(status).toHaveText("");

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
 * table, which would need thousands of them to cross a list this long - shows rows of the last
 * component's own file, `c00665.ddd.json` (confirmed against this fixture's own generated
 * project: findings sort worst first and, within one severity, by file, so the last of the
 * 15,000 `missing-id` notes - the worst severity this clean a project carries - are this file's).
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

  await expect(page.getByRole("gridcell", { name: "c00665.ddd.json" }).first()).toBeVisible();
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
  await expect(first).toBeVisible();
  await first.click();
  for (let step = 0; step < 60; step += 1) await page.keyboard.press("ArrowDown");

  const focused = page.locator('[data-index="60"]');
  await expect.poll(() => withinFindingsWindow(page, focused)).toBe(true);
  await expect(first).toHaveCount(0);
});
