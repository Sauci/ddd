import { describe, expect, test } from "vitest";
import type { ConstantUse } from "../api/types";
import { constantRemoveBlocked, placesNaming } from "./constantUses";

const use = (fields: Partial<ConstantUse>): ConstantUse => ({
  path: "C:/work/demo/components/controller.ddd.json",
  pointer: "component.interface[0].definition.dimensions[0]",
  kind: "variable",
  name: "ValueA",
  component: "Controller",
  ...fields,
});

describe("the places that name a constant", () => {
  test("a declaration spelling the constant twice is one place, its first spelling standing", () => {
    // A dimension and a condition of one declaration: two uses of the server's, one row.
    const dimension = use({});
    const condition = use({ pointer: "component.interface[0].condition" });
    expect(placesNaming([dimension, condition])).toEqual([dimension]);
  });

  test("declarations of one name in two files, and a member beside them, are places apart", () => {
    const places = [
      use({}),
      use({ path: "C:/work/demo/components/sensor_hub.ddd.json", component: "SensorHub" }),
      use({ kind: "member", name: "Sample_t.history", component: null }),
      use({ name: "ValueB" }),
    ];
    expect(placesNaming(places)).toEqual(places);
    expect(placesNaming([])).toEqual([]);
  });
});

describe("why a constant cannot be removed", () => {
  test("counts the places naming it", () => {
    expect(constantRemoveBlocked("CELLS", 2)).toBe("2 places name CELLS, so it cannot be removed.");
  });

  test("says one of them in the singular, verb and all", () => {
    expect(constantRemoveBlocked("CELLS", 1)).toBe("1 place names CELLS, so it cannot be removed.");
  });
});
