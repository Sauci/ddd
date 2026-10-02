import { useEffect, useRef, useState } from "react";
import { atOnce, planDelay, sameRequest } from "../lib/typing";

/**
 * The value last asked for (spec §6, "typing never waits"): starts at `value` itself, so a panel
 * mounted on one has nothing to wait for. A later `value` moves in at once when `atOnce(value,
 * typed)` says so - `null` (nothing to ask, or a gate such as `ValuesPage`'s `appliesOver`
 * closing), or `typed` false (a discrete commit: a chooser pick, Enter, a button) - and otherwise
 * after `planDelay(asked)`: at once the first time this ever waits, `PLAN_DELAY_MS` after every
 * later one. A newer `value` arriving before a wait is over cancels it and starts a fresh one
 * from itself; the component unmounting cancels it the same way, through the effect's own
 * cleanup. `typed` defaults to `true`, for every screen whose one debounced field is always typed
 * into (a plain field, or a chooser wired the same way) - `TypePanel`'s key chooser and
 * `VariablePanel`'s settle chooser pass `false` while a pick or the starting value stands, `true`
 * only once the reader has actually typed into a `limits` row's own fields.
 *
 * Glue only (Global Constraints: "no decision may live in a .tsx file... a src/app hook is glue
 * only"): `atOnce`, `planDelay` and `sameRequest` are `gui/src/lib`'s own, under the Vitest gate.
 * This hook decides nothing - it only runs the timer `planDelay` tells it to, or skips it when
 * `atOnce` says to move at once, and `asked` (whether a wait has ever actually been timed out
 * already) is kept only to ask `planDelay` for the right one next.
 *
 * Two bugs review fix round 1 found live, both from comparing by *reference* rather than by
 * `sameRequest`'s content, since every screen builds its request as a fresh object every render:
 *
 * - **It never came to rest.** The old effect's own guard (`value === debounced`) was `false` on
 *   almost every render once a wait had resolved once: `setDebounced` itself causes a render, the
 *   screen rebuilds the very same request as a new object, the guard sees two different
 *   references and schedules another wait, which resolves and renders again - without end, 12 to
 *   24 times every 3 seconds at rest, confirmed live by counting React's own commits. Comparing
 *   with `sameRequest` instead - true of two objects with the same content, whoever built them -
 *   lets the guard actually recognise "nothing changed" and stop.
 * - **A closing gate was held open.** `ValuesPage`'s cell plan is asked for only while its own
 *   `appliesOver` gate holds; once it closes, the live request goes `null` at once, but the old
 *   effect still timed out a plain wait before the *debounced* value followed it - so the query,
 *   keyed on that lagging value, could still be asked again for up to `PLAN_DELAY_MS` after the
 *   gate closed, including the instant a new revision lands and the query key's own `revision`
 *   changes under it. `atOnce`'s null case is resolved below *during render*, not through the
 *   effect: React's own sanctioned way to derive state from a value that changed (see "Storing
 *   information from previous renders" in the React docs), because an effect runs only after this
 *   render's other hooks already have - too late to stop a sibling `useQuery`, reading this same
 *   `debounced` in its own key on this same render, from asking for the very thing the gate just
 *   closed on.
 */
export function useDebounced<T>(value: T, typed = true): T {
  const [debounced, setDebounced] = useState(value);
  const asked = useRef(false);
  const immediate = atOnce(value, typed);

  if (immediate && !sameRequest(debounced, value)) {
    setDebounced(value);
  }

  useEffect(() => {
    // Already at rest - true once `debounced` already matches `value`, content for content, not
    // only on the render this hook first runs - so there is nothing to wait for and no timer to
    // start. An `immediate` value is handled above, during render, and never reaches a timer.
    if (immediate || sameRequest(value, debounced)) return undefined;
    const timer = setTimeout(() => {
      setDebounced(value);
      asked.current = true;
    }, planDelay(asked.current));
    return () => clearTimeout(timer);
  }, [value, debounced, immediate]);

  return immediate ? value : debounced;
}
