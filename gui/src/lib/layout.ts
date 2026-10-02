import dagre, { type EdgeLabel, type GraphLabel, type NodeLabel } from "@dagrejs/dagre";
import type { GraphFlow, GraphModule } from "../api/types";
import { NODE_HEIGHT, NODE_WIDTH } from "./nodeSize";

/**
 * A module placed on the canvas.
 *
 * It carries the module itself, not only its path: `laidOut` and `ranked` both place every
 * module they are given, so a position is never missing the module it belongs to at the moment
 * either makes one. `nodesOf` (`gui/src/lib/canvas.ts`) still looks a placed module back up by
 * path against the *current* modules, with its own fallback for one the lookup misses - which
 * happens only while a revision whose shape *did* change is still being laid out: the kept
 * placement from before it is drawn against the new modules for the one render in between, and a
 * module the new shape added is not in that kept placement yet (review fix round 2, Minor 5a -
 * once `shapeOf` is unchanged again, every placed path is also a current one, and the lookup
 * cannot miss).
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

/** The space, in pixels, between two ranks and between two modules stacked within one - dagre's
 * own defaults (`ranksep`/`nodesep`), since `laidOut` sets neither of its own (review fix round
 * 2, Minor 4): a fallback placement spaces its grid the same amount dagre would have. */
const RANKSEP = 50;
const NODESEP = 50;

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
 * A module left unranked after that sits on a cycle nothing outside the *unranked set* feeds -
 * review fix round 2, Minor 3: round 1 started each further pass from the smallest unranked
 * module by path, which can sit downstream of such a cycle rather than on it (`search` would
 * then reach it from the wrong side, running an edge that leaves the cycle backwards). The
 * smallest module of a *source* strongly connected component of what is left - one nothing
 * outside it, among the still-unranked modules, feeds - starts each further pass instead, found
 * with `sourceOrderedComponents` below: Kosaraju's algorithm, both of its passes iterative, so a
 * cycle has no depth of its own to overflow either. Within a rank, modules are ordered by path
 * and stacked top to bottom; ranks run left to right, dagre's own `NODE_WIDTH`/`NODE_HEIGHT`
 * sizing each box, `RANKSEP`/`NODESEP` the space between them.
 *
 * Two calls with the same modules and flows, in any order, rank and place them the same way:
 * `modules` is sorted by path before anything else reads it, a flow's own order never decides
 * which root's search reaches a node first (the multi-source search above) nor which source
 * component's search reaches a node first (`sourceOrderedComponents` depends only on the graph's
 * own edges, never on the order flows list them), and position comes from each module's rank and
 * its place in that rank's own path-sorted list, never from search order.
 */
export function ranked(modules: readonly GraphModule[], flows: readonly GraphFlow[]): Placed[] {
  const sorted = [...modules].sort((a, b) => a.path.localeCompare(b.path));
  const known = new Set(sorted.map((module) => module.path));
  const outgoing = new Map<string, string[]>();
  const incoming = new Map<string, string[]>();
  const fed = new Set<string>();
  for (const flow of flows) {
    if (!known.has(flow.from) || !known.has(flow.to)) continue;
    pushTo(outgoing, flow.from, flow.to);
    pushTo(incoming, flow.to, flow.from);
    fed.add(flow.to);
  }

  const rank = new Map<string, number>();
  // Every call below passes only paths `rank` does not have yet - a module's own path is unique
  // (the same assumption `laidOut` and `nodesOf` make), so the root call's own starts, one per
  // distinct module, can never repeat, and the source-component loop below only ever calls this
  // with a path its own `!rank.has` just confirmed is still unranked. So marking a start needs no
  // guard of its own the way following an edge to `next` does, two lines down - where a chain's
  // second module really can be reached while already ranked, by more than one of its producers.
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

  const unranked = sorted.filter((module) => !rank.has(module.path)).map((module) => module.path);
  if (unranked.length > 0) {
    const remaining = new Set(unranked);
    const within = (map: Map<string, string[]>, path: string) =>
      (map.get(path) ?? []).filter((other) => remaining.has(other));
    const components = sourceOrderedComponents(
      unranked,
      (path) => within(outgoing, path),
      (path) => within(incoming, path),
    );
    for (const component of components) {
      const smallest = [...component].sort((a, b) => a.localeCompare(b))[0] as string;
      // A component already ranked is one an earlier component's own search already spilled
      // into - strongly connected, so reaching any one of its modules reaches every other one
      // of them too, by the same edges that make it one component - never only some of them.
      if (!rank.has(smallest)) search([smallest]);
    }
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
        x: at * (NODE_WIDTH + RANKSEP),
        y: index * (NODE_HEIGHT + NODESEP),
      });
    });
  }

  return sorted.map((module) => {
    const at = position.get(module.path) as { x: number; y: number };
    return { module, x: at.x, y: at.y };
  });
}

