import { describe, expect, test } from "vitest";
import type { ValuesReply } from "../api/types";
import {
  appliesOver,
  holdAfter,
  holdOf,
  type ValuesHold,
  valuesShown,
  writtenBy,
} from "./valuesHold";

/** CurveA as the grid showed it before an Apply, at revision 4 - the demo's own six values. */
const BEFORE: ValuesReply = {
  revision: 4,
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
  axes: [],
  owner: "Controller",
  file: "C:/work/demo/components/controller.ddd.json",
  findings: [],
};

/** Element 3 set to 750 raw, answered as edit 7. */
const HOLD: ValuesHold = holdOf(7, BEFORE, { cell: { row: 0, column: 2 }, raw: 750 });

/** The grid as the server answers it at `revision`: the values it read at that revision. */
function served(revision: number, rows: number[][] = BEFORE.rows): ValuesReply {
  return { ...BEFORE, revision, rows };
}

/** A state at `revision`, including the page's and every window's edits up to `edits`. */
function state(revision: number, edits: number) {
  return { revision, edits };
}

const NONE: ReadonlyMap<number, number> = new Map();

describe("what an Apply would write", () => {
  test("a pasted table: its rows, whatever cell was typed into before", () => {
    const rows = [[1, 2, 3, 4, 5, 6]];
    expect(writtenBy(rows, { row: 0, column: 2 }, 750)).toEqual({ rows });
  });

  test("else the cell being typed into, and the raw count its text comes to", () => {
    expect(writtenBy(null, { row: 1, column: 3 }, 50)).toEqual({
      cell: { row: 1, column: 3 },
      raw: 50,
    });
  });

  test("nothing, while no cell is typed into or its text is no number", () => {
    expect(writtenBy(null, null, null)).toBeNull();
    expect(writtenBy(null, { row: 0, column: 2 }, null)).toBeNull();
  });
});

describe("what an Apply in the grid holds", () => {
  test("one cell: the values the grid showed, that cell set to the raw count written", () => {
    expect(HOLD.edit).toBe(7);
    expect(HOLD.landed).toBeNull();
    expect(HOLD.before).toBe(BEFORE);
    expect(HOLD.after).toEqual({ ...BEFORE, rows: [[1200, 900, 750, 750, 700, 650]] });
    // What the grid showed is left as it was.
    expect(BEFORE.rows).toEqual([[1200, 900, 800, 750, 700, 650]]);
  });

  test("one cell of a map: its row and its column, and no other", () => {
    const map = {
      ...BEFORE,
      shape: [2, 3],
      rows: [
        [1, 2, 3],
        [4, 5, 6],
      ],
    };
    expect(holdOf(3, map, { cell: { row: 1, column: 2 }, raw: 60 }).after.rows).toEqual([
      [1, 2, 3],
      [4, 5, 60],
    ]);
  });

  test("a pasted table: every value, as pasted", () => {
    const pasted = [[1300, 950, 850, 800, 750, 700]];
    expect(holdOf(8, BEFORE, { rows: pasted }).after).toEqual({ ...BEFORE, rows: pasted });
  });

  test.each(["scalar", "none"] as const)(
    "a grid stating %s comes to state every value, as the file then does",
    (stated) => {
      // `set_cell` writes the whole init where the file held one value or none.
      const flat = { ...BEFORE, stated, rows: [[200, 200, 200, 200, 200, 200]] };
      const held = holdOf(5, flat, { cell: { row: 0, column: 0 }, raw: 100 }).after;
      expect([held.stated, held.rows]).toEqual(["array", [[100, 200, 200, 200, 200, 200]]]);
    },
  );
});

