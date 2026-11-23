import {
  type Fallen,
  type HeadingWanted,
  headingTaking,
  landing,
  opensAnew,
  outOfView,
  returnPlace,
  showsAgain,
} from "../lib/focus";
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

/** The control a press of the pointer went down on, while that press lasts (`watchFocus`). */
let pressed: Control | null = null;

/** The control an event's target stands for: itself, or the element it is a part of that can take
 * the focus - a row's cell for the words in it, an arrow for its line. */
function controlOf(target: EventTarget | null): Control | null {
  if (!(target instanceof Element)) return null;
  const control = target.closest("[tabindex], a[href], button, input, select, textarea");
  return control instanceof HTMLElement || control instanceof SVGElement ? control : null;
}

/** What a change of page waits to give the focus to (`askPageHeading`, `headingTaking`): nothing
 * once given, or once the reader presses a key or the pointer. */
let headingWanted: HeadingWanted | null = null;

/** The slot whose panel was scrolled into view as it opened, and the window's scroll that scroll
 * left, while the panel is still to be shown from its top (`showsAgain`). */
let showing: { slot: HTMLElement; left: number } | null = null;

/** What stops the watch on the panel a change of page opened (`showWhenSettled`), while it runs. */
let settling: (() => void) | null = null;

/** Whether the key last pressed is Tab, until the focus moves or the key's own task is over
 * (`watchFocus`). */
let tabbing = false;

/** Whether the focus came by Tab or Shift+Tab, as it last moved (`focusCameByTab`). */
let tabbed = false;

/**
 * Watches the focus from the page's start (16:I13):
 * - keeps the control each press of the pointer went down on until the press is over - React Aria
 *   selects a row as the pointer goes down, and the page draws the row's panel before the browser
 *   gives the focus to the cell pressed;
 * - lets a page's heading go that has not yet taken the focus a change of page asked it to, once
 *   the reader presses a key or the pointer meanwhile, and the panel the change opened that is not
 *   yet scrolled into view (`showWhenSettled`), once the reader scrolls by a wheel or a touch too;
 * - gives a place to the focus the page takes away with a control, never leaving it to the page's
 *   body (`landing`): the browser moves it there, its `focusout` naming nothing it moves to, as a
 *   control is removed, disabled - Apply, Put back, while their edit is written - or no longer drawn;
 * - notes whether each move of the focus came by Tab (`focusCameByTab`), which a grid's field asks
 *   as it takes the focus (16:C1).
 *
 * Answers what stops the watching.
 */
export function watchFocus(): () => void {
  const down = (event: PointerEvent) => {
    pressed = controlOf(event.target);
    headingWanted = null;
    settling?.();
  };
  // After the press's own click, which may open a panel too.
  const over = () => {
    setTimeout(() => {
      pressed = null;
    }, 0);
  };
  const key = (event: KeyboardEvent) => {
    headingWanted = null;
    settling?.();
    tabbing = event.key === "Tab";
    // Tab moves the focus as the key's own default, in the key's own task: a Tab that moves it
    // nowhere on the page - past its last control, to the browser's - is let go with that task.
    if (tabbing) {
      setTimeout(() => {
        tabbing = false;
      }, 0);
    }
  };
  const into = () => {
    tabbed = tabbing;
    tabbing = false;
  };
  // A wheel or a touch scrolls the page as the reader would have it: the panel a change of page
  // opened is no longer to be scrolled to.
  const scrolled = () => settling?.();
  const out = (event: FocusEvent) => {
    const from = event.target;
    if (event.relatedTarget !== null) return;
    if (!(from instanceof HTMLElement || from instanceof SVGElement)) return;
    const panel = from.closest<HTMLElement>(".panel");
    const slot = panel === null ? null : slotOf(panel);
    const opener = slot === null ? null : (openers.get(slot)?.opener ?? null);
    const grid = from.closest<HTMLElement>('[role="grid"]');
    queueMicrotask(() => landFrom(from, panel, slot, opener, grid));
  };
  document.addEventListener("pointerdown", down, true);
  document.addEventListener("pointerup", over, true);
  document.addEventListener("pointercancel", over, true);
  document.addEventListener("keydown", key, true);
  document.addEventListener("focusin", into, true);
  document.addEventListener("focusout", out, true);
  document.addEventListener("wheel", scrolled, { capture: true, passive: true });
  document.addEventListener("touchstart", scrolled, { capture: true, passive: true });
  return () => {
    document.removeEventListener("pointerdown", down, true);
    document.removeEventListener("pointerup", over, true);
    document.removeEventListener("pointercancel", over, true);
    document.removeEventListener("keydown", key, true);
    document.removeEventListener("focusin", into, true);
    document.removeEventListener("focusout", out, true);
    document.removeEventListener("wheel", scrolled, true);
    document.removeEventListener("touchstart", scrolled, true);
  };
}

