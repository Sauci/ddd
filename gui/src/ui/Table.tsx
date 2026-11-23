import { type ComponentProps, useLayoutEffect, useRef } from "react";
import {
  Cell,
  Column,
  type Key,
  Rect,
  Row,
  Table,
  TableBody,
  TableHeader,
  TableLayout,
  type TableRenderProps,
  Virtualizer,
} from "react-aria-components";
import { ROW_HEIGHT } from "../lib/findingsWindow";

// React Aria's table, row selection and keyboard navigation included, under the page's own
// styles in ui.css: the one place a screen takes its table from. `Virtualizer` and `TableLayout`
// are React Aria's own too (part 17's task 9): wrapped around a table, they draw only the rows in
// view, which is how every long table but the Findings one is drawn - that one keeps its own
// hand-made window (lib/findingsWindow.ts, part 17's task 7). `LongTable` below is the one place
// that wrapping is written (fix round 1, Minor 3): every long table drew it by hand before, eight
// times over.
export { Cell, Column, Row, Table, TableBody, TableHeader };

/** React Aria's own class, with one or more of a table's own beside it, since ui.css selects on
 * both: a string on its own would replace React Aria's rather than join it. Every long table once
 * wrote this itself; `LongTable` below is now the only one that still needs to (fix round 1,
 * Minor 3) - a screen that wants a class on a `Row`, `Cell` or `Column` still calls this directly,
 * since those vary by row or cell in a way `LongTable` itself cannot know. */
export function also(...names: (string | undefined)[]) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    [defaultClassName, ...names].filter((name) => name).join(" ");
}

export interface LongTableProps extends ComponentProps<typeof Table> {
  /** An extra class beside `.long`, for a table that wants its own look on top of it - the unit
   * panel's own places table reuses `.panel-declarations` this way (fix round 1, Minor 5), rather
   * than a rule of its own repeating what that class already says. */
  className?: string;
  /** Whether a widened filter is still putting its rows back (`rowsToCome`, lib/filter.ts): a panel
   * closing gives the focus back to its row once they are all back (`selectedRowFocus`). */
  rowsToCome?: boolean;
}

/** What a long table bears while a widened filter puts its rows back (`rowsToCome`,
 * lib/filter.ts). */
const ROWS_TO_COME = "data-rows-to-come";

/**
 * React Aria's own layout of a long table, keeping the row the table's focus is on drawn where it
 * now stands (16:I14). React Aria draws that row wherever it is, out of view too, at its place
 * among the rows it last laid out - and it lays out the rows of the box's view and those it has
 * shown, no further. A widened filter puts rows back before the focused row and moves it on, past
 * every row laid out: React Aria then drew the row standing at the focused one's old place
 * instead, in the focused row's own element, so that the row shown focused, and named to a screen
 * reader, was that other one, and Tab back into the table went to it, while the row the arrow keys
 * go on from was drawn nowhere. Where the focused row is not among the rows just laid out, every
 * row is laid out here, as React Aria lays them out for a row it never laid out, the one End goes
 * to: its own test for that one compares the area laid out with the table's, which the box's view,
 * wider than the table, fills before the rows below it are reached.
 */
class FocusedRowLayout<T> extends TableLayout<T> {
  override update(context: Parameters<TableLayout<T>["update"]>[0]): void {
    super.update(context);
    for (const key of this.virtualizer?.persistedKeys ?? []) {
      if (this.collection.getItem(key) !== null && !this.laidOut(key)) {
        this.requestedRect = new Rect(0, 0, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY);
        this.rootNodes = this.buildCollection();
        this.requestedRect = new Rect(0, 0, this.contentSize.width, this.contentSize.height);
        return;
      }
    }
  }

  /** Whether `key` is among the rows, or the cells, this layout last laid out: itself, and each
   * part of the table holding it, at its own place among the parts laid out in the part above. */
  private laidOut(key: Key): boolean {
    for (let node = this.layoutNodes.get(key); node !== undefined; ) {
      const above = node.layoutInfo.parentKey;
      if (above === null) return this.rootNodes.includes(node);
      const parent = this.layoutNodes.get(above);
      if (node.index === undefined || parent?.children?.[node.index] !== node) return false;
      node = parent;
    }
    return false;
  }
}

/** What holds each long table's state, by the grid it draws: what gives the focus to a row it holds
 * but does not draw (`selectedRowFocus`). The holder, not the state: React Aria draws its table
 * anew as its collection changes, without the long table being drawn again. */
const states = new WeakMap<Element, { readonly current: TableRenderProps["state"] | null }>();

/** Every long table but the Findings one (part 17's task 9, design §6; fix round 1, Minor 3):
 * `Virtualizer` and `TableLayout` around a `Table`, `.long` merged onto React Aria's own class
 * rather than replacing it, `ROW_HEIGHT` for both the row and the heading - the one place this
 * shape is written, rather than eight copies that could each drift apart. A screen gives this
 * what `Table` always took - `aria-label`, the selection props, `children` - and, where it wants
 * one, an extra `className` of its own, merged in beside `.long`. Its state, which React Aria hands
 * the class's render props, is kept by its grid (16:I13); its layout keeps the row its focus is on
 * drawn where it stands (`FocusedRowLayout`, 16:I14). */
export function LongTable({ className, rowsToCome = false, ...props }: LongTableProps) {
  const grid = useRef<HTMLTableElement | HTMLDivElement>(null);
  const state = useRef<TableRenderProps["state"] | null>(null);
  useLayoutEffect(() => {
    if (grid.current !== null) states.set(grid.current, state);
  });
  return (
    <Virtualizer
      layout={FocusedRowLayout}
      layoutOptions={{ rowHeight: ROW_HEIGHT, headingHeight: ROW_HEIGHT }}
    >
      <Table
        {...props}
        {...{ [ROWS_TO_COME]: rowsToCome ? "" : undefined }}
        ref={grid}
        className={(values) => {
          state.current = values.state;
          return also("long", className)(values);
        }}
      />
    </Virtualizer>
  );
}

/**
 * What gives the focus to the row `grid` selects, or `null` where it can give it none (16:I13): a
 * long table gives it to the row it holds, drawn or out of view - React Aria draws its focused row
 * and, from the keyboard, scrolls it into view - and none to a row its filter leaves out; any other
 * table to the row it draws.
 *
 * While a long table's rows come back (`ROWS_TO_COME`), the table takes the focus at once and the
 * row once they are all back, unless the reader moved it out of the table meanwhile: rows put back
 * before the one holding the focus move its place, and React Aria then draws another row where it
 * stood, the focus on that one.
 */
export function selectedRowFocus(grid: HTMLElement): (() => void) | null {
  const state = states.get(grid)?.current;
  if (state === undefined || state === null) {
    const row = grid.querySelector<HTMLElement>('[role="row"][aria-selected="true"]');
    return row === null ? null : () => row.focus();
  }
  const [key] = state.selectionManager.selectedKeys;
  const coming = grid.hasAttribute(ROWS_TO_COME);
  if (key === undefined || !(coming || state.collection.getItem(key))) return null;
  return () => {
    grid.focus();
    if (!coming) {
      state.selectionManager.setFocusedKey(key);
      return;
    }
    const watch = new MutationObserver(() => {
      if (grid.hasAttribute(ROWS_TO_COME)) return;
      watch.disconnect();
      if (grid.contains(document.activeElement)) {
        states.get(grid)?.current?.selectionManager.setFocusedKey(key);
      }
    });
    watch.observe(grid, { attributes: true, attributeFilter: [ROWS_TO_COME] });
  };
}
