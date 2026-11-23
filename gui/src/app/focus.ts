import { opensAnew, returnPlace } from "../lib/focus";
import { selectedRowFocus } from "../ui/Table";

/**
 * Where the keyboard's focus goes as the page changes under it (16:I13): glue only, finding in
 * the document what `lib/focus.ts` judges.
 *
 * A panel stands in a slot beside the table it was opened from - the `.with-panel` element every
 * page holding a panel draws, or the panel's parent where none does - and the control it was
 * opened from is kept by that slot while panels follow one another there: a key chooser's panel
 * drawn anew as an edit is analysed, the variable a chooser of the canvas names, the variable
 * Add a declaration has just declared. It is let go once no panel is left there.
 */

/** A control the focus can be given to: an element of the page's, or one of the canvas's arrows,
 * which are drawn in SVG. */
type Control = HTMLElement | SVGElement;

/** The panel each slot holds, by its title, and the control the panels there were opened from,
 * `null` where none of the page's. */
const openers = new WeakMap<Element, { title: string; opener: Control | null }>();

/** The element a panel and the table it was opened beside stand in. */
export function slotOf(panel: HTMLElement): HTMLElement | null {
  return panel.closest<HTMLElement>(".with-panel") ?? panel.parentElement;
}

/** The control a press of the pointer went down on, while that press lasts (`watchPresses`). */
let pressed: Control | null = null;

/** The control an event's target stands for: itself, or the element it is a part of that can take
 * the focus - a row's cell for the words in it, an arrow for its line. */
function controlOf(target: EventTarget | null): Control | null {
  if (!(target instanceof Element)) return null;
  const control = target.closest("[tabindex], a[href], button, input, select, textarea");
  return control instanceof HTMLElement || control instanceof SVGElement ? control : null;
}

/** Whether a change of page waits for its heading to take the focus (`askPageHeading`). */
let headingWanted = false;

/**
 * Watches what the reader presses, from the page's start: keeps the control each press of the
 * pointer went down on until the press is over - React Aria selects a row as the pointer goes
 * down, and the page draws the row's panel before the browser gives the focus to the cell pressed -
 * and lets a page's heading go that has not yet taken the focus a change of page asked it to,
 * once the reader presses a key or the pointer meanwhile. Answers what stops the watching.
 */
export function watchReader(): () => void {
  const down = (event: PointerEvent) => {
    pressed = controlOf(event.target);
    headingWanted = false;
  };
  // After the press's own click, which may open a panel too.
  const over = () => {
    setTimeout(() => {
      pressed = null;
    }, 0);
  };
  const key = () => {
    headingWanted = false;
  };
  document.addEventListener("pointerdown", down, true);
  document.addEventListener("pointerup", over, true);
  document.addEventListener("pointercancel", over, true);
  document.addEventListener("keydown", key, true);
  return () => {
    document.removeEventListener("pointerdown", down, true);
    document.removeEventListener("pointerup", over, true);
    document.removeEventListener("pointercancel", over, true);
    document.removeEventListener("keydown", key, true);
  };
}

/** Puts the focus on the page's heading after a change of page (`pageChanged`, 16:I13): at once
 * where the new page draws it, else as it is drawn (`takePageHeading`) - a component's page, its
 * file read - unless the reader presses a key or the pointer meanwhile. */
export function askPageHeading(): void {
  headingWanted = true;
  const heading = pageHeading();
  if (heading !== null) takePageHeading(heading);
}

/** Gives `heading`, a page's heading drawn, the focus a change of page asked for, if it waits. */
export function takePageHeading(heading: HTMLElement): void {
  if (!headingWanted) return;
  headingWanted = false;
  heading.focus();
}

/** The control a panel is opened from as it is first drawn: the one a press of the pointer is on,
 * where the press goes on and the focus is not there yet, else the one holding the focus - where it
 * is one of the page's own: not the body, a heading, the masthead's or a control of another
 * panel, one a panel is drawn in place of keeping the control that one was opened from. */
export function openerNow(): Control | null {
  const active = document.activeElement;
  const control = pressed?.isConnected && !pressed.contains(active) ? pressed : active;
  if (!(control instanceof HTMLElement || control instanceof SVGElement)) return null;
  if (control === document.body || control.matches("[data-heading]")) return null;
  if (control.closest(".panel") !== null) return null;
  return control.closest("main") === null ? null : control;
}

/** Notes a panel titled `title` drawn in its slot, from `opener` - the control holding the focus as
 * it was first drawn - which the slot then returns to where the panel opens anew (`opensAnew`);
 * otherwise the slot keeps the control the panel before was opened from. Answers the slot. */
export function panelDrawn(
  panel: HTMLElement,
  title: string,
  opener: Control | null,
): HTMLElement | null {
  const slot = slotOf(panel);
  if (slot === null) return null;
  const before = openers.get(slot);
  const anew = opensAnew(before?.title ?? null, title, opener !== null);
  openers.set(slot, { title, opener: anew ? opener : (before?.opener ?? null) });
  return slot;
}

/** Notes a panel taken away from `slot`: once none is drawn there - another drawn in its place
 * comes in the same commit - the control the panels there were opened from is let go. */
export function panelGone(slot: HTMLElement | null): void {
  if (slot === null) return;
  queueMicrotask(() => {
    if (slot.querySelector(".panel") === null) openers.delete(slot);
  });
}

/** The page's heading, where it is drawn: the one a change of page, and a panel closing with no
 * other place to go back to, put the focus on. */
function pageHeading(): HTMLElement | null {
  return document.querySelector<HTMLElement>('main [data-heading="page"]');
}

/** Whether `control`, the one `panel` was opened from, is still in the page as that control: out of
 * the panel, and one standing in a table's row only while the table selects that row for the
 * panel - a row drawn again as the table scrolls may be another's. */
function stillThere(control: Control | null, panel: HTMLElement): boolean {
  if (control === null || !control.isConnected || panel.contains(control)) return false;
  const row = control.closest('[role="row"]');
  return row === null || row.getAttribute("aria-selected") === "true";
}

/** The table a panel was opened beside: the one in its slot that is not the panel's own. */
function tableBeside(slot: HTMLElement, panel: HTMLElement): HTMLElement | null {
  for (const grid of slot.querySelectorAll<HTMLElement>('[role="grid"]')) {
    if (!panel.contains(grid)) return grid;
  }
  return null;
}

/**
 * Gives the focus back to where `panel` was opened from (`returnPlace`), as it closes: called
 * before the page lets it go, while its table still selects its row.
 */
export function returnFromPanel(panel: HTMLElement): void {
  const slot = slotOf(panel);
  const opener = slot === null ? null : (openers.get(slot)?.opener ?? null);
  const table = slot === null ? null : tableBeside(slot, panel);
  const toRow = table === null ? null : selectedRowFocus(table);
  const place = returnPlace({
    opener: stillThere(opener, panel),
    row: toRow !== null,
    table: table !== null,
  });
  if (place === "opener") opener?.focus();
  else if (place === "row") toRow?.();
  else if (place === "table") table?.focus();
  else pageHeading()?.focus();
}
