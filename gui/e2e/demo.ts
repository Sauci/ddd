import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";

export const CONTROLLER = join("components", "controller.ddd.json");
export const SENSOR_HUB = join("components", "sensor_hub.ddd.json");

/** A variable's own `"unit": ...` in a file: the first one after its name, whichever file it is. */
function unitOf(variable: string): RegExp {
  return new RegExp(`("name": "${variable}"[\\s\\S]*?"unit": )"[^"]*"`);
}

/** The bytes of a file with one variable's unit replaced, and nothing else. */
export function withUnitOf(bytes: Buffer, variable: string, unit: string): Buffer {
  const text = bytes.toString("utf8").replace(unitOf(variable), `$1${JSON.stringify(unit)}`);
  return Buffer.from(text, "utf8");
}

/** The bytes of a file with ValueA's unit replaced, and nothing else. */
export function withUnitOfValueA(bytes: Buffer, unit: string): Buffer {
  return withUnitOf(bytes, "ValueA", unit);
}

/** Controller's reading of a variable drifted to another unit, saved from outside - ValueA's to
 * `rpm` unless said otherwise; answers the file as it was before. */
export function drift(directory: string, variable = "ValueA", unit = "rpm"): Buffer {
  const file = join(directory, CONTROLLER);
  const before = readFileSync(file);
  writeFileSync(file, withUnitOf(before, variable, unit));
  return before;
}

/** ValueA renamed from outside in every file of the demo that declares or names it. */
export function renameValueA(directory: string, name: string): void {
  for (const file of [CONTROLLER, SENSOR_HUB]) {
    const path = join(directory, file);
    writeFileSync(path, readFileSync(path, "utf8").replaceAll('"ValueA"', JSON.stringify(name)));
  }
}

/** Chooses a unit for ValueA from its panel's picker: typed, then taken from the list. */
export async function chooseUnit(page: Page, unit: string): Promise<void> {
  await page.getByRole("combobox", { name: "Unit of ValueA" }).fill(unit);
  await page.getByRole("option", { name: unit, exact: true }).first().click();
}
