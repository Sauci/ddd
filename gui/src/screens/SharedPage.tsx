import { useQuery } from "@tanstack/react-query";
import { getShared } from "../api/client";
import type { State } from "../api/types";
import { SharedTableView } from "../components/SharedTableView";
import { baseName } from "../lib/units";
import { Banner } from "../ui/Banner";

interface Props {
  state: State | null;
  /** The constant whose row is marked, as the address names it - `undefined` for the bare tab
   * and for a "declare" address (Task 8's territory), since this task draws no panel for either
   * to open. */
  name: string | undefined;
  onName: (name: string | undefined) => void;
}

/** The open project's Shared files tab (spec 5.1): every constant it declares, across both homes
 * one may be declared in. `SharedTableView` draws the tab's own meta line, its empty-project
 * button and its unreadable-file warning; Task 8 puts a constant's panel, and the add form,
 * beside the table this screen draws. */
export function SharedPage({ state, name, onName }: Props) {
  const revision = state?.revision;
  const shared = useQuery({
    queryKey: ["shared", revision],
    queryFn: () => getShared(),
    // The table stays while the next revision's entries are read: swapped for a loading line on
    // every edit, it lost the reader's place and made the tab flash - as UnitsPage and TypesPage
    // already do.
    placeholderData: (previous) => previous,
  });
  // The names of the constants files that did not load, which declare entries the table cannot
  // show - computed from the same state the rest of the page reads, since the server's own answer
  // to GET /api/shared says nothing about a file it could not read at all. A *file*'s own `kind`
  // is "constants" (plural); an *entry*'s `kind` (what SharedTableView's own Kind column draws) is
  // "constant" (singular) - only the file's word appears here, so the two cannot be swapped in
  // this filter the way they could if both spellings were in play at once.
  const unreadable = (state?.files ?? [])
    .filter((file) => file.kind === "constants" && !file.loaded)
    .map((file) => baseName(file.path));

  if (shared.data === undefined) {
    if (shared.isError) return <Banner tone="error">{shared.error.message}</Banner>;
    return <p className="quiet">Reading the project's shared files…</p>;
  }
  return (
    <>
      {/* A server that stopped answering leaves the table as it was, and says so above it. */}
      {shared.isError && <Banner tone="error">{shared.error.message}</Banner>}
      <div className={name !== undefined ? "with-panel" : undefined}>
        <div>
          <SharedTableView
            reply={shared.data}
            selected={name}
            onSelect={onName}
            unreadable={unreadable}
            // Task 8 replaces this with whatever opens the add form; until then there is no panel
            // this task draws for it to open, so pressing the button does nothing yet.
            onDeclare={() => undefined}
          />
        </div>
        {/* Task 8 puts the constant's panel, and the add form, here. */}
      </div>
    </>
  );
}
