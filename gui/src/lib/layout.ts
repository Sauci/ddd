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
