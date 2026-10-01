import {
  skipToken,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { ApiError, getFindings, getFix, postEdit } from "../api/client";
import type { ListedFinding, State } from "../api/types";
import { FindingPanelView } from "../components/FindingPanelView";
import { FindingsTableView } from "../components/FindingsTableView";
import {
  findingCounts,
  findingsTotal,
  fixEdit,
  noRouteReason,
  routeHref,
  routeLabel,
  routeOf,
  stillReported,
} from "../lib/findings";
import {
  arrivedPages,
  BOX_HEIGHT,
  pageQuery,
  pagesOf,
  spacersOf,
  spanOf,
  windowRows,
} from "../lib/findingsWindow";
import { type Refused, shownRefusal } from "../lib/refusals";
import type { Route } from "../lib/route";
import { fixLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";

interface Props {
  state: State;
  stopped: boolean;
  /** Following a finding: the route it leads to, which the app navigates to. `routeOf` says
   * what that route is, and `routeHref` writes the address the link carries. */
  onOpen: (route: Route) => void;
}

const STALE =
  "A file changed on disk, so nothing was written. The tab now shows the findings as they are.";

/** The open project's Findings tab (spec 5.1): every finding, worst first, and the panel of the
 * one selected - its route, its notes, and the one fix the tab offers where it carries one
 * (spec 5.2). The table is a window: the rows in view and a margin, each page of them asked for
 * as the box scrolls to it (spec 6), how many there are in all being the state's own count. */
export function FindingsPage({ state, stopped, onOpen }: Props) {
  const queries = useQueryClient();
  const revision = state.revision;
  const total = findingsTotal(state.counts);
  // Where the box is scrolled to and how tall it is: at the top and one box high, until the box
  // says otherwise.
  const [view, setView] = useState({ top: 0, height: BOX_HEIGHT });
  const onScroll = useCallback((top: number, height: number) => setView({ top, height }), []);
  const span = spanOf(view.top, view.height, total);
  const pages = pagesOf(span);
  const asked = useQueries({
    queries: pages.map((page) => ({
      queryKey: ["findings", revision, page],
      queryFn: () => getFindings(pageQuery(page)),
      // A page of one revision is the same page however often it is asked: one scrolled back
      // to is drawn from what came, not asked again.
      staleTime: Number.POSITIVE_INFINITY,
    })),
  });
  const rows = windowRows(
    span,
    arrivedPages(
      pages,
      asked.map((page) => page.data),
    ),
  );
  const unasked = asked.find((page) => page.isError)?.error ?? null;
  // The finding whose panel is open, kept whole: the window may have scrolled its row away.
  const [selected, setSelected] = useState<ListedFinding | undefined>(undefined);
  const [chosen, setChosen] = useState<string | undefined>(undefined);
  const [changesShown, setChangesShown] = useState(false);
  // A refused apply for a reason other than staleness, if any: cleared whenever the reader
  // chooses again, exactly as before this task.
  const [refused, setRefused] = useState<string | null>(null);
  // A refused apply because a file changed on disk, the row it was made from, and the revision
  // it happened at. As in the variable and unit panels, a reader who chooses again straight away
  // would otherwise send the same stale fingerprints the server just refused; `shownRefusal`
  // keeps it shown until a later revision arrives. Kept with the row's own key, the way
  // `UnitPanel` keeps it with the action it belongs to: the wait is about the fix that was
  // refused, so another finding selected in the meantime must not be given its sentence - the
  // file it names need not even be one that finding is about.
  const [stale, setStale] = useState<({ key: string | undefined } & Refused) | null>(null);
  // The finding whose panel closed because the next revision no longer reports it - the
  // analysis moved on, or somebody else fixed it (spec 5.3) - named above the table until
  // another finding is selected or the reader leaves the tab. `UnitsPage`'s `gone` is the same
  // pattern; a finding has no name of its own to say instead.
  const [gone, setGone] = useState(false);

  // Asked again of every revision while a panel is open: the findings of its file and its check,
  // among which it is still reported or is not.
  const reported = useQuery({
    queryKey: ["findings", revision, "reported", selected?.file, selected?.check],
    queryFn:
      selected === undefined
        ? skipToken
        : () => getFindings({ file: selected.file, check: selected.check }),
  });
  if (
    selected !== undefined &&
    reported.data !== undefined &&
    !stillReported(selected.key, reported.data)
  ) {
    setSelected(undefined);
    setGone(true);
  }

  const fixes = useQuery({
    queryKey: ["fix", selected?.file, selected?.pointer, selected?.check, revision],
    queryFn:
      selected === undefined
        ? skipToken
        : () => getFix(selected.file, selected.pointer, selected.check),
  });
  const apply = useMutation({
    mutationFn: () => {
      const edit =
        fixes.data === undefined || chosen === undefined || selected === undefined
          ? null
          : fixEdit(fixes.data, chosen, fixLabel(selected, chosen));
      if (edit === null) throw new Error("there is nothing to apply");
      return postEdit(edit);
    },
    onMutate: () => setRefused(null),
    // The reader's own apply closes the panel quietly, exactly as it left it open: the finding
    // is about to be gone from the next revision's rows, but that is the reader's own doing
    // (spec 5.3 reserves the "somebody else fixed it" warning for a finding gone some other
    // way), and clearing `selected` here, before that revision even arrives, is what keeps the
    // render-phase check of whether it is still reported from mistaking this for one. A success
    // is a definite answer, so it also clears a stale wait left over from an earlier attempt.
    onSuccess: () => {
      setChangesShown(false);
      setSelected(undefined);
      setStale(null);
    },
    // Stale is the one refusal that waits for a later revision rather than clearing; setting one
    // kind clears the other, so the panel never shows two different answers to the same apply.
    onError: (error) => {
      if (error instanceof ApiError && error.code === "stale") {
        setStale({ key: selected?.key, text: STALE, revision });
        setRefused(null);
      } else {
        setRefused(`The change was refused: ${error.message}`);
        setStale(null);
      }
    },
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

  const select = (finding: ListedFinding | undefined) => {
    setGone(false);
    setSelected(finding);
    setChosen(undefined);
    setChangesShown(false);
    setRefused(null);
  };

  return (
    <>
      <p className="summary">{findingCounts(state.counts, false)}</p>
      {gone && <Banner tone="warning">This finding is no longer reported.</Banner>}
      {unasked !== null && <Banner tone="error">{unasked.message}</Banner>}
      <div className={selected !== undefined ? "with-panel" : undefined}>
        <div>
          <FindingsTableView
            rows={rows}
            {...spacersOf(span, total)}
            selected={selected?.key}
            onSelect={select}
            onScroll={onScroll}
          />
        </div>
        {selected !== undefined && (
          <div key={selected.key}>
            {/* The fix a finding carries could not even be asked for - a refusal from the
             * engine itself (e.g. a stale fingerprint), not one the reader's own choice
             * provoked - so it is said here rather than under a fix nothing offered. */}
            {fixes.isError && <Banner tone="error">{fixes.error.message}</Banner>}
            <FindingPanelView
              finding={selected}
              label={routeLabel(selected, state)}
              href={routeHref(selected)}
              reason={noRouteReason(selected, state)}
              onOpen={() => {
                const route = routeOf(selected);
                if (route !== null) onOpen(route);
              }}
              fixes={fixes.data ?? null}
              chosen={chosen}
              onChoose={setChosen}
              changesShown={changesShown}
              onChangesShown={setChangesShown}
              onApply={() => apply.mutate()}
              refusal={
                (stale !== null && stale.key === selected.key
                  ? shownRefusal(stale, revision)
                  : null) ?? refused
              }
              busy={stopped || apply.isPending}
              onClose={() => select(undefined)}
            />
          </div>
        )}
      </div>
    </>
  );
}
