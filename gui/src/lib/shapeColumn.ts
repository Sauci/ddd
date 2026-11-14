/** The kinds whose definition states no `dimensions` at all and reads its own word instead - a
 * curve or a map over its axis or axes, or an axis itself. */
const SHAPED_BY_KIND = new Set(["curve", "map", "axis"]);

/** Whether this declaration's kind is one of those - a numeric table whose shape follows from
 * the axes it refers to, which the file itself cannot resolve. */
function shapedByKind(kind: string | undefined): kind is string {
  return kind !== undefined && SHAPED_BY_KIND.has(kind);
}

/** What each type of the project is, by name: `scalar`, `external`, `struct`, or `""` for an entry
 * whose file has drifted since the analysis read it (`GET /api/types`, `ProjectType.kind`). */
export function typeKinds(types: readonly { name: string; kind: string }[]): Map<string, string> {
  return new Map(types.map((type) => [type.name, type.kind]));
}

/** The type a declaration names, and what the project's types are: `kinds` is `undefined` while
 * they are not yet known. */
export interface NamedType {
  name: string | undefined;
  kinds: ReadonlyMap<string, string> | undefined;
}

/** What one declaration's Shape column shows, and whether it is the button to its values page. */
export interface ShapeColumn {
  /** The text: `null` where nothing is said. */
  text: string | null;
  /** Whether the text is a button to the values page, which can draw what it opens. */
  offered: boolean;
}

/**
 * The Shape column of one declaration, read from the file already open and the project's types
 * (one `GET /api/types` for the page, not one request per row): `State` carries no dictionary, so
 * there is no other source.
 *
 * A `dimensions` on the definition is spelled the way the file spells each entry - `16`, or
 * `4 × 2` for more than one - exactly as a type member's own dimensions are (`projectTypes.ts`).
 * A curve, a map or an axis carries no `dimensions` at all, and reads its kind's own word. A
 * scalar - `dimensions` and a shaped kind both absent - reads `scalar` where its storage is a
 * number: a `datatype` of its own, or a `typename` naming a type the project says is a `scalar`
 * one. A name that is a struct, an external type, a drifted entry or no type at all, and a name
 * while the types are not yet known, leave it blank: a structure has no grid.
 *
 * The text is a button only where the grid can draw what it opens, and plain text otherwise: a
 * button that refused the moment it was pressed would be a button that lies (spec 5.1). A curve,
 * a map or an axis is a numeric table whatever type it names - measured, a curve naming a scalar
 * type resolves exactly as one stating its own storage does - so its kind alone is enough.
 * Anything else needs a numeric storage as above, with `dimensions` or without, since
 * `DataDictionary.objects` holds no structure at all and the grid would answer that the project
 * declares no such object. More dimensions than two is more than a grid draws, whichever way in.
 * A text `init` in this very file is text and not a grid; a consumer's declaration cannot see its
 * producer's `init`, so a text one elsewhere is offered anyway, and the grid it opens says so
 * itself (`ValuesGridView`, `reply.stated`).
 */
export function shapeColumn(
  kind: string | undefined,
  dimensions: readonly unknown[],
  datatype: string | undefined,
  init: unknown,
  type: NamedType = { name: undefined, kinds: undefined },
): ShapeColumn {
  const numeric =
    datatype !== undefined || (type.name !== undefined && type.kinds?.get(type.name) === "scalar");
  let text: string | null = null;
  if (dimensions.length > 0) text = dimensions.map(String).join(" × ");
  else if (shapedByKind(kind)) text = kind;
  else if (numeric) text = "scalar";
  const offered =
    typeof init !== "string" && dimensions.length <= 2 && (shapedByKind(kind) || numeric);
  return { text, offered };
}
