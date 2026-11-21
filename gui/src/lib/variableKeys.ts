import type {
  SettleReply,
  VariableDeclaration,
  VariableKeyOffer,
  VariableReply,
} from "../api/types";
import { type CommaMeaning, decimalText, readNumber, spelledNumber, typedComma } from "./numbers";
import { boundRead, wholePast } from "./objectValues";
import { hrefOf } from "./route";
import { unsettledNote } from "./typing";
import { textOf, unitRefusal } from "./units";

/** One entry of a `dimensions` value: the text it reads as, and - for a name - the constant it
 * opens. `constant` and `href` are `null` together, exactly as `KeyCell`'s own `from`/`href` are:
 * a literal number names nothing to open (spec 5.3). */
export interface DimensionEntry {
  text: string;
  constant: string | null;
  href: string | null;
}

/** What one declaration's cell of a row reads. */
export interface KeyCell {
  /** The value as a reader reads it, `none` where nothing is stated, or why there is no cell. */
  text: string;
  /** Drawn quiet: nothing is stated here, or this kind has no such key. */
  quiet: boolean;
  /** The declared type the value comes from, which the cell names after it. */
  from: string | null;
  /** Where `from`'s type opens, paired with it exactly as `label` pairs with `href` in
   * `FindingPanelView`: `null` together with `from`. */
  href: string | null;
  /** The preview writes this key into this declaration. */
  changing: boolean;
  /** `text` split into one part per entry of a `dimensions` value, a name among them a link of
   * its own (spec 5.3) - `null` for every other key, and for a `dimensions` cell whose raw text
   * is not a json array. `VariableKeysTable` draws these in place of `text` when they are given,
   * since a `dimensions` value joined into one string, the way `text` reads it, has nowhere to
   * hang a second entry's own link. */
  parts: readonly DimensionEntry[] | null;
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
      href: null,
      changing: false,
      parts: null,
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
      href: null,
      changing,
      parts: null,
    };
  }
  const stated = declaration.stated[offer.key];
  const fixed = declaration.fixed[offer.key];
  const raw = stated ?? fixed;
  if (raw === undefined) {
    return { text: "none", quiet: true, from: null, href: null, changing, parts: null };
  }
  const from = stated === undefined ? declaration.type : null;
  return {
    text: shortValue(offer.key, raw),
    quiet: false,
    from,
    href: from === null ? null : hrefOf({ page: "project", view: "types", type: from }),
    changing,
    // Redundant today with dimensionEntries's own `Array.isArray` check: no key in KEY_ORDER
    // other than `dimensions` is ever array-shaped, so calling it unconditionally would answer
    // `null` for every one of them anyway. Kept explicit rather than relying on that, because
    // whether an array of constant links belongs on a key is this table's own decision - a
    // future key that happens to be array-shaped too should not start rendering them merely
    // because its raw text happens to parse the same way `dimensions`'s does.
    parts: offer.key === "dimensions" ? dimensionEntries(raw) : null,
  };
}

/** `raw`'s own entries, each a literal number's text or a name paired with where it opens - `null`
 * where `raw` is not a json array, which leaves `text` to show it whole (spec 5.3: a dimension is
 * the one key naming a constant that this table draws, `dimensions` on a variable's declaration -
 * `_DIMENSION_KEY`'s other two places, a declaration's `size` and a structure member's own
 * `dimensions`, are neither this table's row). */
function dimensionEntries(raw: string): readonly DimensionEntry[] | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!Array.isArray(value)) return null;
  return value.map((entry) =>
    typeof entry === "string"
      ? {
          text: entry,
          constant: entry,
          href: hrefOf({ page: "project", view: "shared", kind: "constant", name: entry }),
        }
      : { text: String(entry), constant: null, href: null },
  );
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
  if (key === "limits") {
    const texts = boundTexts(raw);
    return `${boundOf(fields.min, texts.get("min"))} … ${boundOf(fields.max, texts.get("max"))}`;
  }
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
    const factor = `×${String(fields.factor ?? 1)}`;
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
  return typeof value === "number" && value > 0 ? `+${value}` : String(value);
}

/** A range's bound in the key's row and its chooser, shown as its field shows it
 * (`shownBound`). */
