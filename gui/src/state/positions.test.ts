import { beforeEach, expect, test } from "vitest";
import { forgetPositions, rememberPosition, savedPositions } from "./positions";

// The gate's Vitest environment is plain node (screens, and the DOM they need, are Playwright's
// job - see vite.config.ts), so `localStorage` is not a global here as it is in a browser: each
// test gets a fresh in-memory stand-in, the way the reader's own browser storage would start
// empty for a project it has never opened.
function fakeStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string): string | null => (data.has(key) ? (data.get(key) as string) : null),
    setItem: (key: string, value: string): void => {
      data.set(key, value);
    },
    removeItem: (key: string): void => {
      data.delete(key);
    },
  };
}

beforeEach(() => {
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: fakeStorage() });
});

test("what was remembered comes back for that project, and not for another project's key", () => {
  rememberPosition("/p/a.ddd.json", "/p/components/one.ddd.json", 10, 20);
  expect(savedPositions("/p/a.ddd.json")).toEqual({
    "/p/components/one.ddd.json": { x: 10, y: 20 },
  });
  expect(savedPositions("/p/b.ddd.json")).toEqual({});
});

test("forgetting clears that project and leaves another's alone", () => {
  rememberPosition("/p/a.ddd.json", "/p/components/one.ddd.json", 10, 20);
  rememberPosition("/p/b.ddd.json", "/p/components/two.ddd.json", 30, 40);
  forgetPositions("/p/a.ddd.json");
  expect(savedPositions("/p/a.ddd.json")).toEqual({});
  expect(savedPositions("/p/b.ddd.json")).toEqual({
    "/p/components/two.ddd.json": { x: 30, y: 40 },
  });
});

test("reading returns {} when storage is empty", () => {
  expect(savedPositions("/p/empty.ddd.json")).toEqual({});
});

test("reading returns {} when storage holds text that is not JSON", () => {
  localStorage.setItem("ddd-gui:positions:/p/garbled.ddd.json", "not json");
  expect(savedPositions("/p/garbled.ddd.json")).toEqual({});
});

test("reading returns {} when storage holds valid json that is not an object", () => {
  localStorage.setItem("ddd-gui:positions:/p/other.ddd.json", "null");
  expect(savedPositions("/p/other.ddd.json")).toEqual({});
});

test("reading returns {} when the accessor throws", () => {
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    get(): never {
      throw new Error("storage refused");
    },
  });
  expect(savedPositions("/p/refused.ddd.json")).toEqual({});
});

test("writing when storage throws does not throw", () => {
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    get(): never {
      throw new Error("storage refused");
    },
  });
  expect(() => rememberPosition("/p/a.ddd.json", "/p/one.ddd.json", 1, 2)).not.toThrow();
});
