import { Fragment, type MouseEvent } from "react";
import type { SettleReply, VariableReply } from "../api/types";
import { keyColumns, keyRows } from "../lib/variableKeys";
import { also, Cell, Column, LongTable, Row, TableBody, TableHeader } from "../ui/Table";

export interface VariableKeysTableProps {
  variable: VariableReply;
  preview: SettleReply | null;
  /** The key whose chooser is open, or `undefined`. */
  selected: string | undefined;
  /** A row selected, or the selected one let go. `kind` is never selected. */
  onSelect: (key: string | undefined) => void;
  /** Following a cell's `from` to the type that fixes it, without a reload. */
  onOpenType: (name: string) => void;
  /** Following a `dimensions` entry that names a constant, declared or not, to the Shared files
   * tab without a reload - the tab itself decides between the constant's panel and the pre-filled
   * add form (spec 5.3), so this needs to know nothing about which constants the project
   * declares. */
  onOpenConstant: (name: string) => void;
}

/** The panel's table (spec 5.1): a row per key, a column per declaration, drawn from what the
 * api answered. A picture of its props. */
export function VariableKeysTable({
  variable,
  preview,
  selected,
  onSelect,
  onOpenType,
  onOpenConstant,
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
    <LongTable
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
        {(column) => {
          const isKey = column.id === "key";
          // The key column alone is given a width: the table has one column per declaration, so
          // their count grows with however many components declare this variable, and a fixed
          // width could not fit them all - left unset (never `width={undefined}`, which
          // `exactOptionalPropertyTypes` tells apart from unset), each takes the equal share of
          // what the key column leaves that `TableColumnLayout` gives a column without one, down
          // to the 75px floor it gives one with neither a width nor a `minWidth` of its own
          // (react-stately's own TableColumnLayout.mjs; spec §6, task 9 brief).
          return (
            <Column isRowHeader={isKey} {...(isKey ? { width: 140 } : {})}>
              {column.name}
            </Column>
          );
        }}
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
              // `from` and `href` are `null` together (`KeyCell`'s own doc), so narrowing one
              // through a local, rather than `cell.from`/`cell.href` again inside the handler,
              // is what keeps the closure below narrowed too.
              const type = cell.from;
              const href = cell.href;
              return (
                <Cell className={also(cell.quiet ? "quiet" : "")}>
                  {cell.parts === null
                    ? cell.text
                    : cell.parts.map((part, index) => {
                        // `constant` and `href` are `null` together (`DimensionEntry`'s own doc),
                        // narrowed through locals for the same reason `type`/`href` are above.
                        const constant = part.constant;
                        const opens = part.href;
                        return (
                          // The index is the identity here, as `DimensionsField`'s own row is: a
                          // dimension has no name, and two of the same size are two different
                          // dimensions of one shape.
                          // biome-ignore lint/suspicious/noArrayIndexKey: a dimension is its position
                          <Fragment key={index}>
                            {index > 0 && " × "}
                            {constant === null || opens === null ? (
                              part.text
                            ) : (
                              <a
                                className="button link"
                                href={opens}
                                onClick={(event: MouseEvent<HTMLAnchorElement>) => {
                                  const modified =
                                    event.ctrlKey ||
                                    event.metaKey ||
                                    event.shiftKey ||
                                    event.altKey;
                                  if (modified || event.button !== 0) return;
                                  event.preventDefault();
                                  onOpenConstant(constant);
                                }}
                              >
                                {part.text}
                              </a>
                            )}
                          </Fragment>
                        );
                      })}
                  {type !== null && href !== null && (
                    <>
                      {/* Coloured and sized to match the link right after it - `.button.link`'s
                            own rule - so a screen reader announces the type's name alone, not the
                            punctuation introducing it, without moving a single rendered pixel. */}
                      <span className="cell-from">{", from "}</span>
                      <a
                        className="button link"
                        href={href}
                        onClick={(event: MouseEvent<HTMLAnchorElement>) => {
                          // A modified or secondary click asks the browser for a new tab or
                          // window.
                          const modified =
                            event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
                          if (modified || event.button !== 0) return;
                          event.preventDefault();
                          onOpenType(type);
                        }}
                      >
                        {type}
                      </a>
                    </>
                  )}
                  {cell.changing && <span className="tag">will change</span>}
                </Cell>
              );
            }}
          </Row>
        )}
      </TableBody>
    </LongTable>
  );
}
