import { skipToken, useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, getUndo, postUndo } from "../api/client";
import type { State } from "../api/types";
import { UndoStripView } from "../components/UndoStripView";
import { type Refused, shownRefusal } from "../lib/refusals";
import { undoButton } from "../lib/undo";

interface Props {
  state: State | null;
  /** The server stopped answering: nothing can be written. */
  stopped: boolean;
}

/** What the strip says when a preview or an undo was refused. A stale refusal is the server's
 * own sentence, which names the file that changed, and what it means for the reader. */
function refusalOf(error: Error): string {
  return error instanceof ApiError && error.code === "stale"
    ? `${error.message}. Nothing was put back; the page shows the files as they are.`
    : `The undo was refused: ${error.message}`;
}

/**
 * The Undo control beside the project's name: the last edit this session wrote, previewed
 * before any of it is put back.
 *
 * The preview is asked for only once the strip is open, and keyed by the entry and the
 * revision, so that a file changing on disk - or another window undoing first - is noticed
 * without a request of its own. A refusal of the mutation is held to the revision it happened
 * at, as the panels hold theirs: sending the same entry again before the analysis has caught up
 * would be refused a second time.
 */
export function UndoStrip({ state, stopped }: Props) {
  const [open, setOpen] = useState(false);
  const [changesShown, setChangesShown] = useState(false);
  const [refused, setRefused] = useState<Refused | null>(null);
  const undoable = state?.undoable ?? null;
  const revision = state?.revision;
  const preview = useQuery({
    queryKey: ["undo", undoable?.at, revision],
    queryFn: !open || undoable === null ? skipToken : () => getUndo(),
    retry: false,
  });
  const undo = useMutation({
    mutationFn: () => {
      if (undoable === null) throw new Error("there is nothing to undo");
      return postUndo(undoable.at);
    },
    onMutate: () => setRefused(null),
    onSuccess: () => {
      setOpen(false);
      setChangesShown(false);
    },
    onError: (error) => setRefused({ text: refusalOf(error), revision }),
  });
  const label = undoButton(state);
  if (label === null) return null;
  return (
    <UndoStripView
      label={label}
      open={open}
      onOpen={(next) => {
        setOpen(next);
        // A refusal that is not stale changes no file, so no new revision ever arrives to age
        // it out of `shownRefusal` on its own; the button that would let the reader try again is
        // the one the refusal hides. Closing the strip is the only gesture left, so it is what
        // clears the refusal too.
        if (!next) {
          setChangesShown(false);
          setRefused(null);
        }
      }}
      // The preview answers the top of the stack, which may no longer be this entry: another
      // window can apply an edit between this page's last state and this answer. Until the
      // preview names the entry the button does, it counts as not yet arrived.
      preview={preview.data?.at === undoable?.at ? (preview.data ?? null) : null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onUndo={() => undo.mutate()}
      refusal={
        shownRefusal(refused, revision) ?? (preview.isError ? refusalOf(preview.error) : null)
      }
      busy={stopped || undo.isPending}
    />
  );
}
