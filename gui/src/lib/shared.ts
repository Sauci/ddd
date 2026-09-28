import type { Changes, PlanReply, SharedEntry, SharedReply } from "../api/types";
import { planEdit as editOfPlan } from "./projectUnits";

/** The file kinds the Shared files tab's table draws its rows from: a constant's file and a
 * section's, listed together (spec 5.1). `SharedPage` passes this to `lib/findings`'s
 * `unreadable` rather than naming the two kinds itself - `.tsx` is executed by no gate in this
 * repo, so the one fact left saying which vocabularies this tab holds belongs here, where a test
 * can hold it to account, rather than in a screen nothing checks (ruling 7, task 7). Rasters join
 * this list the day their own rows join the table.
 *
 * Not a `for (const kind of SHARED_KINDS)` inside `tabTitle` below, whose own count is read off
 * each entry's `kind` instead: that function tells a reader what is in a table it already has:
 * this one tells `unreadable` which failed *files* are this tab's business before the table is
 * drawn at all, which a project with an entry-less table (every file of a kind failed) could
 * never answer by looking at `entries` alone. */
export const SHARED_KINDS: readonly string[] = ["constants", "sections"];

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
