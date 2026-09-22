import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, getFix, postEdit } from "../api/client";
import type { State } from "../api/types";
import { FindingPanelView } from "../components/FindingPanelView";
import { FindingsTableView } from "../components/FindingsTableView";
import {
  findingCounts,
  findingRows,
  fixEdit,
  noRouteReason,
  routeHref,
  routeLabel,
  routeOf,
} from "../lib/findings";
import type { Route } from "../lib/route";
import { Banner } from "../ui/Banner";

interface Props {
  state: State | null;
  stopped: boolean;
  /** Following a finding: the route it leads to, which the app navigates to. `routeOf` says
   * what that route is, and `routeHref` writes the address the link carries. */
  onOpen: (route: Route) => void;
}

const STALE =
  "A file changed on disk, so nothing was written. The tab now shows the findings as they are.";

/** The open project's Findings tab (spec 5.1): every finding, worst first, and the panel of the
 * one selected - its route, its notes, and the one fix the tab offers where it carries one
 * (spec 5.2). */
export function FindingsPage({ state, stopped, onOpen }: Props) {
  const queries = useQueryClient();
  const revision = state?.revision;
  const rows = state === null ? [] : findingRows(state);
  const [selected, setSelected] = useState<string | undefined>(undefined);
  const [chosen, setChosen] = useState<string | undefined>(undefined);
  const [changesShown, setChangesShown] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  // The finding whose panel closed because it is no longer among the next revision's rows - the
  // analysis moved on, or somebody else fixed it (spec 5.3) - named above the table until
  // another finding is selected or the reader leaves the tab. `UnitsPage`'s `gone` is the same
  // pattern; a finding has no name of its own to say instead.
  const [gone, setGone] = useState(false);

  const row = rows.find((entry) => entry.key === selected);
  if (selected !== undefined && row === undefined) {
    setSelected(undefined);
    setGone(true);
  }
  const finding = row?.finding;

  const fixes = useQuery({
    queryKey: ["fix", finding?.file, finding?.pointer, finding?.check, revision],
    queryFn:
      finding === undefined
        ? skipToken
        : () => getFix(finding.file, finding.pointer, finding.check),
  });
  const apply = useMutation({
    mutationFn: () => {
      const edit =
        fixes.data === undefined || chosen === undefined ? null : fixEdit(fixes.data, chosen);
      if (edit === null) throw new Error("there is nothing to apply");
      return postEdit(edit);
    },
    onMutate: () => setRefused(null),
    // The reader's own apply closes the panel quietly, exactly as it left it open: the finding
    // is about to be gone from the next revision's rows, but that is the reader's own doing
    // (spec 5.3 reserves the "somebody else fixed it" warning for a finding gone some other
    // way), and clearing `selected` here, before that revision even arrives, is what keeps the
    // render-phase check below from mistaking this for one.
    onSuccess: () => {
      setChangesShown(false);
      setSelected(undefined);
    },
    onError: (error) =>
      setRefused(
        error instanceof ApiError && error.code === "stale"
          ? STALE
          : `The change was refused: ${error.message}`,
      ),
    // Applying a fix changes the file it wrote to, the findings the next revision reports, and
    // any panel reading what it edited: asked for again, as `UnitsPage` does for its own edits.
    onSettled: () =>
      Promise.all([
        queries.invalidateQueries({ queryKey: ["state"] }),
        queries.invalidateQueries({ queryKey: ["fix"] }),
        queries.invalidateQueries({ queryKey: ["variable"] }),
        queries.invalidateQueries({ queryKey: ["unit"] }),
      ]),
  });

  const select = (key: string | undefined) => {
    setGone(false);
    setSelected(key);
    setChosen(undefined);
    setChangesShown(false);
    setRefused(null);
  };

  if (state === null) return <p className="quiet">Reading the project's findings…</p>;
  return (
    <>
      <p className="summary">{findingCounts(state.findings)}</p>
      {gone && <Banner tone="warning">This finding is no longer reported.</Banner>}
      <div className={finding !== undefined ? "with-panel" : undefined}>
        <div>
          <FindingsTableView rows={rows} selected={selected} onSelect={select} />
        </div>
        {finding !== undefined && (
          <div key={selected}>
            {/* The fix a finding carries could not even be asked for - a refusal from the
             * engine itself (e.g. a stale fingerprint), not one the reader's own choice
             * provoked - so it is said here rather than under a fix nothing offered. */}
            {fixes.isError && <Banner tone="error">{fixes.error.message}</Banner>}
            <FindingPanelView
              finding={finding}
              label={routeLabel(finding, state)}
              href={routeHref(finding)}
              reason={noRouteReason(finding, state)}
              onOpen={() => {
                const route = routeOf(finding);
                if (route !== null) onOpen(route);
              }}
              fixes={fixes.data ?? null}
              chosen={chosen}
              onChoose={setChosen}
              changesShown={changesShown}
              onChangesShown={setChangesShown}
              onApply={() => apply.mutate()}
              refusal={refused}
              busy={stopped || apply.isPending}
              onClose={() => select(undefined)}
            />
          </div>
        )}
      </div>
    </>
  );
}
