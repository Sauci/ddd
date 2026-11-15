/** The room left between a field and the offer held below it, in pixels: the space the page puts
 * between the lines of a panel (`--space-2`). */
const GAP = 8;

/** A box as the window places it: its top and its foot, in pixels from the window's top. */
interface Placed {
  top: number;
  bottom: number;
}

/**
 * How far the page scrolls so that the field typed into stands above the values grid's offer, held
 * at the window's foot (`.values-offer`): the length of the field under the offer's top, and the
 * gap. The offer is drawn once a plan has come for what was typed, over whatever lies at the
 * window's foot - the very field typed into, where it was near the foot - and would hide what is
 * being typed. Nothing for a field clear of it, and nothing for one wholly below the window either:
 * the reader scrolled away from that one, and is not scrolled back to it.
 */
export function scrollFromUnder(field: Placed, offer: Placed): number {
  if (field.bottom <= offer.top || field.top >= offer.bottom) return 0;
  return field.bottom - offer.top + GAP;
}

/**
 * How far a cell of the values grid keeps the window's foot off while the offer is held there, as
 * its `scroll-margin-bottom` spells it: the offer's height and the gap. The table scrolls a cell
 * the keys moved the focus to into view only after its field has taken the focus - Ctrl+End to the
 * last cell of a grid taller than the window, which `scrollFromUnder` then found below the window
 * and left there - and stops this far short of the window's foot, above the offer, where it stopped
 * at the foot, under it. Nothing else scrolls by it: the offer's own buttons are no cells, and a
 * scroll the reader makes scrolls nothing into view. None while no offer is drawn.
 */
export function marginBelow(offer: Placed | null): string {
  return offer === null ? "0px" : `${offer.bottom - offer.top + GAP}px`;
}
