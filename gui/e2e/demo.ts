import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";

export const CONTROLLER = join("components", "controller.ddd.json");
export const SENSOR_HUB = join("components", "sensor_hub.ddd.json");
export const USER_INTERFACE = join("components", "user_interface.ddd.json");
/** ValueE's other reader, in a sub project of its own - with UserInterface, the only demo
 * variable with one producer and two consumers, which is what lets a settlement reach one file
 * or both. */
export const EVENT_LOGGER = join("subsystems", "logging", "event_logger.ddd.json");
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

/** A table pasted into the grid the way a browser delivers one: a `DataTransfer` built in the
 * page and dispatched as a `paste` event, because Playwright cannot put a table on the system
 * clipboard. Dispatched on the grid's own `<section>` - the one `ValuesGridView` binds `onPaste`
 * to - found by filtering for the `section` that holds a `grid`, `.first()` only as a guard
 * against a second one elsewhere on the page: this project's own `Table` sits in a `<section>`
 * on every grid screen, not only this one. */
export async function paste(page: Page, text: string): Promise<void> {
  await page
    .locator("section")
    .filter({ has: page.getByRole("grid") })
    .first()
    .evaluate((node, block) => {
      const data = new DataTransfer();
      data.setData("text/plain", block);
      node.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true }));
    }, text);
}

/** One variable's linear factor in one file of a copy drifted, saved from outside; answers the
 * file as it was before. */
export function driftFactor(
  directory: string,
  file: string,
  variable: string,
  factor: number,
): Buffer {
  return driftNumber(directory, file, variable, "factor", factor);
}

/** One variable's greatest limit in one file of a copy drifted, saved from outside, which is
 * what makes its two declarations disagree about `limits`; answers the file as it was before. */
export function driftMax(directory: string, file: string, variable: string, max: number): Buffer {
  return driftNumber(directory, file, variable, "max", max);
}

/** The first number one variable's key holds in a file of a copy, replaced in place. */
function driftNumber(
  directory: string,
  file: string,
  variable: string,
  key: string,
  value: number,
): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  const text = before
    .toString("utf8")
    .replace(new RegExp(`("name": "${variable}"[\\s\\S]*?"${key}": )[0-9.]+`), `$1${value}`);
  writeFileSync(path, text, "utf8");
  return before;
}

/** A producing declaration's id taken away from outside, the way a description written before
 * `ddd id` adopted ids states it - which is what `missing-id` reports; answers the file as it
 * was before. */
export function unstamp(directory: string, file: string, variable: string): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  const text = before
    .toString("utf8")
    .replace(new RegExp(`("name": "${variable}"[\\s\\S]*?)\\n\\s*"id": "[^"]*",`), "$1");
  writeFileSync(path, text, "utf8");
  return before;
}

/** BlockA's own array `init` in the copy's user_interface.ddd.json, replaced from outside with
 * the values given - part 7's own fixture for a finding that leads to the values grid: an
 * out-of-range element the analysis reports as `init-invalid`, whose route opens BlockA's own
 * grid rather than its variable panel. */
export function writeBlockAInit(directory: string, values: readonly number[]): void {
  const path = join(directory, USER_INTERFACE);
  const text = readFileSync(path, "utf8").replace(
    /("name": "BlockA"[\s\S]*?"init": )\[[\s\S]*?\]/,
    `$1${JSON.stringify(values)}`,
  );
  writeFileSync(path, text, "utf8");
}

/** CurveA made to name a scalar type instead of stating its own storage, in the copy: the type
 * declared on Controller itself, and the `datatype`, `unit` and `conversion` taken off the
 * declaration, which the loader refuses beside a `typename`. Measured on the copy this writes:
 * the project loads with no finding at all and CurveA resolves exactly as it did - uint16, ms,
 * x0.01, the same six values, the same producing file - so the Shape column must keep offering
 * it. Nothing in examples/ has this shape, which is how it was taken away unnoticed.
 *
 * Written whole rather than patched: this changes what the declaration is made of, not one
 * value inside it, and no journey using it applies an edit whose hunks would move. */
export function typeCurveA(directory: string): void {
  const path = join(directory, CONTROLLER);
  const data = JSON.parse(readFileSync(path, "utf8"));
  data.component.types = [
    {
      type: "scalar",
      name: "Millis_t",
      description: "A duration as every component of this project agrees to see it",
      datatype: "uint16",
      unit: "ms",
      conversion: { factor: 0.01 },
      limits: { min: 0, max: 655.35 },
    },
  ];
  const curve = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "CurveA",
  ).definition;
  for (const key of ["datatype", "unit", "conversion"]) delete curve[key];
  curve.typename = "Millis_t";
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

/** BlockA given three dimensions, and an init nested to match with one value over uint8: a
 * shape no grid draws, saved from outside the page the way every other drift here is. Legal
 * DDD - the loader takes it and only `init-invalid` is reported - and the one shaped object of
 * examples/demo whose declaration is easy to widen without touching anything that reads it. */
export function widenBlockA(directory: string): void {
  const path = join(directory, USER_INTERFACE);
  const text = readFileSync(path, "utf8")
    .replace(/("name": "BlockA"[\s\S]*?"dimensions": )\[[^\]]*\]/, "$1[2, 2, 2]")
    .replace(
      /("name": "BlockA"[\s\S]*?"init": )\[[\s\S]*?\]\s*(?=,\s*\n)/,
      "$1[[[0, 12], [28, 52]], [[84, 124], [180, 9999]]]",
    );
  writeFileSync(path, text, "utf8");
}
