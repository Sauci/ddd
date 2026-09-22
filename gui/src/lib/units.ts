import type {
  Changes,
  Hunk,
  PlannedChange,
  SettleReply,
  UnitsReply,
  VariableDeclaration,
} from "../api/types";

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

const NO_UNIT = "no unit";

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

/** Every section the picker lists, narrowed to what was typed, in the order spec 5.3 gives. */
export function pickerSections(
  name: string,
  declarations: readonly VariableDeclaration[],
  units: UnitsReply,
  typed: string,
): UnitSection[] {
  const declared = declaredUnits(declarations);
  const listed: UnitSection[] = [
    {
      id: "declared",
      title: `Declared for ${name}`,
      choices: [...declared].map(([unit, who]) => choice("declared", unit, who.join(", "))),
    },
    units.vocabulary === null
      ? {
          id: "used",
          title: "Other units in this project",
          choices: units.used
            .filter((used) => !declared.has(used.unit))
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

/** Whether a project that declares a vocabulary leaves this unit out of it. */
export function outsideVocabulary(units: UnitsReply, unit: string | null): boolean {
  return (
    unit !== null &&
    units.vocabulary !== null &&
    !units.vocabulary.some((entry) => entry.unit === unit)
  );
}

/** The json text a chosen unit travels as, or `null` for no unit: the key then goes. */
export function rawOf(unit: string | null): string | null {
  return unit === null ? null : JSON.stringify(unit);
}

/** What a preview changes, in one sentence naming the files. */
export function consequence(changes: readonly PlannedChange[]): string {
  if (changes.length === 0) return "Nothing to change";
  const files = changes.map((change) => baseName(change.file));
  return `Changes ${files.length} file${files.length === 1 ? "" : "s"}: ${files.join(", ")}`;
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
 * of it would offer; `null` when there is nothing to change. */
export function editOf(preview: SettleReply, label: string): Changes | null {
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
function declaredUnits(declarations: readonly VariableDeclaration[]): Map<string | null, string[]> {
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
