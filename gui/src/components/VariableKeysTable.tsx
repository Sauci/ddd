import type { SettleReply, VariableReply } from "../api/types";
import { keyColumns, keyRows } from "../lib/variableKeys";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface VariableKeysTableProps {
  variable: VariableReply;
  preview: SettleReply | null;
  /** The key whose chooser is open, or `undefined`. */
  selected: string | undefined;
  /** A row selected, or the selected one let go. `kind` is never selected. */
  onSelect: (key: string | undefined) => void;
}

/** The panel's table (spec 5.1): a row per key, a column per declaration, drawn from what the
 * api answered. A picture of its props. */
export function VariableKeysTable({
  variable,
  preview,
  selected,
  onSelect,
}: VariableKeysTableProps) {
  const rows = keyRows(variable, preview);
  // The producer's column first, as `keyRows` orders every row's cells. The `at` built here is
  // the place in *that* order, which is what `row.cells` is indexed by below - deliberately not
  // the `at` of `keyColumns`, which is where the answer lists the declaration and what each
  // key's `carried` is indexed by. The two are the same number only when the producer already
  // leads the answer; both meanings are right where they are used, and swapping either would
  // quietly draw one component's values under another's name.
  const columns = [
    { id: "key", name: "Key", at: -1 },
    ...keyColumns(variable).map(({ declaration }, at) => ({
      id: `${declaration.path} ${declaration.pointer}`,
      name: declaration.component,
      at,
    })),
  ];
  return (
    <Table
      aria-label={`Keys of ${variable.name}`}
      selectionMode="single"
      selectedKeys={new Set(selected === undefined ? [] : [selected])}
      onSelectionChange={(keys) => {
        const key = keys === "all" ? undefined : [...keys][0];
        const row = rows.find((entry) => entry.key === key);
        // `kind` decides which other keys a declaration may carry at all, so it is shown and
        // never settled (spec 2): selecting it opens nothing and lets the open one go.
        onSelect(row?.settleable === true ? row.key : undefined);
      }}
    >
      <TableHeader columns={columns}>
        {(column) => <Column isRowHeader={column.id === "key"}>{column.name}</Column>}
      </TableHeader>
      <TableBody items={rows}>
        {(row) => (
          <Row id={row.key} columns={columns} className={also(row.disagrees ? "has-error" : "")}>
            {(column) => {
              if (column.at < 0) return <Cell className={also("key")}>{row.key}</Cell>;
              const cell = row.cells[column.at];
              // `columns` beyond the key column and `row.cells` are both built from
              // `keyColumns(variable)`, in that one order, so the two are always the same
              // length; this is only what tells the type checker so under
              // `noUncheckedIndexedAccess`.
              if (cell === undefined) return <Cell />;
              return (
                <Cell className={also(cell.quiet ? "quiet" : "")}>
                  {cell.text}
                  {cell.from !== null && <span className="quiet">, from {cell.from}</span>}
                  {cell.changing && <span className="tag">will change</span>}
                </Cell>
              );
            }}
          </Row>
        )}
      </TableBody>
    </Table>
  );
}

/** React Aria's own class with this table's beside it, since ui.css selects on both: a string
 * would replace React Aria's. */
function also(name: string) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    `${defaultClassName ?? ""} ${name}`.trim();
}
