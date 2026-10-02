import { expect, test } from "vitest";
import type { GraphFlow, GraphModule, GraphReply } from "../api/types";
import {
  brightOf,
  edgesOf,
  fadedNodes,
  firstMatch,
  flowTitle,
  initialViewport,
  MIN_ZOOM,
  type ModuleNodeType,
  nodesOf,
  objectsInDisagreement,
  STROKE,
  shownEdges,
  stateOf,
  withMeasured,
  withSavedPositions,
} from "./canvas";
import type { Placed } from "./layout";
import { NODE_WIDTH } from "./nodeSize";

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

const placedAt = (module: GraphModule, x: number, y: number): Placed => ({ module, x, y });

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
  const nodes = nodesOf([placedAt(A, 0, 0), placedAt(B, 10, 10)], [A, B], () => undefined);
  expect(nodes.map((node) => node.id)).toEqual([A.path, B.path]);
  expect(nodes[0]?.data).toMatchObject({ name: "Alpha", loaded: true, errors: 2, warnings: 0 });
  expect(nodes[1]?.data).toMatchObject({ name: "Beta", errors: 0, warnings: 1 });
  expect(nodes.every((node) => node.type === "module" && !node.data.faded)).toBe(true);
});

test("a node opens its own module's page, and sits at its placed position", () => {
  const opened: string[] = [];
  const nodes = nodesOf([placedAt(A, 0, 0), placedAt(B, 7, 9)], [A, B], (path) => {
    opened.push(path);
  });
  const beta = nodes[1];
  if (beta === undefined) throw new Error("expected Beta to be placed");
  beta.data.onOpen(beta.id);
  expect(opened).toEqual([B.path]);
  expect(beta.position).toEqual({ x: 7, y: 9 });
});

test("a node's data comes from the modules given now, never from when it was placed", () => {
  const placedWhenQuiet = placedAt(graphModule(A.path, "Alpha", 0, 0), 5, 5);
  const busyNow = graphModule(A.path, "Alpha", 3, 1);
  const nodes = nodesOf([placedWhenQuiet], [busyNow], () => undefined);
  expect(nodes[0]?.data).toMatchObject({ errors: 3, warnings: 1 });
  expect(nodes[0]?.position).toEqual({ x: 5, y: 5 });
});

test("a module the given modules no longer carry draws no node", () => {
  const nodes = nodesOf([placedAt(A, 0, 0), placedAt(B, 1, 1)], [A], () => undefined);
  expect(nodes.map((node) => node.id)).toEqual([A.path]);
});

test("a module not yet placed draws no node, until the layout that places it arrives", () => {
  const nodes = nodesOf([placedAt(A, 0, 0)], [A, B], () => undefined);
  expect(nodes.map((node) => node.id)).toEqual([A.path]);
});

// Review fix round 1, Important 2: the two tests above pin only the findings counts, which left
// `loaded` and `name` free to be read from the placement's own (possibly stale) module instead
// of the current one, unnoticed.
test("a node's loaded flag comes from the modules given now, never from when it was placed", () => {
  const placedWhileLoaded: Placed = { module: { ...A, loaded: true }, x: 0, y: 0 };
  const unloadedNow: GraphModule = { ...A, loaded: false };
  const nodes = nodesOf([placedWhileLoaded], [unloadedNow], () => undefined);
  expect(nodes[0]?.data.loaded).toBe(false);
});

test("a node's name comes from the modules given now, never from when it was placed", () => {
  const placedAsAlpha: Placed = { module: { ...A, name: "Alpha" }, x: 0, y: 0 };
  const renamedNow: GraphModule = { ...A, name: "Omega" };
  const nodes = nodesOf([placedAsAlpha], [renamedNow], () => undefined);
  expect(nodes[0]?.data.name).toBe("Omega");
});

test("a saved position wins for its module, and leaves the others as they were placed", () => {
  const placed = [placedAt(A, 10, 20), placedAt(B, 30, 40)];
  expect(withSavedPositions(placed, { [B.path]: { x: 999, y: 111 } })).toEqual([
    placedAt(A, 10, 20),
    placedAt(B, 999, 111),
  ]);
});