describe("which values the grid shows", () => {
  test("with nothing held, the server's answer", () => {
    expect(valuesShown(null, NONE, state(4, 6), served(4))).toEqual(served(4));
  });

  describe("an Apply, answered as edit 7", () => {
    test("what it wrote, while the revision landed is before it", () => {
      expect(valuesShown(HOLD, NONE, state(4, 6), served(4))).toBe(HOLD.after);
      // An analysis that began before the edit was written lands without it.
      expect(valuesShown(HOLD, NONE, state(5, 6), served(5))).toBe(HOLD.after);
    });

    test("the server's answer, once a revision landed at it or after it answers", () => {
      const landed = served(5, HOLD.after.rows);
      expect(valuesShown(HOLD, NONE, state(5, 7), landed)).toBe(landed);
      expect(valuesShown(HOLD, NONE, state(6, 9), served(6))).toEqual(served(6));
    });

    test("what it wrote, while the answer on screen is a revision's before the one landed", () => {
      // The revision moved and the query keyed by it has not answered yet: the answer it keeps
      // meanwhile was read before the edit.
      expect(valuesShown(HOLD, NONE, state(5, 7), served(4))).toBe(HOLD.after);
    });

    test("what it wrote, while the state has not said an answer newer than it includes the edit", () => {
      // The server answers from the newest revision, which the page may not have heard of yet.
      expect(valuesShown(HOLD, NONE, state(4, 6), served(5, HOLD.after.rows))).toBe(HOLD.after);
    });
  });

  describe("an undo of it, answered as edit 9", () => {
    const undone = new Map([[7, 9]]);

    test("the values from before the Apply, while the revision landed is before the undo", () => {
      // Before the Apply's analysis landed, at it, and past it with another window's edit.
      expect(valuesShown(HOLD, undone, state(4, 6), served(4))).toBe(HOLD.before);
      expect(valuesShown(HOLD, undone, state(5, 7), served(5, HOLD.after.rows))).toBe(HOLD.before);
      expect(valuesShown(HOLD, undone, state(6, 8), served(6, HOLD.after.rows))).toBe(HOLD.before);
    });

    test("the server's answer, once a revision landed at the undo or after it answers", () => {
      expect(valuesShown(HOLD, undone, state(6, 9), served(6))).toEqual(served(6));
      expect(valuesShown(HOLD, undone, state(7, 10), served(7))).toEqual(served(7));
    });

    test("the values from before, while the answer on screen is a revision's before that one", () => {
      expect(valuesShown(HOLD, undone, state(6, 9), served(5, HOLD.after.rows))).toBe(HOLD.before);
    });

    test("the values from before, after an undo of something else made before it", () => {
      // Another window's edit 8 undone first, as 9, then the Apply, as 10.
      const both = new Map([
        [8, 9],
        [7, 10],
      ]);
      expect(valuesShown(HOLD, both, state(5, 9), served(5, HOLD.after.rows))).toBe(HOLD.before);
      expect(valuesShown(HOLD, both, state(6, 10), served(6))).toEqual(served(6));
    });
  });

  describe("an undo of something else", () => {
    test("made before the Apply, it changes nothing the hold says", () => {
      expect(valuesShown(HOLD, new Map([[5, 6]]), state(4, 6), served(4))).toBe(HOLD.after);
    });

    test("made after the Apply, the server's answer, whatever revision it is", () => {
      // Another window's edit 8, undone here as 9: the grid never held it.
      const other = new Map([[8, 9]]);
      expect(valuesShown(HOLD, other, state(4, 6), served(4))).toEqual(served(4));
      expect(valuesShown(HOLD, other, state(5, 7), served(4))).toEqual(served(4));
      expect(valuesShown(HOLD, other, state(6, 9), served(6))).toEqual(served(6));
      expect(valuesShown(HOLD, other, state(7, 10), served(7))).toEqual(served(7));
    });

    test("made after the undo of the Apply, the server's answer", () => {
      // Edit 3, which the grid no longer holds, undone as 10 after the Apply was undone as 9.
      const after = new Map([
        [7, 9],
        [3, 10],
      ]);
      expect(valuesShown(HOLD, after, state(5, 7), served(5, HOLD.after.rows))).toEqual(
        served(5, HOLD.after.rows),
      );
    });
  });
});

describe("when the hold ends", () => {
  /** HOLD once revision 5, the first to include edit 7, has been seen. */
  const LANDED: ValuesHold = { ...HOLD, landed: { edit: 7, revision: 5 } };

  test("it is stamped with the first revision the page sees include its edit", () => {
    expect(holdAfter(HOLD, NONE, state(5, 7))).toEqual(LANDED);
    // Seen first past it, the revision is the one seen: an earlier one was never heard of.
    expect(holdAfter(HOLD, NONE, state(6, 9))).toEqual({
      ...HOLD,
      landed: { edit: 7, revision: 6 },
    });
  });

  test("it stays as it is while no revision includes its edit, or once it is stamped", () => {
    // The very same hold, so that the page can tell nothing changed.
    expect(holdAfter(HOLD, NONE, state(5, 6))).toBe(HOLD);
    expect(holdAfter(LANDED, NONE, state(6, 8))).toBe(LANDED);
    expect(holdAfter(null, NONE, state(6, 8))).toBeNull();
  });

  test("an undo of its Apply noted after the stamp waits for the first revision including the undo", () => {
    const undone = new Map([[7, 9]]);
    expect(holdAfter(LANDED, undone, state(6, 8))).toBe(LANDED);
    expect(holdAfter(LANDED, undone, state(7, 9))).toEqual({
      ...HOLD,
      landed: { edit: 9, revision: 7 },
    });
  });

  test("a later revision answers with the placeholder it keeps, which already includes the edit", () => {
    // Revision 5 included edit 7 and answered; revision 6 landed, and its own answer is asked for.
    const fifth = served(5, HOLD.after.rows);
    expect(valuesShown(LANDED, NONE, state(6, 7), fifth)).toBe(fifth);
  });

  test("a value saved from outside after the landing shows as saved, never as the hold had it", () => {
    // Element 6 set to 100 by a save the analysis of revision 5 read beside edit 7: at the next
    // landing, revision 5's answer is kept while revision 6's is asked for.
    const saved = served(5, [[1200, 900, 750, 750, 700, 100]]);
    expect(valuesShown(LANDED, NONE, state(6, 7), saved).rows).toEqual([
      [1200, 900, 750, 750, 700, 100],
    ]);
  });

  test("an answer from before the stamped revision is still not taken", () => {
    expect(valuesShown(LANDED, NONE, state(6, 7), served(4))).toBe(HOLD.after);
  });

  test("an undo of its Apply after the stamp shows the values from before until the undo lands", () => {
    const undone = new Map([[7, 9]]);
    // Revision 6 answers what edit 7 wrote: the undo, as 9, is not in it.
    expect(valuesShown(LANDED, undone, state(6, 8), served(6, HOLD.after.rows))).toBe(HOLD.before);
    const undoLanded = { ...HOLD, landed: { edit: 9, revision: 7 } };
    expect(valuesShown(undoLanded, undone, state(8, 9), served(7))).toEqual(served(7));
  });
});

describe("whether an Apply may be planned over the values shown", () => {
  test("yes, over the answer of the revision the page holds, or a newer one", () => {
    expect(appliesOver(served(5), state(5, 7))).toBe(true);
    expect(appliesOver(served(6), state(5, 7))).toBe(true);
  });

  test("no, over an older revision's answer, kept while the page's own is asked for", () => {
    // Its hold would keep that revision's values as the values from before the Apply.
    expect(appliesOver(served(4), state(5, 7))).toBe(false);
  });
});
