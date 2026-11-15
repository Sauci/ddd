/** The key a grid's cell is known by to the table, from its row and its column in the row: the
 * table's own keys of cells are made of its columns' ids, which a cell's field has no use for, so
 * the cell is given one of its own. */
export function cellId(row: number, column: number): string {
  return `cell:${row}:${column}`;
}

/** Whether a field taking the focus makes its cell the table's focused cell: only when the table
 * holds none. That is a grid's first entry, which the table would otherwise answer by moving the
 * focus to its first row. When the table holds a cell - a click sets the clicked one itself, and a
 * keyboard entry is given back to the one it remembers, which is how Tab and Shift+Tab leave and
 * enter a table that is one tab stop - the table's own handling stands, and a field taking the
 * cell would take that from it. */
export function takesFocusedCell(held: string | number | null): boolean {
  return held === null;
}
