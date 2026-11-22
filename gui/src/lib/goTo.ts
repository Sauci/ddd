import type { NamesReply } from "../api/types";
import { moreNames, type NameList } from "./declarations";
import { filterText } from "./filter";
import type { Route } from "./route";

/**
 * The masthead's go-to (16:I14): a variable found by a part of its name, over every component of
 * the project, where the tables draw only the rows in view and the browser's own find cannot reach
 * the rest. The names are the server's, from the index of the newest analysis (`GET /api/names`),
 * the name spelling the text exactly first, at most fifty of them; picking one opens its panel on
 * the page of the component producing it, or of the first declaring it where none does.
 */

/** What the go-to is called, and reads while it is empty. */
export const GO_TO = "Go to a variable";

/** What the go-to's list says while the names of what is typed are on their way. */
export const FINDING_NAMES = "Finding names…";

/** What the go-to's list says where no name holds what is typed. */
export const NO_NAME = "no variable matches";

/** The go-to's list: its entries and the line at its foot, as the declare form's Name list has
 * them, and what it says while it holds no entry - `undefined` where it stays closed. */
export interface GoToList extends NameList {
  empty: string | undefined;
}

/** The go-to's list for what is typed, from the names the server answered (`reply`): one entry per
 * name, in the server's order, its kind and the component it opens on beside it, and the line at
 * its foot saying how many more hold the text than were answered, and to type to narrow them.
 *
 * The names come after the text: React Aria opens a list on what is typed only where the list
 * holds entries then, so the go-to's opens empty, saying it is finding names until some have come,
 * and that none matches where none does. Closed while nothing is typed - an answer kept from an
 * earlier text is no list of this one - or where the server `refused`, which is said under the
 * field instead. */
export function goToList(reply: NamesReply | undefined, typed: string, refused: boolean): GoToList {
  if (filterText(typed) === "" || refused) {
    return { sections: [], footnote: undefined, empty: undefined };
  }
  if (reply === undefined) return { sections: [], footnote: undefined, empty: FINDING_NAMES };
  if (reply.names.length === 0) return { sections: [], footnote: undefined, empty: NO_NAME };
  return {
    sections: [
      {
        id: "names",
        title: "This project's variables",
        choices: reply.names.map((named) => ({
          id: named.name,
          label: named.name,
          detail: `${named.kind} in ${named.component}`,
        })),
      },
    ],
    footnote: moreNames(reply.total - reply.names.length),
    empty: NO_NAME,
  };
}

/** Where going to `name` leads: the page of the component the server opens it on, its panel
 * open; `null` for a name the answer does not hold - Enter on a text no name answered spells
 * exactly, its case included. */
export function goToRoute(reply: NamesReply | undefined, name: string): Route | null {
  const named = reply?.names.find((each) => each.name === name);
  if (named === undefined) return null;
  return { page: "component", file: named.file, variable: named.name };
}

/** What Enter does on the go-to's text: goes to the name; waits for the text's own answer
 * (`"ask"`), asked at once; or opens the list on that answer (`"list"`). */
export type Entered = { go: Route } | "ask" | "list";

/**
 * What Enter on `name`, the text the go-to holds, does (16:I14). Enter is a commit, which moves at
 * once (`useDebounced`): it goes to the name where the answer in hand holds it spelled exactly -
 * `reply`, the text's own answer or an earlier text's, kept listed while the next is asked. Where
 * it does not, and the text's own answer (`own`) has not come, the text is asked for at once and
 * Enter waits for its answer; where that answer has come and does not hold it either, the list
 * opens on what it holds, its names or that none matches. Enter never ends in a closed list over a
 * field holding a text as though it had been taken. Nothing for a field holding nothing.
 */
export function entered(
  name: string,
  reply: NamesReply | undefined,
  own: NamesReply | undefined,
): Entered | null {
  if (filterText(name) === "") return null;
  const route = goToRoute(reply, name);
  if (route !== null) return { go: route };
  return own === undefined ? "ask" : "list";
}

/** The answer of the very text the go-to holds (`typed`), `undefined` until it has come: an answer
 * is the text's own once it is no earlier text's kept listed while the next is asked
 * (`placeholder`), and was asked for this text (`asked`, what was last asked for), not one typing
 * has since gone past. */
export function ownAnswer(
  reply: NamesReply | undefined,
  placeholder: boolean,
  asked: string,
  typed: string,
): NamesReply | undefined {
  return !placeholder && asked === filterText(typed) ? reply : undefined;
}
