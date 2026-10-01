import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import type { FindingsReply, ListedFinding } from "../api/types";
import {
  arrivedPages,
  BOX_HEIGHT,
  keeps,
  MARGIN,
  PAGE_SIZE,
  pageQuery,
  pagesOf,
  pendingKeys,
  ROW_HEIGHT,
  spacersOf,
  spanOf,
  windowRows,
} from "./findingsWindow";

const HUB = "C:/work/demo/components/sensor_hub.ddd.json";

/** The finding at `index` of a long table, its key the server's own shape. */
function listed(index: number): ListedFinding {
  const message = `'Value${index}' is written by component 'SensorHub' but read by nobody`;
  const pointer = `component.interface[${index}]`;
  return {
    file: HUB,
    check: "unused-output",
    severity: "warning",
    message,
    pointer,
    notes: [],
    route: { kind: "variable", name: `Value${index}` },
    key: JSON.stringify([HUB, "warning", "unused-output", pointer, message, 0]),
  };
}

/** Page `page` of a table of `total` findings, as `GET /api/findings` answers it. */
function page(number: number, total = 1000): FindingsReply {
  const first = number * PAGE_SIZE;
  const findings = [];
  for (let index = first; index < Math.min(total, first + PAGE_SIZE); index += 1) {
    findings.push(listed(index));
  }
  return { revision: 7, total, offset: first, findings };
}

describe("the window's measures", () => {
  test("a row is 33 pixels, a page a hundred findings, and twenty rows drawn on each side", () => {
    expect([ROW_HEIGHT, PAGE_SIZE, MARGIN]).toEqual([33, 100, 20]);
  });

  test("the box is fifteen rows high", () => {
    expect(BOX_HEIGHT).toBe(15 * 33);
  });

  test("ui.css draws the rows and the box the window's arithmetic counts on", () => {
    // What turns a scroll position into a row is ROW_HEIGHT: a stylesheet drawing rows of another
    // height would misplace every row the window draws. What the window covers before the box
    // reports its own height is BOX_HEIGHT: a box drawn another height would have the window
    // draw too few or too many rows until it does. No other test would see either.
    const css = readFileSync(new URL("../styles/ui.css", import.meta.url), "utf8");
    const rules = css.match(/\.findings-window\s*\{[^}]*\}/g) ?? [];
    expect(rules.some((rule) => rule.includes(`max-height: ${BOX_HEIGHT}px;`))).toBe(true);
    const rows = css.match(/\.findings-window \.react-aria-Row[^{]*\{[^}]*\}/g) ?? [];
    expect(rows.some((rule) => rule.includes(`height: ${ROW_HEIGHT}px;`))).toBe(true);
  });
});

describe("the rows in view, and a margin", () => {
  test("at the top, the margin above is cut off rather than counted below the first row", () => {
    expect(spanOf(0, 330, 1000)).toEqual({ first: 0, last: 30 });
    expect(spanOf(5 * ROW_HEIGHT, 330, 1000)).toEqual({ first: 0, last: 35 });
  });

  test("a box pulled past its top, as some browsers let one be, is at its top", () => {
    expect(spanOf(-50, 330, 1000)).toEqual({ first: 0, last: 30 });
  });

  test("in the middle, the rows in view and twenty on each side", () => {
    expect(spanOf(100 * ROW_HEIGHT + 10, 330, 1000)).toEqual({ first: 80, last: 130 });
  });

  test("a box part of a row high draws that row", () => {
    expect(spanOf(0, 340, 1000)).toEqual({ first: 0, last: 31 });
  });

  test("at the bottom, the margin below is cut off at the last row", () => {
    expect(spanOf(990 * ROW_HEIGHT, 330, 1000)).toEqual({ first: 970, last: 1000 });
  });

  test("a table shorter than its box is drawn whole", () => {
    expect(spanOf(0, BOX_HEIGHT, 5)).toEqual({ first: 0, last: 5 });
  });

  test("a table with no findings draws no row, wherever its box was", () => {
    expect(spanOf(0, BOX_HEIGHT, 0)).toEqual({ first: 0, last: 0 });
    expect(spanOf(500 * ROW_HEIGHT, BOX_HEIGHT, 0)).toEqual({ first: 0, last: 0 });
  });

  test("a box scrolled past a table that has since grown shorter draws none of it", () => {
    expect(spanOf(5000 * ROW_HEIGHT, 330, 100)).toEqual({ first: 100, last: 100 });
  });

  test("a box of no height, or less, draws the margin alone", () => {
    expect(spanOf(0, 0, 1000)).toEqual({ first: 0, last: 20 });
    expect(spanOf(0, -2 * ROW_HEIGHT, 1000)).toEqual({ first: 0, last: 20 });
  });
});

