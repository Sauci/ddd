import { pointerOf, valueAt } from "./pointer";
import { asList, asText } from "./values";

/** The line a variable's panel says what it does not do in, and where that is done: a variable is
 * renamed - the language server rewrites every place that names it - and moved to another scope
 * in its file, in the editor. */
export const EDITED_ELSEWHERE =
  "Renaming the variable and changing its scope are done in its file, in the editor.";

/** The description the declaration of `name` states in a component file's parsed content (`GET
 * /api/file`): the empty text where it states none, which is the model's own default, and `null`
 * where the file declares no such variable - or has no interface, or did not parse. */
export function descriptionIn(data: unknown, name: string): string | null {
  const entries = asList(valueAt(data, "component.interface"));
  for (let index = 0; index < entries.length; index += 1) {
    const at = pointerOf(["component", "interface", index, "definition"]);
    if (valueAt(data, `${at}.name`) === name)
      return asText(valueAt(data, `${at}.description`)) ?? "";
  }
  return null;
}

/** What the description field shows: the text typed into it, the empty text of a field cleared
 * included, or the declaration's own while nothing is. */
export function descriptionShown(typed: string | undefined, stored: string): string {
  return typed ?? stored;
}

/** Which declaration a description is for: the variable's, in the component file the panel is
 * open from. */
export interface Described {
  file: string;
  name: string;
}

/** What describing is asked of the server: the declaration and the text it is to state, `""`
 * taking the key away. `null` where there is nothing to ask - no component in view (`where`
 * `undefined`: the project screen's own panel), nothing typed, or text typed back to the
 * declaration's own. */
export function describeRequest(
  where: Described | undefined,
  typed: string | undefined,
  stored: string,
): (Described & { description: string }) | null {
  if (where === undefined || typed === undefined || typed === stored) return null;
  return { ...where, description: typed };
}

/** What a description changed is, in a sentence above the preview. */
export function describeSentence(name: string, from: string, description: string): string {
  if (description === "") return `Takes the description of ${name} out of ${from}`;
  return `Sets the description of ${name} in ${from}`;
}
