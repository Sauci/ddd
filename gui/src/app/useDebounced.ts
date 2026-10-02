import { useEffect, useRef, useState } from "react";
import { planDelay } from "../lib/typing";

/**
 * The value last asked for (spec §6, "typing never waits"): starts at `value` itself, so a panel
 * mounted on one has nothing to wait for; moves to a new `value` only after `planDelay(asked)` -
 * at once the first time this ever moves, `PLAN_DELAY_MS` after every later one, exactly as
 * `planDelay`'s own doc reads. A newer `value` arriving before the wait is over cancels it and
 * starts a fresh one from itself, so only the reader's latest is ever the one waited for; the
 * component unmounting cancels it the same way, through the effect's own cleanup.
 *
 * Glue only (Global Constraints: "no decision may live in a .tsx file... a src/app hook is glue
 * only"): `planDelay` is `gui/src/lib`'s own, under the Vitest gate. This hook decides nothing -
 * it only runs the timer `planDelay` tells it to, and `asked` (whether it has ever fired once
 * already) is kept only to ask `planDelay` for the right one next.
 */
export function useDebounced<T>(value: T): T {
  const [debounced, setDebounced] = useState(value);
  const asked = useRef(false);

  useEffect(() => {
    // Already what is asked for - true on the render this hook first runs, `useState`'s own
    // initial value being `value` itself - so there is nothing to wait for and no timer to start;
    // starting one here regardless would mark `asked` true before the reader has typed anything,
    // and their very first keystroke would then wait `PLAN_DELAY_MS` rather than ask at once.
    if (value === debounced) return undefined;
    const timer = setTimeout(() => {
      setDebounced(value);
      asked.current = true;
    }, planDelay(asked.current));
    return () => clearTimeout(timer);
  }, [value, debounced]);

  return debounced;
}
