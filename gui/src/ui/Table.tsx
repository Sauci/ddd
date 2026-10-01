import type { ComponentProps } from "react";
import {
  Cell,
  Column,
  Row,
  Table,
  TableBody,
  TableHeader,
  TableLayout,
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
}

/** Every long table but the Findings one (part 17's task 9, design §6; fix round 1, Minor 3):
 * `Virtualizer` and `TableLayout` around a `Table`, `.long` merged onto React Aria's own class
 * rather than replacing it, `ROW_HEIGHT` for both the row and the heading - the one place this
 * shape is written, rather than eight copies that could each drift apart. A screen gives this
 * what `Table` always took - `aria-label`, the selection props, `children` - and, where it wants
 * one, an extra `className` of its own, merged in beside `.long`. */
export function LongTable({ className, ...props }: LongTableProps) {
  return (
    <Virtualizer
      layout={TableLayout}
      layoutOptions={{ rowHeight: ROW_HEIGHT, headingHeight: ROW_HEIGHT }}
    >
      <Table className={also("long", className)} {...props} />
    </Virtualizer>
  );
}
