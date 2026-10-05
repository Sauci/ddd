import { useEffect, useRef, useState } from "react";
import { atOnce, planDelay, sameRequest } from "../lib/typing";

/**
 * The value last asked for (spec §6, "typing never waits"): starts at `value` itself, so a panel
 * mounted on one has nothing to wait for. A later `value` moves in at once when `atOnce(value,
 * typed)` says so - `null` (nothing to ask any more), or `typed` false (a discrete commit: a
 * chooser pick, Enter, a button) - and otherwise after `planDelay(asked)`: at once the first time
 * this ever waits, `PLAN_DELAY_MS` after every later one. A newer `value` arriving before a wait
 * is over cancels it and starts a fresh one from itself; the component unmounting cancels it the
 * same way, through the effect's own cleanup. `typed` defaults to `true`, for every screen whose
 * one debounced field is always typed into (a plain field, or a chooser wired the same way). A
 * screen whose one debounced value can also arrive from a discrete pick passes its own, kept
 * `typed` state instead - never inferred from the value itself, which a pick and typing can both
 * leave in the very same shape (`TypePanel`'s `typedLimits` and `VariablePanel`'s own of the same
 * name, each false for a pick of a `limits` row, including the row's own starting range the
 * moment it opens, true only once Min or Max is actually typed into; `DeclarePanel`'s
 * `typedEdit`, over its one combined request, the same way). Fix round 2's own finding: this hook
 * only ever compares the value `atOnce` and `sameRequest` are given, so a screen that let `typed`
 * follow the value's own presence, rather than keeping its own record of which kind of edit it
 * just made, told it a `limits` pick was typing and waited `PLAN_DELAY_MS` for a preview that
 * should have shown at once.
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
 * - **A closing gate was held open.** `ValuesPage`'s cell plan was then gated before this hook:
 *   its `appliesOver` gate closing made the live request `null` at once, but the old effect still
 *   timed out a plain wait before the *debounced* value followed it - so the query, keyed on that
 *   lagging value, could still be asked again for up to `PLAN_DELAY_MS` after the gate closed,
 *   including the instant a new revision lands and the query key's own `revision` changes under
 *   it. `atOnce`'s null case is resolved below *during render*, not through the effect: React's
 *   own sanctioned way to derive state from a value that changed (see "Storing information from
 *   previous renders" in the React docs), because an effect runs only after this render's other
 *   hooks already have - too late to stop a sibling `useQuery`, reading this same `debounced` in
 *   its own key on this same render, from asking for what it no longer should. The gate itself
 *   is applied after this hook now (`gated`, `lib/typing.ts`, Ruling T12b-1): before it, its
 *   opening again was a change this hook waited out, `PLAN_DELAY_MS` with nothing typed.
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
