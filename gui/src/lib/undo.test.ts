import { describe, expect, it } from "vitest";
import type { Finding, UndoneChange } from "../api/types";
import {
  declareLabel,
  fixLabel,
  removeLabel,
  settleLabel,
  shownUndo,
  typeLabel,
  undoAction,
  undoButton,
  undoConsequence,
  unitLabel,
} from "./undo";

const MISSING_ID: Finding = {
  file: "C:/work/demo/components/sensor_hub.ddd.json",
  check: "missing-id",
  severity: "info",
  message: "SensorHub produces ValueA without an id",
  pointer: "component.interface[0].definition",
  notes: [],
  route: { kind: "variable", name: "ValueA" },
};

describe("what an edit is called", () => {
  it("names the key and the variable a settlement is of", () => {
    expect(settleLabel("ValueA", "unit")).toBe("the unit of ValueA");
    expect(settleLabel("ValueB", "limits")).toBe("the limits of ValueB");
  });

  it("names each change of the project's units", () => {
    expect(unitLabel({ action: "rename", unit: "rpm", to: "RPM" })).toBe(
      "the rename of 'rpm' to 'RPM'",
    );
    expect(unitLabel({ action: "describe", unit: "rpm", description: "turns" })).toBe(
      "the description of 'rpm'",
    );
    expect(unitLabel({ action: "add", unit: "rpm" })).toBe("'rpm' added to the vocabulary");
    expect(unitLabel({ action: "remove", unit: "rpm" })).toBe("'rpm' removed from the vocabulary");
    expect(unitLabel({ action: "adopt" })).toBe("the vocabulary adopted");
  });

  it("names a change of a type", () => {
    expect(typeLabel({ action: "set", name: "Temperature_t", key: "unit", raw: '"K"' })).toBe(
      "the unit of Temperature_t",
    );
    expect(typeLabel({ action: "rename", name: "Sensor_t", to: "Probe_t" })).toBe(
      "the rename of 'Sensor_t' to 'Probe_t'",
    );
  });

  it("names a declaration added to a component's interface", () => {
    expect(declareLabel("read", "ValueC", "Controller")).toBe("reading ValueC into Controller");
    expect(declareLabel("declare", "Pressure", "Controller")).toBe(
      "declaring Pressure in Controller",
    );
  });

  it("names a declaration taken out of a component's interface", () => {
    expect(removeLabel("ValueB", "Controller")).toBe("removing ValueB from Controller");
  });

  it("names the declaration an identity was given to", () => {
    expect(fixLabel(MISSING_ID, "Give 'ValueA' an id")).toBe("the identity of ValueA");
  });

  it("falls back on the fix's own title where it names no declaration", () => {
    expect(fixLabel({ ...MISSING_ID, route: null }, "Give 'ValueA' an id")).toBe(
      "Give 'ValueA' an id",
    );
    expect(fixLabel({ ...MISSING_ID, check: "unknown-unit" }, "Adopt 'rpm'")).toBe("Adopt 'rpm'");
    expect(fixLabel({ ...MISSING_ID, route: { kind: "component", name: null } }, "Open it")).toBe(
      "Open it",
    );
  });

  it("cuts a label the api would refuse for its length", () => {
    const label = settleLabel("V".repeat(200), "unit");
    expect(label).toHaveLength(120);
    expect(label.endsWith("…")).toBe(true);
  });
});

const CHANGED: UndoneChange = {
  file: "C:/work/demo/components/controller.ddd.json",
  gone: false,
  hunks: [{ line: 4, before: ['      "unit": "Hz"'], after: ['      "unit": "rpm"'] }],
};

const CREATED: UndoneChange = {
  file: "C:/work/demo/units.ddd.json",
  gone: true,
  hunks: [{ line: 1, before: ["{", '  "units": []', "}"], after: [] }],
};

const STATE = { revision: 4, project: "C:/work/demo/demo.ddd.json", files: [], findings: [] };

describe("the undo control", () => {
  it("says what it would undo", () => {
    expect(undoButton({ ...STATE, undoable: { at: 3, label: "the unit of ValueA" } })).toBe(
      "Undo the unit of ValueA",
    );
  });

  it("is not there with nothing to undo", () => {
    expect(undoButton(null)).toBeNull();
    expect(undoButton({ ...STATE, undoable: null })).toBeNull();
  });

  it("says which files it puts back, and how many", () => {
    expect(undoConsequence([CHANGED])).toBe("Puts back 1 file: controller.ddd.json");
    expect(undoConsequence([CHANGED, CREATED])).toBe(
      "Puts back 2 files: controller.ddd.json, units.ddd.json",
    );
    expect(undoAction([CHANGED])).toBe("Put back 1 file");
    expect(undoAction([CHANGED, CREATED])).toBe("Put back 2 files");
  });

  it("names a file it takes away by what happens to it", () => {
    expect(shownUndo([CHANGED, CREATED])).toEqual([
      { file: CHANGED.file, hunks: CHANGED.hunks, note: null },
      { file: CREATED.file, hunks: CREATED.hunks, note: "removed" },
    ]);
  });
});
