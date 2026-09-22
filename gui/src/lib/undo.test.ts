import { describe, expect, it } from "vitest";
import type { Finding } from "../api/types";
import { fixLabel, settleLabel, unitLabel } from "./undo";

const MISSING_ID: Finding = {
  file: "C:/work/demo/components/sensor_hub.ddd.json",
  check: "missing-id",
  severity: "info",
  message: "SensorHub produces ValueA without an id",
  pointer: "component.interface[0].definition",
  notes: [],
  route: { kind: "variable", name: "ValueA" },
};

describe("what an edit is called", () => {
  it("names the key and the variable a settlement is of", () => {
    expect(settleLabel("ValueA", "unit")).toBe("the unit of ValueA");
    expect(settleLabel("ValueB", "limits")).toBe("the limits of ValueB");
  });

  it("names each change of the project's units", () => {
    expect(unitLabel({ action: "rename", unit: "rpm", to: "RPM" })).toBe(
      "the rename of 'rpm' to 'RPM'",
    );
    expect(unitLabel({ action: "describe", unit: "rpm", description: "turns" })).toBe(
      "the description of 'rpm'",
    );
    expect(unitLabel({ action: "add", unit: "rpm" })).toBe("'rpm' added to the vocabulary");
    expect(unitLabel({ action: "remove", unit: "rpm" })).toBe("'rpm' removed from the vocabulary");
    expect(unitLabel({ action: "adopt" })).toBe("the vocabulary adopted");
  });

  it("names the declaration an identity was given to", () => {
    expect(fixLabel(MISSING_ID, "Give 'ValueA' an id")).toBe("the identity of ValueA");
  });

  it("falls back on the fix's own title where it names no declaration", () => {
    expect(fixLabel({ ...MISSING_ID, route: null }, "Give 'ValueA' an id")).toBe(
      "Give 'ValueA' an id",
    );
    expect(fixLabel({ ...MISSING_ID, check: "unknown-unit" }, "Adopt 'rpm'")).toBe("Adopt 'rpm'");
    expect(fixLabel({ ...MISSING_ID, route: { kind: "component", name: null } }, "Open it")).toBe(
      "Open it",
    );
  });

  it("cuts a label the api would refuse for its length", () => {
    const label = settleLabel("V".repeat(200), "unit");
    expect(label).toHaveLength(120);
    expect(label.endsWith("…")).toBe(true);
  });
});
