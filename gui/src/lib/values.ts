/** A string written in a description, or `undefined` for anything else. */
export function asText(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

/** An array written in a description, or an empty one for anything else. */
export function asList(value: unknown): readonly unknown[] {
  return Array.isArray(value) ? value : [];
}
