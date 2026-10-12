import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { PUMP } from "./demo";
import { expect, type Gui, test } from "./fixtures";

/** Each vocabulary's file in a copy of examples/vocabulary: its name, which is also the key its
 * list of entries sits under, and the key each entry is named by. */
const FILES = {
  constants: { file: "constants.ddd.json", named: "name" },
  sections: { file: "sections.ddd.json", named: "section" },
  rasters: { file: "rasters.ddd.json", named: "raster" },
} as const;

type Vocabulary = keyof typeof FILES;

/** The entries of one vocabulary's file in a copy, as the file holds them on disk. */
function entriesOf(directory: string, vocabulary: Vocabulary): Record<string, unknown>[] {
  const text = readFileSync(join(directory, FILES[vocabulary].file), "utf8");
  return (JSON.parse(text) as Record<Vocabulary, Record<string, unknown>[]>)[vocabulary];
}

/** One entry of a vocabulary's file in a copy, found by its name, as the file holds it. */
function entryOf(directory: string, vocabulary: Vocabulary, name: string): Record<string, unknown> {
  const entry = entriesOf(directory, vocabulary).find(
    (each) => each[FILES[vocabulary].named] === name,
  );
  if (entry === undefined) throw new Error(`${FILES[vocabulary].file} declares no ${name}`);
  return entry;
}

/** One of Pump's own definitions in the copy's pump.ddd.json, as the file holds it on disk. */
function definitionOf(directory: string, name: string): Record<string, unknown> {
  const { component } = JSON.parse(readFileSync(join(directory, PUMP), "utf8")) as {
    component: { interface: { definition: Record<string, unknown> }[] };
  };
  const found = component.interface.find((each) => each.definition.name === name);
  if (found === undefined) throw new Error(`${PUMP} declares no ${name}`);
  return found.definition;
}

/** Opens an entry's panel the way a reader reaches it: the project, its Shared files tab, then
 * the entry's own row. */
async function openEntry(page: Page, gui: Gui, name: string): Promise<Locator> {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  await page.getByRole("row", { name, exact: true }).click();
  return page.getByRole("complementary", { name });
}

test("a raster nothing measures in is removed, row and panel", async ({ page, vocabularyGui }) => {
  const kept = entriesOf(vocabularyGui.directory, "rasters").filter(
    (entry) => entry.raster !== "100ms",
  );
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  const row = page.getByRole("row", { name: /^100ms/ });
  await row.click();
  const panel = page.getByRole("complementary", { name: "100ms" });
  await expect(panel.getByText("Nothing in the project measures in 100ms.")).toBeVisible();

  // The removal's own plan, shown before the press that applies it: no "Apply to 1 file" here,
  // the button itself says what it does.
  const removing = panel.getByRole("region", { name: "Remove from the rasters" });
  await expect(removing.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await removing.getByRole("button", { name: "Remove from the rasters" }).click();
  await expect(row).toHaveCount(0);
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=shared$/);
  // Gone as the reader asked, so the tab says nothing of its going.
  await expect(page.getByText("no longer declared")).toHaveCount(0);
  // The entry alone, out of the file: the other two rasters are as they were.
  await expect.poll(() => entriesOf(vocabularyGui.directory, "rasters")).toEqual(kept);
});

test("a raster's event, cycle and description are each saved from its panel, and an event another raster claims is refused", async ({
  page,
  vocabularyGui,
}) => {
  const directory = vocabularyGui.directory;
  const before = entryOf(directory, "rasters", "100ms");
  const panel = await openEntry(page, vocabularyGui, "100ms");

  const event = panel.getByRole("region", { name: "Event" });
  const eventField = event.getByRole("textbox", { name: "Event" });
  await expect(eventField).toHaveValue("2");
  await eventField.fill("5");
  await expect(event.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await event.getByRole("button", { name: "Save" }).click();
  await expect.poll(() => entryOf(directory, "rasters", "100ms")).toEqual({ ...before, event: 5 });
  await expect(event.getByText("Changes 1 file")).toHaveCount(0);

  const cycle = panel.getByRole("region", { name: "Cycle" });
  const cycleField = cycle.getByRole("textbox", { name: "Cycle" });
  await expect(cycleField).toHaveValue("100ms");
  await cycleField.fill("50ms");
  await expect(cycle.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await cycle.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "rasters", "100ms"))
    .toEqual({ ...before, event: 5, cycle: "50ms" });
  await expect(cycle.getByText("Changes 1 file")).toHaveCount(0);

  const describing = panel.getByRole("region", { name: "Description" });
  const description = describing.getByRole("textbox", { name: "Description" });
  await expect(description).toHaveValue("diagnostic task");
  await description.fill("slow diagnostic task");
  await expect(describing.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await describing.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "rasters", "100ms"))
    .toEqual({ ...before, event: 5, cycle: "50ms", description: "slow diagnostic task" });
  await expect(describing.getByText("Changes 1 file")).toHaveCount(0);
  await expect(page.getByRole("row", { name: "100ms", exact: true })).toContainText(
    "event 5, 50ms",
  );

  // An event is the project's alone: 1ms already claims 0, so there is nothing to save.
  await eventField.fill("0");
  await expect(event.getByRole("status")).toHaveText("event 0 is already claimed by raster '1ms'");
  await expect(event.getByRole("button", { name: "Save" })).toHaveCount(0);
});

