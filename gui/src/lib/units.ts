import type {
  Changes,
  Hunk,
  PlannedChange,
  PlanReply,
  SettleReply,
  UnitsReply,
  VariableDeclaration,
} from "../api/types";
import { toldApartAll } from "./paths";

/** One unit the picker offers: its section, the unit it sets, and what the list says of it. */
export interface UnitChoice {
  /** Unique across the whole list: the section, then the unit. */
  id: string;
  /** The unit choosing it sets, or `null` for no unit. */
  unit: string | null;
  label: string;
  detail: string;
}

export interface UnitSection {
  id: "declared" | "vocabulary" | "used" | "none" | "typed";
  title: string;
  choices: UnitChoice[];
}

/** One line of a hunk as Show changes prints it, keyed by where it stands in its file. */
export interface HunkLine {
  key: string;
  sign: "-" | "+";
  text: string;
}

export const NO_UNIT = "no unit";

/** The string a json text spells, or `null`: absent, empty, not json, or not a string at all. */
export function textOf(raw: string | undefined): string | null {
  if (raw === undefined) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  return typeof value === "string" && value !== "" ? value : null;
}

/** The unit a declaration has: the one it states, or the one its declared type fixes. */
export function unitOfDeclaration(declaration: VariableDeclaration): string | null {
  return textOf(declaration.stated.unit ?? declaration.fixed.unit);
}

/** Who the variable belongs to: its producer, else the first declaration listed. */
function owner(declarations: readonly VariableDeclaration[]): VariableDeclaration | undefined {
  return declarations.find((entry) => entry.role === "produces") ?? declarations[0];
}

/** The picker's sections: what already states this thing, then the project's vocabulary or the
 * units it uses, then what was typed. `inPlay` is unit -> who states it, the owner's own first. */
export function pickerSections(
  owner: string,
  inPlay: ReadonlyMap<string | null, string[]>,
  units: UnitsReply,
  typed: string,
): UnitSection[] {
  const listed: UnitSection[] = [
    {
      id: "declared",
      title: `Declared for ${owner}`,
      choices: [...inPlay].map(([unit, who]) => choice("declared", unit, who.join(", "))),
    },
    units.vocabulary === null
      ? {
          id: "used",
          title: "Other units in this project",
          choices: units.used
            .filter((used) => !inPlay.has(used.unit))
            .map((used) => choice("used", used.unit, variables(used.variables))),
        }
      : {
          id: "vocabulary",
          title: "This project's units",
          choices: units.vocabulary.map((entry) =>
            choice(
              "vocabulary",
              entry.unit,
              detailOf(
                entry.description,
                units.used.find((used) => used.unit === entry.unit),
              ),
            ),
          ),
        },
    { id: "none", title: "No unit", choices: [choice("none", null, "")] },
  ];
  const wanted = typed.toLowerCase();
  const sections = listed
    .map((section) => ({
      ...section,
      choices: section.choices.filter((entry) => entry.label.toLowerCase().includes(wanted)),
    }))
    .filter((section) => section.choices.length > 0);
  // A match on the label of a no-unit choice counts as exact too: what was typed cannot equal
  // `null` itself, so without this a reader who picks "no unit" - whose label, not its `null`
  // unit, comes back through the field once React Aria commits the selection - would be offered
  // "As typed: no unit", which would write that literal text as the unit instead of clearing it.
  const exact = sections.some((section) =>
    section.choices.some(
      (entry) => entry.unit === typed || (entry.unit === null && entry.label === typed),
    ),
  );
  if (typed !== "" && !exact) {
    const note = outsideVocabulary(units, typed) ? "not one of this project's units" : "";
    sections.push({ id: "typed", title: "As typed", choices: [choice("typed", typed, note)] });
  }
  return sections;
}

/** What the picker's field reads for a unit while nothing is being typed: the No unit entry's
 * label for no unit, so that the field always names what the consequence line is about. */
export function unitLabel(unit: string | null): string {
  return unit ?? NO_UNIT;
}

/**
 * What Enter chooses when no entry of the list is focused, from the text in the field: the unit
 * of an entry spelling the text exactly; else no unit (`null`), when the text is the No unit
 * entry's label; else the text exactly as typed, as its As typed entry would take it - so a
 * unit someone did spell "no unit" is still that unit. `undefined` for a field left empty or
 * blank, which chooses nothing.
 *
 * `sections` is the list the text was typed over, narrowed by that text or not narrowed at all:
 * either way it holds every entry spelling the text, which is all this reads it for.
 */
