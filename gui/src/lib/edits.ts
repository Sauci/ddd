import type { Changes } from "../api/types";

/** The json text of a string, which is how a value travels to the server. */
export function jsonText(text: string): string {
  return JSON.stringify(text);
}

/** An edit writing `raw` at one pointer of one file, as that file was read at `fingerprint`. */
export function setValue(file: string, fingerprint: string, pointer: string, raw: string): Changes {
  return { changes: [{ file, fingerprint, operations: [{ op: "set", pointer, raw }] }] };
}
