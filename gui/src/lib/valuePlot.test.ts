import { describe, expect, test } from "vitest";
import type { GridAxis, ValuesReply } from "../api/types";
import { BOX, plotted } from "./valuePlot";

const AXIS_A = {
  position: "axis",
  name: "AxisA",
  unit: "Hz",
  breakpoints: [0, 3200, 6400, 12800, 19200, 32000],
  conversion: { kind: "linear", factor: 0.25, offset: 0 },
};

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
  axes: [AXIS_A],
  owner: "Controller",
  file: "controller.ddd.json",
  findings: [],
};

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
  file: "user_interface.ddd.json",
  findings: [],
};

const CURVE_B: ValuesReply = {
  ...CURVE_A,
  name: "CurveB",
  datatype: "uint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  minimum: 0,
  maximum: 127.5,
  rows: [[200, 200, 200, 200, 200, 200]],
  stated: "scalar",
};

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
    { ...AXIS_A, position: "x_axis" },
    {
      position: "y_axis",
      name: "AxisB",
      unit: "%",
      breakpoints: [0, 60, 140, 200],
      conversion: { kind: "linear", factor: 0.5, offset: 0 },
    },
  ],
  owner: "Controller",
  file: "controller.ddd.json",
  findings: [],
};

const inside = BOX.width - BOX.left - BOX.right;

