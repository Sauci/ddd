import { useState } from "react";
import type { ConstantReply, PlanReply } from "../api/types";
import {
  CONSTANT_BAD_VALUE,
  CONSTANT_REPLY,
  CONSTANT_UNUSED,
  REMOVE_CONSTANT,
} from "../stories/fixtures";
import { ConstantAddView, ConstantPanelView } from "./ConstantPanelView";

export default { title: "Components / ConstantPanelView" };

/** Removing TREND_SAMPLES while its own two uses (CONSTANT_REPLY, above) still name it -
 * `remove_constant`'s own sentence, naming the count and the first of them (design §4.5). Shared
 * by every story built over that fixture: Remove is asked for as soon as the panel opens
 * (`ConstantPanelView`'s own doc on `removeOffer`), so every one of them shows its answer, not an
 * empty box waiting for a reader to press a button that is not there. */
const REMOVE_REFUSED =
  "'TREND_SAMPLES' is named by 2 shapes, the first in pump.ddd.json; nothing may name it before it goes";

interface Props {
  reply: ConstantReply;
  /** What the Rename field starts on: the constant's own name, unless a scenario means to show
   * it already typed - a refusal only ever appears with the offending name still in the field. */
  renameTo?: string | null;
  refusal?: string;
  /** Remove's own plan, for a constant nothing names; every other scenario here is built over one
   * TREND_SAMPLES still names twice, so `REMOVE_REFUSED` stands in for it there instead. */
  removePlan?: PlanReply;
}

/** The panel over one scenario's fixtures, with its own value, description and rename state - as
 * ConstantPanel.tsx (Task 8's own screen) will keep them. */
function PanelStory({ reply, renameTo: renameSeed = null, refusal, removePlan }: Props) {
  const [value, setValue] = useState(reply.value);
  const [description, setDescription] = useState(reply.description);
  const [renameTo, setRenameTo] = useState<string | null>(renameSeed);
  return (
    <ConstantPanelView
      reply={reply}
      value={value}
      onValue={setValue}
      description={description}
      onDescription={setDescription}
      renameTo={renameTo}
      onRenameTo={setRenameTo}
      valueOffer={null}
      describeOffer={null}
      renameOffer={
        renameTo === null ? null : { plan: null, refusal: refusal ?? null, pending: false }
      }
      removeOffer={
        reply.uses.length === 0
          ? { plan: removePlan ?? null, refusal: null, pending: false }
          : { plan: null, refusal: REMOVE_REFUSED, pending: false }
      }
      shown={null}
      onShown={() => undefined}
      onApply={() => undefined}
      onOpen={() => undefined}
      busy={false}
      onClose={() => undefined}
    />
  );
}

/** TREND_SAMPLES: two shapes name it - a variable's dimension and a structure member's - its
 * value, its description, no findings, and Remove already refused for the same two uses. */
export const TwoShapesNameIt = () => <PanelStory reply={CONSTANT_REPLY} />;

/** The same constant set to a value no shape can use: `dimension-value`, filed on PressureTrend's
 * own dimension rather than on the entry, is the state this tab exists to let a reader fix. */
export const AValueNoShapeCanUse = () => <PanelStory reply={CONSTANT_BAD_VALUE} />;

/** A constant nothing names: Remove is offered - its own plan already in, ready for Show changes
 * or Apply - rather than refused. */
export const NothingNamesIt = () => (
  <PanelStory reply={CONSTANT_UNUSED} removePlan={REMOVE_CONSTANT} />
);

/** Renaming TREND_SAMPLES to a name already declared: the editor's own sentence, where the
 * consequence line would otherwise stand - no Show changes, no Apply under it. */
export const RenameRefused = () => (
  <PanelStory
    reply={CONSTANT_REPLY}
    renameTo="PRESSURE_CELLS"
    refusal="'PRESSURE_CELLS' is the name of the declared constant 'PRESSURE_CELLS', which shares c's namespace with the variables"
  />
);

/** The add form as `unknown-constant`'s route leaves it (design §5.3, a later part's territory):
 * the name filled in, no value typed yet, so nothing is previewed. */
export const DeclaringOne = () => (
  <ConstantAddView
    typed="PRESSURE_CELLS"
    onTyped={() => undefined}
    raw=""
    onRaw={() => undefined}
    plan={null}
    refusal={null}
    changesShown={false}
    onChangesShown={() => undefined}
    onApply={() => undefined}
    busy={false}
    onClose={() => undefined}
  />
);
