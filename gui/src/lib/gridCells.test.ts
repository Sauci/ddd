import { describe, expect, it } from "vitest";
import { cellId, takesFocusedCell } from "./gridCells";

describe("cellId", () => {
  it("names a cell by its row and its column", () => {
    expect(cellId(2, 3)).toBe("cell:2:3");
  });

  it("names every cell of a grid differently", () => {
    expect(cellId(1, 11)).not.toBe(cellId(11, 1));
  });
});

describe("takesFocusedCell", () => {
  it("takes it when the table holds no focused cell, however the focus came", () => {
    expect(takesFocusedCell(null, false)).toBe(true);
    expect(takesFocusedCell(null, true)).toBe(true);
  });

  it("leaves a cell the table holds to the table where Tab brought the focus, whatever its key", () => {
    expect(takesFocusedCell("cell:2:2", true)).toBe(false);
    expect(takesFocusedCell(0, true)).toBe(false);
    expect(takesFocusedCell("", true)).toBe(false);
  });

  it("takes it from the table where the focus came another way: a screen reader's, a click, a key", () => {
    expect(takesFocusedCell("cell:2:2", false)).toBe(true);
    expect(takesFocusedCell(0, false)).toBe(true);
  });
});
