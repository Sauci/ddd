/** Whether a key pressed in a grid cell's field is the field's own, and not the table's: a key
 * naming one character - a digit, a sign, a point - with neither Ctrl nor Meta held. These are
 * the keys React Aria's type-to-find takes from a table, looking for a row label that starts with
 * the character and, when it finds one, moving the focus there and swallowing the key: a map's
 * row labels are its axis's breakpoints and a block's its indices, so a digit typed into a cell
 * jumped to a row and never reached the cell. React Aria reads a key as a character when its name
 * is one character long, or does not start with a letter (`private/selection/useTypeSelect`'s own
 * `getStringForKey`), so `Enter`, `ArrowLeft` and `F1` are not; every other key keeps the grid's
 * navigation as before. */
export function keptByCell(event: { key: string; ctrlKey: boolean; metaKey: boolean }): boolean {
  if (event.ctrlKey || event.metaKey) return false;
  return event.key.length === 1 || (event.key !== "" && !/^[A-Z]/i.test(event.key));
}
