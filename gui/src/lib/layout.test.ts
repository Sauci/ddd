import { expect, test } from "vitest";
import type { GraphFlow, GraphModule } from "../api/types";
import { laidOut, layoutOf, type Placed, ranked } from "./layout";
import { NODE_HEIGHT, NODE_WIDTH } from "./nodeSize";

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
  const found = placed.find((p) => p.module.path === path);
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
  expect(positionOf(moved, b.path)).toEqual({ module: b, x: 999, y: 111 });
  expect(positionOf(moved, a.path)).toEqual(positionOf(unmoved, a.path));
  expect(positionOf(moved, c.path)).toEqual(positionOf(unmoved, c.path));
});

test("a saved position for a module that no longer exists is ignored, not returned", () => {
  const a = graphModule("/a.ddd.json");
  const placed = laidOut([a], [], { "/gone.ddd.json": { x: 5, y: 5 } });
  expect(placed).toHaveLength(1);
  expect(placed.find((p) => p.module.path === "/gone.ddd.json")).toBeUndefined();
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

test("ranked lays out a chain of 5,000 modules with no recursion", () => {
  const modules = Array.from({ length: 5000 }, (_, i) => graphModule(`/m${i}.ddd.json`));
  const pairs: Array<[GraphModule, GraphModule]> = [];
  for (let i = 0; i + 1 < modules.length; i += 1) {
    const from = modules[i];
    const to = modules[i + 1];
    if (from === undefined || to === undefined) throw new Error("unreachable: i stays in range");
    pairs.push([from, to]);
  }
  const placed = ranked(
    modules,
    pairs.map(([from, to]) => graphFlow(from.path, to.path)),
  );
  expect(placed).toHaveLength(5000);
  // Each module feeds only the next, so rank is strictly increasing along the chain: the first
  // module's box sits left of the second's, the second's left of the third's, and so on.
  for (const [from, to] of pairs) {
    expect(positionOf(placed, from.path).x).toBeLessThan(positionOf(placed, to.path).x);
  }
});

test("ranked places every module of a cycle nothing feeds from outside", () => {
  const [a, b, c] = [
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/c.ddd.json"),
  ];
  const flows = [graphFlow(a.path, b.path), graphFlow(b.path, c.path), graphFlow(c.path, a.path)];
  const placed = ranked([a, b, c], flows);
  expect(placed.map((p) => p.module.path).sort()).toEqual([a.path, b.path, c.path]);
  // The smallest path on the cycle (a) starts the fallback pass at rank 0, then follows the
  // cycle outward: a, then b, then c, strictly left to right.
  expect(positionOf(placed, a.path).x).toBeLessThan(positionOf(placed, b.path).x);
  expect(positionOf(placed, b.path).x).toBeLessThan(positionOf(placed, c.path).x);
});

test("ranked places a cycle that something feeds by its own distance from the feeder", () => {
  const [r, a, b, c] = [
    graphModule("/r.ddd.json"),
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/c.ddd.json"),
  ];
  const flows = [
    graphFlow(r.path, a.path),
    graphFlow(a.path, b.path),
    graphFlow(b.path, c.path),
    graphFlow(c.path, a.path),
  ];
  const placed = ranked([r, a, b, c], flows);
  // Reached by the root's own breadth-first search, not the cycle fallback: r, then a, then b,
  // then c, strictly left to right - never two of them tied by starting their own search.
  expect(positionOf(placed, r.path).x).toBeLessThan(positionOf(placed, a.path).x);
  expect(positionOf(placed, a.path).x).toBeLessThan(positionOf(placed, b.path).x);
  expect(positionOf(placed, b.path).x).toBeLessThan(positionOf(placed, c.path).x);
});

test("ranked places disconnected parts independently, each from its own root", () => {
  const [a, b, x, y] = [
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/x.ddd.json"),
    graphModule("/y.ddd.json"),
  ];
  const placed = ranked([a, b, x, y], [graphFlow(a.path, b.path), graphFlow(x.path, y.path)]);
  expect(placed).toHaveLength(4);
  // Both a and x feed nothing from outside, so both start the search at rank 0: the same
  // leftmost column, not one part offset behind the other's.
  expect(positionOf(placed, a.path).x).toBe(positionOf(placed, x.path).x);
  expect(positionOf(placed, b.path).x).toBe(positionOf(placed, y.path).x);
});

test("ranked gives the same placement for the same modules and flows in any order", () => {
  const [a, b, c] = [
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/c.ddd.json"),
  ];
  const [ab, bc] = [graphFlow(a.path, b.path), graphFlow(b.path, c.path)];
  expect(ranked([a, b, c], [ab, bc])).toEqual(ranked([c, a, b], [bc, ab]));
});

test("ranked places nothing for an empty graph", () => {
  expect(ranked([], [])).toEqual([]);
});

test("ranked places every module a root feeds, not only its first", () => {
  const [r, a, b] = [
    graphModule("/r.ddd.json"),
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
  ];
  const placed = ranked([r, a, b], [graphFlow(r.path, a.path), graphFlow(r.path, b.path)]);
  expect(positionOf(placed, r.path).x).toBeLessThan(positionOf(placed, a.path).x);
  expect(positionOf(placed, r.path).x).toBeLessThan(positionOf(placed, b.path).x);
  // Both a and b are one step from r, so they share a rank, ordered by path within it.
  expect(positionOf(placed, a.path).x).toBe(positionOf(placed, b.path).x);
  expect(positionOf(placed, a.path).y).toBeLessThan(positionOf(placed, b.path).y);
});

test("ranked ignores a flow naming a module it was not given", () => {
  const a = graphModule("/a.ddd.json");
  const placed = ranked(
    [a],
    [graphFlow("/gone.ddd.json", a.path), graphFlow(a.path, "/gone.ddd.json")],
  );
  expect(placed).toEqual([{ module: a, x: 0, y: 0 }]);
});

// Review fix round 2, Minor 3: a further pass used to start from the smallest unranked module by
// path, which can sit downstream of an unfed cycle rather than on it.
test("ranked starts an unfed cycle's further pass on the cycle, not downstream of it", () => {
  const [a, b, c] = [
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
    graphModule("/c.ddd.json"),
  ];
  // b and c cycle (b→c, c→b); c also feeds a, downstream of the cycle. Nothing from outside
  // feeds any of the three - all three need the fallback - and the smallest path overall, a, is
  // not on the cycle, only downstream of it.
  const placed = ranked(
    [a, b, c],
    [graphFlow(b.path, c.path), graphFlow(c.path, b.path), graphFlow(c.path, a.path)],
  );
  // b, the cycle's own smallest member, starts the pass - not a, which would run c→a backwards.
  expect(positionOf(placed, b.path).x).toBeLessThan(positionOf(placed, c.path).x);
  expect(positionOf(placed, c.path).x).toBeLessThan(positionOf(placed, a.path).x);
});

test("ranked places a self-loop's own module once, not forever", () => {
  const a = graphModule("/a.ddd.json");
  const placed = ranked([a], [graphFlow(a.path, a.path)]);
  expect(placed).toEqual([{ module: a, x: 0, y: 0 }]);
});

// Review fix round 2, New Important 2: pins the multi-source search layout.ts's own doc
// describes - searching from each root on its own, instead, also passed every test above.
test("ranked's root search is multi-source: a node two roots reach keeps the shorter distance", () => {
  const [m, r1, r2, x] = [
    graphModule("/m.ddd.json"),
    graphModule("/r1.ddd.json"),
    graphModule("/r2.ddd.json"),
    graphModule("/x.ddd.json"),
  ];
  const flows = [graphFlow(r1.path, x.path), graphFlow(x.path, m.path), graphFlow(r2.path, m.path)];
  const placed = ranked([m, r1, r2, x], flows);
  // r1 (sorted before r2) reaches m in two hops, via x; r2 reaches it directly, in one. A true
  // multi-source search starts both roots together and keeps the shorter distance regardless of
  // which root sorts first, so m lands in the same rank as x - one hop from a root, not two, the
  // way processing r1's own search to completion before starting r2's would leave it.
  expect(positionOf(placed, m.path).x).toBe(positionOf(placed, x.path).x);
  expect(positionOf(placed, r1.path).x).toBeLessThan(positionOf(placed, x.path).x);
});

// Review fix round 2, Minor 4: dagre's own default spacing (`ranksep`/`nodesep`, 50 each), since
// `laidOut` sets neither of its own - pinned by the literal 50, not by importing the constant.
test("ranked spaces ranks 50px apart, beyond the node's own width", () => {
  const [a, b] = [graphModule("/a.ddd.json"), graphModule("/b.ddd.json")];
  const placed = ranked([a, b], [graphFlow(a.path, b.path)]);
  expect(positionOf(placed, b.path).x - positionOf(placed, a.path).x).toBe(NODE_WIDTH + 50);
});

test("ranked spaces modules sharing a rank 50px apart, beyond the node's own height", () => {
  const [r, a, b] = [
    graphModule("/r.ddd.json"),
    graphModule("/a.ddd.json"),
    graphModule("/b.ddd.json"),
  ];
  const placed = ranked([r, a, b], [graphFlow(r.path, a.path), graphFlow(r.path, b.path)]);
  expect(positionOf(placed, b.path).y - positionOf(placed, a.path).y).toBe(NODE_HEIGHT + 50);
});

// Review fix round 2, New Important 1: the fallback's own trigger - a RangeError means ranks
// only, any other error is not this function's to answer - as a lib function, tested.
test("layoutOf falls back to ranked, marked ranksOnly, when dagre overflows its stack", () => {
  const modules = Array.from({ length: 3000 }, (_, i) => graphModule(`/m${i}.ddd.json`));
  const pairs: Array<[GraphModule, GraphModule]> = [];
  for (let i = 0; i + 1 < modules.length; i += 1) {
    const from = modules[i];
    const to = modules[i + 1];
    if (from === undefined || to === undefined) throw new Error("unreachable: i stays in range");
    pairs.push([from, to]);
  }
  const flows = pairs.map(([from, to]) => graphFlow(from.path, to.path));
  const result = layoutOf(modules, flows);
  expect(result.ranksOnly).toBe(true);
  expect(result.placed).toHaveLength(3000);
});

test("layoutOf answers dagre's own layout directly when it succeeds, not ranksOnly", () => {
  const [a, b] = [graphModule("/a.ddd.json"), graphModule("/b.ddd.json")];
  const result = layoutOf([a, b], [graphFlow(a.path, b.path)]);
  expect(result.ranksOnly).toBe(false);
  expect(result.placed).toEqual(laidOut([a, b], [graphFlow(a.path, b.path)], {}));
});

test("layoutOf lets an error that is not a RangeError through, rather than falling back", () => {
  // Array.prototype.sort never calls its comparator for a single element, so laidOut's own
  // sorted = [...modules].sort(...) needs a second malformed module before comparing paths - and
  // so throwing - actually happens.
  const malformed = [
    { path: undefined, name: "x", loaded: true, findings: { error: 0, warning: 0, info: 0 } },
    { path: undefined, name: "y", loaded: true, findings: { error: 0, warning: 0, info: 0 } },
  ] as unknown as GraphModule[];
  expect(() => layoutOf(malformed, [])).toThrow(TypeError);
});
