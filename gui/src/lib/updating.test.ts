import { expect, test } from "vitest";
import { ANALYSING, analysed, beforeAnalysis, updatingOf } from "./updating";

test("a state holds an analysed revision from the first on, and none at 0", () => {
  expect(analysed({ revision: 0 })).toBe(false);
  expect(analysed({ revision: 1 })).toBe(true);
  expect(analysed({ revision: 12 })).toBe(true);
});

test("before the first analysis the page says the project is being analysed", () => {
  expect(ANALYSING).toBe("Analysing the project…");
  expect(beforeAnalysis(null)).toBe(ANALYSING);
});

test("but says nothing in a tab's place once that analysis failed: the banner says why", () => {
  // The next poll asks for another analysis, which may run as this is drawn: said to be under way,
  // a failure asked again at every poll read as an analysis that never ends.
  expect(beforeAnalysis("boom")).toBeNull();
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
