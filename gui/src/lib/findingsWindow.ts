import type { FindingsQuery } from "../api/client";
import type { FindingCounts, FindingsReply, ListedFinding } from "../api/types";
import { baseName } from "./units";

/** Every row of the Findings table is this tall, in pixels - `ui.css` draws it so - which is what
 * turns a scroll position into a row. Every virtualised table takes its rows' height from here. */
export const ROW_HEIGHT = 33;

/** How many findings one request asks for. */
export const PAGE_SIZE = 100;

/** How many rows beyond the ones in view are drawn on each side: what the keyboard moves into
 * before the window follows it. */
export const MARGIN = 20;

/** How tall the Findings table's box grows before it scrolls, in pixels - `ui.css` draws it so,
 * fifteen rows with the header's: the height the window is reckoned at before the box has said
 * its own. */
export const BOX_HEIGHT = 15 * ROW_HEIGHT;

/** The rows drawn: from `first`, up to but not including `last`. */
export interface Span {
  first: number;
  last: number;
}

/** The rows in view at a scroll position and height, and `MARGIN` on each side, within `total`. */
export function spanOf(scrollTop: number, height: number, total: number): Span {
  const top = Math.floor(Math.max(0, scrollTop) / ROW_HEIGHT);
  const shown = Math.ceil(Math.max(0, height) / ROW_HEIGHT);
  return {
    first: Math.min(total, Math.max(0, top - MARGIN)),
    last: Math.min(total, top + shown + MARGIN),
  };
}

/** The pages of `PAGE_SIZE` findings a span covers, in order: none for a span with no row,
 * wherever it stands - one off a page boundary would otherwise ask for the page it starts in. */
export function pagesOf(span: Span): number[] {
  const pages: number[] = [];
  if (span.first >= span.last) return pages;
  for (let page = Math.floor(span.first / PAGE_SIZE); page * PAGE_SIZE < span.last; page += 1) {
    pages.push(page);
  }
  return pages;
}

/** What one page is asked for as: its `PAGE_SIZE` findings, from the first of them. */
export function pageQuery(page: number): FindingsQuery {
  return { offset: page * PAGE_SIZE, limit: PAGE_SIZE };
}

/** The pages of `revision` that have arrived, by page: `replies` answers `pages`, place for place,
 * with `undefined` for one still on its way. A page is asked for under the revision the page holds
 * and answered by the newest the server has, and the two differ between an analysis landing and
 * the state saying so: a page of another revision is left out, drawn as placeholders until its
 * own revision's arrives, rather than set among this one's, where a finding could be drawn twice
 * or not at all. */
export function arrivedPages(
  pages: readonly number[],
  replies: readonly (FindingsReply | undefined)[],
  revision: number,
): Map<number, FindingsReply> {
  const arrived = new Map<number, FindingsReply>();
  pages.forEach((page, at) => {
    const reply = replies[at];
    if (reply !== undefined && reply.revision === revision) arrived.set(page, reply);
  });
  return arrived;
}

/** A row the window draws: its place, its key, and its finding - `null` until its page arrives,
 * when it is drawn as a placeholder nobody can select. */
export interface WindowRow {
  index: number;
  key: string;
  finding: ListedFinding | null;
  file: string;
}

/** The rows of a span, from the pages that have arrived. */
export function windowRows(span: Span, pages: ReadonlyMap<number, FindingsReply>): WindowRow[] {
  const rows: WindowRow[] = [];
  for (let index = span.first; index < span.last; index += 1) {
    const finding = pages.get(Math.floor(index / PAGE_SIZE))?.findings[index % PAGE_SIZE] ?? null;
    rows.push({
      index,
      key: finding?.key ?? `pending-${index}`,
      finding,
      file: finding === null ? "" : baseName(finding.file),
    });
  }
  return rows;
}

/** The keys of the rows drawn as placeholders: the ones nobody can select. */
export function pendingKeys(rows: readonly WindowRow[]): string[] {
  return rows.filter((row) => row.finding === null).map((row) => row.key);
}

/** Whether a box scrolled to `scrollTop`, `height` high, still draws the row at `index` - a row
 * drawn, which is always within the table it was drawn from, so no total bounds it. Where it does
 * not and that row holds the keyboard's focus, the focus is given up before the window lets the
 * row go: React Aria would otherwise move it to whichever row then stands at the same place, and,
 * while the reader is on the keyboard rather than the pointer, scroll the box back to that one. */
export function keeps(index: number, scrollTop: number, height: number): boolean {
  const span = spanOf(scrollTop, height, Number.POSITIVE_INFINITY);
  return span.first <= index && index < span.last;
}

/** One revision's window: which revision it is, how many findings it has in all and of each
 * severity - what the line above the table counts - the rows the box covers of them, and the pages
 * of those rows that have arrived. */
export interface RevisionWindow {
  revision: number;
  total: number;
  counts: FindingCounts;
  span: Span;
  pages: ReadonlyMap<number, FindingsReply>;
}

/** Whether every page a window's rows fall in has arrived. */
function whole(window: RevisionWindow): boolean {
  return pagesOf(window.span).every((page) => window.pages.has(page));
}

/**
 * Which revision's rows the window draws: the newest's, once every page of its rows has arrived;
 * until then the last one drawn whole, while every page of its rows is still there; and the
 * newest's, placeholders and all, when neither is whole.
 *
 * A revision's pages are asked for under it, and none of another revision is drawn among them
 * (`arrivedPages`): drawing the newest at once, an analysis landing turned every row into a
 * placeholder and back for one round trip, and every row's key changed twice - React Aria then
 * moved the focus to the row standing at its place, and under the keyboard scrolled the box back
 * to it. Kept until the newest is whole and then switched at once, total and counts included - so
 * the line above the table always counts the revision the table draws - a finding that stays keeps
 * its key across the two revisions, and React Aria its focus on it.
 */
export function drawnWindow(newest: RevisionWindow, last: RevisionWindow | null): RevisionWindow {
  if (whole(newest) || last === null || !whole(last)) return newest;
  return last;
}

/** Which revision the window draws through the next analysis landing, and how many findings it
 * has in all and of each severity. */
export interface KeptWindow {
  revision: number;
  total: number;
  counts: FindingCounts;
}

/** The revision to keep drawing through the next analysis landing: the one `drawn` now, once its
 * rows' pages have all arrived; else `kept`, the one kept before - the very same answer where
 * nothing changed, so that the page can tell. */
export function keptAfter(drawn: RevisionWindow, kept: KeptWindow | null): KeptWindow | null {
  if (!whole(drawn) || drawn.revision === kept?.revision) return kept;
  return { revision: drawn.revision, total: drawn.total, counts: drawn.counts };
}

/** How tall, in pixels, the space above the rows drawn and the space below them stand: each row
 * not drawn at `ROW_HEIGHT`, so that the box scrolls as though every row were there. */
export function spacersOf(span: Span, total: number): { above: number; below: number } {
  return { above: span.first * ROW_HEIGHT, below: (total - span.last) * ROW_HEIGHT };
}
