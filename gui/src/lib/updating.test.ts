import { expect, test } from "vitest";
import { analysed, updatingOf } from "./updating";

test("a state holds an analysed revision from the first on, and none at 0", () => {
  expect(analysed({ revision: 0 })).toBe(false);
  expect(analysed({ revision: 1 })).toBe(true);
  expect(analysed({ revision: 12 })).toBe(true);
});

test("the findings are updating while an analysis is asked for or running", () => {
  expect(updatingOf({ revision: 3, analysing: true, edits: 4 }, 4)).toBe(true);
  expect(updatingOf({ revision: 3, analysing: true, edits: 4 }, 0)).toBe(true);
});

test("they are updating while the page's own last edit is newer than the revision holds", () => {
  // The moment between an edit's answer and the state saying it is being analysed: nothing
  // analyses yet, and the revision on screen does not include the page's own change.
  expect(updatingOf({ revision: 3, analysing: false, edits: 3 }, 4)).toBe(true);
});

test("they are current once the revision includes the page's own last edit and nothing analyses", () => {
  expect(updatingOf({ revision: 3, analysing: false, edits: 4 }, 4)).toBe(false);
  // Another window's edit, made after this page's own, included too.
  expect(updatingOf({ revision: 3, analysing: false, edits: 6 }, 4)).toBe(false);
  // A page that has written nothing.
  expect(updatingOf({ revision: 3, analysing: false, edits: 0 }, 0)).toBe(false);
});

test("nothing is updating before the first analysis: no finding is on screen to update", () => {
  // The project's first analysis runs: the heading says "Analysing the project…", and must not
  // also say the findings are updating.
  expect(updatingOf({ revision: 0, analysing: true, edits: 0 }, 0)).toBe(false);
  expect(updatingOf({ revision: 0, analysing: false, edits: 0 }, 2)).toBe(false);
});
