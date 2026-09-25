# Plotting an object's values

- **Part:** 10 of the GUI work, the last third of milestone 5
- **Status:** design approved; to be planned
- **Builds on:** [`2026-09-23-gui-values-design.md`](2026-09-23-gui-values-design.md) and
  [`2026-09-24-gui-paste-design.md`](2026-09-24-gui-paste-design.md), shipped as parts 8 and 9

## 1 Why

Nine parts have each added a way to **change** something. Not one has added a way to **see** it. A
reader opens `CurveA`, reads `12, 9, 8, 7.5, 7, 6.5`, and imagines the line.

Part 9 sharpened the case rather than softening it. A paste writes twenty-four values in a single
action, and the one failure it deliberately does not catch is a block built against a different
axis: its header is discarded unread, and §5.1 of that spec says the preview is what catches it.
But a preview shows changed *lines*. A curve that suddenly bends the wrong way is invisible in a
table of numbers and obvious in a picture of them.

This part draws the picture. It changes nothing: the grid still edits, the paste still fills, and
the plot is for looking at.

## 2 What it is not

Settled before the design, so that the design stays small:

- **Not draggable.** A point cannot be grabbed to change a value. Dragging needs pointer capture,
  snapping to a raw count the datatype can hold, a rule for crossing the limits, and a preview
  that reads sensibly while the pointer is still down — a part of its own. The grid already edits
  well; what the tool cannot do at all is show.
- **Not a surface, and not a heatmap.** A map is drawn as a family of curves (§3). A projected
  surface hand-rolled in SVG needs hidden-line removal, a projection, and a way to rotate it
  before it is useful at all.
- **No zoom, no pan, no export.** And no second way to reach it: the plot is where the grid is.

## 3 What gets drawn

**A polyline per row, with a marker at each point**, under the grid it belongs to.

| Object | Lines | Over |
| --- | --- | --- |
| `CurveA` | 1 | `AxisA`, six breakpoints |
| `MapA` | 4, one per `AxisB` row, labelled with its reading: `0`, `30`, `70`, `100` | `AxisA` |
| `BlockA` | 1 | indices `0 … 7`, having no axis at all |
| `AxisA` | 1 | indices `0 … 5`, an axis being its own breakpoints |

**The x positions are proportional to the breakpoints, never evenly spaced.** This is the detail
most easily got wrong: `AxisA` reads `0, 800, 1600, 3200, 4800, 8000`, so its gaps are 800, 800,
1600, 1600 and 3200. Spacing those evenly draws a curve that is not the curve. Where there is no
axis, indices are evenly spaced, because they are.

The labels are the ones the grid already computes — `AxisA (Hz)` along the bottom and
`CurveA (ms)` up the side — and both drop their unit in raw counts, exactly as the grid's own
headers do. The plot follows the Physical/Raw toggle and adds no control of its own.

## 4 The vertical range

**The values set it; the declared limits are drawn as lines where they fall inside it.**

Part 8 shows an object's limits and deliberately neither enforces nor marks them: a value outside
them is stored rather than refused, because nothing in `ddd check` weighs an init against them.
The plot is the one place that surprise can be made visible without changing what is written.

Scaling to the limits instead was rejected: they are usually far wider than real calibration
values — `CurveA` is `0 … 655.35` around values of 6.5 to 12 — so the shape the plot exists to
show would collapse into a flat line near the bottom.

Measured, in `examples/demo`, which is where the rule earns its detail:

| Object | Values | Limits | Drawn |
| --- | --- | --- | --- |
| `CurveA` | 6.5 … 12 | `0 … 655.35` | neither — the ordinary case |
| `MapA` | 3 … 16 | `-64 … 63.5` | neither |
| `BlockA` | 0 … 255 | `0 … 255` | **both, exactly at the extremes** |
| `AxisA` | 0 … 8000 | `0 … 8000` | **both, exactly at the extremes** |

**So the drawn range is padded by a twentieth of itself above and below the values.** Without
that, `BlockA`'s two limit lines land on the frame's own edges, where a line is clipped to half
its width or lost to the border. The padding is what makes "drawn where it falls inside" mean
something for the two objects in the demo where a limit falls inside at all.

**A range of zero is a real case, not a hypothetical.** `CurveB` states `init: 200` once, so every
value reads 100 % and the range is empty; a naive scale divides by zero. It draws as a flat line
across the middle, the range taken as **the value plus and minus a twentieth of itself** — for
`CurveB`, 95 to 105 — and a limit is drawn only if it falls within that span. `CurveB`'s upper
limit of 127.5 does not, which is right, because nothing about that object is near its limit. A
value of exactly zero, which an absent init gives every element, takes a span of **-1 to 1**,
there being no proportion of zero to take.

## 5 Where it lives

`ValuesGridView` draws it between the table and the offer, so that the offer — the sentence,
`Show changes` and `Apply` — stays at the foot where a reader's hand already goes, and the picture
sits against the numbers it draws.

**No screen change and no server change.** `ValuesReply` already carries the values, each axis's
breakpoints and conversion, the units and the limits. This is the first part since the walking
skeleton that touches no Python at all.

- `gui/src/lib/valuePlot.ts` (new), pure: a reply and the physical flag in, geometry out — the
  points of each line, the ticks, and which limits fall in frame. Everything that can be
  arithmetically wrong lives here, under the 100 % gate.
- `gui/src/components/ValuesPlotView.tsx` (new): the SVG, drawn from that geometry and holding no
  state. One fixed `viewBox` scaled to the width it is given, so the drawing is resolution-free and
  a screenshot of it is stable. `role="img"` with a label naming the object and its axis; **no
  `biome-ignore` for an a11y rule**, as everywhere else.
- `gui/src/components/ValuesGridView.tsx`: renders it, and passes the `physical` flag it already
  has.

The page has **no charting dependency and no hand-written SVG today** — `@xyflow/react` draws the
canvas and nothing else vectors. This is the first, and it stays hand-rolled: the no-new-dependency
rule has held since part 1.

## 6 What a grid without a plot looks like

- An object whose init is **text** has no grid, so it has no plot.
- A **shapeless** object has no grid either.
- A **read-only** grid still plots. Seeing is not changing, and an object nothing produces is
  exactly one a reader may want to look at.
- A shape of **one element** draws a marker and no line.

## 7 Testing

- **Vitest at 100 % of lines and branches over `gui/src/lib/valuePlot.ts`**, which is where the
  arithmetic is: proportional spacing against `AxisA`'s uneven gaps, the padded range, a limit in
  frame and a limit out of it, the zero range, the single point, and a map's four lines.
- **Stories and their screenshots** for the drawing, because a picture is the only thing that
  shows a plot is visibly wrong: a curve, a map's family, a value block over indices, `CurveB`'s
  flat line, `BlockA` with both limits drawn, and a curve in raw counts.
- **One journey**: open `CurveA` and assert the polyline's own `points`, so the page is proved to
  draw the numbers it holds rather than something that merely looks like a plot.
- **No Vitest test for a component or a screen**, as since part 1.
- No existing screenshot reference may change except the `ValuesGridView` ones that draw a grid,
  which gain a plot. There are twelve; `a-text-init` draws no grid, so **eleven** move.
