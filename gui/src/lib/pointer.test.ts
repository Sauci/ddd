import { describe, expect, test } from "vitest";
import { pointerOf, segments, valueAt, within } from "./pointer";

describe("pointers, spelled the way ddd reports them", () => {
  test.each([
    ["a.b[2].c", ["a", "b", 2, "c"]],
    ["component.interface[10].definition", ["component", "interface", 10, "definition"]],
    ["[0]", [0]],
    ["", []],
  ])("%s has the segments ddd.lsp.ranges.segments gives it", (pointer, parts) => {
    expect(segments(pointer)).toEqual(parts);
    expect(pointerOf(parts)).toBe(pointer);
  });

  test("a value is read at a pointer, and undefined where nothing is written", () => {
    const data = { component: { interface: [{ definition: { unit: "rpm" } }] } };
    expect(valueAt(data, "component.interface[0].definition.unit")).toBe("rpm");
    expect(valueAt(data, "")).toBe(data);
    expect(valueAt(data, "component.interface[1].definition")).toBeUndefined();
    expect(valueAt(data, "component[0]")).toBeUndefined();
    expect(valueAt(data, "component.interface.name")).toBeUndefined();
    expect(valueAt(data, "component.toString")).toBeUndefined();
    expect(valueAt(null, "a")).toBeUndefined();
  });

  test("a finding belongs to the entry it is at or inside", () => {
    expect(within("component.interface[0].definition", "component.interface[0]")).toBe(true);
    expect(within("component.interface[0]", "component.interface[0]")).toBe(true);
    expect(within("component.interface[0][1]", "component.interface[0]")).toBe(true);
    expect(within("component.interface[01]", "component.interface[0]")).toBe(false);
    expect(within("component.interface[10]", "component.interface[1]")).toBe(false);
  });
});