describe("plotted", () => {
  test("a curve is one line of six points", () => {
    const plot = plotted(CURVE_A, true);
    expect(plot.lines).toHaveLength(1);
    expect(plot.lines[0]?.points).toHaveLength(6);
    expect(plot.lines[0]?.label).toBe("");
  });

  test("the x positions follow the breakpoints, not their order", () => {
    // AxisA reads 0, 800, 1600, 3200, 4800, 8000 - gaps of 800, 800, 1600, 1600, 3200. Evenly
    // spaced they would sit a fifth apart; proportional, the third is a fifth of the way along
    // and the fourth two fifths.
    const xs = plotted(CURVE_A, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs[0]).toBeCloseTo(BOX.left);
    expect(xs[2]).toBeCloseTo(BOX.left + inside * 0.2);
    expect(xs[3]).toBeCloseTo(BOX.left + inside * 0.4);
    expect(xs[5]).toBeCloseTo(BOX.left + BOX.width - BOX.left - BOX.right);
  });

  test("without an axis the x positions are the indices, evenly spaced", () => {
    const xs = plotted(BLOCK_A, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs[0]).toBeCloseTo(BOX.left);
    expect(xs[4]).toBeCloseTo(BOX.left + inside * (4 / 7));
  });

  test("the range is the values padded by a twentieth", () => {
    // CurveA reads 6.5 to 12, a span of 5.5, so a twentieth is 0.275.
    const plot = plotted(CURVE_A, true);
    expect(plot.low).toBeCloseTo(6.225);
    expect(plot.high).toBeCloseTo(12.275);
  });

  test("a value at the top of the range is drawn at the top of the padding", () => {
    const plot = plotted(CURVE_A, true);
    expect(plot.lines[0]?.points[0]?.y).toBeGreaterThan(BOX.top);
    expect(plot.lines[0]?.points[0]?.y).toBeLessThan(BOX.top + 20);
  });

  test("limits outside the values are not drawn", () => {
    // 0 and 655.35 against values of 6.5 to 12: the ordinary case, and neither is in frame.
    expect(plotted(CURVE_A, true).rules).toEqual([]);
  });

  test("limits that fall inside are drawn, both of them", () => {
    // BlockA spans exactly its own limits, so both land on the values' extremes - inside the
    // padded range, which is the whole reason the range is padded.
    const rules = plotted(BLOCK_A, true).rules;
    expect(rules.map((rule) => rule.value)).toEqual([0, 255]);
  });

  test("in raw counts a limit is converted back", () => {
    // `minimum` and `maximum` are physical. CurveB's upper limit of 127.5 % is 255 counts, and
    // drawing 127.5 against counts of 200 would put the line in the wrong place entirely.
    const withLimit: ValuesReply = { ...CURVE_B, maximum: 102 };
    expect(plotted(withLimit, false).rules.map((rule) => rule.value)).toEqual([204]);
  });

  test("a range of zero gets a span of its own", () => {
    // CurveB reads 100 throughout, so there is nothing to scale; 100 ± a twentieth of itself.
    const plot = plotted(CURVE_B, true);
    expect(plot.low).toBeCloseTo(95);
    expect(plot.high).toBeCloseTo(105);
  });

  test("a range of zero at zero gets one either side", () => {
    // An absent init is zeros, and a twentieth of zero is zero - there is no proportion to take.
    const zeros: ValuesReply = { ...BLOCK_A, rows: [[0, 0, 0, 0, 0, 0, 0, 0]] };
    const plot = plotted(zeros, true);
    expect([plot.low, plot.high]).toEqual([-1, 1]);
  });

  test("a flat line at zero is ruled by its own lower limit", () => {
    // `ValueD` is this object in the demo: an absent init reads zero everywhere, its limits are
    // `0 … 65535`, and the range of -1 to 1 the line above gives it puts the lower limit *inside*
    // the frame - so the rule is drawn exactly where the flat line is. That is correct and looks
    // odd, which is worth knowing before a picture of it is reported as a fault.
    const zeros: ValuesReply = { ...BLOCK_A, rows: [[0, 0, 0, 0, 0, 0, 0, 0]] };
    const plot = plotted(zeros, true);
    expect(plot.rules.map((rule) => rule.value)).toEqual([0]);
    expect(plot.rules[0]?.y).toBeCloseTo(plot.lines[0]?.points[0]?.y ?? -1);
  });

  test("one point is a point and no line", () => {
    const single: ValuesReply = { ...BLOCK_A, shape: [1], rows: [[7]] };
    const points = plotted(single, true).lines[0]?.points ?? [];
    expect(points).toHaveLength(1);
    expect(points[0]?.x).toBeCloseTo(BOX.left + inside / 2);
  });

  test("a map is four lines, each labelled with its own reading", () => {
    const plot = plotted(MAP_A, true);
    expect(plot.lines).toHaveLength(4);
    expect(plot.lines.map((line) => line.label)).toEqual(["0", "30", "70", "100"]);
  });

  test("a row with no label of its own is left unlabelled", () => {
    // A y axis stating fewer breakpoints than the object has rows: the analysis would file a
    // finding, and the page still has to draw what it was sent.
    const short: ValuesReply = {
      ...MAP_A,
      axes: [MAP_A.axes[0] as GridAxis, { ...(MAP_A.axes[1] as GridAxis), breakpoints: [0, 60] }],
    };
    expect(plotted(short, true).lines.map((line) => line.label)).toEqual(["0", "30", "", ""]);
  });

  test("the ticks are the grid's own column readings", () => {
    const plot = plotted(CURVE_A, true);
    expect(plot.ticks.map((tick) => tick.label)).toEqual([
      "0",
      "800",
      "1600",
      "3200",
      "4800",
      "8000",
    ]);
  });

  test("the labels name the axis below and the object beside", () => {
    const plot = plotted(CURVE_A, true);
    expect([plot.xLabel, plot.yLabel]).toEqual(["AxisA (Hz)", "CurveA (ms)"]);
  });

  test("in raw counts the labels drop their units", () => {
    const plot = plotted(CURVE_A, false);
    expect([plot.xLabel, plot.yLabel]).toEqual(["AxisA", "CurveA"]);
  });

  test("laid against indices there is no axis to name", () => {
    expect(plotted(BLOCK_A, true).xLabel).toBe("");
  });

  // The tests below are not in the brief. They close branch-coverage gaps that the brief's own
  // fixtures leave unreached, per the task's instruction to add a covering test rather than
  // delete the branch. See the task report for why each one is needed.

  test("a map whose x axis states no breakpoints is indexed by its own width, not its row count", () => {
    // An axis states a `size` and need not state an `init`; one that does not states no
    // breakpoints at all. A map still needs both of its axes - only this one's breakpoints go
    // missing, not the axis itself or the y axis beside it. MapA is 4 rows of 6, and the
    // fallback must answer 6 - its *column* count - not 4, its row count.
    const noInit: ValuesReply = {
      ...MAP_A,
      axes: [{ ...(MAP_A.axes[0] as GridAxis), breakpoints: [] }, MAP_A.axes[1] as GridAxis],
    };
    const xs = plotted(noInit, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs).toHaveLength(6);
    expect(xs[5]).toBeCloseTo(BOX.left + inside);
  });

  test("a column with no breakpoint of its own sits at the axis's own start", () => {
    // AxisA normally states one breakpoint per column. State fewer than CurveA has columns, and
    // the missing ones must still place somewhere rather than throw - at the start of the range
    // the breakpoints that do exist describe, same as a missing row label reads as "".
    const shortAxis: ValuesReply = {
      ...CURVE_A,
      axes: [{ ...AXIS_A, breakpoints: [0, 3200, 6400] }],
    };
    const xs = plotted(shortAxis, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs[5]).toBeCloseTo(BOX.left);
  });
});
