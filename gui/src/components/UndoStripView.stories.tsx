import { useState } from "react";
import { UNDO_ADOPTION } from "../stories/fixtures";
import { LinkTabs } from "../ui/LinkTabs";
import { UpdatingStatus } from "../ui/UpdatingNote";
import { UndoStripView } from "./UndoStripView";

export default { title: "Components / UndoStripView" };

// What UndoStrip's `refusalOf` builds from the api's own "stale" message (UndoStrip.tsx),
// now that the api names the file by its own name rather than its full path.
const REFUSED =
  "demo.ddd.json changed on disk since it was written. " +
  "Nothing was put back; the page shows the files as they are.";

// The project's views, as App.tsx names them, the first one open.
const VIEWS = ["Graph", "Table", "Units", "Types", "Shared files", "Files", "Findings", "Compare"];

/** The heading a project screen draws, laid out as App.tsx lays it out: the project's name, the
 * control beside it, the strip below them, and last the heading's status region, which says when
 * the findings are updating and takes no room while it says nothing. The project's tabs stand
 * under it, as they do on the page: a heading grown by a line moves them. */
function Heading({
  opened = false,
  shown = false,
  refusal = null,
  reading = false,
  updating = false,
}: {
  opened?: boolean;
  shown?: boolean;
  refusal?: string | null;
  /** Still `GET /api/undo`'s answer waited for: no preview, and no refusal either. */
  reading?: boolean;
  /** The findings may be about to change: an edit waits for its analysis, or one runs. */
  updating?: boolean;
}) {
  const [open, setOpen] = useState(opened);
  const [changesShown, setChangesShown] = useState(shown);
  return (
    <section>
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
        <UpdatingStatus updating={updating} />
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

export const Refused = () => <Heading opened refusal={REFUSED} />;

/** The last edit written and its analysis not landed yet: the heading says so beside the control,
 * in what room its row has left. */
export const Updating = () => <Heading updating />;

/** The same with the strip open: the strip's own line leaves the heading's status no room, so the
 * note is not seen - it is still announced - and the tabs stay where `Open` has them. */
export const OpenUpdating = () => <Heading opened updating />;