test("no saved position leaves every module exactly as it was placed", () => {
  const placed = [placedAt(A, 10, 20), placedAt(B, 30, 40)];
  expect(withSavedPositions(placed, {})).toEqual(placed);
});

test("a saved position for a module the placement does not carry changes nothing", () => {
  const placed = [placedAt(A, 10, 20)];
  expect(withSavedPositions(placed, { [B.path]: { x: 1, y: 1 } })).toEqual(placed);
});

test("every flow becomes an arrow announced as one sentence, coloured by its severity", () => {
  const edges = edgesOf(
    reply(
      [A, B, C],
      [graphFlow(A.path, B.path, ["One", "Two"], "error"), graphFlow(B.path, C.path)],
    ),
    () => undefined,
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
  const [edge] = edgesOf(
    reply([A, B], [graphFlow(A.path, B.path)]),
    (id) => reached.push(id),
    () => undefined,
  );
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
  expect(
    edgesOf(
      reply(modules, [graphFlow("/gone.ddd.json", B.path)]),
      () => undefined,
      () => undefined,
    ),
  ).toEqual([]);
  expect(
    edgesOf(
      reply(modules, [graphFlow(A.path, "/gone.ddd.json")]),
      () => undefined,
      () => undefined,
    ),
  ).toEqual([]);
});

test("an arrow opens its panel when clicked, or on Enter or Space, and on no other key", () => {
  const opened: string[] = [];
  const [edge] = edgesOf(
    reply([A, B], [graphFlow(A.path, B.path)]),
    () => undefined,
    (id) => {
      opened.push(id);
    },
  );
  fire(edge?.domAttributes?.onClick);
  const press = (key: string): boolean => {
    const handler = edge?.domAttributes?.onKeyDown;
    if (handler === undefined) throw new Error("the arrow carries no key handler");
    let prevented = false;
    handler({ key, preventDefault: () => (prevented = true) } as never);
    return prevented;
  };
  expect([press("Enter"), press(" "), press("a")]).toEqual([true, true, false]);
  expect(opened).toEqual([edge?.id, edge?.id, edge?.id]);
});

test("an arrow's variables in disagreement are listed once each, in order", () => {
  const disagreeing: GraphFlow = {
    ...graphFlow(A.path, B.path, ["One", "Two"], "error"),
    disagreements: [
      { object: "Two", check: "definition-mismatch", severity: "error", message: "m" },
      { object: "One", check: "definition-mismatch", severity: "warning", message: "m" },
      { object: "Two", check: "storage-mismatch", severity: "error", message: "m" },
      { object: null, check: "definition-mismatch", severity: "error", message: "m" },
    ],
  };
  const graph = reply([A, B], [disagreeing, graphFlow(B.path, A.path)]);
  expect(objectsInDisagreement(graph, `${A.path} -> ${B.path}`)).toEqual(["One", "Two"]);
  expect(objectsInDisagreement(graph, `${B.path} -> ${A.path}`)).toEqual([]);
  expect(objectsInDisagreement(graph, "nowhere")).toEqual([]);
});

test("an arrow naming a variable in disagreement is a button; one that agrees is not", () => {
  const disagreeing: GraphFlow = {
    ...graphFlow(A.path, B.path),
    disagreements: [
      { object: "One", check: "definition-mismatch", severity: "error", message: "m" },
    ],
  };
  const [opens, agrees] = edgesOf(
    reply([A, B], [disagreeing, graphFlow(B.path, A.path)]),
    () => undefined,
    () => undefined,
  );
  expect(opens?.ariaRole).toBe("button");
  expect(agrees?.ariaRole).toBeUndefined();
});

test("an arrow is named by the modules it joins", () => {
  const graph = reply([A, B], [graphFlow(A.path, B.path)]);
  expect(flowTitle(graph, `${A.path} -> ${B.path}`)).toBe("Alpha to Beta");
  expect(flowTitle(graph, "nowhere")).toBe("nowhere");
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
  const nodes = nodesOf([placedAt(A, 0, 0), placedAt(B, 10, 10)], [A, B], () => undefined);
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
    () => undefined,
  );
  const shown = shownEdges(edges, new Set([A.path, B.path]), edges[0]?.id ?? null);
  expect(shown.map((edge) => [edge.data.faded, edge.data.active])).toEqual([
    [false, true],
    [true, false],
  ]);
  expect(shownEdges(edges, null, null)).toEqual(edges);
});

