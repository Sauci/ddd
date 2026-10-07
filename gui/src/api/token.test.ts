import { describe, expect, test, vi } from "vitest";
import { keeperOver, signedOutStore, TOKEN_KEY } from "./token";

/** A Storage keeping what it is given, as the browser's does. */
function memoryStorage(): Storage {
  const items = new Map<string, string>();
  return {
    get length() {
      return items.size;
    },
    clear: () => items.clear(),
    getItem: (key) => items.get(key) ?? null,
    key: (index) => [...items.keys()][index] ?? null,
    removeItem: (key) => {
      items.delete(key);
    },
    setItem: (key, value) => {
      items.set(key, value);
    },
  };
}

describe("where the token is kept", () => {
  test("in storage, under the page's own key", () => {
    const storage = memoryStorage();
    const kept = keeperOver(() => storage);
    expect(kept.get()).toBeNull();
    kept.set("t");
    expect(storage.getItem(TOKEN_KEY)).toBe("t");
    expect(kept.get()).toBe("t");
    kept.clear();
    expect(storage.getItem(TOKEN_KEY)).toBeNull();
    expect(kept.get()).toBeNull();
  });

  test("in the tab's memory once the browser refuses storage", () => {
    const kept = keeperOver(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(kept.get()).toBeNull();
    kept.set("t");
    expect(kept.get()).toBe("t");
    kept.clear();
    expect(kept.get()).toBeNull();
  });

  test("the key is ddd-gui-token", () => {
    // Pinned by its literal: every other test reads the key from TOKEN_KEY, which would drift
    // along with any change to it.
    expect(TOKEN_KEY).toBe("ddd-gui-token");
  });

  test("a write storage refuses moves the token to memory, and keeps it there", () => {
    const storage = memoryStorage();
    storage.setItem = () => {
      throw new DOMException("full", "QuotaExceededError");
    };
    const kept = keeperOver(() => storage);
    kept.set("t");
    expect(kept.get()).toBe("t");
  });
});

describe("whether the server refused the token", () => {
  test("is false until marked, and tells each listener once", () => {
    const out = signedOutStore();
    const heard = vi.fn();
    const stop = out.subscribe(heard);
    expect(out.current()).toBe(false);
    out.mark();
    out.mark();
    expect(out.current()).toBe(true);
    expect(heard).toHaveBeenCalledTimes(1);
    stop();
  });

  test("a listener that stopped hears nothing", () => {
    const out = signedOutStore();
    const heard = vi.fn();
    out.subscribe(heard)();
    out.mark();
    expect(heard).not.toHaveBeenCalled();
  });
});
