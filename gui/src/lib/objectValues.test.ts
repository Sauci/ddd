import { describe, expect, test } from "vitest";
import type { ValuesReply } from "../api/types";
import {
  cellAt,
  cellSentence,
  columnAxisLabel,
  columnHeader,
  cornerLabel,
  drawable,
  elementLabel,
  physicalOf,
  rawOf,
  readOnlyNote,
  rowHeader,
  typedNumber,
  typedRefusal,
} from "./objectValues";

// Every fixture below is `GET /api/values?name=…` against examples/demo, read verbatim off a
// real answer rather than invented, the same way the objects it draws are real.

/** CurveA: one row against AxisA, a linear conversion on both the object and its axis. */
const CURVE_A: ValuesReply = {
  revision: 1,
  name: "CurveA",
  kind: "curve",
  datatype: "uint16",
  unit: "ms",
  conversion: { kind: "linear", factor: 0.01, offset: 0 },
  minimum: 0,
  maximum: 655.35,
  shape: [6],
  rows: [[1200, 900, 800, 750, 700, 650]],
  stated: "array",
  axes: [
    {
      position: "axis",
      name: "AxisA",
      unit: "Hz",
      breakpoints: [0, 3200, 6400, 12800, 19200, 32000],
      conversion: { kind: "linear", factor: 0.25, offset: 0 },
    },
  ],
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

/** MapA: four rows of six, x_axis AxisA and y_axis AxisB, both linear. */
const MAP_A: ValuesReply = {
  revision: 1,
  name: "MapA",
  kind: "map",
  datatype: "sint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  minimum: -64,
  maximum: 63.5,
  shape: [4, 6],
  rows: [
    [20, 24, 28, 30, 32, 30],
    [18, 22, 26, 28, 30, 28],
    [12, 16, 20, 22, 24, 22],
    [6, 10, 14, 16, 18, 16],
  ],
  stated: "array",
  axes: [
    {
      position: "x_axis",
      name: "AxisA",
      unit: "Hz",
      breakpoints: [0, 3200, 6400, 12800, 19200, 32000],
      conversion: { kind: "linear", factor: 0.25, offset: 0 },
    },
    {
      position: "y_axis",
      name: "AxisB",
      unit: "%",
      breakpoints: [0, 60, 140, 200],
      conversion: { kind: "linear", factor: 0.5, offset: 0 },
    },
  ],
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

/** BlockA: one row of eight against no axis at all, and the identity conversion. */
const BLOCK_A: ValuesReply = {
  revision: 1,
  name: "BlockA",
  kind: "value_block",
  datatype: "uint8",
  unit: "",
  conversion: { kind: "identity" },
  minimum: 0,
  maximum: 255,
  shape: [8],
  rows: [[0, 12, 28, 52, 84, 124, 180, 255]],
  stated: "array",
  axes: [],
  owner: "UserInterface",
  file: "/repo/examples/demo/components/user_interface.ddd.json",
  findings: [],
};

/** ValueK: two dimensional, against no axis - the "else indices" arm neither CurveA (one
 * dimensional) nor MapA (an axis on both sides) reaches. */
const VALUE_K: ValuesReply = {
  revision: 1,
  name: "ValueK",
  kind: "measurement",
  datatype: "sint8",
  unit: "",
  conversion: { kind: "identity" },
  minimum: -128,
  maximum: 127,
  shape: [3, 4],
  rows: [
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
  ],
  stated: "array",
  axes: [],
  owner: "EventLogger",
  file: "/repo/examples/demo/subsystems/logging/event_logger.ddd.json",
  findings: [],
};

/** ValueA: a plain scalar measurement - shapeless, so there is no grid to draw at all. */
const VALUE_A: ValuesReply = {
  revision: 1,
  name: "ValueA",
  kind: "measurement",
  datatype: "uint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  minimum: 0,
  maximum: 100,
  shape: [],
  rows: [],
  stated: "scalar",
  axes: [],
  owner: "SensorHub",
  file: "/repo/examples/demo/components/sensor_hub.ddd.json",
  findings: [],
};

/** CurveX over AxisX, an axis stating a size and no init at all: measured on a project of
 * those two declarations alone, which answers the curve's own three numbers and an axis with
 * `breakpoints: []`. `test_an_axis_with_no_init_gives_no_breakpoints` states the intent on the
 * Python side - "the grid degrades to indices, not a crash" - and this is the half that did
 * not: a header of no columns, so a row of no value cells. */
const CURVE_X: ValuesReply = {
  revision: 1,
  name: "CurveX",
  kind: "curve",
  datatype: "uint8",
  unit: "",
  conversion: { kind: "identity" },
  minimum: 0,
  maximum: 255,
  shape: [3],
  rows: [[1, 2, 3]],
  stated: "array",
  axes: [
    {
      position: "axis",
      name: "AxisX",
      unit: "",
      breakpoints: [],
      conversion: { kind: "identity" },
    },
  ],
  owner: "A",
  file: "/repo/a.ddd.json",
  findings: [],
};

/** The same degradation down a map's side: MapA with both its axes' breakpoints taken away,
 * built from the reply above it rather than measured - the way `AReadOnlyGrid` is built from
 * BlockA's own answer - because no example pairs a map with two empty axes. */
const MAP_WITHOUT_BREAKPOINTS: ValuesReply = {
  ...MAP_A,
  axes: MAP_A.axes.map((axis) => ({ ...axis, breakpoints: [] })),
};

/** SoftwareLabel: a shaped object initialised with text - no grid either, the other way. */
const SOFTWARE_LABEL: ValuesReply = {
  revision: 1,
  name: "SoftwareLabel",
  kind: "value_block",
  datatype: "uint8",
  unit: "",
  conversion: { kind: "string" },
  minimum: 0,
  maximum: 255,
  shape: [16],
  rows: [],
  stated: "text",
  axes: [],
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

describe("physicalOf", () => {
  test("a linear conversion multiplies and offsets", () => {
    expect(physicalOf(1200, { kind: "linear", factor: 0.01, offset: 0 })).toBe(12);
  });

  test("anything else hands the raw count back", () => {
    expect(physicalOf(1200, { kind: "identity" })).toBe(1200);
  });

  test("a missing factor or offset reads as the identity's own defaults", () => {
    expect(physicalOf(12, { kind: "linear" })).toBe(12);
  });
});

describe("rawOf", () => {
  test("an integer datatype rounds to the nearest whole raw count", () => {
    expect(rawOf(12.004, { kind: "linear", factor: 0.01, offset: 0 }, "uint16")).toBe(1200);
  });

  test("a float datatype keeps the exact raw count", () => {
    expect(rawOf(12.004, { kind: "linear", factor: 0.01, offset: 0 }, "float32")).toBeCloseTo(
      1200.4,
      9,
    );
  });

  test("anything but a linear conversion takes the physical value as the raw one", () => {
    expect(rawOf(84, { kind: "identity" }, "uint8")).toBe(84);
  });
});

describe("columnHeader", () => {
  test("CurveA in physical reads AxisA's breakpoints through AxisA's own conversion", () => {
    expect(columnHeader(CURVE_A, true)).toEqual(["0", "800", "1600", "3200", "4800", "8000"]);
  });

  test("CurveA in raw is AxisA's breakpoints untouched", () => {
    expect(columnHeader(CURVE_A, false)).toEqual(["0", "3200", "6400", "12800", "19200", "32000"]);
  });

  test("MapA reads its x axis, AxisA, and not its y", () => {
    // The x/y assignment itself, in words rather than in a picture: MapA's rows are AxisB's
    // readings (below) and its columns AxisA's - swapping the two would draw a plausible grid
    // with every number in the wrong cell, and only this and the row test say which is which.
    expect(columnHeader(MAP_A, true)).toEqual(["0", "800", "1600", "3200", "4800", "8000"]);
  });

  test("BlockA, against no axis, is the column indices", () => {
    expect(columnHeader(BLOCK_A, true)).toEqual(["0", "1", "2", "3", "4", "5", "6", "7"]);
  });

  test("an axis that states no breakpoints falls back to the indices", () => {
    // Not `[]`: a header of no columns draws a row of no value cells, so the curve's three
    // numbers would be invisible and uneditable.
    expect(columnHeader(CURVE_X, true)).toEqual(["0", "1", "2"]);
  });

  test("a shapeless object draws no columns at all", () => {
    expect(columnHeader(VALUE_A, true)).toEqual([]);
  });
});

describe("rowHeader", () => {
  test("MapA in physical is AxisB's breakpoints through AxisB's own conversion", () => {
    expect(rowHeader(MAP_A, true)).toEqual(["0", "30", "70", "100"]);
  });

  test("CurveA, one row and no y axis, is labelled with the object itself", () => {
    // Spec 5.2's own sketch: `CurveA (ms)` beside its values, under `AxisA (Hz)` above them.
    expect(rowHeader(CURVE_A, true)).toEqual(["CurveA (ms)"]);
  });

  test("an object with no unit is labelled by its bare name", () => {
    expect(rowHeader(BLOCK_A, true)).toEqual(["BlockA"]);
  });

  test("ValueK, two dimensional against no axis, is the row indices", () => {
    expect(rowHeader(VALUE_K, true)).toEqual(["0", "1", "2"]);
  });

  test("a y axis that states no breakpoints falls back to the row indices", () => {
    expect(rowHeader(MAP_WITHOUT_BREAKPOINTS, true)).toEqual(["0", "1", "2", "3"]);
  });

  test("a shapeless object draws no rows at all", () => {
    expect(rowHeader(VALUE_A, true)).toEqual([]);
  });
});

describe("cornerLabel", () => {
  test("a curve names the axis its columns are laid against", () => {
    expect(cornerLabel(CURVE_A)).toBe("AxisA (Hz)");
  });

  test("a map names the axis its rows are laid against", () => {
    // Spec 5.2's map sketch: AxisB (%) down the side, AxisA (Hz) across the top - the one
    // reading that tells a reader which unit belongs to which edge.
    expect(cornerLabel(MAP_A)).toBe("AxisB (%)");
  });

  test("a grid laid against indices alone names nothing", () => {
    expect(cornerLabel(BLOCK_A)).toBe("");
  });

  test("a two dimensional grid with no y axis names nothing either", () => {
    expect(cornerLabel(VALUE_K)).toBe("");
  });
});

describe("columnAxisLabel", () => {
  test("a map names its x axis above the columns", () => {
    expect(columnAxisLabel(MAP_A)).toBe("AxisA (Hz)");
  });

  test("a single row says nothing above it - its own corner names the axis", () => {
    expect(columnAxisLabel(CURVE_A)).toBe("");
  });

  test("a two dimensional grid with no x axis says nothing", () => {
    expect(columnAxisLabel(VALUE_K)).toBe("");
  });
});

describe("typedNumber", () => {
  test("a decimal comma is not a number, rather than the whole part of one", () => {
    // `parseFloat("1,5")` is 1: half the world's decimal separator, silently planning a write
    // of a value the reader did not type.
    expect(typedNumber("1,5")).toBeNaN();
  });

  test("a numeric prefix is not a number either", () => {
    expect(typedNumber("7abc")).toBeNaN();
  });

  test("an empty cell is nothing typed, not zero", () => {
    expect(typedNumber("  ")).toBeNaN();
  });

  test("a number with space around it is that number", () => {
    expect(typedNumber(" 12 ")).toBe(12);
  });

  test("a fractional number reads whole", () => {
    expect(typedNumber("7.5")).toBe(7.5);
  });
});

describe("typedRefusal", () => {
  test("what is not wholly a number is refused in the grid's own voice", () => {
    expect(typedRefusal("1,5")).toBe("'1,5' is not a number");
  });

  test("a number is not refused", () => {
    expect(typedRefusal("7.5")).toBeNull();
  });

  test("an empty cell is not refused - nothing has been typed yet", () => {
    expect(typedRefusal("")).toBeNull();
  });
});

describe("readOnlyNote", () => {
  test("a grid with a producing file has nothing to say", () => {
    expect(readOnlyNote(CURVE_A)).toBeNull();
  });

  test("a name nothing produces has no declaration to write into", () => {
    // `owner` is null only where nothing produces it at all, which
    // `test_an_object_nothing_produces_has_no_file_or_pointer` pins on the Python side.
    expect(readOnlyNote({ ...BLOCK_A, file: null, owner: null })).toBe(
      "nothing produces 'BlockA', so it has no values to set",
    );
  });

  test("a name more than one declaration produces has no single one", () => {
    // The other cause of the same read-only grid, and `set_cell`'s own second sentence: the
    // owner is named - these are its numbers - and there is still no file to write into.
    expect(readOnlyNote({ ...BLOCK_A, file: null })).toBe(
      "'BlockA' is produced in more than one place, so there is no one file to set it in",
    );
  });
});

describe("cellAt", () => {
  test("a single row names its element by the column alone", () => {
    expect(cellAt(0, 2, [6])).toBe("[2]");
  });

  test("a map names its row and its column", () => {
    expect(cellAt(1, 3, [4, 6])).toBe("[1][3]");
  });
});

describe("elementLabel", () => {
  test("a single row names its element by the column alone, one-based", () => {
    expect(elementLabel(0, 2, [6])).toBe("element 3");
  });

  test("a map names its row and its column, one-based", () => {
    expect(elementLabel(1, 3, [4, 6])).toBe("element 2, 4");
  });
});

describe("cellSentence", () => {
  test("a curve's cell, one-based, in physical", () => {
    // The same [2] and 750 the client tests plan onto CurveA: 750 raw ms-counts is 7.5 ms.
    expect(cellSentence(CURVE_A, 0, 2, 750, true)).toBe("Sets element 3 of CurveA to 7.5 ms");
  });

  test("a map's cell names its row and its column, one-based, in physical", () => {
    // [1][3] one-based is "element 2, 4"; 99 is the raw Task 3's own endpoint test plans onto
    // that cell (tests/test_gui_api.py:2697), and 49.5 % is what it reads through MapA's ×0.5
    // conversion - so the page's sentence and the server's test name the same cell change.
    expect(cellSentence(MAP_A, 1, 3, 99, true)).toBe("Sets element 2, 4 of MapA to 49.5 %");
  });

  test("in raw, the count is written as typed, with no unit", () => {
    expect(cellSentence(CURVE_A, 0, 2, 750, false)).toBe("Sets element 3 of CurveA to 750");
  });

  test("an object with no unit carries none in its sentence either", () => {
    expect(cellSentence(BLOCK_A, 0, 4, 84, true)).toBe("Sets element 5 of BlockA to 84");
  });
});

describe("drawable", () => {
  test("a text init is not a grid, however it is shaped", () => {
    expect(drawable(SOFTWARE_LABEL)).toBe(false);
  });

  test("a shapeless object has no cell for a value to sit in", () => {
    expect(drawable(VALUE_A)).toBe(false);
  });

  test("a shaped, non-text object is drawable", () => {
    expect(drawable(CURVE_A)).toBe(true);
  });
});
