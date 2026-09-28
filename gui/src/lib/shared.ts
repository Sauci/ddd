import type { ConstantPlanRequest, RasterPlanRequest, SectionPlanRequest } from "../api/client";
import type { Changes, PlanReply, RasterUse, SharedEntry, SharedReply } from "../api/types";
import type { SectionAccess } from "../generated/sections";
import { planEdit as editOfPlan } from "./projectUnits";
import type { Route } from "./route";

/** The file kinds the Shared files tab's table draws its rows from: a constant's file, a
 * section's and a raster's, listed together (spec 5.1). `SharedPage` passes this to
 * `lib/findings`'s `unreadable` rather than naming the three kinds itself - `.tsx` is executed by
 * no gate in this repo, so the one fact left saying which vocabularies this tab holds belongs
 * here, where a test can hold it to account, rather than in a screen nothing checks (ruling 7,
 * task 7).
 *
 * Not a `for (const kind of SHARED_KINDS)` inside `tabTitle` below, whose own count is read off
 * each entry's `kind` instead: that function tells a reader what is in a table it already has:
 * this one tells `unreadable` which failed *files* are this tab's business before the table is
 * drawn at all, which a project with an entry-less table (every file of a kind failed) could
 * never answer by looking at `entries` alone. */
export const SHARED_KINDS: readonly string[] = ["constants", "sections", "rasters"];

/** One of the tab's vocabularies, as an address names the selection and as a row's own `kind`
 * spells it: the singular word, where `SHARED_KINDS` above holds the plural its *file* is known
 * by. Read off `Route`'s own shape rather than spelled again here, so the words a page can route
 * to and the words this file judges cannot come to be different sets. */
export type SharedKind = Extract<Route, { view: "shared"; kind: string }>["kind"];

/**
 * The values of a union, as a list something can offer.
 *
 * `Record<T, null>` is what earns this its cast: an object literal has to carry one key per value
 * of `T` and may carry no others, so a value the union gains - a third `SectionAccess` in a
 * regenerated schema, a third vocabulary in `Route` - stops the build here rather than going
 * quietly missing from a chooser, which is the failure a `.tsx` list of literals would ship.
 */
function valuesOf<T extends string>(record: Record<T, null>): readonly T[] {
  return Object.keys(record) as T[];
}

/** The vocabularies the add form's chooser offers, in the order it lists them: constants first,
 * as `ddd.project_shared.HELD` walks them and as `GET /api/shared` sorts the table's own rows. */
export const SHARED_VOCABULARIES = valuesOf<SharedKind>({
  constant: null,
  section: null,
  raster: null,
});

/** The values a section's `access` may take, in the order the panel's chooser offers them - the
 * model's own two (`ddd.models.sections.SectionAccess`), by way of the type generated from its
 * schema. The api judges what arrives against the same enum, so a word typed over the chooser is
 * refused there rather than written; this list is what spares a reader having to guess one. */
export const SECTION_ACCESSES = valuesOf<SectionAccess>({
  "read-write": null,
  "read-only": null,
});

/** Which vocabulary a row belongs to, in the word a reader knows it by: the plural, which is also
 * the word its file kind uses (`SHARED_KINDS`).
 *
 * `Vocabulary` rather than `Kind`, which the Types tab already uses for a different fact - the
 * shape of a type, `scalar` or `external` or `struct`. One header meaning two things on adjacent
 * tabs was cheap to change before sections shipped and would not have been after.
 *
 * All three of the tab's kinds pluralise with a plain `s`. `vocabularyOf` takes a bare `string`,
 * not a `SharedKind`, so it pluralises whatever kind it is handed regardless of whether the page
 * can route to it or open a panel for it - which is what lets a kind's row read correctly in the
 * table while either is still being built. All three vocabularies have both now, so nothing today
 * relies on that; the bare parameter is kept for the fourth, which will be built the same way. A
 * fourth vocabulary that does not pluralise with a plain `s` would need its own answer here. */
export function vocabularyOf(kind: string): string {
  return `${kind}s`;
}

/** Which vocabulary that word names, or `undefined` where it names none of them - what the add
 * form's chooser settles on from the text its field holds, since a combo box takes anything
 * typed. Undefined is the unset chooser: a form that declares nothing yet, never a guess at which
 * vocabulary a half-typed word meant. */
export function kindNamed(word: string): SharedKind | undefined {
  return SHARED_VOCABULARIES.find((kind) => vocabularyOf(kind) === word);
}

