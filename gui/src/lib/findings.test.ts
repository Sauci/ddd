import { describe, expect, test } from "vitest";
import type { Finding, FixReply, State } from "../api/types";
import {
  distinctFindings,
  findingCounts,
  findingRows,
  fixEdit,
  keyedFindings,
  leadsElsewhere,
  namesThisVariable,
  noRouteReason,
  routeHref,
  routeLabel,
  routeOf,
} from "./findings";

const SENSOR_HUB = "C:/work/demo/components/sensor_hub.ddd.json";
const TYPES = "C:/work/demo/types.ddd.json";

function finding(fields: Partial<Finding> = {}): Finding {
  return {
    file: SENSOR_HUB,
    check: "definition-mismatch",
    severity: "error",
    message: "'ValueA' is declared differently by component 'Controller'",
    pointer: "component.interface[2].definition",
    notes: [],
    route: { kind: "variable", name: "ValueA" },
    ...fields,
  };
}

function state(findings: Finding[]): State {
  return {
    revision: 7,
    project: "C:/work/demo/demo.ddd.json",
    files: [
      {
        path: SENSOR_HUB,
        kind: "component",
        name: "SensorHub",
        loaded: true,
        fingerprint: "a",
        findings: { error: 1, warning: 0, info: 0 },
      },
      {
        path: TYPES,
        kind: "types",
        name: null,
        loaded: true,
        fingerprint: "b",
        findings: { error: 1, warning: 0, info: 0 },
      },
    ],
    findings,
    undoable: null,
  };
}

// Destructuring keyedFindings' result by position would run into noUncheckedIndexedAccess
// (its length is not known statically), so tests read the keys through map() instead.
const keysOf = (findings: Finding[]): string[] => keyedFindings(findings).map(([, key]) => key);

test("distinct findings get distinct keys", () => {
  const a = finding({ pointer: "component.interface[0].definition" });
  const b = finding({ pointer: "component.interface[1].definition" });
  const keys = keysOf([a, b]);
  expect(keys[0]).not.toBe(keys[1]);
});

test("two findings equal in all four fields get different keys", () => {
  const keys = keysOf([finding(), finding()]);
  expect(keys[0]).not.toBe(keys[1]);
});

test("a finding keeps its key when a different finding before it in the list disappears", () => {
  const other = finding({ check: "unknown-unit", message: "a different problem" });
  const kept = finding({ pointer: "component.interface[2].definition" });
  const keyWithOther = keysOf([other, kept])[1];
  const keyWithoutOther = keysOf([kept])[0];
  expect(keyWithoutOther).toBe(keyWithOther);
});

test("the two sides of one disagreement, filed on each of its files, are said once", () => {
  const consumer = finding({ file: "/p/controller.ddd.json" });
  const producer = finding({ file: "/p/sensor_hub.ddd.json" });
  expect(distinctFindings([consumer, producer])).toEqual([consumer]);
});

test("findings that differ in severity, check or message are each kept, in order", () => {
  const listed = [
    finding(),
    finding({ severity: "warning" }),
    finding({ check: "storage-mismatch" }),
    finding({ message: "'ValueA' is declared differently by component 'UserInterface'" }),
  ];
  expect(distinctFindings(listed)).toEqual(listed);
});

describe("the rows of the findings tab", () => {
  test("errors come before warnings, and warnings before information", () => {
    const rows = findingRows(
      state([
        finding({ severity: "info", check: "missing-id" }),
        finding({ severity: "error" }),
        finding({ severity: "warning", check: "storage-mismatch" }),
      ]),
    );
    expect(rows.map((row) => row.finding.severity)).toEqual(["error", "warning", "info"]);
  });

  test("within a severity the analysis's own order is kept, which groups them by file", () => {
    const rows = findingRows(
      state([
        finding({ file: TYPES, check: "duplicate-type", route: null }),
        finding({ file: SENSOR_HUB }),
      ]),
    );
    expect(rows.map((row) => row.file)).toEqual(["types.ddd.json", "sensor_hub.ddd.json"]);
  });

  test("each row has a key that tells two findings of one wording apart", () => {
    const rows = findingRows(state([finding(), finding()]));
    expect(new Set(rows.map((row) => row.key)).size).toBe(2);
  });
});

