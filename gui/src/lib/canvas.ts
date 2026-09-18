/**
 * What the canvas draws, decided away from the screen that draws it.
 *
 * `GraphPage` used to hold these joins itself, where the frontend's 100 % gate does not reach -
 * so two of their fallbacks were unreachable and unnoticed, one of them able to put an absolute
 * path into an accessible name that spec 4.2 says the page never shows. They are pure functions
 * over the endpoint's answer, so they belong here with tests: the screen is left with the state
 * and the wiring, which Playwright covers.
 */

import { type Edge, MarkerType, type Node } from "@xyflow/react";
import type { KeyboardEvent } from "react";
import type { GraphDisagreement, GraphFlow, GraphModule, GraphReply } from "../api/types";
import { laidOut } from "./layout";
import { neighboursOf } from "./neighbours";

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

/** Every module as a node, where the layout puts it, with what its box has to draw. */
export function nodesOf(
  graph: GraphReply,
  positions: Readonly<Record<string, { x: number; y: number }>>,
  onOpen: (path: string) => void,
): ModuleNodeType[] {
  return laidOut(graph.modules, graph.flows, positions).map((at) => ({
    id: at.module.path,
    type: "module",
    position: { x: at.x, y: at.y },
    data: {
      name: at.module.name,
      loaded: at.module.loaded,
      errors: at.module.findings.error,
      warnings: at.module.findings.warning,
      onOpen,
      faded: false,
    },
  }));
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
