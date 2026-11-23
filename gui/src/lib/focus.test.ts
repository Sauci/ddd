import { describe, expect, test } from "vitest";
import { opensAnew, pageChanged, pageOf, returnPlace } from "./focus";
import type { Route } from "./route";

describe("whether a following changes the page", () => {
  const graph: Route = { page: "project", view: "graph" };
  const controller: Route = { page: "component", file: "/p/controller.ddd.json" };

  test("from one page to another: the start page, a tab, a component's page, its values", () => {
    expect(pageChanged({ page: "start" }, graph)).toBe(true);
    expect(pageChanged(graph, { page: "project", view: "units" })).toBe(true);
    expect(pageChanged({ page: "project", view: "table" }, controller)).toBe(true);
    expect(pageChanged(controller, { page: "component", file: "/p/sensor_hub.ddd.json" })).toBe(
      true,
    );
    const values: Route = { ...controller, variable: "MapA", view: "values" };
    expect(pageChanged({ ...controller, variable: "MapA" }, values)).toBe(true);
    expect(pageChanged(values, { ...values, variable: "CurveA" })).toBe(true);
    expect(pageChanged(values, { ...values, file: "/p/user_interface.ddd.json" })).toBe(true);
  });

  test("not what a page selects in it, nor the page drawn again", () => {
    expect(pageChanged(graph, { ...graph, variable: "ValueA" })).toBe(false);
    expect(pageChanged(controller, { ...controller, variable: "ValueB" })).toBe(false);
    expect(
      pageChanged(
        { page: "project", view: "units" },
        { page: "project", view: "units", unit: "rpm" },
      ),
    ).toBe(false);
    expect(
      pageChanged(
        { page: "project", view: "findings", text: "a" },
        { page: "project", view: "findings" },
      ),
    ).toBe(false);
    expect(pageChanged({ page: "start" }, { page: "start" })).toBe(false);
  });

  test("names each page apart, a file and a variable being told apart where their names run on", () => {
    const values = (file: string, variable: string): Route => ({
      page: "component",
      file,
      variable,
      view: "values",
    });
    expect(pageOf(values("a b", "c"))).not.toBe(pageOf(values("a", "b c")));
    expect(pageOf({ page: "component", file: "/p/x" })).not.toBe(pageOf(values("/p/x", "")));
  });
});

describe("whether a panel drawn takes the control holding the focus as its opener", () => {
  test("the first panel of its slot, drawn from a control of the page", () => {
    expect(opensAnew(null, "ValueA", true)).toBe(true);
  });

  test("another panel, drawn from a control in place of the one before", () => {
    expect(opensAnew("ValueA", "ValueB", true)).toBe(true);
  });

  test("not the same panel drawn again, whatever holds the focus by then", () => {
    expect(opensAnew("ValueA", "ValueA", true)).toBe(false);
  });

  test("not one drawn from no control of the page: the slot keeps the one before's", () => {
    expect(opensAnew("SensorHub to Controller", "ValueB", false)).toBe(false);
    expect(opensAnew(null, "ValueA", false)).toBe(false);
  });
});

describe("where the focus goes back to as a panel closes", () => {
  test("the control the panel was opened from, while it is still in the page", () => {
    expect(returnPlace({ opener: true, row: true, table: true })).toBe("opener");
    expect(returnPlace({ opener: true, row: false, table: false })).toBe("opener");
  });

  test("else the row its table selects for it, where that is drawn", () => {
    expect(returnPlace({ opener: false, row: true, table: true })).toBe("row");
  });

  test("else its table, which gives the focus to the row it remembers", () => {
    expect(returnPlace({ opener: false, row: false, table: true })).toBe("table");
  });

  test("and the page's heading where no table is drawn beside it", () => {
    expect(returnPlace({ opener: false, row: false, table: false })).toBe("heading");
  });
});
