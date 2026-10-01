import { createContext, useContext } from "react";

/** Whether the findings on screen may be about to change (spec 6) - `useProjectState`'s
 * `updating`, provided around the page by `App` so that every screen can say so where its
 * findings are. Glue only: `updatingOf` (lib/updating.ts) decides it. */
export const UpdatingContext = createContext(false);

/** The findings' `UpdatingContext`: what a screen reads, and hands to the views it draws. */
export function useUpdating(): boolean {
  return useContext(UpdatingContext);
}
