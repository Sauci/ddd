import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getUndo, postUndo } from "../api/client";
import type { State } from "../api/types";
import { UndoStripView } from "../components/UndoStripView";
import { putBackOf, type Write } from "../lib/announcing";
import {
  askedAgainAfterUndo,
  holding,
  previewRefused,
  type UndoRefused,
  undoRefused,
  undoShown,
} from "../lib/undo";
import { ownEdits } from "../state/edits";

interface Props {
  state: State | null;
  /** The server stopped answering: nothing can be written. */
  stopped: boolean;
}

/**
 * The Undo control beside the project's name: the last edit this session wrote, previewed
 * before any of it is put back.
 *
 * The preview is asked for only once the strip is open, and keyed by the entry and the
 * revision, so that a file changing on disk - or another window undoing first - is noticed
 * without a request of its own. A refusal of the Put back, whatever its code, is held for the
 * entry the reader pressed for until their next choice in the strip - Put back pressed again, or
 * the strip closed - as the panels hold theirs, and a revision landing - the one a refusal of the
 * entry on top asks for, within milliseconds (refusing one no longer on top asks for none) - never
 * takes it away (`Refused`, lib/refusals.ts). So is a refusal of the preview `stale`: a file the
 * entry would put back gone, changed on disk, or unreadable. What the strip offers beside them is
 * `undoShown`'s:
 * - the server takes an entry off the stack with a refusal of either where the disk moved past
 *   it, a file gone or changed (16:M23), and once the state says so the strip says why it went
 *   beside the entry under it, which it offers whole without being closed - or, with none left,
 *   says so until it is closed;
 * - a refusal that leaves the entry on top - a file that could not be read or written - is said
 *   beside that entry as it stands, offered again to be pressed once the reader has mended the
 *   file, the strip never closed between (R22).
 *
 * An undo answered, every query `askedAgainAfterUndo` names is asked for again at once: the files
 * are back before the revision says so.
 */
export function UndoStrip({ state, stopped }: Props) {
  const queries = useQueryClient();
  const [open, setOpen] = useState(false);
  const [changesShown, setChangesShown] = useState(false);
  const [held, setHeld] = useState<readonly UndoRefused[]>([]);
  const undoable = state?.undoable ?? null;
  const revision = state?.revision;
  const preview = useQuery({
    queryKey: ["undo", undoable?.at, revision],
    queryFn:
      !open || undoable === null
        ? skipToken
        : () =>
            getUndo(undoable.at).catch((error: unknown) => {
              // Held as the answer comes, of the entry this query was asked for, where the server
              // took that entry off the stack with it: the state naming the one under it can reach
              // the page before this answer does, which moves the strip to that entry's query, and
              // a refusal held only once the strip saw it refused was then never seen at all.
              const kept = error instanceof Error ? previewRefused(error, undoable) : null;
              if (kept !== null) setHeld((before) => holding(before, kept));
              throw error;
            }),
    retry: false,
  });
  const undo = useMutation({
    // The entry the reader pressed for, which the refusal, if any, is of, and what its preview says
    // it puts back, for the heading to say once it has (16:I13).
    mutationFn: ({ at, putBack }: { at: number; label: string; putBack: Write | undefined }) =>
      postUndo(at, fetch, ownEdits, putBack),
    onMutate: () => setHeld([]),
    onSuccess: () => {
      setOpen(false);
      setChangesShown(false);
    },
    onError: (error, entry) => setHeld((before) => holding(before, undoRefused(error, entry))),
    // An undo is answered once its files are back, its analysis following: whatever on screen
    // draws what it put back asks again now, rather than when the revision moves.
    onSettled: () =>
      queries.invalidateQueries({ predicate: (query) => askedAgainAfterUndo(query.queryKey) }),
  });
  const shown = undoShown(held, state, preview);
  if (shown.label === null) return null;
  return (
    <UndoStripView
      label={shown.label}
      open={open}
      onOpen={(next) => {
        setOpen(next);
        // Closing the strip is the reader's choice that lets every refusal it says go.
        if (!next) {
          setChangesShown(false);
          setHeld([]);
        }
      }}
      refusals={shown.refusals}
      // The preview answers the top of the stack, which may no longer be this entry: another
      // window can apply an edit between this page's last state and this answer. Until the
      // preview names the entry the button does, it counts as not yet arrived (`undoShown`).
      preview={shown.preview}
      reading={shown.reading}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onUndo={() => {
        if (shown.preview === null) return;
        const { at, label } = shown.preview;
        undo.mutate({ at, label, putBack: putBackOf(shown.preview) });
      }}
      busy={stopped || undo.isPending}
    />
  );
}