function nodeWithMeasured(
  id: string,
  measured?: { width: number; height: number },
): ModuleNodeType {
  return {
    id,
    type: "module",
    position: { x: 0, y: 0 },
    // Spread in only when given: exactOptionalPropertyTypes makes `measured: undefined` a type
    // error of its own, distinct from the key being absent - the same reason `edgesOf` spreads
    // `ariaRole` in conditionally (canvas.ts's own doc on it).
    ...(measured !== undefined ? { measured } : {}),
    data: {
      name: id,
      loaded: true,
      errors: 0,
      warnings: 0,
      onOpen: () => undefined,
      faded: false,
    },
  };
}

test("withMeasured carries a current node's measured size onto the fresh node of the same id", () => {
  const current = [nodeWithMeasured(A.path, { width: 180, height: 48 })];
  const fresh = [nodeWithMeasured(A.path)];
  const result = withMeasured(fresh, current);
  expect(result[0]?.measured).toEqual({ width: 180, height: 48 });
});

test("withMeasured leaves a node current does not carry exactly as it was built", () => {
  const fresh = [nodeWithMeasured(A.path)];
  const result = withMeasured(fresh, []);
  expect(result).toEqual(fresh);
  expect(result[0]).toBe(fresh[0]);
});

test("withMeasured does not carry a measured of undefined over one already set", () => {
  const current = [nodeWithMeasured(A.path)];
  const fresh = [nodeWithMeasured(A.path, { width: 1, height: 1 })];
  const result = withMeasured(fresh, current);
  expect(result[0]?.measured).toEqual({ width: 1, height: 1 });
});

test("initialViewport leaves fitView alone when nothing is placed", () => {
  expect(initialViewport([], { width: 1280, height: 800 }, MIN_ZOOM)).toBeNull();
});

test("initialViewport leaves fitView alone when its own fit already shows everything", () => {
  const placed = [placedAt(A, 0, 0), placedAt(B, 300, 0)];
  expect(initialViewport(placed, { width: 1280, height: 800 }, MIN_ZOOM)).toBeNull();
});

test("initialViewport centres the first rank at minZoom when the whole graph would not fit", () => {
  // Fifty ranks spread along x: fitting all fifty into 1280px needs a zoom fitView would clamp
  // to MIN_ZOOM, leaving the fitted middle - around rank 25 - the only thing in view.
  const GAP = 60;
  const placed = Array.from({ length: 50 }, (_, rank) =>
    placedAt(graphModule(`/m${rank}.ddd.json`, `M${rank}`), rank * (NODE_WIDTH + GAP), 0),
  );
  const size = { width: 1280, height: 800 };
  const result = initialViewport(placed, size, MIN_ZOOM);
  expect(result).not.toBeNull();
  expect(result?.zoom).toBe(MIN_ZOOM);
  // The first rank (x = 0) must actually be on screen at this viewport: world x = 0 maps to
  // screen x = 0 * zoom + result.x, which has to land inside [0, size.width].
  const screenX = 0 * MIN_ZOOM + (result?.x ?? 0);
  const screenY = 0 * MIN_ZOOM + (result?.y ?? 0);
  expect(screenX).toBeGreaterThanOrEqual(0);
  expect(screenX).toBeLessThan(size.width);
  expect(screenY).toBeGreaterThanOrEqual(0);
  expect(screenY).toBeLessThan(size.height);
});

test("initialViewport leaves fitView alone when the canvas has not been measured yet", () => {
  const placed = [placedAt(A, 0, 0)];
  expect(initialViewport(placed, { width: 0, height: 0 }, MIN_ZOOM)).toBeNull();
});
