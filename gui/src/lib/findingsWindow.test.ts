import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import type { FindingsReply, ListedFinding } from "../api/types";
import {
  arrivedPages,
  BOX_HEIGHT,
  drawnWindow,
  keeps,
  keptAfter,
  listingTotal,
  MARGIN,
  opensAt,
  PAGE_SIZE,
  pageQuery,
  pagesOf,
  pendingKeys,
  placeOpened,
  type RevisionWindow,
  ROW_HEIGHT,
  scrolledTo,
  scrolledTop,
  spacersOf,
  spanOf,
  windowLine,
  windowRows,
} from "./findingsWindow";
import { fileNames } from "./paths";

const HUB = "C:/work/demo/components/sensor_hub.ddd.json";

/** The names the File column draws for the project's files, by path (`fileNames`): the hub's alone
 * is the only file of its name here. */
const NAMES = fileNames([HUB]);

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
    line: null,
    column: null,
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

  test("ui.css keeps a long table's own row from under its sticky header, by the same ROW_HEIGHT", () => {
    // `.long`'s own `scroll-padding-top` is what stops a row the keyboard walks up to from
    // landing under the sticky header instead of below it (fix round 1, Important 4) - pinned
    // here the way the row height above is, since the window's own ROW_HEIGHT is the one number
    // both this and `.findings-window`'s own scroll-padding-top answer to (fix round 2, New Minor
    // 4). A long table's own row takes its height from the wrapper React Aria's `Virtualizer`
    // sizes to the layout's own `rowHeight` instead of a CSS literal (fix round 1, Important 1) -
    // pinned on `ui/Table.tsx`'s own source text instead, the one place every long table's
    // `layoutOptions` are written (fix round 1, Minor 3).
    const css = readFileSync(new URL("../styles/ui.css", import.meta.url), "utf8");
    const long = css.match(/\.react-aria-Table\.long\s*\{[^}]*\}/g) ?? [];
    expect(long.some((rule) => rule.includes(`scroll-padding-top: ${ROW_HEIGHT}px;`))).toBe(true);
    const table = readFileSync(new URL("../ui/Table.tsx", import.meta.url), "utf8");
    expect(table).toMatch(/rowHeight:\s*ROW_HEIGHT/);
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

  test("a filtered listing's page is asked for under its text, an unfiltered one's under none", () => {
    expect(pageQuery(0, "C00500")).toEqual({ offset: 0, limit: 100, text: "C00500" });
    expect(pageQuery(2, "valuee")).toEqual({ offset: 200, limit: 100, text: "valuee" });
    expect(pageQuery(2, "")).toEqual({ offset: 200, limit: 100 });
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
    const rows = windowRows({ first: 0, last: 2 }, new Map([[0, page(0)]]), NAMES);
    expect(rows).toEqual([
      { index: 0, key: listed(0).key, finding: listed(0), file: "sensor_hub.ddd.json" },
      { index: 1, key: listed(1).key, finding: listed(1), file: "sensor_hub.ddd.json" },
    ]);
  });

  test("a row whose page has not arrived is a placeholder, keyed by its place", () => {
    const rows = windowRows({ first: 98, last: 102 }, new Map([[0, page(0)]]), NAMES);
    expect(rows.map((row) => [row.index, row.key, row.finding === null, row.file])).toEqual([
      [98, listed(98).key, false, "sensor_hub.ddd.json"],
      [99, listed(99).key, false, "sensor_hub.ddd.json"],
      [100, "pending-100", true, ""],
      [101, "pending-101", true, ""],
    ]);
  });

  test("the rows of a later page are read from where that page starts", () => {
    const rows = windowRows({ first: 205, last: 207 }, new Map([[2, page(2)]]), NAMES);
    expect(rows.map((row) => row.finding)).toEqual([listed(205), listed(206)]);
  });

  test("a file told apart from another of its name by its path, as the column draws it", () => {
    // `left/gauge.ddd.json` and `right/gauge.ddd.json` are two rows of one name otherwise
    // (16:M15). A file the project does not list keeps its own name.
    const left = "C:/work/demo/left/gauge.ddd.json";
    const right = "C:/work/demo/right/gauge.ddd.json";
    const elsewhere = { ...listed(2), file: "C:/other/unlisted.ddd.json" };
    const reply: FindingsReply = {
      revision: 7,
      total: 3,
      offset: 0,
      findings: [{ ...listed(0), file: left }, { ...listed(1), file: right }, elsewhere],
    };
    const rows = windowRows({ first: 0, last: 3 }, new Map([[0, reply]]), fileNames([left, right]));
    expect(rows.map((row) => row.file)).toEqual([
      "left/gauge.ddd.json",
      "right/gauge.ddd.json",
      "unlisted.ddd.json",
    ]);
  });

  test("none, for a span with no row", () => {
    expect(windowRows({ first: 0, last: 0 }, new Map(), NAMES)).toEqual([]);
  });
});

