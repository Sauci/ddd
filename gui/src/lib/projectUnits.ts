import type {
  Changes,
  PlanReply,
  ProjectUnit,
  UnitPlace,
  UnitReply,
  UnitsReply,
} from "../api/types";
import { baseName, consequence, editOf, outsideVocabulary, type UnitSection } from "./units";

/** The file adoption writes beside the project description (`ddd.lsp.units.ADOPTED`). */
const ADOPTED = "units.ddd.json";

const OUTSIDE = "not in the vocabulary";

/** The Units tab's rows in the order spec 5.1 gives: units with findings first, then the most
 * stated, then by spelling - code unit by code unit, as Python sorts them, so `RPM` comes before
 * `rpm` on every machine whatever its locale. A vocabulary entry nothing states is stated by
 * nothing, and so comes last among its kind. */
export function unitRows(units: readonly ProjectUnit[]): ProjectUnit[] {
  return [...units].sort(
    (a, b) =>
      Number(b.findings > 0) - Number(a.findings > 0) ||
      stated(b) - stated(a) ||
      spelling(a.unit, b.unit),
  );
}

/** The table's Stated by column: "2 variables", "1 variable, 1 type", or "unused" for a
 * vocabulary entry nothing states. */
export function statedBy(unit: ProjectUnit): string {
  const parts = [
    counted(unit.variables, "variable"),
    counted(unit.types, "type"),
    counted(unit.members, "member"),
  ].filter((part) => part !== null);
  return parts.length === 0 ? "unused" : parts.join(", ");
}

/** The table's Description column: the vocabulary's description, "not in the vocabulary"
 * outside it, and nothing at all for a project with no units file, where every unit is free. */
export function descriptionOf(unit: ProjectUnit, hasVocabulary: boolean): string {
  if (!hasVocabulary) return "";
  return unit.files.length === 0 ? OUTSIDE : (unit.description ?? "");
}

/**
 * The check a unit's findings are filed by, for its chip in the table; `null` without any.
 *
 * The row carries a count, not the findings: which check they are is read from where the unit
 * stands, since a unit outside the vocabulary can only be unknown and one inside it can only be
 * listed twice.
 */
export function findingCheck(unit: ProjectUnit): "unknown-unit" | "duplicate-unit" | null {
  if (unit.findings === 0) return null;
  return unit.files.length === 0 ? "unknown-unit" : "duplicate-unit";
}

/** The line above the table: "9 units · 2 not in the vocabulary", or "8 units · no units file". */
export function tabTitle(units: readonly ProjectUnit[], hasVocabulary: boolean): string {
  const all = plural(units.length, "unit");
  if (!hasVocabulary) return `${all} · no units file`;
  const outside = units.filter((unit) => unit.files.length === 0).length;
  return `${all} · ${outside === 0 ? "all in the vocabulary" : `${outside} ${OUTSIDE}`}`;
}

/** The panel's line under the unit: where the vocabulary lists it, and how many places in how
 * many files state it - "in the vocabulary, units.ddd.json · stated in 2 places, 2 files". A
 * project with no units file has no vocabulary to speak of, and the line says only the places. */
export function unitMeta(unit: ProjectUnit, reply: UnitReply, hasVocabulary: boolean): string {
  const files = new Set(reply.sites.map((site) => site.path)).size;
  const places =
    reply.sites.length === 0
      ? "stated nowhere"
      : `stated in ${plural(reply.sites.length, "place")}, ${plural(files, "file")}`;
  if (!hasVocabulary) return places;
  const listed =
    unit.files.length === 0 ? OUTSIDE : `in the vocabulary, ${unit.files.map(baseName).join(", ")}`;
  return `${listed} · ${places}`;
}

/** What a place stating the unit is, for the panel's What column: a variable's role, or the
 * kind of type. */
export function placeRole(place: UnitPlace): string {
  if (place.kind === "type") return "scalar type";
  if (place.kind === "member") return "structure member";
  return place.role ?? "variable";
}

/** What the unit's state offers beside the rename, which it always offers (spec 5.2): a
 * description for a unit the vocabulary lists, its removal once nothing states it, and its
 * addition for a unit outside a vocabulary the project has. */
export function offers(
  unit: ProjectUnit,
  hasVocabulary: boolean,
): { describe: boolean; add: boolean; remove: boolean } {
  const listed = unit.files.length > 0;
  return { describe: listed, add: hasVocabulary && !listed, remove: listed && stated(unit) === 0 };
}

