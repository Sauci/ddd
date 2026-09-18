import {
  BaseEdge,
  type Edge,
  EdgeLabelRenderer,
  type EdgeProps,
  getBezierPath,
} from "@xyflow/react";
import { type FlowData, STROKE, stateOf } from "../lib/canvas";

// The custom edge always carries our own data; EdgeProps types it optional only because an edge
// in general need not have any.
type Props = EdgeProps<Edge<FlowData>> & { data: FlowData };

/** One producing-consuming pair: a curve coloured by the worst thing its two ends disagree on. */
export function FlowEdge({
  id,
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
  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={markerEnd}
        className={data.faded ? "faded" : ""}
        style={{ stroke: STROKE[state], strokeWidth: state === "agreed" ? 1.5 : 2 }}
      />
      <EdgeLabelRenderer>
        <span
          className={`flow-label ${state}`}
          data-faded={data.faded}
          // The arrow's own group carries the sentence a reader hears (`ariaLabel`, built in
          // lib/canvas.ts); this is the picture of it, and saying it twice helps nobody.
          aria-hidden="true"
          // It sits on the middle of the curve, over the very stroke a reader aims at: it opens
          // the same tooltip rather than being a hole in the arrow, and the same panel on click -
          // the keyboard reaches that through the arrow's own group instead, which already
          // handles Enter and Space, so the label itself is left out of the tab order rather
          // than given a click handler of its own to reach by keyboard, which would be a second
          // stop on every arrow.
          onClick={() => data.onOpen(id)}
          onMouseEnter={() => data.onReached(id)}
          onMouseLeave={() => data.onReached(null)}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          {data.objects.length}
        </span>
        {data.active && (
          <div
            className={`flow-tooltip ${state}`}
            role="tooltip"
            // The arrow points at this with aria-describedby, so reaching it by keyboard reads
            // out what is wrong rather than only that something is.
            id={data.tooltip}
            style={{ transform: `translate(-50%, -100%) translate(${labelX}px, ${labelY - 12}px)` }}
          >
            <p className="objects">{data.objects.join(", ")}</p>
            {data.disagreements.length > 0 && (
              <ul>
                {data.disagreements.map((disagreement) => (
                  <li key={`${disagreement.check} ${disagreement.object} ${disagreement.message}`}>
                    <span className="flow-check">{disagreement.check}</span> {disagreement.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </EdgeLabelRenderer>
    </>
  );
}
