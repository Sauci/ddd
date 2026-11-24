import { describe, expect, test } from "vitest";
import { PROJECT_VIEWS } from "./announcing";
import {
  headingAsked,
  headingTaking,
  landing,
  opensAnew,
  outOfView,
  pageChanged,
  pageOf,
  returnPlace,
  selectsPanel,
  showsAgain,
} from "./focus";
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

describe("whether a change of page opens a panel, whose heading then takes the focus", () => {
  const controller = "/p/controller.ddd.json";

  test("a route naming what its page selects in itself", () => {
    expect(selectsPanel({ page: "component", file: controller, variable: "ParameterA" })).toBe(
      true,
    );
    expect(selectsPanel({ page: "project", view: "graph", variable: "ValueA" })).toBe(true);
    expect(selectsPanel({ page: "project", view: "units", unit: "rpm" })).toBe(true);
    expect(selectsPanel({ page: "project", view: "types", type: "Speed_t" })).toBe(true);
    expect(selectsPanel({ page: "project", view: "shared", kind: "constant", name: "LIMIT" })).toBe(
      true,
    );
    expect(selectsPanel({ page: "project", view: "files", path: "/p/a.ddd.json" })).toBe(true);
  });

  test("not a page selecting nothing, a variable's values, nor a filter's text", () => {
    expect(selectsPanel({ page: "start" })).toBe(false);
    expect(selectsPanel({ page: "component", file: controller })).toBe(false);
    expect(
      selectsPanel({ page: "component", file: controller, variable: "MapA", view: "values" }),
    ).toBe(false);
    for (const view of PROJECT_VIEWS) {
      expect(selectsPanel({ page: "project", view } as Route)).toBe(false);
    }
    expect(selectsPanel({ page: "project", view: "findings", text: "rpm" })).toBe(false);
  });
});

describe("which heading the page asks to take the focus as its route moves on", () => {
  const controller = "/p/controller.ddd.json";
  const page: Route = { page: "component", file: controller };
  const parameter: Route = { ...page, variable: "ParameterA" };
  const shown = (route: Route, followings: number) => ({ route, followings });

  test("a change of page: its page's heading, or the panel's its address opens", () => {
    expect(headingAsked(shown({ page: "project", view: "table" }, 1), shown(page, 2))).toBe("page");
    expect(headingAsked(shown({ page: "project", view: "graph" }, 1), shown(parameter, 2))).toBe(
      "panel",
    );
  });

  test("a following on the page it was on, to an address naming a selection: that panel's", () => {
    // The masthead's go-to used on the component's page it opens on, with no panel open, with
    // another open, or with that very one open; Forward back to it.
    expect(headingAsked(shown(page, 1), shown(parameter, 2))).toBe("panel");
    expect(headingAsked(shown({ ...page, variable: "ValueA" }, 1), shown(parameter, 2))).toBe(
      "panel",
    );
    expect(headingAsked(shown(parameter, 1), shown(parameter, 2))).toBe("panel");
  });

  test("none for a selection made in the page, nor for a following that opens no panel", () => {
    // A row selected, or a filter's text typed, replaces the address: no following.
    expect(headingAsked(shown(page, 1), shown(parameter, 1))).toBeNull();
    expect(
      headingAsked(
        shown({ page: "project", view: "findings" }, 1),
        shown({ page: "project", view: "findings", text: "rpm" }, 1),
      ),
    ).toBeNull();
    // Back to the page with no panel, or a link followed to the page already shown.
    expect(headingAsked(shown(parameter, 1), shown(page, 2))).toBeNull();
    expect(
      headingAsked(
        shown({ page: "project", view: "findings", text: "a" }, 1),
        shown({ page: "project", view: "findings", text: "b" }, 2),
      ),
    ).toBeNull();
  });
});

describe("which heading takes the focus a change of page asked for", () => {
  test("the heading of the panel the change opens, once that panel is drawn", () => {
    expect(headingTaking("panel", { page: true, panel: true })).toEqual({
      takes: "panel",
      waits: false,
    });
    expect(headingTaking("panel", { page: false, panel: true })).toEqual({
      takes: "panel",
      waits: false,
    });
  });

  test("the page's heading meanwhile, the change still waiting for its panel", () => {
    expect(headingTaking("panel", { page: true, panel: false })).toEqual({
      takes: "page",
      waits: true,
    });
  });

  test("the page's heading on a change opening no panel, whatever panel is drawn", () => {
    expect(headingTaking("page", { page: true, panel: false })).toEqual({
      takes: "page",
      waits: false,
    });
    expect(headingTaking("page", { page: true, panel: true })).toEqual({
      takes: "page",
      waits: false,
    });
  });

  test("none while the heading it waits for is not drawn", () => {
    expect(headingTaking("page", { page: false, panel: true })).toEqual({
      takes: null,
      waits: true,
    });
    expect(headingTaking("panel", { page: false, panel: false })).toEqual({
      takes: null,
      waits: true,
    });
  });
});

describe("whether a panel scrolled into view is scrolled to its top once more", () => {
  test("the window where the scroll left it, the panel's top still below the window's", () => {
    // 800 by 600, ValueB's panel read: its top at 520, the window scrolled to 165 and left there.
    expect(showsAgain(165, 165, 520)).toBe(true);
  });

  test("not once the reader has scrolled, nor where the panel's top is shown", () => {
    expect(showsAgain(165, 300, 520)).toBe(false);
    expect(showsAgain(165, 165, 0)).toBe(false);
    expect(showsAgain(165, 165, -40)).toBe(false);
  });
});

describe("whether a panel opened stands out of view", () => {
  test("its heading past the window's foot, or above its top", () => {
    // 800 by 600, a row selected: the panel's top at 608, under the table.
    expect(outOfView({ top: 608, bottom: 632 }, 600)).toBe(true);
    expect(outOfView({ top: 590, bottom: 614 }, 600)).toBe(true);
    expect(outOfView({ top: -20, bottom: 4 }, 600)).toBe(true);
  });

  test("not where its heading stands whole in the window", () => {
    expect(outOfView({ top: 0, bottom: 24 }, 600)).toBe(false);
    expect(outOfView({ top: 576, bottom: 600 }, 600)).toBe(false);
  });
});

describe("where the focus goes that a control took with it", () => {
  test("nowhere where the reader moved it on", () => {
    expect(landing({ taken: false, table: true, panel: "drawn" })).toBe("none");
    expect(landing({ taken: false, table: false, panel: "none" })).toBe("none");
  });

  test("to the table it stood in, still drawn", () => {
    expect(landing({ taken: true, table: true, panel: "none" })).toBe("table");
    expect(landing({ taken: true, table: true, panel: "drawn" })).toBe("table");
  });

  test("to its panel's heading, the panel still drawn or drawn anew", () => {
    expect(landing({ taken: true, table: false, panel: "drawn" })).toBe("panel");
    expect(landing({ taken: true, table: false, panel: "replaced" })).toBe("panel");
  });

  test("back to where its panel was opened from, the panel closed", () => {
    expect(landing({ taken: true, table: false, panel: "closed" })).toBe("return");
  });

  test("to the page's heading, in no table and no panel", () => {
    expect(landing({ taken: true, table: false, panel: "none" })).toBe("page");
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