export function enteredUnit(
  sections: readonly UnitSection[],
  text: string,
): string | null | undefined {
  if (text.trim() === "") return undefined;
  if (sections.some((section) => section.choices.some((entry) => entry.unit === text))) {
    return text;
  }
  return text === NO_UNIT ? null : text;
}

/** Whether a project with a units file - whatever it lists - leaves this unit out of its
 * vocabulary. */
export function outsideVocabulary(units: UnitsReply, unit: string | null): boolean {
  return (
    unit !== null &&
    units.vocabulary !== null &&
    !units.vocabulary.some((entry) => entry.unit === unit)
  );
}

/** The white space python's `str.strip` takes off a text, by code point - what the Units tab judges
 * a spelling by on the server (`ddd.lsp.units`): JavaScript's `trim` takes off a byte order mark
 * python keeps, and keeps the four information separators and the next-line python takes off. */
const STRIPPED: ReadonlySet<number> = new Set([
  0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680, 0x2000, 0x2001,
  0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a, 0x2028, 0x2029, 0x202f,
  0x205f, 0x3000,
]);

/** Whether `text` begins or ends with white space python strips (`STRIPPED`). */
function spaced(text: string): boolean {
  return (
    STRIPPED.has(text.codePointAt(0) ?? -1) || STRIPPED.has(text.codePointAt(text.length - 1) ?? -1)
  );
}

/** Why a unit chosen for a variable or a type is refused, in the words the Units tab refuses a
 * spelling with, or `null`: spaces around a unit are a slip of the keyboard rather than part of
 * its spelling, and written they made the project hold two spellings of one unit, which no finding
 * said without a units file (15:M10). No unit at all is none to refuse. */
export function unitRefusal(unit: string | null): string | null {
  return unit !== null && spaced(unit) ? `'${unit}' has spaces around it` : null;
}

/** The json text a chosen unit travels as, or `null` for no unit: the key then goes. */
export function rawOf(unit: string | null): string | null {
  return unit === null ? null : JSON.stringify(unit);
}

/** How many files a consequence names before it counts the rest. A rename of a unit every
 * component states changes every file of the project: named one by one, the sentence ran to a
 * wall of names, with Apply below it. */
export const FILES_NAMED = 3;

/** What a preview changes, in one sentence: how many files, then their names - three of them and
 * a count of the rest past four, since a count standing for one file is no shorter than its name.
 * Its counts are written as the Apply under it writes its own, so that the two read alike. */
export function consequence(changes: readonly PlannedChange[]): string {
  if (changes.length === 0) return "Nothing to change";
  const files = changedNames(changes);
  const named =
    files.length <= FILES_NAMED + 1
      ? files.join(", ")
      : `${files.slice(0, FILES_NAMED).join(", ")} and ${files.length - FILES_NAMED} more`;
  return `Changes ${files.length} file${files.length === 1 ? "" : "s"}: ${named}`;
}

/** What every settlement says after what it changes, in the words the server's fix titles end in
 * (`CODE_NOT_TOUCHED`, ddd.finding_fixes): the descriptions agree once it is applied, and the code
 * that reads the variable keeps the scale it was written with. */
export const CODE_NOT_TOUCHED = " (the code of the readers is not touched)";

/** What a settle's preview says: the consequence a preview always says, and that the readers' code
 * is not touched - as the quick fix's own title says it, which the server writes. Nothing more
 * than the consequence where there is nothing to change. */
export function settleConsequence(changes: readonly PlannedChange[]): string {
  return changes.length === 0 ? consequence(changes) : `${consequence(changes)}${CODE_NOT_TOUCHED}`;
}

/** The names a change gives the files it writes, in its order: the one place they are made, all of
 * them, before `consequence` keeps the first few - each by its own name, and two files of one name
 * in different folders by as much of their paths as tells them apart (`toldApartAll`), among every
 * file the change writes (16:M15). Counted in one pass: a rename of a unit stated in a project's
 * every file changes thousands. */
export function changedNames(changes: readonly { file: string }[]): string[] {
  return toldApartAll(changes.map((change) => change.file));
}

/** What a panel says in place of a plan's consequence while the plan is asked for and has not come
 * (`planning`): a rename of the unit stated in the most files takes seconds to plan on a large
 * project - the reference page measures 1.2 to 4.1 s - and the panel looked meanwhile as it had
 * before it was asked. */
export const PLANNING = "Planning…";

