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
