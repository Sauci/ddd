import { useState } from "react";
import type { SettleReply, UnitsReply, VariableReply } from "../api/types";
import { outsideVocabulary, textOf } from "../lib/units";
import { labelOfRaw, limitsOf, limitsRaw, startingRaw } from "../lib/variableKeys";
import {
  AGREEING,
  DISAGREEING,
  FIXED_BY_TYPE,
  FREE_UNITS,
  MIXED_KINDS,
  NOTHING,
  ONE_FILE,
  PREVIEW_CONVERSION,
  PREVIEW_LIMITS,
  SHAPED,
  VOCABULARY,
} from "../stories/fixtures";
import { VariablePanelView } from "./VariablePanelView";

export default { title: "Components / VariablePanelView" };

interface Props {
  variable: VariableReply;
  units: UnitsReply;
  preview: SettleReply | null;
  /** The key whose chooser is open, or unopened when left out. */
  selected?: string;
  refusal?: string;
  /** The value the reader chose; the producer's is settled on until they do. */
  chosen?: string | null;
  changesShown?: boolean;
  pickerOpen?: boolean;
}

/** The panel over one scenario's fixtures, with its own selection, choice, draft and Show
 * changes state.
 *
 * As in VariablePanel.tsx: `typed` is `undefined` unless the reader is typing, so the field shows
 * the label of the value settled on (the producer's, `startingRaw`, until one is chosen), and the
 * chooser's sections are narrowed only by what is actually typed, never by the value shown. */
function View({
  variable,
  units,
  preview,
  selected: initialSelected,
  refusal,
  chosen: initialChosen,
  changesShown: initialChangesShown = false,
  pickerOpen = false,
}: Props) {
  const [selected, setSelected] = useState<string | undefined>(initialSelected);
  const [chosen, setChosen] = useState<string | null | undefined>(initialChosen);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [range, setRange] = useState<{ min: string; max: string }>(
    initialSelected === undefined
      ? { min: "", max: "" }
      : limitsOf(startingRaw(variable, initialSelected)),
  );
  const [changesShown, setChangesShown] = useState(initialChangesShown);
  const target =
    selected === undefined ? null : chosen === undefined ? startingRaw(variable, selected) : chosen;
  const select = (key: string | undefined) => {
    setSelected(key);
    setChosen(undefined);
    setTyped(undefined);
    setChangesShown(false);
    setRange(key === undefined ? { min: "", max: "" } : limitsOf(startingRaw(variable, key)));
  };
  const onRange = (next: { min: string; max: string }) => {
    setRange(next);
    setTyped(undefined);
    const raw = limitsRaw(next.min, next.max);
    if (raw !== null) setChosen(raw);
  };
  return (
    <VariablePanelView
      variable={variable}
      units={units}
      selected={selected}
      onSelect={select}
      typed={typed ?? (selected === undefined ? "" : labelOfRaw(variable, selected, target))}
      // Never the target: opening the list on the value settled on must still list everything,
      // not just the entries that happen to contain it (spec 5.3, and part 1's own journey).
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(raw) => {
        setChosen(raw);
        setTyped(undefined);
        if (selected === "limits") setRange(limitsOf(raw));
      }}
      onPickerClosed={() => setTyped(undefined)}
      range={range}
      onRange={onRange}
      note={
        selected === "unit" && outsideVocabulary(units, textOf(target ?? undefined))
          ? "Not one of this project's units"
          : undefined
      }
      preview={preview}
      refusal={refusal ?? null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => undefined}
      busy={false}
      focus={pickerOpen ? 1 : null}
      pickerTrigger={pickerOpen ? "focus" : "input"}
      onClose={() => undefined}
    />
  );
}

export const Disagreeing = () => (
  <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} selected="unit" />
);

export const NothingSelected = () => (
  <View variable={DISAGREEING} units={FREE_UNITS} preview={null} />
);

export const ChangesShown = () => (
  <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} selected="unit" changesShown />
);

export const PickerOpen = () => (
  <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} selected="unit" pickerOpen />
);

export const TypedOutsideVocabulary = () => (
  <View variable={DISAGREEING} units={VOCABULARY} preview={null} selected="unit" chosen='"RPM"' />
);

export const FixedByType = () => (
  <View
    variable={FIXED_BY_TYPE}
    units={FREE_UNITS}
    preview={null}
    selected="unit"
    refusal="the declaration of 'ValueA' in sensor_hub.ddd.json names the type 'Speed_t', which fixes its unit"
  />
);

export const Agreeing = () => (
  <View variable={AGREEING} units={FREE_UNITS} preview={NOTHING} selected="unit" />
);

export const RefusedAsStale = () => (
  <View
    variable={DISAGREEING}
    units={FREE_UNITS}
    preview={null}
    selected="unit"
    refusal="A file changed on disk, so nothing was written. The panel now shows the files as they are."
  />
);

export const ConversionChosen = () => (
  <View
    variable={DISAGREEING}
    units={FREE_UNITS}
    preview={PREVIEW_CONVERSION}
    selected="conversion"
    pickerOpen
  />
);

export const RangeTyped = () => (
  <View variable={SHAPED} units={FREE_UNITS} preview={PREVIEW_LIMITS} selected="limits" />
);

export const NameChosen = () => (
  <View variable={SHAPED} units={FREE_UNITS} preview={null} selected="input" pickerOpen />
);

export const NotOnThisKind = () => (
  <View variable={MIXED_KINDS} units={FREE_UNITS} preview={null} selected="dimensions" />
);