/** Whether the focus, as it last moved, came by Tab or Shift+Tab: the first move a press of Tab
 * makes in its own task - the browser's, or React Aria's taking the focus to a grid's last field so
 * that the browser's own move then leaves the grid, a table being one stop for Tab. Asked by a
 * grid's field taking the focus (`takesFocusedCell`, 16:C1). */
export function focusCameByTab(): boolean {
  return tabbed;
}

/** Puts the focus on the page's heading after a change of page (`pageChanged`, 16:I13): at once
 * where the new page draws it, else as it is drawn (`takePageHeading`) - a component's page, its
 * file read - unless the reader presses a key or the pointer meanwhile. Where the change of page
 * opens a panel (`panel`, `selectsPanel`), the focus goes on to that panel's heading as the panel
 * is drawn (`panelDrawn`), at once where it is drawn already. */
export function askPageHeading(panel = false): void {
  headingWanted = panel ? "panel" : "page";
  giveHeading(pageHeading(), panelHeading());
}

/** Gives `heading`, a page's heading drawn, the focus a change of page asked for, if it waits. */
export function takePageHeading(heading: HTMLElement): void {
  giveHeading(heading, panelHeading());
}

/** Gives the focus a change of page asked for, where it waits, to the heading `headingTaking`
 * names of those drawn: the page's (`page`), or the panel's (`panel`), the panel then scrolled into
 * view once the page it stands in has settled (`showWhenSettled`). */
function giveHeading(page: HTMLElement | null, panel: HTMLElement | null): void {
  if (headingWanted === null) return;
  const { takes, waits } = headingTaking(headingWanted, {
    page: page !== null,
    panel: panel !== null,
  });
  if (!waits) headingWanted = null;
  if (takes === "page") page?.focus();
  if (takes !== "panel" || panel === null) return;
  panel.focus({ preventScroll: true });
  const shown = panel.closest<HTMLElement>(".panel");
  const slot = shown === null ? null : slotOf(shown);
  if (slot !== null) showWhenSettled(slot);
}

/**
 * Scrolls the panel a change of page opened into view once the page it opened has settled (16:M9):
 * what stands above it - a long table, which sizes its box to its rows only once it has measured
 * itself - is laid out after the panel is first drawn, and pushes it out of view then. Watched by
 * the size of the slot it stands in (`slot`), the panel drawn there is scrolled into view as soon as
 * it stands out of it (`scrollShown`); the watch ends then, once no panel is drawn there, or once
 * the reader presses a key or the pointer, or scrolls the page by a wheel or a touch.
 */
function showWhenSettled(slot: HTMLElement): void {
  settling?.();
  const watch = new ResizeObserver(() => {
    const panel = slot.querySelector<HTMLElement>(".panel");
    const heading = panel?.querySelector<HTMLElement>('[data-heading="panel"]') ?? null;
    if (panel === null || heading === null) stop();
    else if (outOfView(heading.getBoundingClientRect(), window.innerHeight)) {
      stop();
      scrollShown(panel, heading);
    }
  });
  const stop = () => {
    watch.disconnect();
    if (settling === stop) settling = null;
  };
  settling = stop;
  watch.observe(slot);
}

/** Scrolls `panel`, opened anew, into view where its heading stands out of it (`outOfView`,
 * 16:M9): to its top, so that the window shows the panel rather than its heading alone at the
 * window's foot - and, where the page cannot scroll it that far yet, once more as it is drawn again
 * (`showsAgain`). */
