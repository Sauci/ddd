import { startTransition, useEffect, useState } from "react";
import { rowsDrawnNext, sameRows } from "../lib/filter";

/**
 * The rows a filtered table draws (16:I14, fix round 1): `shown`, the rows its filter leaves,
 * reached at most `ROWS_PUT_BACK` rows put back at a time (`rowsDrawnNext`, lib/filter.ts). The
 * first step is drawn in the render the filter changed in, so that the table never draws a row
 * the filter does not leave; each next step in a transition of its own once the last is drawn,
 * which a key typed meanwhile goes ahead of. `shown` keeps its identity while its rows do: the
 * caller memoises it.
 *
 * Glue only: which rows each step draws is `rowsDrawnNext`'s to say, and `sameRows`' whether a
 * step drew anything new. This hook keeps the rows last drawn, from which the next step starts.
 */
export function useDrawnRows<T>(shown: readonly T[], key: (row: T) => string): readonly T[] {
  const [drawn, setDrawn] = useState(shown);
  const next = rowsDrawnNext(shown, drawn, key);
  useEffect(() => {
    if (!sameRows(drawn, next)) startTransition(() => setDrawn(next));
  }, [drawn, next]);
  return next;
}
