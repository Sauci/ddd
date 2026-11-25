import { describe, expect, test, vi } from "vitest";
import type { ValuesReply } from "../api/types";
import { gridTexts } from "./gridTexts";
import { readNumber } from "./numbers";
import {
  boundRead,
  cellAt,
  cellName,
  cellRead,
  cellSentence,
  cellText,
  columnAxisLabel,
  columnHeader,
  commaOf,
  cornerLabel,
  drawable,
  elementLabel,
  heldReadings,
  limitsLine,
  noGridNote,
  oneCell,
  pasted,
  pastedValue,
  pasteHint,
  pasteSentence,
  pastes,
  physicalOf,
  physicalText,
  plotDrawn,
  rawOf,
  readOnlyNote,
  rounded,
  rowHeader,
  statedNote,
  statedValue,
  type TypedCell,
  typedRaw,
  typedRefusal,
  wanted,
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
  unshown: null,
  minimum_text: null,
  maximum_text: null,
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
  unshown: null,
  minimum_text: null,
  maximum_text: null,
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
  unshown: null,
  minimum_text: null,
  maximum_text: null,
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
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "EventLogger",
  file: "/repo/examples/demo/subsystems/logging/event_logger.ddd.json",
  findings: [],
};

/** ParameterA: a plain calibration parameter - shapeless, so its one value is a grid of one
 * cell: 3200 raw, which its factor of 0.25 reads as 800 Hz. */
