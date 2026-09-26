import { expect, test } from "vitest";
import type { CompareReply, Finding } from "../api/types";
import { compareRouteReason, compareRows } from "./compare";

function finding(fields: Partial<Finding> = {}): Finding {
  return {
    file: "C:/work/demo/demo.ddd.json",
    check: "changed-interface",
    severity: "error",
    message: "'ValueA' changed datatype from uint16 to uint32",
    pointer: "",
    notes: [],
    route: null,
    ...fields,
  };
}

function reply(fields: Partial<CompareReply> = {}): CompareReply {
  return {
    revision: 1,
    verdict: false,
    findings: [],
    baseline_findings: [],
    renames: [],
    ...fields,
  };
}

test.each([
  [false, "it is about the whole delivery being compared, not a place in one file"],
  [true, "it is the baseline's own finding, not a place in your project"],
] as const)("compareRouteReason(%o) is %o", (fromBaseline, text) => {
  expect(compareRouteReason(fromBaseline)).toBe(text);
});

test("rows from both fields are merged, worst severity first, each naming its own side", () => {
  const ownWarning = finding({ severity: "warning", check: "removed-object", message: "gone" });
  const ownError = finding({
    file: "C:/work/demo/demo.ddd.json",
    severity: "error",
    check: "changed-interface",
  });
  // Same file this project's own components/sensor_hub.ddd.json would display as - the exact
  // collision a project-description baseline with an error of its own produces (comparing a
  // project against itself is legal), which is what the File column must not read as the
  // reader's own file.
  const baselineError = finding({
    file: "C:/elsewhere/components/sensor_hub.ddd.json",
    severity: "error",
    check: "duplicate-id",
    message: "in the baseline: 'ValueC' carries the id 'x', which 'ValueB' already carries",
  });
  const rows = compareRows(
    reply({ findings: [ownWarning, ownError], baseline_findings: [baselineError] }),
  );
  expect(rows.map((row) => row.finding.severity)).toEqual(["error", "error", "warning"]);
  expect(rows.map((row) => row.fromBaseline)).toEqual([false, true, false]);
  expect(rows.map((row) => row.file)).toEqual([
    "demo.ddd.json",
    "the baseline's sensor_hub.ddd.json",
    "demo.ddd.json",
  ]);
  // Two rows, each with a key of its own, even though nothing here forces that: `keyedFindings`
  // is trusted with it, not re-proven here.
  expect(new Set(rows.map((row) => row.key)).size).toBe(3);
});

test("an empty reply has no rows", () => {
  expect(compareRows(reply())).toEqual([]);
});
