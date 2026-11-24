import { skipToken, useQuery } from "@tanstack/react-query";
import { type Dispatch, type SetStateAction, useState } from "react";
import { getCompare } from "../api/client";
import type { State } from "../api/types";
import { CompareView } from "../components/CompareView";
import { askedIn, type CompareHeld, compareRows, heldFor, typedIn } from "../lib/compare";
import type { Route } from "../lib/route";

interface Props {
  state: State;
  stopped: boolean;
  /** What the tab holds while another tab is shown (`CompareHeld`), held above it by the app so
   * that leaving the tab and coming back finds its field and its verdict as they were (16:M2):
   * `null` before the tab was first used. */
  held: CompareHeld | null;
  onHeld: Dispatch<SetStateAction<CompareHeld | null>>;
  /** Following a finding that names a place in the open project, which the app navigates to -
   * `FindingsPage`'s own prop, wired the same way from `App`. */
  onOpen: (route: Route) => void;
}

/**
 * The open project's Compare tab: can it replace a baseline delivery? Reads the baseline path and
 * the comparison last asked for from what the app holds for it (`held`), asks the server for that
 * comparison, and holds which of its findings the reader has selected - `CompareView` draws all
 * three, holding none of them itself.
 *
 * Re-asks whenever the revision changes: `revision` sits in the query's own key beside the
 * comparison last asked for, exactly as `FindingsPage` reads `state.revision` into its own `fix`
 * query, so that fixing what the verdict complained about turns it, on this tab or on another and
 * coming back (spec 2026-09-26-gui-compare-design.md §4) - and typing in the field, which never
 * touches the ask, cannot itself trigger a request. Asking again for the baseline just asked for
 * asks again too: every ask is numbered into the key (`nextAsk`), so the server reads the
 * baseline's file as it stands, where the answer the page held would have stood for a file made or
 * written over since. Nothing else asks: coming back to the tab draws the answer the page holds for
 * that key (`staleTime`), and asks for it again only where the page has let that answer go, five
 * minutes after the tab last drew it - TanStack Query's own `gcTime`, left as it is, so that the
 * answers of asks no tab draws any more are not kept for as long as the page is open.
 */
export function ComparePage({ state, stopped, held, onHeld, onOpen }: Props) {
  const revision = state.revision;
  const project = state.project;
  // What the field shows, typed freely, and the comparison last asked for, or `null` before the
  // reader has asked at all - what keys the query, so a later revision re-asks *this* baseline
  // rather than whatever the field shows by then, and so that asking for it again is a query of
  // its own (`nextAsk`). Both the open project's (`heldFor`).
  const { typed, asked } = heldFor(held, project);
  const [selected, setSelected] = useState<string | undefined>(undefined);
  const compare = useQuery({
    queryKey: ["compare", asked, revision],
    queryFn: asked === null ? skipToken : () => getCompare(asked.baseline),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const reply = compare.data ?? null;
  // The finding whose panel was open closes quietly when a fresh reply no longer carries it - a
  // re-ask, whether the reader's own or the revision's, is answered wholesale, never one row
  // fixed from under the reader the way an edit in the Findings tab can be, so this needs no
  // banner of its own the way that tab's `gone` does.
  if (
    reply !== null &&
    selected !== undefined &&
    !compareRows(reply).some((row) => row.key === selected)
  ) {
    setSelected(undefined);
  }
  return (
    <CompareView
      state={state}
      onOpen={onOpen}
      baseline={typed}
      onBaseline={(text) => onHeld((current) => typedIn(heldFor(current, project), text))}
      // The path the field names, asked for in `nextAsk`, once, rather than where the field is
      // typed: `CompareView`'s own disabled check reads the same way (`asksNothing`), so the two
      // agree on what counts as nothing typed.
      onAsk={() => onHeld((current) => askedIn(heldFor(current, project)))}
      asked={asked?.baseline ?? ""}
      reply={reply}
      refusal={compare.isError ? compare.error.message : null}
      busy={stopped || compare.isFetching}
      selected={selected}
      onSelect={setSelected}
    />
  );
}