describe("the rows nobody can select", () => {
  test("each placeholder, by its key, and no row whose finding has arrived", () => {
    const rows = windowRows({ first: 98, last: 102 }, new Map([[0, page(0)]]), NAMES);
    expect(pendingKeys(rows)).toEqual(["pending-100", "pending-101"]);
    expect(pendingKeys(windowRows({ first: 0, last: 3 }, new Map([[0, page(0)]]), NAMES))).toEqual(
      [],
    );
  });
});

describe("where the box stands for the listing asked", () => {
  test("where it was scrolled to, under the very text asked", () => {
    expect(scrolledTop({ text: "c00500", top: 990 }, "c00500")).toBe(990);
    expect(scrolledTop({ text: "", top: 824_967 }, "")).toBe(824_967);
  });

  test("at its top for a text newly asked, whose table is drawn anew", () => {
    // Scrolled to the last of 25,000 findings, then filtered: the listing starts at its first row.
    expect(scrolledTop({ text: "", top: 824_967 }, "c00500")).toBe(0);
    // And back to every finding, or on to another text.
    expect(scrolledTop({ text: "c00500", top: 990 }, "")).toBe(0);
    expect(scrolledTop({ text: "c00500", top: 990 }, "missing-id")).toBe(0);
  });
});

describe("where the tab opens, drawn anew (16:M16)", () => {
  const PROJECT = "C:/work/demo/demo.ddd.json";
  /** Scrolled to row 606 of the 15,000 `missing-id` findings, the one at row 610 opened. */
  const held = { project: PROJECT, text: "missing-id", top: 20_000, selected: listed(610) };

  test("at the place held of the very listing its address asks for: its scroll and its finding", () => {
    expect(placeOpened(held, PROJECT, "missing-id")).toEqual({
      top: 20_000,
      selected: listed(610),
    });
    // The bare tab's own place, its box scrolled and no panel open.
    const bare = { project: PROJECT, text: "", top: 824_967, selected: undefined };
    expect(placeOpened(bare, PROJECT, "")).toEqual({ top: 824_967, selected: undefined });
  });

  test("at its top, no panel open, for another listing, another project's place, or none held", () => {
    // A link to a file's findings, while the place held is of every finding.
    expect(placeOpened(held, PROJECT, "controller.ddd.json")).toEqual({
      top: 0,
      selected: undefined,
    });
    expect(placeOpened(held, PROJECT, "")).toEqual({ top: 0, selected: undefined });
    expect(placeOpened(held, "C:/work/second/second.ddd.json", "missing-id")).toEqual({
      top: 0,
      selected: undefined,
    });
    expect(placeOpened(null, PROJECT, "missing-id")).toEqual({ top: 0, selected: undefined });
  });

  /** A listing's window as the tab draws it, `total` rows in all or `null` where its count is not
   * known yet. */
  function drawnOf(text: string, total: number | null): RevisionWindow {
    return {
      revision: 7,
      text,
      total,
      all: 25000,
      statements: { error: 0, warning: 25000, info: 0 },
      span: { first: 0, last: 0 },
      pages: new Map(),
    };
  }

  test("its box scrolled there once the spaces standing for its rows are known", () => {
    expect(opensAt(drawnOf("", 25000), 20_000)).toBe(20_000);
    expect(opensAt(drawnOf("missing-id", 15000), 20_000)).toBe(20_000);
    expect(opensAt(drawnOf("missing-id", 15000), 0)).toBe(0);
  });

  test("nowhere yet while a filtered listing's count has not come: the box could not stand there", () => {
    expect(opensAt(drawnOf("missing-id", null), 20_000)).toBeNull();
  });
});

describe("whether a scroll keeps the row the keyboard is on", () => {
  // A row that leaves the window while it holds the focus is one React Aria moves the focus off,
  // to whichever row then stands at its place - and, while the reader is on the keyboard, scrolls
  // the box back to that row: it gives the focus up first.
  test("yes, while the rows drawn after the scroll still include it", () => {
    expect(keeps(3, 0, BOX_HEIGHT)).toBe(true);
    expect(keeps(3, 23 * ROW_HEIGHT, BOX_HEIGHT)).toBe(true);
    expect(keeps(57, 23 * ROW_HEIGHT, BOX_HEIGHT)).toBe(true);
  });

  test("no, once a scroll takes the window past it, either way", () => {
    expect(keeps(3, 24 * ROW_HEIGHT, BOX_HEIGHT)).toBe(false);
    expect(keeps(58, 23 * ROW_HEIGHT, BOX_HEIGHT)).toBe(false);
    expect(keeps(3, 1200, BOX_HEIGHT)).toBe(false);
  });
});