/** Appends `to` to the list `map` keeps for `from`, starting one if this is its first. */
function pushTo(map: Map<string, string[]>, from: string, to: string): void {
  const list = map.get(from);
  if (list === undefined) map.set(from, [to]);
  else list.push(to);
}

/**
 * Every strongly connected component of `nodes` - under `outOf`/`into`, each node's own edges
 * restricted to other members of `nodes`, so an edge to or from one already ranked plays no part
 * - in source-first order: a component earlier in the result has no edge reaching it from one
 * later in it, the two ends of an edge between different components always running the same way
 * `ranked`'s own ranks are meant to.
 *
 * Kosaraju's algorithm: a depth-first search over `outOf`, recording each node's own finishing
 * order; a second one over `into` (the same graph, every edge reversed), visiting unvisited nodes
 * in the *reverse* of that order, each one's own reach - before the next unvisited start is
 * tried - being exactly one component. Processed this way, the first component a start can ever
 * belong to is always one nothing outside it, among `nodes`, reaches - a source component of the
 * condensation - which is the one property `ranked` needs from this. Both passes are iterative,
 * an explicit array standing in for the call stack a recursive depth-first search would use, a
 * frame's own position in its own neighbour list taking the place of where such a call would have
 * paused - so neither has a depth of its own to overflow at any size, the same reason `ranked`
 * itself never recurses.
 */
function sourceOrderedComponents(
  nodes: readonly string[],
  outOf: (node: string) => readonly string[],
  into: (node: string) => readonly string[],
): string[][] {
  const finished: string[] = [];
  const seen = new Set<string>();
  for (const start of nodes) {
    if (seen.has(start)) continue;
    seen.add(start);
    const frames: Array<{ node: string; neighbours: readonly string[]; at: number }> = [
      { node: start, neighbours: outOf(start), at: 0 },
    ];
    while (frames.length > 0) {
      const top = frames[frames.length - 1] as (typeof frames)[number];
      if (top.at >= top.neighbours.length) {
        finished.push(top.node);
        frames.pop();
        continue;
      }
      const candidate = top.neighbours[top.at] as string;
      top.at += 1;
      if (!seen.has(candidate)) {
        seen.add(candidate);
        frames.push({ node: candidate, neighbours: outOf(candidate), at: 0 });
      }
    }
  }

  const assigned = new Set<string>();
  const components: string[][] = [];
  for (let i = finished.length - 1; i >= 0; i -= 1) {
    const start = finished[i] as string;
    if (assigned.has(start)) continue;
    const component: string[] = [];
    const stack = [start];
    assigned.add(start);
    while (stack.length > 0) {
      const node = stack.pop() as string;
      component.push(node);
      for (const prior of into(node)) {
        if (assigned.has(prior)) continue;
        assigned.add(prior);
        stack.push(prior);
      }
    }
    components.push(component);
  }
  return components;
}

/**
 * The one judgement `gui/src/app/layoutWorker.ts` needs from `gui/src/lib`: dagre laying the
 * graph out, or - a `RangeError`, which is what dagre's own recursion throws once a chain is too
 * long for its stack - `ranked` laying it out by hand instead, marked `ranksOnly`. Any other
 * error is not this function's to answer; it is thrown onward, the worker's own concern once it
 * reaches there (review fix round 2, New Important 1 - the worker was deciding this itself,
 * untested, until now).
 */
export function layoutOf(
  modules: readonly GraphModule[],
  flows: readonly GraphFlow[],
): { placed: Placed[]; ranksOnly: boolean } {
  try {
    return { placed: laidOut(modules, flows, {}), ranksOnly: false };
  } catch (error) {
    if (error instanceof RangeError) return { placed: ranked(modules, flows), ranksOnly: true };
    throw error;
  }
}
