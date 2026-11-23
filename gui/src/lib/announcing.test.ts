import { describe, expect, test } from "vitest";
import type { SourceFile } from "../api/types";
import { PROJECT_VIEWS, pageTitle, VIEW_NAMES } from "./announcing";

const file = (path: string, name: string | null): SourceFile => ({
  path,
  kind: "component",
  name,
  loaded: true,
  fingerprint: "0",
  findings: { error: 0, warning: 0, info: 0 },
});

const CONTROLLER = file("/work/demo/components/controller.ddd.json", "Controller");
const BROKEN = file("/work/demo/components/broken.ddd.json", null);
const FILES = [CONTROLLER, BROKEN];

describe("the title a page is named by", () => {
  test("a tab's name, then the project's and the tool's", () => {
    const page = { drawn: true, project: "DemoDevice", files: FILES };
    expect(pageTitle({ ...page, route: { page: "project", view: "graph" } })).toBe(
      "Graph · DemoDevice · ddd gui",
    );
    expect(pageTitle({ ...page, route: { page: "project", view: "shared" } })).toBe(
      "Shared files · DemoDevice · ddd gui",
    );
    // What a tab selects is no page of its own.
    expect(pageTitle({ ...page, route: { page: "project", view: "units", unit: "rpm" } })).toBe(
      "Units · DemoDevice · ddd gui",
    );
  });

  test("a component's page by its component, its values by the variable and the component", () => {
    const page = { drawn: true, project: "DemoDevice", files: FILES };
    const route = { page: "component", file: CONTROLLER.path } as const;
    expect(pageTitle({ ...page, route })).toBe("Controller · DemoDevice · ddd gui");
    expect(pageTitle({ ...page, route: { ...route, variable: "ValueA" } })).toBe(
      "Controller · DemoDevice · ddd gui",
    );
    expect(pageTitle({ ...page, route: { ...route, variable: "MapA", view: "values" } })).toBe(
      "MapA · Controller · DemoDevice · ddd gui",
    );
  });

  test("a component by its file's name where its name is not known", () => {
    const page = { drawn: true, project: "DemoDevice" };
    expect(
      pageTitle({ ...page, files: FILES, route: { page: "component", file: BROKEN.path } }),
    ).toBe("broken.ddd.json · DemoDevice · ddd gui");
    // Before the project's first analysis there is no state, and no file of it.
    expect(
      pageTitle({ ...page, files: [], route: { page: "component", file: CONTROLLER.path } }),
    ).toBe("controller.ddd.json · DemoDevice · ddd gui");
  });

  test("the start page, asked for or drawn where no project is open", () => {
    expect(
      pageTitle({ drawn: true, project: "DemoDevice", files: [], route: { page: "start" } }),
    ).toBe("Open a project · ddd gui");
    expect(
      pageTitle({
        drawn: true,
        project: null,
        files: [],
        route: { page: "project", view: "graph" },
      }),
    ).toBe("Open a project · ddd gui");
  });

  test("the tool alone before a page is drawn", () => {
    expect(
      pageTitle({ drawn: false, project: "DemoDevice", files: FILES, route: { page: "start" } }),
    ).toBe("ddd gui");
  });

  test("every tab of the project screen, in its order, by the name it is shown under", () => {
    expect(PROJECT_VIEWS.map((view) => VIEW_NAMES[view])).toEqual([
      "Graph",
      "Table",
      "Units",
      "Types",
      "Shared files",
      "Files",
      "Findings",
      "Compare",
    ]);
  });
});
