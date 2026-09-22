import { useState } from "react";
import { UNDO_ADOPTION } from "../stories/fixtures";
import { UndoStripView } from "./UndoStripView";

export default { title: "Components / UndoStripView" };

// What UndoStrip's `refusalOf` builds from the api's own "stale" message (UndoStrip.tsx),
// now that the api names the file by its own name rather than its full path.
const REFUSED =
  "demo.ddd.json changed on disk since it was written. " +
  "Nothing was put back; the page shows the files as they are.";

/** The heading a project screen draws, laid out as App.tsx lays it out: the project's name, the
 * control beside it, and the strip below them. */
function Heading({
  opened = false,
  shown = false,
  refusal = null,
  reading = false,
}: {
  opened?: boolean;
  shown?: boolean;
  refusal?: string | null;
  /** Still `GET /api/undo`'s answer waited for: no preview, and no refusal either. */
  reading?: boolean;
}) {
  const [open, setOpen] = useState(opened);
  const [changesShown, setChangesShown] = useState(shown);
  return (
    <div className="heading">
      <h1>DemoDevice</h1>
      <UndoStripView
        label={`Undo ${UNDO_ADOPTION.label}`}
        open={open}
        onOpen={setOpen}
        preview={reading ? null : refusal === null ? UNDO_ADOPTION : null}
        changesShown={changesShown}
        onChangesShown={setChangesShown}
        onUndo={() => undefined}
        refusal={refusal}
        busy={false}
      />
    </div>
  );
}

export const Closed = () => <Heading />;

export const Open = () => <Heading opened />;

export const Reading = () => <Heading opened reading />;

export const ChangesShown = () => <Heading opened shown />;

export const Refused = () => <Heading opened refusal={REFUSED} />;
