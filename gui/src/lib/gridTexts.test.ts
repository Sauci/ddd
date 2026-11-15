import { describe, expect, test, vi } from "vitest";
import type { ValuesReply } from "../api/types";
import { GridStore, gridTexts, textAt } from "./gridTexts";
import { heldReadings, type TypedCell } from "./objectValues";

const BLOCK: ValuesReply = {
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
  file: "user_interface.ddd.json",
  findings: [],
};

const MAP: ValuesReply = {
  ...BLOCK,
  name: "MapA",
  kind: "map",
  datatype: "sint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  shape: [2, 3],
  rows: [
    [20, 24, 28],
    [18, 22, 26],
  ],
};

function typedCell(row: number, column: number, typed: string, physical = true): TypedCell {
  return { row, column, typed, physical };
}

/** `reply` with every row of its cells wrapped to count the reads of them, and the count. */
function counted(reply: ValuesReply): [ValuesReply, () => number] {
  let reads = 0;
  const rows = reply.rows.map(
    (row) =>
      new Proxy(row, {
        get(target, key, receiver) {
          if (typeof key === "string" && /^\d+$/.test(key)) reads += 1;
          return Reflect.get(target, key, receiver);
        },
      }),
  );
  return [{ ...reply, rows }, () => reads];
}

/** A row of `columns` float32 counts read in physical by a factor, the readings the page works
 * hardest at (`floatReading`). */
function floats(rows: number, columns: number): ValuesReply {
  return {
    ...BLOCK,
    datatype: "float32",
    conversion: { kind: "linear", factor: 0.1, offset: 0 },
    shape: rows === 1 ? [columns] : [rows, columns],
    rows: Array.from({ length: rows }, (_, row) =>
      Array.from({ length: columns }, (_, column) => row * 1000 + column + 0.25),
    ),
  };
}

