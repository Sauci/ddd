import { type ReactNode, useState } from "react";
import type { PlanReply, ValuesReply } from "../api/types";
import type { TypedCell } from "../lib/objectValues";
import { withTyped } from "../lib/typedCells";
import { holdOf } from "../lib/valuesHold";
import {
  CURVE_CELL_PLAN,
  CURVE_CELLS_PLAN,
  VALUES_AXIS,
  VALUES_BLOCK,
  VALUES_BLOCK_PAST_2_53,
  VALUES_BLOCK_WIDE,
  VALUES_CURVE,
  VALUES_CURVE_B,
  VALUES_MAP,
  VALUES_SOFTWARE_LABEL,
  VALUES_VALUE_D,
} from "../stories/fixtures";
import { Banner } from "../ui/Banner";
import { UndoStripView } from "./UndoStripView";
import { ValuesGridView } from "./ValuesGridView";
import { ValuesPlotView } from "./ValuesPlotView";

export default { title: "Components / ValuesGridView" };

interface Props {
  reply: ValuesReply;
  backTo: string;
  physical: boolean;
  typed?: TypedCell[];
  plan?: PlanReply | null;
  refusal?: string | null;
  changesShown?: boolean;
  busy?: boolean;
  banner?: ReactNode;
}

/** The grid over one scenario's fixtures, with its own toggle, cells typed into and Show changes
 * - kept as ValuesPage.tsx keeps them. */
function View({
  reply,
  backTo,
  physical: initialPhysical,
  typed: initialTyped = [],
  plan = null,
  refusal = null,
  changesShown: initialChangesShown = false,
  busy = false,
  banner,
}: Props) {
  const [physical, setPhysical] = useState(initialPhysical);
  const [typed, setTyped] = useState<readonly TypedCell[]>(initialTyped);
  const [changesShown, setChangesShown] = useState(initialChangesShown);
  return (
    <ValuesGridView
      reply={reply}
      backTo={backTo}
      banner={banner}
      physical={physical}
      onPhysical={setPhysical}
      typed={typed}
      onTyped={(cell) => setTyped((held) => withTyped(held, cell))}
      plan={plan}
      refusal={refusal}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      busy={busy}
      onApply={() => undefined}
      onBack={() => undefined}
      onPaste={() => undefined}
    />
  );
}

export const ACurveAgainstItsAxis = () => (
  <View reply={VALUES_CURVE} backTo="Controller" physical />
);

export const ACurveInRawCounts = () => (
  <View reply={VALUES_CURVE} backTo="Controller" physical={false} />
);

export const AMapWithBothHeaders = () => <View reply={VALUES_MAP} backTo="Controller" physical />;

export const AnAxisOnItsOwn = () => <View reply={VALUES_AXIS} backTo="Controller" physical />;

export const AValueBlockOverIndices = () => (
  <View reply={VALUES_BLOCK} backTo="UserInterface" physical />
);

// Each field as wide as its column's longest number: 123456789 and 4000000000 whole, where fields
// of one width showed 123456 and 400000, smaller numbers than the ones held.
export const ABlockOfWideNumbers = () => (
  <View reply={VALUES_BLOCK_WIDE} backTo="UserInterface" physical />
);

export const AScalarInitStatedOnce = () => (
  <View reply={VALUES_CURVE_B} backTo="UserInterface" physical />
);

export const ACellMidChange = () => (
  <View
    reply={VALUES_CURVE}
    backTo="Controller"
    physical
    typed={[{ row: 0, column: 2, typed: "7.5", physical: true }]}
    plan={CURVE_CELL_PLAN}
    changesShown
  />
);

export const ARefusedCell = () => (
  <View
    reply={VALUES_MAP}
    backTo="Controller"
    physical={false}
    typed={[{ row: 0, column: 0, typed: "200", physical: false }]}
    refusal="200 does not fit into sint8 (-128 .. 127)"
  />
);

// Three of CurveA's elements typed 13, 14 and 15 ms and held together: each field shows what was
// typed into it, and one sentence, one preview and one Apply cover all three (16:I3).
export const ThreeCellsTypedAsOneChange = () => (
  <View
    reply={VALUES_CURVE}
    backTo="Controller"
    physical
    typed={[13, 14, 15].map((value, column) => ({
      row: 0,
      column,
      typed: String(value),
      physical: true,
    }))}
    plan={CURVE_CELLS_PLAN}
    changesShown
  />
);

