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

/** The keys a kind asks for: the ones it must state first, each group in the server's order.
 * Required first because a form a reader fills top to bottom should ask for what it cannot do
 * without before what it can. */
export function keysOf(kind: string, reply: DeclarableReply): VariableKeyOffer[] {
  const keys = reply.kinds.find((entry) => entry.kind === kind)?.keys ?? [];
  const required = keys.filter((key) => key.carried[0]?.required === true);
  return [...required, ...keys.filter((key) => key.carried[0]?.required !== true)];
}

/** The definition the form has made, as json text - `null` while it could not be written:
 * no name, no kind, a required key unstated, or a value that is not json. */
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
