import type { DeclarableName, DeclarableReply, VariableKeyOffer } from "../api/types";
import { countText, decimalText, readNumber } from "./numbers";
import { unsettled } from "./typing";
import { shortValue } from "./variableKeys";

/** Which of the two verbs the name field has landed on. */
export type Mode = "unchosen" | "read" | "declare";

/** How the page words each scope, as ROLES words it on every other screen. */
const ROLE: Record<string, string> = {
  output: "produces",
  input: "reads",
  local: "keeps to itself",
};

export function chosenName(typed: string, names: DeclarableName[]): DeclarableName | null {
  return names.find((entry) => entry.name === typed) ?? null;
}

export function modeOf(typed: string, names: DeclarableName[]): Mode {
  if (typed === "") return "unchosen";
  return chosenName(typed, names) === null ? "declare" : "read";
}

export function scopesOf(typed: string, reply: DeclarableReply): string[] {
  return [...(chosenName(typed, reply.names)?.scopes ?? reply.scopes)];
}

/** The scope the form keeps once the name it scopes changes, or the answer the name is read
 * against does - `scopes` being what the name may take now (`scopesOf`): the scope chosen while
 * the name still takes it, else the first the name does, else none. It only ever moves forward:
 * typing between two names that both take the scope chosen leaves it as it was, never back onto
 * a scope let go of for a name typed in between. */
export function followedScope(current: string, scopes: readonly string[]): string {
  return scopes.includes(current) ? current : (scopes[0] ?? "");
}

/** The keys a kind asks for when it is declared new: what a *loadable* declaration needs, not
 * everything the kind accepts. `unit`, `limits` and a composed `conversion` are left for the key
 * chooser to add afterwards, the way part 3 already leaves them for any other declaration - no
 * kind requires them. Required keys first (`volatile` always, plus whichever of `dimensions`,
 * `size`, `axis`, `x_axis` or `y_axis` this kind needs), then `datatype` and `typename` - the
 * storage a declaration must name exactly one of - each group in the server's order. */
export function keysOf(kind: string, reply: DeclarableReply): VariableKeyOffer[] {
  const keys = reply.kinds.find((entry) => entry.kind === kind)?.keys ?? [];
  const required = keys.filter((key) => key.carried[0]?.required === true);
  const storage = keys.filter(
    (key) =>
      key.carried[0]?.required !== true && (key.key === "datatype" || key.key === "typename"),
  );
  return [...required, ...storage];
}

/** The definition the form has made, as json text - `null` while it could not be written:
 * no name, no kind, a required key unstated, or a value that is not json. A stated `datatype`
 * carries the identity `conversion` with it (`{"kind": "identity"}`) - the one answer the server
 * requires be stated rather than composed, so `keysOf` offers no field for it. */
