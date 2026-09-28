import { useState } from "react";
import type { ConstantReply, PlanReply } from "../api/types";
import {
  CONSTANT_BAD_VALUE,
  CONSTANT_REPLY,
  CONSTANT_UNUSED,
  REMOVE_CONSTANT,
} from "../stories/fixtures";
import { ConstantPanelView } from "./ConstantPanelView";

export default { title: "Components / ConstantPanelView" };

interface Props {
  reply: ConstantReply;
  /** What the Rename field starts on: the constant's own name, unless a scenario means to show
   * it already typed - a refusal only ever appears with the offending name still in the field. */
  renameTo?: string | null;
  refusal?: string;
  /** Remove's own plan, for a constant nothing names - `null` (nothing asked for) wherever a
   * shape still does, `ConstantPanelView`'s own concern to say why from `reply.uses` alone. */
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
        reply.uses.length === 0 ? { plan: removePlan ?? null, refusal: null, pending: false } : null
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
 * value, its description, no findings, and Remove not offered while both still name it. */
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

/* The add form's own story moved with the form itself, to SharedAddView.stories.tsx: what
 * `unknown-constant`'s route leaves on screen is now that form with its chooser already on
 * constants, which is what the tab draws and so what a photograph of it has to show. */
