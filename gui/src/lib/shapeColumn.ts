/** The kinds whose definition states no `dimensions` at all and reads its own word instead - a
 * curve or a map over its axis or axes, or an axis itself. */
const SHAPED_BY_KIND = new Set(["curve", "map", "axis"]);

/** Whether this declaration's kind is one of those - a numeric table whose shape follows from
 * the axes it refers to, which the file itself cannot resolve. */
function shapedByKind(kind: string | undefined): kind is string {
  return kind !== undefined && SHAPED_BY_KIND.has(kind);
}

/** What one declaration's Shape column shows, and whether it is the button to its values page. */
export interface ShapeColumn {
  /** The text: `null` where nothing is said. */
  text: string | null;
  /** Whether the text is a button to the values page, which can draw what it opens. */
  offered: boolean;
}

/**
 * The Shape column of one declaration, read from the file already open rather than asked of the
 * server: `State` carries no dictionary - the revision, the project, its files and how many
 * findings there are - so there is no second source and no request per row.
 *
 * A `dimensions` on the definition is spelled the way the file spells each entry - `16`, or
 * `4 × 2` for more than one - exactly as a type member's own dimensions are (`projectTypes.ts`).
 * A curve, a map or an axis carries no `dimensions` at all, and reads its kind's own word. A
 * scalar - `dimensions` and a shaped kind both absent - reads `scalar` where it states its own
 * `datatype`, and is a grid of one cell; one naming a type states none, and is left blank, since
 * the type may be a structure, which no grid holds.
 *
 * The text is a button only where the grid can draw what it opens, and plain text otherwise: a
 * button that refused the moment it was pressed would be a button that lies (spec 5.1). A curve,
 * a map or an axis is a numeric table whatever type it names - measured, a curve naming a scalar
 * type resolves exactly as one stating its own storage does - so its kind alone is enough.
 * Anything else has to state a `datatype` of its own, with `dimensions` or without: a
 * `typename` is a structured declaration, which `DataDictionary.objects` does not hold at all,
 * so the grid would answer that the project declares no such object. More dimensions than two is
 * more than a grid draws, whichever way in. A text `init` in this very file is text and not a
 * grid; a consumer's declaration cannot see its producer's `init`, so a text one elsewhere is
 * offered anyway, and the grid it opens says so itself (`ValuesGridView`, `reply.stated`).
 */
export function shapeColumn(
  kind: string | undefined,
  dimensions: readonly unknown[],
  datatype: string | undefined,
  init: unknown,
): ShapeColumn {
  let text: string | null = null;
  if (dimensions.length > 0) text = dimensions.map(String).join(" × ");
  else if (shapedByKind(kind)) text = kind;
  else if (datatype !== undefined) text = "scalar";
  const offered =
    typeof init !== "string" &&
    dimensions.length <= 2 &&
    (shapedByKind(kind) || datatype !== undefined);
  return { text, offered };
}
