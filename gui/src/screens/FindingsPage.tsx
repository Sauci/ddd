import {
  skipToken,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { getFindings, getFix, postEdit } from "../api/client";
import type { ListedFinding, State } from "../api/types";
import { useUpdating } from "../app/updating";
import { useDebounced } from "../app/useDebounced";
import { FindingPanelView } from "../components/FindingPanelView";
import { FindingsTableView } from "../components/FindingsTableView";
import { filterText } from "../lib/filter";
import {
  findingCounts,
  findingsTotal,
  fixEdit,
  noRouteReason,
  placeOf,
  routeHref,
  routeLabel,
  routeOf,
  selectionAfter,
} from "../lib/findings";
import {
  arrivedPages,
  BOX_HEIGHT,
  drawnWindow,
  type FindingsPlace,
  type KeptWindow,
  keptAfter,
  listingTotal,
  namedBy,
  opensAt,
  pageQuery,
  pagesOf,
  placeOpened,
  scrolledTop,
  spacersOf,
  spanOf,
  windowLine,
  windowRows,
} from "../lib/findingsWindow";
import { fileNames } from "../lib/paths";
import { refusalSentence } from "../lib/refusals";
import type { Route } from "../lib/route";
import { fixLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { FilterField } from "../ui/FilterField";

interface Props {
  state: State;
  /** What the filter holds as the tab opens, as its address asks (the route's own `text`): the
   * name of a file the banner under the masthead says did not load, leading to its finding
   * (16:I9), or what the reader typed before a reload. `undefined` for the bare tab, which filters
   * nothing. */
  text: string | undefined;
  /** What the filter asks for once typing pauses, `""` for nothing, which the app writes into the
   * address, replacing it (16:I9): the address follows the filter, so that a reload keeps it and a
   * link to a file's findings, pressed after other text was typed, is a move to another address. */
  onText: (text: string) => void;
  /** The tab's place as it was last drawn (`FindingsPlace`), which the app holds above it while
   * another page is shown (16:M16), `null` before the tab was drawn: read as the tab is drawn anew,
   * which opens at it where it is of the listing the address asks for (`placeOpened`). */
  place: () => FindingsPlace | null;
  /** The tab's place as it moves - the listing asked, its box's scroll, the finding whose panel is
   * open - for the app to hold. */
  onPlace: (place: FindingsPlace) => void;
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
 * as the box scrolls to it (spec 6), how many there are in all being the state's own count - a
 * disagreement on each of its files - where the line above it counts the statements, each once as
 * `ddd check` counts them (decision 14.3). When an analysis lands, the window keeps drawing the
 * revision it drew whole until the new one's pages for its rows have all come (`drawnWindow`).
 *
 * The filter above the table (16:I14) asks the server for the findings whose check, words or
 * file's name hold its text, once typing pauses: the rows are the server's pages, which the page
 * cannot filter itself. A filtered listing's first page says how many rows it has (`listingTotal`),
 * and the listing drawn before stays until its own rows have come, as through a landing. Its table
 * starts at its top, and the line beside the filter counts it (`windowLine`), where the line above
 * the table goes on counting the revision's statements.
 *
 * Drawn anew at each following, the tab opens at its place (16:M16): the box scrolled where it
 * stood and the finding's panel open, where the place the app holds is of the listing the address
 * asks for (`placeOpened`) - a finding followed and Back, the tab pressed, a component's page's way
 * back - and otherwise at that listing's top, no panel open. */
export function FindingsPage({ state, text, onText, place, onPlace, stopped, onOpen }: Props) {
  const queries = useQueryClient();
  const updating = useUpdating();
  const revision = state.revision;
  const all = findingsTotal(state.counts);
  // What the filter holds, starting as the address asks, and what it asks the server for once
  // typing pauses: its text, without the white space around it, `""` for none. Asked at once as
  // the tab opens (`useDebounced` starts at its value).
  const [typed, setTyped] = useState(text ?? "");
  const asking = useDebounced(filterText(typed));
  // Where the tab opens, read once as it is drawn anew: the listing the address asks for, and the
  // place held of it, or its top.
  const [opening] = useState(() => {
    const listing = filterText(text ?? "");
    return { listing, ...placeOpened(place(), state.project, listing) };
  });
  // The address follows what the filter asks, written where it says otherwise.
  useEffect(() => {
    if (asking !== (text ?? "")) onText(asking);
  }, [asking, text, onText]);
  // Where the box is scrolled to and how tall it is, and the filter it was scrolled under: where the
  // tab opens and one box high, until the box says otherwise - and at the top again for a filter
  // newly asked, whose table is drawn anew (`scrolledTop`, and `key` below).
  const [view, setView] = useState({
    text: opening.listing,
    top: opening.top,
    height: BOX_HEIGHT,
  });
  const onScroll = useCallback(
    (top: number, height: number) => setView({ text: asking, top, height }),
    [asking],
  );
  const top = scrolledTop(view, asking);
  // A filtered listing's first page, which says how many rows the listing has: asked as soon as the
  // filter is, whatever the box covers - the same query as the window's own first page.
  const head = useQuery({
    queryKey: ["findings", revision, "page", asking, 0],
    queryFn: () => getFindings(pageQuery(0, asking)),
    enabled: asking !== "",
    staleTime: Number.POSITIVE_INFINITY,
  });
  const total = listingTotal(asking, all, head.data, revision);
  const span = spanOf(top, view.height, total ?? 0);
  const pages = pagesOf(span);
  const asked = useQueries({
    queries: pages.map((page) => ({
      queryKey: ["findings", revision, "page", asking, page],
      queryFn: () => getFindings(pageQuery(page, asking)),
      // A page of one revision is the same page however often it is asked: one scrolled back
      // to is drawn from what came, not asked again.
      staleTime: Number.POSITIVE_INFINITY,
    })),
  });
  // The listing last drawn whole, and its own pages of the rows in the box, as they came: read
  // where they are, never asked for again - the server answers the newest revision alone. While it
  // is the newest, these are the very queries above, so they carry the same function: each
  // observer's options become its query's, and a refetch - after an undo - runs the last set.
  const [kept, setKept] = useState<KeptWindow | null>(null);
  const keptSpan = spanOf(top, view.height, kept?.total ?? 0);
  const keptPages = kept === null ? [] : pagesOf(keptSpan);
  const held = useQueries({
    queries: keptPages.map((page) => ({
      queryKey: ["findings", kept?.revision, "page", kept?.text, page],
      queryFn: () => getFindings(pageQuery(page, kept?.text)),
      enabled: false,
    })),
  });
  const drawn = drawnWindow(
    {
      revision,
      text: asking,
      total,
      all,
      statements: state.statements,
      span,
      pages: arrivedPages(
        pages,
        asked.map((page) => page.data),
        revision,
      ),
    },
    kept === null
      ? null
      : {
          ...kept,
          span: keptSpan,
          pages: arrivedPages(
            keptPages,
            held.map((page) => page.data),
            kept.revision,
          ),
        },
  );
  const keeping = keptAfter(drawn, kept);
  if (keeping !== kept) setKept(keeping);
  const names = fileNames(state.files.map((file) => file.path));
  const rows = windowRows(drawn.span, drawn.pages, names);
  const unasked = head.error ?? asked.find((page) => page.isError)?.error ?? null;
  // The finding whose panel is open, kept whole - as it was selected, then as the newest reply
  // about it reported it: the window may have scrolled its row away. The place's, as the tab opens.
  const [selected, setSelected] = useState<ListedFinding | undefined>(opening.selected);
  const [chosen, setChosen] = useState<string | undefined>(undefined);
  const [changesShown, setChangesShown] = useState(false);
  // What the server refused the last apply for, if it did, in the tab's own words where a file
  // changed on disk (`STALE`): held until the reader chooses again - another finding, another fix,
  // the same one let go and chosen again, or Apply pressed once more - whatever its code, and never
  // let go by a revision landing (`Refused`, lib/refusals.ts). Another finding selected meanwhile
  // is a choice, so it is never given this one's sentence.
  const [refused, setRefused] = useState<string | null>(null);
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
  // What the panel keeps of its finding once that reply has come (`selectionAfter`): the newest
  // report of it, kept as the selection, or nothing once the reply no longer reports it - when the
  // panel closes, and the tab says so.
  const after = selectionAfter(selected, reported.data);
  if (after.selected !== selected) {
    setSelected(after.selected);
    setGone(after.gone);
  }
  const finding = after.selected;
  // The tab's place as it moves, for the app to hold while another page is shown (16:M16): the
  // listing asked, where its box is scrolled to, and the finding whose panel is open.
  useEffect(() => {
    onPlace({ project: state.project, text: asking, top, selected: finding });
  }, [onPlace, state.project, asking, top, finding]);

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
        fixes.data === undefined || chosen === undefined || finding === undefined
          ? null
          : fixEdit(fixes.data, chosen, fixLabel(finding, chosen));
      if (edit === null) throw new Error("there is nothing to apply");
      return postEdit(edit);
    },
    onMutate: () => setRefused(null),
    // The reader's own apply closes the panel quietly, exactly as it left it open: the finding
    // is about to be gone from the next revision's rows, but that is the reader's own doing
    // (spec 5.3 reserves the "somebody else fixed it" warning for a finding gone some other
    // way), and clearing `selected` here, before that revision even arrives, is what keeps the
    // render-phase check of whether it is still reported from mistaking this for one.
    onSuccess: () => {
      setChangesShown(false);
      setSelected(undefined);
    },
    onError: (error) => setRefused(refusalSentence(error, STALE)),
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

  // Choosing a fix, or letting it go, is the reader's next choice too.
  const choose = (title: string | undefined) => {
    setChosen(title);
    setRefused(null);
  };

  return (
    <>
      {/* The revision the table draws: the one kept while the newest's pages come (`drawnWindow`). */}
      <p className="summary">{findingCounts(drawn.statements, updating)}</p>
      {gone && <Banner tone="warning">This finding is no longer reported.</Banner>}
      {unasked !== null && <Banner tone="error">{unasked.message}</Banner>}
      <FilterField
        label="Filter findings"
        value={typed}
        onChange={setTyped}
        line={windowLine(drawn)}
      />
      <div className={finding !== undefined ? "with-panel" : undefined}>
        <div>
          <FindingsTableView
            // Drawn anew for each filter asked, its box where `top` is: at the place the tab opens
            // at, for the listing it opens on, and at the top for one newly asked.
            key={asking}
            rows={rows}
            {...spacersOf(drawn.span, drawn.total ?? 0)}
            opensAt={opensAt(drawn, top)}
            selected={finding?.key}
            onSelect={select}
            onScroll={onScroll}
          />
        </div>
        {finding !== undefined && (
          <div key={finding.key}>
            {/* The fix a finding carries could not even be asked for - a refusal from the
             * engine itself (e.g. a stale fingerprint), not one the reader's own choice
             * provoked - so it is said here rather than under a fix nothing offered. */}
            {fixes.isError && <Banner tone="error">{fixes.error.message}</Banner>}
            <FindingPanelView
              finding={finding}
              label={routeLabel(finding, state)}
              href={routeHref(finding)}
              reason={noRouteReason(finding, state)}
              place={placeOf(finding, namedBy(names))}
              fileName={namedBy(names)}
              onOpen={() => {
                const route = routeOf(finding);
                if (route !== null) onOpen(route);
              }}
              fixes={fixes.data ?? null}
              chosen={chosen}
              onChoose={choose}
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
