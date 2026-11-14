/** Whether a key pressed in a grid cell's field is the field's own, and not the table's: a key
 * naming one character - a digit, a sign, a point - with neither Ctrl nor Meta held. The table's
 * type-to-find takes such a key (React Aria's `useTypeSelect`, which reads a key as a character
 * when its name is one character long or does not start with a letter) and looks for a row label
 * that starts with it; found, it moves the focus there and swallows the key. A map's row labels are
 * its axis's breakpoints and a block's its indices, so a digit typed into a cell jumped to a row
 * and never reached the cell.
 *
 * The field keeps every such key. That is more than type-to-find takes: it ignores a key with Alt
 * held, and a space when no search is going on, and the field keeps those too, which costs nothing
 * (a character typed with Alt, or AltGr, is one the field should get). Enter, the arrows, Tab and
 * every other key named by a word stay the grid's, as before. */
export function keptByCell(event: { key: string; ctrlKey: boolean; metaKey: boolean }): boolean {
  if (event.ctrlKey || event.metaKey) return false;
  return event.key.length === 1 || (event.key !== "" && !/^[A-Z]/i.test(event.key));
}

/** The key a grid's cell is known by to the table, from its row and its column in the row: the
 * table's own keys of cells are made of its columns' ids, which a cell's field has no use for, so
 * the cell is given one of its own. */
export function cellId(row: number, column: number): string {
  return `cell:${row}:${column}`;
}
