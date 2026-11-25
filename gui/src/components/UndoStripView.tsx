import type { UndoPreview } from "../api/types";
import { shownUndo, undoAction, undoConsequence } from "../lib/undo";
import { Button } from "../ui/Button";
import { Changes } from "./Changes";

export interface UndoStripViewProps {
  /** What the button says, from `undoShown`: "Undo the unit of ValueA", or "Nothing left to undo"
   * while the strip still says why the last entry left the stack. */
  label: string;
  open: boolean;
  onOpen: (open: boolean) => void;
  /** Every refusal the strip says, in the order they came (`undoShown`): of an entry the server
   * took off the stack, said beside the one under it, and of the entry on top - and its preview's
   * failure, said in a sentence of its own. */
  refusals: readonly { key: string; text: string }[];
  /** The entry offered to put back, once its preview has come; `null` while it is asked for, where
   * it was refused, and where nothing is left to undo. */
  preview: UndoPreview | null;
  /** Whether the strip says it is reading the files: the preview of the entry on top is asked for
   * and has not come. */
  reading: boolean;
  /** Reads the files again, offered beside a refusal of the preview the server keeps the entry
   * through (`undoShown`, R22); `null` where nothing is to be read again. */
  onAskAgain: (() => void) | null;
  /** Whether the files are being read again. */
  asking: boolean;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onUndo: () => void;
  /** Undoing, or the server stopped. */
  busy: boolean;
}

/**
 * The Undo control in a page's heading and the strip it opens (spec 5.1 and 5.2): a picture of
 * its props.
 *
 * A fragment rather than a wrapper, so that the button sits in the heading's own row - after the
 * controls there, before the row's status - while the strip takes the line below it, which is what
 * `.undo-open` asks that row for.
 */
export function UndoStripView(props: UndoStripViewProps) {
  const { label, open, preview, refusals, reading, asking, changesShown, busy } = props;
  return (
    <>
      <Button
        variant="secondary"
        isDisabled={busy}
        aria-expanded={open}
        onPress={() => props.onOpen(!open)}
      >
        {/* On one line, cut with an ellipsis past a measure: the 120 characters a label can have
            would otherwise wrap the heading's row and push the table down (16:M22). */}
        <span className="undo-label" title={label}>
          {label}
        </span>
      </Button>
      {open && (
        <section className="undo-open" aria-label="Undo">
          {/* What was refused comes first, and whatever the stack's top offers under it, always
              whole: an entry taken off is said beside the one under it, and a refusal that left
              the entry on top beside that entry, to be pressed again. An undo is all-or-nothing,
              so a preview refused offers none of its files. */}
          {refusals.length > 0 && (
            <div className="undo-refusal" role="status">
              {refusals.map(({ key, text }) => (
                <p key={key}>{text}</p>
              ))}
            </div>
          )}
          {props.onAskAgain !== null && (
            <div className="panel-actions">
              <Button variant="secondary" isDisabled={busy || asking} onPress={props.onAskAgain}>
                Read the files again
              </Button>
            </div>
          )}
          {reading && <p className="quiet">Reading the files…</p>}
          {preview !== null && (
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
