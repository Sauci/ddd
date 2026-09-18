import { useState } from "react";
import type { SettleReply, UnitsReply, VariableReply } from "../api/types";
import { outsideVocabulary, startingUnit, unitLabel } from "../lib/units";
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
  /** The unit the reader chose; the owner's is settled on until they do. */
  chosen?: string | null;
  changesShown?: boolean;
  pickerOpen?: boolean;
}

/** The panel over one scenario's fixtures, with its own choice, draft and Show changes state.
 *
 * As in VariablePanel.tsx: `typed` is `undefined` unless the reader is typing, so the field shows
 * the label of the unit settled on (the owner's, `startingUnit`, until one is chosen), and the
 * picker's sections are narrowed only by what is actually typed, never by the unit shown. */
function View({
  variable,
  units,
  preview,
  refusal,
  chosen: initialChosen,
  changesShown: initialChangesShown = false,
  pickerOpen = false,
}: Props) {
  const [chosen, setChosen] = useState<string | null | undefined>(initialChosen);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [changesShown, setChangesShown] = useState(initialChangesShown);
  const target = chosen === undefined ? startingUnit(variable.declarations) : chosen;
  return (
    <VariablePanelView
      variable={variable}
      units={units}
      typed={typed ?? unitLabel(target)}
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(unit) => {
        setChosen(unit);
        setTyped(undefined);
      }}
      onPickerClosed={() => setTyped(undefined)}
      note={outsideVocabulary(units, target) ? "Not one of this project's units" : undefined}
      preview={preview}
      refusal={refusal ?? null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => undefined}
      busy={false}
      focusPicker={pickerOpen ? 1 : null}
      pickerTrigger={pickerOpen ? "focus" : "input"}
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
  <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} pickerOpen />
);

export const TypedOutsideVocabulary = () => (
  <View variable={DISAGREEING} units={VOCABULARY} preview={null} chosen="RPM" />
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