/** What the add form is called while the chooser is on that vocabulary, and while it is on none.
 *
 * Every vocabulary the tab holds takes "a" - constant, section, raster - so the article is fixed
 * here rather than chosen per word, as `ddd.shared_plans._article` has to choose it server-side
 * for sentences that also name an `entry`. "Declare a constant" is the name `e2e/constants.spec.
 * ts` finds this form by, and the name part 13's own button gave it. */
export function addTitle(kind: SharedKind | undefined): string {
  return kind === undefined ? "Declare an entry" : `Declare a ${kind}`;
}

/** The line above the table: one count per vocabulary that has entries, or that the project has
 * nothing shared at all.
 *
 * A project with nothing shared is told so in words rather than shown a table with a zero in it:
 * the tab is where a constant or a section is declared, and an empty table with a count above it
 * reads as a screen that failed to load. Counted by `entry.kind` itself rather than a fixed list
 * of the vocabularies known today: `SharedEntry.kind` is a plain string on the wire for exactly
 * this reason (its own doc: "no generic function had to change when sections joined the tab"), so
 * a third vocabulary's rows count themselves the moment they arrive, with nothing here to change. */
export function tabTitle(entries: readonly SharedEntry[]): string {
  if (entries.length === 0) return "This project declares nothing in its shared files.";
  const counts = new Map<string, number>();
  for (const { kind } of entries) counts.set(kind, (counts.get(kind) ?? 0) + 1);
  return [...counts]
    .map(([kind, count]) => `${count} ${kind}${count === 1 ? "" : "s"}`)
    .join(" · ");
}

/** Whether the table holds that entry.
 *
 * What decides between the panel and the add form. A route carries the name a finding named, and
 * `unknown-constant` names one no file declares - so the page asks the table it already has rather
 * than a second request that would answer 404 on purpose. It also settles the race where the
 * constant was declared between the analysis and the click. */
export function isDeclared(reply: SharedReply, kind: string, name: string): boolean {
  return reply.entries.some((entry) => entry.kind === kind && entry.name === name);
}

/** One entry of the tab, as a selection and an address both name it: which vocabulary, and which
 * name within it.
 *
 * Both halves, because neither identifies a row on its own. A section's name is a linker string,
 * not a c identifier - `SECTION_NAME_PATTERN` is `[A-Za-z0-9_.$]+`, so the leading dot the shipped
 * example uses is a convention and not a rule - and a project may therefore declare a constant
 * `FOO` and a section `FOO` at once, two rows of one table under one spelling. */
export interface SharedSelection {
  kind: SharedKind;
  name: string;
}

/** The key the table gives a row, and reads a selection back from: the row's vocabulary and its
 * name, which together are unique where the name alone is not.
 *
 * Takes the kind as it comes off the wire rather than as a `SharedKind`, because every row needs a
 * key of its own whether or not the page can do anything with the row once it is clicked. Every
 * kind the tab lists has a panel now, a raster's included, so nothing exercises that today; it is
 * `SharedEntry.kind` being a plain string on the wire that this follows, and a fourth vocabulary's
 * rows would be keyed correctly here before its panel existed, exactly as a raster's were.
 *
 * A space joins the two, being a character neither half can hold: a kind is one of the server's
 * own vocabulary words and a name is a c identifier or a linker section name. `selectionAt` splits
 * at the first space all the same, so a vocabulary that ever admitted one in a name would still
 * come back whole. */
export function rowKey(kind: string, name: string): string {
  return `${kind} ${name}`;
}

/** Which entry that key names, or `undefined` where its vocabulary is one no address can name at
 * all - a vocabulary outside `SHARED_VOCABULARIES`, or a key with none in it.
 *
 * What turns a click in the table into an address. The key carries the row's own kind, so nothing
 * has to look the name up again: where a project declares a constant and a section under one
 * spelling, the row the reader clicked is the row that opens. Looking it up by name is what the
 * page did before, and `shared_rows` sorts by kind then name, so the constant always won and the
 * section's row opened the constant's panel. Undefined leaves the address bare - the tab itself -
 * which is `route.ts`'s own rule for an address that does not say what it selected: the tab, never
 * a guess at which vocabulary a name belonged to. */
export function selectionAt(key: string): SharedSelection | undefined {
  const space = key.indexOf(" ");
  if (space === -1) return undefined;
  const kind = SHARED_VOCABULARIES.find((known) => known === key.slice(0, space));
  return kind === undefined ? undefined : { kind, name: key.slice(space + 1) };
}

/** Of a section's keys, the ones whose value is a json string - `ddd.project_shared.SECTIONS.
 * strings`, the same two words. */
const SECTION_STRINGS: readonly string[] = ["access", "description"];

