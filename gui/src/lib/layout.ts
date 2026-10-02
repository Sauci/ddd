import dagre, { type EdgeLabel, type GraphLabel, type NodeLabel } from "@dagrejs/dagre";
import type { GraphFlow, GraphModule } from "../api/types";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 48;

/**
 * A module placed on the canvas.
 *
 * It carries the module itself, not only its path: what draws the node needs the name and the
 * counts beside the position, and a second lookup by path would need a fallback for a module
 * that was never laid out - a case this function makes impossible, since it places every module
 * it is given.
 */
export interface Placed {
  module: GraphModule;
  x: number;
  y: number;
}

/**
 * Where every module goes: dagre lays the flows out left to right, and a position the reader
 * saved wins over the one dagre computed.
 *
 * Every module is given to dagre and laid out - a moved module still occupies its slot in the
 * layout, so the ones that were not moved are placed exactly as if it had not been - and the
 * saved position is substituted afterwards, per spec 5.1. The modules are sorted by path before
 * they reach dagre, so that the two modules of an unconnected pair, which no edge orders, still
 * come out in the same relative place every time: one project always lays out the same way.
 */
export function laidOut(
  modules: readonly GraphModule[],
  flows: readonly GraphFlow[],
  saved: Readonly<Record<string, { x: number; y: number }>>,
): Placed[] {
  const sorted = [...modules].sort((a, b) => a.path.localeCompare(b.path));
  const graph = new dagre.graphlib.Graph<GraphLabel, NodeLabel, EdgeLabel>();
  graph.setGraph({ rankdir: "LR" });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const module of sorted) {
    graph.setNode(module.path, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const flow of flows) {
    graph.setEdge(flow.from, flow.to);
  }
  dagre.layout(graph);
  return sorted.map((module) => {
    const at = saved[module.path];
    if (at !== undefined) return { module, x: at.x, y: at.y };
    // dagre.layout() gives every node it laid out a numeric centre; NodeLabel's x and y are
    // typed optional only because they are unset before layout runs.
    const node = graph.node(module.path) as { x: number; y: number };
    return { module, x: node.x - NODE_WIDTH / 2, y: node.y - NODE_HEIGHT / 2 };
  });
}

/**
 * One string standing for a graph's shape: the sorted module paths, then the sorted arrows'
 * `from` and `to` pairs. Two calls give the same string for the same modules and arrows
 * regardless of the order either was given in, and a different string the moment a module or an
 * arrow comes or goes - a revision that only changes a module's findings counts or `loaded`, or
 * an arrow's objects, severity or disagreements, carries the same modules and the same arrows,
 * so its shape is unchanged. This is what `useLayout` (`gui/src/app`) compares to decide whether
 * the layout - the one part of drawing the graph dagre's own cost makes too slow for the main
 * thread (Ruling 2) - has to be made again, rather than kept as it was for a revision that moved
 * nothing.
 */
export function shapeOf(modules: readonly GraphModule[], flows: readonly GraphFlow[]): string {
  const paths = modules.map((module) => module.path).sort();
  const arrows = flows.map((flow) => JSON.stringify([flow.from, flow.to])).sort();
  return JSON.stringify([paths, arrows]);
}

/**
 * How many modules a graph needs before drawing every node whole, rather than only the ones in
 * view, costs something a reader would notice (Ruling 2). Below this, React Flow drawing every
 * node regardless of the viewport is free enough that a reader never meets one appear late while
 * panning; `visibleOnly` is what reads this threshold, so nothing else compares against it.
 */
export const VISIBLE_ONLY_ABOVE = 200;

/**
 * Whether the canvas should ask React Flow to draw only the nodes currently in view
 * (`onlyRenderVisibleElements`), rather than every one regardless of the viewport.
 */
export function visibleOnly(count: number): boolean {
  return count > VISIBLE_ONLY_ABOVE;
}
