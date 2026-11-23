import type { UnreadDescription } from "../api/types";

/** What opening a project has come to, as the start page's mutation says it: `useMutation`'s own
 * status. */
export type Opening = "idle" | "pending" | "success" | "error";

/**
 * Whether the start page's list takes no press (`StartPage.tsx`): from the press that opens a
 * project until the page leaves the list.
 *
 * Not only while the open is asked (`pending`). Once it is answered the page asks the server who
 * has a project open and draws this list until that answer lands (`onOpened`, `App.tsx`), and a
 * press then would open another project in place of the one just opened. An open the server
 * refused (`error`) gives the list back, with the reason above it.
 */
export function listHeld(opening: Opening): boolean {
  return opening === "pending" || opening === "success";
}

/** The heading over the descriptions the walk found and could not read (16:M13): a file left off
 * the list above in silence, a reader looking for it would take for not there. */
export const UNREAD_HEADING = "Project descriptions that could not be read";

/** One such file as the start page says it: its path, and why the server could not read it,
 * as the build records not used are (`path: reason`). */
export function unreadLine(entry: UnreadDescription): string {
  return `${entry.path}: ${entry.reason}`;
}
