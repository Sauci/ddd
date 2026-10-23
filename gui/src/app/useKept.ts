import type { UseQueryResult } from "@tanstack/react-query";
import { useState } from "react";
import { type Kept, kept, shown } from "../lib/kept";

/** A screen's answer as it should draw it (`shown`, lib/kept.ts): its query's own, or, once the
 * read of a new revision failed, the last good one for the same question; none once a read was
 * refused. The kept answer is state adjusted while rendering - React's own pattern for state that
 * follows what a render is given - so the render in which the read fails already draws it, with
 * no frame of the error alone. */
export function useKept<T>(query: UseQueryResult<T>, identity: string): T | undefined {
  const [before, setBefore] = useState<Kept<T> | null>(null);
  const after = kept(query.data, query.isPlaceholderData, identity, before);
  if (after !== before) setBefore(after);
  return shown(query.data, identity, after, query.error);
}
