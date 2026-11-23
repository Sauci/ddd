import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

/** Whether the reader's system asks for less motion, and again when they change it. Glue only:
 * what a flight of the viewport lasts for it is `flightOf`'s (`lib/canvas.ts`). */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const query = window.matchMedia(QUERY);
      query.addEventListener("change", notify);
      return () => query.removeEventListener("change", notify);
    },
    () => window.matchMedia(QUERY).matches,
  );
}
