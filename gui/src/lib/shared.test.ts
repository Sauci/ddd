import { describe, expect, test } from "vitest";
import type { PlanReply, SharedEntry, SharedReply } from "../api/types";
import { isDeclared, planEdit, tabTitle } from "./shared";

const reply = (names: string[]): SharedReply => ({
  revision: 1,
  entries: names.map((name) => ({
    kind: "constant",
    name,
    states: "16",
    uses: 0,
    findings: 0,
  })),
});

/** A `SharedEntry` per kind word, named `N0`, `N1`, ... so a row is never mistaken for another of
 * the same kind - `tabTitle` counts by `kind` alone, and the name only has to keep entries apart. */
function entries(kinds: string[]): SharedEntry[] {
  return kinds.map((kind, index) => ({
    kind,
    name: `N${index}`,
    states: "x",
    uses: 0,
    findings: 0,
  }));
}

describe("the tab's summary line", () => {
  test("names each vocabulary that has entries", () => {
    expect(tabTitle(entries(["constant", "constant", "section"]))).toBe("2 constants · 1 section");
  });

  test("says one of a kind in the singular", () => {
    // Part 13 shipped a plural no assertion could tell from the wrong one, because "1 shape" is a
    // substring of "1 shapes". `toBe` on the whole line is what catches a mutation that always
    // pluralises.
    expect(tabTitle(entries(["constant"]))).toBe("1 constant");
  });

  test("names only the kinds that have any", () => {
    expect(tabTitle(entries(["section", "section"]))).toBe("2 sections");
  });

  test("says a project with none declares none", () => {
    expect(tabTitle([])).toBe("This project declares nothing in its shared files.");
  });
});

describe("whether a name is declared", () => {
  test("a name the table holds is declared", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "constant", "TREND_SAMPLES")).toBe(true);
  });

  test("a name it does not hold is not - which is what opens the add form", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "constant", "CELLS")).toBe(false);
  });

  test("a name of another kind is not, however it is spelled", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "section", "TREND_SAMPLES")).toBe(false);
  });
});

describe("a plan's changes, ready to send", () => {
  const PLAN: PlanReply = {
    revision: 3,
    changes: [
      {
        file: "C:/w/constants.ddd.json",
        fingerprint: "a",
        operations: [{ op: "set", pointer: "constants[0].value", raw: "8" }],
        hunks: [{ line: 4, before: ['    "value": "16"'], after: ['    "value": "8"'] }],
      },
    ],
  };

  test("delegates to the units tab's converter - a plan is a plan whichever route previewed it", () => {
    expect(planEdit(PLAN, "the value of CELLS")).toEqual({
      changes: [
        {
          file: "C:/w/constants.ddd.json",
          fingerprint: "a",
          operations: [{ op: "set", pointer: "constants[0].value", raw: "8" }],
        },
      ],
      label: "the value of CELLS",
    });
  });

  test("a plan with nothing to change comes to no edit", () => {
    expect(planEdit({ revision: 3, changes: [] }, "the value of CELLS")).toBeNull();
  });
});