const PARAMETER_A: ValuesReply = {
  revision: 1,
  name: "ParameterA",
  kind: "parameter",
  datatype: "uint16",
  unit: "Hz",
  conversion: { kind: "linear", factor: 0.25, offset: 0 },
  minimum: 500,
  maximum: 1500,
  shape: [],
  rows: [[3200]],
  stated: "scalar",
  axes: [],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

/** ValueC: a scalar stating no init, which the startup code zeroes: one cell of 0, unstated. */
const VALUE_C: ValuesReply = {
  ...PARAMETER_A,
  name: "ValueC",
  kind: "measurement",
  rows: [[0]],
  stated: "none",
};

/** A list written for an object of no shape (an `init-invalid` of its own): no value to show,
 * so no cell for one to sit in. */
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
  unshown: null,
  minimum_text: null,
  maximum_text: null,
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
  unshown: null,
  minimum_text: null,
  maximum_text: null,
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

/** BlockA made a uint64 block of two whose file holds 9007199254740993 and 18446744073709551615,
 * as the route answers it: each the double nearest it, 2^53 and 2^64 - which no uint64 holds -
 * and the block marked as one the grid cannot show. Built from BlockA's own answer rather than
 * measured, the way `MAP_WITHOUT_BREAKPOINTS` is: no example holds a number past 2^53. */
const BIG: ValuesReply = {
  ...BLOCK_A,
  datatype: "uint64",
  maximum: 2 ** 64,
  shape: [2],
  rows: [[2 ** 53, 2 ** 64]],
  unshown: "BlockA",
  maximum_text: "18446744073709551615",
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
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

describe("physicalOf", () => {
  test("a linear conversion multiplies and offsets", () => {
    expect(physicalOf(1200, { kind: "linear", factor: 0.01, offset: 0 })).toBe(12);
  });

  test("a position is the double arithmetic's, which needs no fewer digits", () => {
    expect(physicalOf(255, { kind: "linear", factor: 0.03, offset: 0 })).toBe(7.6499999999999995);
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

  test("an exact half to the even count, as round_physical rounds, either side of zero", () => {
    // 3:M4: `Math.round` made 2.5 3 and -2.5 -2.
    expect(rawOf(0.025, { kind: "linear", factor: 0.01, offset: 0 }, "uint16")).toBe(2);
    expect(rawOf(2.5, { kind: "identity" }, "sint8")).toBe(2);
    expect(rawOf(-2.5, { kind: "identity" }, "sint8")).toBe(-2);
    expect(rawOf(3.5, { kind: "identity" }, "uint8")).toBe(4);
  });

  test("a float datatype keeps the raw count, as the float nearest it spelled shortest", () => {
    expect(rawOf(12.004, { kind: "linear", factor: 0.01, offset: 0 }, "float32")).toBe(1200.4);
    // 15:M5: 0.3 at 0.1 a count is 3, where the double arithmetic made it 2.9999999999999996.
    expect(rawOf(0.3, { kind: "linear", factor: 0.1, offset: 0 }, "float32")).toBe(3);
  });

  test("anything but a linear conversion takes the physical value as the raw one", () => {
    expect(rawOf(84, { kind: "identity" }, "uint8")).toBe(84);
  });

  test("a count the page could send none of is placed by the double arithmetic", () => {
    expect(rawOf(1e20, { kind: "linear", factor: 0.01, offset: 0 }, "uint64")).toBe(1e22);
    expect(rawOf(1e300, { kind: "identity" }, "uint8")).toBe(1e300);
  });
});

describe("rounded", () => {
  test("a computed value to twelve digits, an exact half to the even one as round_physical", () => {
    // 3:M4: `toPrecision` read 1234567890.125 as 1234567890.13.
    expect(rounded(1234567890.125)).toBe(1234567890.12);
    expect(rounded(1.2349999999999999)).toBe(1.235);
  });
});

/** BlockF: a float32 block of four counted in tenths, holding 3, 7, 1 and 2 - 0.3, 0.7, 0.1 and
 * 0.2 in physical. */
const BLOCK_F: ValuesReply = {
  ...BLOCK_A,
  name: "BlockF",
  datatype: "float32",
  conversion: { kind: "linear", factor: 0.1, offset: 0 },
  shape: [4],
  rows: [[3, 7, 1, 2]],
};

/** A float64 block counted one to one, holding numbers of thirteen and fifteen digits. */
const LONG_FLOATS: ValuesReply = {
  ...BLOCK_A,
  name: "LongFloats",
  datatype: "float64",
  conversion: { kind: "linear", factor: 1, offset: 0 },
  shape: [3],
  rows: [[1234567890123, 1.23456789012345, 1234567890.125]],
};

/** BlockS: a float32 block whose file spells 0.1f at double precision, as float32 data a script
 * writes out does, counted at a factor of 0.5 (fix round 1, M4). */
const DOUBLE_SPELLED: ValuesReply = {
  ...BLOCK_F,
  name: "BlockS",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  shape: [2],
  rows: [[0.10000000149011612, 3]],
};

describe("a float32 reads as the float32 its file's number rounds to (fix round 1, M4)", () => {
  test("in raw and in physical alike, as briefly as that float32 reads back", () => {
    // It read 0.10000000149011612 in raw and 0.05000000074505806 in physical.
    expect(cellText(DOUBLE_SPELLED, [], 0, 0, false)).toBe("0.1");
    expect(cellText(DOUBLE_SPELLED, [], 0, 0, true)).toBe("0.05");
    expect(physicalText(0.10000000149011612, { kind: "identity" }, "float32")).toBe("0.1");
    expect(cellSentence(DOUBLE_SPELLED, 0, 0, 0.10000000149011612, false)).toBe(
      "Sets element 1 of BlockS to 0.1",
    );
  });

  test("a float64 holds every digit of its double, and reads them all", () => {
    const double = { ...DOUBLE_SPELLED, datatype: "float64" };
    expect(cellText(double, [], 0, 0, false)).toBe("0.10000000149011612");
    expect(cellText(double, [], 0, 0, true)).toBe("0.05000000074505806");
  });
});

describe("physicalText", () => {
  test("a whole datatype's count reads as the count times the factor, exactly", () => {
    expect(physicalText(255, { kind: "linear", factor: 0.03, offset: 0 }, "uint8")).toBe("7.65");
    expect(physicalText(7, { kind: "linear", factor: 1.5, offset: 0 }, "uint8")).toBe("10.5");
    expect(physicalText(100, { kind: "linear", factor: 0.5, offset: -40 }, "uint8")).toBe("10");
  });

  test("a float's reads as the shortest decimal that reads back as its count", () => {
    expect(physicalText(3, BLOCK_F.conversion, "float32")).toBe("0.3");
    // The exact product is 0.49999999999999995, the tail of the double a third is.
    expect(
      physicalText(0.3333333333333333, { kind: "linear", factor: 1.5, offset: 0 }, "float64"),
    ).toBe("0.5");
    expect(physicalText(2.9999999999999996, BLOCK_F.conversion, "float64")).toBe(
      "0.29999999999999996",
    );
  });

  test("anything but a linear conversion reads as the count", () => {
    expect(physicalText(0.1, { kind: "identity" }, "float32")).toBe("0.1");
    expect(physicalText(84, { kind: "linear", factor: 0 }, "uint8")).toBe("84");
  });

  test("a reading worked out once is the same the second time, and after many more", () => {
    const conversion = { kind: "linear", factor: 0.5, offset: 0 };
    expect(physicalText(3, conversion, "uint8")).toBe("1.5");
    expect(physicalText(3, conversion, "uint8")).toBe("1.5");
    for (let raw = 0; raw <= 50_001; raw += 1) physicalText(raw, conversion, "uint32");
    expect(heldReadings()).toBeLessThanOrEqual(50_001);
    expect(physicalText(3, conversion, "uint8")).toBe("1.5");
  });
});

describe("Physical shows the digits a value needs (15:M6)", () => {
  test("never cut at twelve significant digits", () => {
    // Raw 1234567890123 read 1234567890120 and 1.23456789012345 read 1.23456789012.
    expect(cellText(LONG_FLOATS, [], 0, 0, true)).toBe("1234567890123");
    expect(cellText(LONG_FLOATS, [], 0, 1, true)).toBe("1.23456789012345");
    // 3:M4: an exact half the page once rounded away from zero, and the server to the even digit.
    expect(cellText(LONG_FLOATS, [], 0, 2, true)).toBe("1234567890.125");
  });

  test("and in a sentence too", () => {
    expect(cellSentence(LONG_FLOATS, 0, 1, 1.23456789012345, true)).toBe(
      "Sets element 2 of LongFloats to 1.23456789012345",
    );
  });
});

describe("a physical value typed into a float object (15:M5)", () => {
  test("is planned as the shortest float that reads back as it", () => {
    expect(typedRaw("0.3", BLOCK_F, true)).toBe(3);
    expect(typedRaw("0.7", BLOCK_F, true)).toBe(7);
    expect(pasted("0.3\t0.7\t0.1\t0.25", BLOCK_F, true).rows).toEqual([[3, 7, 1, 2.5]]);
  });

  test("and what each cell reads, typed back, is the count it holds", () => {
    for (const column of [0, 1, 2, 3]) {
      const read = cellText(BLOCK_F, [], 0, column, true);
      expect(typedRaw(read, BLOCK_F, true)).toBe(BLOCK_F.rows[0]?.[column]);
    }
  });
});

describe("a whole count past 2^53, weighed as the count (task 1's n1)", () => {
  const SINT64_THOUSANDS: ValuesReply = {
    ...BIG,
    datatype: "sint64",
    conversion: { kind: "linear", factor: 1000, offset: 0 },
    unshown: null,
  };
  const SINT64_FEMTO: ValuesReply = {
    ...SINT64_THOUSANDS,
    conversion: { kind: "linear", factor: 1e-15, offset: 0 },
  };

  test("a physical value past 2^53 whose count is inside it is taken", () => {
    expect(typedRaw("1e16", SINT64_THOUSANDS, true)).toBe(1e13);
    expect(typedRefusal("1e16", SINT64_THOUSANDS, true)).toBeNull();
  });

  test("a physical value inside 2^53 whose count is past it is refused, as the count", () => {
    expect(typedRefusal("10", SINT64_FEMTO, true)).toBe(
      "'10' comes to a raw count past 2^53, where the page cannot hold every whole number exactly",
    );
    expect(typedRefusal("-10", SINT64_FEMTO, true)).toBe(
      "'-10' comes to a raw count past -2^53, where the page cannot hold every whole number exactly",
    );
  });

  test("a fraction in physical is the conversion's to round, the page holding every digit", () => {
    expect(
      typedRaw(
        "4503599627370496.5",
        { ...SINT64_THOUSANDS, conversion: { kind: "identity" } },
        true,
      ),
    ).toBe(4503599627370496);
  });
});

describe("a float the datatype cannot hold", () => {
  const FLOAT64: ValuesReply = { ...BLOCK_A, datatype: "float64" };
  const FLOAT32: ValuesReply = { ...BLOCK_A, datatype: "float32" };

  test.each([
    { text: "1e400", cell: FLOAT64, physical: false, says: "'1e400' is past what a float64 holds" },
    {
      text: "-1e400",
      cell: FLOAT32,
      physical: false,
      says: "'-1e400' is past what a float32 holds",
    },
    { text: "1e-400", cell: FLOAT64, physical: false, says: "'1e-400' rounds to zero in float64" },
    { text: "1e39", cell: FLOAT32, physical: true, says: "'1e39' is past what a float32 holds" },
    { text: "1e-50", cell: FLOAT32, physical: true, says: "'1e-50' rounds to zero in float32" },
  ])(
    "'$text' in a $cell.datatype cell, physical $physical: $says",
    ({ text, cell, physical, says }) => {
      expect(typedRefusal(text, cell, physical)).toBe(says);
      expect(typedRaw(text, cell, physical)).toBeNull();
    },
  );
});

describe("boundRead", () => {
  /** `text` read as a bound of a range of `datatype`. */
  function bound(text: string, datatype: string) {
    const read = readNumber(text);
    if (!("decimal" in read)) throw new Error(`${text} reads as no number`);
    return boundRead(read.decimal, text, datatype);
  }

  test("a float's bound is the double it is, however it is spelled", () => {
    // Task 1's n3: digits past 2^53 were refused a float, though it holds 1e19 as it is.
    expect(bound("10000000000000000000", "float64")).toEqual({ value: 1e19 });
    expect(bound("1e19", "float32")).toEqual({ value: 1e19 });
    expect(bound("0", "float32")).toEqual({ value: 0 });
    expect(bound("1e400", "float64")).toEqual({ refusal: "'1e400' is past what a float64 holds" });
    expect(bound("1e-400", "float64")).toEqual({ refusal: "'1e-400' rounds to zero in float64" });
  });

  test("any other's is refused past 2^53 in every spelling, and where the double would send another", () => {
    // Task 1's n3: an exponent past 2^53 reached the server, and a fraction from 2^51 was sent
    // rounded.
    expect(bound("1e19", "uint64")).toEqual({
      refusal: "'1e19' is past 2^53, where the page cannot hold every whole number exactly",
    });
    expect(bound("2251799813685248.25", "uint64")).toEqual({
      refusal: "'2251799813685248.25' has a fraction the page cannot hold exactly",
    });
    expect(bound("2251799813685248.3", "")).toEqual({
      refusal: "'2251799813685248.3' has a fraction the page cannot hold exactly",
    });
    expect(bound("0.1", "uint8")).toEqual({ value: 0.1 });
    expect(bound("-40", "sint16")).toEqual({ value: -40 });
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

  test("an object with no cell draws no columns at all", () => {
    expect(columnHeader(VALUE_A, true)).toEqual([]);
  });

  test("a scalar is one column, its value", () => {
    expect(columnHeader(PARAMETER_A, true)).toEqual(["Value"]);
    expect(columnHeader(PARAMETER_A, false)).toEqual(["Value"]);
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

  test("in raw the row keeps the object's name and drops its unit", () => {
    // The cells there hold 1200, 900, 800 - counts, not milliseconds - so `(ms)` beside them
    // would be a label the numbers under it contradict.
    expect(rowHeader(CURVE_A, false)).toEqual(["CurveA"]);
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

  test("an object with no cell draws no rows at all", () => {
    expect(rowHeader(VALUE_A, true)).toEqual([]);
  });

  test("a scalar is one row, labelled with the object itself as a single row is", () => {
    expect(rowHeader(PARAMETER_A, true)).toEqual(["ParameterA (Hz)"]);
    expect(rowHeader(PARAMETER_A, false)).toEqual(["ParameterA"]);
  });
});

describe("cornerLabel", () => {
  test("a curve names the axis its columns are laid against", () => {
    expect(cornerLabel(CURVE_A, true)).toBe("AxisA (Hz)");
  });

  test("in raw it keeps the axis's name and drops its unit", () => {
    // The header under it reads 0, 3200, 6400 - AxisA's own counts, which are not Hz.
    expect(cornerLabel(CURVE_A, false)).toBe("AxisA");
  });

  test("a map names the axis its rows are laid against", () => {
    // Spec 5.2's map sketch: AxisB (%) down the side, AxisA (Hz) across the top - the one
    // reading that tells a reader which unit belongs to which edge.
    expect(cornerLabel(MAP_A, true)).toBe("AxisB (%)");
  });

  test("a grid laid against indices alone names nothing", () => {
    expect(cornerLabel(BLOCK_A, true)).toBe("");
  });

  test("a two dimensional grid with no y axis names nothing either", () => {
    expect(cornerLabel(VALUE_K, true)).toBe("");
  });
});

describe("columnAxisLabel", () => {
  test("a map names its x axis above the columns", () => {
    expect(columnAxisLabel(MAP_A, true)).toBe("AxisA (Hz)");
  });

  test("in raw that name carries no unit either", () => {
    expect(columnAxisLabel(MAP_A, false)).toBe("AxisA");
  });

  test("a single row says nothing above it - its own corner names the axis", () => {
    expect(columnAxisLabel(CURVE_A, true)).toBe("");
  });

  test("a two dimensional grid with no x axis says nothing", () => {
    expect(columnAxisLabel(VALUE_K, true)).toBe("");
  });
});

describe("typedRaw", () => {
  test("a decimal comma that groups no thousands is a decimal point, not the whole part of one", () => {
    // `parseFloat("1,5")` is 1: half the world's decimal separator, silently planning a write
    // of a value the reader did not type; and `Number` refused it, where it is one and a half.
    expect(typedRaw("1,5", BLOCK_A, false)).toBe(1.5);
    expect(typedRaw("0,125", BLOCK_A, false)).toBe(0.125);
  });

  test("a comma that could be either writes nothing until it is said which", () => {
    expect(typedRaw("1,500", BLOCK_A, false)).toBeNull();
    expect(typedRaw("1,500", BLOCK_A, false, "decimal")).toBe(1.5);
    expect(typedRaw("1,500", BLOCK_A, false, "grouping")).toBe(1500);
  });

  test("a numeric prefix is not a number either", () => {
    expect(typedRaw("7abc", BLOCK_A, false)).toBeNull();
  });

  test("an empty cell is nothing typed, not zero", () => {
    expect(typedRaw("  ", BLOCK_A, false)).toBeNull();
  });

  test("a number with space around it is that number", () => {
    expect(typedRaw(" 12 ", BLOCK_A, false)).toBe(12);
  });

  test("a fraction in raw is the fraction, for the server to weigh against the datatype", () => {
    expect(typedRaw("7.5", BLOCK_A, false)).toBe(7.5);
  });

  test("in physical it is the raw count the conversion comes to, rounded for an integer", () => {
    expect(typedRaw("12.004", CURVE_A, true)).toBe(1200);
  });

  test("a number in another notation writes nothing, in either reading", () => {
    // 15:M13: `Number` read `0x10` as 16, and CurveA's cell planned 16 ms.
    expect(typedRaw("0x10", CURVE_A, false)).toBeNull();
    expect(typedRaw("0b101", CURVE_A, true)).toBeNull();
    expect(typedRaw("Infinity", CURVE_A, false)).toBeNull();
  });
});

describe("typedRefusal", () => {
  test("what is not wholly a number is refused in the grid's own voice", () => {
    expect(typedRefusal("7abc", BLOCK_A, false)).toBe("'7abc' is not a number");
  });

  test("a number in another notation is refused in the sentence every field refuses it with", () => {
    expect(typedRefusal("0x10", CURVE_A, false)).toBe("'0x10' is not a number in decimal notation");
    expect(typedRefusal("NaN", CURVE_A, true)).toBe("'NaN' is not a number in decimal notation");
    expect(typedRefusal("1_000", CURVE_A, false)).toBe(
      "'1_000' is not a number in decimal notation",
    );
  });

  test("a comma that could be either is refused until it is said which", () => {
    expect(typedRefusal("1,500", BLOCK_A, false)).toBe(
      "the comma in '1,500' could be a decimal point or a thousands separator",
    );
    expect(typedRefusal("1,500", BLOCK_A, false, "grouping")).toBeNull();
  });

  test("a number is not refused", () => {
    expect(typedRefusal("7.5", BLOCK_A, false)).toBeNull();
    expect(typedRefusal("1,5", BLOCK_A, false)).toBeNull();
  });

  test("an empty cell is not refused - nothing has been typed yet", () => {
    expect(typedRefusal("", BLOCK_A, false)).toBeNull();
  });
});

describe("cellRead", () => {
  test("says which refusal a choice of the comma's meaning answers", () => {
    expect(cellRead("1,500", BLOCK_A, false)).toEqual({
      refusal: "the comma in '1,500' could be a decimal point or a thousands separator",
      ambiguous: true,
    });
    expect(cellRead("7abc", BLOCK_A, false)).toEqual({
      refusal: "'7abc' is not a number",
      ambiguous: false,
    });
    expect(cellRead("12", BLOCK_A, false)).toEqual({ raw: 12 });
    expect(cellRead(" ", BLOCK_A, false)).toBeNull();
  });
});

/** FlagA: a boolean scalar holding false, the count 0, under the identity conversion. */
const FLAG_A: ValuesReply = {
  ...PARAMETER_A,
  name: "FlagA",
  kind: "measurement",
  datatype: "boolean",
  unit: "",
  conversion: { kind: "identity" },
  minimum: 0,
  maximum: 1,
  rows: [[0]],
};

describe("a boolean takes 0 and 1 alone", () => {
  test.each([
    // 3:M4: 0.6 typed in physical was rounded to 1, which the file stored, where in raw the same
    // 0.6 is refused - it is not a valid bool. Both readings now send it as it is typed, for the
    // server to refuse in the same words; 0 and 1 are what a boolean holds, in either.
    { text: "0.6", physical: true, raw: 0.6 },
    { text: "0.6", physical: false, raw: 0.6 },
    { text: "1", physical: true, raw: 1 },
    { text: "0", physical: false, raw: 0 },
    { text: "1.0", physical: true, raw: 1 },
  ])("'$text' in physical $physical writes $raw", ({ text, physical, raw }) => {
    expect(typedRaw(text, FLAG_A, physical)).toBe(raw);
  });

  test("and a pasted boolean is no more rounded than a typed one", () => {
    expect(pasted("0.6", { ...FLAG_A, shape: [1] }, true).rows).toEqual([[0.6]]);
  });

  test("rawOf keeps a boolean's raw count as the conversion comes to it", () => {
    expect(rawOf(0.6, { kind: "identity" }, "boolean")).toBe(0.6);
    expect(rawOf(0.5, { kind: "linear", factor: 0.5, offset: 0 }, "boolean")).toBe(1);
  });
});

describe("a number a double cannot hold", () => {
  // Past 2^53 a double, the number the page holds, no longer holds every whole number, and
  // `Number` reads the others as a double beside them, saying nothing. Planned from what it
  // read, 9007199254740993 was written as 9007199254740992; the 64 bit mask
  // 0x8000000000000001, read as 2^63, was written as 9223372036854776000, the shortest decimal
  // of that double, which is 0x80000000000000C0 - its low bit cleared and two others set; and
  // 18446744073709551615, the most a uint64 holds, read as 2^64, was refused as a number that
  // does not fit, though nobody typed it. Below 2^53 a double holds every whole number, but from
  // 2^51 it no longer holds every fraction: 4503599627370496.5 read as 4503599627370496, and
  // planned so for an integer.
  const INEXACT = "where the page cannot hold every whole number exactly";
  const FRACTION = "is not a whole number, and the page cannot hold its fraction";
  const UINT64 = BIG;
  const SINT64: ValuesReply = { ...BIG, datatype: "sint64" };
  const FLOAT64: ValuesReply = { ...BIG, datatype: "float64", unshown: null };
  const FLOAT32: ValuesReply = { ...BIG, datatype: "float32", unshown: null };

  test.each([
    // An integer cell takes a whole number up to 2^53, as it is written - 2^53 itself the
    // server refuses a 64 bit integer, which cannot tell it from 2^53 + 1 rounded.
    { text: "9007199254740991", cell: UINT64, raw: 9007199254740991, refused: null },
    { text: "9007199254740992", cell: UINT64, raw: 2 ** 53, refused: null },
    { text: "-9007199254740992", cell: SINT64, raw: -(2 ** 53), refused: null },
    // Past it, whichever side, in every decimal spelling, the space around it included.
    {
      text: "9007199254740993",
      cell: UINT64,
      raw: null,
      refused: `'9007199254740993' is past 2^53, ${INEXACT}`,
    },
    {
      text: "-9007199254740993",
      cell: SINT64,
      raw: null,
      refused: `'-9007199254740993' is past -2^53, ${INEXACT}`,
    },
    {
      text: "18446744073709551615",
      cell: UINT64,
      raw: null,
      refused: `'18446744073709551615' is past 2^53, ${INEXACT}`,
    },
    {
      text: " 9007199254740993 ",
      cell: UINT64,
      raw: null,
      refused: `' 9007199254740993 ' is past 2^53, ${INEXACT}`,
    },
    {
      text: "9007199254740993.0",
      cell: UINT64,
      raw: null,
      refused: `'9007199254740993.0' is past 2^53, ${INEXACT}`,
    },
    {
      text: "1.8446744073709551615e19",
      cell: UINT64,
      raw: null,
      refused: `'1.8446744073709551615e19' is past 2^53, ${INEXACT}`,
    },
    { text: "1e19", cell: UINT64, raw: null, refused: `'1e19' is past 2^53, ${INEXACT}` },
    {
      text: "9007199254740992.5",
      cell: UINT64,
      raw: null,
      refused: `'9007199254740992.5' is past 2^53, ${INEXACT}`,
    },
    {
      text: "-9.007199254740993e15",
      cell: SINT64,
      raw: null,
      refused: `'-9.007199254740993e15' is past -2^53, ${INEXACT}`,
    },
    // A fraction the double cannot hold is no whole number, rather than the one it reads as; a
    // fraction it holds is the fraction, which the server refuses an integer in raw.
    {
      text: "4503599627370496.5",
      cell: UINT64,
      raw: null,
      refused: `'4503599627370496.5' ${FRACTION}`,
    },
    {
      text: "2251799813685248.25",
      cell: UINT64,
      raw: null,
      refused: `'2251799813685248.25' ${FRACTION}`,
    },
    { text: "2251799813685248.5", cell: UINT64, raw: 2251799813685248.5, refused: null },
    // A float cell takes the double whatever the spelling: FLT_MAX is a whole number past 2^53
    // too, and the double is what the float holds.
    { text: "9007199254740993", cell: FLOAT64, raw: 2 ** 53, refused: null },
    { text: "10000000000000000000", cell: FLOAT64, raw: 1e19, refused: null },
    { text: "1e19", cell: FLOAT64, raw: 1e19, refused: null },
    { text: "4503599627370496.5", cell: FLOAT64, raw: 4503599627370496, refused: null },
    {
      text: "3.4028234663852886e38",
      cell: FLOAT32,
      raw: 3.4028234663852886e38,
      refused: null,
    },
    // Raw on a float32 plans the float32 the number rounds to, spelled as briefly as it reads
    // back: C's FLT_MAX, 3.4028235e38, lies past FLT_MAX's own double, which the server refuses.
    { text: "3.4028235e38", cell: FLOAT32, raw: 3.4028234663852886e38, refused: null },
    { text: "-3.4028235e38", cell: FLOAT32, raw: -3.4028234663852886e38, refused: null },
    { text: "0.1", cell: FLOAT32, raw: 0.1, refused: null },
    // Past what a float32 holds it is sent as typed, and the server refuses it.
    { text: "1e39", cell: FLOAT32, raw: 1e39, refused: null },
    // A float64 cell's entry is the double typed.
    { text: "3.4028235e38", cell: FLOAT64, raw: 3.4028235e38, refused: null },
  ])("'$text' in a $cell.datatype cell", ({ text, cell, raw, refused }) => {
    expect(typedRaw(text, cell, false)).toBe(raw);
    expect(typedRefusal(text, cell, false)).toBe(refused);
  });

  test.each([
    // Ruling B3-1: the 64 bit mask `0x8000000000000001`, which `Number` read as 2^63 and the page
    // wrote as 9223372036854776000, stays refused - now as a number in another notation, before
    // anything weighs it against 2^53; and so do the other spellings `Number` read, inside 2^53
    // as past it, and `Infinity`, which it read as a double on no side of it.
    "0x8000000000000001",
    "0x20000000000001",
    `0b1${"0".repeat(52)}1`,
    "0o400000000000000001",
    "0x1F",
    "Infinity",
  ])("'%s', in another notation, is refused before it is weighed against 2^53", (text) => {
    expect(typedRaw(text, UINT64, false)).toBeNull();
    expect(typedRefusal(text, UINT64, false)).toBe(`'${text}' is not a number in decimal notation`);
  });

  test("a pasted block holding one is refused in the same words, and plans nothing", () => {
    expect(pasted("9007199254740993\t9007199254740995", BIG, false)).toEqual({
      rows: null,
      header: false,
      refusal: `'9007199254740993' is past 2^53, ${INEXACT}`,
      ambiguous: null,
    });
  });

  test("so is a block holding one in the cell a header row and column leave", () => {
    const text = ["\t0\t1", `BlockA\t1\t18446744073709551615`].join("\n");
    expect(pasted(text, BIG, true).refusal).toBe(`'18446744073709551615' is past 2^53, ${INEXACT}`);
  });

  test("and a pasted fraction an integer cell would lose", () => {
    expect(pasted("1\t4503599627370496.5", BIG, false).refusal).toBe(
      `'4503599627370496.5' ${FRACTION}`,
    );
  });

  test("a pasted block up to 2^53 is read as it is written", () => {
    expect(pasted("9007199254740991\t-9007199254740992", SINT64, false).rows).toEqual([
      [9007199254740991, -(2 ** 53)],
    ]);
  });

  test("a float block takes a whole number past 2^53 as the double it is", () => {
    expect(pasted("9007199254740993\t10000000000000000000", FLOAT64, false).rows).toEqual([
      [2 ** 53, 1e19],
    ]);
  });

  test.each([
    // Fix round 1, M2: a number past what a double holds reaches no request, an exponent whose
    // size made the double NaN among them - planned as a count of NaN in raw, and said to be past
    // 2^53, or past what a float holds, where it rounds to zero.
    {
      text: "1e-1000000000000000000000",
      cell: UINT64,
      physical: false,
      refused: `'1e-1000000000000000000000' ${FRACTION}`,
    },
    {
      text: "1e-1000000000000000000000",
      cell: FLOAT64,
      physical: false,
      refused: "'1e-1000000000000000000000' rounds to zero in float64",
    },
    {
      text: "-1e1000000000000000000000",
      cell: FLOAT32,
      physical: false,
      refused: "'-1e1000000000000000000000' is past what a float32 holds",
    },
    {
      text: "1e-1000000000000000000000",
      cell: FLOAT64,
      physical: true,
      refused: "'1e-1000000000000000000000' rounds to zero in float64",
    },
    // And one an exponent of a few thousand makes zero, which a float cell planned as 0.
    {
      text: "1e-2000",
      cell: FLOAT64,
      physical: true,
      refused: "'1e-2000' rounds to zero in float64",
    },
    {
      text: "1e1000000000000000000000",
      cell: UINT64,
      physical: true,
      refused: `'1e1000000000000000000000' is past 2^53, ${INEXACT}`,
    },
  ])(
    "'$text' in a $cell.datatype cell, in physical $physical, is refused",
    ({ text, cell, physical, refused }) => {
      expect(typedRaw(text, cell, physical)).toBeNull();
      expect(typedRefusal(text, cell, physical)).toBe(refused);
    },
  );

  test("a whole count it rounds to is the count, which is no number past a double", () => {
    expect(typedRaw("1e-1000000000000000000000", CURVE_A, true)).toBe(0);
  });

  test("a boolean in physical too, which sent 1e400 as Infinity for the server to call inf", () => {
    expect(typedRefusal("1e400", FLAG_A, true)).toBe(`'1e400' is past 2^53, ${INEXACT}`);
    expect(typedRefusal("1e-400", FLAG_A, true)).toBe("'1e-400' rounds to zero in boolean");
    expect(typedRefusal("1e-400", FLAG_A, false)).toBe(`'1e-400' ${FRACTION}`);
  });
});

describe("the work a pasted block costs", () => {
  // A 64 by 64 map's 4,096 cells, counted rather than timed: each cell is read once, and only a
  // cell of sixteen whole digits, the one length that falls either side of 2^53, asks `BigInt` -
  // which throws for a fraction, so asking it of every cell made a block of fractions cost about
  // a hundred times what reading their numbers does.
  const MAP_64: ValuesReply = {
    ...MAP_A,
    datatype: "uint64",
    conversion: { kind: "identity" },
    shape: [64, 64],
    axes: [],
  };
  const block = (cell: (index: number) => string) =>
    Array.from({ length: 64 }, (_, row) =>
      Array.from({ length: 64 }, (_, column) => cell(row * 64 + column)).join("\t"),
    ).join("\n");

  test("a block of fractions asks BigInt nothing", () => {
    const asked = vi.spyOn(globalThis, "BigInt");
    try {
      const read = pasted(
        block((index) => (index * 0.37).toFixed(2)),
        MAP_64,
        false,
      );
      expect(read.rows?.flat()).toHaveLength(4096);
      expect(asked).not.toHaveBeenCalled();
    } finally {
      asked.mockRestore();
    }
  });

  test("a block of sixteen digit numbers asks it once a cell", () => {
    const asked = vi.spyOn(globalThis, "BigInt");
    try {
      const read = pasted(
        block(() => "9007199254740991"),
        MAP_64,
        false,
      );
      expect(read.rows?.flat()).toHaveLength(4096);
      expect(asked).toHaveBeenCalledTimes(4096);
    } finally {
      asked.mockRestore();
    }
  });
});

describe("limitsLine", () => {
  test("the limits as the doubles they cross as, where those show them", () => {
    expect(limitsLine(CURVE_A)).toBe("0 … 655.35");
  });

  test("a limit the double cannot carry in its own digits, not the double's", () => {
    // 2^64 - 1, the most a uint64 holds, crosses as 2^64 and printed as 18446744073709552000,
    // which none holds, over every 64 bit values page.
    expect(limitsLine(BIG)).toBe("0 … 18446744073709551615");
  });

  test("on either side", () => {
    const sint64: ValuesReply = {
      ...BIG,
      datatype: "sint64",
      minimum: -(2 ** 63),
      maximum: 2 ** 63,
      minimum_text: "-9223372036854775808",
      maximum_text: "9223372036854775807",
    };
    expect(limitsLine(sint64)).toBe("-9223372036854775808 … 9223372036854775807");
  });
});

describe("noGridNote", () => {
  const AT_OR_PAST =
    "holds a whole number at or past ±2^53, where the page cannot hold every whole number " +
    "exactly, so the grid cannot show it";

  test("a grid of numbers the page holds has nothing to say", () => {
    expect(noGridNote(CURVE_A)).toBeNull();
  });

  test("text is no grid at all", () => {
    expect(noGridNote(SOFTWARE_LABEL)).toBe(
      "'SoftwareLabel' is initialised with text, not with a grid",
    );
  });

  test("a block the route marks is not drawn as other numbers", () => {
    expect(noGridNote(BIG)).toBe(`'BlockA' ${AT_OR_PAST}`);
  });

  test("an axis it marks is named, whichever object's grid lies against it", () => {
    expect(noGridNote({ ...CURVE_A, unshown: "AxisA" })).toBe(`'AxisA' ${AT_OR_PAST}`);
  });

  test("text is said first: it is no grid whatever it holds", () => {
    expect(noGridNote({ ...SOFTWARE_LABEL, unshown: "SoftwareLabel" })).toBe(
      "'SoftwareLabel' is initialised with text, not with a grid",
    );
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
  test("a scalar is the whole object, named by no element at all", () => {
    expect(cellAt(0, 0, [])).toBe("");
  });

  test("a single row names its element by the column alone", () => {
    expect(cellAt(0, 2, [6])).toBe("[2]");
  });

  test("a map names its row and its column", () => {
    expect(cellAt(1, 3, [4, 6])).toBe("[1][3]");
  });
});

describe("elementLabel", () => {
  test("a scalar's cell is its value", () => {
    expect(elementLabel(0, 0, [])).toBe("the value");
  });

  test("a single row names its element by the column alone, one-based", () => {
    expect(elementLabel(0, 2, [6])).toBe("element 3");
  });

  test("a map names its row and its column, one-based", () => {
    expect(elementLabel(1, 3, [4, 6])).toBe("element 2, 4");
  });
});

describe("cellSentence", () => {
  test("a scalar's value, in physical with its own unit", () => {
    expect(cellSentence(PARAMETER_A, 0, 0, 4000, true)).toBe(
      "Sets the value of ParameterA to 1000 Hz",
    );
  });

  test("a scalar's value, in raw", () => {
    expect(cellSentence(PARAMETER_A, 0, 0, 4000, false)).toBe(
      "Sets the value of ParameterA to 4000",
    );
  });

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

/** A uint32 block holding numbers of nine, ten, two and seven digits. */
const WIDE_WHOLE: ValuesReply = {
  ...BLOCK_A,
  datatype: "uint32",
  maximum: 4294967295,
  shape: [4],
  rows: [[123456789, 4000000000, 42, 1000000]],
};

/** A float64 block whose numbers are spelled in fifteen, eleven and nine characters. */
const WIDE_FRACTIONS: ValuesReply = {
  ...BLOCK_A,
  datatype: "float64",
  shape: [3],
  rows: [[0.1234567890123, 1234567.125, -0.000001]],
};

/** MapA counted in steps of 0.125 %, its first cell 83 counts: 10.375 % in physical. */
const EIGHTHS: ValuesReply = {
  ...MAP_A,
  conversion: { kind: "linear", factor: 0.125, offset: 0 },
  rows: [[83, 24, 28, 30, 32, 30], ...MAP_A.rows.slice(1)],
};

/** A cell typed into, in physical unless said. */
function typedCell(row: number, column: number, typed: string, physical = true): TypedCell {
  return { row, column, typed, physical };
}

describe("cellText", () => {
  test("a cell shows what its count reads as in physical, and the count itself in raw", () => {
    expect(cellText(CURVE_A, [], 0, 2, true)).toBe("8");
    expect(cellText(CURVE_A, [], 0, 2, false)).toBe("800");
  });

  test("a cell typed into shows what was typed, in the reading it was typed in, and no other does", () => {
    const typed = [typedCell(0, 2, "7.25")];
    expect(cellText(CURVE_A, typed, 0, 2, true)).toBe("7.25");
    expect(cellText(CURVE_A, typed, 0, 1, true)).toBe("9");
    expect(cellText(MAP_A, [typedCell(1, 3, "7.25", false)], 1, 3, false)).toBe("7.25");
    expect(cellText(MAP_A, [typedCell(1, 3, "7.25", false)], 3, 1, false)).toBe("10");
  });

  test("in the other reading, it shows the count its text comes to, read as the grid now reads", () => {
    // 7.25 ms typed comes to 725 counts; 13 counts typed read 0.13 ms.
    expect(cellText(CURVE_A, [typedCell(0, 2, "7.25")], 0, 2, false)).toBe("725");
    expect(cellText(CURVE_A, [typedCell(0, 2, "13", false)], 0, 2, true)).toBe("0.13");
    // 5.1 % comes to the 10 counts a sint8 map can hold, which read 5 %.
    expect(cellText(MAP_A, [typedCell(0, 1, "5.1")], 0, 1, false)).toBe("10");
  });

  test("text that comes to no count is shown as typed in either reading", () => {
    expect(cellText(CURVE_A, [typedCell(0, 2, "1,500")], 0, 2, false)).toBe("1,500");
    expect(cellText(CURVE_A, [typedCell(0, 2, "")], 0, 2, false)).toBe("");
  });

  test("a comma is read as the cells typed together read it, or as the reader said", () => {
    // 1,5 ms is a decimal comma, 150 counts; beside it, 1,250 ms is 125 counts.
    expect(cellText(CURVE_A, [typedCell(0, 2, "1,5")], 0, 2, false)).toBe("150");
    const together = [typedCell(0, 1, "0,5"), typedCell(0, 2, "1,250")];
    expect(cellText(CURVE_A, together, 0, 2, false)).toBe("125");
    const said = { ...typedCell(0, 2, "1,500"), comma: "grouping" as const };
    expect(cellText(CURVE_A, [said], 0, 2, false)).toBe("150000");
  });

  test("a cell the file does not state is hollow, where it read the zero the startup code makes", () => {
    // 15:M7: a short init of [1, 2] showed zeros past its end, as though the file held them.
    expect(cellText({ ...CURVE_A, rows: [[1200, 900]] }, [], 0, 4, false)).toBe("");
    expect(cellText({ ...MAP_A, rows: MAP_A.rows.slice(0, 2) }, [], 3, 0, true)).toBe("");
    expect(cellText({ ...CURVE_A, stated: "none" }, [], 0, 1, true)).toBe("");
  });

  test("and what is typed into one shows as it was typed", () => {
    const short = { ...CURVE_A, rows: [[1200, 900]] };
    expect(cellText(short, [typedCell(0, 4, "7.5")], 0, 4, true)).toBe("7.5");
  });
});

describe("commaOf", () => {
  test("a comma one typed cell shows to be a decimal point is one in every typed cell", () => {
    const decimal = typedCell(0, 0, "0,5");
    const either = typedCell(0, 1, "1,250");
    expect(commaOf([decimal, either], either)).toBe("decimal");
  });

  test("else it is what was said of the cell's own, or nothing", () => {
    const either = typedCell(0, 1, "1,250");
    expect(commaOf([either], either)).toBeUndefined();
    const said = { ...either, comma: "grouping" as const };
    expect(commaOf([said], said)).toBe("grouping");
  });

  test("an answer given stands, whatever a cell typed later shows (fix round 1, M1)", () => {
    // `1,250`, said to group thousands, read 1.25 once `0,5` was typed beside it.
    const said = { ...typedCell(0, 1, "1,250"), comma: "grouping" as const };
    expect(commaOf([typedCell(0, 0, "0,5"), said], said)).toBe("grouping");
  });

  test("commas one typed cell shows to group thousands group them in every typed cell (M1)", () => {
    const either = typedCell(0, 1, "1,250");
    expect(commaOf([typedCell(0, 0, "1,234,567"), either], either)).toBe("grouping");
    expect(commaOf([typedCell(0, 0, "1,234,567"), typedCell(0, 2, "0,5"), either], either)).toBe(
      undefined,
    );
  });
});

/** CurveA of six over an axis stating three breakpoints, its file writing two values: the grid of
 * 15:M7, which drew three cells and left values 4 to 6 unreachable. */
const SHORT_CURVE: ValuesReply = {
  ...CURVE_A,
  rows: [[1200, 900]],
  axes: CURVE_A.axes.map((axis) => ({ ...axis, breakpoints: [0, 3200, 6400] })),
};

describe("the grid's columns and rows come from the shape (15:M7)", () => {
  test("a breakpoint labels its own column, and the columns past the axis's last are unlabelled", () => {
    expect(columnHeader(SHORT_CURVE, true)).toEqual(["0", "800", "1600", "", "", ""]);
    expect(columnHeader(SHORT_CURVE, false)).toEqual(["0", "3200", "6400", "", "", ""]);
  });

  test("an axis stating more breakpoints than the shape labels the shape's columns alone", () => {
    const narrow: ValuesReply = { ...CURVE_A, shape: [2], rows: [[7, 8]] };
    expect(columnHeader(narrow, false)).toEqual(["0", "3200"]);
  });

  test("so does a map's y axis its rows", () => {
    const tall: ValuesReply = {
      ...MAP_A,
      axes: MAP_A.axes.map((axis) =>
        axis.position === "y_axis" ? { ...axis, breakpoints: [0, 60] } : axis,
      ),
    };
    expect(rowHeader(tall, true)).toEqual(["0", "30", "", ""]);
  });

  test("a cell the file does not state is hollow, and its name says so", () => {
    expect(statedValue(SHORT_CURVE, 0, 1)).toBe(900);
    expect(statedValue(SHORT_CURVE, 0, 2)).toBeUndefined();
    expect(cellName(SHORT_CURVE, 0, 1)).toBe("element 2");
    expect(cellName(SHORT_CURVE, 0, 5)).toBe("element 6, not stated");
    expect(cellName({ ...PARAMETER_A, stated: "none" }, 0, 0)).toBe("the value, not stated");
    expect(cellName({ ...MAP_A, rows: [] }, 2, 3)).toBe("element 3, 4, not stated");
  });

  test("an object stated once states every cell, and one stating nothing none", () => {
    expect(statedValue({ ...CURVE_A, stated: "scalar" }, 0, 3)).toBe(750);
    expect(statedValue({ ...CURVE_A, stated: "none" }, 0, 3)).toBeUndefined();
  });
});

/** How many characters wide each of `columns` columns is drawn (`gridTexts`). */
function columnChars(
  reply: ValuesReply,
  typed: readonly TypedCell[],
  physical: boolean,
  columns: number,
): readonly number[] {
  return gridTexts(reply, typed, physical, columns).chars;
}

describe("the width of a column (`gridTexts`)", () => {
  test("each column of a uint32 block holds its own number whole", () => {
    expect(columnChars(WIDE_WHOLE, [], false, 4)).toEqual([9, 10, 2, 7]);
    expect(columnChars(WIDE_WHOLE, [], true, 4)).toEqual([9, 10, 2, 7]);
  });

  test("a float64 block's fractions are counted as the page spells them", () => {
    expect(columnChars(WIDE_FRACTIONS, [], true, 3)).toEqual([15, 11, 9]);
  });

  test("a map's column is as wide as the longest number of its rows, read as the grid reads it", () => {
    // 83, 18, 12 and 6 counts read 10.375, 2.25, 1.5 and 0.75 %; the next column's longest are
    // 2.75 and 1.25. In raw every count of the map is two digits at most.
    expect(columnChars(EIGHTHS, [], true, 6)).toEqual([6, 4, 4, 4, 4, 4]);
    expect(columnChars(EIGHTHS, [], false, 6)).toEqual([2, 2, 2, 2, 2, 2]);
  });

  test("what is typed into a cell widens its own column alone, while it is typed", () => {
    expect(columnChars(WIDE_WHOLE, [typedCell(0, 2, "4294967295", false)], false, 4)).toEqual([
      9, 10, 10, 7,
    ]);
    expect(columnChars(WIDE_WHOLE, [typedCell(0, 2, "", false)], false, 4)).toEqual([9, 10, 0, 7]);
  });

  test("a column past the row's last value is a hollow cell, which shows nothing", () => {
    expect(columnChars({ ...CURVE_A, rows: [[1200, 900]] }, [], false, 3)).toEqual([4, 3, 0]);
  });

  test("every row the shape has is counted, the ones the file does not write too", () => {
    const short = { ...MAP_A, rows: MAP_A.rows.slice(0, 1) };
    expect(columnChars(short, [typedCell(3, 0, "12345", false)], false, 6)).toEqual([
      5, 2, 2, 2, 2, 2,
    ]);
  });

  test("a grid of no rows has no width to give", () => {
    expect(columnChars({ ...CURVE_A, rows: [] }, [], true, 6)).toEqual([0, 0, 0, 0, 0, 0]);
  });
});

/** CurveA made a curve of three, over the first three of AxisA's breakpoints: two rows of four are
 * its shape with a row and a column more. */
const CURVE_OF_THREE: ValuesReply = {
  ...CURVE_A,
  shape: [3],
  rows: [[1200, 900, 800]],
  axes: CURVE_A.axes.map((axis) => ({ ...axis, breakpoints: axis.breakpoints.slice(0, 3) })),
};

/** Two rows of four, which a curve of three reads as a header row and column around its values. */
const TWO_ROWS_OF_FOUR = "10\t20\t30\t40\n50\t60\t70\t80";

describe("pasteSentence", () => {
  test("names the object a pasted table is about to replace every value of", () => {
    expect(pasteSentence(CURVE_A, false)).toBe("Replaces every value of CurveA");
  });

  test("carries no count of its own, one-dimensional or not - the hint above already has it", () => {
    expect(pasteSentence(MAP_A, false)).toBe("Replaces every value of MapA");
  });

  test("says that the first row and column pasted are taken for a header and not written (decision 15.1)", () => {
    expect(pasteSentence(CURVE_OF_THREE, true)).toBe(
      "Replaces every value of CurveA; the first row and column pasted are taken for a header " +
        "and not written",
    );
  });

  test("so two rows of four pasted into a curve of three say what was not written", () => {
    // Taken for a header row and column, 10, 20, 30, 40 and 50 are left out and 60, 70 and 80
    // are the curve's: the sentence over the preview is where a reader who meant something else
    // learns it, before opening Show changes.
    const block = pasted(TWO_ROWS_OF_FOUR, CURVE_OF_THREE, false);
    expect(block.rows).toEqual([[60, 70, 80]]);
    expect(pasteSentence(CURVE_OF_THREE, block.header)).toBe(
      "Replaces every value of CurveA; the first row and column pasted are taken for a header " +
        "and not written",
    );
  });
});

describe("drawable", () => {
  test("a text init is not a grid, however it is shaped", () => {
    expect(drawable(SOFTWARE_LABEL)).toBe(false);
  });

  test("an object with no cell for a value to sit in is not", () => {
    expect(drawable(VALUE_A)).toBe(false);
  });

  test("a scalar is one cell, stated or not", () => {
    expect(drawable(PARAMETER_A)).toBe(true);
    expect(drawable(VALUE_C)).toBe(true);
  });

  test("a shaped, non-text object is drawable", () => {
    expect(drawable(CURVE_A)).toBe(true);
  });
});

/** CurveA's six cells as a uint32's, which holds counts of seven digits. */
const BIG_CURVE: ValuesReply = { ...CURVE_A, datatype: "uint32" };

describe("pasted", () => {
  test("a curve's six values, in physical, become the counts the file holds", () => {
    // 12 ms through ×0.01 is 1200 counts - the same arithmetic a typed cell goes through.
    const block = pasted("12\t9\t8\t7.5\t7\t6.5", CURVE_A, true);
    expect(block.refusal).toBeNull();
    expect(block.rows).toEqual([[1200, 900, 800, 750, 700, 650]]);
    // The object's own shape: nothing is taken for a header.
    expect(block.header).toBe(false);
  });

  test("in raw, the counts are taken as they are", () => {
    const block = pasted("1300\t950\t850\t800\t750\t700", CURVE_A, false);
    expect(block.rows).toEqual([[1300, 950, 850, 800, 750, 700]]);
  });

  test("a map takes four rows of six", () => {
    const text = [
      "1\t2\t3\t4\t5\t6",
      "7\t8\t9\t10\t11\t12",
      "13\t14\t15\t16\t17\t18",
      "19\t20\t21\t22\t23\t24",
    ].join("\n");
    expect(pasted(text, MAP_A, false).rows).toEqual([
      [1, 2, 3, 4, 5, 6],
      [7, 8, 9, 10, 11, 12],
      [13, 14, 15, 16, 17, 18],
      [19, 20, 21, 22, 23, 24],
    ]);
  });

  test("a header row and column are dropped without being read", () => {
    // What selecting the drawn grid gives: a blank corner, AxisA's readings, the CurveA label -
    // and readings that belong to no axis at all, which are discarded just the same.
    const text = ["\t0\t800\t1600\t3200\t4800\t8000", "CurveA (ms)\t12\t9\t8\t7.5\t7\t6.5"].join(
      "\n",
    );
    expect(pasted(text, CURVE_A, true).rows).toEqual([[1200, 900, 800, 750, 700, 650]]);
  });

  test("two rows of four pasted into a curve of three are taken for a header around its values, and say so", () => {
    // Nothing but the block's size tells a header from values, so its first row and column are
    // left out whatever they hold, and the answer says so (decision 15.1).
    expect(pasted(TWO_ROWS_OF_FOUR, CURVE_OF_THREE, false)).toEqual({
      rows: [[60, 70, 80]],
      header: true,
      refusal: null,
      ambiguous: null,
    });
  });

  test("a map's header row and column are dropped too", () => {
    const text = [
      "\t0\t800\t1600\t3200\t4800\t8000",
      "0\t1\t2\t3\t4\t5\t6",
      "30\t7\t8\t9\t10\t11\t12",
      "70\t13\t14\t15\t16\t17\t18",
      "100\t19\t20\t21\t22\t23\t24",
    ].join("\n");
    expect(pasted(text, MAP_A, false).rows?.[3]).toEqual([19, 20, 21, 22, 23, 24]);
  });

  test("breakpoints above values, with no labels, matches neither shape", () => {
    const text = ["0\t3200\t6400\t12800\t19200\t32000", "1200\t900\t800\t750\t700\t650"].join("\n");
    expect(pasted(text, CURVE_A, false)).toEqual({
      rows: null,
      header: false,
      refusal: "expected 1 row of 6, or 2 rows of 7 with a header; got 2 rows of 6",
      ambiguous: null,
    });
  });

  test("a column is refused: the grid draws a curve as a row", () => {
    expect(pasted("1200\n900\n800\n750\n700\n650", CURVE_A, false).refusal).toBe(
      "expected 1 row of 6, or 2 rows of 7 with a header; got 6 rows of 1",
    );
  });

  test("rows of different lengths are not a table", () => {
    expect(pasted("1\t2\t3\t4\t5\t6\n7\t8\t9", MAP_A, false)).toEqual({
      rows: null,
      header: false,
      refusal: "this is not a table: its rows are 6 and 3 values long",
      ambiguous: null,
    });
  });

  test("three different lengths are listed, not joined by two ands", () => {
    // `join(" and ")` reads for two and turns three into "6 and 3 and 9", which is one
    // sentence pretending to be three.
    const text = "1\t2\t3\t4\t5\t6\n7\t8\t9\n1\t2\t3\t4\t5\t6\t7\t8\t9";
    expect(pasted(text, MAP_A, false).refusal).toBe(
      "this is not a table: its rows are 6, 3 and 9 values long",
    );
  });

  test("a comma is the decimal separator where no cell has a point", () => {
    expect(pasted("12\t9\t8\t7,5\t7\t6,5", CURVE_A, true).rows).toEqual([
      [1200, 900, 800, 750, 700, 650],
    ]);
  });

  test("a block mixing a comma and a point does not know which it means", () => {
    expect(pasted("12\t9\t8\t7.5\t7\t6,5", CURVE_A, true)).toEqual({
      rows: null,
      header: false,
      refusal: "this mixes '.' and ',' as decimal separators, so it is not clear what it means",
      ambiguous: null,
    });
  });

  test("a block whose commas group thousands reads one that could be either so (M1)", () => {
    // `1,500` beside `1,234,567` is fifteen hundred, and nothing is asked: the choice of what it
    // means is offered only where nothing in the block says it.
    expect(pasted("1,234,567\t1,500\t8\t7\t6\t5", BIG_CURVE, false)).toEqual({
      rows: [[1234567, 1500, 8, 7, 6, 5]],
      header: false,
      refusal: null,
      ambiguous: null,
    });
    // Said to be a decimal point, it is not: the block says what it is.
    expect(pasted("1,234,567\t1,500\t8\t7\t6\t5", BIG_CURVE, false, "decimal").rows).toEqual([
      [1234567, 1500, 8, 7, 6, 5],
    ]);
  });

  test("a block writing its comma both ways is refused, naming no point it does not hold (M1)", () => {
    expect(pasted("1,234,567\t0,5\t8\t7\t6\t5", BIG_CURVE, false).refusal).toBe(
      "this writes ',' both as a decimal separator and as a thousands separator, so it is not " +
        "clear what it means",
    );
  });

  test("text holding both a point and a comma is read by the same rule, its decimal point last", () => {
    // `1.234,56` groups thousands with points and parts its fraction with the comma: 1234.56.
    expect(pasted("1.234,56\t9\t8\t7,5\t7\t6,5", CURVE_A, false).rows).toEqual([
      [1234.56, 9, 8, 7.5, 7, 6.5],
    ]);
    expect(pasted("1,234.56\t9\t8\t7.5\t7\t6.5", CURVE_A, false).rows).toEqual([
      [1234.56, 9, 8, 7.5, 7, 6.5],
    ]);
  });

  test("and so is refused where the block's other values write the decimal point the other way", () => {
    expect(pasted("1.234,56\t9\t8\t7.5\t7\t6.5", CURVE_A, true).refusal).toBe(
      "this mixes '.' and ',' as decimal separators, so it is not clear what it means",
    );
  });

  test("a comma before three digits could be either, so the block is refused until it is said", () => {
    // What an English spreadsheet puts on the clipboard for twelve hundred, and what a French
    // one puts there for one and a fifth. Read as a decimal point - the rule as it once stood - a
    // uint32 curve of 1,000 / 2,000 / 3,000 was written 1 / 2 / 3 and nothing said so.
    expect(pasted("1,200\t2\t3\t4\t5\t6", CURVE_A, false)).toEqual({
      rows: null,
      header: false,
      refusal: "the comma in '1,200' could be a decimal point or a thousands separator",
      ambiguous: "1,200",
    });
  });

  test("said with one press, the block is read as it says, the same choice as a typed cell's", () => {
    expect(pasted("1,200\t2\t3\t4\t5\t6", CURVE_A, false, "decimal").rows).toEqual([
      [1.2, 2, 3, 4, 5, 6],
    ]);
    expect(pasted("1,200\t2\t3\t4\t5\t6", CURVE_A, false, "grouping").rows).toEqual([
      [1200, 2, 3, 4, 5, 6],
    ]);
  });

  test("a comma locale's block holding a value of three decimals is read, its leading 0 no grouping", () => {
    // 15:M9: `0,125 0,250 0,500` was refused, though no grouping starts at 0, and so was
    // `0,5 1,250 2`, whose `0,5` says what every comma of the block is.
    expect(pasted("0,125\t0,250\t0,500\t1\t2\t3", CURVE_A, false).rows).toEqual([
      [0.125, 0.25, 0.5, 1, 2, 3],
    ]);
    expect(pasted("0,5\t1,250\t2\t3\t4\t5", CURVE_A, false).rows).toEqual([
      [0.5, 1.25, 2, 3, 4, 5],
    ]);
  });

  test("what the block itself shows comes before what was said for it", () => {
    expect(pasted("0,5\t1,250\t2\t3\t4\t5", CURVE_A, false, "grouping").rows).toEqual([
      [0.5, 1.25, 2, 3, 4, 5],
    ]);
  });

  test("a number in another notation pasted is refused in the one sentence, and asks nothing", () => {
    expect(pasted("0x10\t2\t3\t4\t5\t6", CURVE_A, false)).toEqual({
      rows: null,
      header: false,
      refusal: "'0x10' is not a number in decimal notation",
      ambiguous: null,
    });
  });

  test("a comma before one, two or four digits is a decimal point still", () => {
    // The blocks §4.2 was written for are untouched: only three digits at the end of the cell
    // are a grouping anyone writes, so 1,5 and 1,25 stay halves and 1,2345 stays a decimal.
    expect(pasted("1,5\t1,25\t1,2345\t7\t7\t7", CURVE_A, false).rows).toEqual([
      [1.5, 1.25, 1.2345, 7, 7, 7],
    ]);
  });

  test("a header's own cells are read for neither the comma rule nor the grouping", () => {
    // AxisA's readings are the header, and one of them carries a point - which, weighed with
    // the values, would turn the comma rule off and refuse a perfectly good French block; and
    // another is grouped, which would refuse it a second way. Spec 3 says the header is
    // discarded without being read, and this is where that has to mean something.
    const text = ["\t0\t3.2\t1,600\t3200\t4800\t8000", "CurveA (ms)\t12\t9\t8\t7,5\t7\t6,5"].join(
      "\n",
    );
    expect(pasted(text, CURVE_A, true).rows).toEqual([[1200, 900, 800, 750, 700, 650]]);
  });

  test("whitespace inside a cell is not stripped", () => {
    expect(pasted("1 234\t9\t8\t7.5\t7\t6.5", CURVE_A, true).refusal).toBe(
      "'1 234' is not a number",
    );
  });

  test("an empty cell is nothing, not zero", () => {
    expect(pasted("12\t\t8\t7.5\t7\t6.5", CURVE_A, true).refusal).toBe("'' is not a number");
  });

  test("a value block over indices takes one row of eight", () => {
    expect(pasted("0\t12\t28\t52\t84\t124\t180\t255", BLOCK_A, false).rows).toEqual([
      [0, 12, 28, 52, 84, 124, 180, 255],
    ]);
  });
});

describe("pastedValue", () => {
  test("one cell pasted is the one value it holds, a trailing line break aside (decision 15.2)", () => {
    // What a spreadsheet puts on the clipboard for one cell copied: its text and a line break,
    // which Windows writes as two characters.
    expect(pastedValue("14")).toBe("14");
    expect(pastedValue("14\n")).toBe("14");
    expect(pastedValue("14\r\n")).toBe("14");
  });

  test("its text is kept as pasted, for the cell to read as it reads one typed", () => {
    expect(pastedValue(" 7,5 ")).toBe(" 7,5 ");
    expect(pastedValue("abc")).toBe("abc");
  });

  test("an empty one is a cell nothing is typed into", () => {
    expect(pastedValue("")).toBe("");
    expect(pastedValue("\n")).toBe("");
  });

  test("anything more is a block, which replaces every value", () => {
    expect(pastedValue("14\t15")).toBeNull();
    expect(pastedValue("14\n15")).toBeNull();
    expect(pastedValue("14\t")).toBeNull();
    // A second line break is a second row, empty.
    expect(pastedValue("14\n\n")).toBeNull();
  });
});

describe("pasteHint", () => {
  test("a curve asks for one row, or one value into a cell", () => {
    expect(pasteHint(CURVE_A)).toBe(
      "Paste 1 row of 6 values from a spreadsheet to replace them all, or one value into a " +
        "cell to set it.",
    );
  });

  test("a map asks for four", () => {
    expect(pasteHint(MAP_A)).toBe(
      "Paste 4 rows of 6 values from a spreadsheet to replace them all, or one value into a " +
        "cell to set it.",
    );
  });
});

describe("wanted", () => {
  test("a scalar takes one row of one", () => {
    expect(wanted(PARAMETER_A)).toEqual([1, 1]);
  });

  test("a curve takes one row of its width and a map its own", () => {
    expect(wanted(CURVE_A)).toEqual([1, 6]);
    expect(wanted(MAP_A)).toEqual([4, 6]);
  });
});

describe("pastes", () => {
  test("a table is pasted into a grid of a shape", () => {
    expect(pastes(CURVE_A)).toBe(true);
    expect(pastes(MAP_A)).toBe(true);
  });

  test("one value is no table, which the server refuses it", () => {
    expect(pastes(PARAMETER_A)).toBe(false);
  });
});

describe("plotDrawn", () => {
  test("a grid is drawn as a picture too", () => {
    expect(plotDrawn(CURVE_A)).toBe(true);
  });

  test("one point plots nothing", () => {
    expect(plotDrawn(PARAMETER_A)).toBe(false);
  });

  test("a grid stating nothing draws no picture, its file stating no point to place", () => {
    // The picture follows the cells: every one is hollow, and a line of the startup code's zeros
    // under them would say what the grid does not.
    expect(plotDrawn({ ...CURVE_A, stated: "none" })).toBe(false);
    expect(plotDrawn({ ...MAP_A, stated: "none" })).toBe(false);
  });

  test("a grid the file states is drawn, one stated short or once for every cell alike", () => {
    expect(plotDrawn(SHORT_CURVE)).toBe(true);
    expect(plotDrawn({ ...CURVE_A, stated: "scalar" })).toBe(true);
  });
});

describe("statedNote", () => {
  test("an object stating one value for every element says so", () => {
    expect(statedNote({ ...CURVE_A, stated: "scalar" })).toBe("Stated once, for every cell.");
  });

  test("an object stating nothing says so, a scalar too", () => {
    expect(statedNote({ ...CURVE_A, stated: "none" })).toBe("Nothing is stated.");
    expect(statedNote(VALUE_C)).toBe("Nothing is stated.");
  });

  test("a table written out says nothing", () => {
    expect(statedNote(CURVE_A)).toBeNull();
  });

  test("a scalar written is one value for one cell, which needs no sentence", () => {
    expect(statedNote(PARAMETER_A)).toBeNull();
  });
});

describe("oneCell", () => {
  test("a scalar is a grid of one cell, which keeps its natural width", () => {
    expect(oneCell(PARAMETER_A)).toBe(true);
  });

  test("a curve and a map are laid across the page", () => {
    expect(oneCell(CURVE_A)).toBe(false);
    expect(oneCell(MAP_A)).toBe(false);
  });
});