function scrollShown(panel: HTMLElement, heading: HTMLElement): void {
  showing = null;
  if (!outOfView(heading.getBoundingClientRect(), window.innerHeight)) return;
  panel.scrollIntoView({ block: "start" });
  const slot = slotOf(panel);
  showing = slot === null ? null : { slot, left: window.scrollY };
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
 * otherwise the slot keeps the control the panel before was opened from. A panel opened anew
 * standing out of view is scrolled into it (`scrollShown`, 16:M9); one a change of page opens takes
 * the focus that change asked for (`askPageHeading`). Answers the slot. */
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
  const heading = panel.querySelector<HTMLElement>('[data-heading="panel"]');
  if (heading === null) return slot;
  if (headingWanted === "panel" && panel.closest("main") !== null) giveHeading(null, heading);
  else if (anew) scrollShown(panel, heading);
  else if (showing?.slot === slot) {
    if (showsAgain(showing.left, window.scrollY, panel.getBoundingClientRect().top)) {
      panel.scrollIntoView({ block: "start" });
      showing = { slot, left: window.scrollY };
    } else showing = null;
  }
  return slot;
}

/** Notes a panel taken away from `slot`: once none is drawn there - another drawn in its place
 * comes in the same commit - the control the panels there were opened from is let go, and the
 * scroll that was showing it. */
export function panelGone(slot: HTMLElement | null): void {
  if (slot === null) return;
  queueMicrotask(() => {
    if (slot.querySelector(".panel") !== null) return;
    openers.delete(slot);
    if (showing?.slot === slot) showing = null;
  });
}

/** The page's heading, where it is drawn: the one a change of page, and a panel closing with no
 * other place to go back to, put the focus on. */
function pageHeading(): HTMLElement | null {
  return document.querySelector<HTMLElement>('main [data-heading="page"]');
}

/** The heading of the panel the page draws, where it draws one: the one a change of page opening
 * that panel puts the focus on. */
function panelHeading(): HTMLElement | null {
  return document.querySelector<HTMLElement>('main .panel [data-heading="panel"]');
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

/** Gives the focus back to where `panel`, standing in `slot`, was opened from (`returnPlace`):
 * `opener`, the control the slot kept, else the row its table selects, else the table, else the
 * page's heading. */
function returnTo(slot: HTMLElement | null, panel: HTMLElement, opener: Control | null): void {
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

/**
 * Gives the focus back to where `panel` was opened from, as Close is pressed in it: called before
 * the page lets it go, while its table still selects its row.
 */
export function returnFromPanel(panel: HTMLElement): void {
  const slot = slotOf(panel);
  returnTo(slot, panel, slot === null ? null : (openers.get(slot)?.opener ?? null));
}

/** What became of `panel`, a control's: none, still drawn, drawn anew as `replaced`, or closed. */
function panelAfter(panel: HTMLElement | null, replaced: HTMLElement | null): Fallen["panel"] {
  if (panel === null) return "none";
  if (panel.isConnected) return "drawn";
  return replaced === null ? "closed" : "replaced";
}

/** Whether the page took `control` away: removed it, disabled it, or stopped drawing it. */
function takenAway(control: Control): boolean {
  return (
    !control.isConnected || control.matches(":disabled") || control.getClientRects().length === 0
  );
}

/**
 * Where the focus goes that `from` took with it to the page's body (`landing`), found once the
 * page has drawn what replaces it: `panel`, `slot`, `opener` and `grid` are what `from` stood in,
 * read as it lost the focus, while it was still in the page.
 */
function landFrom(
  from: Control,
  panel: HTMLElement | null,
  slot: HTMLElement | null,
  opener: Control | null,
  grid: HTMLElement | null,
): void {
  const active = document.activeElement;
  if (active !== null && active !== document.body) return;
  const replaced = slot?.isConnected ? slot.querySelector<HTMLElement>(".panel") : null;
  const place = landing({
    taken: takenAway(from),
    table: grid?.isConnected ?? false,
    panel: panelAfter(panel, replaced),
  });
  if (place === "table") grid?.focus();
  else if (place === "panel") {
    // A panel drawn anew stands where the one before it stood: its heading takes the focus where
    // the page stands, scrolled by the reader meanwhile or not.
    const standing = panel?.isConnected ? panel : replaced;
    const heading = standing?.querySelector<HTMLElement>('[data-heading="panel"]');
    heading?.focus({ preventScroll: standing !== panel });
  } else if (place === "return" && panel !== null) returnTo(slot, panel, opener);
  else if (place === "page") askPageHeading();
}