describe("the scroll that brings a row the window let go back into the box", () => {
  test("every row before it, so that it stands first in view and the window draws it", () => {
    expect(scrolledTo(0)).toBe(0);
    expect(scrolledTo(1)).toBe(ROW_HEIGHT);
    expect(scrolledTo(24999)).toBe(24999 * ROW_HEIGHT);
    for (const index of [0, 57, 9999, 24999]) {
      expect(keeps(index, scrolledTo(index), BOX_HEIGHT)).toBe(true);
      expect(spanOf(scrolledTo(index), BOX_HEIGHT, 25000).first).toBe(Math.max(0, index - MARGIN));
    }
  });

  test("the top of the box, for a place before the first row", () => {
    expect(scrolledTo(-3)).toBe(0);
  });
});

describe("how many rows a listing has in all", () => {
  test("unfiltered, every finding its revision files, known at once", () => {
    expect(listingTotal("", 25000, undefined, 7)).toBe(25000);
    expect(listingTotal("", 25000, page(0, 30), 7)).toBe(25000);
  });

  test("filtered, what its first page says, once that page has come of its revision", () => {
    expect(listingTotal("C00500", 25000, page(0, 30), 7)).toBe(30);
    expect(listingTotal("nothing", 25000, page(0, 0), 7)).toBe(0);
  });

  test("filtered, unknown before its first page has come, or while that is another revision's", () => {
    expect(listingTotal("C00500", 25000, undefined, 7)).toBeNull();
    expect(listingTotal("C00500", 25000, { ...page(0, 30), revision: 8 }, 7)).toBeNull();
  });
});

