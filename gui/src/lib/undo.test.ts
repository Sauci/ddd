import { describe, expect, it, test } from "vitest";
import type { Finding, UndoneChange } from "../api/types";
import {
  constantLabel,
  declareLabel,
  filesLabel,
  fixLabel,
  pasteLabel,
  rasterLabel,
  removeLabel,
  sectionLabel,
  settleLabel,
  shownUndo,
  typeLabel,
  undoAction,
  undoButton,
  undoConsequence,
  unitLabel,
  valueLabel,
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

  it("names the element of an object's values that was set", () => {
    expect(valueLabel("CurveA", 0, 2, [6])).toBe("element 3 of CurveA");
    expect(valueLabel("MapA", 1, 3, [4, 6])).toBe("element 2, 4 of MapA");
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

test.each([
  [{ action: "set", name: "TREND_SAMPLES", key: "value", raw: "16" }, "the value of TREND_SAMPLES"],
  [
    { action: "set", name: "TREND_SAMPLES", key: "description" },
    "the description of TREND_SAMPLES",
  ],
  [
    { action: "rename", name: "TREND_SAMPLES", to: "TREND_SLOTS" },
    "the rename of 'TREND_SAMPLES' to 'TREND_SLOTS'",
  ],
  [{ action: "add", name: "CELLS", raw: "8" }, "'CELLS' declared as a constant"],
  [{ action: "remove", name: "CELLS" }, "'CELLS' removed from the constants"],
] as const)("%o is undone as %s", (plan, label) => {
  expect(constantLabel(plan)).toBe(label);
});

test.each([
  [{ action: "set", name: ".calib", key: "access", raw: '"read-only"' }, "the access of .calib"],
  [{ action: "set", name: ".calib", key: "alignment" }, "the alignment of .calib"],
  [{ action: "rename", name: ".calib", to: ".trend" }, "the rename of '.calib' to '.trend'"],
  [
    { action: "add", name: ".calib", access: '"read-only"', alignment: "4" },
    "'.calib' declared as a section",
  ],
  [{ action: "remove", name: ".calib" }, "'.calib' removed from the sections"],
] as const)("%o is undone as %s", (plan, label) => {
  expect(sectionLabel(plan)).toBe(label);
});

test.each([
  [{ action: "set", name: "10ms", key: "cycle", raw: '"20ms"' }, "the cycle of 10ms"],
  [{ action: "set", name: "10ms", key: "event" }, "the event of 10ms"],
  [{ action: "rename", name: "10ms", to: "20ms" }, "the rename of '10ms' to '20ms'"],
  [{ action: "add", name: "10ms", event: "1" }, "'10ms' declared as a raster"],
  [{ action: "remove", name: "10ms" }, "'10ms' removed from the rasters"],
] as const)("%o is undone as %s", (plan, label) => {
  expect(rasterLabel(plan)).toBe(label);
});

test.each([
  [{ action: "create", kind: "types", name: "sizes" }, "'sizes.ddd.json' created"],
  [
    { action: "create", kind: "component", name: "pump", component: "Pump" },
    "'pump.ddd.json' created",
  ],
  // An add is named by the path exactly as typed: that text is the entry the includes gain.
  [{ action: "add", path: "sensors/a.ddd.json" }, "'sensors/a.ddd.json' added to the includes"],
  [{ action: "add", path: "./a.ddd.json" }, "'./a.ddd.json' added to the includes"],
  // A removal is named by its key relative to the project's directory: a pattern in a directory
  // as `lib/*.ddd.json`, never `*.ddd.json`, which `test_a_pattern_in_a_directory_is_named_as_
  // the_includes_spell_it` rules out of the server's own sentences.
  [
    { action: "remove", path: "C:/work/demo/sensors/a.ddd.json" },
    "'sensors/a.ddd.json' removed from the includes",
  ],
  [
    { action: "remove", path: "C:/work/demo/lib/*.ddd.json" },
    "'lib/*.ddd.json' removed from the includes",
  ],
  // A key outside the description's directory falls back to its base name (`relativeToProject`).
  [
    { action: "remove", path: "C:/work/shared/limits.ddd.json" },
    "'limits.ddd.json' removed from the includes",
  ],
] as const)("%o is undone as %s", (plan, label) => {
  expect(filesLabel(plan, "C:/work/demo/demo.ddd.json")).toBe(label);
});

test("an undone paste is named by the object whose table it replaced", () => {
  expect(pasteLabel("CurveA")).toBe("the values of CurveA");
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
