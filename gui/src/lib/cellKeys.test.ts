import { describe, expect, it } from "vitest";
import { cellId, keptByCell } from "./cellKeys";

const key = (name: string, held: { ctrlKey?: boolean; metaKey?: boolean } = {}) =>
  keptByCell({ key: name, ctrlKey: false, metaKey: false, ...held });

describe("keptByCell", () => {
  it("keeps every key naming one character, digits and a number's signs first", () => {
    for (const name of ["0", "5", "9", ".", "-", "+", ",", "e", "a", " ", "é"]) {
      expect(key(name), name).toBe(true);
    }
  });

  it("keeps a key whose name does not start with a letter, as type-to-find reads it", () => {
    expect(key("€uro")).toBe(true);
  });

  it("leaves a key named by a word to the grid, Enter and the arrows among them", () => {
    for (const name of ["Enter", "ArrowLeft", "Tab", "Backspace", "Delete", "F1", "Escape"]) {
      expect(key(name), name).toBe(false);
    }
  });

  it("leaves a key with no name to the grid", () => {
    expect(key("")).toBe(false);
  });

  it("leaves a shortcut to the grid: Ctrl or Meta held", () => {
    expect(key("a", { ctrlKey: true })).toBe(false);
    expect(key("5", { metaKey: true })).toBe(false);
  });
});

describe("cellId", () => {
  it("names a cell by its row and its column", () => {
    expect(cellId(2, 3)).toBe("cell:2:3");
  });

  it("names every cell of a grid differently", () => {
    expect(cellId(1, 11)).not.toBe(cellId(11, 1));
  });
});
