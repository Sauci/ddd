import { skipToken, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getCompare } from "../api/client";
import type { State } from "../api/types";
import { CompareView } from "../components/CompareView";
import { findingRows } from "../lib/findings";

interface Props {
  state: State | null;
  stopped: boolean;
}

/**
 * The open project's Compare tab: can it replace a baseline delivery? Holds the baseline path,
 * the reply the server last gave for it, and which of its findings the reader has selected -
 * `CompareView` draws all three, holding none of them itself.
 *
 * Re-asks whenever the revision changes: `revision` sits in the query's own key beside the
 * baseline last asked for, exactly as `FindingsPage` reads `state?.revision` into its own `fix`
 * query, so that fixing what the verdict complained about turns it while the tab is open (spec
 * 2026-09-26-gui-compare-design.md §4) - and typing in the field, which never touches `asked`,
 * cannot itself trigger a request.
 */
export function ComparePage({ state, stopped }: Props) {
  const revision = state?.revision;
  // What the field shows, typed freely.
  const [baseline, setBaseline] = useState("");
  // The baseline last asked for, or `null` before the reader has asked at all - what keys the
  // query, so a later revision re-asks *this* baseline rather than whatever the field shows by
  // then.
  const [asked, setAsked] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | undefined>(undefined);
  const compare = useQuery({
    queryKey: ["compare", asked, revision],
    queryFn: asked === null ? skipToken : () => getCompare(asked),
  });
  const reply = compare.data ?? null;
  // The finding whose panel was open closes quietly when a fresh reply no longer carries it - a
  // re-ask, whether the reader's own or the revision's, is answered wholesale, never one row
  // fixed from under the reader the way an edit in the Findings tab can be, so this needs no
  // banner of its own the way that tab's `gone` does.
  if (
    reply !== null &&
    selected !== undefined &&
    !findingRows(reply.findings).some((row) => row.key === selected)
  ) {
    setSelected(undefined);
  }
  return (
    <CompareView
      baseline={baseline}
      onBaseline={setBaseline}
      // Trimmed here, once, rather than where the field is typed: `CompareView`'s own disabled
      // check reads the same way (`baseline.trim() === ""`), so the two must agree on what
      // counts as "nothing typed" - and a path with a stray leading or trailing space is not a
      // path under the root the server would find.
      onAsk={() => setAsked(baseline.trim())}
      reply={reply}
      refusal={compare.isError ? compare.error.message : null}
      busy={stopped || compare.isFetching}
      selected={selected}
      onSelect={setSelected}
    />
  );
}
