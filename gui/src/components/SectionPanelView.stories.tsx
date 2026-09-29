import { useState } from "react";
import type { PlanReply, SectionReply } from "../api/types";
import {
  REMOVE_SECTION,
  RENAME_SECTION_REFUSED,
  SECTION_CALIB,
  SECTION_REPLY,
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
}

/** The panel over one scenario's fixtures, with its own access, alignment, description and rename
 * state - as SectionPanel.tsx keeps them. */
function PanelStory({ reply, renameTo: renameSeed = null, renameRefusal, removePlan }: Props) {
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

/** .fast_ram: three definitions place their data there, from two components - its access, its
 * alignment, its description, no findings, and Remove replaced by the sentence saying how many
 * would be left pointing at a section that had gone. */
export const ThreeDefinitionsPlaceDataInIt = () => <PanelStory reply={SECTION_REPLY} />;

/** A section nothing places data in, one of three its file declares: Remove is offered - its own
 * plan already in, ready for Show changes or Apply - rather than refused. */
export const NothingPlacesDataInIt = () => (
  <PanelStory reply={SECTION_UNUSED} removePlan={REMOVE_SECTION} />
);

/** Renaming .calib to a section the project already declares: the editor's own sentence, where
 * the consequence line would otherwise stand - no Show changes, no Apply under it. */
export const RenameRefused = () => (
  <PanelStory reply={SECTION_CALIB} renameTo=".fast_ram" renameRefusal={RENAME_SECTION_REFUSED} />
);
