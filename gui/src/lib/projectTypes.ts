import type { TypeMember, TypeReply, TypesReply, VariableKeyOffer } from "../api/types";
import { shortValue } from "./variableKeys";

/** What a kind is called on the page: the file says `struct`, a reader reads "structure". */
const KIND_WORDS: Record<string, string> = {
  scalar: "scalar",
  struct: "structure",
  external: "external",
};

export interface TypeRowShown {
  name: string;
  kind: string;
  kindWord: string;
  description: string;
  uses: number;
  findings: number;
}

/** Every type as the table draws it, in the order the server sorted them. */
export function typeRows(reply: TypesReply): TypeRowShown[] {
  return reply.types.map((entry) => ({ ...entry, kindWord: KIND_WORDS[entry.kind] ?? "unknown" }));
}

/** What the tab's meta line says: how many types, and how many of each kind there are any of. */
export function typesTitle(reply: TypesReply): string {
  if (reply.types.length === 0) return "This project declares no types";
  const counted = (["scalar", "struct", "external"] as const)
    .map((kind) => [kind, reply.types.filter((entry) => entry.kind === kind).length] as const)
    .filter(([, count]) => count > 0)
    .map(([kind, count]) => `${count} ${plural(KIND_WORDS[kind] as string, count)}`);
  return `${reply.types.length} ${plural("type", reply.types.length)} · ${counted.join(", ")}`;
}

export interface TypeKeyRow {
  key: string;
  label: string;
  text: string;
  offer: VariableKeyOffer;
}

/** A row per key a scalar fixes, in the order the answer lists them; none for the other kinds.
 *
 * The text reads the way `variableKeys.labelOfRaw` reads a value - "state nothing" for a key
 * nothing states, else its short form - but is not called through it: `labelOfRaw` takes a
 * `VariableReply` it never reads, carried only for symmetry with `startingRaw`, which a type
 * has no use for, since its offer already carries the one value it has, if it has one at all.
 * `shortValue` is `labelOfRaw`'s own formatter, and public for exactly this.
 */
export function keyRowsOfType(reply: TypeReply): TypeKeyRow[] {
  return reply.keys.map((offer) => ({
    key: offer.key,
    label: capitalised(offer.key),
    text: textOf(offer.key, offer.values[0]?.raw ?? null),
    offer,
  }));
}

/** `labelOfRaw`'s own reading of a key's value, without a `VariableReply` to call it with. */
function textOf(key: string, raw: string | null): string {
  return raw === null ? "state nothing" : shortValue(key, raw);
}

export interface TypeMemberRow {
  id: string;
  name: string;
  member: string;
  type: string;
  unit: string;
  bits: string;
  dimensions: string;
}

/** A structure's members as the panel's columns read them. */
export function memberRows(reply: TypeReply): TypeMemberRow[] {
  return reply.members.map((member: TypeMember) => ({
    id: member.name,
    name: member.name,
    member: member.member,
    type: member.typename ?? member.datatype ?? "",
    unit: member.unit ?? "",
    bits: member.bits === null ? "" : String(member.bits),
    dimensions: member.dimensions.join(" × "),
  }));
}

/** A noun in the count it is asked for: `plural("type", 1)` is `"type"`, `plural("type", 2)` is
 * `"types"`. `lib/units.ts` and `lib/undo.ts` each already spell their own single noun's plural
 * inline; this tab counts four - `type` and each of the three kinds - which is worth one shared
 * helper instead of four. */
function plural(noun: string, count: number): string {
  return count === 1 ? noun : `${noun}s`;
}

/** `capitalised("datatype")` is `"Datatype"`: a key's label, from its own json spelling. */
function capitalised(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
