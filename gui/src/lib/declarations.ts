import type { DeclarableName, DeclarableReply, VariableKeyOffer } from "../api/types";

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
      if (key.carried[0]?.required === true) return null;
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

/** The json a row of dimension fields makes: a whole number stays a number, anything else is
 * the name of a constant. `null` while any row is blank - a value block is never a scalar, so
 * a half-filled row states nothing rather than a shape nobody asked for. */
export function dimensionsRaw(rows: string[]): string | null {
  if (rows.length === 0 || rows.some((row) => row.trim() === "")) return null;
  return JSON.stringify(
    rows.map((row) => (/^[1-9][0-9]*$/.test(row.trim()) ? Number(row.trim()) : row.trim())),
  );
}

/** The sentence above the preview, which is what tells reading from declaring apart before
 * anything is written. */
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
    return `Reads ${typed} as ${whose} declares it.`;
  }
  const role = ROLE[scope] ?? scope;
  return `Declares ${typed}, a ${kind} this component ${role}.`;
}
