import { describe, expect, test } from "vitest";
import { opensAnew, returnPlace } from "./focus";

describe("whether a panel drawn takes the control holding the focus as its opener", () => {
  test("the first panel of its slot, drawn from a control of the page", () => {
    expect(opensAnew(null, "ValueA", true)).toBe(true);
  });

  test("another panel, drawn from a control in place of the one before", () => {
    expect(opensAnew("ValueA", "ValueB", true)).toBe(true);
  });

  test("not the same panel drawn again, whatever holds the focus by then", () => {
    expect(opensAnew("ValueA", "ValueA", true)).toBe(false);
  });

  test("not one drawn from no control of the page: the slot keeps the one before's", () => {
    expect(opensAnew("SensorHub to Controller", "ValueB", false)).toBe(false);
    expect(opensAnew(null, "ValueA", false)).toBe(false);
  });
});

describe("where the focus goes back to as a panel closes", () => {
  test("the control the panel was opened from, while it is still in the page", () => {
    expect(returnPlace({ opener: true, row: true, table: true })).toBe("opener");
    expect(returnPlace({ opener: true, row: false, table: false })).toBe("opener");
  });

  test("else the row its table selects for it, where that is drawn", () => {
    expect(returnPlace({ opener: false, row: true, table: true })).toBe("row");
  });

  test("else its table, which gives the focus to the row it remembers", () => {
    expect(returnPlace({ opener: false, row: false, table: true })).toBe("table");
  });

  test("and the page's heading where no table is drawn beside it", () => {
    expect(returnPlace({ opener: false, row: false, table: false })).toBe("heading");
  });
});
