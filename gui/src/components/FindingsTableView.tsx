import { useEffect, useLayoutEffect, useRef } from "react";
import type { ListedFinding } from "../api/types";
import {
  keeps,
  pendingKeys,
  scrolledTo,
  type WalkKey,
  type WindowRow,
  walkTarget,
} from "../lib/findingsWindow";
import { also, Cell, Column, keepsWindow, Row, Table, TableBody, TableHeader } from "../ui/Table";
import { FindingLine } from "./FindingChip";

export interface FindingsTableViewProps {
  /** The rows the window draws, in order: each a finding, or a placeholder for one whose page has
   * not arrived. */
  rows: readonly WindowRow[];
  /** How tall the space above the rows drawn stands, in pixels: every row before them. */
  above: number;
  /** How tall the space below them stands: every row after them. */
  below: number;
  /** How many rows the listing has in all, drawn or not: where Home, End, PageUp and PageDown go
   * (`walkTarget`). */
  total: number;
  /** The key of the finding whose panel is open, or `undefined`. */
  selected: string | undefined;
  onSelect: (finding: ListedFinding | undefined) => void;
  /** The box drawn, scrolled, grown or shrunk: where it is scrolled to, and how tall it is. One
   * identity for the life of the table: the box is watched again whenever it changes. Said once the
   * box stands where the table opens it (`opensAt`), and from then on. */
  onScroll: (scrollTop: number, height: number) => void;
  /** Where the box is scrolled to as the table is drawn: the place the tab opens at (16:M16), once
   * the spaces standing for the listing's rows are known (`opensAt`, lib/findingsWindow.ts), and
   * `null` until then - the box would stop at the foot of what it holds. Read until the box has
   * stood there: the table is drawn anew for each listing asked. */
  opensAt: number | null;
}

const WALKING: readonly string[] = ["Home", "End", "PageUp", "PageDown"];

/** Brings the focus to the row of the listing at `index`: at once where the window draws it, else
 * the box is scrolled to it and the focus goes there once its page has come and it is drawn - the
 * box holding the focus meanwhile, as it does where a scroll lets the focused row go. Given up if
 * the reader moves the focus out of the box in the meantime. */
function walkTo(box: HTMLElement, grid: HTMLElement, index: number): void {
  const drawn = () =>
    grid.querySelector<HTMLElement>(`[role="row"][data-index="${index}"]:not(.pending)`);
  const landed = () => {
    if (!grid.isConnected || document.activeElement !== box) return true;
    const row = drawn();
    if (row === null) return false;
    row.focus();
    return true;
  };
  const there = drawn();
  if (there !== null) {
    there.focus();
    return;
  }
  box.focus({ preventScroll: true });
  box.scrollTop = scrolledTo(index);
  if (landed()) return;
  const watch = new MutationObserver(() => {
    if (landed()) watch.disconnect();
  });
  watch.observe(grid, { childList: true, subtree: true });
}

/** The Findings tab's table (spec 5.1): a window of the project's findings, worst first - the
 * rows in view and a margin, between two spaces standing for the rows above and below, in a box
 * of its own that the table scrolls in, its header kept at the top. A picture of its props: which
 * rows those are is `lib/findingsWindow`'s to say. */
