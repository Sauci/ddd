import { useQuery } from "@tanstack/react-query";
import { getFiles } from "../api/client";
import type { State } from "../api/types";
import { FilesTableView } from "../components/FilesTableView";
import { Banner } from "../ui/Banner";

interface Props {
  state: State | null;
  /** The row whose key the address names, as the route's own `path` - `undefined` for the bare
   * tab. */
  path: string | undefined;
  onPath: (path: string | undefined) => void;
}

/** The open project's Files tab (design §2): the root project's own `includes`, one row per
 * entry, a pattern's matched files indented beneath it. Fetches `GET /api/files` itself and
 * re-reads it on each new revision, the way every other tab's own screen does; Task 8 gives it
 * its three actions. */
export function FilesPage({ state, path, onPath }: Props) {
  const revision = state?.revision;
  const files = useQuery({
    queryKey: ["files", revision],
    queryFn: () => getFiles(),
    // The table stays while the next revision's entries are read: swapped for a loading line on
    // every edit, it lost the reader's place and made the tab flash - as every other tab's own
    // table already keeps its place across a poll.
    placeholderData: (previous) => previous,
  });
  if (files.data === undefined) {
    if (files.isError) return <Banner tone="error">{files.error.message}</Banner>;
    return <p className="quiet">Reading the project's files…</p>;
  }
  return (
    <>
      {/* A server that stopped answering leaves the table as it was, and says so above it. */}
      {files.isError && <Banner tone="error">{files.error.message}</Banner>}
      <FilesTableView
        reply={files.data}
        files={state?.files ?? []}
        selected={path}
        onSelect={onPath}
      />
    </>
  );
}
