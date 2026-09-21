import { useState } from "react";
import type { SettleReply, VariableReply } from "../api/types";
import { DISAGREEING, MIXED_KINDS, PREVIEW_CONVERSION } from "../stories/fixtures";
import { VariableKeysTable } from "./VariableKeysTable";

export default { title: "Components / VariableKeysTable" };

interface Props {
  variable: VariableReply;
  preview?: SettleReply | null;
  initialSelected: string | undefined;
}

/** The table over one scenario's fixtures, holding which row is open itself, as VariablePanel
 * will (Task 6). */
function View({ variable, preview = null, initialSelected }: Props) {
  const [selected, setSelected] = useState<string | undefined>(initialSelected);
  return (
    <VariableKeysTable
      variable={variable}
      preview={preview}
      selected={selected}
      onSelect={setSelected}
    />
  );
}

/** The unit row disagreeing and selected, beside a preview that marks Controller's conversion
 * "will change" too. */
export const WithDisagreement = () => (
  <View variable={DISAGREEING} preview={PREVIEW_CONVERSION} initialSelected="unit" />
);

export const NothingSelected = () => <View variable={DISAGREEING} initialSelected={undefined} />;

/** Pump's cell reads "not on a parameter": dimensions belongs to SensorHub's measurement alone. */
export const MixedKinds = () => <View variable={MIXED_KINDS} initialSelected="dimensions" />;
