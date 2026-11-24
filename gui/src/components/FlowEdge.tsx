import {
  BaseEdge,
  type Edge,
  EdgeLabelRenderer,
  type EdgeProps,
  getBezierPath,
  useStore,
} from "@xyflow/react";
import { useLayoutEffect, useReducer, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  type FlowData,
  type Point,
  type Size,
  STROKE,
  stateOf,
  tooltipSpot,
  windowPointOf,
} from "../lib/canvas";

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
          // the same tooltip rather than being a hole in the arrow, and the same panel on click.
          // That click needs no handler here: portalled out of the arrow's svg as the label is,
          // React still bubbles it through its own tree to the arrow's group, whose click opens
          // the panel - a handler here as well opened it twice. The keyboard reaches the panel
          // through that group too, which handles Enter and Space, so the label is left out of
          // the tab order rather than being a second stop on every arrow.
          onMouseEnter={() => data.onReached(id)}
          onMouseLeave={() => data.onReached(null)}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          {data.objects.length}
        </span>
      </EdgeLabelRenderer>
      {data.active && <Tooltip data={data} state={state} anchor={{ x: labelX, y: labelY }} />}
    </>
  );
}

/**
 * What the arrow carries, while the reader is on it, drawn outside the canvas (16:M11): a tooltip
 * inside React Flow's label layer is scaled with the canvas, twice its size at the greatest zoom,
 * and cut by the canvas's edge, the line listing its variables with it. It is
 * placed in the window instead (`tooltipSpot`), over the arrow's own middle as the viewport puts
 * it (`windowPointOf`), and kept in view; it is told where the arrow is again whenever the canvas
 * pans or zooms, the page scrolls or the window changes.
 */
function Tooltip({ data, state, anchor }: { data: FlowData; state: string; anchor: Point }) {
  const transform = useStore((store) => store.transform);
  const canvas = useStore((store) => store.domNode);
  // Drawn again where the page itself moves under it: scrolled, or the window resized.
  const [, moved] = useReducer((count: number) => count + 1, 0);
  useLayoutEffect(() => {
    window.addEventListener("scroll", moved, true);
    window.addEventListener("resize", moved);
    return () => {
      window.removeEventListener("scroll", moved, true);
      window.removeEventListener("resize", moved);
    };
  }, []);
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<Size | null>(null);
  // Measured where it is drawn, before the first paint: the place it takes depends on its size.
  useLayoutEffect(() => {
    const element = box.current;
    if (element === null) return;
    const measured = { width: element.offsetWidth, height: element.offsetHeight };
    setSize((was) =>
      was !== null && was.width === measured.width && was.height === measured.height
        ? was
        : measured,
    );
  });
  const corner = canvas === null ? { x: 0, y: 0 } : canvas.getBoundingClientRect();
  const spot =
    size === null
      ? { x: 0, y: 0 }
      : tooltipSpot(windowPointOf(anchor, transform, { x: corner.x, y: corner.y }), size, {
          width: window.innerWidth,
          height: window.innerHeight,
        });
  return createPortal(
    <div
      ref={box}
      className={`flow-tooltip ${state}`}
      role="tooltip"
      // The arrow points at this with aria-describedby, so reaching it by keyboard reads out what
      // is wrong rather than only that something is.
      id={data.tooltip}
      // Hidden until measured, so that it is never painted in a place meant for another size.
      style={{ left: spot.x, top: spot.y, visibility: size === null ? "hidden" : "visible" }}
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
    </div>,
    document.body,
  );
}
