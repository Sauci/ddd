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
 * Whether a route names what its page selects in itself, which the page draws in a panel beside
 * its table: a variable of the Graph or of a component's page, a unit, a type, an entry of the
 * shared files, a file - not a variable's values, a page of their own, nor the text of the Findings
 * tab's filter. A change of page to it, the masthead's go-to, a finding's link or an address naming
 * a selection, gives the focus to that panel's heading, the panel being what the reader asked for,
 * and the page's heading meanwhile (16:I13, ruling B11-41); so does the go-to used on the page it
 * opens on (`headingAsked`, ruling B11-44).
 */
export function selectsPanel(route: Route): boolean {
  if (route.page === "start") return false;
  if (route.page === "component") return !("view" in route) && route.variable !== undefined;
  if (route.view === "graph") return route.variable !== undefined;
  if (route.view === "units") return route.unit !== undefined;
  if (route.view === "types") return route.type !== undefined;
  if (route.view === "shared") return "name" in route;
  if (route.view === "files") return route.path !== undefined;
  return false;
}

/**
 * Whether a panel scrolled into view as it opened is scrolled to its top once more as it is drawn
 * again, where the page could not show it whole the first time: the window's scroll is still where
 * that scroll left it (`left`, `now`), the reader having scrolled nowhere since, and the panel's top
 * (`top`, in the window) still stands below the window's own. A panel drawn first while it reads
 * its answer is short, at the page's foot, so that the window cannot scroll it to its top: it then
 * stood with its heading alone at the window's foot, once its keys were drawn (16:M9).
 */
export function showsAgain(left: number, now: number, top: number): boolean {
  return now === left && top > 0;
}

/** What a change of page waits to give the focus to: the page's heading, or the heading of the
 * panel its address opens (`selectsPanel`). */
export type HeadingWanted = "page" | "panel";

/** The route the page shows, and how many followings led there (`useRoute`): a link followed or
 * the masthead's go-to used, Back or Forward - not a selection made in the page, which replaces its
 * address. */
export interface Shown {
  route: Route;
  followings: number;
}

/**
 * Which heading the page asks to take the focus as what it shows moves from `before` to `now`
 * (16:I13, rulings B11-41 and B11-44), `null` where it asks none:
 * - on a change of page (`pageChanged`), the new page's heading, or the heading of the panel its
 *   address opens (`selectsPanel`);
 * - on a following that stays on its page, to an address naming such a panel, that panel's
 *   heading: the masthead's go-to used on the component's page it opens on - the reader asked for
 *   that panel by name, as from another page - or Forward back to it;
 * - none for a selection made in the page, a row or a filter's text, which replaces its address and
 *   leaves the focus on what made it, nor for a following that opens no panel on the page it was
 *   on.
 */
export function headingAsked(before: Shown, now: Shown): HeadingWanted | null {
  const panel = selectsPanel(now.route);
  if (pageChanged(before.route, now.route)) return panel ? "panel" : "page";
  return panel && now.followings !== before.followings ? "panel" : null;
}

/**
 * Which heading takes the focus a change of page asked for (`wanted`), of the headings drawn, and
 * whether the change still waits (16:I13, ruling B11-41): the heading of the panel it opens, once
 * that panel is drawn; else the page's, where it is drawn - holding the focus, where the change
 * opens a panel, until the panel is drawn, and keeping it where none ever is, as on a change of
 * page opening none; else none yet, the change waiting for one to be drawn.
 */
export function headingTaking(
  wanted: HeadingWanted,
  drawn: { page: boolean; panel: boolean },
): { takes: HeadingWanted | null; waits: boolean } {
  if (wanted === "panel" && drawn.panel) return { takes: "panel", waits: false };
  if (drawn.page) return { takes: "page", waits: wanted === "panel" };
  return { takes: null, waits: true };
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

/**
 * Whether a panel opened anew from a control of the page stands out of the reader's view, by its
 * heading (`heading`, its box in the window, `height` high): above the window's top, or past its
 * foot - in a window narrower than 900px the panel stands under the table it was opened from, and a
 * row selected in a window 600px high opened it past the window's foot, nothing showing it had
 * (16:M9). The page then scrolls it into view.
 */
export function outOfView(heading: { top: number; bottom: number }, height: number): boolean {
  return heading.top < 0 || heading.bottom > height;
}

/** What the page finds of a control that lost the focus to nothing, the page's body taking it. */
export interface Fallen {
  /** The page took it away: removed it, disabled it - an Apply or a Put back while its edit is
   * written - or stopped drawing it. Not where the reader moved on: a press elsewhere, the window
   * left. */
  taken: boolean;
  /** It stood in a table still drawn. */
  table: boolean;
  /** Where it stood in a panel: that panel still drawn, another drawn in its place - the same panel
   * drawn anew, a variable's going from its keys to "Updating the findings…" and back - or none left
   * there, the panel closed. */
  panel: "none" | "drawn" | "replaced" | "closed";
}

/** Where a fallen focus goes. */
export type Landing = "none" | "table" | "panel" | "return" | "page";

/**
 * Where the focus goes that a control took with it as the page took the control away (16:I13): to
 * the table it stood in, which gives it to the row nearest the one gone; else to its panel's
 * heading, the panel still drawn or drawn anew - "the panel after Apply" - else back to where the
 * panel was opened from, the panel closed (`returnPlace`); else to the page's heading - after Put
 * back, the Undo control beside it disabled while the files are put back. Nowhere where the reader
 * moved it on.
 */
export function landing(fallen: Fallen): Landing {
  if (!fallen.taken) return "none";
  if (fallen.table) return "table";
  if (fallen.panel === "drawn" || fallen.panel === "replaced") return "panel";
  if (fallen.panel === "closed") return "return";
  return "page";
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
