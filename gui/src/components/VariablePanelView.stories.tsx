import { useState } from "react";
import type { PlanReply, SettleReply, UnitsReply, VariableReply } from "../api/types";
import { outsideVocabulary, textOf } from "../lib/units";
import { labelOfRaw, limitsNote, limitsOf, limitsRaw, startingRaw } from "../lib/variableKeys";
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
import type { Offer } from "./UnitPanelView";
import { VariablePanelView } from "./VariablePanelView";

export default { title: "Components / VariablePanelView" };

// The removal offer's own plans, local to this file rather than the shared fixtures module:
// both take SensorHub's declaration of ValueA out of sensor_hub.ddd.json (DISAGREEING and
// FIXED_BY_TYPE both declare it at component.interface[2]), the two scenarios differing only in
// what removalSentence then has left to say.

/** DISAGREEING's own SensorHub declaration removed, leaving Controller and UserInterface - both
 * readers - behind. */
const REMOVAL_WITH_READERS_LEFT: PlanReply = {
  revision: 7,
  changes: [
    {
      file: "C:/work/demo/components/sensor_hub.ddd.json",
      fingerprint: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
      operations: [{ op: "remove", pointer: "component.interface[2]", raw: null }],
      hunks: [
        {
          line: 12,
          before: [
            "        {",
            '          "scope": "output",',
            '          "definition": { "name": "ValueA", "kind": "measurement", "unit": "%" }',
            "        },",
          ],
          after: [],
        },
      ],
    },
  ],
};

/** FIXED_BY_TYPE's own SensorHub declaration removed - the only one it has, so nothing is left
 * declaring it afterwards. */
const REMOVAL_WITH_NOTHING_LEFT: PlanReply = {
  revision: 7,
  changes: [
    {
      file: "C:/work/demo/components/sensor_hub.ddd.json",
      fingerprint: "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
      operations: [{ op: "remove", pointer: "component.interface[2]", raw: null }],
      hunks: [
        {
          line: 12,
          before: [
            "        {",
            '          "scope": "output",',
            '          "definition": { "name": "ValueA", "typename": "Speed_t" }',
            "        },",
          ],
          after: [],
        },
      ],
    },
  ],
};

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
  /** What removing the variable from a component would take, and which component that is; left
   * out for a story that shows no removal offer at all - the way a screen with no component in
   * view never offers one either. */
  removal?: { from: string; offer: Offer };
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
  removal,
}: Props) {
  const [selected, setSelected] = useState<string | undefined>(initialSelected);
  const [chosen, setChosen] = useState<string | null | undefined>(initialChosen);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [edited, setEdited] = useState<{ min: string; max: string } | undefined>(undefined);
  const [changesShown, setChangesShown] = useState(initialChangesShown);
  const [removalShown, setRemovalShown] = useState(false);
  // As in VariablePanel.tsx: for `limits` the two fields are the value, so what they say and
  // what would be applied are one thing, and a pair that is no range says so and offers none.
  // Derived here as the screen derives it - a story that seeded the fields instead would draw
  // a panel the screen cannot reach, which is how a row opening on two empty fields, a
  // removal, went unseen through forty screenshots.
  const range =
    edited ??
    (selected === undefined ? { min: "", max: "" } : limitsOf(startingRaw(variable, selected)));
  const broken = selected === "limits" ? limitsNote(range.min, range.max) : null;
  const target =
    selected === undefined || broken !== null
      ? null
      : selected === "limits"
        ? limitsRaw(range.min, range.max)
        : chosen === undefined
          ? startingRaw(variable, selected)
          : chosen;
  const select = (key: string | undefined) => {
    setSelected(key);
    setChosen(undefined);
    setTyped(undefined);
    setEdited(undefined);
    setChangesShown(false);
  };
  const onRange = (next: { min: string; max: string }) => {
    setEdited(next);
    setTyped(undefined);
  };
  return (
    <VariablePanelView
      variable={variable}
      units={units}
      selected={selected}
      onSelect={select}
      onOpenType={() => undefined}
      typed={
        typed ??
        (selected === undefined || broken !== null ? "" : labelOfRaw(variable, selected, target))
      }
      // Never the target: opening the list on the value settled on must still list everything,
      // not just the entries that happen to contain it (spec 5.3, and part 1's own journey).
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(raw) => {
        setChosen(raw);
        setTyped(undefined);
        if (selected === "limits") setEdited(limitsOf(raw));
      }}
      onPickerClosed={() => setTyped(undefined)}
      range={range}
      onRange={onRange}
      note={
        broken ??
        (selected === "unit" && outsideVocabulary(units, textOf(target ?? undefined))
          ? "Not one of this project's units"
          : undefined)
      }
      preview={broken === null ? preview : null}
      refusal={refusal ?? null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => undefined}
      busy={false}
      focus={pickerOpen ? 1 : null}
      pickerTrigger={pickerOpen ? "focus" : "input"}
      removal={removal?.offer ?? null}
      removeFrom={removal?.from ?? null}
      removalShown={removalShown}
      onRemovalShown={setRemovalShown}
      onRemove={() => undefined}
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

export const WithARemovalAndReadersLeft = () => (
  <View
    variable={DISAGREEING}
    units={FREE_UNITS}
    preview={null}
    removal={{
      from: "SensorHub",
      offer: { plan: REMOVAL_WITH_READERS_LEFT, refusal: null, pending: false },
    }}
  />
);

export const WithARemovalAndNothingLeft = () => (
  <View
    variable={FIXED_BY_TYPE}
    units={FREE_UNITS}
    preview={null}
    removal={{
      from: "SensorHub",
      offer: { plan: REMOVAL_WITH_NOTHING_LEFT, refusal: null, pending: false },
    }}
  />
);
