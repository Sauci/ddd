import type { Changes, PlanReply, SharedEntry, SharedReply } from "../api/types";
import { planEdit as editOfPlan } from "./projectUnits";

/** The line above the table: what this tab holds, or that the project has nothing of the kind.
 *
 * A project with no constants is told so in words rather than shown a table with a zero in it:
 * the tab is where a constant is declared, and an empty table with a count above it reads as a
 * screen that failed to load. */
export function tabTitle(entries: readonly SharedEntry[]): string {
  if (entries.length === 0) return "This project declares no constants.";
  return `${entries.length} constant${entries.length === 1 ? "" : "s"}`;
}

/** Whether the table holds that entry.
 *
 * What decides between the panel and the add form. A route carries the name a finding named, and
 * `unknown-constant` names one no file declares - so the page asks the table it already has rather
 * than a second request that would answer 404 on purpose. It also settles the race where the
 * constant was declared between the analysis and the click. */
export function isDeclared(reply: SharedReply, kind: string, name: string): boolean {
  return reply.entries.some((entry) => entry.kind === kind && entry.name === name);
}

/** A preview's changes as `POST /api/edit` takes them, under the label an undo of it offers.
 *
 * The units tab's own converter, not a second one: a plan is a plan whichever route previewed it,
 * and two of these would drift. */
export function planEdit(plan: PlanReply, label: string): Changes | null {
  return editOfPlan(plan, label);
}
