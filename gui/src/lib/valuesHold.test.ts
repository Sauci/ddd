import { describe, expect, test } from "vitest";
import type { ValuesReply } from "../api/types";
import { holdOf, type ValuesHold, valuesShown, writtenBy } from "./valuesHold";

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