/** Records, from now on and at every frame the page paints, the name of every panel drawn beside
 * the table, each once, in the order they first came: what a reader sees at each paint, which a
 * wait on any one moment can step over - a panel swapped for another and back within a few
 * frames. Read back with `panelsSeen`. */
async function watchPanels(page: Page): Promise<void> {
  await page.evaluate(() => {
    const seen: string[] = [];
    (window as unknown as { panelsSeen: string[] }).panelsSeen = seen;
    const each = () => {
      for (const aside of document.querySelectorAll("aside")) {
        const name = aside.getAttribute("aria-label") ?? "";
        if (!seen.includes(name)) seen.push(name);
      }
      requestAnimationFrame(each);
    };
    requestAnimationFrame(each);
  });
}

/** Every panel `watchPanels` has seen so far, in the order they first came. */
function panelsSeen(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as unknown as { panelsSeen: string[] }).panelsSeen);
}

test("a raster is renamed everywhere, its panel moving straight to the new name, and a rename onto another raster's name is refused", async ({
  page,
  vocabularyGui,
}) => {
  const directory = vocabularyGui.directory;
  const before = entryOf(directory, "rasters", "1ms");
  const panel = await openEntry(page, vocabularyGui, "1ms");
  const renaming = panel.getByRole("region", { name: "Rename" });
  await renaming.getByRole("textbox", { name: "Rename 1ms to" }).fill("2ms");
  await expect(
    renaming.getByText("Changes 2 files: pump.ddd.json, rasters.ddd.json"),
  ).toBeVisible();
  await watchPanels(page);
  await renaming.getByRole("button", { name: "Apply to 2 files" }).click();

  // The raster and the one definition measured in it, both renamed; and the panel moved onto the
  // new spelling with nothing drawn between the two - not the form declaring "2ms", which the
  // table, not listing it yet, would have had the tab open instead.
  const moved = page.getByRole("complementary", { name: "2ms" });
  await expect(moved.getByRole("textbox", { name: "Rename 2ms to" })).toBeVisible();
  await expect(page).toHaveURL(/\/project\?view=shared&kind=raster&name=2ms$/);
  expect(entryOf(directory, "rasters", "2ms")).toEqual({ ...before, raster: "2ms" });
  expect(definitionOf(directory, "PumpSpeed").raster).toBe("2ms");
  expect(await panelsSeen(page)).toEqual(["1ms", "2ms"]);

  // Onto a name the vocabulary already declares: refused before anything is written, and
  // nothing left to press to write it anyway.
  await moved.getByRole("textbox", { name: "Rename 2ms to" }).fill("10ms");
  await expect(moved.getByRole("region", { name: "Rename" }).getByRole("status")).toHaveText(
    "'10ms' is already a raster this project declares",
  );
  await expect(moved.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
});

/** The Shared files tab loaded at an address naming one entry - a link from a finding, or a
 * bookmark - as a page opened there loads it. Signed in first at the address ddd gui printed,
 * whose token the page keeps for the next address this tab opens. */
async function openAt(
  page: Page,
  gui: Gui,
  kind: "constant" | "section" | "raster",
  name: string,
): Promise<void> {
  await page.goto(gui.address);
  await expect(page.getByRole("link", { name: "Shared files", exact: true })).toBeVisible();
  const origin = new URL(gui.address).origin;
  await page.goto(`${origin}/project?view=shared&kind=${kind}&name=${encodeURIComponent(name)}`);
}

test("a raster nothing declares any longer closes the panel an address opened, and the tab says so, even when the table hears of it first", async ({
  page,
  vocabularyGui,
}) => {
  const path = join(vocabularyGui.directory, FILES.rasters.file);
  // Its panel reached from an address rather than its row: no move of the tab's own picked it,
  // so all that holds it is that the tab drew it.
  await openAt(page, vocabularyGui, "raster", "100ms");
  const panel = page.getByRole("complementary", { name: "100ms" });
  await expect(panel.getByRole("textbox", { name: "Rename 100ms to" })).toBeVisible();

  // The panel's next read of the raster is held until the table has answered without it - the
  // order that swapped the panel for the form declaring "100ms", where the tab should have said
  // the raster went. Held once, and let through whatever happens below.
  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    (url) => url.pathname === "/api/raster" && url.searchParams.get("name") === "100ms",
    async (route) => {
      await released;
      await route.continue();
    },
    { times: 1 },
  );
  try {
    // Rewritten from outside without 100ms's entry, and still a rasters file that loads.
    const declared = JSON.parse(readFileSync(path, "utf8")) as { rasters: { raster: string }[] };
    declared.rasters = declared.rasters.filter((raster) => raster.raster !== "100ms");
    writeFileSync(path, `${JSON.stringify(declared, null, 2)}\n`);
    await expect(page.getByRole("row", { name: "100ms", exact: true })).toHaveCount(0);
    // The table no longer lists it, and the panel is still the raster's own, waiting for its
    // own answer to say why.
    await expect(panel.getByRole("textbox", { name: "Rename 100ms to" })).toBeVisible();
  } finally {
    release();
  }

  const gone = page.getByRole("status").filter({ hasText: "no longer declared" });
  await expect(gone).toHaveText("100ms is no longer declared in the open project.");
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=shared$/);
});
