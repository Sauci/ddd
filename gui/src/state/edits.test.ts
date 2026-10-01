import { expect, test } from "vitest";
import { OwnEdits, ownEdits } from "./edits";

test("a page has written nothing until it notes an edit", () => {
  expect(new OwnEdits().newest()).toBe(0);
});

test("the newest edit noted is kept, and every listener hears of it", () => {
  const edits = new OwnEdits();
  const heard: string[] = [];
  edits.subscribe(() => heard.push("first"));
  edits.subscribe(() => heard.push("second"));
  edits.wrote(3);
  expect(edits.newest()).toBe(3);
  expect(heard).toEqual(["first", "second"]);
});

test("an edit no newer than one noted before changes nothing, and nobody hears of it", () => {
  // Two answers can arrive out of order: an undo answered after the edit it followed, say, as
  // two windows' replies can. The newest stays the newest.
  const edits = new OwnEdits();
  let heard = 0;
  edits.subscribe(() => {
    heard += 1;
  });
  edits.wrote(5);
  edits.wrote(5);
  edits.wrote(2);
  expect(edits.newest()).toBe(5);
  expect(heard).toBe(1);
});

test("a listener that stopped listening hears nothing more", () => {
  const edits = new OwnEdits();
  let heard = 0;
  const stop = edits.subscribe(() => {
    heard += 1;
  });
  edits.wrote(1);
  stop();
  edits.wrote(2);
  expect(heard).toBe(1);
  expect(edits.newest()).toBe(2);
});

test("each of the three works handed on alone, as useSyncExternalStore and the client take them", () => {
  const edits = new OwnEdits();
  const { wrote, newest, subscribe } = edits;
  let heard = 0;
  subscribe(() => {
    heard += 1;
  });
  wrote(7);
  expect([newest(), heard]).toEqual([7, 1]);
});

test("the page's own is one, and has written nothing when it loads", () => {
  expect(ownEdits).toBeInstanceOf(OwnEdits);
  expect(ownEdits.newest()).toBe(0);
});

test("an undo noted keeps which edit it put back, by the number the undo took", () => {
  const edits = new OwnEdits();
  edits.wrote(3);
  edits.undid(3, 5);
  expect(edits.undone()).toEqual(new Map([[3, 5]]));
  // An undo is an edit of its own: the newest, until another is written.
  expect(edits.newest()).toBe(5);
  edits.wrote(6);
  edits.undid(2, 7);
  expect(edits.undone()).toEqual(
    new Map([
      [3, 5],
      [2, 7],
    ]),
  );
  expect(edits.newest()).toBe(7);
});

test("every listener hears of an undo, even one answered after a newer edit", () => {
  // Answers can arrive out of order: what the undo put back is news all the same.
  const edits = new OwnEdits();
  let heard = 0;
  edits.subscribe(() => {
    heard += 1;
  });
  edits.wrote(9);
  edits.undid(4, 8);
  expect(heard).toBe(2);
  expect(edits.newest()).toBe(9);
  expect(edits.undone()).toEqual(new Map([[4, 8]]));
});

test("what was undone is one answer until another undo is noted, as useSyncExternalStore needs", () => {
  const edits = new OwnEdits();
  const { undone, undid } = edits;
  const first = undone();
  expect(undone()).toBe(first);
  edits.wrote(4);
  expect(undone()).toBe(first);
  undid(4, 5);
  const second = undone();
  expect(second).not.toBe(first);
  expect(undone()).toBe(second);
  // The answer given before is left as it was.
  expect(first).toEqual(new Map());
});

test("the page's own has undone nothing when it loads", () => {
  expect(ownEdits.undone()).toEqual(new Map());
});
