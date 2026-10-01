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
