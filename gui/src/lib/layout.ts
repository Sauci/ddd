import dagre, { type EdgeLabel, type GraphLabel, type NodeLabel } from "@dagrejs/dagre";
import type { GraphFlow, GraphModule } from "../api/types";
import { NODE_HEIGHT, NODE_WIDTH } from "./nodeSize";

/**
 * A module placed on the canvas.
 *
 * It carries the module itself, not only its path: `laidOut` and `ranked` both place every
 * module they are given, so a position is never missing the module it belongs to at the moment
 * either makes one. `nodesOf` (`gui/src/lib/canvas.ts`) still looks a placed module back up by
 * path against the *current* modules, with its own fallback for one the lookup misses - not
 * because placing can leave one out, but because a layout kept across a revision (`shapeOf`
 * unchanged) can be older than the modules it is now drawn against.
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

/** The gap, in pixels, `ranked` leaves between two modules' boxes - between ranks and within one
 * - a plain, stated number rather than one read from dagre, which `ranked` never calls. */
const RANK_GAP = 60;

/**
 * Where every module goes when dagre cannot lay the graph out at all: a chain long enough
 * overflows its stack in the worker (review fix round 1, Critical 1 - about 908 modules deep
 * there, against about 1,772 on the main thread and 1,787 in Node, all measured the same way).
 * `ranked` never recurses, so it has no depth of its own to overflow at any size.
 *
 * A module's rank is its breadth-first distance along the flows from the modules nothing feeds -
 * every such module starts the one search at rank 0 together, a true multi-source breadth-first
 * search with an explicit array and a read index standing in for the queue, so a node two
 * different roots can both reach keeps the shorter of the two distances regardless of which root
 * `modules` happened to sort first. A flow naming a module `modules` does not carry is ignored,
 * the same tolerance `nodesOf` has for a placement naming one `modules` no longer carries.
 *
 * A module left unranked after that sits on a cycle nothing outside it feeds: the smallest of
 * the remaining modules by path starts a further search from itself alone, repeated - each
 * pass's own leftover smallest module starting the next - until every module has a rank. Within
 * a rank, modules are ordered by path and stacked top to bottom; ranks run left to right, dagre's
 * own `NODE_WIDTH`/`NODE_HEIGHT` sizing each box and `RANK_GAP` the space between them, so a
 * fallback placement sits on the same kind of grid a dagre one would.
 *
 * Two calls with the same modules and flows, in any order, rank and place them the same way:
 * `modules` is sorted by path before anything else reads it, a flow's own order never decides
 * which root's search reaches a node first (the multi-source search above), and position comes
 * from each module's rank and its place in that rank's own path-sorted list, never from search
 * order.
 */
export function ranked(modules: readonly GraphModule[], flows: readonly GraphFlow[]): Placed[] {
  const sorted = [...modules].sort((a, b) => a.path.localeCompare(b.path));
  const known = new Set(sorted.map((module) => module.path));
  const outgoing = new Map<string, string[]>();
  const fed = new Set<string>();
  for (const flow of flows) {
    if (!known.has(flow.from) || !known.has(flow.to)) continue;
    const targets = outgoing.get(flow.from);
    if (targets === undefined) outgoing.set(flow.from, [flow.to]);
    else targets.push(flow.to);
    fed.add(flow.to);
  }

  const rank = new Map<string, number>();
  // Every call below passes only paths `rank` does not have yet - a module's own path is unique
  // (the same assumption `laidOut` and `nodesOf` make), so the root call's own starts, one per
  // distinct module, can never repeat, and the cycle fallback's loop only ever calls this with a
  // path its own `!rank.has` just confirmed is still unranked. So marking a start needs no guard
  // of its own the way following an edge to `next` does, two lines down - where a chain's second
  // module really can be reached while already ranked, by more than one of its producers.
  function search(starts: readonly string[]): void {
    const queue: string[] = [...starts];
    for (const start of starts) rank.set(start, 0);
    let at = 0;
    while (at < queue.length) {
      const path = queue[at] as string;
      at += 1;
      const distance = rank.get(path) as number;
      for (const next of outgoing.get(path) ?? []) {
        if (rank.has(next)) continue;
        rank.set(next, distance + 1);
        queue.push(next);
      }
    }
  }

  const roots = sorted.filter((module) => !fed.has(module.path)).map((module) => module.path);
  search(roots);
  for (const module of sorted) {
    if (!rank.has(module.path)) search([module.path]);
  }

  const byRank = new Map<number, string[]>();
  for (const module of sorted) {
    const at = rank.get(module.path) as number;
    const inRank = byRank.get(at);
    if (inRank === undefined) byRank.set(at, [module.path]);
    else inRank.push(module.path);
  }

  const position = new Map<string, { x: number; y: number }>();
  for (const [at, paths] of byRank) {
    paths.forEach((path, index) => {
      position.set(path, {
        x: at * (NODE_WIDTH + RANK_GAP),
        y: index * (NODE_HEIGHT + RANK_GAP),
      });
    });
  }

  return sorted.map((module) => {
    const at = position.get(module.path) as { x: number; y: number };
    return { module, x: at.x, y: at.y };
  });
}
