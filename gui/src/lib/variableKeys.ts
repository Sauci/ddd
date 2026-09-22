import type {
  SettleReply,
  VariableDeclaration,
  VariableKeyOffer,
  VariableReply,
} from "../api/types";
import { textOf } from "./units";

/** What one declaration's cell of a row reads. */
export interface KeyCell {
  /** The value as a reader reads it, `none` where nothing is stated, or why there is no cell. */
  text: string;
  /** Drawn quiet: nothing is stated here, or this kind has no such key. */
  quiet: boolean;
  /** The declared type the value comes from, which the cell names after it. */
  from: string | null;
  /** The preview writes this key into this declaration. */
  changing: boolean;
}

/** One row of the panel's table: a key, and what each declaration says about it. */
export interface KeyRow {
  key: string;
  cells: KeyCell[];
  disagrees: boolean;
  /** Selecting it opens a chooser. `kind` never does. */
  settleable: boolean;
}

/** One column of the panel's table: the declaration it draws, and where the answer lists it. */
export interface KeyColumn {
  declaration: VariableDeclaration;
  /** Its place in `variable.declarations`, which every key's `carried` is indexed by. */
  at: number;
}

/** One value a chooser offers: the json text it settles on, or `null` for "state nothing". */
export interface ValueChoice {
  /** Unique across the whole list: its section, then the value. */
  id: string;
  raw: string | null;
  label: string;
  detail: string;
}

export interface ValueSection {
  id: "declared" | "project" | "nothing" | "typed";
  title: string;
  choices: ValueChoice[];
}

const NOTHING = "state nothing";

/** What each naming editor is naming, for the title of its section and for nothing else. */
const NAMED: Record<string, string> = {
  datatype: "Datatypes",
  typename: "This project's types",
  size: "This project's constants",
  volatile: "True or false",
  axis: "This project's axes",
  x_axis: "This project's axes",
  y_axis: "This project's axes",
  input: "This project's measurements",
};

/** The columns of the panel's table, in the order it draws them: the producer's declaration
 * first (spec 1.1), then the rest as the answer lists them, which is the order the project
 * lists its components in.
 *
 * The one place that order is decided. The header, every row's cells and each key's `carried`
 * are positional and have to line up, so a column keeps the place it has in the answer (`at`)
 * whatever place the table gives it. The answer itself is left alone: other readers of
 * `GET /api/variable` are entitled to the project's own order.
 */
export function keyColumns(variable: VariableReply): KeyColumn[] {
  const columns = variable.declarations.map((declaration, at) => ({ declaration, at }));
  const producer = columns.find((column) => column.declaration.role === "produces");
  if (producer === undefined) return columns;
  return [producer, ...columns.filter((column) => column !== producer)];
}

/** The rows of the panel's table: `kind`, then what disagrees, then what is stated, then the
 * keys this variable's kinds allow and nobody states.
 *
 * A key no declaration's kind holds at all is not a row: an axis has no `x_axis`, and a reader
 * looking at one learns nothing from a line of "not on an axis".
 */
export function keyRows(variable: VariableReply, preview: SettleReply | null): KeyRow[] {
  const columns = keyColumns(variable);
  const kinds = columns.map((column) => column.declaration.stated.kind);
  const kind: KeyRow = {
    key: "kind",
    cells: columns.map(({ declaration }) => ({
      text: textOf(declaration.stated.kind) ?? "none",
      quiet: textOf(declaration.stated.kind) === null,
      from: null,
      changing: false,
    })),
    disagrees: new Set(kinds).size > 1,
    settleable: false,
  };
  const rows = variable.keys
    .filter((offer) => offer.carried.some((carried) => carried.allowed))
    .map((offer) => rowOf(columns, offer, preview));
  // Stable, so the answer's own order - the order a definition spells its keys - survives
  // inside each of the three groups.
  return [kind, ...rows.sort((one, other) => group(one) - group(other))];
}

/** Which of the three groups a row belongs to. */
function group(row: KeyRow): number {
  if (row.disagrees) return 0;
  return row.cells.some((cell) => !cell.quiet) ? 1 : 2;
}

function rowOf(
  columns: readonly KeyColumn[],
  offer: VariableKeyOffer,
  preview: SettleReply | null,
): KeyRow {
  return {
    key: offer.key,
    cells: columns.map((column) => cellOf(column.declaration, offer, column.at, preview)),
    disagrees: offer.disagrees,
    settleable: true,
  };
}

function cellOf(
  declaration: VariableDeclaration,
  offer: VariableKeyOffer,
  at: number,
  preview: SettleReply | null,
): KeyCell {
  const changing = preview !== null && willChangeKey(preview, declaration, offer.key);
  if (offer.carried[at]?.allowed !== true) {
    return {
      text: `not on a ${textOf(declaration.stated.kind) ?? "declaration"}`,
      quiet: true,
      from: null,
      changing,
    };
  }
  const stated = declaration.stated[offer.key];
  const fixed = declaration.fixed[offer.key];
  const raw = stated ?? fixed;
  if (raw === undefined) return { text: "none", quiet: true, from: null, changing };
  return {
    text: shortValue(offer.key, raw),
    quiet: false,
    from: stated === undefined ? declaration.type : null,
    changing,
  };
}