describe("what the tab says about how many there are", () => {
  test.each([
    [[], "Nothing to report"],
    [[finding()], "1 finding · 1 error"],
    [
      [finding(), finding({ severity: "warning" }), finding({ severity: "info" })],
      "3 findings · 1 error, 1 warning, 1 note",
    ],
    [[finding(), finding()], "2 findings · 2 errors"],
  ])("%#", (findings, says) => {
    expect(findingCounts(findings)).toBe(says);
  });
});

describe("where a finding leads", () => {
  test("a variable, by name", () => {
    const one = finding();
    expect(routeLabel(one, state([one]))).toBe("Open ValueA");
    expect(routeHref(one)).toBe(
      `/component?file=${encodeURIComponent(SENSOR_HUB)}&variable=ValueA`,
    );
  });

  test("a unit, by its spelling", () => {
    const one = finding({ check: "unknown-unit", route: { kind: "unit", name: "degC" } });
    expect(routeLabel(one, state([one]))).toBe("Open degC");
    expect(routeHref(one)).toBe("/project?view=units&unit=degC");
  });

  test("a type, by its name", () => {
    const one = finding({ check: "duplicate-type", route: { kind: "type", name: "Sensor_t" } });
    expect(routeLabel(one, state([one]))).toBe("Open Sensor_t");
    expect(routeHref(one)).toBe("/project?view=types&type=Sensor_t");
  });

  test("a component, by the name its file gives it", () => {
    const one = finding({ route: { kind: "component", name: null } });
    expect(routeLabel(one, state([one]))).toBe("Open SensorHub");
    expect(routeHref(one)).toBe(`/component?file=${encodeURIComponent(SENSOR_HUB)}`);
  });

  test("a component the analysis has not listed, by its own file name", () => {
    const elsewhere = finding({
      file: "C:/elsewhere.ddd.json",
      route: { kind: "component", name: null },
    });
    expect(routeLabel(elsewhere, state([elsewhere]))).toBe("Open elsewhere.ddd.json");
  });

  test("nowhere, when the answer says so", () => {
    const one = finding({ route: null });
    expect(routeLabel(one, state([one]))).toBeNull();
    expect(routeHref(one)).toBeNull();
    expect(routeOf(one)).toBeNull();
  });

  test("the route itself is what a screen navigates to", () => {
    // The address and the route are one answer in two forms: a link carries the address, and
    // the screen hands the route to the app's own navigate.
    expect(routeOf(finding())).toEqual({
      page: "component",
      file: SENSOR_HUB,
      variable: "ValueA",
    });
  });
});

describe("why a finding leads nowhere", () => {
  test("its file did not load", () => {
    const one = finding({ route: null });
    const half = state([one]);
    half.files = half.files.map((file) =>
      file.path === SENSOR_HUB ? { ...file, loaded: false } : file,
    );
    expect(noRouteReason(one, half)).toBe("sensor_hub.ddd.json did not load");
  });

  test("the page has no screen for that kind of file", () => {
    const one = finding({ file: TYPES, check: "duplicate-type", route: null });
    expect(noRouteReason(one, state([one]))).toBe(
      "types.ddd.json is a types file, which has no page yet",
    );
  });

  test("it names no place in a file", () => {
    const one = finding({ pointer: "", route: null, check: "missing-producer" });
    expect(noRouteReason(one, state([one]))).toBe(
      "it is about the project rather than a place in a file",
    );
  });

  test("the declaration it names has moved since the analysis read the file", () => {
    // The server answers no route for a pointer whose declaration the file no longer holds
    // there - `ddd.finding_routes.route_of`. The file is a loaded component all the same, so
    // the reason must not tell the reader it is a finding about the project.
    const one = finding({ route: null });
    expect(noRouteReason(one, state([one]))).toBe("there is nothing at that place any more");
  });

  test("the unit it was filed on is no longer stated there", () => {
    const one = finding({
      check: "unknown-unit",
      pointer: "component.interface[2].definition.unit",
      route: null,
    });
    expect(noRouteReason(one, state([one]))).toBe("there is nothing at that place any more");
  });

  test("its file is not one the analysis listed", () => {
    const one = finding({ file: "C:/elsewhere.ddd.json", route: null });
    expect(noRouteReason(one, state([one]))).toBe(
      "elsewhere.ddd.json is not a file of this project",
    );
  });
});

