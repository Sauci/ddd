import { expect, test } from "vitest";
import type { CompareReply, Finding, State } from "../api/types";
import { type CompareRow, compareRouteReason, compareRows } from "./compare";

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

function row(fields: Partial<CompareRow> = {}): CompareRow {
  return { finding: finding(), key: "k", file: "demo.ddd.json", fromBaseline: false, ...fields };
}

/** The Findings tab's own fixture: the open project as the session published it. */
const STATE: State = {
  revision: 7,
  version: 14,
  project: "C:/work/demo/demo.ddd.json",
  files: [
    {
      path: "C:/work/demo/components/sensor_hub.ddd.json",
      kind: "component",
      name: "SensorHub",
      loaded: true,
      fingerprint: "a",
      findings: { error: 0, warning: 0, info: 0 },
    },
  ],
  counts: { error: 0, warning: 0, info: 0 },
  undoable: null,
  analysing: false,
  edits: 0,
};

test("a baseline's own finding is answered before the state is ever asked", () => {
  // The case `noRouteReason` cannot answer: the baseline's file is, path for path, a live and
  // loaded component of the open project, with a pointer naming a declaration that is really
  // there. Asked of it, `noRouteReason` would say "there is nothing at that place any more".
  const baseline = row({
    fromBaseline: true,
    finding: finding({
      file: "C:/work/demo/components/sensor_hub.ddd.json",
      pointer: "component.interface[2].definition.id",
    }),
  });
  expect(compareRouteReason(baseline, STATE)).toBe(
    "it is the baseline's own finding, not a place in your project",
  );
});

test("a finding filed at no place in particular is about the whole delivery", () => {
  expect(compareRouteReason(row(), STATE)).toBe(
    "it is about the whole delivery being compared, not a place in one file",
  );
});

test("a comparison finding that names a place is answered about that place", () => {
  // A plugin's comparison rule files at the declaration it is about; when it no longer routes,
  // the open project's own file is what the reason is about, so `noRouteReason` answers it.
  const named = row({
    finding: finding({
      check: "layout/key-changed",
      file: "C:/work/demo/components/pump.ddd.json",
      pointer: "component.interface[0]",
    }),
  });
  expect(compareRouteReason(named, STATE)).toBe("pump.ddd.json is not a file of this project");
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
