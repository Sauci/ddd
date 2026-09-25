import type { ValuesReply } from "../api/types";
import { BOX, plotted } from "../lib/valuePlot";

export interface ValuesPlotViewProps {
  reply: ValuesReply;
  physical: boolean;
}

/** The numbers above, as a picture. One polyline per row with a marker at each point, the axis
 * named below and the object beside, and the declared limits ruled across where they fall inside
 * the drawn range - which is the one thing the table deliberately does not show (spec 4).
 *
 * `role="img"` with a name of its own: every number in here is in the table above, so a reader
 * who cannot see the drawing loses nothing by being told what it is rather than what it holds. */
export function ValuesPlotView({ reply, physical }: ValuesPlotViewProps) {
  const plot = plotted(reply, physical);
  const inside = BOX.height - BOX.top - BOX.bottom;
  return (
    <svg
      className="values-plot"
      viewBox={`0 0 ${BOX.width} ${BOX.height}`}
      role="img"
      aria-label={`${plot.yLabel} plotted against ${plot.xLabel === "" ? "its indices" : plot.xLabel}`}
    >
      <title>{`${reply.name}, drawn`}</title>
      {plot.rules.map((rule) => (
        <line
          key={rule.value}
          className="values-plot-rule"
          x1={BOX.left}
          x2={BOX.width - BOX.right}
          y1={rule.y}
          y2={rule.y}
        />
      ))}
      <line
        className="values-plot-axis"
        x1={BOX.left}
        x2={BOX.width - BOX.right}
        y1={BOX.top + inside}
        y2={BOX.top + inside}
      />
      {plot.ticks.map((tick) => (
        <text key={tick.label} className="values-plot-tick" x={tick.x} y={BOX.height - 8}>
          {tick.label}
        </text>
      ))}
      <text className="values-plot-side" x={4} y={BOX.top + 8}>
        {String(plot.high)}
      </text>
      <text className="values-plot-side" x={4} y={BOX.top + inside}>
        {String(plot.low)}
      </text>
      {plot.lines.map((line, index) => {
        // Keyed by the row's own index rather than `line.label`: a map's y axis is free to
        // repeat a reading (two rows, one label), and the index is unique regardless a label is
        // not.
        const last = line.points.at(-1);
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: a row is its own position in `plot.lines`
          <g key={index} className="values-plot-line">
            {line.points.length > 1 && (
              <polyline points={line.points.map((p) => `${p.x},${p.y}`).join(" ")} />
            )}
            {line.points.map((point, at) => (
              // Keyed the same way, and for the same reason: two points can legitimately land on
              // the same pixel (a flat line, or two rows crossing), where `${x},${y}` could not.
              // biome-ignore lint/suspicious/noArrayIndexKey: a point is its own position in `line.points`
              <circle key={at} cx={point.x} cy={point.y} r={2.5} />
            ))}
            {/* `last` is `undefined` only when `line.points` is empty, so this is the one
                condition that guards it - no `?? 0` fallback left for nothing to reach. */}
            {line.label !== "" && last !== undefined && (
              <text className="values-plot-row" x={BOX.width - BOX.right} y={last.y}>
                {line.label}
              </text>
            )}
          </g>
        );
      })}
      {/* The right-hand end of the bottom margin, not the left: the first tick sits at
          `x = BOX.left` too, which is where the brief itself first drew this label - and the
          last tick sits at this same right-hand `x` by the same construction, so sharing the
          ticks' own `y = BOX.height - 8` prints this name over the last reading instead (found
          by looking, not by reading the brief: `AxisA (Hz)` over `8000` on `ACurvePlotted`). A
          row of its own, one line above the ticks and still short of the axis line, is what the
          brief's fixed `BOX` leaves room for without moving anything Task 1 shipped. */}
      <text className="values-plot-name" x={BOX.width - BOX.right} y={BOX.height - 18}>
        {plot.xLabel}
      </text>
    </svg>
  );
}
