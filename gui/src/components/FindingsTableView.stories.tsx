import { useState } from "react";
import type { FindingsReply } from "../api/types";
import { BOX_HEIGHT, spacersOf, spanOf, type WindowRow, windowRows } from "../lib/findingsWindow";
import { LONG_FIRST_PAGE, LONG_TOTAL, PROJECT_FINDINGS_PAGE } from "../stories/fixtures";
import { FindingsTableView } from "./FindingsTableView";

export default { title: "Components / FindingsTableView" };

/** The window the Findings tab draws before its box has been scrolled: at the top, one box high,
 * from the pages that have arrived. */
function atTheTop(total: number, pages: ReadonlyMap<number, FindingsReply>) {
  const span = spanOf(0, BOX_HEIGHT, total);
  return { rows: windowRows(span, pages), ...spacersOf(span, total) };
}

/** Nothing moves when a story's box is scrolled: each story is a picture of one window. */
const still = () => {};

const PROJECT = atTheTop(PROJECT_FINDINGS_PAGE.total, new Map([[0, PROJECT_FINDINGS_PAGE]]));

/** Every severity, worst first, grouped by file within a severity. */
export const WorstFirst = () => {
  const [selected, setSelected] = useState<string | undefined>(undefined);
  return (
    <FindingsTableView
      {...PROJECT}
      selected={selected}
      onSelect={(finding) => setSelected(finding?.key)}
      onScroll={still}
    />
  );
};

/** The first row - the worst finding there is - selected, as it is while its panel is open. */
export const Selected = () => {
  const [selected, setSelected] = useState<string | undefined>(PROJECT.rows[0]?.key);
  return (
    <FindingsTableView
      {...PROJECT}
      selected={selected}
      onSelect={(finding) => setSelected(finding?.key)}
      onScroll={still}
    />
  );
};

/** A project with nothing to report: the header alone, no row under it. */
export const NothingToReport = () => {
  const [selected, setSelected] = useState<string | undefined>(undefined);
  return (
    <FindingsTableView
      {...atTheTop(0, new Map())}
      selected={selected}
      onSelect={(finding) => setSelected(finding?.key)}
      onScroll={still}
    />
  );
};

/** The fifth row of the long table as it is drawn before its page arrives. */
const PENDING: WindowRow = { index: 4, key: "pending-4", finding: null, file: "" };

const LONG = atTheTop(LONG_TOTAL, new Map([[0, LONG_FIRST_PAGE]]));

/** A long table: 2,000 findings, the window at the top of its box - its rows of the first page,
 * and the space below standing for every row after them, so the box scrolls as far as the whole
 * table would. One row is a placeholder among the arrived ones - constructed: a page arrives
 * whole, so in use a placeholder stands where a whole page is still to come, and one is drawn
 * here so that a single picture shows both. */
export const ALongTable = () => {
  const [selected, setSelected] = useState<string | undefined>(undefined);
  return (
    <FindingsTableView
      {...LONG}
      rows={LONG.rows.map((row) => (row.index === PENDING.index ? PENDING : row))}
      selected={selected}
      onSelect={(finding) => setSelected(finding?.key)}
      onScroll={still}
    />
  );
};
