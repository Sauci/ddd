import { useState } from "react";
import type { PlanReply, ValuesReply } from "../api/types";
import {
  CURVE_CELL_PLAN,
  VALUES_AXIS,
  VALUES_BLOCK,
  VALUES_CURVE,
  VALUES_CURVE_B,
  VALUES_MAP,
  VALUES_SOFTWARE_LABEL,
  VALUES_VALUE_D,
} from "../stories/fixtures";
import { ValuesGridView } from "./ValuesGridView";

export default { title: "Components / ValuesGridView" };

interface Props {
  reply: ValuesReply;
  backTo: string;
  physical: boolean;
  editing?: { row: number; column: number; typed: string };
  plan?: PlanReply | null;
  refusal?: string | null;
  changesShown?: boolean;
  busy?: boolean;
}

/** The grid over one scenario's fixtures, with its own toggle, cell being typed into and Show
 * changes - kept as ValuesPage.tsx keeps them. */
function View({
  reply,
  backTo,
  physical: initialPhysical,
  editing: initialEditing,
  plan = null,
  refusal = null,
  changesShown: initialChangesShown = false,
  busy = false,
}: Props) {
  const [physical, setPhysical] = useState(initialPhysical);
  const [editing, setEditing] = useState(initialEditing ?? null);
  const [changesShown, setChangesShown] = useState(initialChangesShown);
  return (
    <ValuesGridView
      reply={reply}
      backTo={backTo}
      physical={physical}
      onPhysical={setPhysical}
      editing={editing}
      onEditing={setEditing}
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

export const AScalarInitStatedOnce = () => (
  <View reply={VALUES_CURVE_B} backTo="UserInterface" physical />
);

export const ACellMidChange = () => (
  <View
    reply={VALUES_CURVE}
    backTo="Controller"
    physical
    editing={{ row: 0, column: 2, typed: "7.5" }}
    plan={CURVE_CELL_PLAN}
    changesShown
  />
);

export const ARefusedCell = () => (
  <View
    reply={VALUES_MAP}
    backTo="Controller"
    physical={false}
    editing={{ row: 0, column: 0, typed: "200" }}
    refusal="200 does not fit into sint8 (-128 .. 127)"
  />
);

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

// Part 9's own story: the hint line under a writable grid, waiting for Ctrl-V - drawn straight
// from `ValuesGridView` rather than through `View`, since nothing here is mid-paste yet.
export function ATableWaitingForAPaste() {
  const [physical, setPhysical] = useState(true);
  return (
    <ValuesGridView
      reply={VALUES_MAP}
      backTo="Controller"
      physical={physical}
      editing={null}
      plan={null}
      refusal={null}
      changesShown={false}
      busy={false}
      onPhysical={setPhysical}
      onEditing={() => {}}
      onChangesShown={() => {}}
      onApply={() => {}}
      onBack={() => {}}
      onPaste={() => {}}
    />
  );
}
