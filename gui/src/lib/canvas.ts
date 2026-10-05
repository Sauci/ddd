/**
 * What the canvas draws, decided away from the screen that draws it.
 *
 * `GraphPage` used to hold these joins itself, where the frontend's 100 % gate does not reach -
 * so two of their fallbacks were unreachable and unnoticed, one of them able to put an absolute
 * path into an accessible name that spec 4.2 says the page never shows. They are pure functions
 * over the endpoint's answer, so they belong here with tests: the screen is left with the state
 * and the wiring, which Playwright covers.
 */

import {
  type Edge,
  getViewportForBounds,
  MarkerType,
  type Node,
  type NodeHandle,
  Position,
  type Viewport,
} from "@xyflow/react";
import type { KeyboardEvent } from "react";
import type { GraphDisagreement, GraphFlow, GraphModule, GraphReply } from "../api/types";
import type { Placed } from "./layout";
import { neighboursOf } from "./neighbours";
import { NODE_HEIGHT, NODE_WIDTH } from "./nodeSize";

/** React Flow's own default, given explicitly to `<ReactFlow>` so `openingViewport` always
 * agrees with what it is deciding against (review fix round 1, Ruling T10-2). Pinned by the
 * literal 0.5 in canvas.test.ts (review fix round 2, New Important 2). */
export const MIN_ZOOM = 0.5;
/** React Flow's own default `maxZoom`, which `<ReactFlow>` is left to use: `openingViewport` caps
 * its fit at the same, so the view it opens on is one React Flow itself would allow. Pinned by
 * the zoom of 2 in canvas.test.ts's capped fit. */
const MAX_ZOOM = 2;

/**
 * Everything the canvas hands one module's node.
 *
 * `onOpen` takes the module's path - the node's own id - because that is what the component page
 * is addressed by; the path is never shown, only the name is. `faded` is written by the canvas
 * and read by the stylesheet, so that hovering or searching can dim what is not a neighbour.
 */
export interface ModuleData extends Record<string, unknown> {
  name: string;
  loaded: boolean;
  errors: number;
  warnings: number;
  onOpen: (path: string) => void;
  faded: boolean;
}

/**
 * Everything the canvas hands one arrow.
 *
 * `source` and `target` are the two modules' names, not their paths: they are what the arrow
 * says out loud, and a path is never shown. `disagreements` rides along for the tooltip, which
 * is open while `active` and carries `tooltip` as its id, the one the arrow points at with
 * `aria-describedby`. `onReached` is the same callback the arrow's own group calls, so that the
 * label sitting on the middle of the curve opens the tooltip exactly as the curve itself does;
 * a click on the label reaches the group's own click through React's tree, and opens the panel.
 */
export interface FlowData extends Record<string, unknown> {
  source: string;
  target: string;
  objects: readonly string[];
  severity: GraphFlow["severity"];
  disagreements: readonly GraphDisagreement[];
  tooltip: string;
  onReached: (id: string | null) => void;
  faded: boolean;
  active: boolean;
}

export type ModuleNodeType = Node<ModuleData, "module">;
/** An arrow always carries our own data; `Edge` types it optional only because an edge may not. */
export type FlowEdgeType = Edge<FlowData, "flow"> & { data: FlowData };

/** The state a reader hears: the arrow is in error, in warning, or its two ends agree. */
export function stateOf(severity: FlowData["severity"]): "error" | "warning" | "agreed" {
  return severity === "error" || severity === "warning" ? severity : "agreed";
}

/** What each state paints with; `info` and `ignore` leave the arrow plain, as spec 4.4 says. */
export const STROKE: Record<ReturnType<typeof stateOf>, string> = {
  error: "var(--error)",
  warning: "var(--warning)",
  agreed: "var(--rule)",
};

/**
 * A layout's positions with the reader's saved ones laid over them: a saved position wins for
 * its module, and every other one is left exactly where it was placed - the same substitution
 * `laidOut` makes when it is given the saved positions directly (spec 5.1), done here instead
 * because the worker that makes the layout (`gui/src/app/layoutWorker.ts`) always asks `laidOut`
 * with none, so that its answer does not depend on which browser asks and can be reused for it
 * unchanged. A saved position for a module the placement does not carry changes nothing, the
 * same way `laidOut` itself ignores one for a module that no longer exists.
 */
export function withSavedPositions(
  placed: readonly Placed[],
  saved: Readonly<Record<string, { x: number; y: number }>>,
): Placed[] {
  return placed.map((at) => {
    const position = saved[at.module.path];
    return position === undefined ? at : { ...at, x: position.x, y: position.y };
  });
}