describe("the pages a span covers", () => {
  test("one page, when the span is inside it", () => {
    expect(pagesOf({ first: 0, last: 30 })).toEqual([0]);
    expect(pagesOf({ first: 100, last: 200 })).toEqual([1]);
  });

  test("each page a span crosses into, in order", () => {
    expect(pagesOf({ first: 80, last: 130 })).toEqual([0, 1]);
    expect(pagesOf({ first: 99, last: 201 })).toEqual([0, 1, 2]);
  });

  test("none, for a span with no row, wherever it stands", () => {
    expect(pagesOf({ first: 0, last: 0 })).toEqual([]);
    expect(pagesOf({ first: 100, last: 100 })).toEqual([]);
    // What a box scrolled past the end of a table that has grown shorter draws for one render
    // (`spanOf(32500, 495, 150)`), off a page boundary.
    expect(pagesOf({ first: 150, last: 150 })).toEqual([]);
  });

  test("a page is asked for as a hundred findings from its first", () => {
    expect(pageQuery(0)).toEqual({ offset: 0, limit: 100 });
    expect(pageQuery(3)).toEqual({ offset: 300, limit: 100 });
  });

  test("the pages that have arrived, by page, and none that has not", () => {
    const third = page(3);
    expect(arrivedPages([3, 4], [third, undefined], 7)).toEqual(new Map([[3, third]]));
    expect(arrivedPages([], [], 7)).toEqual(new Map());
  });

  test("a page another revision answered is not drawn among this one's", () => {
    // Asked under the revision the page holds, answered by the newest the server has: between an
    // analysis landing and the state saying so, the two differ.
    const third = page(3);
    const newer = { ...page(4), revision: 8 };
    expect(arrivedPages([3, 4], [third, newer], 7)).toEqual(new Map([[3, third]]));
  });
});

describe("the rows the window draws", () => {
  test("from a page that has arrived: each finding with its key and its file's own name", () => {
    const rows = windowRows({ first: 0, last: 2 }, new Map([[0, page(0)]]));
    expect(rows).toEqual([
      { index: 0, key: listed(0).key, finding: listed(0), file: "sensor_hub.ddd.json" },
      { index: 1, key: listed(1).key, finding: listed(1), file: "sensor_hub.ddd.json" },
    ]);
  });

  test("a row whose page has not arrived is a placeholder, keyed by its place", () => {
    const rows = windowRows({ first: 98, last: 102 }, new Map([[0, page(0)]]));
    expect(rows.map((row) => [row.index, row.key, row.finding === null, row.file])).toEqual([
      [98, listed(98).key, false, "sensor_hub.ddd.json"],
      [99, listed(99).key, false, "sensor_hub.ddd.json"],
      [100, "pending-100", true, ""],
      [101, "pending-101", true, ""],
    ]);
  });

  test("the rows of a later page are read from where that page starts", () => {
    const rows = windowRows({ first: 205, last: 207 }, new Map([[2, page(2)]]));
    expect(rows.map((row) => row.finding)).toEqual([listed(205), listed(206)]);
  });

  test("none, for a span with no row", () => {
    expect(windowRows({ first: 0, last: 0 }, new Map())).toEqual([]);
  });
});

describe("the rows nobody can select", () => {
  test("each placeholder, by its key, and no row whose finding has arrived", () => {
    const rows = windowRows({ first: 98, last: 102 }, new Map([[0, page(0)]]));
    expect(pendingKeys(rows)).toEqual(["pending-100", "pending-101"]);
    expect(pendingKeys(windowRows({ first: 0, last: 3 }, new Map([[0, page(0)]])))).toEqual([]);
  });
});

describe("whether a scroll keeps the row the keyboard is on", () => {
  // A row that leaves the window while it holds the focus is one React Aria moves the focus off,
  // to whichever row then stands at its place, and scrolls the box back to: it gives the focus up
  // first.
  test("yes, while the rows drawn after the scroll still include it", () => {
    expect(keeps(3, 0, BOX_HEIGHT, 1000)).toBe(true);
    expect(keeps(3, 23 * ROW_HEIGHT, BOX_HEIGHT, 1000)).toBe(true);
    expect(keeps(57, 23 * ROW_HEIGHT, BOX_HEIGHT, 1000)).toBe(true);
  });

  test("no, once a scroll takes the window past it, either way", () => {
    expect(keeps(3, 24 * ROW_HEIGHT, BOX_HEIGHT, 1000)).toBe(false);
    expect(keeps(58, 23 * ROW_HEIGHT, BOX_HEIGHT, 1000)).toBe(false);
    expect(keeps(3, 1200, BOX_HEIGHT, 1000)).toBe(false);
  });

  test("no, for a row past the end of a table that has grown shorter", () => {
    expect(keeps(150, 0, BOX_HEIGHT, 150)).toBe(false);
  });
});

describe("what stands for the rows not drawn", () => {
  test("above, every row before the first drawn; below, every row after the last", () => {
    expect(spacersOf({ first: 80, last: 130 }, 1000)).toEqual({
      above: 80 * 33,
      below: 870 * 33,
    });
  });

  test("nothing, at the top of a table drawn whole", () => {
    expect(spacersOf({ first: 0, last: 5 }, 5)).toEqual({ above: 0, below: 0 });
  });
});
