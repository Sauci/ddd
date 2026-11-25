import { useState } from "react";
import type { UndoPreview } from "../api/types";
import { type WrittenLine, writtenSentence } from "../lib/announcing";
import { NOTHING_LEFT } from "../lib/undo";
import { UNDO_ADOPTION, UNDO_UNIT } from "../stories/fixtures";
import { LinkTabs } from "../ui/LinkTabs";
import { UpdatingStatus } from "../ui/UpdatingNote";
import { UndoStripView } from "./UndoStripView";

export default { title: "Components / UndoStripView" };

// What the strip says of the api's own "stale" message (`undoRefusal`, lib/undo.ts), now that
// the api names the file by its own name rather than its full path: the server took the edit off
// the stack with it (16:M23).
const TAKEN_OFF =
  "demo.ddd.json changed on disk since it was written, so the vocabulary adopted can no longer " +
  "be undone. Nothing was put back; the page shows the files as they are.";

// What the strip says of a preview the server failed on, in the server's own words.
const FAILED =
  "The undo was refused: ddd gui failed on this request; the terminal it runs in shows why";

// What the strip says of a Put back refused because a file is kept read-only, in the server's own
// words, which name the file by its full path.
const READ_ONLY =
  "The undo was refused: C:/work/demo/demo.ddd.json is read-only, so nothing was put back";

// The project's views, as App.tsx names them, the first one open.
const VIEWS = ["Graph", "Table", "Units", "Types", "Shared files", "Files", "Findings", "Compare"];

/** The heading a project screen draws, laid out as App.tsx lays it out: the project's name, the
 * control beside it, the strip below them, and last the heading's status region, which says when
 * the findings are updating and takes no room while it says nothing. The project's tabs stand
 * under it, as they do on the page: a heading grown by a line moves them. */
function Heading({
  opened = false,
  shown = false,
  entry = UNDO_ADOPTION,
  refusals = [],
  offered = refusals.length === 0,
  reading = false,
  updating = false,
  written = null,
}: {
  opened?: boolean;
  shown?: boolean;
  /** The entry on top of the stack, `null` once none is left. */
  entry?: UndoPreview | null;
  /** What the strip says was refused, in the order it came. */
  refusals?: readonly string[];
  /** Whether the strip offers `entry` to put back: by default, where nothing is refused. */
  offered?: boolean;
  /** Still `GET /api/undo`'s answer waited for: no preview, and no refusal either. */
  reading?: boolean;
  /** The findings may be about to change: an edit waits for its analysis, or one runs. */
  updating?: boolean;
  /** What the heading says the page last wrote. */
  written?: WrittenLine | null;
}) {
  const [open, setOpen] = useState(opened);
  const [changesShown, setChangesShown] = useState(shown);
  return (
    <section>
      <div className="heading">
        <h1>DemoDevice</h1>
        <UndoStripView
          label={entry === null ? NOTHING_LEFT : `Undo ${entry.label}`}
          open={open}
          onOpen={setOpen}
          refusals={refusals.map((text) => ({ key: text, text }))}
          preview={reading || !offered ? null : entry}
          reading={reading}
          changesShown={changesShown}
          onChangesShown={setChangesShown}
          onUndo={() => undefined}
          busy={false}
        />
        <UpdatingStatus updating={updating} written={written} />
      </div>
      <LinkTabs
        label="Project views"
        tabs={VIEWS.map((view, index) => ({
          href: `/project?view=${view}`,
          label: view,
          current: index === 0,
          onFollow: () => undefined,
        }))}
      />
    </section>
  );
}

export const Closed = () => <Heading />;

export const Open = () => <Heading opened />;

export const Reading = () => <Heading opened reading />;

export const ChangesShown = () => <Heading opened shown />;

/** The preview refused, in the server's words: said in its place, with nothing to put back. */
export const Refused = () => <Heading opened refusals={[FAILED]} />;

/** The Put back refused because a file could not be written: the edit stays on the stack, and the
 * strip offers it again under the sentence, to be pressed once the file is writable (R22). */
export const OfferedAgain = () => <Heading opened refusals={[READ_ONLY]} offered />;

/** The adoption on top refused because a file it would put back was saved from outside: the
 * server took it off the stack, and the strip, still open, says why beside the edit under it,
 * which it offers whole (16:M23). */
export const TakenOff = () => <Heading opened entry={UNDO_UNIT} refusals={[TAKEN_OFF]} offered />;

/** The same with no edit under it: nothing is left to undo, which the control says for as long
 * as the strip says why. */
export const NothingLeft = () => <Heading opened entry={null} refusals={[TAKEN_OFF]} />;

/** Two edits of one file, and a save from outside that took both off the stack: the strip says
 * each, in the order they went, and nothing is left to undo. */
export const BothTakenOff = () => (
  <Heading
    opened
    entry={null}
    refusals={["the limits of ValueA", "the unit of ValueA"].map(
      (label) =>
        `controller.ddd.json changed on disk since it was written, so ${label} can no longer be ` +
        "undone. Nothing was put back; the page shows the files as they are.",
    )}
  />
);

/** The last edit written and its analysis not landed yet: the heading says so beside the control,
 * in what room its row has left. */
export const Updating = () => <Heading updating />;

/** The same with the strip open: the strip's own line leaves the heading's status no room, so the
 * note is not seen - it is still announced - and the tabs stay where `Open` has them. */
export const OpenUpdating = () => <Heading opened updating />;

/** The edit the control would undo, written, and its findings analysed: the heading says what it
 * wrote, beside the control, in what room its row has left (16:I13). */
export const Written = () => (
  <Heading
    written={{
      edit: 1,
      sentence: writtenSentence({
        kind: "wrote",
        label: UNDO_ADOPTION.label,
        files: UNDO_ADOPTION.changes.map((change) => change.file),
      }),
    }}
  />
);