describe("which revision's rows the window draws", () => {
  /** A revision's window at the top of the box, of `total` rows, with these pages arrived: every
   * finding a warning, and each a statement of its own unless `statements` says how many fewer
   * the revision makes - a disagreement is filed on each of its files. Unfiltered, unless `text`
   * is given, where its revision files `all` rows. */
  function windowOf(
    revision: number,
    total: number,
    arrived: number[],
    statements = total,
    text = "",
    all = total,
  ): RevisionWindow {
    const span = spanOf(0, BOX_HEIGHT, total);
    const pages = new Map(arrived.map((number) => [number, { ...page(number, total), revision }]));
    return {
      revision,
      text,
      total,
      all,
      statements: { error: 0, warning: statements, info: 0 },
      span,
      pages,
    };
  }
  /** Revision 7, drawn whole at the top of the box: its one page there has arrived. */
  const last = windowOf(7, 1000, [0]);

  test("the newest revision's, once every page of its span has arrived", () => {
    const newest = windowOf(8, 990, [0]);
    expect(drawnWindow(newest, last)).toBe(newest);
    expect(drawnWindow(newest, null)).toBe(newest);
  });

  test("the last revision drawn whole, until then: no row turns to a placeholder and back", () => {
    // Its rows are its own findings, keyed as they were, so React Aria keeps its focus on the one
    // it was on: a finding that stays keeps its key into the next revision.
    const newest = windowOf(8, 990, []);
    expect(drawnWindow(newest, last)).toBe(last);
    expect(pendingKeys(windowRows(last.span, last.pages, NAMES))).toEqual([]);
  });

  test("the newest, placeholders and all, where the last's pages for the span are not all there", () => {
    // Scrolled while the newest was asked for, to rows the last revision never had asked.
    const scrolled = { ...last, span: { first: 80, last: 130 } };
    expect(drawnWindow(windowOf(8, 990, []), scrolled)).toEqual(windowOf(8, 990, []));
    // And before any revision was drawn whole.
    expect(drawnWindow(windowOf(8, 990, []), null)).toEqual(windowOf(8, 990, []));
  });

  test("a revision with no finding is whole at once, and drawn as soon as it lands", () => {
    const none = windowOf(8, 0, []);
    expect(drawnWindow(none, last)).toBe(none);
  });

  test("its total switches with it: the window draws the revision's own", () => {
    expect(drawnWindow(windowOf(8, 990, []), last).total).toBe(1000);
    expect(drawnWindow(windowOf(8, 990, [0]), last).total).toBe(990);
  });

  test("its statements switch with it: the line above the table counts the revision drawn", () => {
    // Until the newest revision's pages have come, the table draws the last one's rows, and the
    // line above it says how many statements that one makes, not the newest.
    expect(drawnWindow(windowOf(8, 990, []), last).statements).toEqual({
      error: 0,
      warning: 1000,
      info: 0,
    });
    expect(drawnWindow(windowOf(8, 990, [0]), last).statements).toEqual({
      error: 0,
      warning: 990,
      info: 0,
    });
  });

  test("the rows size the box and the statements are what the line counts, each the drawn one's", () => {
    // Decision 14.3: a disagreement filed on both of its files is two rows of the table and one
    // statement of the line, as `ddd check` counts it - so 990 rows of 600 statements, and the
    // last revision's 1000 of 700 while the newest's page is still to come.
    const newest = windowOf(8, 990, [0], 600);
    const before = windowOf(7, 1000, [0], 700);
    expect(drawnWindow(newest, before)).toMatchObject({
      total: 990,
      statements: { error: 0, warning: 600, info: 0 },
    });
    expect(drawnWindow(windowOf(8, 990, [], 600), before)).toMatchObject({
      total: 1000,
      statements: { error: 0, warning: 700, info: 0 },
    });
    expect(keptAfter(newest, null)).toEqual({
      revision: 8,
      text: "",
      total: 990,
      all: 990,
      statements: { error: 0, warning: 600, info: 0 },
    });
  });

  test("the one to keep drawing through the next landing: the window drawn, once it is whole", () => {
    const statements = { error: 0, warning: 990, info: 0 };
    const eight = { revision: 8, text: "", total: 990, all: 990, statements };
    expect(keptAfter(windowOf(8, 990, [0]), null)).toEqual(eight);
    expect(
      keptAfter(windowOf(8, 990, [0]), {
        revision: 7,
        text: "",
        total: 1000,
        all: 1000,
        statements: { error: 0, warning: 1000, info: 0 },
      }),
    ).toEqual(eight);
  });

  test("the one kept before, while the window drawn is not whole, or is that very revision", () => {
    const kept = {
      revision: 7,
      text: "",
      total: 1000,
      all: 1000,
      statements: { error: 0, warning: 1000, info: 0 },
    };
    expect(keptAfter(windowOf(8, 990, []), kept)).toBe(kept);
    expect(keptAfter(windowOf(8, 990, []), null)).toBeNull();
    // The very same answer, so that the page can tell nothing changed.
    expect(keptAfter(last, kept)).toBe(kept);
  });

  test("a filter typed is a listing of its own, drawn once whole, the last kept till then", () => {
    // 16:I14: the newest listing, of revision 7 filtered by `C00500`, 30 of its 1000 rows: until
    // its first page has come, its total is not known, and the unfiltered listing stays drawn.
    const asked: RevisionWindow = { ...windowOf(7, 30, [], 30, "C00500", 1000), total: null };
    expect(drawnWindow(asked, last)).toBe(last);
    const come = windowOf(7, 30, [0], 30, "C00500", 1000);
    expect(drawnWindow(come, last)).toBe(come);
    const kept = keptAfter(last, null);
    expect(keptAfter(come, kept)).toEqual({
      revision: 7,
      text: "C00500",
      total: 30,
      all: 1000,
      statements: { error: 0, warning: 30, info: 0 },
    });
    // Back to no filter: the unfiltered listing is another again.
    expect(keptAfter(last, keptAfter(come, kept))).toEqual(kept);
  });

  test("a listing whose total is not known is never whole, even with no page to ask", () => {
    const unknown: RevisionWindow = {
      ...windowOf(7, 0, [], 0, "C00500", 1000),
      total: null,
    };
    expect(drawnWindow(unknown, last)).toBe(last);
    expect(keptAfter(unknown, null)).toBeNull();
  });
});

describe("the line beside the Findings tab's filter", () => {
  function listing(text: string, total: number | null): RevisionWindow {
    return {
      revision: 7,
      text,
      total,
      all: 25000,
      statements: { error: 0, warning: 25000, info: 0 },
      span: { first: 0, last: 0 },
      pages: new Map(),
    };
  }

  test("how many rows the listing drawn leaves of its revision's", () => {
    expect(windowLine(listing("C00500", 45))).toBe("45 of 25,000 findings");
    expect(windowLine(listing("C00500", 0))).toBe("no finding matches");
  });

  test("nothing for the unfiltered listing, or one whose count is not known yet", () => {
    expect(windowLine(listing("", 25000))).toBeNull();
    expect(windowLine(listing("C00500", null))).toBeNull();
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