/** A handle's own size, React Flow's own default for the `Handle` `ModuleNode.tsx` draws (its
 * CSS, `@xyflow/react/dist/style.css`'s `.react-flow__handle`, not this page's own - nothing
 * here can read that file's `width`/`height` back as a value, so this states it instead, the
 * same way `.module`'s own CSS states `NODE_WIDTH`/`NODE_HEIGHT` back in a comment). Pinned by
 * the literal 6 in canvas.test.ts. */
const HANDLE_SIZE = 6;

/**
 * The two handles every module node carries from the moment it is first built - a target on the
 * left, a source on the right, `ModuleNode.tsx`'s own two `<Handle>`s - derived from the node's
 * own size and the handle's: centred on each vertical edge, `HANDLE_SIZE` square. Review fix
 * round 2, Finding 7: without these (and `measured`, `nodesOf`'s own doc), React Flow cannot
 * compute a node's `handleBounds` without first mounting it to measure the DOM - which it does
 * for every node still missing them, regardless of `onlyRenderVisibleElements`, the one render
 * `onlyRenderVisibleElements` is meant to spare a reader at all above `VISIBLE_ONLY_ABOVE`.
 */
function handlesOf(): NodeHandle[] {
  const y = (NODE_HEIGHT - HANDLE_SIZE) / 2;
  return [
    {
      type: "target",
      position: Position.Left,
      x: -HANDLE_SIZE / 2,
      y,
      width: HANDLE_SIZE,
      height: HANDLE_SIZE,
    },
    {
      type: "source",
      position: Position.Right,
      x: NODE_WIDTH - HANDLE_SIZE / 2,
      y,
      width: HANDLE_SIZE,
      height: HANDLE_SIZE,
    },
  ];
}

/**
 * Every placed module as a node, its data taken from `modules` as they are now rather than as
 * they were when `placed` was made: a revision whose shape is unchanged keeps its placement
 * (`shapeOf`, `gui/src/lib/shape.ts`) while its nodes still take the new counts and `loaded`, so
 * a module never moves on screen because only its findings changed. A module `modules` no longer
 * carries draws no node; one `placed` does not carry yet - a shape just grown, its fresh layout
 * still being made - draws none either, until the layout that places it arrives.
 *
 * `measured` and `handles` are given from the start, every box the same known size
 * (`NODE_WIDTH`/`NODE_HEIGHT`, `.module`'s own CSS) and the same two handles
 * (`handlesOf`) - review fix round 2, Finding 7: without them, React Flow mounts every node at
 * least once to measure it regardless of whether `onlyRenderVisibleElements` would otherwise
 * have culled it, which at 3,333 modules peaked the DOM at all of them and cost two long tasks
 * over 100 ms; with them, confirmed by hand, the peak falls to the few actually in view and
 * neither task remains.
 */
export function nodesOf(
  placed: readonly Placed[],
  modules: readonly GraphModule[],
  onOpen: (path: string) => void,
): ModuleNodeType[] {
  const byPath = new Map(modules.map((module) => [module.path, module]));
  return placed.flatMap((at) => {
    const module = byPath.get(at.module.path);
    if (module === undefined) return [];
    return [
      {
        id: module.path,
        type: "module" as const,
        position: { x: at.x, y: at.y },
        measured: { width: NODE_WIDTH, height: NODE_HEIGHT },
        handles: handlesOf(),
        data: {
          name: module.name,
          loaded: module.loaded,
          errors: module.findings.error,
          warnings: module.findings.warning,
          onOpen,
          faded: false,
        },
      },
    ];
  });
}

/** How far apart, as a fraction of the viewport, a fitted graph is left from its own edge - the
 * same padding React Flow's own `fitView` would otherwise default to, so `openingViewport`
 * decides in the same terms it does. Pinned by the literal 0.1 in canvas.test.ts. */
const FIT_PADDING = 0.1;

/** The smallest rectangle containing every placed module's own box. */
function boundsOf(placed: readonly Placed[]): {
  x: number;
  y: number;
  width: number;
  height: number;
} {
  const left = Math.min(...placed.map((at) => at.x));
  const top = Math.min(...placed.map((at) => at.y));
  const right = Math.max(...placed.map((at) => at.x + NODE_WIDTH));
  const bottom = Math.max(...placed.map((at) => at.y + NODE_HEIGHT));
  return { x: left, y: top, width: right - left, height: bottom - top };
}

