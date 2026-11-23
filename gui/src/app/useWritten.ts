import { useState, useSyncExternalStore } from "react";
import { type WrittenLine, writtenSince } from "../lib/announcing";
import { ownEdits } from "../state/edits";

/**
 * What the heading's line says the page last wrote (`writtenSince`, 16:I13): a write of the page's
 * own made since `page` - what the heading heads, a tab, a component's file - was drawn, and none
 * made before, which is no longer the news of the page drawn.
 *
 * Glue only: the sentence is `lib/announcing.ts`'s, the writes `ownEdits`'.
 */
export function useWritten(page: string): WrittenLine | null {
  const last = useSyncExternalStore(ownEdits.subscribe, ownEdits.last);
  const [since, setSince] = useState({ page, edit: last?.edit ?? 0 });
  if (since.page !== page) setSince({ page, edit: last?.edit ?? 0 });
  return since.page === page ? writtenSince(last, since.edit) : null;
}