/** The json text one of a section's keys travels to the api as.
 *
 * `access` and `description` are strings, so they go in their quotes; `alignment` is a whole
 * number and goes without, since `"4"` is a string where the model wants a number and the file
 * would no longer load. The panel shows all three without quotes either way - `SectionReply` is
 * read that way on purpose, "so the panel's chooser is given the value and not its source". */
export function sectionRaw(key: string, text: string): string {
  return SECTION_STRINGS.includes(key) ? JSON.stringify(text) : text;
}

/**
 * One of a section's keys set to what its field holds, as `GET /api/section-plan` takes it.
 *
 * The key travels to the request and to the quoting from one argument, which is the whole reason
 * this exists. The panel's own `satisfies` clause pins each request to its own `key` literal, and
 * cannot pin that the same literal reached `sectionRaw`: measured in fix round 1, writing
 * `sectionRaw("access", draftAlignment)` under the alignment request passed biome, `tsc`, the
 * build and all 474 tests, and sent `?raw="8"` for an alignment - a quoted string where the model
 * wants a number, which the api refuses and a reader meets as a refusal they did nothing to earn.
 * Here the two cannot disagree, and a test can say so.
 *
 * Generic in the key so the literal survives into the return type: the panel's `satisfies` clause
 * reads `key: "access"`, and a plain `string` here would widen it away.
 */
export function sectionSet<K extends string>(
  name: string,
  key: K,
  text: string,
): Extract<SectionPlanRequest, { action: "set" }> & { key: K } {
  return { action: "set", name, key, raw: sectionRaw(key, text) };
}

/** Of a raster's keys, the ones whose value is a json string - `ddd.project_shared.RASTERS.
 * strings`, the same two words as a section's own. */
const RASTER_STRINGS: readonly string[] = ["cycle", "description"];

/** The json text one of a raster's keys travels to the api as, as `sectionRaw`'s over a raster's
 * own three keys: `cycle` and `description` are strings, so they go in their quotes; `event` is a
 * whole number and goes without, since `"1"` is a string where the model wants a number and the
 * file would no longer load. */
export function rasterRaw(key: string, text: string): string {
  return RASTER_STRINGS.includes(key) ? JSON.stringify(text) : text;
}

/**
 * One of a raster's keys set to what its field holds, as `GET /api/raster-plan` takes it.
 *
 * Generic in the key exactly as `sectionSet` is, and for the same reason: `screens/SectionPanel.
 * tsx`'s own `satisfies` clause pins each of its requests to its own `key` literal because
 * `sectionSet` lets that literal survive into the return type - a plain `string` here would widen
 * it away before a raster panel could rely on it the same way.
 */
export function rasterSet<K extends string>(
  name: string,
  key: K,
  text: string,
): Extract<RasterPlanRequest, { action: "set" }> & { key: K } {
  return { action: "set", name, key, raw: rasterRaw(key, text) };
}

/** The declaration a constant's add form comes to, or `null` while a parameter `add` requires is
 * still empty.
 *
 * `add`'s own `raw` is required where `set`'s may be left out (`ConstantPlanRequest`'s own doc): a
 * name with no value yet is not a request the api takes, and asking anyway would only ever come
 * back `bad-request` for a reader who has not finished typing. */
export function constantAdd(name: string, raw: string): ConstantPlanRequest | null {
  return name.trim() === "" || raw.trim() === "" ? null : { action: "add", name, raw };
}

/** The declaration a section's add form comes to, or `null` while a parameter `add` requires is
 * still empty.
 *
 * Two required parameters where a constant has one, because the model gives a default for neither
 * (`SECTIONS.required`) and a section missing either is one whose file would not load. Each
 * carries json text, as `?access="read-only"&alignment=4` - which is why the access goes through
 * `sectionRaw` rather than straight from the chooser. */
export function sectionAdd(
  name: string,
  access: string,
  alignment: string,
): SectionPlanRequest | null {
  if (name.trim() === "" || access.trim() === "" || alignment.trim() === "") return null;
  return {
    action: "add",
    name,
    access: sectionRaw("access", access),
    alignment: sectionRaw("alignment", alignment),
  };
}

/** What stands where a section's Remove would be while a definition still places its data there:
 * the count that would make the api refuse, read off the reply already on screen.
 *
 * Not the api's own refusal - asking for a plan only to prove it refuses is the lying button
 * `ComponentPage.tsx` will not draw - and not silence either, which leaves a reader looking at a
 * gap where a control might have been. The panel's own table above names each definition; this
 * only says how many. */
export function sectionRemoveBlocked(name: string, uses: number): string {
  const definitions = uses === 1 ? "1 definition places" : `${uses} definitions place`;
  return `${definitions} data in ${name}, so it cannot be removed.`;
}

