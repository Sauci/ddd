import { expect, test } from "vitest";
import type { GraphFlow, GraphModule } from "../api/types";
import { laidOut, type Placed } from "./layout";

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

function positionOf(placed: readonly Placed[], path: string): Placed {
  const found = placed.find((p) => p.path === path);
  if (found === undefined) throw new Error(`${path} was not placed`);
  return found;
}

test("a chain of producers and consumers is laid out left to right", () => {
  const [a, b, c] = [
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/c.ddd.json"),
  ];
  const placed = laidOut([a, b, c], [graphFlow(a.path, b.path), graphFlow(b.path, c.path)], {});
  expect(positionOf(placed, a.path).x).toBeLessThan(positionOf(placed, b.path).x);
  expect(positionOf(placed, b.path).x).toBeLessThan(positionOf(placed, c.path).x);
});

test("two modules with no flow between them are both placed, at different positions", () => {
  const a = graphModule("/a.ddd.json");
  const b = graphModule("/b.ddd.json");
  const placed = laidOut([a, b], [], {});
  expect(placed).toHaveLength(2);
  expect(positionOf(placed, a.path)).not.toEqual(positionOf(placed, b.path));
});

test("a saved position wins for its module, and leaves the others at dagre's layout", () => {
  const [a, b, c] = [
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/c.ddd.json"),
  ];
  const flows = [graphFlow(a.path, b.path), graphFlow(b.path, c.path)];
  const unmoved = laidOut([a, b, c], flows, {});
  const moved = laidOut([a, b, c], flows, { [b.path]: { x: 999, y: 111 } });
  expect(positionOf(moved, b.path)).toEqual({ path: b.path, x: 999, y: 111 });
  expect(positionOf(moved, a.path)).toEqual(positionOf(unmoved, a.path));
  expect(positionOf(moved, c.path)).toEqual(positionOf(unmoved, c.path));
});

test("a saved position for a module that no longer exists is ignored, not returned", () => {
  const a = graphModule("/a.ddd.json");
  const placed = laidOut([a], [], { "/gone.ddd.json": { x: 5, y: 5 } });
  expect(placed).toHaveLength(1);
  expect(placed.find((p) => p.path === "/gone.ddd.json")).toBeUndefined();
});

test("laying out the same input twice gives the same output", () => {
  const [a, b, c] = [
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/c.ddd.json"),
  ];
  const flows = [graphFlow(a.path, b.path), graphFlow(b.path, c.path)];
  const saved = { [a.path]: { x: 42, y: 7 } };
  expect(laidOut([a, b, c], flows, saved)).toEqual(laidOut([a, b, c], flows, saved));
});
