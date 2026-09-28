import { useState } from "react";
import type { PlanReply, SectionReply } from "../api/types";
import {
  REMOVE_SECTION,
  REMOVE_SECTION_REFUSED,
  RENAME_SECTION_REFUSED,
  SECTION_CALIB,
  SECTION_REPLY,
  SECTION_SOLE_ENTRY,
  SECTION_UNUSED,
} from "../stories/fixtures";
import { SectionPanelView } from "./SectionPanelView";

export default { title: "Components / SectionPanelView" };

interface Props {
  reply: SectionReply;
  /** What the Rename field starts on: the section's own name, unless a scenario means to show it
   * already typed - a refusal only ever appears with the offending name still in the field. */
  renameTo?: string | null;
  renameRefusal?: string;
  /** Remove's own plan, for a section nothing places data in - `null` (nothing asked for)
   * wherever a definition still does, `SectionPanelView`'s own concern to say why from
   * `reply.uses` alone. */
  removePlan?: PlanReply;
  /** Why Remove was refused although nothing places data there: the sole-entry refusal, which is
   * the api's to give and not a fact `SectionReply` carries. */
  removeRefusal?: string;
}

/** The panel over one scenario's fixtures, with its own access, alignment, description and rename
 * state - as SectionPanel.tsx keeps them. */
function PanelStory({
  reply,
  renameTo: renameSeed = null,
  renameRefusal,
  removePlan,
  removeRefusal,
}: Props) {
  const [access, setAccess] = useState(reply.access);
  const [alignment, setAlignment] = useState(reply.alignment);
  const [description, setDescription] = useState(reply.description);
  const [renameTo, setRenameTo] = useState<string | null>(renameSeed);
  return (
    <SectionPanelView
      reply={reply}
      access={access}
      onAccess={setAccess}
      alignment={alignment}
      onAlignment={setAlignment}
      description={description}
      onDescription={setDescription}
      renameTo={renameTo}
      onRenameTo={setRenameTo}
      accessOffer={null}
      alignmentOffer={null}
      describeOffer={null}
      renameOffer={
        renameTo === null ? null : { plan: null, refusal: renameRefusal ?? null, pending: false }
      }
      removeOffer={
        reply.uses.length === 0
          ? { plan: removePlan ?? null, refusal: removeRefusal ?? null, pending: false }
          : null
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

/** .fast_ram: three definitions place their data there, from two components - its access, its
 * alignment, its description, no findings, and Remove replaced by the sentence saying how many
 * would be left pointing at a section that had gone. */
export const ThreeDefinitionsPlaceDataInIt = () => <PanelStory reply={SECTION_REPLY} />;

/** A section nothing places data in, one of three its file declares: Remove is offered - its own
 * plan already in, ready for Show changes or Apply - rather than refused. */
export const NothingPlacesDataInIt = () => (
  <PanelStory reply={SECTION_UNUSED} removePlan={REMOVE_SECTION} />
);

/** The other way Remove is refused, and the one the sibling panel has no answer for: nothing
 * places data in .bench_log either, but it is all its file declares, and a sections list is never
 * empty. The api's own sentence stands where the consequence line would, with no button under
 * it - the panel cannot say this from `SectionReply`, which carries no count of what a file
 * holds, so it asks for the plan and shows what comes back. */
export const TheOnlyOneItsFileDeclares = () => (
  <PanelStory reply={SECTION_SOLE_ENTRY} removeRefusal={REMOVE_SECTION_REFUSED} />
);

/** Renaming .calib to a section the project already declares: the editor's own sentence, where
 * the consequence line would otherwise stand - no Show changes, no Apply under it. */
export const RenameRefused = () => (
  <PanelStory reply={SECTION_CALIB} renameTo=".fast_ram" renameRefusal={RENAME_SECTION_REFUSED} />
);
