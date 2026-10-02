/** How long a panel waits after the reader's last keystroke before asking for the plan it
 * previews: long enough that typing a name asks once, short enough that the preview follows. */
export const PLAN_DELAY_MS = 250;

/** How long to wait before asking for a plan: at once for a panel's first - opening it previews
 * straight away - and `PLAN_DELAY_MS` for every later one. */
export function planDelay(asked: boolean): number {
  return asked ? PLAN_DELAY_MS : 0;
}

/** Whether a plan asked for is the one the reader's fields now say: only then is its preview
 * shown and applied, never one for text the reader has since typed past. */
export function sameRequest(asked: unknown, typed: unknown): boolean {
  return JSON.stringify(asked) === JSON.stringify(typed);
}
