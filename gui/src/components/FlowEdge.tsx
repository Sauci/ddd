import {
  BaseEdge,
  type Edge,
  EdgeLabelRenderer,
  type EdgeProps,
  getBezierPath,
} from "@xyflow/react";
import type { GraphDisagreement, GraphFlow } from "../api/types";

/**
 * Everything the canvas hands one arrow.
 *
 * `source` and `target` are the two modules' names, not their paths: they are what the label
 * says out loud, and a path is never shown. `disagreements` rides along for the tooltip.
 */
export interface FlowData extends Record<string, unknown> {
  source: string;
  target: string;
  objects: readonly string[];
  severity: GraphFlow["severity"];
  disagreements: readonly GraphDisagreement[];
  faded: boolean;
}

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

// The custom edge always carries our own data; EdgeProps types it optional only because an edge
// in general need not have any.
type Props = EdgeProps<Edge<FlowData>> & { data: FlowData };

/** One producing-consuming pair: a curve coloured by the worst thing its two ends disagree on. */
export function FlowEdge({
  data,
  // The canvas gives every arrow its head; `none` is svg's own way of saying an edge has none,
  // and is what an edge built without one would fall back to.
  markerEnd = "none",
  sourceX,
  sourceY,
  sourcePosition,
  targetX,
  targetY,
  targetPosition,
}: Props) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });
  const state = stateOf(data.severity);
  const count = data.objects.length;
  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={markerEnd}
        style={{ stroke: STROKE[state], strokeWidth: state === "agreed" ? 1.5 : 2 }}
      />
      <EdgeLabelRenderer>
        <span
          className={`flow-label ${state}`}
          data-faded={data.faded}
          // A bare span takes no name, so the label is announced as the one picture it is: the
          // count on its own says nothing, the whole sentence does.
          role="img"
          aria-label={`${data.source} to ${data.target}: ${count} ${
            count > 1 ? "variables" : "variable"
          }, ${state}`}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          {count}
        </span>
      </EdgeLabelRenderer>
    </>
  );
}
