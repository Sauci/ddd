import { describe, expect, test } from "vitest";
import type { PlanReply, SharedReply } from "../api/types";
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

describe("the tab's summary line", () => {
  test("names how many constants the project declares", () => {
    expect(tabTitle(reply(["A", "B"]).entries)).toBe("2 constants");
  });

  test("says one constant in the singular", () => {
    expect(tabTitle(reply(["A"]).entries)).toBe("1 constant");
  });

  test("says a project with none declares none, rather than showing a zero", () => {
    expect(tabTitle([])).toBe("This project declares no constants.");
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
