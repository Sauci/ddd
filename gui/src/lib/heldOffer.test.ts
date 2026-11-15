import { describe, expect, test } from "vitest";
import { marginBelow, scrollFromUnder } from "./heldOffer";

/** The offer held at the foot of an 800px window, 84px tall. */
const OFFER = { top: 716, bottom: 800 };

describe("scrollFromUnder", () => {
  test("a field the offer covers is scrolled above it, with room to spare", () => {
    // The field typed into at the window's foot: 34px tall, its foot 10px above the window's.
    expect(scrollFromUnder({ top: 756, bottom: 790 }, OFFER)).toBe(82);
  });

  test("so is one the offer's top cuts through", () => {
    expect(scrollFromUnder({ top: 700, bottom: 734 }, OFFER)).toBe(26);
  });

  test("a field clear of the offer stays where it is, even touching it", () => {
    expect(scrollFromUnder({ top: 300, bottom: 334 }, OFFER)).toBe(0);
    expect(scrollFromUnder({ top: 682, bottom: 716 }, OFFER)).toBe(0);
  });

  test("a field below the window, where the reader scrolled away from it, is left there", () => {
    expect(scrollFromUnder({ top: 800, bottom: 834 }, OFFER)).toBe(0);
    expect(scrollFromUnder({ top: 1200, bottom: 1234 }, OFFER)).toBe(0);
  });
});

describe("marginBelow", () => {
  test("a cell keeps the offer's height clear below it, and the room to spare", () => {
    // The table scrolls a cell the keys moved the focus to into view at the window's foot: kept
    // this far off it, the cell stops above the offer, with the gap `scrollFromUnder` leaves.
    expect(marginBelow(OFFER)).toBe("92px");
  });

  test("and none while no offer is drawn", () => {
    expect(marginBelow(null)).toBe("0px");
  });
});