// Part 17's own: ACellMidChange's 7.5 ms applied, its edit written and answered, its analysis not
// landed yet. The server still answers the values from before it, and the grid holds what it wrote
// (`holdOf`, `valuesShown`) - the undo offered beside the name, the findings said to be updating
// where they are listed.
export function AnAppliedValueHeld() {
  const [physical, setPhysical] = useState(true);
  return (
    <ValuesGridView
      reply={holdOf(2, VALUES_CURVE, { cell: { row: 0, column: 2 }, raw: 750 }).after}
      updating
      backTo="Controller"
      undoStrip={
        <UndoStripView
          label="Undo element 3 of CurveA"
          open={false}
          onOpen={() => {}}
          preview={null}
          changesShown={false}
          onChangesShown={() => {}}
          onUndo={() => {}}
          refusal={null}
          busy={false}
        />
      }
      physical={physical}
      typed={[]}
      plan={null}
      refusal={null}
      changesShown={false}
      busy={false}
      onPhysical={setPhysical}
      onTyped={() => {}}
      onChangesShown={() => {}}
      onApply={() => {}}
      onBack={() => {}}
      onPaste={() => {}}
    />
  );
}

// Spec 6's own list, beyond the brief's: an absent init greyed, and a grid nothing produces.

export const AnAbsentInitGreyed = () => <View reply={VALUES_VALUE_D} backTo="SensorHub" physical />;

// No object in examples/demo answers with `file: null`, so this is BlockA's own reply with its
// producing declaration taken away - a story drawing its own props, not a server's real answer.
// `owner` goes with it: the analysis names no owner for a name nothing produces, and that is
// what tells this grid from the one two producers leave, which keeps its owner and its numbers.
export const AReadOnlyGrid = () => (
  <View reply={{ ...VALUES_BLOCK, file: null, owner: null }} backTo="UserInterface" physical />
);

// The fourth and last `stated`, with no picture until now: a text init draws no grid at all.
export const ATextInit = () => <View reply={VALUES_SOFTWARE_LABEL} backTo="Controller" physical />;

// Nor does a block holding a whole number past 2^53: its numbers reach the page as the doubles
// nearest them, and a grid drawing those would offer them as the ones written.
export const ABlockTheGridCannotShow = () => (
  <View reply={VALUES_BLOCK_PAST_2_53} backTo="UserInterface" physical />
);

// Part 9's own story: the hint line under a writable grid, waiting for Ctrl-V - drawn straight
// from `ValuesGridView` rather than through `View`, since nothing here is mid-paste yet. CurveA
// rather than MapA, so its singular "Paste 1 row of 6" is a picture of its own rather than one
// AMapWithBothHeaders' updated picture already shows.
export function ATableWaitingForAPaste() {
  const [physical, setPhysical] = useState(true);
  return (
    <ValuesGridView
      reply={VALUES_CURVE}
      backTo="Controller"
      physical={physical}
      typed={[]}
      plan={null}
      refusal={null}
      changesShown={false}
      busy={false}
      onPhysical={setPhysical}
      onTyped={() => {}}
      onChangesShown={() => {}}
      onApply={() => {}}
      onBack={() => {}}
      onPaste={() => {}}
    />
  );
}

// Part 19c's own: CurveA's grid as its page keeps it once the read of the project's next
// revision failed (`useKept`, spec 2026-10-21 §5) - the last grid read, under the server's own
// sentence for a request it failed on, which the page draws under the heading (`banner`).
export const AGridKeptUnderAFailedRead = () => (
  <View
    reply={VALUES_CURVE}
    backTo="Controller"
    physical
    banner={
      <Banner tone="error">
        ddd gui failed on this request; the terminal it runs in shows why
      </Banner>
    }
  />
);

// Part 10's own stories: the plot alone rather than the whole grid, since a grid's own picture
// is already the ones above - `View` wraps `ValuesGridView`, these draw `ValuesPlotView` direct.

export const ACurvePlotted = () => <ValuesPlotView reply={VALUES_CURVE} physical />;

export const ACurvePlottedInRawCounts = () => (
  <ValuesPlotView reply={VALUES_CURVE} physical={false} />
);

export const AMapAsAFamilyOfCurves = () => <ValuesPlotView reply={VALUES_MAP} physical />;

// BlockA's own limits, 0 and 255, are its own extremes (spec 4) - the one fixture in this file
// where both draw, ruled just inside the frame rather than clipped to its edge.
export const ABlockPlottedWithBothLimits = () => <ValuesPlotView reply={VALUES_BLOCK} physical />;

export const AFlatLineStatedOnce = () => <ValuesPlotView reply={VALUES_CURVE_B} physical />;

// ValueD's absent init reads zero throughout, and its lower limit is zero too - the flat line and
// the limit line share one y, which is correct rather than a coincidence to hide.
export const AnAbsentInitAtZero = () => <ValuesPlotView reply={VALUES_VALUE_D} physical />;