describe("gridTexts", () => {
  test("a cell nothing is typed into shows what its count reads as", () => {
    const shown = gridTexts(MAP, [], true, 3);
    expect(textAt(shown, 0, 1)).toBe("12");
    expect(textAt(shown, 1, 2)).toBe("13");
    expect(textAt(gridTexts(MAP, [], false, 3), 1, 2)).toBe("26");
  });

  test("a cell typed into shows what was typed, and the others still what they read", () => {
    const shown = gridTexts(MAP, [typedCell(0, 1, "7.25")], true, 3);
    expect(textAt(shown, 0, 1)).toBe("7.25");
    expect(textAt(shown, 0, 0)).toBe("10");
    expect(shown.held.size).toBe(1);
  });

  test("typed in one reading, a cell shows the count its text comes to in the other", () => {
    expect(textAt(gridTexts(MAP, [typedCell(0, 1, "7.25")], false, 3), 0, 1)).toBe("14");
  });

  test("a cell past the shape shows nothing", () => {
    const shown = gridTexts(MAP, [], true, 3);
    expect(textAt(shown, 5, 0)).toBe("");
    expect(textAt(shown, 0, 9)).toBe("");
  });

  test("the cells' readings are worked out once for a reply, whatever is typed after", () => {
    const [reply, reads] = counted(floats(1, 4096));
    const first = gridTexts(reply, [], true, 4096);
    const afterReading = reads();
    expect(afterReading).toBeGreaterThanOrEqual(4096);
    expect(afterReading).toBeLessThanOrEqual(4 * 4096);
    let typed: TypedCell[] = [];
    for (const text of ["1", "12", "123", "1234"]) {
      typed = [typedCell(0, 7, text)];
      const shown = gridTexts(reply, typed, true, 4096);
      expect(shown.texts).toBe(first.texts);
    }
    // Four keystrokes, each reading nothing of the thousands of cells it did not type into.
    expect(reads() - afterReading).toBeLessThanOrEqual(8);
  });

  test("a grid past the readings the page keeps is read once, not on every drawing (15:M8)", () => {
    const reply = floats(1, 60_000);
    const first = gridTexts(reply, [], true, 60_000);
    // The readings were let go whole on the way: a drawing that read each cell again would read
    // all sixty thousand again.
    expect(heldReadings()).toBeLessThan(60_000);
    const again = gridTexts(reply, [typedCell(0, 3, "9")], true, 60_000);
    expect(again.texts).toBe(first.texts);
    expect(heldReadings()).toBeLessThan(60_000);
  });

  test("another reading, or another reply, is read of its own", () => {
    const first = gridTexts(MAP, [], true, 3);
    expect(gridTexts(MAP, [], false, 3).texts).not.toBe(first.texts);
    expect(gridTexts({ ...MAP }, [], true, 3).texts).not.toBe(first.texts);
    expect(gridTexts(MAP, [], true, 3).texts).toBe(first.texts);
  });

  test("a reply counted for another number of columns keeps what it read", () => {
    const first = gridTexts(MAP, [], true, 3);
    const second = gridTexts(MAP, [], true, 2);
    expect(second.texts).toBe(first.texts);
    expect(second.chars).toHaveLength(2);
    expect(gridTexts(MAP, [], true, 3).chars).toHaveLength(3);
  });

  test("the widths of a reply nothing is typed into are the ones worked out for it, once", () => {
    const first = gridTexts(MAP, [], true, 3);
    expect(gridTexts(MAP, [], true, 3).chars).toBe(first.chars);
    expect(gridTexts(MAP, [typedCell(0, 0, "1")], true, 3).chars).not.toBe(first.chars);
  });

  test("only the columns a cell is typed into have their width worked out again", () => {
    const base = gridTexts(MAP, [], true, 3);
    const shown = gridTexts(MAP, [typedCell(1, 1, "123456")], true, 3);
    expect(base.chars).toEqual([2, 2, 2]);
    expect(shown.chars).toEqual([2, 6, 2]);
    // A cell typed back to nothing is no wider than the others of its column.
    expect(gridTexts(MAP, [typedCell(0, 1, ""), typedCell(1, 1, "")], true, 3).chars).toEqual([
      2, 0, 2,
    ]);
  });

  test("a cell typed into outside the shape widens nothing", () => {
    expect(gridTexts(MAP, [typedCell(9, 1, "123456")], true, 3).chars).toEqual([2, 2, 2]);
  });
});

describe("GridStore", () => {
  test("hands out the text and the width of each field", () => {
    const store = new GridStore(gridTexts(MAP, [], true, 3));
    expect(store.textAt(0, 0)).toBe("10");
    expect(store.charsAt(0)).toBe(2);
    expect(store.charsAt(9)).toBe(0);
  });

  test("tells those subscribed what the grid now shows, and not those who let go", () => {
    const store = new GridStore(gridTexts(MAP, [], true, 3));
    const kept = vi.fn();
    const dropped = vi.fn();
    store.subscribe(kept);
    store.subscribe(dropped)();
    store.update(gridTexts(MAP, [typedCell(0, 0, "99")], true, 3));
    expect(store.textAt(0, 0)).toBe("99");
    expect(kept).toHaveBeenCalledTimes(1);
    expect(dropped).not.toHaveBeenCalled();
  });

  test("says nothing of what it already shows", () => {
    const shown = gridTexts(MAP, [], true, 3);
    const store = new GridStore(shown);
    const listener = vi.fn();
    store.subscribe(listener);
    store.update(shown);
    expect(listener).not.toHaveBeenCalled();
  });

  test("a listener that lets go while it is told does not stop the others being told", () => {
    const store = new GridStore(gridTexts(MAP, [], true, 3));
    const second = vi.fn();
    const first = store.subscribe(() => first());
    store.subscribe(second);
    store.update(gridTexts(MAP, [typedCell(0, 0, "1")], true, 3));
    expect(second).toHaveBeenCalledTimes(1);
  });
});
