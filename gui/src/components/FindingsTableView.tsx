import { useEffect, useRef } from "react";
import type { ListedFinding } from "../api/types";
import { keeps, pendingKeys, type WindowRow } from "../lib/findingsWindow";
import { Chip } from "../ui/Chip";
import { also, Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface FindingsTableViewProps {
  /** The rows the window draws, in order: each a finding, or a placeholder for one whose page has
   * not arrived. */
  rows: readonly WindowRow[];
  /** How tall the space above the rows drawn stands, in pixels: every row before them. */
  above: number;
  /** How tall the space below them stands: every row after them. */
  below: number;
  /** The key of the finding whose panel is open, or `undefined`. */
  selected: string | undefined;
  onSelect: (finding: ListedFinding | undefined) => void;
  /** The box drawn, scrolled, grown or shrunk: where it is scrolled to, and how tall it is. One
   * identity for the life of the table: the box is watched again whenever it changes. */
  onScroll: (scrollTop: number, height: number) => void;
}

/** The Findings tab's table (spec 5.1): a window of the project's findings, worst first - the
 * rows in view and a margin, between two spaces standing for the rows above and below, in a box
 * of its own that the table scrolls in, its header kept at the top. A picture of its props: which
 * rows those are is `lib/findingsWindow`'s to say. */
export function FindingsTableView(props: FindingsTableViewProps) {
  const { rows, selected, onSelect, onScroll } = props;
  const box = useRef<HTMLDivElement>(null);
  // The box's own height, said once it is drawn and again whenever it changes - a short table's
  // box grows with its rows until it is full - which a box that only scrolled would never say.
  useEffect(() => {
    const drawn = box.current;
    if (drawn === null) return;
    const observer = new ResizeObserver(() => onScroll(drawn.scrollTop, drawn.clientHeight));
    observer.observe(drawn);
    return () => observer.disconnect();
  }, [onScroll]);
  return (
    <div
      ref={box}
      className="findings-window"
      // Focusable from here alone: what takes the keyboard's focus off a row the window lets go.
      tabIndex={-1}
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
                  <Chip tone={toneOf(row.finding.severity)}>{row.finding.check}</Chip>
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

/** The chip's tone for a severity; `info` is the quiet one the design system calls neutral. */
function toneOf(severity: ListedFinding["severity"]) {
  return severity === "error" ? "error" : severity === "warning" ? "warning" : "neutral";
}
