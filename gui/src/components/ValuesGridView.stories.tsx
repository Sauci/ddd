import { useState } from "react";
import type { PlanReply, ValuesReply } from "../api/types";
import {
  CURVE_CELL_PLAN,
  VALUES_AXIS,
  VALUES_BLOCK,
  VALUES_CURVE,
  VALUES_CURVE_B,
  VALUES_MAP,
  VALUES_VALUE_D,
} from "../stories/fixtures";
import { ValuesGridView } from "./ValuesGridView";

export default { title: "Components / ValuesGridView" };

interface Props {
  reply: ValuesReply;
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
      physical={physical}
      onPhysical={setPhysical}
      editing={editing}
      onEditing={setEditing}
      onEntered={() => undefined}
      plan={plan}
      refusal={refusal}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      busy={busy}
      onApply={() => undefined}
      onBack={() => undefined}
    />
  );
}

export const ACurveAgainstItsAxis = () => <View reply={VALUES_CURVE} physical />;

export const ACurveInRawCounts = () => <View reply={VALUES_CURVE} physical={false} />;

export const AMapWithBothHeaders = () => <View reply={VALUES_MAP} physical />;

export const AnAxisOnItsOwn = () => <View reply={VALUES_AXIS} physical />;

export const AValueBlockOverIndices = () => <View reply={VALUES_BLOCK} physical />;

export const AScalarInitStatedOnce = () => <View reply={VALUES_CURVE_B} physical />;

export const ACellMidChange = () => (
  <View
    reply={VALUES_CURVE}
    physical
    editing={{ row: 0, column: 2, typed: "7.5" }}
    plan={CURVE_CELL_PLAN}
    changesShown
  />
);

export const ARefusedCell = () => (
  <View
    reply={VALUES_MAP}
    physical={false}
    editing={{ row: 0, column: 0, typed: "200" }}
    refusal="200 does not fit into sint8 (-128 .. 127)"
  />
);

// Spec 6's own list, beyond the brief's: an absent init greyed, and a grid nothing produces.

export const AnAbsentInitGreyed = () => <View reply={VALUES_VALUE_D} physical />;

// No object in examples/demo answers with `file: null`, so this is BlockA's own reply with its
// producing declaration taken away - a story drawing its own props, not a server's real answer.
export const AReadOnlyGrid = () => <View reply={{ ...VALUES_BLOCK, file: null }} physical />;
