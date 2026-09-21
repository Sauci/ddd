import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";

export const CONTROLLER = join("components", "controller.ddd.json");
export const SENSOR_HUB = join("components", "sensor_hub.ddd.json");
/** The files of examples/vocabulary the journeys change, in its copy: the component stating its
 * units, and the units file listing them. */
export const PUMP = "pump.ddd.json";
export const UNITS = "units.ddd.json";

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
  return driftIn(directory, CONTROLLER, variable, unit);
}

/** A variable's unit in one file of a copy drifted to another spelling, saved from outside;
 * answers the file as it was before. */
export function driftIn(directory: string, file: string, variable: string, unit: string): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  writeFileSync(path, withUnitOf(before, variable, unit));
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

/** Opens a variable's panel from its component's table, the way a reader reaches it: the unit
 * cell, which opens the panel on the unit's row with its field focused. */
export async function openPanel(
  page: Page,
  address: string,
  variable: string,
  component = "Controller",
): Promise<Locator> {
  await page.goto(address);
  await page.getByRole("button", { name: component, exact: true }).click();
  await page.getByRole("button", { name: `Set the unit of ${variable}` }).click();
  return page.getByRole("complementary", { name: variable });
}

/** One variable's linear factor in one file of a copy drifted, saved from outside; answers the
 * file as it was before. */
export function driftFactor(
  directory: string,
  file: string,
  variable: string,
  factor: number,
): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  const text = before
    .toString("utf8")
    .replace(new RegExp(`("name": "${variable}"[\\s\\S]*?"factor": )[0-9.]+`), `$1${factor}`);
  writeFileSync(path, text, "utf8");
  return before;
}
