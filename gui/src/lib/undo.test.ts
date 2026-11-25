import { describe, expect, it, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import type { Finding, PlanReply, State, UndoneChange, UndoPreview } from "../api/types";
import {
  answerOf,
  askedAgainAfterUndo,
  constantLabel,
  declareLabel,
  filesLabel,
  fixLabel,
  heldUnder,
  holding,
  onItsWay,
  pasteLabel,
  previewAsked,
  previewRefused,
  rasterLabel,
  removeLabel,
  sectionLabel,
  settledAnswering,
  settleLabel,
  shownUndo,
  typeLabel,
  type UndoShown,
  undoAction,
  undoButton,
  undoConsequence,
  undoRefusal,
  undoRefused,
  undoShown,
  unitLabel,
  valueLabel,
  valuesLabel,
} from "./undo";

const MISSING_ID: Finding = {
  file: "C:/work/demo/components/sensor_hub.ddd.json",
  check: "missing-id",
  severity: "info",
  message: "SensorHub produces ValueA without an id",
  pointer: "component.interface[0].definition",
  line: null,
  column: null,
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

  it("falls back on the fix's own title, named as a fix, where it names no declaration", () => {
    // The button reads "Undo" and the label: a title alone - an "Undo Apply this unit to ..." -
    // opened a sentence of its own after the verb (16:M22).
    expect(fixLabel({ ...MISSING_ID, route: null }, "Give 'ValueA' an id")).toBe(
      "the fix \"Give 'ValueA' an id\"",
    );
    expect(fixLabel({ ...MISSING_ID, check: "unknown-unit" }, "Adopt 'rpm'")).toBe(
      "the fix \"Adopt 'rpm'\"",
    );
    expect(fixLabel({ ...MISSING_ID, route: { kind: "component", name: null } }, "Open it")).toBe(
      'the fix "Open it"',
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
    "the creation of 'sizes.ddd.json'",
  ],
  [
    { action: "create", kind: "component", name: "pump", component: "Pump" },
    answered(DESCRIBED, ["C:/work/demo/pump.ddd.json", null]),
    "the creation of 'pump.ddd.json'",
  ],
  // A created file is named as the plan creates it, never by the name typed with a suffix the
  // page would have to restate: a server creating it under another suffix is followed.
  [
    { action: "create", kind: "types", name: "sizes" },
    answered(DESCRIBED, ["C:/work/demo/sizes.ddd.jsonc", null]),
    "the creation of 'sizes.ddd.jsonc'",
  ],
  // A file created of the name the description has is told apart from it by its path (16:M15).
  [
    { action: "create", kind: "types", name: "demo" },
    answered(DESCRIBED, ["C:/work/demo/shared/demo.ddd.json", null]),
    "the creation of 'shared/demo.ddd.json'",
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

test("cells typed and applied together are named by the element one of them set, or by how many", () => {
  expect(valuesLabel("CurveA", [{ row: 0, column: 2 }], [6])).toBe("element 3 of CurveA");
  expect(valuesLabel("ParameterA", [{ row: 0, column: 0 }], [])).toBe("the value of ParameterA");
  const three = [0, 1, 2].map((column) => ({ row: 0, column }));
  expect(valuesLabel("CurveA", three, [6])).toBe("3 elements of CurveA");
  expect(valuesLabel("MapA", [{ row: 1, column: 3 }, ...three], [4, 6])).toBe("4 elements of MapA");
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
  counts: { error: 0, warning: 0, info: 0 },
  statements: { error: 0, warning: 0, info: 0 },
  failed: null,
  refused: [],
  analysing: false,
  edits: 3,
};

describe("the undo control", () => {
  it("says what it would undo", () => {
    expect(undoButton({ ...STATE, undoable: { at: 3, label: "the unit of ValueA" } })).toBe(
      "Undo the unit of ValueA",
    );
  });

  it("reads a fix applied as a fix", () => {
    const fix = fixLabel({ ...MISSING_ID, route: null }, "Apply this unit to 1 other declaration");
    expect(undoButton({ ...STATE, undoable: { at: 3, label: fix } })).toBe(
      'Undo the fix "Apply this unit to 1 other declaration"',
    );
  });

  it("is not there with nothing to undo", () => {
    expect(undoButton(null)).toBeNull();
    expect(undoButton({ ...STATE, undoable: null })).toBeNull();
  });

  it("says an undo refused because a file changed on disk in the server's sentence, and what it means", () => {
    // The server's own sentence names the file that changed. Once the edit has left the stack -
    // the server takes it off where the disk moved past it - the strip's names it as no longer
    // to be undone, the button naming another by then; while it is still there, as it stands.
    const stale = undoRefused(
      new ApiError(409, "stale", "controller.ddd.json changed on disk since it was read"),
      { at: 3, label: "the unit of ValueA" },
    );
    expect(undoRefusal(stale, true)).toBe(
      "controller.ddd.json changed on disk since it was read, so the unit of ValueA can no " +
        "longer be undone. Nothing was put back; the page shows the files as they are.",
    );
    expect(undoRefusal(stale, false)).toBe(
      "controller.ddd.json changed on disk since it was read. Nothing was put back; the page " +
        "shows the files as they are.",
    );
  });

  it("says any other refusal of an undo in the server's words", () => {
    const entry = { at: 3, label: "the unit of ValueA" };
    const unwritable = new ApiError(409, "unwritable", "controller.ddd.json is read-only");
    for (const gone of [true, false]) {
      expect(undoRefusal(undoRefused(unwritable, entry), gone)).toBe(
        "The undo was refused: controller.ddd.json is read-only",
      );
    }
    expect(
      undoRefusal(undoRefused(new ServerUnreachable(new Error("refused")), entry), false),
    ).toBe("The undo was refused: ddd gui is not answering");
  });

  it("says which files it puts back, and how many", () => {
    const sensor = { ...CHANGED, file: "C:/work/demo/components/sensor_hub.ddd.json" };
    expect(undoConsequence([CHANGED])).toBe("Puts back 1 file: controller.ddd.json");
    expect(undoConsequence([CHANGED, sensor])).toBe(
      "Puts back 2 files: controller.ddd.json, sensor_hub.ddd.json",
    );
    expect(undoAction([CHANGED])).toBe("Put back 1 file");
    expect(undoAction([CHANGED, sensor])).toBe("Put back 2 files");
  });

  it("counts a file it takes away apart from those it puts back, as the heading's line does (16:I13)", () => {
    // The adopted vocabulary's undo: the description put back, the units file taken away - the
    // strip's own word for it under Show changes, and the heading's once the undo is answered.
    const sensor = { ...CHANGED, file: "C:/work/demo/components/sensor_hub.ddd.json" };
    expect(undoConsequence([CHANGED, CREATED])).toBe(
      "Puts back 1 file: controller.ddd.json, and removes 1 file: units.ddd.json",
    );
    expect(undoConsequence([CHANGED, sensor, CREATED])).toBe(
      "Puts back 2 files: controller.ddd.json, sensor_hub.ddd.json, and removes 1 file: " +
        "units.ddd.json",
    );
    expect(undoAction([CHANGED, CREATED])).toBe("Put back 1 file and remove 1 file");
    expect(undoAction([CHANGED, sensor, CREATED])).toBe("Put back 2 files and remove 1 file");
    // An undo taking files away and putting none back says that alone.
    expect(undoConsequence([CREATED])).toBe("Removes 1 file: units.ddd.json");
    expect(undoAction([CREATED])).toBe("Remove 1 file");
  });

  it("tells two files of one name apart by their paths, among every file it puts back", () => {
    const left = { ...CHANGED, file: "C:/work/demo/left/gauge.ddd.json" };
    const right = { ...CREATED, file: "C:/work/demo/right/gauge.ddd.json" };
    expect(undoConsequence([left, right])).toBe(
      "Puts back 1 file: left/gauge.ddd.json, and removes 1 file: right/gauge.ddd.json",
    );
  });

  it("names a file it takes away by what happens to it", () => {
    expect(shownUndo([CHANGED, CREATED])).toEqual([
      { file: CHANGED.file, hunks: CHANGED.hunks, note: null },
      { file: CREATED.file, hunks: CREATED.hunks, note: "removed" },
    ]);
  });
});

describe("a refused undo, and the entries under it (16:M23)", () => {
  const STALE = new ApiError(
    409,
    "stale",
    "controller.ddd.json changed on disk since it was written",
  );
  // A file that only could not be read: the server keeps the entry, its bytes the ones it left.
  const UNREAD = new ApiError(409, "stale", "controller.ddd.json can no longer be read");
  const NOT_ON_TOP = new ApiError(409, "stale", "edit 2 is not the one to undo any more");
  const UNWRITABLE = new ApiError(
    409,
    "unwritable",
    "controller.ddd.json is read-only, so nothing was put back",
  );
  const FAILED = new ApiError(500, "internal", "ddd gui failed on this request");
  const LIMITS = { at: 2, label: "the limits of ValueA" };
  const UNIT = { at: 1, label: "the unit of ValueA" };
  const NEWER = { at: 3, label: "the description of ValueA" };
  const stateOf = (undoable: { at: number; label: string } | null): State => ({
    ...STATE,
    undoable,
  });
  const previewOf = ({ at, label }: { at: number; label: string }): UndoPreview => ({
    revision: 4,
    at,
    label,
    changes: [CHANGED],
  });
  const asked = (data: UndoPreview | undefined, error: Error | null = null) => ({ data, error });
  const said = (shown: UndoShown) => shown.refusals.map((refusal) => refusal.text);
  const LIMITS_GONE =
    "controller.ddd.json changed on disk since it was written, so the limits of ValueA can no " +
    "longer be undone. Nothing was put back; the page shows the files as they are.";
  const LIMITS_STANDS =
    "controller.ddd.json changed on disk since it was written. Nothing was put back; the page " +
    "shows the files as they are.";
  const UNIT_GONE =
    "controller.ddd.json changed on disk since it was written, so the unit of ValueA can no " +
    "longer be undone. Nothing was put back; the page shows the files as they are.";
  const READ_ONLY =
    "The undo was refused: controller.ddd.json is read-only, so nothing was put back";

  it("holds a refusal by the entry it is of, in the server's words, and whether it is stale", () => {
    expect(undoRefused(STALE, LIMITS)).toEqual({
      at: 2,
      label: "the limits of ValueA",
      message: "controller.ddd.json changed on disk since it was written",
      stale: true,
      covered: false,
    });
    expect(undoRefused(UNWRITABLE, LIMITS)).toEqual({
      at: 2,
      label: "the limits of ValueA",
      message: "controller.ddd.json is read-only, so nothing was put back",
      stale: false,
      covered: false,
    });
  });

  it("holds a preview's refusal only where it is stale, which may take the entry off the stack", () => {
    expect(previewRefused(STALE, LIMITS)).toEqual(undoRefused(STALE, LIMITS));
    expect(previewRefused(UNWRITABLE, LIMITS)).toBeNull();
    expect(previewRefused(new ServerUnreachable(new Error("refused")), LIMITS)).toBeNull();
  });

  it("holds each refusal once, in the order they came", () => {
    const limits = undoRefused(STALE, LIMITS);
    const unit = undoRefused(STALE, UNIT);
    const held = holding([], limits);
    expect(held).toEqual([limits]);
    // The same preview refused again in the same words is held already: the same list, which
    // draws nothing anew.
    expect(holding(held, undoRefused(STALE, LIMITS))).toBe(held);
    expect(holding(held, unit)).toEqual([limits, unit]);
  });

  it("says why an entry was taken off beside the one under it, which it offers to put back", () => {
    const shown = undoShown([undoRefused(STALE, LIMITS)], stateOf(UNIT), asked(previewOf(UNIT)));
    expect(said(shown)).toEqual([LIMITS_GONE]);
    expect(shown.label).toBe("Undo the unit of ValueA");
    expect(shown.preview).toEqual(previewOf(UNIT));
    expect(shown.reading).toBe(false);
  });

  it("reads the files of the entry under it while its preview is asked for", () => {
    const shown = undoShown([undoRefused(STALE, LIMITS)], stateOf(UNIT), asked(undefined));
    expect(said(shown)).toEqual([LIMITS_GONE]);
    expect(shown.preview).toBeNull();
    expect(shown.reading).toBe(true);
  });

  it("says a stale refusal of the entry still on top as it stands, and offers that entry again", () => {
    // A file that could not be read keeps the entry: the strip never says it can no longer be
    // undone, and offers it again, to be pressed once the file reads.
    const unread = undoShown(
      [undoRefused(UNREAD, LIMITS)],
      stateOf(LIMITS),
      asked(previewOf(LIMITS)),
    );
    expect(said(unread)).toEqual([
      "controller.ddd.json can no longer be read. Nothing was put back; the page shows the " +
        "files as they are.",
    ]);
    expect(unread.label).toBe("Undo the limits of ValueA");
    expect(unread.preview).toEqual(previewOf(LIMITS));
    // One the server did take off is said the same way until the state names another.
    const changed = undoShown(
      [undoRefused(STALE, LIMITS)],
      stateOf(LIMITS),
      asked(previewOf(LIMITS)),
    );
    expect(said(changed)).toEqual([LIMITS_STANDS]);
    expect(said(undoShown([undoRefused(STALE, LIMITS)], stateOf(UNIT), asked(undefined)))).toEqual([
      LIMITS_GONE,
    ]);
  });

  it("says an edit no longer on top is no longer to be undone only once it has left the stack", () => {
    const refused = undoRefused(NOT_ON_TOP, LIMITS);
    // A window behind the server, its state still naming the edit: as it stands.
    expect(said(undoShown([refused], stateOf(LIMITS), asked(undefined)))).toEqual([
      "edit 2 is not the one to undo any more. Nothing was put back; the page shows the files " +
        "as they are.",
    ]);
    // A newer edit covering it: unsaid, the newer one offered whole.
    const covered = undoShown([refused], stateOf(NEWER), asked(previewOf(NEWER)));
    expect(said(covered)).toEqual([]);
    expect(covered.preview).toEqual(previewOf(NEWER));
    // Gone from the stack: no longer to be undone.
    expect(said(undoShown([refused], stateOf(UNIT), asked(undefined)))).toEqual([
      "edit 2 is not the one to undo any more, so the limits of ValueA can no longer be undone. " +
        "Nothing was put back; the page shows the files as they are.",
    ]);
  });

  it("says why with nothing left to undo, and its button says that nothing is", () => {
    const shown = undoShown([undoRefused(STALE, LIMITS)], stateOf(null), asked(undefined));
    expect(said(shown)).toEqual([LIMITS_GONE]);
    expect(shown.label).toBe("Nothing left to undo");
    expect(shown.preview).toBeNull();
    expect(shown.reading).toBe(false);
    // With nothing said either, there is no control.
    expect(undoShown([], stateOf(null), asked(undefined)).label).toBeNull();
    expect(undoShown([], null, asked(undefined)).label).toBeNull();
  });

  it("says every entry taken off while the strip is open, in the order they went", () => {
    // The two edits wrote one file, and the save that took the first off took the second too.
    const held = [undoRefused(STALE, LIMITS), undoRefused(STALE, UNIT)];
    expect(said(undoShown(held, stateOf(null), asked(undefined)))).toEqual([
      LIMITS_GONE,
      UNIT_GONE,
    ]);
  });

  it("leaves unsaid a refusal of an entry a newer one covers, and offers the newer one whole", () => {
    // An edit made while the strip is open: the entry refused may come back to the top.
    const shown = undoShown(
      [undoRefused(UNWRITABLE, UNIT)],
      stateOf(LIMITS),
      asked(previewOf(LIMITS)),
    );
    expect(said(shown)).toEqual([]);
    expect(shown.preview).toEqual(previewOf(LIMITS));
  });

  it("says a preview's own refusal in its place, and offers nothing to put back", () => {
    // Asked again and refused, the preview before it is no longer what the undo would do.
    const full = new ApiError(409, "unwritable", "disk full");
    const shown = undoShown([], stateOf(LIMITS), asked(previewOf(LIMITS), full));
    expect(said(shown)).toEqual(["The undo was refused: disk full"]);
    expect(shown.preview).toBeNull();
    expect(shown.reading).toBe(false);
  });

  it("says a preview that failed failed, in a sentence of its own, where nothing was refused", () => {
    // The server failing on it, or not answering: no undo was asked, and none refused. Nothing is
    // offered either: asked again and failed, the preview before it is no longer what the undo
    // would do.
    const failed = undoShown([], stateOf(LIMITS), asked(previewOf(LIMITS), FAILED));
    expect(said(failed)).toEqual(["Reading the files failed: ddd gui failed on this request."]);
    expect(failed.preview).toBeNull();
    expect(failed.reading).toBe(false);
    const unanswered = new ServerUnreachable(new Error("refused"));
    expect(said(undoShown([], stateOf(LIMITS), asked(undefined, unanswered)))).toEqual([
      "Reading the files failed: ddd gui is not answering.",
    ]);
  });

  it("says a preview's refusal once, whether the strip holds it yet or not", () => {
    const refused = previewRefused(STALE, LIMITS);
    expect(refused).not.toBeNull();
    const held = refused === null ? [] : [refused];
    expect(said(undoShown([], stateOf(LIMITS), asked(undefined, STALE)))).toEqual([LIMITS_STANDS]);
    expect(said(undoShown(held, stateOf(LIMITS), asked(undefined, STALE)))).toEqual([
      LIMITS_STANDS,
    ]);
  });

  it("keys each sentence by the entry it is of", () => {
    // Two edits of one label, refused in one sentence, are two sentences of two entries.
    const again = { at: 3, label: "the limits of ValueA" };
    const shown = undoShown(
      [undoRefused(STALE, LIMITS), undoRefused(STALE, again)],
      stateOf(UNIT),
      asked(undefined, UNWRITABLE),
    );
    const keys = shown.refusals.map((refusal) => refusal.key);
    expect(new Set(keys).size).toBe(3);
  });

  it("says nothing was put back only where no refusal of the same edit before it may have", () => {
    // An undo the disk refused half way put a file back and could not write it forward again,
    // which its own sentence says; asked again, that file is not as the edit left it, and the
    // edit is taken off - a sentence that nothing was put back would say the first one wrong.
    const half = new ApiError(
      409,
      "unwritable",
      "b.ddd.json could not be put back (disk full); these could not be written forward again: " +
        "a.ddd.json",
    );
    const after = new ApiError(409, "stale", "a.ddd.json changed on disk since it was written");
    // Held as the strip holds them: the take-off beside the Put back refused before it.
    const held = holding(holding([], undoRefused(half, LIMITS)), undoRefused(after, LIMITS));
    const first =
      "The undo was refused: b.ddd.json could not be put back (disk full); these could not be " +
      "written forward again: a.ddd.json";
    expect(said(undoShown(held, stateOf(UNIT), asked(undefined)))).toEqual([
      first,
      "a.ddd.json changed on disk since it was written, so the limits of ValueA can no longer be " +
        "undone; the page shows the files as they are.",
    ]);
    // While the state still names the edit, as it stands, and the same holds.
    expect(said(undoShown(held, stateOf(LIMITS), asked(undefined)))).toEqual([
      first,
      "a.ddd.json changed on disk since it was written; the page shows the files as they are.",
    ]);
    // Beside a refusal of another edit, or one of the same edit coming after it, it is said.
    const other = [undoRefused(UNWRITABLE, NEWER), undoRefused(after, LIMITS)];
    expect(said(undoShown(other, stateOf(UNIT), asked(undefined)))[1]).toBe(
      "a.ddd.json changed on disk since it was written, so the limits of ValueA can no longer be " +
        "undone. Nothing was put back; the page shows the files as they are.",
    );
    const later = [undoRefused(after, LIMITS), undoRefused(half, LIMITS)];
    expect(said(undoShown(later, stateOf(UNIT), asked(undefined)))[0]).toBe(
      "a.ddd.json changed on disk since it was written, so the limits of ValueA can no longer be " +
        "undone. Nothing was put back; the page shows the files as they are.",
    );
    // A stale refusal before it put nothing back either - a file that could not be read - and
    // this one still says so. A list the strip no longer holds - it keeps the first stale refusal
    // of an edit alone (`holding`) - kept for what `undoShown` says of one, given it.
    const unreadable = undoRefused(UNREAD, LIMITS);
    expect(holding([unreadable], undoRefused(after, LIMITS))).toEqual([unreadable]);
    const unread = [unreadable, undoRefused(after, LIMITS)];
    expect(said(undoShown(unread, stateOf(UNIT), asked(undefined)))[1]).toBe(
      "a.ddd.json changed on disk since it was written, so the limits of ValueA can no longer be " +
        "undone. Nothing was put back; the page shows the files as they are.",
    );
  });

  it("holds no second stale refusal of an edit it holds one of, which is said once, as it went", () => {
    // CI's run of the journey at undo.spec.ts:148: the preview of edit 2 asked twice, the first
    // answer taking it off, the second refused as no longer on top - the edit's going said twice.
    const held = holding([], undoRefused(STALE, LIMITS));
    expect(holding(held, undoRefused(NOT_ON_TOP, LIMITS))).toBe(held);
    expect(
      said(
        undoShown(holding(held, undoRefused(NOT_ON_TOP, LIMITS)), stateOf(UNIT), asked(undefined)),
      ),
    ).toEqual([LIMITS_GONE]);
    // One that is not stale is held beside it, and so is a stale one of another edit.
    expect(holding(held, undoRefused(UNWRITABLE, LIMITS))).toHaveLength(2);
    expect(holding(held, undoRefused(STALE, UNIT))).toHaveLength(2);
    // So is a take-off after a Put back the disk refused, which left the edit on top: both are said.
    const refusedPutBack = [undoRefused(UNWRITABLE, LIMITS)];
    expect(holding(refusedPutBack, undoRefused(STALE, LIMITS))).toEqual([
      ...refusedPutBack,
      undoRefused(STALE, LIMITS),
    ]);
  });

  it("gives an ask of an edit's preview the answer kept for that edit alone", () => {
    // One answer on its way to edit 2: a revision landing meanwhile asks edit 2 again, and gets it.
    const answer = Promise.resolve("edit 2's answer");
    const kept = { at: 2, answer, come: false };
    expect(answerOf(kept, LIMITS)).toBe(answer);
    // Another edit's answer is none of this one's, and none kept is none.
    expect(answerOf(kept, UNIT)).toBeNull();
    expect(answerOf(null, LIMITS)).toBeNull();
  });

  it("forgets an answer once it has come, and keeps one asked since", () => {
    const first = Promise.resolve("the first");
    const second = Promise.resolve("the second");
    expect(settledAnswering({ at: 2, answer: first, come: false }, first, false)).toBeNull();
    // An answer that comes after another was asked leaves the other kept.
    const since = { at: 1, answer: second, come: false };
    expect(settledAnswering(since, first, false)).toBe(since);
    expect(settledAnswering(since, first, true)).toBe(since);
    expect(settledAnswering(null, first, false)).toBeNull();
  });

  it("keeps an answer whose stale refusal it holds as the edit's answer, decided at the ask", () => {
    // CI's race, left open one frame: the answer taking edit 2 off came after a revision was drawn
    // and before that drawing's effects asked edit 2 again. The refusal held, its answer stays the
    // edit's - an ask then gets that very refusal and sends nothing - until the reader's next
    // choice forgets it with what the strip holds.
    const refused = Promise.reject(new Error("demo.ddd.json changed on disk since it was written"));
    refused.catch(() => undefined);
    const kept = settledAnswering({ at: 2, answer: refused, come: false }, refused, true);
    expect(answerOf(kept, LIMITS)).toBe(refused);
    // Not held - an answer that came, or a refusal the strip did not hold - it is forgotten, and
    // the next revision asks the server again.
    expect(settledAnswering({ at: 2, answer: refused, come: false }, refused, false)).toBeNull();
  });

  it("keeps through the reader's choice an answer still on its way, and forgets one that has come", () => {
    // Closed while edit 2's preview is on its way, a revision landing, and opened again: the strip
    // asks edit 2 under a new key, and gets the answer still out rather than ask a second time.
    const answer = Promise.resolve("edit 2's answer");
    const out = { at: 2, answer, come: false };
    expect(onItsWay(out)).toBe(out);
    // Come, and kept for the refusal the strip holds of it, it goes with that refusal.
    const come = settledAnswering(out, answer, true);
    expect(come).toEqual({ ...out, come: true });
    expect(onItsWay(come)).toBeNull();
    expect(onItsWay(null)).toBeNull();
  });

  it("asks no preview of an edit while it holds a stale refusal of it, and offers to read again", () => {
    // Asked again, it is refused as no longer on top where the refusal took it off; a file that
    // could not be read is read again when the reader asks, once they have mended it (R22).
    const held = [undoRefused(STALE, LIMITS)];
    expect(previewAsked(held, LIMITS)).toBe(false);
    expect(previewAsked(held, UNIT)).toBe(true);
    expect(previewAsked([undoRefused(UNWRITABLE, LIMITS)], LIMITS)).toBe(true);
    expect(previewAsked([], LIMITS)).toBe(true);
    // Not asked, the strip reads nothing: it says what it holds and offers to read the files again.
    expect(undoShown(held, stateOf(LIMITS), asked(undefined))).toMatchObject({
      preview: null,
      reading: false,
      askAgain: true,
    });
    // A preview it has from before, its Put back refused, is offered again with its Put back.
    expect(undoShown(held, stateOf(LIMITS), asked(previewOf(LIMITS)))).toMatchObject({
      preview: previewOf(LIMITS),
      askAgain: false,
    });
  });

  it("lets a stale refusal go once its entry is back on top from under a newer one, offered whole", () => {
    // Another window made an edit as this strip asked, then undid it: edit 2, refused as no longer
    // on top while the newer one was there, is the one to undo again, and is asked anew.
    const covered = heldUnder([undoRefused(NOT_ON_TOP, LIMITS)], NEWER);
    expect(covered).toEqual([{ ...undoRefused(NOT_ON_TOP, LIMITS), covered: true }]);
    expect(heldUnder(covered, NEWER)).toBe(covered);
    const back = heldUnder(covered, LIMITS);
    expect(back).toEqual([]);
    expect(previewAsked(back, LIMITS)).toBe(true);
    expect(undoShown(back, stateOf(LIMITS), asked(undefined)).reading).toBe(true);
    const shown = undoShown(back, stateOf(LIMITS), asked(previewOf(LIMITS)));
    expect(said(shown)).toEqual([]);
    expect(shown.preview).toEqual(previewOf(LIMITS));
    expect(shown.askAgain).toBe(false);
  });

  it("keeps every other refusal as the stack moves: of the entry on top, not stale, or of one gone", () => {
    // Of the entry on top and never covered - the state not yet naming the newer edit the server
    // refused it for - its preview stays held back.
    const onTop = [undoRefused(NOT_ON_TOP, LIMITS)];
    expect(heldUnder(onTop, LIMITS)).toBe(onTop);
    expect(heldUnder(onTop, null)).toBe(onTop);
    // A Put back refused for a file it cannot write is offered again beside its entry (R22).
    const unwritable = [undoRefused(UNWRITABLE, UNIT)];
    expect(heldUnder(unwritable, LIMITS)).toBe(unwritable);
    // An entry taken off never comes back, numbers never reused: once the newer edit goes, the
    // strip says again why it went.
    const takenOff = heldUnder([undoRefused(STALE, LIMITS)], NEWER);
    expect(takenOff).toEqual([{ ...undoRefused(STALE, LIMITS), covered: true }]);
    expect(heldUnder(takenOff, UNIT)).toBe(takenOff);
    expect(said(undoShown(takenOff, stateOf(UNIT), asked(previewOf(UNIT))))).toEqual([LIMITS_GONE]);
  });

  it("offers to read the files again beside a refusal of the preview of the entry on top", () => {
    // R22: a file that could not be read keeps the entry on the stack; the reader may mend it and
    // ask again from the strip, which reads the files again rather than offer a Put back of files
    // it has not read.
    const unread = undoShown([], stateOf(LIMITS), asked(undefined, UNREAD));
    expect(said(unread)).toEqual([
      "controller.ddd.json can no longer be read. Nothing was put back; the page shows the " +
        "files as they are.",
    ]);
    expect(unread.preview).toBeNull();
    expect(unread.askAgain).toBe(true);
    // Held too, it is offered the same.
    expect(
      undoShown([undoRefused(UNREAD, LIMITS)], stateOf(LIMITS), asked(undefined, UNREAD)),
    ).toMatchObject({ askAgain: true, preview: null });
    // A failure, not a refusal, stays as the page's other failed reads do: asked again at the
    // next revision, or once the strip is closed.
    expect(undoShown([], stateOf(LIMITS), asked(undefined, FAILED)).askAgain).toBe(false);
    expect(
      undoShown([], stateOf(LIMITS), asked(undefined, new ServerUnreachable(new Error("x"))))
        .askAgain,
    ).toBe(false);
    // Nothing refused of the preview, nothing to ask again: a preview offered, or being read, or a
    // refusal held of the Put back beside the preview it offers again.
    expect(undoShown([], stateOf(LIMITS), asked(previewOf(LIMITS))).askAgain).toBe(false);
    expect(undoShown([], stateOf(LIMITS), asked(undefined)).askAgain).toBe(false);
    expect(
      undoShown([undoRefused(UNWRITABLE, LIMITS)], stateOf(LIMITS), asked(previewOf(LIMITS)))
        .askAgain,
    ).toBe(false);
    expect(undoShown([undoRefused(STALE, LIMITS)], stateOf(null), asked(undefined)).askAgain).toBe(
      false,
    );
  });

  it("offers the entry again beside a refusal of its Put back that leaves it on the stack", () => {
    // R22: a file that could not be written - the reader may make it writable and press again,
    // with no need to close the strip, the preview the revision on screen answers offered whole.
    const refused = undoRefused(UNWRITABLE, LIMITS);
    const shown = undoShown([refused], stateOf(LIMITS), asked(previewOf(LIMITS)));
    expect(said(shown)).toEqual([READ_ONLY]);
    expect(shown.preview).toEqual(previewOf(LIMITS));
    expect(shown.reading).toBe(false);
    // Asked again, the preview is read before it is offered.
    const reading = undoShown([refused], stateOf(LIMITS), asked(undefined));
    expect(said(reading)).toEqual([READ_ONLY]);
    expect(reading.reading).toBe(true);
  });
});

describe("what an undo asks again", () => {
  // An undo is answered once its files are back, and the revision moves only once they are
  // analysed: what draws a file as it stands, and a plan whose fingerprints the undo spent, is
  // asked for again at once; what an analysis made waits for the revision every key holds.
  it("asks again for whatever draws a file as it stands, a tab's rows, an entry's panel or a plan", () => {
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
      ["declarable", "C:/work/demo/components/controller.ddd.json", 7],
      ["unit-plan", { action: "describe", unit: "rpm", description: "speed" }, 7],
      ["type-plan", { action: "set", name: "Sensor_t", key: "unit", raw: '"rpm"' }, 7],
      ["constant-plan", { action: "remove", name: "TREND_SAMPLES" }, 7],
      ["section-plan", { action: "remove", name: ".calib" }, 7],
      ["raster-plan", { action: "remove", name: "10ms" }, 7],
      ["files-plan", { action: "add", path: "extra.ddd.json" }, 7],
      ["declaration-plan", "remove", "C:/work/demo/components/controller.ddd.json", "ValueA", 7],
      ["settle", "ValueA", "unit", '"rpm"', 7],
      ["value-plan", "CurveA", { at: [0, 1], raw: 900 }, 7],
      ["values-plan", "CurveA", [[1200, 900]], 7],
      ["fix", "C:/work/demo/components/controller.ddd.json", "", "missing-id", 7],
    ];
    expect(drawn.filter((key) => !askedAgainAfterUndo(key))).toEqual([]);
  });

  it("leaves to the analysis the graph, a comparison, the findings and an object's values", () => {
    // The final review's fix wave: a component's whole-file findings were asked again at every
    // undo, 3.4 MB at 100000-large-heavy, and none of them can change before the undo's own
    // analysis lands - when the revision their key holds moves, and they are asked for anew.
    const left = [
      ["graph", "C:/work/demo/demo.ddd.json", 7],
      ["compare", "C:/b.json", 7],
      ["findings", 7, "file", "C:/work/demo/components/controller.ddd.json"],
      ["findings", 7, 0],
      ["findings", 7, "reported", "C:/work/demo/components/controller.ddd.json", "missing-id"],
      ["values", "CurveA", 7],
    ];
    expect(left.filter((key) => askedAgainAfterUndo(key))).toEqual([]);
  });

  it("leaves the strip's own preview, and the session and the projects found", () => {
    // The undo closes the strip, and the entry it previews next is the one the next state
    // names, under a key of its own: asked again, the entry just put back is not on top.
    const left = [["undo", 3, 7], ["session"], ["projects"]];
    expect(left.filter((key) => askedAgainAfterUndo(key))).toEqual([]);
  });
});

describe("a label cut for its length (3:M5)", () => {
  // A label naming a unit of emoji, long enough to be cut, was cut through a surrogate pair: the
  // lone half before the ellipsis was refused, the edit's json no file can hold.
  const emoji = String.fromCodePoint(0x1f600);

  test("is cut on a code point, never through a pair", () => {
    const label = unitLabel({ action: "rename", unit: `a${emoji.repeat(150)}`, to: "b" });
    const points = [...label];
    expect(points).toHaveLength(120);
    expect(points.at(-1)).toBe("…");
    expect(points.slice(0, -1).every((point) => point.length === 1 || point === emoji)).toBe(true);
    // No half of a pair is left alone: every code point is a whole character.
    const halves = points.filter((point) => {
      const code = point.codePointAt(0) ?? 0;
      return code >= 0xd800 && code <= 0xdfff;
    });
    expect(halves).toEqual([]);
  });

  test("and counted in code points, as the api counts its limit", () => {
    // Sixty emoji after "the unit of " are 132 UTF-16 units and 72 code points: no cut is due,
    // where a count in units would make one (fix round 1, M3 - fifty emoji were under 120 either
    // way, and pinned nothing of the count).
    const label = settleLabel(emoji.repeat(60), "unit");
    expect(label.length).toBe(132);
    expect([...label]).toHaveLength(72);
    expect(label).toBe(`the unit of ${emoji.repeat(60)}`);
  });
});