/**
 * The rename picker's sections: the vocabulary's units first, in the order its files list them,
 * then the other units in use, the most stated first, then the text as typed - the unit itself
 * left out of all three, since renaming it onto itself changes nothing. Narrowed as part 1's
 * picker narrows, by what is typed, regardless of case.
 */
export function renameSections(unit: string, units: UnitsReply, narrow: string): UnitSection[] {
  const others = units.units.filter((row) => row.unit !== unit);
  const order = (units.vocabulary ?? []).map((entry) => entry.unit);
  const listed: UnitSection[] = [
    {
      id: "vocabulary",
      title: "This project's units",
      choices: others
        .filter((row) => row.files.length > 0)
        .sort((a, b) => order.indexOf(a.unit) - order.indexOf(b.unit))
        .map((row) => choice("vocabulary", row.unit, detailOf(row))),
    },
    {
      id: "used",
      title: "Other units in this project",
      choices: others
        .filter((row) => row.files.length === 0)
        .sort((a, b) => stated(b) - stated(a) || spelling(a.unit, b.unit))
        .map((row) => choice("used", row.unit, statedBy(row))),
    },
  ];
  const wanted = narrow.toLowerCase();
  const sections = listed
    .map((section) => ({
      ...section,
      choices: section.choices.filter((entry) => entry.label.toLowerCase().includes(wanted)),
    }))
    .filter((section) => section.choices.length > 0);
  const exact = sections.some((section) => section.choices.some((entry) => entry.unit === narrow));
  if (narrow !== "" && narrow !== unit && !exact) {
    const note = outsideVocabulary(units, narrow) ? "not one of this project's units" : "";
    sections.push({ id: "typed", title: "As typed", choices: [choice("typed", narrow, note)] });
  }
  return sections;
}

/**
 * What a rename changes, and what becomes of the vocabulary (spec 5.2): the files it writes,
 * then - where the project has a vocabulary - that the new spelling is listed already and the
 * two merge, that the unit's own entry is renamed too, or that the new spelling is not one of
 * the project's units.
 */
export function renameConsequence(
  plan: PlanReply,
  from: ProjectUnit,
  to: string,
  units: UnitsReply,
): string {
  const changes = consequence(plan.changes);
  if (units.vocabulary === null) return changes;
  const vocabulary = units.vocabulary.some((entry) => entry.unit === to)
    ? `${to} is in the vocabulary already, so ${from.unit} merges into it`
    : from.files.length > 0
      ? `${from.unit} is renamed in ${from.files.map(baseName).join(", ")} too`
      : "Not one of this project's units";
  return `${changes}. ${vocabulary}.`;
}

/** The adoption banner's sentence (spec 5.3), for a project with no units file. */
export function adoptionSentence(adoptable: number): string {
  const opening = "This project has no units file, so no unit is checked against a vocabulary.";
  if (adoptable === 0) return `${opening} It states no unit, so there is nothing to adopt.`;
  return (
    `${opening} Adopting writes ${ADOPTED} with the ${plural(adoptable, "unit")} in use and ` +
    "includes it in the project: nothing is reported that is not reported today."
  );
}

/** The edit a plan comes to, exactly as `POST /api/edit` takes it - the `null` fingerprint of a
 * file it creates included - or `null` when there is nothing to change. A plan has the shape of
 * part 1's preview, and comes to its edit the same way. */
export function planEdit(plan: PlanReply, label: string): Changes | null {
  return editOf(plan, label);
}

/** How many variables, types and structure members state a unit. */
function stated(unit: ProjectUnit): number {
  return unit.variables + unit.types + unit.members;
}

/** Two spellings compared code unit by code unit, without a branch for the equal pair a table
 * of one row per spelling never holds. */
function spelling(a: string, b: string): number {
  return Number(a > b) - Number(a < b);
}

/** "1 variable", "2 variables". */
function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/** A count of what states a unit, or `null` for none, which the sentence leaves out. */
function counted(count: number, noun: string): string | null {
  return count === 0 ? null : plural(count, noun);
}

/** A vocabulary unit's detail in the picker: its description, then what states it. */
function detailOf(row: ProjectUnit): string {
  return [row.description, statedBy(row)]
    .filter((part) => part !== null && part !== "")
    .join(" · ");
}

function choice(section: UnitSection["id"], unit: string, detail: string) {
  return { id: `${section}:${unit}`, unit, label: unit, detail };
}
