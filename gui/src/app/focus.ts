import {
  type Asked,
  type Fallen,
  type HeadingWanted,
  headingTaking,
  landing,
  letsWaitGo,
  opensAnew,
  outOfView,
  returnPlace,
  showsAgain,
  stillWaits,
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

/** What a change of page waits to give the focus to (`askHeading`, `headingTaking`), and since
 * when the page's heading has held it for the panel the change opens - `null` until it holds it:
 * nothing once given, or once the reader presses a key or the pointer, turns the wheel or touches
 * the page (ruling B11-48), or the focus is moved elsewhere (`letsWaitGo`), or `WAITS_AT_MOST_MS`
 * after the page's heading began holding it (`stillWaits`). Each ask is a want of its own, so that
 * every change of page waits afresh. */
let headingWanted: { heading: HeadingWanted; holding: number | null } | null = null;

/** What a page loaded anew waits to show: the panel its address opens, to be scrolled into view
 * once drawn and its page settled, with no heading taking the focus (`askHeading`,
 * `showWhenSettled`); and since when the project's first analysis has landed (`analysisLanded`),
 * `null` until then. No longer once drawn, or once the reader presses a key or the pointer, turns
 * the wheel or touches the page, or the focus is moved elsewhere (`letsWaitGo`), or
 * `WAITS_AT_MOST_MS` after that landing (`stillWaits`, ruling B11-47): a slow first analysis spends
 * none of that time, what the page then reads of its own does. The panel a change of page opens
 * waits for nothing of its own: it is shown with its heading as that takes the focus
 * (`giveHeading`), and so no later than the page's heading holds the focus for it. */
let showWanted: { since: number | null } | null = null;

/** The slot whose panel was scrolled into view as it opened, and the window's scroll that scroll
 * left, while the panel is still to be shown from its top (`showsAgain`). */
let showing: { slot: HTMLElement; left: number } | null = null;

/** What stops the watch on the panel a change of page opened (`showWhenSettled`), while it runs. */
let settling: (() => void) | null = null;

/** The field that asked (`landing`'s `held`), while the page has it disabled, and what stops the
 * watch for it to be enabled again (`giveBackWhenEnabled`, ruling B11-40): `null` once it has the
 * focus back, once the reader has taken the page meanwhile (`letGo`), or once the page has changed
 * (`askHeading`). */
let asking: { field: Control; stop: () => void } | null = null;

/** Whether the key last pressed is Tab, until the focus moves or the key's own task is over
 * (`watchFocus`). */
let tabbing = false;

/** Whether the focus came by Tab or Shift+Tab, as it last moved (`focusCameByTab`). */
let tabbed = false;

/**
 * Watches the focus from the page's start (16:I13):
 * - keeps the control each press of the pointer went down on until the press is over, for a panel
 *   the press opens to take as the control it was opened from wherever the browser has put the
 *   focus by then - a table's row is selected as the press on it ends (16:M21), the focus on the
 *   cell pressed since the press went down;
 * - lets go of what a change of page asked for and has not had yet, once the reader presses a key
 *   or the pointer, turns the wheel or touches the page meanwhile (ruling B11-48): while the
 *   panel's heading is still to take the focus, that focus and the panel's show, the focus staying
 *   where the reader has it; once it has it, what the watch on the panel shown would still move
 *   (`showWhenSettled`); and all of it once the focus is moved anywhere but onto a heading, a screen
 *   reader's doing or the page's own (`letsWaitGo`, ruling B11-45);
 * - gives a place to the focus the page takes away with a control, never leaving it to the page's
 *   body (`landing`): the browser moves it there, its `focusout` naming nothing it moves to, as a
 *   control is removed, disabled - Apply, Put back, while their edit is written - or no longer drawn;
 *   and gives it back to a field that asked, disabled while its answer comes, once the page enables
 *   it again, unless the reader has taken the page meanwhile (`giveBackWhenEnabled`, ruling B11-40);
 * - notes whether each move of the focus came by Tab (`focusCameByTab`), which a grid's field asks
 *   as it takes the focus (16:C1).
 *
 * Answers what stops the watching.
 */
export function watchFocus(): () => void {
  const down = (event: PointerEvent) => {
    pressed = controlOf(event.target);
    letGo();
  };
  // After the press's own click, which may open a panel too.
  const over = () => {
    setTimeout(() => {
      pressed = null;
    }, 0);
  };
  const key = (event: KeyboardEvent) => {
    letGo();
    tabbing = event.key === "Tab";
    // Tab moves the focus as the key's own default, in the key's own task: a Tab that moves it
    // nowhere on the page - past its last control, to the browser's - is let go with that task.
    if (tabbing) {
      setTimeout(() => {
        tabbing = false;
      }, 0);
    }
  };
  const into = (event: FocusEvent) => {
    tabbed = tabbing;
    tabbing = false;
    // Moved with no key and no pointer - a screen reader taking it on, or the page's own code:
    // where the reader is now, which nothing a change of page left waiting takes back
    // (`letsWaitGo`).
    const to = event.target;
    if (letsWaitGo(to instanceof Element && to.matches("[data-heading]"))) letGo();
  };
  // The wheel turned, or a touch, is the reader taking the page, as a key and the pointer are
  // (ruling B11-48), whether it moves the page or not. Before a change of page's panel has its
  // heading focused, nothing the change asked for is left - its focus nor its show, the focus
  // staying where the reader has it - nor what a page loaded anew waits to show; after, nothing the
  // watch on that panel would still move.
  const taken = () => letGo();
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
  document.addEventListener("wheel", taken, { capture: true, passive: true });
  document.addEventListener("touchstart", taken, { capture: true, passive: true });
  return () => {
    document.removeEventListener("pointerdown", down, true);
    document.removeEventListener("pointerup", over, true);
    document.removeEventListener("pointercancel", over, true);
    document.removeEventListener("keydown", key, true);
    document.removeEventListener("focusin", into, true);
    document.removeEventListener("focusout", out, true);
    document.removeEventListener("wheel", taken, true);
    document.removeEventListener("touchstart", taken, true);
  };
}

/** Whether the focus, as it last moved, came by Tab or Shift+Tab: the first move a press of Tab
 * makes in its own task - the browser's, or React Aria's taking the focus to a grid's last field so
 * that the browser's own move then leaves the grid, a table being one stop for Tab. Asked by a
 * grid's field taking the focus (`takesFocusedCell`, 16:C1). */
export function focusCameByTab(): boolean {
  return tabbed;
}

/** Lets go of all that a change of page or a page loaded anew waits for: the heading to give the
 * focus to, the panel to show, and what the watch on a panel shown would still move
 * (`showWhenSettled`); and of the field that asked, waiting to be given the focus back
 * (`giveBackWhenEnabled`). */
function letGo(): void {
  headingWanted = null;
  showWanted = null;
  settling?.();
  asking?.stop();
}

/** Asks what `headingAsked` answers as the page's route moves on (16:I13, 16:M9): the focus on the
 * page's heading at once where the new page draws it, else as it is drawn (`takePageHeading`) - a
 * component's page, its file read - unless the reader presses a key or the pointer, turns the wheel
 * or touches the page meanwhile; on the heading of the panel the address opens (`panel`,
 * `selectsPanel`) as the panel is drawn (`panelDrawn`), at once where it is drawn already; and that
 * panel, where it is to be `shown`, scrolled into view once its page has settled - on a page loaded
 * anew, with no focus moved. A field that asked on the page before is no longer waited on: it went
 * with its page. */
export function askHeading(asked: Asked): void {
  asking?.stop();
  headingWanted = asked.heading === null ? null : { heading: asked.heading, holding: null };
  showWanted = asked.shown ? { since: null } : null;
  giveHeading(pageHeading(), panelHeading());
}

/** Notes that the project's first analysis has landed (`App`): what a page loaded anew waits to show
 * waits `WAITS_AT_MOST_MS` from now at most (ruling B11-47). Before the landing, no page draws what
 * it shows - only the project's heading, with its tabs on a tab of the project, and a line saying
 * the analysis is on its way - so the time the analysis took is left out of it. What a page reads
 * of its own once the analysis has landed is counted in - a tab's own answer, the Graph's layout, a
 * component's file - the page drawing meanwhile a line saying so, in place of what it shows. */
export function analysisLanded(): void {
  if (showWanted !== null) showWanted.since ??= performance.now();
}

/** Puts the focus on the page's heading, at once where it is drawn, else as it is drawn: where a
 * control the page took away leaves it nowhere else to go (`landing`). */
function askPageHeading(): void {
  headingWanted = { heading: "page", holding: null };
  giveHeading(pageHeading(), panelHeading());
}

/** Gives `heading`, a page's heading drawn, the focus a change of page asked for, if it waits. */
export function takePageHeading(heading: HTMLElement): void {
  giveHeading(heading, panelHeading());
}

/** Gives the focus a change of page asked for, where it waits, to the heading `headingTaking`
 * names of those drawn: the page's (`page`), holding it for a panel no longer than a short time,
 * or the panel's (`panel`); and scrolls the panel drawn into view once the page it stands in has
 * settled (`showWhenSettled`), where it waits to be shown, or where its heading takes the focus.
 * The focus and the view go together (rulings B11-46, B11-48): the page's heading is scrolled to as
 * it takes the focus, and the panel's heading is shown in the very step it takes it in, before any
 * input of the reader's can come between the two. What the page does after that step is the
 * reader's to stop: their key, pointer, wheel or touch ends what the watch would still move. */
function giveHeading(page: HTMLElement | null, panel: HTMLElement | null): void {
  const since = showWanted?.since ?? null;
  if (since !== null && !stillWaits(since, performance.now())) showWanted = null;
  const shows = showWanted !== null;
  let focused = false;
  const wanted = headingWanted;
  const holding = wanted?.holding ?? null;
  if (holding !== null && !stillWaits(holding, performance.now())) {
    headingWanted = null;
  } else if (wanted !== null) {
    const { takes, waits } = headingTaking(wanted.heading, {
      page: page !== null,
      panel: panel !== null,
    });
    if (!waits) headingWanted = null;
    if (takes === "page") {
      page?.focus();
      if (waits) wanted.holding ??= performance.now();
    }
    if (takes === "panel") {
      panel?.focus({ preventScroll: true });
      focused = true;
    }
  }
  if (!(shows || focused) || panel === null) return;
  showWanted = null;
  const shown = panel.closest<HTMLElement>(".panel");
  const slot = shown === null ? null : slotOf(shown);
  if (slot !== null) showWhenSettled(slot, focused);
}

/**
 * Scrolls the panel a change of page opened into view once the page it opened has settled (16:M9):
 * what stands above it - a long table, which sizes its box to its rows only once it has measured
 * itself - is laid out after the panel is first drawn, and pushes it out of view then. Where its
 * heading has just taken the focus (`focused`), the panel is looked at first in that very step
 * (ruling B11-48), once what the step itself lays out has been laid out: a long table drawn with
 * the panel measures itself in a microtask queued as it was drawn, before the panel was, while the
 * reader's input comes in a task or a frame of its own, after the step. Then, watched by the size
 * of the slot it stands in (`slot`), the panel drawn there is scrolled into view as soon as it
 * stands out of it (`scrollShown`); the watch ends then, once no panel is drawn there, or once the
 * reader presses a key or the pointer, turns the wheel or touches the page, or the focus is moved
 * elsewhere (`letsWaitGo`), or a short time after it began (`stillWaits`): the page has settled by
 * then, and what it does next is no longer the change's.
 */
function showWhenSettled(slot: HTMLElement, focused: boolean): void {
  settling?.();
  const since = performance.now();
  const look = () => {
    const panel = slot.querySelector<HTMLElement>(".panel");
    const heading = panel?.querySelector<HTMLElement>('[data-heading="panel"]') ?? null;
    if (panel === null || heading === null || !stillWaits(since, performance.now())) stop();
    else if (outOfView(heading.getBoundingClientRect(), window.innerHeight)) {
      stop();
      scrollShown(panel, heading);
    }
  };
  const watch = new ResizeObserver(look);
  const stop = () => {
    watch.disconnect();
    if (settling === stop) settling = null;
  };
  settling = stop;
  watch.observe(slot);
  if (focused) {
    queueMicrotask(() => {
      if (settling === stop) look();
    });
  }
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
  const waited = headingWanted?.heading === "panel" || showWanted !== null;
  if (waited && panel.closest("main") !== null) giveHeading(null, heading);
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

/** Gives `field`, a field that asked and stands disabled while its answer comes, the focus back once
 * the page enables it again (`landing`'s `held`, ruling B11-40), the page's heading holding the focus
 * meanwhile: watched by its `disabled` attribute, which the page takes off as the answer comes. */
function giveBackWhenEnabled(field: Control): void {
  asking?.stop();
  const watch = new MutationObserver(() => {
    if (field.matches(":disabled")) return;
    stop();
    if (field.isConnected) field.focus();
  });
  const stop = () => {
    watch.disconnect();
    if (asking?.field === field) asking = null;
  };
  asking = { field, stop };
  watch.observe(field, { attributes: true, attributeFilter: ["disabled"] });
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
    // A field marked as one that asks (`data-asks`), disabled while its answer comes.
    asks: from.isConnected && from.matches("[data-asks]:disabled"),
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
  else if (place === "held") {
    askPageHeading();
    giveBackWhenEnabled(from);
  }
}
