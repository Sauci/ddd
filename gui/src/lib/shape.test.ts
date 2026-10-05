import { expect, test } from "vitest";
import type { GraphFlow, GraphModule } from "../api/types";
import { shapeOf, VISIBLE_ONLY_ABOVE, visibleOnly } from "./shape";

const graphModule = (path: string): GraphModule => ({
  path,
  name: path,
  loaded: true,
  findings: { error: 0, warning: 0, info: 0 },
});

const graphFlow = (from: string, to: string): GraphFlow => ({
  from,
  to,
  objects: ["Value"],
  severity: null,
  disagreements: [],
});

test("a graph's shape is the same string for the same modules and arrows in any order", () => {
  const [a, b, c] = [
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/c.ddd.json"),
  ];
  const [ab, bc] = [graphFlow(a.path, b.path), graphFlow(b.path, c.path)];
  expect(shapeOf([a, b, c], [ab, bc])).toBe(shapeOf([c, a, b], [bc, ab]));
});

test("a graph's shape changes when a module comes or goes", () => {
  const [a, b] = [graphModule("/a.ddd.json"), graphModule("/b.ddd.json")];
  expect(shapeOf([a, b], [])).not.toBe(shapeOf([a], []));
});

test("a graph's shape changes when an arrow comes or goes", () => {
  const [a, b] = [graphModule("/a.ddd.json"), graphModule("/b.ddd.json")];
  expect(shapeOf([a, b], [graphFlow(a.path, b.path)])).not.toBe(shapeOf([a, b], []));
});

test("a graph's shape does not change when only a module's findings counts change", () => {
  const [a, b] = [graphModule("/a.ddd.json"), graphModule("/b.ddd.json")];
  const busy: GraphModule = { ...a, findings: { error: 9, warning: 3, info: 1 } };
  const flows = [graphFlow(a.path, b.path)];
  expect(shapeOf([a, b], flows)).toBe(shapeOf([busy, b], flows));
});

test("a graph's shape does not change when only a module's loaded flag changes", () => {
  const [a, b] = [graphModule("/a.ddd.json"), graphModule("/b.ddd.json")];
  const unloaded: GraphModule = { ...a, loaded: false };
  const flows = [graphFlow(a.path, b.path)];
  expect(shapeOf([a, b], flows)).toBe(shapeOf([unloaded, b], flows));
});

test("a graph's shape does not change when only an arrow's objects or severity change", () => {
  const [a, b] = [graphModule("/a.ddd.json"), graphModule("/b.ddd.json")];
  const quiet = graphFlow(a.path, b.path);
  const disagreeing: GraphFlow = { ...quiet, objects: ["One", "Two"], severity: "error" };
  expect(shapeOf([a, b], [quiet])).toBe(shapeOf([a, b], [disagreeing]));
});

test("a graph's shape does not change when only an arrow's disagreements change", () => {
  const [a, b] = [graphModule("/a.ddd.json"), graphModule("/b.ddd.json")];
  const quiet = graphFlow(a.path, b.path);
  const disagreeing: GraphFlow = {
    ...quiet,
    disagreements: [
      { object: "Value", check: "definition-mismatch", severity: "error", message: "differs" },
    ],
  };
  expect(shapeOf([a, b], [quiet])).toBe(shapeOf([a, b], [disagreeing]));
});

test("React Flow draws every node whole at or below VISIBLE_ONLY_ABOVE modules", () => {
  expect(visibleOnly(VISIBLE_ONLY_ABOVE)).toBe(false);
  expect(visibleOnly(0)).toBe(false);
});

test("React Flow draws only the nodes in view above VISIBLE_ONLY_ABOVE modules", () => {
  expect(visibleOnly(VISIBLE_ONLY_ABOVE + 1)).toBe(true);
});

// Review fix round 1, Important 2: the two tests above compare only against the constant itself,
// so changing its value left them green - pin the literal value React Flow's own culling turns
// on at, not only its relationship to whatever the constant happens to be.
test("React Flow draws every node whole at exactly 200 modules", () => {
  expect(visibleOnly(200)).toBe(false);
});

test("React Flow draws only the nodes in view at 201 modules", () => {
  expect(visibleOnly(201)).toBe(true);
});
