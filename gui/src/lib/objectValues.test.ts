import { describe, expect, test } from "vitest";
import type { ValuesReply } from "../api/types";
import {
  cellAt,
  cellSentence,
  columnHeader,
  drawable,
  physicalOf,
  rawOf,
  rowHeader,
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

  test("BlockA, against no axis, is the column indices", () => {
    expect(columnHeader(BLOCK_A, true)).toEqual(["0", "1", "2", "3", "4", "5", "6", "7"]);
  });

  test("a shapeless object draws no columns at all", () => {
    expect(columnHeader(VALUE_A, true)).toEqual([]);
  });
});

describe("rowHeader", () => {
  test("MapA in physical is AxisB's breakpoints through AxisB's own conversion", () => {
    expect(rowHeader(MAP_A, true)).toEqual(["0", "30", "70", "100"]);
  });

  test("CurveA, one row and no y axis, is one empty label", () => {
    expect(rowHeader(CURVE_A, true)).toEqual([""]);
  });

  test("ValueK, two dimensional against no axis, is the row indices", () => {
    expect(rowHeader(VALUE_K, true)).toEqual(["0", "1", "2"]);
  });

  test("a shapeless object draws no rows at all", () => {
    expect(rowHeader(VALUE_A, true)).toEqual([]);
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
