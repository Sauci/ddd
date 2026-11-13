import { ApiError } from "../api/client";

/**
 * What a panel of several writes holds of the server's refusal of one of them: which write it was
 * - an action, a key - and the sentence it says. A panel of one write holds the sentence alone.
 *
 * Either is held until the reader's next choice in the panel, whatever the refusal's code: what
 * takes the panel's other refusals away takes it away too - another write chosen, a field typed
 * into, a value picked, the write applied again, the strip closed - and a revision landing never
 * does. A refusal because a file changed on disk used to go as the revision after the one it was
 * refused at came, so that a reader would not send the refused fingerprints straight back before
 * the analysis had caught up. Refusing one, the server now asks for that analysis itself
 * (`ddd.gui.session.Session._refused`), and its revision reaches the page a few milliseconds from
 * the refusal, sooner or later than it: tied to the revision, the sentence was gone as soon as it
 * was drawn, or stayed until the revision after, and a reader was not told why nothing was
 * written. Tied to their next choice, it stays for as long as they need it, and what it says of
 * the panel - that it now shows the files as they are - holds once that revision has come, in
 * whichever order the two reached the page, with nothing in the server's answer needed to say
 * which.
 */
export interface Refused<A> {
  about: A;
  text: string;
}

/** Whether an Apply was refused because a file changed on disk since its plan was made: the
 * refusal a panel says in a sentence of its own, that nothing was written. The server's own code
 * for it, `ddd.editing.STALE`: never a word of the sentence, which the server may reword. */
export function isStale(error: Error): boolean {
  return error instanceof ApiError && error.code === "stale";
}

/**
 * The one refusal a panel of several writes shows beside its write `about`: the refusal it holds
 * of that write's Apply (`Refused`), else why the write's plan was refused when asked for, in the
 * server's own words - `asked`, read straight off `planShown`'s own `refusal` (`lib/typing.ts`) -
 * else none. A panel of one write shows the sentence it holds, else its plan's, the same way.
 *
 * `asked` is the answer of the revision on screen, the plan being asked for again at every one, so
 * a revision landing moves it - none while the new plan is asked for, then that plan's own answer -
 * and never the refusal held, which only the reader's next choice takes away. A refusal held of
 * another of the panel's writes is not shown beside this one, nor does it take this one's Apply
 * away.
 */
export function refusalShown<A>(
  held: Refused<A> | null,
  asked: string | null,
  about: A,
): string | null {
  return held !== null && held.about === about ? held.text : asked;
}

/** What a page holds of the refusal of an offer it makes - adopting a vocabulary - once it has
 * read whether it still makes that offer: the refusal while it does, and none once the offer is
 * withdrawn. A refusal is of the offer it was made of and does not outlive it: the same offer made
 * again, once the page reads that it can be, is a new one, and starts with no refusal. */
export function refusalOfOffer<T>(held: T | null, offered: boolean): T | null {
  return offered ? held : null;
}

/** What a panel about one entity shows of the server's answer about it: the answer, a refusal in
 * its place, "Updating the findings…" alone, or that it is reading. */
export type PanelShows<T> =
  | { shown: "reply"; reply: T }
  | { shown: "refusal"; refusal: string }
  | { shown: "updating" }
  | { shown: "reading" };

/** Whether an answer was refused because a file it is built from did not load, or changed since
 * the analysis read it - the server's own code, `ddd.editing.UNREADABLE`. */
function isUnreadable(error: Error): boolean {
  return error instanceof ApiError && error.code === "unreadable";
}

/**
 * What the panel open on one entity - a variable, a unit, a type, a constant, a section or a
 * raster, which `about` names an answer by - shows of the answer about it, while the findings are
 * `updating` or not.
 *
 * An edit is answered once its files are written and analysed after (spec 5), and these answers
 * are built from what the last analysis indexed: an entity an edit renamed or added - or moved
 * within its file, an entry above it taken out or put back - is refused `unreadable` until the
 * analysis reading that file lands. Each route reads an entity only at a place the index recorded
 * that still names it, and refuses it where none is left (`ddd.variables.declarations_of` for a
 * variable; `ddd.project_shared.entry_in_place`, `ddd.project_types.type_in_place` and
 * `ddd.project_units.listed_in_place` for the others): "'RPM' is not declared in any file that
 * has not changed since, and pump.ddd.json, units.ddd.json changed since it was read". While the
 * findings are updating, that refusal is not shown: the panel says "Updating the findings…" in its
 * place, over what its query still holds of its own entity, and alone where it holds nothing of
 * it - a renamed or an added entity's panel. What a query holds is the last answer of its own key:
 * a revision that lands while the page is still updating starts a new key, and where that key's
 * first answer is refused, the panel says the note alone, its content gone until an answer comes.
 * That is accepted. It never shows another entity's answer under this one's name, which a query
 * carries from one key to the next (`placeholderData`) and could carry from a name before. Every
 * other refusal, and an `unreadable` one once nothing is updating, is shown as it always was.
 *
 * The moment the analysis lands asks nothing of its own: the state's revision moves before the
 * panel's next answer comes, and the panel's query, keyed by that revision, starts again with no
 * refusal - the panel shows the answer it kept meanwhile, or that it is reading.
 */
export function panelShows<T>(
  answer: { data: T | undefined; error: Error | null },
  about: (reply: T) => string,
  name: string,
  updating: boolean,
): PanelShows<T> {
  const own = answer.data !== undefined && about(answer.data) === name ? answer.data : undefined;
  if (answer.error !== null && !(updating && isUnreadable(answer.error))) {
    return { shown: "refusal", refusal: answer.error.message };
  }
  if (own !== undefined) return { shown: "reply", reply: own };
  return answer.error === null ? { shown: "reading" } : { shown: "updating" };
}