/** Whether a preview writes this key into this declaration. */
export function willChangeKey(
  preview: SettleReply,
  declaration: VariableDeclaration,
  key: string,
): boolean {
  return preview.changes.some(
    (change) =>
      change.file === declaration.path &&
      change.operations.some((operation) => operation.pointer === `${declaration.pointer}.${key}`),
  );
}

/** A value as a reader reads it: short, and in the words the description files use.
 *
 * The json text is what the file says, layout and all; a table of twelve rows has no room for
 * four lines of conversion, and a reader comparing two declarations wants to see at a glance
 * which of them is the odd one.
 */
export function shortValue(key: string, raw: string): string {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    // Not json at all: the file says it, so the table does too.
    return raw;
  }
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((entry) => String(entry)).join(" × ");
  if (value === null || typeof value !== "object") return raw;
  const fields = value as Record<string, unknown>;
  if (key === "limits") return `${format(fields.min)} … ${format(fields.max)}`;
  if (key === "conversion") return conversion(fields);
  return raw.replace(/\s+/g, " ");
}

/** A conversion in one phrase; the kind may be left out where the keys make it plain. */
function conversion(fields: Record<string, unknown>): string {
  const kind =
    fields.kind ??
    (fields.factor !== undefined || fields.offset !== undefined
      ? "linear"
      : fields.enumerators !== undefined || fields.name !== undefined
        ? "enum"
        : "identity");
  if (kind === "linear") {
    const factor = `×${format(fields.factor ?? 1)}`;
    const offset =
      fields.offset === undefined || fields.offset === 0 ? "" : ` ${signed(fields.offset)}`;
    return `linear ${factor}${offset}`;
  }
  if (kind === "enum") {
    if (typeof fields.name === "string") return `enum ${fields.name}`;
    const listed = Array.isArray(fields.enumerators) ? fields.enumerators.length : 0;
    return `enum, ${listed} enumerator${listed === 1 ? "" : "s"}`;
  }
  return String(kind);
}

function signed(value: unknown): string {
  return typeof value === "number" && value > 0 ? `+${value}` : format(value);
}

function format(value: unknown): string {
  return value === undefined ? "?" : String(value);
}

/** The panel's line under the variable's name. */
export function describeVariable(variable: VariableReply): string {
  const first = owner(variable.declarations);
  if (first === undefined) return "";
  const kind = textOf(first.stated.kind) ?? "declaration";
  const datatype = first.type ?? textOf(first.stated.datatype) ?? "no datatype";
  const who =
    first.role === "produces"
      ? `produced by ${first.component}`
      : first.role === "local"
        ? `local to ${first.component}`
        : "no producer";
  const declarations = `${variable.declarations.length} declaration${
    variable.declarations.length === 1 ? "" : "s"
  }`;
  // `kind` is the page's own row - keyRows marks it the same way, so the line and the table
  // never contradict each other over whether it disagrees.
  const kindDisagrees = new Set(variable.declarations.map((entry) => entry.stated.kind)).size > 1;
  const disagreeing =
    variable.keys.filter((offer) => offer.disagrees).length + (kindDisagrees ? 1 : 0);
  const state =
    disagreeing === 0
      ? "all agreed"
      : `${disagreeing} key${disagreeing === 1 ? "" : "s"} disagree${disagreeing === 1 ? "s" : ""}`;
  return `${kind} · ${datatype} · ${who} · ${declarations} · ${state}`;
}

/** Who the variable belongs to: its producer, else the first declaration listed. */
function owner(declarations: readonly VariableDeclaration[]): VariableDeclaration | undefined {
  return declarations.find((entry) => entry.role === "produces") ?? declarations[0];
}

/** What the answer says about one key, or `undefined` for a key it does not carry. */
export function offerOf(variable: VariableReply, key: string): VariableKeyOffer | undefined {
  return variable.keys.find((offer) => offer.key === key);
}

/** The json text the chooser starts on: the first value the answer lists, which is the
 * producer's where a declaration produces the variable and the first in the project's own
 * order where none does. */
export function startingRaw(variable: VariableReply, key: string): string | null {
  return offerOf(variable, key)?.values[0]?.raw ?? null;
}

/** What the field reads for a value while nothing is being typed.
 *
 * Takes the variable for symmetry with `startingRaw`, whose result this labels; the label
 * itself comes from the key and the raw value alone. */
export function labelOfRaw(_variable: VariableReply, key: string, raw: string | null): string {
  return raw === null ? NOTHING : shortValue(key, raw);
}

