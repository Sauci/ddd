import { describe, expect, it, test } from "vitest";
import type { Finding, PlanReply, UndoneChange } from "../api/types";
import {
  askedAgainAfterUndo,
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

/** A files plan as `GET /api/files-plan` answers it, cut to what `filesLabel` reads: its changes,
 * each a file and the fingerprint it was read at - none, for a file the plan creates. */
function answered(...changes: (readonly [string, string | null])[]): PlanReply {
  return {
    revision: 1,
    changes: changes.map(([file, fingerprint]) => ({
      file,
      fingerprint,
      operations: [],
      hunks: [],
    })),
  };
}

/** The description every one of the three plans edits, read at some fingerprint. */
const DESCRIBED = ["C:/work/demo/demo.ddd.json", "5d41402abc4b2a76"] as const;

test.each([
  [
    { action: "create", kind: "types", name: "sizes" },
    answered(DESCRIBED, ["C:/work/demo/sizes.ddd.json", null]),
    "'sizes.ddd.json' created",
  ],
  [
    { action: "create", kind: "component", name: "pump", component: "Pump" },
    answered(DESCRIBED, ["C:/work/demo/pump.ddd.json", null]),
    "'pump.ddd.json' created",
  ],
  // A created file is named as the plan creates it, never by the name typed with a suffix the
  // page would have to restate: a server creating it under another suffix is followed.
  [
    { action: "create", kind: "types", name: "sizes" },
    answered(DESCRIBED, ["C:/work/demo/sizes.ddd.jsonc", null]),
    "'sizes.ddd.jsonc' created",
  ],
  // An add is named by the path exactly as typed: that text is the entry the includes gain.
  [
    { action: "add", path: "sensors/a.ddd.json" },
    answered(DESCRIBED),
    "'sensors/a.ddd.json' added to the includes",
  ],
  [
    { action: "add", path: "./a.ddd.json" },
    answered(DESCRIBED),
    "'./a.ddd.json' added to the includes",
  ],
  // A removal is named by its key relative to the project's directory: a pattern in a directory
  // as `lib/*.ddd.json`, never `*.ddd.json`, which `test_a_pattern_in_a_directory_is_named_as_
  // the_includes_spell_it` rules out of the server's own sentences.
  [
    { action: "remove", path: "C:/work/demo/sensors/a.ddd.json" },
    answered(DESCRIBED),
    "'sensors/a.ddd.json' removed from the includes",
  ],
  [
    { action: "remove", path: "C:/work/demo/lib/*.ddd.json" },
    answered(DESCRIBED),
    "'lib/*.ddd.json' removed from the includes",
  ],
  // A key outside the description's directory falls back to its base name (`relativeToProject`).
  [
    { action: "remove", path: "C:/work/shared/limits.ddd.json" },
    answered(DESCRIBED),
    "'limits.ddd.json' removed from the includes",
  ],
] as const)("%o, planned as %o, is undone as %s", (plan, reply, label) => {
  expect(filesLabel(plan, reply, "C:/work/demo/demo.ddd.json")).toBe(label);
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

const STATE = {
  revision: 4,
  version: 8,
  project: "C:/work/demo/demo.ddd.json",
  files: [],
  findings: [],
  analysing: false,
  edits: 3,
};

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

describe("what an undo asks again", () => {
  // An undo is answered once its files are back, and the revision moves only once they are
  // analysed: what is on screen and draws a file is asked for again at once.
  it("asks again for whatever draws a file, a tab's rows, an entry's panel or a plan", () => {
    const drawn = [
      ["file", "C:/work/demo/components/controller.ddd.json", 7],
      ["variable", "ValueA", 7],
      ["units", 7],
      ["unit", "rpm", 7],
      ["types", 7],
      ["type", "Sensor_t", 7],
      ["shared", 7],
      ["constant", "TREND_SAMPLES", 7],
      ["section", ".calib", 7],
      ["raster", "10ms", 7],
      ["files", 7],
      ["values", "CurveA", 7],
      ["declarable", "C:/work/demo/components/controller.ddd.json", 7],
      ["unit-plan", { action: "describe", unit: "rpm", description: "speed" }, 7],
      ["settle", "ValueA", "unit", '"rpm"', 7],
      ["fix", "C:/work/demo/components/controller.ddd.json", "", "missing-id", 7],
      ["undo", 3, 7],
    ];
    expect(drawn.filter((key) => !askedAgainAfterUndo(key))).toEqual([]);
  });

  it("leaves to the analysis the graph and a comparison, and the session and the projects found", () => {
    const left = [
      ["graph", "C:/work/demo/demo.ddd.json", 7],
      ["compare", "C:/b.json", 7],
      ["session"],
      ["projects"],
    ];
    expect(left.filter((key) => askedAgainAfterUndo(key))).toEqual([]);
  });
});
