import { expect, test } from "vitest";
import type { GraphFlow, GraphModule, GraphReply } from "../api/types";
import {
  brightOf,
  edgesOf,
  fadedNodes,
  firstMatch,
  flightOf,
  flowTitle,
  insideBox,
  MIN_ZOOM,
  modulesCut,
  noDictionary,
  nodesOf,
  objectsInDisagreement,
  openingViewport,
  STROKE,
  searchLine,
  shownEdges,
  stateOf,
  tooltipSpot,
  windowPointOf,
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

// Review fix round 2, Finding 7: a node without these is mounted at least once to be measured
// regardless of whether it was ever in view. Pinned by the literal numbers the re-review read
// off the real DOM: target (-3, 21), source (177, 21), each 6×6.
test("every node carries its own measured size and both handles from the start", () => {
  const [node] = nodesOf([placedAt(A, 0, 0)], [A], () => undefined);
  expect(node?.measured).toEqual({ width: 180, height: 48 });
  expect(node?.handles).toEqual([
    { type: "target", position: "left", x: -3, y: 21, width: 6, height: 6 },
    { type: "source", position: "right", x: 177, y: 21, width: 6, height: 6 },
  ]);
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

test("the line under the search box says how many modules a search found of how many there are", () => {
  // A project of 1,166 modules, three of them holding the text searched for.
  const modules = [
    ...Array.from({ length: 1163 }, (_, index) =>
      graphModule(`/c${index}.ddd.json`, `C${String(index).padStart(5, "0")}`),
    ),
    graphModule("/sensor_hub.ddd.json", "SensorHub"),
    graphModule("/pressure.ddd.json", "PressureSensor"),
    graphModule("/sensor_bus.ddd.json", "SensorBus"),
  ];
  expect(searchLine(modules, "sensor")).toBe("3 of 1,166 modules");
  expect(searchLine(modules, "C0050")).toBe("10 of 1,166 modules");
  expect(searchLine([...modules.slice(0, 3)], "c0000")).toBe("3 of 3 modules");
  expect(searchLine([A], "alp")).toBe("1 of 1 module");
});

test("a search that finds no module says so, and nothing typed says nothing", () => {
  expect(searchLine([A, B, C], "nothing")).toBe("no module matches");
  expect(searchLine([A, B, C], "")).toBeNull();
  expect(searchLine([A, B, C], "  ")).toBeNull();
});

test("the line counts exactly what a search dims the rest for, ignoring case", () => {
  expect(searchLine([A, B, C], "A")).toBe("3 of 3 modules");
  expect(searchLine([A, B, C], "BET")).toBe("1 of 3 modules");
  expect(searchLine([A, B, C], " gam ")).toBe("1 of 3 modules");
});

test("a canvas with no dictionary says so, naming the files that did not load where that is why", () => {
  // A plugin that raised or a constant declared twice leaves no dictionary too, with every file
  // loaded: the graph cannot tell those apart, and names no cause.
  expect(noDictionary([], false)).toBe(
    "This project has no dictionary, so its modules are drawn without arrows.",
  );
  // A file that did not load leaves every read of the project with an error, and so no dictionary.
  expect(noDictionary(["controller.ddd.json"], false)).toBe(
    "controller.ddd.json did not load, so this project has no dictionary, and its modules are " +
      "drawn without arrows.",
  );
  expect(
    noDictionary(["a.ddd.json", "b.ddd.json", "c.ddd.json", "d.ddd.json", "e.ddd.json"], false),
  ).toBe(
    "a.ddd.json, b.ddd.json, c.ddd.json and 2 more did not load, so this project has no " +
      "dictionary, and its modules are drawn without arrows.",
  );
});

test("a canvas whose project's own description did not load says no module is drawn", () => {
  // Nothing past the description is read, so there is no module for arrows to be missing from.
  expect(noDictionary(["demo.ddd.json"], true)).toBe(
    "demo.ddd.json did not load, so this project has no dictionary and no module is drawn.",
  );
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

// Review fix round 2, New Important 2: MIN_ZOOM pinned by the literal 0.5, not by comparing the
// constant against itself the way passing it as openingViewport's own minZoom argument would.
test("MIN_ZOOM is React Flow's own default, 0.5", () => {
  expect(MIN_ZOOM).toBe(0.5);
});

test("modules are cut where a module's box reaches past the canvas, whichever edge", () => {
  const module = {} as GraphModule;
  const at = (x: number, y: number): Placed => ({ module, x, y });
  const size = { width: 600, height: 400 };
  const view = { x: 0, y: 0, zoom: 1 };
  // NODE_WIDTH wide: inside at 0, cut past the right edge once it reaches beyond 600.
  expect(modulesCut([at(0, 0), at(100, 100)], view, size)).toBe(false);
  expect(modulesCut([at(0, 0), at(600 - NODE_WIDTH + 1, 0)], view, size)).toBe(true);
  expect(modulesCut([at(-1, 0)], view, size)).toBe(true);
  expect(modulesCut([at(0, -1)], view, size)).toBe(true);
  expect(modulesCut([at(0, 400)], view, size)).toBe(true);
  // The view's own offset and zoom move every box with it.
  expect(modulesCut([at(10, 10)], { x: 590, y: 0, zoom: 1 }, size)).toBe(true);
  expect(modulesCut([at(0, 0)], { x: 0, y: 0, zoom: 0.5 }, size)).toBe(false);
  expect(modulesCut([at(500, 0)], { x: 0, y: 0, zoom: 2 }, size)).toBe(true);
  // A module of this width, zoomed in, reaches further than at the zoom of 1.
  expect(modulesCut([at(150, 0)], { x: 0, y: 0, zoom: 2 }, size)).toBe(true);
  expect(modulesCut([at(150, 0)], { x: 0, y: 0, zoom: 1 }, size)).toBe(false);
  expect(modulesCut([at(0, 0)], { x: 0, y: 0, zoom: 4 }, { width: 5000, height: 100 })).toBe(true);
  expect(modulesCut([at(0, 0)], { x: 0, y: 0, zoom: 1 }, { width: 5000, height: 100 })).toBe(false);
  expect(modulesCut([], view, size)).toBe(false);
});

test("openingViewport shows nothing when nothing is placed", () => {
  expect(openingViewport([], { width: 1280, height: 800 }, MIN_ZOOM)).toBeNull();
});

test("openingViewport shows nothing when the canvas has not been measured yet", () => {
  const placed = [placedAt(A, 0, 0)];
  expect(openingViewport(placed, { width: 0, height: 0 }, MIN_ZOOM)).toBeNull();
});

test("openingViewport fits the whole placement when it already fits, uncapped", () => {
  // Three modules spread so the zoom needed to fit them all lands strictly between MIN_ZOOM and
  // React Flow's own default maxZoom (2) - neither clamp applies, so this is fitView's own
  // result, computed directly rather than left to it.
  const placed = [placedAt(A, 0, 0), placedAt(B, 400, 0), placedAt(C, 800, 0)];
  const result = openingViewport(placed, { width: 1280, height: 800 }, MIN_ZOOM);
  expect(result).toEqual({ x: 58, y: 371.49387755102043, zoom: 1.1877551020408164 });
});

test("openingViewport fits the whole placement capped at maxZoom when it fits with room to spare", () => {
  const placed = [placedAt(A, 0, 0), placedAt(B, 300, 0)];
  const result = openingViewport(placed, { width: 1280, height: 800 }, MIN_ZOOM);
  // Uncapped this would zoom to 2.425 - capped at React Flow's own default maxZoom, 2, the same
  // ceiling fitView itself would apply.
  expect(result).toEqual({ x: 160, y: 352, zoom: 2 });
});

// The final review's fix wave (Ruling T10-5, Minor 2): the boundary itself is the fit's. Two
// modules 2,148 px apart make bounds 2,328 px wide; 1,280 px less React Flow's own padding at 0.1
// (58 px each side, floored) leaves 1,164 px, so the zoom that fits them is exactly MIN_ZOOM - the
// fit, centred at x 58, where the first rank alone would open at x 595.
test("openingViewport fits the whole placement when it fits at exactly minZoom", () => {
  const placed = [placedAt(A, 0, 0), placedAt(B, 2148, 0)];
  const result = openingViewport(placed, { width: 1280, height: 800 }, MIN_ZOOM);
  expect(result).toEqual({ x: 58, y: 388, zoom: 0.5 });
});

test("openingViewport centres the first rank at minZoom when the whole graph would not fit", () => {
  // Fifty ranks spread along x, ranked's own spacing (NODE_WIDTH + 50): fitting all fifty into
  // 1280px needs a zoom below MIN_ZOOM, leaving the fitted middle - around rank 25 - the only
  // thing in view were this the fit instead.
  const placed = Array.from({ length: 50 }, (_, rank) =>
    placedAt(graphModule(`/m${rank}.ddd.json`, `M${rank}`), rank * (NODE_WIDTH + 50), 0),
  );
  const result = openingViewport(placed, { width: 1280, height: 800 }, MIN_ZOOM);
  expect(result).toEqual({ x: 595, y: 388, zoom: 0.5 });
});

// 16:I11: a graphic that carries meaning wants 3:1 on its ground, and `--rule` on `--canvas` is 1.17:1.
test("an arrow that agrees is drawn in the quiet ink, as dark as the page's own quiet text", () => {
  expect(STROKE.agreed).toBe("var(--ink-quiet)");
});

// 16:M19: the viewport's flights take 300 ms, and none for a reader who asked for less motion.
test("the viewport flies for 300 ms, and for no time at all under reduced motion", () => {
  expect(flightOf(false)).toBe(300);
  expect(flightOf(true)).toBe(0);
});

test("a point of the canvas is in the window where the viewport's pan and zoom, and the canvas's corner, put it", () => {
  expect(windowPointOf({ x: 100, y: 50 }, [10, -20, 1], { x: 0, y: 0 })).toEqual({ x: 110, y: 30 });
  expect(windowPointOf({ x: 100, y: 50 }, [10, -20, 2], { x: 40, y: 90 })).toEqual({
    x: 250,
    y: 170,
  });
});

test("a tooltip sits above its arrow, centred, and keeps its size whatever the zoom", () => {
  const spot = tooltipSpot(
    { x: 500, y: 400 },
    { width: 200, height: 80 },
    { width: 1000, height: 800 },
  );
  expect(spot).toEqual({ x: 400, y: 308 });
});

test("a tooltip with no room above its arrow goes below it", () => {
  const spot = tooltipSpot(
    { x: 500, y: 50 },
    { width: 200, height: 80 },
    { width: 1000, height: 800 },
  );
  expect(spot).toEqual({ x: 400, y: 62 });
});

test("a tooltip is moved in from the window's edges, and never above or left of its corner", () => {
  const window = { width: 1000, height: 800 };
  const size = { width: 200, height: 80 };
  expect(tooltipSpot({ x: 20, y: 400 }, size, window).x).toBe(8);
  expect(tooltipSpot({ x: 990, y: 400 }, size, window).x).toBe(792);
  // Below an arrow near the window's foot there is no room either: kept in, its first line shown.
  expect(tooltipSpot({ x: 500, y: 20 }, size, { width: 1000, height: 100 }).y).toBe(12);
  // Larger than the window: the first line first.
  expect(tooltipSpot({ x: 500, y: 400 }, { width: 2000, height: 900 }, window)).toEqual({
    x: 8,
    y: 8,
  });
});

test("a point is inside a box up to its edges, and outside past them", () => {
  const box = { x: 10, y: 20, width: 100, height: 50 };
  expect(insideBox({ x: 10, y: 20 }, box)).toBe(true);
  expect(insideBox({ x: 110, y: 70 }, box)).toBe(true);
  expect(insideBox({ x: 9, y: 40 }, box)).toBe(false);
  expect(insideBox({ x: 111, y: 40 }, box)).toBe(false);
  expect(insideBox({ x: 50, y: 19 }, box)).toBe(false);
  expect(insideBox({ x: 50, y: 71 }, box)).toBe(false);
});
