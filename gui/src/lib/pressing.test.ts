import { expect, test } from "vitest";
import { selectsText } from "./pressing";

test("a press that began a selection and ends holding text of its row selected that text", () => {
  // A path dragged over: the press went down on the text, and ends with it selected (16:M21).
  expect(selectsText({ began: true, selected: true })).toBe(true);
});

test("a click is the row's own: the selection it began holds no text", () => {
  // Pressed on a cell's words and let go where it went down: the caret it leaves holds nothing.
  expect(selectsText({ began: true, selected: false })).toBe(false);
});

test("a press that began no selection is the row's own, whatever text was selected before it", () => {
  // A button of the row pressed - the Table tab's Name - while the reader's earlier selection of
  // the row's path still stands: a button's words begin no selection.
  expect(selectsText({ began: false, selected: true })).toBe(false);
  expect(selectsText({ began: false, selected: false })).toBe(false);
});