describe("whether a finding in a component's list leads elsewhere", () => {
  test("a variable route on this very file still leads somewhere - it opens that panel", () => {
    expect(leadsElsewhere(finding(), SENSOR_HUB)).toBe(true);
  });

  test("a unit route always leads elsewhere, whichever file is asking", () => {
    const one = finding({ check: "unknown-unit", route: { kind: "unit", name: "degC" } });
    expect(leadsElsewhere(one, SENSOR_HUB)).toBe(true);
  });

  test("a bare component route naming this very file is the page already open - no link", () => {
    const one = finding({ route: { kind: "component", name: null } });
    expect(leadsElsewhere(one, SENSOR_HUB)).toBe(false);
  });

  test("that same bare route still leads elsewhere from a different file's page", () => {
    const one = finding({ route: { kind: "component", name: null } });
    expect(leadsElsewhere(one, TYPES)).toBe(true);
  });

  test("nowhere to lead when the answer says so", () => {
    expect(leadsElsewhere(finding({ route: null }), SENSOR_HUB)).toBe(false);
  });
});

describe("whether a finding in a variable's panel names that very variable", () => {
  test("its route names the variable whose panel this is", () => {
    expect(namesThisVariable(finding(), "ValueA")).toBe(true);
  });

  test("its route names a different variable", () => {
    expect(namesThisVariable(finding(), "ValueB")).toBe(false);
  });

  test("its route is a bare component page, naming no variable at all", () => {
    const one = finding({ route: { kind: "component", name: null } });
    expect(namesThisVariable(one, "ValueA")).toBe(false);
  });

  test("its route is a unit, not a place on any component's page", () => {
    const one = finding({ check: "unknown-unit", route: { kind: "unit", name: "degC" } });
    expect(namesThisVariable(one, "ValueA")).toBe(false);
  });

  test("nowhere to lead when the answer says so", () => {
    expect(namesThisVariable(finding({ route: null }), "ValueA")).toBe(false);
  });
});

describe("the edit a chosen fix comes to", () => {
  const reply: FixReply = {
    revision: 7,
    fixes: [
      {
        title: "Give 'ValueA' an id",
        changes: [
          {
            file: SENSOR_HUB,
            fingerprint: "a",
            operations: [
              { op: "set", pointer: "component.interface[2].definition.id", raw: '"rbdtf7g2eey1"' },
            ],
            hunks: [],
          },
        ],
      },
    ],
  };

  test("the one it names", () => {
    const edit = fixEdit(reply, "Give 'ValueA' an id", "the identity of ValueA");
    expect(edit?.changes).toHaveLength(1);
    expect(edit?.label).toBe("the identity of ValueA");
  });

  test("nothing for a title the answer does not carry, or a fix that changes nothing", () => {
    expect(fixEdit(reply, "Give 'ValueB' an id", "the identity of ValueB")).toBeNull();
    expect(fixEdit({ revision: 7, fixes: [{ title: "t", changes: [] }] }, "t", "t")).toBeNull();
  });

  test("nothing when the one file it would touch ends up with nothing to write", () => {
    // A PlannedChange's own operations can be empty (a file listed but computed to no edit);
    // fixEdit narrows Changes' non-empty tuple by dropping such a change, same as editOf does.
    expect(
      fixEdit(
        {
          revision: 7,
          fixes: [
            { title: "t", changes: [{ file: TYPES, fingerprint: "b", operations: [], hunks: [] }] },
          ],
        },
        "t",
        "t",
      ),
    ).toBeNull();
  });
});
