import { useState } from "react";
import type { SettleReply, UnitsReply, VariableReply } from "../api/types";
import { outsideVocabulary, startingUnit } from "../lib/units";
import {
  AGREEING,
  DISAGREEING,
  FIXED_BY_TYPE,
  FREE_UNITS,
  NOTHING,
  ONE_FILE,
  VOCABULARY,
} from "../stories/fixtures";
import { VariablePanelView } from "./VariablePanelView";

export default { title: "Components / VariablePanelView" };

interface Props {
  variable: VariableReply;
  units: UnitsReply;
  preview: SettleReply | null;
  refusal?: string;
  typed?: string;
  note?: string | undefined;
  changesShown?: boolean;
  focusPicker?: boolean;
}

/** The panel over one scenario's fixtures, with its own draft and Show changes state.
 *
 * `typed` stays `undefined` until the story's `typed` prop seeds it or the reader edits the
 * field, exactly as VariablePanel.tsx's own state does: the field still shows the target unit
 * (`startingUnit`), but the picker's sections are narrowed only once something was actually
 * typed, never by the pre-filled value alone. */
function View({
  variable,
  units,
  preview,
  refusal,
  typed: initialTyped,
  note,
  changesShown: initialChangesShown = false,
  focusPicker = false,
}: Props) {
  const [typed, setTyped] = useState<string | undefined>(initialTyped);
  const [changesShown, setChangesShown] = useState(initialChangesShown);
  return (
    <VariablePanelView
      variable={variable}
      units={units}
      typed={typed ?? startingUnit(variable.declarations) ?? ""}
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={() => undefined}
      note={note}
      preview={preview}
      refusal={refusal ?? null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => undefined}
      busy={false}
      focusPicker={focusPicker}
      onClose={() => undefined}
    />
  );
}

export const Disagreeing = () => (
  <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} />
);

export const ChangesShown = () => (
  <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} changesShown />
);

export const PickerOpen = () => (
  <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} focusPicker />
);

export const TypedOutsideVocabulary = () => (
  <View
    variable={DISAGREEING}
    units={VOCABULARY}
    preview={null}
    typed="RPM"
    note={outsideVocabulary(VOCABULARY, "RPM") ? "Not one of this project's units" : undefined}
  />
);

export const FixedByType = () => (
  <View
    variable={FIXED_BY_TYPE}
    units={FREE_UNITS}
    preview={null}
    refusal="the declaration of 'ValueA' in sensor_hub.ddd.json names the type 'Speed_t', which fixes its unit"
  />
);

export const Agreeing = () => <View variable={AGREEING} units={FREE_UNITS} preview={NOTHING} />;

export const RefusedAsStale = () => (
  <View
    variable={DISAGREEING}
    units={FREE_UNITS}
    preview={null}
    refusal="A file changed on disk, so nothing was written. The panel now shows the files as they are."
  />
);