/** Whether a panel says `PLANNING` where an offer's consequence stands: its plan is pending - asked
 * for, or about to be once the reader's typing pauses (`planShown`, lib/typing.ts) - and neither
 * the plan nor why it was refused has come. */
export function planning(offer: {
  plan: unknown;
  refusal: string | null;
  pending: boolean;
}): boolean {
  return offer.pending && offer.plan === null && offer.refusal === null;
}

/** What a settlement's plan says of the files it would leave unable to load, as the panel draws it
 * beside the plan, before Apply: the server's own sentences, in its words and its order. The
 * reader chose the value, so they warn and stand in no way of applying it. Nothing for no plan, and
 * nothing while the panel says why the plan cannot be applied instead of drawing it. */
export function unloadableOf(
  preview: SettleReply | null,
  refusal: string | null,
): readonly string[] {
  return preview === null || refusal !== null ? [] : preview.unloadable;
}

/** `sentences` each with a key of its own: the words, and for a sentence the list holds again, how
 * many of its words came before it. The server's sentences name the file by its name, so two files
 * of one name say the same words; a list keyed by its words alone drew one of the two under a key
 * the other had. */
export function sentenceKeys(
  sentences: readonly string[],
): readonly { key: string; text: string }[] {
  const seen = new Map<string, number>();
  return sentences.map((text) => {
    const before = seen.get(text) ?? 0;
    seen.set(text, before + 1);
    return { key: `${before} ${text}`, text };
  });
}

/** One file's lines as `Changes` prints them: what it changes, and the word standing where its
 * line number would when it has none of its own - a file that is about to appear or go. */
export interface ShownChange {
  file: string;
  hunks: readonly Hunk[];
  note: string | null;
}

/** A preview's changes as `Changes` prints them: a file the change creates has no line of its
 * own yet, and is named as new. */
export function shownChanges(changes: readonly PlannedChange[]): ShownChange[] {
  return changes.map(({ file, fingerprint, hunks }) => ({
    file,
    hunks,
    note: fingerprint === null ? "new" : null,
  }));
}

/** A file's own name, from the absolute posix path the api speaks. */
export function baseName(file: string): string {
  return file.slice(file.lastIndexOf("/") + 1);
}

/** A hunk's lines taken out, then its lines put in, each keyed by where it stands. */
export function hunkLines(hunk: Hunk): HunkLine[] {
  return [
    ...hunk.before.map((text, offset) => ({
      key: `-${hunk.line + offset}`,
      sign: "-" as const,
      text,
    })),
    ...hunk.after.map((text, offset) => ({
      key: `+${hunk.line + offset}`,
      sign: "+" as const,
      text,
    })),
  ];
}

/** The edit a preview comes to, exactly as `POST /api/edit` takes it, under the label an undo
 * of it would offer; `null` when there is nothing to change. A settlement's preview and a plan's
 * come to their edit the same way: only their `changes` are read. */
export function editOf(preview: SettleReply | PlanReply, label: string): Changes | null {
  const changes = nonEmpty(
    preview.changes.flatMap(({ file, fingerprint, operations }) => {
      const made = nonEmpty(operations);
      return made === null ? [] : [{ file, fingerprint, operations: made }];
    }),
  );
  return changes === null ? null : { changes, label };
}

function nonEmpty<T>(items: readonly T[]): [T, ...T[]] | null {
  const [first, ...rest] = items;
  return first === undefined ? null : [first, ...rest];
}

/** Each unit the declarations have, the owner's first, with the components having it. */
export function declaredUnits(
  declarations: readonly VariableDeclaration[],
): Map<string | null, string[]> {
  const first = owner(declarations);
  const ordered = first === undefined ? [] : [first, ...declarations.filter((d) => d !== first)];
  const units = new Map<string | null, string[]>();
  for (const declaration of ordered) {
    const unit = unitOfDeclaration(declaration);
    units.set(unit, [...(units.get(unit) ?? []), declaration.component]);
  }
  return units;
}

function choice(section: UnitSection["id"], unit: string | null, detail: string): UnitChoice {
  return { id: `${section}:${unit ?? ""}`, unit, label: unitLabel(unit), detail };
}

function variables(count: number): string {
  return `${count} variable${count === 1 ? "" : "s"}`;
}

function detailOf(description: string | null, used: { variables: number } | undefined): string {
  return [description, used === undefined ? null : variables(used.variables)]
    .filter((part) => part !== null)
    .join(" · ");
}
