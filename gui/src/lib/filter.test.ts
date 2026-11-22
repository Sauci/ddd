import { describe, expect, test } from "vitest";
import type { SourceFile, UnitPlace } from "../api/types";
import {
  COMPONENTS,
  componentsShown,
  DECLARATIONS,
  declarationsShown,
  FINDINGS,
  filterLine,
  filterText,
  PLACES,
  placesShown,
  tableDrawn,
} from "./filter";

const PROJECT = "/work/demo/demo.ddd.json";

const file = (path: string, name: string | null): SourceFile => ({
  path,
  kind: "component",
  name,
  loaded: true,
  fingerprint: "0",
  findings: { error: 0, warning: 0, info: 0 },
});

const CONTROLLER = file("/work/demo/components/controller.ddd.json", "Controller");
const SENSOR_HUB = file("/work/demo/components/sensor_hub.ddd.json", "SensorHub");
const LOGGER = file("/work/demo/subsystems/logging/event_logger.ddd.json", "EventLogger");
const UNNAMED = file("/work/demo/components/broken.ddd.json", null);
const FILES = [CONTROLLER, SENSOR_HUB, LOGGER, UNNAMED];

const place = (name: string, path: string): UnitPlace => ({
  path,
  pointer: "component.interface[0].definition.unit",
  kind: "variable",
  name,
  component: "Controller",
  role: "produces",
});

describe("what a filter asks for", () => {
  test("the text typed, without the white space around it", () => {
    expect(filterText("  C00500 ")).toBe("C00500");
    expect(filterText("Value A")).toBe("Value A");
    expect(filterText("   ")).toBe("");
  });
});

describe("the components the Table tab's filter leaves", () => {
  test("every one, the very list, while nothing is typed", () => {
    expect(componentsShown(FILES, PROJECT, "")).toBe(FILES);
    expect(componentsShown(FILES, PROJECT, "  ")).toBe(FILES);
  });

  test("each whose name holds the text, whatever its case, in the table's order", () => {
    expect(componentsShown(FILES, PROJECT, "sensor")).toEqual([SENSOR_HUB]);
    expect(componentsShown(FILES, PROJECT, "LOG")).toEqual([LOGGER]);
    expect(componentsShown(FILES, PROJECT, " er ")).toEqual([CONTROLLER, LOGGER]);
  });

  test("each whose file, as the table shows it, holds the text", () => {
    // Relative to the project's directory (`shownPath`): a folder of it finds what it holds, and
    // the directories above the project's find nothing.
    expect(componentsShown(FILES, PROJECT, "subsystems/")).toEqual([LOGGER]);
    expect(componentsShown(FILES, PROJECT, "components/")).toEqual([
      CONTROLLER,
      SENSOR_HUB,
      UNNAMED,
    ]);
    expect(componentsShown([CONTROLLER, SENSOR_HUB, LOGGER], PROJECT, "work")).toEqual([]);
  });

  test("a component with no name, by the whole path the table names it by", () => {
    expect(componentsShown(FILES, PROJECT, "broken")).toEqual([UNNAMED]);
    expect(componentsShown(FILES, PROJECT, "/work/demo/")).toEqual([UNNAMED]);
  });

  test("each row the one it was, so that it keeps its key", () => {
    expect(componentsShown(FILES, PROJECT, "hub")[0]).toBe(SENSOR_HUB);
  });
});

describe("the declarations a component page's filter leaves", () => {
  const rows = [{ name: "ValueA" }, { name: "ValueB" }, { name: "ParameterA" }, { name: "AxisA" }];

  test("every one, the very list, while nothing is typed", () => {
    expect(declarationsShown(rows, "")).toBe(rows);
  });

  test("each whose name holds the text, whatever its case, in the table's order", () => {
    expect(declarationsShown(rows, "value")).toEqual([rows[0], rows[1]]);
    expect(declarationsShown(rows, "A")).toEqual(rows);
    expect(declarationsShown(rows, "xisa")).toEqual([rows[3]]);
    expect(declarationsShown(rows, "Curve")).toEqual([]);
  });
});

describe("the places a unit's filter leaves", () => {
  const speed = place("Speed", "/work/p/components/engine.ddd.json");
  const member = place("Gear_t.ratio", "/work/p/types.ddd.json");
  const torque = place("Torque", "/work/p/components/gearbox.ddd.json");
  const sites = [speed, member, torque];

  test("every one, the very list, while nothing is typed", () => {
    expect(placesShown(sites, "")).toBe(sites);
  });

  test("each whose name or file's name holds the text, whatever its case", () => {
    expect(placesShown(sites, "speed")).toEqual([speed]);
    expect(placesShown(sites, "GEAR")).toEqual([member, torque]);
    expect(placesShown(sites, "types.ddd")).toEqual([member]);
    // The file's own name, not the folders above it.
    expect(placesShown(sites, "components")).toEqual([]);
  });
});

describe("whether a filtered table is drawn", () => {
  test("while the filter leaves a row of it", () => {
    expect(tableDrawn("Hub", 1)).toBe(true);
    expect(tableDrawn("", 4)).toBe(true);
  });

  test("not where the filter leaves none, whose line says so", () => {
    expect(tableDrawn("nothing", 0)).toBe(false);
  });

  test("as it was where nothing is typed, a table of no row included", () => {
    expect(tableDrawn("", 0)).toBe(true);
    expect(tableDrawn("  ", 0)).toBe(true);
  });
});

describe("the line beside a filter", () => {
  test("how many rows it leaves of how many, counts grouped", () => {
    expect(filterLine("C005", 3, 1166, COMPONENTS)).toBe("3 of 1,166 components");
    expect(filterLine("Value", 12, 3334, DECLARATIONS)).toBe("12 of 3,334 declarations");
    expect(filterLine("c00500", 2, 12500, PLACES)).toBe("2 of 12,500 places");
    expect(filterLine("missing", 15000, 25000, FINDINGS)).toBe("15,000 of 25,000 findings");
  });

  test("of one, in the singular", () => {
    expect(filterLine("Hub", 1, 1, COMPONENTS)).toBe("1 of 1 component");
    expect(filterLine("Speed", 1, 1, PLACES)).toBe("1 of 1 place");
  });

  test("that nothing matches, where it leaves none", () => {
    expect(filterLine("nothing", 0, 4, COMPONENTS)).toBe("no component matches");
    expect(filterLine("nothing", 0, 30, DECLARATIONS)).toBe("no declaration matches");
    expect(filterLine("nothing", 0, 3, PLACES)).toBe("no place matches");
    expect(filterLine("nothing", 0, 25000, FINDINGS)).toBe("no finding matches");
  });

  test("nothing while nothing is typed", () => {
    expect(filterLine("", 4, 4, COMPONENTS)).toBeNull();
    expect(filterLine("   ", 4, 4, COMPONENTS)).toBeNull();
  });
});
