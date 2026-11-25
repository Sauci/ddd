/** The key a grid's cell is known by to the table, from its row and its column in the row: the
 * table's own keys of cells are made of its columns' ids, which a cell's field has no use for, so
 * the cell is given one of its own. */
export function cellId(row: number, column: number): string {
  return `cell:${row}:${column}`;
}

/** Whether a field taking the focus makes its cell the table's focused cell. Where the table holds
 * none, it does: that is a grid's first entry, which the table would otherwise answer by moving the
 * focus to its first row. Where the table holds a cell, it does unless the focus came by Tab
 * (`byTab`): Tab and Shift+Tab enter a table that is one tab stop at the cell it remembers, the
 * table's own handling, which a field taking the cell would take from it. A click sets the clicked
 * cell itself, and an arrow key the cell it moves to, before the field takes the focus, so taking
 * it again changes nothing; and a field focused any other way - a screen reader or voice control
 * moving the focus to the field it names (16:C1) - keeps it, where the table would give it back to
 * the cell it remembered. */
export function takesFocusedCell(held: string | number | null, byTab: boolean): boolean {
  return held === null || !byTab;
}