/**
 * Where the canvas should open, and what `Fit` returns it to - review fix round 2, item 1
 * (continuing round 1's Ruling T10-2, which this replaces): applied as `defaultViewport` on React
 * Flow's first mount, with `fitView` never asked for (`GraphPage`'s `fitView={false}`), rather
 * than raced against it: `fitView` does not resolve until a `ResizeObserver` delivers every
 * node's own measured size - a later task, not a guarantee about which of the two runs first
 * (confirmed by hand: with another page brought to the front right after the click, the order
 * reversed in most openings on a fresh server).
 *
 * `placed` is the placement *as drawn* - the reader's saved positions already laid over it
 * (`withSavedPositions`), not the bare layout - so a module the reader moved is where this
 * decides from, the same placement the canvas itself draws. `null` only when there is truly
 * nothing to show: no module placed yet, or the canvas not yet measured.
 *
 * It is either the fit - every module in view, centred, `fitView`'s own result had it run - when
 * the whole placement fits at `minZoom` or above, or, when it would not, the first rank instead:
 * the modules at the lowest x anyone in `placed` sits at, the leftmost column the layout makes,
 * centred at exactly `minZoom`. A layout wide enough for the first to fail (confirmed on
 * 10000-many-clean, a long, shallow chain) leaves the *fitted*, clamped middle with no module in
 * it at all - every module sits along one edge, not spread through the centre - which the first
 * rank, by construction, never can.
 *
 * `size` is the canvas element's own measured box; `getViewportForBounds` is React Flow's own
 * arithmetic for fitting a rectangle of world units into one of screen pixels, reused here so
 * this answers in the same coordinate space `fitView` itself would, rather than a second,
 * independently written formula that could disagree with it.
 */
export function openingViewport(
  placed: readonly Placed[],
  size: { width: number; height: number },
  minZoom: number,
): Viewport | null {
  if (placed.length === 0 || size.width <= 0 || size.height <= 0) return null;
  const bounds = boundsOf(placed);
  const natural = getViewportForBounds(
    bounds,
    size.width,
    size.height,
    0,
    Number.POSITIVE_INFINITY,
    FIT_PADDING,
  );
  if (natural.zoom >= minZoom) {
    return getViewportForBounds(bounds, size.width, size.height, minZoom, MAX_ZOOM, FIT_PADDING);
  }
  const leftmost = Math.min(...placed.map((at) => at.x));
  const firstRank = placed.filter((at) => at.x === leftmost);
  return getViewportForBounds(
    boundsOf(firstRank),
    size.width,
    size.height,
    minZoom,
    minZoom,
    FIT_PADDING,
  );
}

/**
 * Every flow as an arrow, carrying the two modules' names rather than their paths.
 *
 * `onReached` is called with the arrow's id when the reader's pointer or keyboard arrives on it
 * and with `null` when it leaves, which is what opens and closes the tooltip. `onOpen` is called
 * with the id on a click, or on Enter or Space, which is what opens the panel beside the canvas
 * (spec 5.4). Both handlers ride in `domAttributes` because React Flow owns the group they
 * belong on, spreading it after its own `onClick` and `onKeyDown` there - so `onOpen`'s handlers
 * replace React Flow's click-to-select and its Enter, Space and Escape keyboard selection
 * outright, which costs this canvas nothing, since it never otherwise turns an edge "selected".
 * `ariaLabel` replaces the default that would otherwise announce the arrow as its two file paths;
 * `ariaRole` marks as a button only the arrow choosing it would open something on, spec 5.4's "a
 * red or orange arrow is a button" - one whose ends agree needs no role of its own.
 */
export function edgesOf(
  graph: GraphReply,
  onReached: (id: string | null) => void,
  onOpen: (id: string) => void,
): FlowEdgeType[] {
  const names = new Map(graph.modules.map((module) => [module.path, module.name]));
  return graph.flows.flatMap((flow, index) => {
    const source = names.get(flow.from);
    const target = names.get(flow.to);
    // React Flow draws no arrow whose two ends it has no node for, so a flow naming a module the
    // answer does not carry is dropped rather than left for the console to complain about.
    if (source === undefined || target === undefined) return [];
    const id = `${flow.from} -> ${flow.to}`;
    const tooltip = `flow-tooltip-${index}`;
    const opensPanel = flow.disagreements.some((disagreement) => disagreement.object !== null);
    return [
      {
        id,
        source: flow.from,
        target: flow.to,
        type: "flow",
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: STROKE[stateOf(flow.severity)],
          width: 18,
          height: 18,
        },
        ariaLabel: sentenceOf(source, target, flow.objects.length, stateOf(flow.severity)),
        // Only present when true: exactOptionalPropertyTypes makes `ariaRole: undefined` a type
        // error of its own, and would in any case still be a key React Flow's `??` falls back
        // past, drawing the group as a plain "img" while advertising a role that never applied.
        ...(opensPanel ? { ariaRole: "button" as const } : {}),
        domAttributes: {
          onMouseEnter: () => onReached(id),
          onMouseLeave: () => onReached(null),
          onFocus: () => onReached(id),
          onBlur: () => onReached(null),
          onClick: () => onOpen(id),
          onKeyDown: (event: KeyboardEvent) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            onOpen(id);
          },
          // What a reader hears the moment they reach the arrow: React Flow's own description
          // here only says how to select an edge, which this canvas does nothing with.
          "aria-describedby": tooltip,
        },
        data: {
          source,
          target,
          objects: flow.objects,
          severity: flow.severity,
          disagreements: flow.disagreements,
          tooltip,
          onReached,
          faded: false,
          active: false,
        },
      },
    ];
  });
}

