import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getUndo, postUndo } from "../api/client";
import type { State } from "../api/types";
import { UndoStripView } from "../components/UndoStripView";
import { putBackOf, type Write } from "../lib/announcing";
import { type Refused, refusalShown } from "../lib/refusals";
import { askedAgainAfterUndo, undoButton, undoRefusal } from "../lib/undo";
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
 * without a request of its own. A refusal of the mutation, whatever its code, is held for the
 * entry the reader pressed for until they close the strip, as the panels hold theirs until the
 * reader's next choice, and a revision landing - the one a refusal of the entry on top asks for,
 * within milliseconds (refusing one no longer on top asks for none) - never takes it away
 * (`Refused`, lib/refusals.ts). It is that entry's alone:
 * another reaching the top while the strip stays open - an edit a panel makes meanwhile, or an
 * undo from another window - is offered whole, its preview and its Put back, and the refusal goes
 * unsaid. An undo answered, every query `askedAgainAfterUndo` names is asked for again at once:
 * the files are back before the revision says so.
 */
export function UndoStrip({ state, stopped }: Props) {
  const queries = useQueryClient();
  const [open, setOpen] = useState(false);
  const [changesShown, setChangesShown] = useState(false);
  const [refused, setRefused] = useState<Refused<number | undefined> | null>(null);
  const undoable = state?.undoable ?? null;
  const revision = state?.revision;
  const preview = useQuery({
    queryKey: ["undo", undoable?.at, revision],
    queryFn: !open || undoable === null ? skipToken : () => getUndo(),
    retry: false,
  });
  const undo = useMutation({
    // The entry the reader pressed for, which the refusal, if any, is of, and what its preview says
    // it puts back, for the heading to say once it has (16:I13).
    mutationFn: ({ at, putBack }: { at: number; putBack: Write | undefined }) =>
      postUndo(at, fetch, ownEdits, putBack),
    onMutate: () => setRefused(null),
    onSuccess: () => {
      setOpen(false);
      setChangesShown(false);
    },
    onError: (error, { at }) => setRefused({ about: at, text: undoRefusal(error) }),
    // An undo is answered once its files are back, its analysis following: whatever on screen
    // draws what it put back asks again now, rather than when the revision moves.
    onSettled: () =>
      queries.invalidateQueries({ predicate: (query) => askedAgainAfterUndo(query.queryKey) }),
  });
  const label = undoButton(state);
  if (label === null) return null;
  return (
    <UndoStripView
      label={label}
      open={open}
      onOpen={(next) => {
        setOpen(next);
        // A refusal is the whole of the strip, hiding the button that would let the reader try
        // again: closing the strip is the one gesture left, so it is what clears the refusal.
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
      onUndo={() => {
        if (undoable === null) return;
        const shown = preview.data?.at === undoable.at ? preview.data : undefined;
        undo.mutate({ at: undoable.at, putBack: shown && putBackOf(shown) });
      }}
      refusal={refusalShown(
        refused,
        preview.isError ? undoRefusal(preview.error) : null,
        undoable?.at,
      )}
      busy={stopped || undo.isPending}
    />
  );
}