/** Every section a key's chooser lists, narrowed to what was typed (spec 5.2). */
export function chooserSections(
  offer: VariableKeyOffer,
  owner: string,
  key: string,
  typed: string,
): ValueSection[] {
  const inPlay = offer.values.map((value) =>
    choice("declared", key, value.raw, who(value.components, value.producer)),
  );
  const listed: ValueSection[] = [
    { id: "declared", title: `Declared for ${owner}`, choices: inPlay },
    {
      id: "project",
      title: NAMED[offer.editor === "name" ? key : offer.editor] ?? "",
      choices: projectChoices(offer, key).filter(
        (entry) => !inPlay.some((had) => had.raw === entry.raw),
      ),
    },
  ];
  if (!offer.carried.some((carried) => carried.required)) {
    listed.push({
      id: "nothing",
      title: "State nothing",
      choices: [{ id: "nothing:", raw: null, label: NOTHING, detail: "" }],
    });
  }
  const wanted = typed.toLowerCase();
  const sections = listed
    .map((section) => ({
      ...section,
      choices: section.choices.filter((entry) => entry.label.toLowerCase().includes(wanted)),
    }))
    .filter((section) => section.choices.length > 0);
  const exact = sections.some((section) => section.choices.some((entry) => entry.label === typed));
  const asTyped = typedRaw(key, typed);
  if (!exact && asTyped !== null) {
    sections.push({
      id: "typed",
      title: "As typed",
      choices: [{ id: `typed:${typed}`, raw: asTyped, label: typed, detail: "" }],
    });
  }
  return sections;
}

/** What the project itself offers for the key, beside what is already in play. */
function projectChoices(offer: VariableKeyOffer, key: string): ValueChoice[] {
  if (offer.editor === "volatile") {
    return ["true", "false"].map((raw) => choice("project", key, raw, ""));
  }
  return offer.choices.map((name) => choice("project", key, JSON.stringify(name), ""));
}

function choice(
  section: ValueSection["id"],
  key: string,
  raw: string,
  detail: string,
): ValueChoice {
  return { id: `${section}:${raw}`, raw, label: shortValue(key, raw), detail };
}

function who(components: readonly string[], producer: boolean): string {
  const listed = components.join(", ");
  return producer ? `${listed} · the producer` : listed;
}

/** The json text a text typed into the field travels as, or `null` when the key takes none.
 *
 * A size may be any whole number, so one typed is taken as it stands. Everything else names
 * something the project declares, and a name it does not declare is not offered: the list is
 * the answer to "what may this be", and a typed one would be a reference to nothing.
 */
function typedRaw(key: string, typed: string): string | null {
  return key === "size" && /^[1-9][0-9]*$/.test(typed) ? typed : null;
}

/**
 * What Enter chooses from the text in the field: the value of an entry whose label spells it
 * exactly, else what the text itself may be taken as, else nothing at all (`undefined`), which
 * leaves the chooser as it was.
 */
export function enteredValue(
  sections: readonly ValueSection[],
  key: string,
  text: string,
): string | null | undefined {
  if (text.trim() === "") return undefined;
  for (const section of sections) {
    for (const entry of section.choices) {
      if (entry.label === text) return entry.raw;
    }
  }
  return typedRaw(key, text) ?? undefined;
}

/** The two fields of a range, read from what is stated. */
export function limitsOf(raw: string | null): { min: string; max: string } {
  if (raw === null) return { min: "", max: "" };
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return { min: "", max: "" };
  }
  const fields = (value ?? {}) as Record<string, unknown>;
  return { min: numberText(fields.min), max: numberText(fields.max) };
}

function numberText(value: unknown): string {
  return typeof value === "number" ? String(value) : "";
}

/** The json text a range typed into the two fields travels as; `null` while it is not one.
 *
 * A range is two numbers with the maximum at least the minimum (spec 5.2), which is what
 * `Limits` itself allows: a pair the models refuse would be written into every declaration
 * and stop each of those files loading, so it never becomes a value to settle on.
 */
export function limitsRaw(min: string, max: string): string | null {
  const low = numberOf(min);
  const high = numberOf(max);
  if (low === null || high === null || high < low) return null;
  return `{ "min": ${low}, "max": ${high} }`;
}

/** What the chooser says is wrong with the two fields, or `null` while they say something the
 * panel can settle on.
 *
 * Two empty fields are not wrong: they are "state nothing", which the list offers as well and
 * which removes the key. Anything else that is not a range is nothing to apply, and saying so
 * is the whole of what the panel does about it - no Apply, and no preview behind it.
 */
export function limitsNote(min: string, max: string): string | null {
  if (min.trim() === "" && max.trim() === "") return null;
  const low = numberOf(min);
  const high = numberOf(max);
  if (low === null || high === null) return "A range needs a minimum and a maximum";
  return high < low ? "The maximum is below the minimum" : null;
}

/** The number a field holds, or `null` where it holds none: empty, or not a number at all. */
function numberOf(text: string): number | null {
  const value = Number(text);
  return text.trim() === "" || Number.isNaN(value) ? null : value;
}
