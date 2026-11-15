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
  it("takes it when the table holds no focused cell", () => {
    expect(takesFocusedCell(null)).toBe(true);
  });

  it("leaves a cell the table holds to the table, whatever its key", () => {
    expect(takesFocusedCell("cell:2:2")).toBe(false);
    expect(takesFocusedCell(0)).toBe(false);
    expect(takesFocusedCell("")).toBe(false);
  });
});
