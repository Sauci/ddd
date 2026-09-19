import { useState } from "react";
import type { PlanReply, ProjectUnit, UnitReply } from "../api/types";
import {
  ADDITION,
  DESCRIPTION,
  LISTED_RPM,
  LISTED_RPM_PANEL,
  MERGE,
  PROJECT_UNITS,
  REMOVAL,
  UNKNOWN_RPM,
  UNKNOWN_RPM_PANEL,
  UNUSED_KPA,
  UNUSED_KPA_PANEL,
} from "../stories/fixtures";
import { type Offer, type UnitAction, UnitPanelView } from "./UnitPanelView";

export default { title: "Components / UnitPanelView" };

interface Props {
  unit: ProjectUnit;
  reply: UnitReply;
  /** The description as the reader has typed it, and the plan that saves it. */
  draft?: { description: string; plan: PlanReply };
  /** The plan of the vocabulary's change the unit's state offers: its addition or its removal. */
  vocabulary?: PlanReply;
  /** The spelling chosen to rename the unit to, and where its rename stands. */
  rename?: { to: string; offer: Offer };
  shown?: UnitAction;
}

/** The panel over one scenario's fixtures, with its own draft, spelling and Show changes, kept
 * as UnitPanel.tsx keeps them: the picker's field reads what is typed, else the spelling chosen,
 * else the unit's own, and its sections are narrowed only by what is typed. */
function View({ unit, reply, draft, vocabulary, rename, shown: initiallyShown }: Props) {
  const [description, setDescription] = useState(draft?.description);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [to, setTo] = useState<string | null>(rename?.to ?? null);
  const [shown, setShown] = useState<UnitAction | null>(initiallyShown ?? null);
  const planned =
    vocabulary === undefined ? null : { plan: vocabulary, refusal: null, pending: false };
  return (
    <UnitPanelView
      unit={unit}
      reply={reply}
      units={PROJECT_UNITS}
      description={description ?? unit.description ?? ""}
      onDescription={setDescription}
      typed={typed ?? to ?? unit.unit}
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(chosen) => {
        setTo(chosen === unit.unit ? null : chosen);
        setTyped(undefined);
      }}
      onPickerClosed={() => setTyped(undefined)}
      to={to}
      describing={
        draft !== undefined && description === draft.description
          ? { plan: draft.plan, refusal: null, pending: false }
          : null
      }
      adding={unit.files.length === 0 ? planned : null}
      removing={unit.files.length === 0 ? null : planned}
      renaming={rename !== undefined && to === rename.to ? rename.offer : null}
      shown={shown}
      onShown={setShown}
      onApply={() => undefined}
      busy={false}
      onClose={() => undefined}
    />
  );
}

export const InTheVocabulary = () => (
  <View
    unit={LISTED_RPM}
    reply={LISTED_RPM_PANEL}
    draft={{ description: "revolutions per minute", plan: DESCRIPTION }}
  />
);

export const OutsideTheVocabulary = () => (
  <View
    unit={UNKNOWN_RPM}
    reply={UNKNOWN_RPM_PANEL}
    vocabulary={ADDITION}
    rename={{ to: "rpm", offer: { plan: MERGE, refusal: null, pending: false } }}
  />
);

export const Unused = () => (
  <View unit={UNUSED_KPA} reply={UNUSED_KPA_PANEL} vocabulary={REMOVAL} />
);

export const MergeChangesShown = () => (
  <View
    unit={UNKNOWN_RPM}
    reply={UNKNOWN_RPM_PANEL}
    vocabulary={ADDITION}
    rename={{ to: "rpm", offer: { plan: MERGE, refusal: null, pending: false } }}
    shown="rename"
  />
);

export const Refused = () => (
  <View
    unit={UNKNOWN_RPM}
    reply={UNKNOWN_RPM_PANEL}
    vocabulary={ADDITION}
    rename={{
      to: "rpm",
      offer: {
        plan: null,
        refusal:
          "types.ddd.json did not load, so renaming 'RPM' could not reach every place it is stated",
        pending: false,
      },
    }}
  />
);
