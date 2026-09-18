import { expect, test } from "vitest";
import type { GraphFlow, GraphModule, GraphReply } from "../api/types";
import {
  brightOf,
  edgesOf,
  fadedNodes,
  firstMatch,
  nodesOf,
  STROKE,
  shownEdges,
  stateOf,
} from "./canvas";

const graphModule = (path: string, name: string, errors = 0, warnings = 0): GraphModule => ({
  path,
  name,
  loaded: true,
  findings: { error: errors, warning: warnings, info: 0 },
});

const graphFlow = (
  from: string,
  to: string,
  objects: string[] = ["Value"],
  severity: GraphFlow["severity"] = null,
): GraphFlow => ({ from, to, objects, severity, disagreements: [] });

const reply = (modules: GraphModule[], flows: GraphFlow[]): GraphReply => ({
  revision: 1,
  dictionary: true,
  modules,
  flows,
});

const A = graphModule("/a.ddd.json", "Alpha", 2);
const B = graphModule("/b.ddd.json", "Beta", 0, 1);
const C = graphModule("/c.ddd.json", "Gamma");

/** A handler React Flow calls with a DOM event these tests have no need to build. */
function fire(handler: ((event: never) => void) | undefined): void {
  if (handler === undefined) throw new Error("the arrow carries no such handler");
  handler(undefined as never);
}

test("a severity the arrow paints with, and every other one leaving it plain", () => {
  expect(stateOf("error")).toBe("error");
  expect(stateOf("warning")).toBe("warning");
  expect(stateOf("info")).toBe("agreed");
  expect(stateOf("ignore")).toBe("agreed");
  expect(stateOf(null)).toBe("agreed");
});

test("every module becomes a node carrying what its box draws", () => {
  const nodes = nodesOf(reply([A, B], []), {}, () => undefined);
  expect(nodes.map((node) => node.id)).toEqual([A.path, B.path]);
  expect(nodes[0]?.data).toMatchObject({ name: "Alpha", loaded: true, errors: 2, warnings: 0 });
  expect(nodes[1]?.data).toMatchObject({ name: "Beta", errors: 0, warnings: 1 });
  expect(nodes.every((node) => node.type === "module" && !node.data.faded)).toBe(true);
});

test("a node opens its own module's page, and sits where the reader left it", () => {
  const opened: string[] = [];
  const nodes = nodesOf(reply([A, B], []), { [B.path]: { x: 7, y: 9 } }, (path) => {
    opened.push(path);
  });
  const beta = nodes[1];
  if (beta === undefined) throw new Error("expected Beta to be placed");
  beta.data.onOpen(beta.id);
  expect(opened).toEqual([B.path]);
  expect(beta.position).toEqual({ x: 7, y: 9 });
});

test("every flow becomes an arrow announced as one sentence, coloured by its severity", () => {
  const edges = edgesOf(
    reply(
      [A, B, C],
      [graphFlow(A.path, B.path, ["One", "Two"], "error"), graphFlow(B.path, C.path)],
    ),
    () => undefined,
  );
  expect(edges.map((edge) => [edge.source, edge.target])).toEqual([
    [A.path, B.path],
    [B.path, C.path],
  ]);
  expect(edges[0]?.ariaLabel).toBe("Alpha to Beta: 2 variables, error");
  expect(edges[1]?.ariaLabel).toBe("Beta to Gamma: 1 variable, agreed");
  expect(edges[0]?.markerEnd).toMatchObject({ color: STROKE.error });
  expect(edges[1]?.markerEnd).toMatchObject({ color: STROKE.agreed });
  expect(edges[0]?.data.objects).toEqual(["One", "Two"]);
});

test("an arrow tells the canvas when the reader reaches it, by pointer or by keyboard", () => {
  const reached: (string | null)[] = [];
  const [edge] = edgesOf(reply([A, B], [graphFlow(A.path, B.path)]), (id) => reached.push(id));
  fire(edge?.domAttributes?.onMouseEnter);
  fire(edge?.domAttributes?.onFocus);
  fire(edge?.domAttributes?.onMouseLeave);
  fire(edge?.domAttributes?.onBlur);
  // The same callback rides in the data, for the label that sits on the middle of the curve.
  edge?.data.onReached(edge.id);
  expect(reached).toEqual([edge?.id, edge?.id, null, null, edge?.id]);
  expect(edge?.domAttributes?.["aria-describedby"]).toBe(edge?.data.tooltip);
});

test("a flow naming a module the answer does not carry is not drawn", () => {
  const modules = [A, B];
  expect(edgesOf(reply(modules, [graphFlow("/gone.ddd.json", B.path)]), () => undefined)).toEqual(
    [],
  );
  expect(edgesOf(reply(modules, [graphFlow(A.path, "/gone.ddd.json")]), () => undefined)).toEqual(
    [],
  );
});

test("nothing is dimmed while no module is hovered and nothing is searched for", () => {
  expect(brightOf([A, B], [], null, "  ")).toBeNull();
});

test("hovering keeps the module and its direct neighbours bright", () => {
  const flows = [graphFlow(A.path, B.path), graphFlow(B.path, C.path)];
  expect(brightOf([A, B, C], flows, A.path, "")).toEqual(new Set([A.path, B.path]));
});

test("searching keeps every module whose name contains the text, ignoring case", () => {
  expect(brightOf([A, B, C], [], null, "a")).toEqual(new Set([A.path, B.path, C.path]));
  expect(brightOf([A, B, C], [], null, "BET")).toEqual(new Set([B.path]));
});

test("a module a revision took away stops dimming the canvas from under the pointer", () => {
  expect(brightOf([A, B], [graphFlow(A.path, B.path)], "/gone.ddd.json", "")).toBeNull();
});

test("searching while hovering keeps what both would keep", () => {
  const flows = [graphFlow(A.path, B.path), graphFlow(B.path, C.path)];
  expect(brightOf([A, B, C], flows, B.path, "gam")).toEqual(new Set([C.path]));
});

test("the first match is the first module whose name contains the text", () => {
  expect(firstMatch([A, B, C], "a")).toBe(A.path);
  expect(firstMatch([A, B, C], "BET")).toBe(B.path);
  expect(firstMatch([A, B, C], "nothing")).toBeNull();
  expect(firstMatch([A, B, C], " ")).toBeNull();
});

test("a node outside the bright set is faded, and one whose state did not change is left alone", () => {
  const nodes = nodesOf(reply([A, B], []), {}, () => undefined);
  const faded = fadedNodes(nodes, new Set([A.path]));
  expect(faded.map((node) => node.data.faded)).toEqual([false, true]);
  expect(faded[0]).toBe(nodes[0]);
  expect(fadedNodes(faded, null).map((node) => node.data.faded)).toEqual([false, false]);
  expect(fadedNodes(nodes, null)).toEqual(nodes);
});

test("an arrow is bright only while both of its ends are, and open only while it is reached", () => {
  const edges = edgesOf(
    reply([A, B, C], [graphFlow(A.path, B.path), graphFlow(B.path, C.path)]),
    () => undefined,
  );
  const shown = shownEdges(edges, new Set([A.path, B.path]), edges[0]?.id ?? null);
  expect(shown.map((edge) => [edge.data.faded, edge.data.active])).toEqual([
    [false, true],
    [true, false],
  ]);
  expect(shownEdges(edges, null, null)).toEqual(edges);
});
