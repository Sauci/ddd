import { expect, test } from "vitest";
import type { Finding } from "../api/types";
import { compareRouteReason } from "./compare";

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

test("an ordinary comparison finding is about the whole delivery, not a place in a file", () => {
  expect(compareRouteReason(finding())).toBe(
    "it is about the whole delivery being compared, not a place in one file",
  );
});

test("a finding forwarded from the baseline is the baseline's own, wherever its file resolves", () => {
  // Same file as a live, loaded component of the open project (self-comparison, spec §3) and a
  // real pointer into it: exactly the shape that used to route by asking the open project's own
  // state, and exactly the shape this must not do that for.
  const baseline = finding({
    file: "C:/work/demo/components/sensor_hub.ddd.json",
    check: "multiple-producers",
    pointer: "component.interface[2].definition",
    message: "in the baseline: 'Speed' is written by component 'B' and by component 'A'",
  });
  expect(compareRouteReason(baseline)).toBe(
    "it is the baseline's own finding, not a place in your project",
  );
});
