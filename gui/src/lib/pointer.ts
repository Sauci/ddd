const SEGMENT = /\[(\d+)\]|([^.[\]]+)/g;

/** `a.b[2].c` -> `["a", "b", 2, "c"]`: the twin of `ddd.lsp.ranges.segments`. */
export function segments(pointer: string): (string | number)[] {
  return Array.from(pointer.matchAll(SEGMENT), (match) =>
    match[1] === undefined ? (match[2] as string) : Number(match[1]),
  );
}

/** The pointer the segments spell, the way ddd spells it. */
export function pointerOf(parts: readonly (string | number)[]): string {
  return parts.reduce<string>((pointer, part) => {
    if (typeof part === "number") return `${pointer}[${part}]`;
    return pointer === "" ? part : `${pointer}.${part}`;
  }, "");
}

/** What is written at a pointer of a parsed document, or `undefined` where nothing is. */
export function valueAt(data: unknown, pointer: string): unknown {
  let value: unknown = data;
  for (const part of segments(pointer)) {
    if (typeof part === "number") {
      if (!Array.isArray(value)) return undefined;
      value = value[part];
    } else {
      if (
        typeof value !== "object" ||
        value === null ||
        Array.isArray(value) ||
        !Object.hasOwn(value, part)
      ) {
        return undefined;
      }
      value = (value as Record<string, unknown>)[part];
    }
  }
  return value;
}

/** Whether a finding at `pointer` is about the entry at `entry` or about something inside it. */
export function within(pointer: string, entry: string): boolean {
  return pointer === entry || pointer.startsWith(`${entry}.`) || pointer.startsWith(`${entry}[`);
}
