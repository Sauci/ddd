import type { Changes, PlanReply, SharedEntry, SharedReply } from "../api/types";
import { planEdit as editOfPlan } from "./projectUnits";

/** The line above the table: one count per vocabulary that has entries, or that the project has
 * nothing shared at all.
 *
 * A project with nothing shared is told so in words rather than shown a table with a zero in it:
 * the tab is where a constant or a section is declared, and an empty table with a count above it
 * reads as a screen that failed to load. Counted by `entry.kind` itself rather than a fixed list
 * of the vocabularies known today: `SharedEntry.kind` is a plain string on the wire for exactly
 * this reason (its own doc: "no generic function had to change when sections joined the tab"), so
 * a third vocabulary's rows count themselves the moment they arrive, with nothing here to change. */
export function tabTitle(entries: readonly SharedEntry[]): string {
  if (entries.length === 0) return "This project declares nothing in its shared files.";
  const counts = new Map<string, number>();
  for (const { kind } of entries) counts.set(kind, (counts.get(kind) ?? 0) + 1);
  return [...counts]
    .map(([kind, count]) => `${count} ${kind}${count === 1 ? "" : "s"}`)
    .join(" · ");
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
