import type { UndoPreview } from "../api/types";
import { shownUndo, undoAction, undoConsequence } from "../lib/undo";
import { Button } from "../ui/Button";
import { Changes } from "./Changes";

export interface UndoStripViewProps {
  /** What the button says, from `undoButton`: "Undo the unit of ValueA". */
  label: string;
  open: boolean;
  onOpen: (open: boolean) => void;
  /** The preview once it has come; `null` while it is asked for, and when it was refused. */
  preview: UndoPreview | null;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onUndo: () => void;
  /** Why nothing can be put back, or why putting it back was refused; `null` when neither. */
  refusal: string | null;
  /** Undoing, or the server stopped. */
  busy: boolean;
}

/**
 * The Undo control beside the project's name and the strip it opens (spec 5.1 and 5.2): a
 * picture of its props.
 *
 * A fragment rather than a wrapper, so that the button sits in the heading's own row beside the
 * name while the strip takes the line below it - which is what `.undo-open` asks that row for.
 */
export function UndoStripView(props: UndoStripViewProps) {
  const { label, open, preview, refusal, changesShown, busy } = props;
  return (
    <>
      <Button
        variant="secondary"
        isDisabled={busy}
        aria-expanded={open}
        onPress={() => props.onOpen(!open)}
      >
        {label}
      </Button>
      {open && (
        <section className="undo-open" aria-label="Undo">
          {/* A refusal is the whole of the strip: an undo is all-or-nothing, and offering to
              put back the files that have not changed would be offering half of it. */}
          {refusal !== null ? (
            <p className="undo-refusal" role="status">
              {refusal}
            </p>
          ) : preview === null ? (
            <p className="quiet">Reading the files…</p>
          ) : (
            <>
              <p className="consequence">{undoConsequence(preview.changes)}</p>
              {changesShown && <Changes changes={shownUndo(preview.changes)} />}
              <div className="panel-actions">
                <Button variant="link" onPress={() => props.onChangesShown(!changesShown)}>
                  {changesShown ? "Hide changes" : "Show changes"}
                </Button>
                <Button variant="primary" isDisabled={busy} onPress={props.onUndo}>
                  {undoAction(preview.changes)}
                </Button>
              </div>
            </>
          )}
        </section>
      )}
    </>
  );
}
