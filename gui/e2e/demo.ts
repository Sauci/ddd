import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";

export const CONTROLLER = join("components", "controller.ddd.json");
export const SENSOR_HUB = join("components", "sensor_hub.ddd.json");

/** ValueA's own `"unit": ...` in a file: the first one after its name, whichever file it is. */
const VALUE_A_UNIT = /("name": "ValueA"[\s\S]*?"unit": )"[^"]*"/;

/** The bytes of a file with ValueA's unit replaced, and nothing else. */
export function withUnitOfValueA(bytes: Buffer, unit: string): Buffer {
  const text = bytes.toString("utf8").replace(VALUE_A_UNIT, `$1${JSON.stringify(unit)}`);
  return Buffer.from(text, "utf8");
}

/** Controller's reading of ValueA drifted to `rpm`, saved from outside; answers the original. */
export function drift(directory: string): Buffer {
  const file = join(directory, CONTROLLER);
  const before = readFileSync(file);
  writeFileSync(file, withUnitOfValueA(before, "rpm"));
  return before;
}

/** Chooses a unit for ValueA from its panel's picker: typed, then taken from the list. */
export async function chooseUnit(page: Page, unit: string): Promise<void> {
  await page.getByRole("combobox", { name: "Unit of ValueA" }).fill(unit);
  await page.getByRole("option", { name: unit, exact: true }).first().click();
}