/** The declaration a raster's add form comes to, or `null` while a parameter `add` requires is
 * still empty.
 *
 * One required parameter where a section has two and a constant one: `RASTERS.required` holds
 * `event` alone, the model defaulting `cycle` and `description` both - and an event that is not
 * cyclic is a real kind of raster rather than an omission, so a form asking for a cycle would be
 * asking for something the reader may have nothing to put in.
 *
 * The event goes through `rasterRaw` rather than straight from the field, as a section's access
 * and alignment do through `sectionRaw`: `add` carries json text, and the one place that decides
 * which of a raster's keys wear quotes is that function. It answers `event` unquoted today, and
 * would keep answering correctly if the model ever made the key a string. */
export function rasterAdd(name: string, event: string): RasterPlanRequest | null {
  if (name.trim() === "" || event.trim() === "") return null;
  return { action: "add", name, event: rasterRaw("event", event) };
}

/** Whether a raster's Remove may be offered at all: only while nothing names it.
 *
 * A function rather than a `uses.length === 0` written into each of the two `.tsx` files that
 * need it - `RasterPanelView`, which draws the control or the sentence below instead, and
 * `RasterPanel`, which asks for the plan or does not. A section's own rule is spelled twice that
 * way, and neither spelling is executed by any gate in this repo; here one fact has one home and
 * a test can hold it to account.
 *
 * Takes the uses rather than a count, so that a caller cannot pass the wrong number: the two that
 * matter are `reply.uses.length === 0` and nothing else, and a raster is named by a component's
 * own default as readily as by a definition - `remove_entry` refuses on either, and a panel
 * counting definitions alone would draw a Remove that refuses the moment it is pressed. */
export function rasterRemovable(uses: readonly RasterUse[]): boolean {
  return uses.length === 0;
}

/** What stands where a raster's Remove would be while a shape still names it: the count that
 * would make the api refuse, read off the reply already on screen - `sectionRemoveBlocked`'s own
 * sentence over a raster's uses.
 *
 * "shape" and not "definition", which is the whole difference between this and a section's: a
 * raster is named by a component's own default as well as by a definition, so a sentence counting
 * definitions would under-report a project whose only use is a default. It is the server's own
 * word for the pair, too - `ddd.shared_plans.remove_entry` refuses with "is named by N shapes". */
export function rasterRemoveBlocked(name: string, uses: number): string {
  const shapes = uses === 1 ? "1 shape names" : `${uses} shapes name`;
  return `${shapes} ${name}, so it cannot be removed.`;
}

/** What one use is, for the What column of a raster's panel: which of the two shapes
 * `RasterUse.kind` spells, in words rather than in the wire's own vocabulary.
 *
 * The column a section's panel fills with the component's name alone, because a section has one
 * shape naming it and the component is the only thing left to say. A raster has two, and a panel
 * that did not say which is which would list a component's default as though it were a definition
 * - the silent omission `RasterUse.kind` exists to prevent.
 *
 * A component's default says what it covers rather than whose it is: `RasterUse.name` is the
 * component's own name there, already in the row's first cell, so naming it again would be the
 * one cell that repeats its neighbour. A definition names its component, which is the fact its
 * own first cell does not carry.
 *
 * `component` is `string | null` on the wire and never null in an answer about a raster
 * (`RasterUse.component`'s own doc: a definition whose file has dropped the variable is left out
 * of `uses` altogether, and a component's default falls back to its file's name). The shape the
 * type admits is still answered, and answered as a definition: what it must never read as is a
 * default. */
export function rasterUseWhat(use: RasterUse): string {
  if (use.kind === "component") return "everything it produces";
  return use.component === null ? "a definition" : `a definition of ${use.component}`;
}

/** Where a use's row leads: the variable measured in the raster, on its component's page, or that
 * component's own page where the component names the raster for everything it produces.
 *
 * Two shapes where a section's own `routeOfUse` has one, for the reason `RasterUse.kind` has two
 * words: a component's default sits inside no definition, so there is no variable to open. A
 * route carrying `RasterUse.name` as its `variable` would ask the component's page for a variable
 * of the component's own name, which no file declares. */
export function rasterUseRoute(use: RasterUse): Route {
  return use.kind === "component"
    ? { page: "component", file: use.path }
    : { page: "component", file: use.path, variable: use.name };
}

/** A preview's changes as `POST /api/edit` takes them, under the label an undo of it offers.
 *
 * The units tab's own converter, not a second one: a plan is a plan whichever route previewed it,
 * and two of these would drift. */
export function planEdit(plan: PlanReply, label: string): Changes | null {
  return editOfPlan(plan, label);
}
