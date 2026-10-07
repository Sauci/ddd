/** Where the page keeps the token `ddd gui` traded for its address, and whether the server has
 * since refused it.
 *
 * Kept in `localStorage` for the page's own origin, `http://127.0.0.1:<port>`, port included: no
 * server on another port of 127.0.0.1 is sent it, or can read it. A cookie, which `ddd gui`
 * signed a page in with before, is sent to every port of the address (part 18b's spec, §1). */

/** The key the token is kept under. The origin, port and all, keeps two servers' tokens apart. */
export const TOKEN_KEY = "ddd-gui-token";

export interface Keeper {
  get(): string | null;
  set(token: string): void;
  clear(): void;
}

/** A keeper over `storage()`, which moves to the tab's own memory the first time storage
 * throws: in a private window, under a policy, or with its quota full. The tab then stays
 * signed in until it reloads or closes, since a token kept only in memory does not outlive the
 * page. */
export function keeperOver(storage: () => Storage): Keeper {
  let usable = true;
  let memory: string | null = null;
  function using<T>(stored: (store: Storage) => T, remembered: () => T): T {
    if (usable) {
      try {
        return stored(storage());
      } catch {
        usable = false;
      }
    }
    return remembered();
  }
  return {
    get: () =>
      using(
        (store) => store.getItem(TOKEN_KEY),
        () => memory,
      ),
    set: (token) =>
      using(
        (store) => store.setItem(TOKEN_KEY, token),
        () => {
          memory = token;
        },
      ),
    clear: () =>
      using(
        (store) => store.removeItem(TOKEN_KEY),
        () => {
          memory = null;
        },
      ),
  };
}

/** The page's own keeper. */
export const token: Keeper = keeperOver(() => window.localStorage);

export interface SignedOut {
  subscribe(listener: () => void): () => void;
  current(): boolean;
  mark(): void;
}

/** Whether the server has refused the page's token since the page loaded. Once marked, the
 * page shows it is signed out and asks nothing more: nothing retries. */
export function signedOutStore(): SignedOut {
  let out = false;
  const listeners = new Set<() => void>();
  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    current: () => out,
    mark() {
      if (out) return;
      out = true;
      for (const listener of listeners) listener();
    },
  };
}

/** The page's own. */
export const signedOut: SignedOut = signedOutStore();