function boundOf(value: unknown, text: string | undefined): string {
  return value === undefined ? "?" : shownBound(value, text);
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

/** The json text a key's chooser has settled on: the reader's pick once they have made one, and
 * the value it starts on (`startingRaw`) until then.
 *
 * `chosen` is a tri-state, `undefined` until a pick: a pick of nothing ("state nothing", "no
 * unit") is a pick, `null`, and stays `null` - only `undefined` gives way to `starting`. Reading
 * `chosen ?? starting` took it for no pick at all, so that a type's "no unit" went back to the
 * unit it started on: the field read it again, and Apply left it in the file. */
export function settledRaw(
  chosen: string | null | undefined,
  starting: string | null,
): string | null {
  return chosen === undefined ? starting : chosen;
}

/** What a panel holds of the reader's own work on one key: the value they picked, the text they
 * typed into its field, the two fields of a range (and whether they were typed into, rather than
 * a range picked from the list), and whether the diff is open. */
export interface Choice {
  chosen: string | null | undefined;
  typed: string | undefined;
  range: { min: string; max: string; typed: boolean } | undefined;
  changesShown: boolean;
}

/** Nothing chosen, typed or opened: where every row starts. */
export const FRESH: Choice = {
  chosen: undefined,
  typed: undefined,
  range: undefined,
  changesShown: false,
};

/** A `Choice` with the key it was made for. A panel moves by itself from one key to the next - the
 * first that disagrees, once the last is settled - and a row opened by itself starts on the
 * producer's value, so what was held for another key is never read, and is let go by
 * `staleHold` the moment the key on screen is not its own: a later return to that key, by an
 * undo or an outside edit, starts afresh too. */
export interface Held {
  key: string;
  value: Choice;
}

/** What is held for `selected`: the choice made for it, else `FRESH`. */
export function heldFor(held: Held | undefined, selected: string | undefined): Choice {
  return held !== undefined && held.key === selected ? held.value : FRESH;
}

/** Whether what is held was made for a key other than the one on screen (none included), and so
 * is to be let go. */
export function staleHold(held: Held | undefined, selected: string | undefined): boolean {
  return held !== undefined && held.key !== selected;
}

/** What is held after `patch` is made on `selected`: the choice held for it with `patch`
 * laid over, or over `FRESH` when nothing - or another key's - is held. Nothing is held for no
 * key. */
export function holdOn(
  held: Held | undefined,
  selected: string | undefined,
  patch: Partial<Choice>,
): Held | undefined {
  if (selected === undefined) return undefined;
  return { key: selected, value: { ...heldFor(held, selected), ...patch } };
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

/** A name a constant, a type or a measurement may have: what the field reads as a name rather
 * than as a number. */
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

/** A size typed, read as a number (`numbers.ts`): the whole number of at least 1 it spells, or the
 * sentence a spelling in another notation, or a comma that could be either, is refused with - or
 * `null` for a name, which the list offers, and for a number that is no size. */
function sizeOf(typed: string): { raw: string } | { refusal: string } | null {
  if (IDENTIFIER.test(typed.trim())) return null;
  const read = readNumber(typed);
  if (!("decimal" in read)) return { refusal: read.refusal };
  const { negative, digits, exponent } = read.decimal;
  return !negative && digits !== "" && exponent >= 0 ? { raw: decimalText(read.decimal) } : null;
}

/** The json text a text typed into the field travels as, or `null` when the key takes none.
 *
 * A size may be any whole number, so one typed is taken as it stands, read as every field reads a
 * number (`sizeOf`). Everything else names something the project declares, and a name it does not
 * declare is not offered: the list is the answer to "what may this be", and a typed one would be
 * a reference to nothing.
 */
function typedRaw(key: string, typed: string): string | null {
  if (key !== "size") return null;
  const size = sizeOf(typed);
  return size !== null && "raw" in size ? size.raw : null;
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

/** The chooser's note while its text is not the value settled on, `undefined` while it is: why a
 * size typed in another notation is no number - in the sentence every field refuses one with - and
 * otherwise the way out of the text (`unsettledNote`). */
export function chooserNote(
  isUnsettled: boolean,
  key: string,
  typed: string,
  sections: readonly ValueSection[],
): string | undefined {
  const size = isUnsettled && key === "size" ? sizeOf(typed) : null;
  if (size !== null && "refusal" in size) return size.refusal;
  return unsettledNote(isUnsettled, typed, sections, (listed, text) =>
    enteredValue(listed, key, text),
  );
}

/** The two fields of a range, read from what is stated: each bound as the double `JSON.parse`
 * reads, but a whole number past 2^53 in its own digits (`shownBound`). */
export function limitsOf(raw: string | null): { min: string; max: string } {
  if (raw === null) return { min: "", max: "" };
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return { min: "", max: "" };
  }
  const fields = (value ?? {}) as Record<string, unknown>;
  const texts = boundTexts(raw);
  return {
    min: numberText(fields.min, texts.get("min")),
    max: numberText(fields.max, texts.get("max")),
  };
}

/** How many characters wide each of a range's two fields is drawn: as many as its own text holds,
 * as a cell of the values grid is as wide as its column's text (`gridTexts`). A field of a fixed
 * width cut a bound short with no sign of it - Max's 18446744073709551615 read 1844674 - and a
 * long one widens its own field and leaves the other as narrow as its own. ui.css keeps the
 * width each had as the least. */
export function rangeChars(range: { min: string; max: string }): { min: number; max: number } {
  return { min: range.min.length, max: range.max.length };
}

function numberText(value: unknown, text: string | undefined): string {
  return typeof value === "number" ? shownBound(value, text) : "";
}

/** Each bound of a stated range as its file spells it, before `JSON.parse` reads it as a double:
 * the last one written of each, as `JSON.parse` takes the last. */
const BOUND = /"(min|max)"\s*:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

function boundTexts(raw: string): Map<string, string> {
  const texts = new Map<string, string>();
  for (const [, bound = "", text = ""] of raw.matchAll(BOUND)) texts.set(bound, text);
  return texts;
}

/** A stated bound as the page shows it: the double `JSON.parse` read it as - which is the
 * number, for a fraction or anything short of 2^53 - but a whole number past 2^53 in its own
 * digits, where the double reads as another: `18446744073709551615`, the most a uint64 holds, as
 * `18446744073709552000`, which none holds. Its field then holds those digits, and a range made
 * of them is refused (`limitsNote`) rather than sent back as the double. */
function shownBound(value: unknown, text: string | undefined): string {
  return text !== undefined && wholePast(text) !== null ? text : String(value);
}

/** The datatype a range is read by, of the datatypes the declarations it is written into state: a
 * whole one where any states one, whose rule is the stricter, else a float - and a whole one's
 * rule, `""`, where none states any. */
export function rangeDatatype(datatypes: readonly (string | null)[]): string {
  const stated = datatypes.filter((datatype) => datatype !== null);
  return stated.find((datatype) => !datatype.startsWith("float")) ?? stated[0] ?? "";
}

/** The datatype a variable's range is read by: its declarations' (`rangeDatatype`), each the one it
 * states or its type fixes. */
export function variableDatatype(variable: VariableReply): string {
  return rangeDatatype(
    variable.declarations.map((declaration) =>
      textOf(declaration.stated.datatype ?? declaration.fixed.datatype),
    ),
  );
}

/** The datatype a type's range is read by: the one it fixes. */
export function typeDatatype(keys: readonly VariableKeyOffer[]): string {
  return rangeDatatype([textOf(keys.find((key) => key.key === "datatype")?.values[0]?.raw)]);
}

/** A bound as a range's json writes it: in the digits typed, as `jsonNumber` spells a number
 * field's (3:I1) - where it was the shortest spelling of the double the page weighed it as - and a
 * float's as a float (task 1's n2), given a point where it was typed whole: a float64's bound typed
 * `10000000000000000000` was a whole number past 2^53, which a float holds as no other. */
function boundText(json: string, datatype: string): string {
  return datatype.startsWith("float") && !/[.e]/.test(json) ? `${json}.0` : json;
}

/** What a key's chooser field reads while nothing is being typed into it (decision 15.3), by one
 * rule for the variable's panel and the type's, where each spelled it out for itself in the screen
 * (fix round 1, M8): nothing while no key is selected, or while the two fields make no range
 * (`broken`) - they show what was typed themselves; a range they make, as the range it comes to
 * (`target`); any other key as the value the chooser settled on (`chosen`), a unit refused for its
 * spaces among them, the note under the field saying why. `label` is the panel's own spelling of
 * a key's value. */
export function settledLabel(
  selected: string | undefined,
  broken: string | null,
  target: string | null,
  chosen: string | null,
  label: (key: string, raw: string | null) => string,
): string {
  if (selected === undefined || (broken !== null && selected === "limits")) return "";
  return label(selected, selected === "limits" ? target : chosen);
}

/** What is wrong with the value a key's chooser would settle on, said under the field in place of
 * a plan, or `null` where nothing is: a range the two fields do not make (`limitsNote`), read by
 * `datatype`; and a unit with spaces around it (`unitRefusal`), `raw` the json text chosen. */
export function settleNote(
  key: string | undefined,
  range: { min: string; max: string },
  datatype: string,
  raw: string | null,
): string | null {
  if (key === "limits") return limitsNote(range.min, range.max, datatype);
  if (key === "unit") return unitRefusal(textOf(raw ?? undefined));
  return null;
}

/** The json text a range typed into the two fields travels as; `null` while it is not one.
 *
 * A range is two numbers with the maximum at least the minimum (spec 5.2), which is what
 * `Limits` itself allows: a pair the models refuse would be written into every declaration
 * and stop each of those files loading, so it never becomes a value to settle on. `datatype` is
 * what it is read by (`rangeDatatype`). Each bound travels as the text typed (`boundText`),
 * weighed first as the double the page holds of it, which is not what is sent.
 */
export function limitsRaw(min: string, max: string, datatype = ""): string | null {
  const range = rangeOf(min, max, datatype);
  if (range === null || "note" in range) return null;
  const { low, high } = range;
  return `{ "min": ${boundText(low.json, datatype)}, "max": ${boundText(high.json, datatype)} }`;
}

/** What the chooser says is wrong with the two fields, or `null` while they say something the
 * panel can settle on (`rangeOf`). */
export function limitsNote(min: string, max: string, datatype = ""): string | null {
  const range = rangeOf(min, max, datatype);
  return range !== null && "note" in range ? range.note : null;
}

/**
 * The range the two fields say, the sentence saying what is wrong with them, or `null` for two
 * empty fields.
 *
 * Two empty fields are not wrong: they are "state nothing", which the list offers as well and
 * which removes the key. Anything else that is not a range is nothing to apply, and saying so
 * is the whole of what the panel does about it - no Apply, and no preview behind it. Each sentence
 * but the last names the one field it is about (`fieldBound`); the two are read together, so that
 * a comma one shows to be a decimal point is one in the other too.
 */
function rangeOf(
  min: string,
  max: string,
  datatype: string,
): { note: string } | { low: Bound; high: Bound } | null {
  if (min.trim() === "" && max.trim() === "") return null;
  const meaning = typedComma([min, max]);
  const low = fieldBound("Min", min, meaning, datatype);
  if ("note" in low) return low;
  const high = fieldBound("Max", max, meaning, datatype);
  if ("note" in high) return high;
  if (high.value < low.value) return { note: "The maximum is below the minimum" };
  return { low, high };
}

/** One bound of a range: the double the page weighs it as, and the json text it is sent as, the
 * digits typed (`spelledNumber`). */
interface Bound {
  value: number;
  json: string;
}

/** The number one of the two fields holds, read as every field reads one (`numbers.ts`) and
 * weighed as a cell of `datatype` weighs one (`boundRead`), or what is wrong with it, in a sentence
 * naming the field: empty, a number in another notation, a comma that could be either, no number
 * at all, or a number the page cannot send as typed. */
function fieldBound(
  field: "Min" | "Max",
  text: string,
  meaning: CommaMeaning | undefined,
  datatype: string,
): { note: string } | Bound {
  if (text.trim() === "") return { note: `${field} is empty` };
  const read = spelledNumber(text, meaning);
  if (!("decimal" in read)) return { note: `${field}: ${read.refusal}` };
  const bound = boundRead(read.decimal, text, datatype);
  if ("refusal" in bound) return { note: `${field}: ${bound.refusal}` };
  return { value: bound.value, json: read.json };
}
