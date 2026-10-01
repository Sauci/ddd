import { ApiError } from "../api/client";

/** What a panel refused, and the revision it was refused at. */
export interface Refused {
  text: string;
  revision: number | undefined;
}

/**
 * The refusal a panel shows: the one stored, until the analysis has moved past the revision it
 * was refused at.
 *
 * A stale refusal is the reason this exists. The server refuses an edit whose file changed on
 * disk, and the panel says the files are shown as they are - but the analysis that noticed the
 * change has not finished yet, so everything on screen, the fingerprints included, is still the
 * revision that was refused. Choosing again straight away sends those same fingerprints and is
 * refused a second time. Holding the sentence until the next revision arrives makes it true:
 * the watcher answers within a second, and what comes back is a panel that can be applied.
 */
export function shownRefusal(stored: Refused | null, revision: number | undefined): string | null {
  if (stored === null) return null;
  return stored.revision === revision ? stored.text : null;
}

/** Whether an Apply was refused because a file changed on disk since its plan was made - the one
 * refusal a panel holds until the analysis moves on (`shownRefusal`), where every other is cleared
 * by the reader's next choice. The server's own code for it, `ddd.editing.STALE`: never a word of
 * the sentence, which the server may reword. */
export function isStale(error: Error): boolean {
  return error instanceof ApiError && error.code === "stale";
}

/**
 * The one refusal an action shows, of the three it can have: an Apply refused as stale, while the
 * revision it was refused at stands; else an Apply refused for another reason; else why its plan
 * was refused when asked for, in the server's own words.
 *
 * The precedence the other panels already have, kept rather than argued afresh: `UnitsPage`'s
 * adoption banner writes this very expression, and `ConstantPanel`'s own `offer` asks in the same
 * order - though once a stale refusal's revision has passed, that one shows nothing, where this, as
 * `UnitsPage`'s does, falls through to whichever of the other two there is.
 */
export function refusalShown(
  stale: Refused | null,
  refused: string | null,
  asked: Error | null,
  revision: number | undefined,
): string | null {
  return shownRefusal(stale, revision) ?? refused ?? asked?.message ?? null;
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
 * are built from what the last analysis indexed: an entity an edit renamed or added, or whose
 * declaration it moved within its file, is refused `unreadable` until the analysis reading that
 * file lands - "'RPM' is not declared in any file that has not changed since, and pump.ddd.json,
 * units.ddd.json changed since it was read". While the findings are updating, that refusal is not
 * shown: the panel says "Updating the findings…" in its place, over what it already showed of its
 * own entity, and alone where it showed nothing of it yet - a renamed or an added entity's panel.
 * It never shows another entity's answer under this one's name, which a query carries from one
 * key to the next (`placeholderData`) and could carry from a name before. Every other refusal,
 * and an `unreadable` one once nothing is updating, is shown as it always was.
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
