import { useState } from "react";
import type { PlanReply, RasterReply } from "../api/types";
import { rasterRemovable } from "../lib/shared";
import {
  RASTER_1MS_REPLY,
  RASTER_EVENT_REFUSED,
  RASTER_REPLY,
  RASTER_UNUSED,
  REMOVE_RASTER,
  RENAME_RASTER_REFUSED,
} from "../stories/fixtures";
import { RasterPanelView } from "./RasterPanelView";

export default { title: "Components / RasterPanelView" };

interface Props {
  reply: RasterReply;
  /** What the Event field starts on: the raster's own event, unless a scenario means to show it
   * already typed - a refusal only ever appears with the offending value still in the field. */
  event?: string;
  eventRefusal?: string;
  /** What the Rename field starts on: the raster's own name, unless a scenario means to show it
   * already typed, for the same reason. */
  renameTo?: string | null;
  renameRefusal?: string;
  /** Remove's own plan, for a raster nothing names - `null` (nothing asked for) wherever a shape
   * still does, `RasterPanelView`'s own concern to say why from `reply.uses` alone. */
  removePlan?: PlanReply;
}

/** The panel over one scenario's fixtures, with its own event, cycle, description and rename
 * state - as RasterPanel.tsx keeps them. */
function PanelStory({
  reply,
  event: eventSeed,
  eventRefusal,
  renameTo: renameSeed = null,
  renameRefusal,
  removePlan,
}: Props) {
  const [event, setEvent] = useState(eventSeed ?? reply.event);
  const [cycle, setCycle] = useState(reply.cycle);
  const [description, setDescription] = useState(reply.description);
  const [renameTo, setRenameTo] = useState<string | null>(renameSeed);
  return (
    <RasterPanelView
      reply={reply}
      event={event}
      onEvent={setEvent}
      cycle={cycle}
      onCycle={setCycle}
      description={description}
      onDescription={setDescription}
      renameTo={renameTo}
      onRenameTo={setRenameTo}
      eventOffer={
        event === reply.event ? null : { plan: null, refusal: eventRefusal ?? null, pending: false }
      }
      cycleOffer={null}
      describeOffer={null}
      renameOffer={
        renameTo === null ? null : { plan: null, refusal: renameRefusal ?? null, pending: false }
      }
      removeOffer={
        // `rasterRemovable`, as RasterPanel.tsx asks it - not a `uses.length === 0` of its own.
        // A story standing in for the screen has to stand in for the screen's judgement too, or
        // the photographs stop being evidence about what the screen would draw.
        rasterRemovable(reply.uses)
          ? { plan: removePlan ?? null, refusal: null, pending: false }
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

/** 10ms, named twice and in two different ways: Pump measuring everything it produces in it, and
 * SensorHub's InletPressure measured in it on its own. The shape neither a constant's panel nor a
 * section's has - a section is named by a definition and nowhere else - and the reason
 * `RasterUse.kind` carries two words: a list of definitions alone would have drawn one row here
 * and told a reader nothing about the component that was missing from it. Remove is replaced by
 * the sentence counting the shapes that would be left naming a raster that had gone. */
export const NamedByADefinitionAndAComponent = () => <PanelStory reply={RASTER_REPLY} />;

/** A raster nothing names, one of three its file declares: Remove is offered - its own plan
 * already in, ready for Show changes or Apply - rather than refused. 100ms is the shipped
 * example's own unused raster, so this is the real case and not a constructed one. */
export const NothingMeasuresInIt = () => (
  <PanelStory reply={RASTER_UNUSED} removePlan={REMOVE_RASTER} />
);

/** Renaming 1ms to a raster the project already declares: the editor's own sentence, where the
 * consequence line would otherwise stand - no Show changes, no Apply under it. The same refusal
 * F2 gives in the editor, both arriving through `rename_problem`'s raster arm. */
export const RenameRefused = () => (
  <PanelStory reply={RASTER_1MS_REPLY} renameTo="10ms" renameRefusal={RENAME_RASTER_REFUSED} />
);

/** The refusal no other vocabulary on this tab can show: 1ms's event set to 1, which 10ms already
 * claims. A section's alignment and a constant's value are nobody's to hold; an event is a channel
 * xcp addresses, so the project owns it, and nothing in `RasterReply` says which are free - the
 * panel asks for the plan and shows the sentence that comes back, with the value that earned it
 * still in the field. */
export const EventAlreadyClaimed = () => (
  <PanelStory reply={RASTER_1MS_REPLY} event="1" eventRefusal={RASTER_EVENT_REFUSED} />
);