export function definitionOf(
  name: string,
  kind: string,
  values: Record<string, string>,
  reply: DeclarableReply,
): string | null {
  if (name === "" || kind === "") return null;
  const definition: Record<string, unknown> = { name, kind };
  for (const key of keysOf(kind, reply)) {
    const raw = values[key.key];
    if (raw === undefined || raw === "") {
      if (requires(key)) return null;
      continue;
    }
    try {
      definition[key.key] = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (definition.datatype !== undefined) definition.conversion = { kind: "identity" };
  return JSON.stringify(definition);
}

/** A name a constant may have: what a dimension's field reads as a name rather than as a number. */
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

/** One dimension's field read: the json text it travels as - a name as a string, anything else
 * as the number it spells, read as every field reads one (`numbers.ts`) and in its digits, never
 * the double nearest them - or the sentence a spelling in another notation, a comma that could be
 * either or text that is no number is refused with. */
function dimensionOf(row: string): { json: string } | { refusal: string } {
  const text = row.trim();
  if (IDENTIFIER.test(text)) return { json: JSON.stringify(text) };
  const read = readNumber(text);
  return "decimal" in read ? { json: decimalText(read.decimal) } : { refusal: read.refusal };
}

/** Why one dimension's field is refused, or `undefined` while it holds a name, a number or
 * nothing yet: the note under the field. */
export function dimensionNote(row: string): string | undefined {
  if (row.trim() === "") return undefined;
  const dimension = dimensionOf(row);
  return "refusal" in dimension ? dimension.refusal : undefined;
}

/** The json a row of dimension fields makes: a name is the name of a constant, and anything else
 * the number it spells. `null` while any row is blank - a value block is never a scalar, so a
 * half-filled row states nothing rather than a shape nobody asked for - or refused
 * (`dimensionNote`), which asks for no plan. */
export function dimensionsRaw(rows: string[]): string | null {
  if (rows.length === 0 || rows.some((row) => row.trim() === "")) return null;
  const parts: string[] = [];
  for (const row of rows) {
    const dimension = dimensionOf(row);
    if ("refusal" in dimension) return null;
    parts.push(dimension.json);
  }
  return `[${parts.join(",")}]`;
}

/** The sentence above the preview, which is what tells reading from declaring apart before
 * anything is written. A new name with no kind chosen yet still needs its own sentence - not the
 * one below, which would otherwise interpolate an empty kind. */
export function declareSentence(
  typed: string,
  kind: string,
  scope: string,
  reply: DeclarableReply,
): string {
  const mode = modeOf(typed, reply.names);
  if (mode === "unchosen") return "Choose a variable, or type a new name.";
  if (mode === "read") {
    const producer = chosenName(typed, reply.names)?.producer;
    const whose = producer === null || producer === undefined ? "this project" : producer;
    // The verb follows the scope chosen: reading is what an input does, and the other two write.
    if (scope === "output") return `Produces ${typed} as ${whose} declares it.`;
    if (scope === "local") return `Keeps ${typed} to itself as ${whose} declares it.`;
    return `Reads ${typed} as ${whose} declares it.`;
  }
  if (kind === "") return `Choose a kind for ${typed}.`;
  const role = ROLE[scope] ?? scope;
  return `Declares ${typed}, a ${kind} this component ${role}.`;
}

/** What removing one declaration leaves behind, from what the panel already holds: the other
 * components declaring the variable, and what they do with it. */
export function removalSentence(
  variable: { name: string; declarations: { component: string; role: string }[] },
  from: string,
): string {
  const others = variable.declarations.filter((entry) => entry.component !== from);
  const readers = others.filter((entry) => entry.role === "reads").map((entry) => entry.component);
  if (others.length === 0) {
    return `Removes ${variable.name}, which no other component declares.`;
  }
  if (readers.length === 0) {
    const names = others.map((e) => e.component);
    const verb = names.length === 1 ? "declares" : "declare";
    return `Removes ${variable.name} from ${from}; ${listed(names)} still ${verb} it.`;
  }
  const verb = readers.length === 1 ? "reads" : "read";
  return `Removes ${variable.name} from ${from}; ${listed(readers)} still ${verb} it.`;
}

/** "A", "A and B", "A, B and C" - the way every sentence of this interface lists names. */
function listed(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** The label a key's field shows for its committed value, `shortValue`'s own wording - the same
 * idea `labelOfRaw` reads for an existing variable's chooser, adapted for `values`' "absent
 * means unstated" instead of a `VariableReply` to read `null` from: a declaration being drafted
 * has none yet. A key the kind requires, stated nowhere, reads empty rather than "state nothing":
 * that is a choice the list never held (`stillNeeded`). */
export function labelOf(key: string, raw: string | undefined, required = false): string {
  if (raw === undefined || raw === "") return required ? "" : "state nothing";
  return shortValue(key, raw);
}

/** Whether a kind requires this key of the declaration (`keysOf`'s first group). */
export function requires(key: VariableKeyOffer): boolean {
  return key.carried[0]?.required === true;
}

/** Whether the text typed into a key's field is not the value the form states for it
 * (`unsettled`, lib/typing.ts, decision 15.3). */
export function keyUnsettled(
  key: string,
  typed: Record<string, string | undefined>,
  values: Record<string, string>,
  required = false,
): boolean {
  return unsettled(typed[key], labelOf(key, values[key], required));
}

/** Whether any key's field of this kind's form holds text not yet taken: the form then offers no
 * Add, since it would write what the fields stated before it. A key the kind does not ask for is
 * not in the form, whatever was typed into it earlier. */
export function formUnsettled(
  kind: string,
  reply: DeclarableReply,
  typed: Record<string, string | undefined>,
  values: Record<string, string>,
): boolean {
  return keysOf(kind, reply).some((key) => keyUnsettled(key.key, typed, values, requires(key)));
}

/** The values the form has stated, a value block's rows among them: the rows are folded in under
 * the one key `definitionOf` reads them through, once every row states something. */
export function statedValues(
  values: Record<string, string>,
  dimensions: string[],
): Record<string, string> {
  const raw = dimensionsRaw(dimensions);
  return raw === null ? values : { ...values, dimensions: raw };
}

/** The one line saying what a new declaration still needs before the form can add it, `null`
 * while it needs nothing, or is not one being declared (a name the project already has is read,
 * a kind is chosen first). It is the reason `definitionOf` returns `null`, said in words: each
 * key the kind requires and the form leaves unstated, the storage - `datatype` or `typename`,
 * exactly one - as the one choice it is, and each field holding text not yet taken
 * (`formUnsettled`), which holds Add back as much. */
export function stillNeeded(
  name: string,
  kind: string,
  values: Record<string, string>,
  typed: Record<string, string | undefined>,
  reply: DeclarableReply,
): string | null {
  if (name === "" || kind === "" || chosenName(name, reply.names) !== null) return null;
  const keys = keysOf(kind, reply);
  const stated = (key: string) => values[key] !== undefined && values[key] !== "";
  const needs = keys.filter((key) => requires(key) && !stated(key.key)).map((key) => key.key);
  const storage = keys.filter((key) => key.key === "datatype" || key.key === "typename");
  if (storage.length > 0 && !storage.some((key) => stated(key.key))) {
    needs.push(storage.map((key) => key.key).join(" or "));
  }
  const text = keys
    .filter((key) => keyUnsettled(key.key, typed, values, requires(key)))
    .map((key) => key.key);
  const lines: string[] = [];
  if (needs.length > 0) lines.push(`Still needs ${listed(needs)}.`);
  if (text.length > 0) lines.push(`Text left in ${listed(text)} is not taken yet.`);
  return lines.length === 0 ? null : lines.join(" ");
}

/** How many names the Name list draws at most. React Aria draws every entry of a list it is
 * handed, and the list was drawn whole: over the journeys' generated project of 20,000
 * declarations, C00000's opened on 14,968 names, every one of them in the document, and typing
 * narrowed none. Past fifty the line under them says how many more match, and to type to narrow
 * them (`nameList`). */
export const NAMES_SHOWN = 50;

/** One name the Name list offers: the variable, with its kind and the component producing it. */
export interface NameChoice {
  id: string;
  label: string;
  detail: string;
}

/** The Name list's one section, the project's variables. */
export interface NameSection {
  id: "names";
  title: string;
  choices: NameChoice[];
}

/** The Name list as the field's text leaves it: what it draws, and the line at its foot. */
export interface NameList {
  /** The list's one section, or none where no name holds the text: an empty list closes. */
  sections: NameSection[];
  /** How many more names hold the text than the list draws, and to type to narrow them; `undefined`
   * while it draws every one. */
  footnote: string | undefined;
}

/** The declare form's Name list for the text its field holds: every name of the project holding
 * that text, whatever its case, as the unit picker narrows its own (`pickerSections`,
 * lib/units.ts), drawn to `NAMES_SHOWN` - the name spelling the text exactly first, so that the cap
 * never hides the very name typed - with the line saying how many more match. Only the names drawn
 * are made into entries, so that a key typed costs the page fifty entries, not thousands. */
export function nameList(names: readonly DeclarableName[], typed: string): NameList {
  const wanted = typed.toLowerCase();
  const exact = names.find((entry) => entry.name === typed);
  const others = names.filter(
    (entry) => entry !== exact && entry.name.toLowerCase().includes(wanted),
  );
  const matching = exact === undefined ? others : [exact, ...others];
  const choices = matching.slice(0, NAMES_SHOWN).map((entry) => ({
    id: entry.name,
    label: entry.name,
    detail: `${entry.kind} from ${entry.producer ?? "no producer"}`,
  }));
  const more = matching.length - choices.length;
  return {
    sections:
      choices.length === 0 ? [] : [{ id: "names", title: "This project's variables", choices }],
    footnote:
      more === 0
        ? undefined
        : `${countText(more)} more ${more === 1 ? "name matches" : "names match"}: type to narrow the list.`,
  };
}
