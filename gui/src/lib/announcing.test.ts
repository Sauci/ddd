import { describe, expect, test } from "vitest";
import type { SourceFile } from "../api/types";
import {
  PROJECT_VIEWS,
  pageTitle,
  putBackOf,
  VIEW_NAMES,
  writtenSentence,
  writtenSince,
} from "./announcing";

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

describe("what the heading says the page last wrote", () => {
  const at = (name: string) => `/work/demo/components/${name}`;

  test("an edit written, by its label, with how many files and which", () => {
    expect(
      writtenSentence({
        kind: "wrote",
        label: "the unit of ValueA",
        files: [at("controller.ddd.json"), at("sensor_hub.ddd.json")],
      }),
    ).toBe("Wrote 2 files for the unit of ValueA: controller.ddd.json, sensor_hub.ddd.json.");
    expect(
      writtenSentence({
        kind: "wrote",
        label: "removing ValueA from SensorHub",
        files: [at("sensor_hub.ddd.json")],
      }),
    ).toBe("Wrote 1 file for removing ValueA from SensorHub: sensor_hub.ddd.json.");
  });

  test("an undo, by the label of the edit it put back", () => {
    expect(
      writtenSentence({
        kind: "put back",
        label: "the unit of ValueA",
        files: [at("controller.ddd.json")],
      }),
    ).toBe("Undid the unit of ValueA, putting back 1 file: controller.ddd.json.");
  });

  test("four files named, past four three of them and how many more", () => {
    const files = (count: number) =>
      Array.from({ length: count }, (_, index) => at(`c${index}.ddd.json`));
    expect(
      writtenSentence({ kind: "wrote", label: "the rename of 'RPM' to 'rpm'", files: files(4) }),
    ).toBe(
      "Wrote 4 files for the rename of 'RPM' to 'rpm': c0.ddd.json, c1.ddd.json, c2.ddd.json, c3.ddd.json.",
    );
    expect(
      writtenSentence({
        kind: "put back",
        label: "the rename of 'RPM' to 'rpm'",
        files: files(1200),
      }),
    ).toBe(
      "Undid the rename of 'RPM' to 'rpm', putting back 1200 files: c0.ddd.json, c1.ddd.json, c2.ddd.json and 1197 more.",
    );
  });

  test("two files of one name by as much of their paths as tells them apart", () => {
    expect(
      writtenSentence({
        kind: "wrote",
        label: "the unit of Speed",
        files: ["/work/p/front/pump.ddd.json", "/work/p/rear/pump.ddd.json"],
      }),
    ).toBe("Wrote 2 files for the unit of Speed: front/pump.ddd.json, rear/pump.ddd.json.");
  });

  test("no file, where none was named", () => {
    expect(writtenSentence({ kind: "wrote", label: "the unit of ValueA", files: [] })).toBe(
      "Wrote 0 files for the unit of ValueA.",
    );
  });

  test("a write made since the page was drawn, and none before it", () => {
    const write = {
      kind: "wrote",
      label: "the unit of ValueA",
      files: [at("a.ddd.json")],
    } as const;
    expect(writtenSince({ edit: 4, write }, 3)).toEqual({
      edit: 4,
      sentence: "Wrote 1 file for the unit of ValueA: a.ddd.json.",
    });
    expect(writtenSince({ edit: 4, write }, 4)).toBeNull();
    expect(writtenSince(null, 0)).toBeNull();
  });

  test("an undo's preview, as what it put back", () => {
    expect(
      putBackOf({
        revision: 3,
        at: 2,
        label: "the unit of ValueA",
        changes: [
          { file: at("controller.ddd.json"), gone: false, hunks: [] },
          { file: at("sensor_hub.ddd.json"), gone: false, hunks: [] },
        ],
      }),
    ).toEqual({
      kind: "put back",
      label: "the unit of ValueA",
      files: [at("controller.ddd.json"), at("sensor_hub.ddd.json")],
    });
  });
});