/** The variables an arrow disagrees about, each once: what its panel is for. */
export function objectsInDisagreement(graph: GraphReply, id: string): string[] {
  const flow = graph.flows.find((entry) => `${entry.from} -> ${entry.to}` === id);
  const objects = (flow?.disagreements ?? []).flatMap((entry) =>
    entry.object === null ? [] : [entry.object],
  );
  return [...new Set(objects)].sort();
}

/** An arrow as its sentence begins: the module it leaves, then the one it reaches. */
export function flowTitle(graph: GraphReply, id: string): string {
  const flow = graph.flows.find((entry) => `${entry.from} -> ${entry.to}` === id);
  const name = (path: string) => graph.modules.find((module) => module.path === path)?.name;
  const source = flow === undefined ? undefined : name(flow.from);
  const target = flow === undefined ? undefined : name(flow.to);
  return source === undefined || target === undefined ? id : `${source} to ${target}`;
}

/** What one arrow says out loud: who sends how much to whom, and how the two ends get on. */
function sentenceOf(
  source: string,
  target: string,
  count: number,
  state: ReturnType<typeof stateOf>,
): string {
  return `${source} to ${target}: ${count} ${count > 1 ? "variables" : "variable"}, ${state}`;
}

/**
 * The modules that stay bright, or `null` when nothing dims the canvas.
 *
 * Hovering keeps a module and its direct neighbours; searching keeps every module whose name
 * contains the text, ignoring case; doing both keeps what both would keep, so that a search
 * narrowed down to one module still answers "and what does it talk to" when it is hovered.
 */
export function brightOf(
  modules: readonly GraphModule[],
  flows: readonly GraphFlow[],
  hovered: string | null,
  search: string,
): ReadonlySet<string> | null {
  const matching = matchesOf(modules, search);
  // A module the pointer was on when a revision took it away leaves no mouse-leave behind it,
  // so a hover that names nobody is dropped rather than dimming the whole canvas for good.
  const on = modules.some((module) => module.path === hovered) ? hovered : null;
  const near = on === null ? null : neighboursOf(on, flows);
  if (matching === null) return near;
  const found = new Set(matching.map((module) => module.path));
  if (near === null) return found;
  return new Set([...found].filter((path) => near.has(path)));
}

/** The module a search centres on: the first whose name contains the text, or none. */
export function firstMatch(modules: readonly GraphModule[], search: string): string | null {
  return matchesOf(modules, search)?.[0]?.path ?? null;
}

/** Every module whose name contains the text, ignoring case, or `null` when none was typed. */
function matchesOf(modules: readonly GraphModule[], search: string): GraphModule[] | null {
  const wanted = search.trim().toLowerCase();
  if (wanted === "") return null;
  return modules.filter((module) => module.name.toLowerCase().includes(wanted));
}

/**
 * The nodes with each module's fading brought up to date.
 *
 * A node whose state did not change is handed back as it was, so that React Flow re-renders the
 * few boxes a hover actually changed rather than all two hundred.
 */
export function fadedNodes(
  nodes: readonly ModuleNodeType[],
  bright: ReadonlySet<string> | null,
): ModuleNodeType[] {
  return nodes.map((node) => {
    const faded = bright !== null && !bright.has(node.id);
    return node.data.faded === faded ? node : { ...node, data: { ...node.data, faded } };
  });
}

/**
 * The arrows with their fading and their tooltip brought up to date, unchanged ones kept.
 *
 * An arrow is bright only while both of its ends are, which is spec 5.4 for a search - "every
 * arrow that does not join two modules still shown" - and, for a hover, every arrow that leaves
 * the neighbourhood.
 */
export function shownEdges(
  edges: readonly FlowEdgeType[],
  bright: ReadonlySet<string> | null,
  reached: string | null,
): FlowEdgeType[] {
  return edges.map((edge) => {
    const faded = bright !== null && !(bright.has(edge.source) && bright.has(edge.target));
    const active = edge.id === reached;
    if (edge.data.faded === faded && edge.data.active === active) return edge;
    return { ...edge, data: { ...edge.data, faded, active } };
  });
}
