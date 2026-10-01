import type { FindingsQuery } from "../api/client";
import type { FindingsReply, ListedFinding } from "../api/types";
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

/** The pages of `PAGE_SIZE` findings a span covers, in order. */
export function pagesOf(span: Span): number[] {
  const pages: number[] = [];
  for (let page = Math.floor(span.first / PAGE_SIZE); page * PAGE_SIZE < span.last; page += 1) {
    pages.push(page);
  }
  return pages;
}

/** What one page is asked for as: its `PAGE_SIZE` findings, from the first of them. */
export function pageQuery(page: number): FindingsQuery {
  return { offset: page * PAGE_SIZE, limit: PAGE_SIZE };
}

/** The pages that have arrived, by page: `replies` answers `pages`, place for place, with
 * `undefined` for one still on its way. */
export function arrivedPages(
  pages: readonly number[],
  replies: readonly (FindingsReply | undefined)[],
): Map<number, FindingsReply> {
  const arrived = new Map<number, FindingsReply>();
  pages.forEach((page, at) => {
    const reply = replies[at];
    if (reply !== undefined) arrived.set(page, reply);
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

/** How tall, in pixels, the space above the rows drawn and the space below them stand: each row
 * not drawn at `ROW_HEIGHT`, so that the box scrolls as though every row were there. */
export function spacersOf(span: Span, total: number): { above: number; below: number } {
  return { above: span.first * ROW_HEIGHT, below: (total - span.last) * ROW_HEIGHT };
}
