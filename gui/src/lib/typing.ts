/** How long a panel waits after the reader's last keystroke before asking for the plan it
 * previews: long enough that typing a name asks once, short enough that the preview follows. */
export const PLAN_DELAY_MS = 250;

/** How long to wait before asking for a plan: at once for one debounced value's first wait -
 * previewed straight away - and `PLAN_DELAY_MS` for every later one. Per value, not per panel:
 * `useDebounced` keeps `asked` per call, so a panel with several debounced fields asks each
 * field's own first at once, and only a field already asked of before waits. */
export function planDelay(asked: boolean): number {
  return asked ? PLAN_DELAY_MS : 0;
}

/** Whether a plan asked for is the one the reader's fields now say: only then is its preview
 * shown and applied, never one for text the reader has since typed past. */
export function sameRequest(asked: unknown, typed: unknown): boolean {
  return JSON.stringify(asked) === JSON.stringify(typed);
}

/** Whether a value moving into `useDebounced` takes effect at once rather than waiting
 * `planDelay`'s own delay (review fix round 1, Important 3 and Minor 2): a `null` value - nothing
 * to ask for any more, the fields emptied or let go - must never be held past that moment, so the
 * next render sees it gone; and a discrete commit - a chooser pick, Enter, a button - was never a
 * keystroke to wait out to begin with. `typed` is false for exactly those discrete commits, true
 * for text actually typed - only that waits. A gate - `ValuesPage`'s `appliesOver` - is no value
 * moving in at all: it is applied to what comes out (`gated`). */
export function atOnce(value: unknown, typed: boolean): boolean {
  return value === null || !typed;
}

/**
 * What a plan is asked for behind a gate, of `debounced` - `useDebounced`'s own value, the request
 * the fields made once typing paused: nothing while the gate is closed, and `debounced` while it
 * is open and still what the fields say (`sameRequest` against `typed`) - never a plan for text
 * the reader has since typed past.
 *
 * Applied after the debounce, never before it (Ruling T12b-1). Before it, a gate closing made the
 * request `null` and its opening again a change to wait out: the values grid's `appliesOver`
 * closes as a revision lands, opens once an answer of it has come, and the cell typed before it
 * was asked for again only `PLAN_DELAY_MS` later, Apply gone meanwhile with nothing typed. After
 * it, the gate opening asks at once for what the fields still say, and a value typed while it is
 * closed, or just after, waits for its own debounce alone. Closed, it asks for nothing from the
 * very render it closes in, so no plan is asked over what it closed on.
 */
export function gated<T>(debounced: T | null, typed: T | null, open: boolean): T | null {
  if (!open) return null;
  return sameRequest(debounced, typed) ? debounced : null;
}

/** The plan a screen's offer should draw, why its own fetch was refused if it was, and whether
 * it may still change (review fix round 1, Important 1 and 5): all three held back until the
 * debounced request `asked` is what the fields now say (`sameRequest` against `typed`) *and* the
 * query's answer is not an earlier request's, kept on screen as a placeholder while this one is
 * still loading (`query.isPlaceholderData`) - a plan, and a refusal, is never shown or offered
 * for text the reader has since typed past, nor one still settling. Until both hold, `plan` and
 * `refusal` are `null` and `pending` is `true`, and a screen offers no Apply then; a screen's own
 * refusal from applying, or from a file changed on disk, takes precedence over this one and is
 * unaffected by it, exactly as before this function existed.
 *
 * `pending` also holds once both do, while the query is still settling its first answer to the
 * current request (`query.data` not arrived yet) - harmless where it is read only to withhold
 * Apply, since `plan` is `null` then regardless, but it is why `refusal` is read straight from
 * `query.error`, never gated on `pending`: a settled refusal of the *current* request must still
 * be shown, and would otherwise be swallowed by "still loading" meaning the same `pending`. */
export function planShown<T>(
  asked: unknown,
  typed: unknown,
  query: { data: T | undefined; error: { message: string } | null; isPlaceholderData: boolean },
): { plan: T | null; refusal: string | null; pending: boolean } {
  const trusted = sameRequest(asked, typed) && !query.isPlaceholderData;
  return {
    plan: trusted ? (query.data ?? null) : null,
    refusal: trusted ? (query.error?.message ?? null) : null,
    pending: !trusted || query.data === undefined,
  };
}