export function FindingsTableView(props: FindingsTableViewProps) {
  const { rows, total, selected, onSelect, onScroll, opensAt } = props;
  const box = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLTableElement>(null);
  // Whether the box has stood where the table opens it (`opensAt`). Until then it says nothing of
  // where it stands: drawn before the listing's size is known, it stands at its top, and saying so
  // would take the place the tab opens at for the top.
  const opened = useRef(false);
  useLayoutEffect(() => {
    const drawn = box.current;
    if (opened.current || opensAt === null || drawn === null) return;
    opened.current = true;
    drawn.scrollTop = opensAt;
    onScroll(drawn.scrollTop, drawn.clientHeight);
  }, [opensAt, onScroll]);
  // Where the window last drew the row it selects: what a panel closing scrolls the window back to,
  // once a scroll has taken the window past that row (`keepsWindow`, 16:I13).
  const selectedAt = useRef<WindowRow | null>(null);
  useLayoutEffect(() => {
    const drawn = rows.find((row) => row.key === selected);
    if (drawn !== undefined) selectedAt.current = drawn;
    if (grid.current === null || box.current === null) return;
    keepsWindow(grid.current, {
      box: box.current,
      selected: () =>
        selected !== undefined && selectedAt.current?.key === selected
          ? { key: selected, index: selectedAt.current.index }
          : null,
      drawnAt: (index) => rows.find((row) => row.index === index)?.finding?.key ?? null,
    });
  });
  // The box's own height, said once it is drawn and again whenever it changes - a short table's
  // box grows with its rows until it is full - which a box that only scrolled would never say.
  useEffect(() => {
    const drawn = box.current;
    if (drawn === null) return;
    const observer = new ResizeObserver(() => {
      if (opened.current) onScroll(drawn.scrollTop, drawn.clientHeight);
    });
    observer.observe(drawn);
    return () => observer.disconnect();
  }, [onScroll]);
  return (
    <div
      ref={box}
      className="findings-window"
      // Focusable from here alone: what takes the keyboard's focus off a row the window lets go.
      tabIndex={-1}
      // Home, End, PageUp and PageDown go by the listing's rows (`walkTarget`): React Aria's own
      // go by the rows its collection holds, which are the rows drawn.
      onKeyDownCapture={(event) => {
        const held = event.target instanceof Element ? event.target.closest("[data-index]") : null;
        if (
          !WALKING.includes(event.key) ||
          event.altKey ||
          event.ctrlKey ||
          event.metaKey ||
          event.shiftKey ||
          !(held instanceof HTMLElement) ||
          grid.current === null ||
          !grid.current.contains(held)
        ) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        const target = walkTarget(
          event.key as WalkKey,
          Number(held.dataset.index),
          total,
          event.currentTarget.clientHeight,
        );
        if (target !== null) walkTo(event.currentTarget, grid.current, target);
      }}
      onScroll={(event) => {
        const scrolled = event.currentTarget;
        // The row the keyboard is on gives the focus up to the box before a scroll takes the
        // window past it (`keeps` says when): React Aria would otherwise move the focus to the
        // row standing at its place - and, while the reader is on the keyboard, scroll the box
        // back to that one.
        const held = document.activeElement?.closest("[data-index]");
        if (
          held instanceof HTMLElement &&
          scrolled.contains(held) &&
          !keeps(Number(held.dataset.index), scrolled.scrollTop, scrolled.clientHeight)
        ) {
          scrolled.focus({ preventScroll: true });
        }
        onScroll(scrolled.scrollTop, scrolled.clientHeight);
      }}
    >
      <div style={{ height: props.above }} />
      <Table
        ref={grid}
        aria-label="Findings"
        selectionMode="single"
        disabledBehavior="selection"
        disabledKeys={pendingKeys(rows)}
        selectedKeys={new Set(selected === undefined ? [] : [selected])}
        onSelectionChange={(keys) => {
          const key = keys === "all" ? undefined : [...keys][0];
          onSelect(rows.find((row) => row.key === key)?.finding ?? undefined);
        }}
      >
        <TableHeader>
          <Column isRowHeader className={also("check")}>
            Check
          </Column>
          <Column className={also("message")}>Message</Column>
          <Column className={also("file")}>File</Column>
        </TableHeader>
        <TableBody items={rows}>
          {(row) =>
            row.finding === null ? (
              <Row id={row.key} data-index={row.index} className={also("pending")}>
                <Cell />
                <Cell className={also("quiet")}>Reading…</Cell>
                <Cell />
              </Row>
            ) : (
              <Row
                id={row.key}
                data-index={row.index}
                className={also(row.finding.severity === "error" ? "has-error" : "")}
              >
                <Cell>
                  <FindingLine severity={row.finding.severity} check={row.finding.check} />
                </Cell>
                <Cell>{row.finding.message}</Cell>
                <Cell className={also("quiet")}>{row.file}</Cell>
              </Row>
            )
          }
        </TableBody>
      </Table>
      <div style={{ height: props.below }} />
    </div>
  );
}
