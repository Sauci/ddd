import type { UnreadDescription } from "../api/types";

/** What opening a project has come to, as the start page's mutation says it: `useMutation`'s own
 * status. */
export type Opening = "idle" | "pending" | "success" | "error";

/**
 * Whether the start page's list takes no press (`StartPage.tsx`): from the press that opens a
 * project until the page holds that project open. `before` is the path the page held open at the
 * press (`openPath`, lib/session.ts), `open` the one it holds now, `null` for none.
 *
 * Not only while the open is asked (`pending`). Once it is answered the page asks the server who
 * has a project open and draws this list until that answer lands (`onOpened`, `App.tsx`), and a
 * press then would open another project in place of the one just opened. Once the answer has
 * landed the page holds another project open than at the press, and the list is given back: where
 * the reader went back to it meanwhile (Projects, pressed in the moment between the two answers),
 * it is drawn on, and held for good it took no press until the page was left (15:M15). An open
 * the server refused (`error`) gives the list back, with the reason above it.
 */
export function listHeld(opening: Opening, before: string | null, open: string | null): boolean {
  if (opening === "pending") return true;
  return opening === "success" && open === before;
}

/**
 * Whether the project the start page lists at `listed`, its path, is the one open - `open`, the
 * path the page holds open (`openPath`, lib/session.ts), or `null` while none is: pressed, it is
 * gone to as it stands, and asked of the server to open no more (15:M11). Opened again, it was
 * analysed anew and its undo list emptied, every edit the pages made out of reach, nothing said.
 */
export function isOpen(listed: string, open: string | null): boolean {
  return listed === open;
}

/** What the start page says of the project open, beside its name: the reader is on that project
 * already, and pressing it goes back to it. */
export const ALREADY_OPEN = "Already open";

/** The heading over the descriptions the walk found and could not read (16:M13): a file left off
 * the list above in silence, a reader looking for it would take for not there. */
export const UNREAD_HEADING = "Project descriptions that could not be read";

/** One such file as the start page says it: its path, and why the server could not read it,
 * as the build records not used are (`path: reason`). */
export function unreadLine(entry: UnreadDescription): string {
  return `${entry.path}: ${entry.reason}`;
}

/** Whether the start page draws the list of descriptions that could not be read: only where the
 * walk met one, so that no heading over nothing is drawn on a page where every file was read. */
export function unreadShown(entries: readonly UnreadDescription[]): boolean {
  return entries.length > 0;
}

/** What the start page says in place of the list where no project is offered: the walk found no
 * description at all, or found some (`unread` of them) and could read none, which is not "none was
 * found" while the list below names each. */
export function noProjectSentence(unread: number): string {
  if (unread === 0) {
    return "No project description was found here. Start ddd gui with the path of one.";
  }
  return "No project description found here could be read. Each is listed below with why.";
}
