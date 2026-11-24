import { expect, test } from "vitest";
import type { CompareReply, Finding, State } from "../api/types";
import {
  askedIn,
  asksNothing,
  baselineOf,
  type CompareRow,
  compareLine,
  compareRouteReason,
  compareRows,
  fileNameIn,
  heldFor,
  nextAsk,
  typedIn,
  verdictLine,
} from "./compare";

function finding(fields: Partial<Finding> = {}): Finding {
  return {
    file: "C:/work/demo/demo.ddd.json",
    check: "changed-interface",
    severity: "error",
    message: "'ValueA' changed datatype from uint16 to uint32",
    pointer: "",
    line: null,
    column: null,
    notes: [],
    route: null,
    ...fields,
  };
}

function reply(fields: Partial<CompareReply> = {}): CompareReply {
  return {
    revision: 1,
    verdict: false,
    own_errors: 0,
    findings: [],
    baseline_findings: [],
    statements: { error: 0, warning: 0, info: 0 },
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
  statements: { error: 0, warning: 0, info: 0 },
  failed: null,
  refused: [],
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

test("the line counts the statements of the reply, a baseline's disagreement once over its two rows", () => {
  // Decision 14.3: the baseline's `definition-mismatch` is filed on the reader that disagrees,
  // its note naming the producer, and again on the producer - two rows of one statement, which
  // `ddd compare` prints once.
  const onTheReader = finding({
    file: "C:/elsewhere/components/controller.ddd.json",
    check: "definition-mismatch",
    message: "in the baseline: 'ValueA' is declared differently by component 'Controller'",
    pointer: "component.interface[0].definition",
    notes: [
      {
        message: "reference declaration",
        file: "C:/elsewhere/components/sensor_hub.ddd.json",
        pointer: "component.interface[0].definition",
      },
    ],
  });
  const onTheProducer = {
    ...onTheReader,
    file: "C:/elsewhere/components/sensor_hub.ddd.json",
    notes: [],
  };
  const mirrored = reply({
    baseline_findings: [onTheReader, onTheProducer],
    statements: { error: 1, warning: 0, info: 0 },
  });
  expect(compareRows(mirrored)).toHaveLength(2);
  expect(compareLine(mirrored)).toBe("1 finding · 1 error");
});

test("the line says how many of each severity the comparison and the baseline make", () => {
  const counted = reply({ statements: { error: 2, warning: 1, info: 1 } });
  expect(compareLine(counted)).toBe("4 findings · 2 errors, 1 warning, 1 info");
  expect(compareLine(reply())).toBe("Nothing to report");
});

test("a baseline's file is named as the baseline's, wherever a comparison names it", () => {
  // The panel names a finding's file, and each file its notes point at, with this: the baseline's
  // own sensor_hub.ddd.json is not the open project's, whose display name it shares.
  const path = "C:/elsewhere/components/sensor_hub.ddd.json";
  expect(fileNameIn(true)(path)).toBe("the baseline's sensor_hub.ddd.json");
});

test("a file of the open project is named plainly, by its base name", () => {
  expect(fileNameIn(false)("C:/work/demo/components/sensor_hub.ddd.json")).toBe(
    "sensor_hub.ddd.json",
  );
});

test("the first ask is numbered one, its baseline trimmed of the spaces round it", () => {
  expect(nextAsk(null, "  baseline.json ")).toEqual({ baseline: "baseline.json", number: 1 });
});

test("a baseline asked for again is a new ask, so that it is sent again", () => {
  const first = nextAsk(null, "baseline.json");
  const again = nextAsk(first, "baseline.json");
  expect(again.baseline).toBe(first.baseline);
  expect(again).not.toEqual(first);
});

test("a baseline typed with spaces round it is the baseline already asked for", () => {
  const first = nextAsk(null, "baseline.json");
  expect(nextAsk(first, "  baseline.json  ").baseline).toBe(first.baseline);
});

test("no ask repeats an earlier one, even when its baseline comes back", () => {
  const first = nextAsk(null, "a.json");
  const second = nextAsk(first, "b.json");
  const third = nextAsk(second, "a.json");
  expect(third.baseline).toBe(first.baseline);
  expect(new Set([first.number, second.number, third.number]).size).toBe(3);
});

test("a baseline pasted in a pair of like quotes is asked for as the path between them", () => {
  // Windows' Copy as path writes double quotes round a path, a shell's quoting single ones; the
  // server takes them off as well (16:M3), and the verdict names what was asked (16:M2).
  expect(baselineOf('"C:\\work\\demo\\baseline.json"')).toBe("C:\\work\\demo\\baseline.json");
  expect(baselineOf("'baseline.json'")).toBe("baseline.json");
  expect(baselineOf('  "baseline.json"  ')).toBe("baseline.json");
  expect(nextAsk(null, '"baseline.json"').baseline).toBe("baseline.json");
});

test("a quote alone, or two unlike, are the path's own characters", () => {
  expect(baselineOf('"baseline.json')).toBe('"baseline.json');
  expect(baselineOf("baseline.json'")).toBe("baseline.json'");
  expect(baselineOf("\"baseline.json'")).toBe("\"baseline.json'");
  expect(baselineOf('"')).toBe('"');
});

test("nothing but spaces, or quotes round nothing, ask for nothing", () => {
  expect(asksNothing("   ")).toBe(true);
  expect(asksNothing(' "" ')).toBe(true);
  expect(asksNothing("''")).toBe(true);
  expect(asksNothing('"')).toBe(false);
  expect(asksNothing("baseline.json")).toBe(false);
});

test("the verdict names the baseline it was asked for", () => {
  expect(verdictLine(true, "baseline.json")).toBe(
    "This project can replace the baseline 'baseline.json'.",
  );
  expect(verdictLine(false, "C:/work/demo/deliveries/released/demo.ddd.json")).toBe(
    "This project cannot replace the baseline 'C:/work/demo/deliveries/released/demo.ddd.json'.",
  );
});

test("the tab holds nothing typed and nothing asked for a project it held nothing of", () => {
  expect(heldFor(null, "C:/work/demo/demo.ddd.json")).toEqual({
    project: "C:/work/demo/demo.ddd.json",
    typed: "",
    asked: null,
  });
});

test("what the tab holds is kept for its project, and another project starts with nothing", () => {
  const demo = askedIn(typedIn(heldFor(null, "C:/work/demo/demo.ddd.json"), "baseline.json"));
  expect(heldFor(demo, "C:/work/demo/demo.ddd.json")).toBe(demo);
  expect(heldFor(demo, "C:/work/second/second.ddd.json")).toEqual({
    project: "C:/work/second/second.ddd.json",
    typed: "",
    asked: null,
  });
});

test("typing is held without asking, and asking asks for what the field holds", () => {
  const typed = typedIn(heldFor(null, "C:/work/demo/demo.ddd.json"), " baseline.json ");
  expect(typed.typed).toBe(" baseline.json ");
  expect(typed.asked).toBeNull();
  const asked = askedIn(typed);
  expect(asked.asked).toEqual({ baseline: "baseline.json", number: 1 });
  expect(asked.typed).toBe(" baseline.json ");
  // Typed again and not asked: the ask held is still the one before, which the verdict names.
  const retyped = typedIn(asked, "other.json");
  expect(retyped.asked).toBe(asked.asked);
  expect(askedIn(retyped).asked).toEqual({ baseline: "other.json", number: 2 });
});
