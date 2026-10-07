import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, chooseUnit, openPanel } from "./demo";
import { expect, test } from "./fixtures";

/** ValueA's own definition in `file` of the copy on the drive, read back as written. */
function valueA(directory: string, file: string): { unit?: string } {
  const data = JSON.parse(readFileSync(join(directory, file), "utf8"));
  return data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueA",
  ).definition;
}

test("a project on a mapped drive is served by its network path, and edited through it", async ({
  page,
  mappedGui,
}) => {
  const token = new URL(mappedGui.address).searchParams.get("token");
  const headers = { authorization: `Bearer ${token}` };

  // Windows names a mapped drive's directory by the network path it maps (P18-12): every file
  // the server answers is named so, and the page sends those names back.
  const state = (await (
    await fetch(new URL("/api/state", mappedGui.address), { headers })
  ).json()) as {
    files: { path: string }[];
  };
  expect(state.files.length).toBeGreaterThan(0);
  for (const file of state.files) {
    expect(file.path.toLowerCase()).toMatch(/^\/\/localhost\/ddd-mapped\//);
  }

  // An edit through the page, written through the share: applied as units.spec.ts applies it,
  // once the plan names both files that declare ValueA.
  const panel = await openPanel(page, mappedGui.address, "ValueA");
  await chooseUnit(page, "rpm");
  await expect(
    panel.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect.poll(() => valueA(mappedGui.directory, CONTROLLER).unit).toBe("rpm");
  await expect(panel.getByText("Nothing to change")).toBeVisible();

  // A file added under the drive: created beside the description through the share, by the
  // network path the page sends back for a file not there yet, and read by the analysis after
  // it - the row's kind is the state's, read off the file (files.spec.ts).
  await page.getByRole("button", { name: "DemoDevice" }).click();
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "New file" }).click();
  const creating = page.getByRole("complementary", { name: "New file" });
  const kind = creating.getByRole("combobox", { name: "Kind" });
  await kind.fill("component");
  await kind.press("Enter");
  await creating.getByRole("textbox", { name: "File name" }).fill("valve");
  await creating.getByRole("textbox", { name: "Component name" }).fill("Valve");
  await expect(creating.getByText("Changes 2 files: demo.ddd.json, valve.ddd.json")).toBeVisible();
  await creating.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(page.getByRole("row", { name: "valve.ddd.json" })).toContainText("component");
  expect(existsSync(join(mappedGui.directory, "valve.ddd.json"))).toBe(true);

  // A network path beside the directory served is refused, in the server's own words.
  const beside = new URL("/api/file", mappedGui.address);
  beside.searchParams.set("path", "//localhost/ddd-mapped-other/a.ddd.json");
  const refused = await fetch(beside, { headers });
  expect(refused.status).toBe(400);
  expect(await refused.json()).toEqual({
    error: "bad-request",
    message: "file takes ?path= as a file's path",
  });
});
