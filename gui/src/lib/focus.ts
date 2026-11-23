import type { Route } from "./route";

/**
 * Where the keyboard's focus goes as the page changes under it (16:I13, decision 16.3): what the
 * page finds there is gathered by `app/focus.ts`, out of the document, and judged here.
 */

/** The page a route shows, as a change of page reads it: the start page, a tab of the project
 * screen, a component's page or a variable's values - not what the page selects, a row or a
 * filter's text, which replaces its address on the same page. */
export function pageOf(route: Route): string {
  if (route.page === "start") return JSON.stringify(["start"]);
  if (route.page === "project") return JSON.stringify(["project", route.view]);
  return "view" in route
    ? JSON.stringify(["values", route.file, route.variable])
    : JSON.stringify(["component", route.file]);
}

/** Whether going from `before` to `after` changes the page (`pageOf`): the focus then goes to the
 * new page's heading, as it starts at a page's top once a link loads it, where the control that
 * held it - a row, a link of a panel - is gone, or stands for another page than the one shown. */
export function pageChanged(before: Route, after: Route): boolean {
  return pageOf(before) !== pageOf(after);
}

/**
 * Whether a panel drawn takes the control holding the focus as the one it was opened from (16:I13):
 * where it was drawn from a control of the page's (`fromControl`), and is not the panel drawn
 * before it in its slot (`before`, that panel's title, `null` where none was) drawn again - a
 * variable's panel goes from "Reading…" to its keys, or to "Updating the findings…" and back, while
 * the reader types in a filter, and is the panel it was all along. Otherwise the slot keeps the
 * control the panel before was opened from: one drawn in place of a chooser's, or of Add a
 * declaration's, was opened from what those were.
 */
export function opensAnew(before: string | null, title: string, fromControl: boolean): boolean {
  return fromControl && before !== title;
}

/** What the page finds, as a panel closes, of the places its focus can go back to. */
export interface Found {
  /** The control the panel was opened from is still in the page, as that same control: one that
   * stands in a table's row stands in the row the table selects for the panel, a row drawn again
   * being another's where it is not. */
  opener: boolean;
  /** The row the panel's table selects for it can take the focus: one the table draws, one a long
   * table holds out of view, which it draws as it gives it the focus, or one a long table may hold
   * once a widened filter has put its rows back, which it then gives the focus. */
  row: boolean;
  /** The table the panel was opened beside is drawn. */
  table: boolean;
}

/** Where the focus goes back to as a panel closes. */
export type ReturnPlace = "opener" | "row" | "table" | "heading";

/**
 * Where the focus goes back to as a panel closes (16:I13, ruling B11-14): to the control it was
 * opened from - the unit cell's button, a row, a link of the page, Add a declaration, an arrow of
 * the canvas - while that is still in the page. Otherwise to the row its table selects for it,
 * where the table can give it the focus: a filter took the opener's row away and put it back, or
 * the panel was opened by its address. Otherwise - the filter leaves the panel's row out, or a
 * window of rows left it undrawn - to its table, which gives the focus to the row it remembers,
 * the nearest to the one gone, or its first. And where no table is drawn beside the panel - a
 * filter leaving none of its rows, or a page with none, the Graph's - to the page's heading.
 */
export function returnPlace(found: Found): ReturnPlace {
  if (found.opener) return "opener";
  if (found.row) return "row";
  if (found.table) return "table";
  return "heading";
}
