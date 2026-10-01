import type {
  Changes,
  Finding,
  FindingCounts,
  FindingsReply,
  FixReply,
  ListedFinding,
  State,
} from "../api/types";
import { hrefOf, type Route } from "./route";
import { baseName } from "./units";

/**
 * Each finding of a list, paired with a React key stable across re-renders of that list.
 *
 * Position alone is not a key: the list is rebuilt on every revision, and an unrelated finding
 * appearing or disappearing earlier in it would shift every key after it. Content alone is not
 * enough either, since the API sends no line or column: a consumer whose unit and limits both
 * disagree gets two `definition-mismatch` findings at the same pointer, and a producer with
 * several disagreeing consumers gets one finding mirrored onto it per consumer, so two distinct
 * findings can share severity, check, pointer and message. The key is that content together
 * with which repeat of it this is - 0 for the first, 1 for the next with the same content, and
 * so on - which tells such findings apart while staying stable when a differently-keyed finding
 * elsewhere in the list comes or goes.
 */
export function keyedFindings(findings: readonly Finding[]): (readonly [Finding, string])[] {
  const seen = new Map<string, number>();
  return findings.map((finding) => {
    const content = JSON.stringify([
      finding.severity,
      finding.check,
      finding.pointer,
      finding.message,
    ]);
    const occurrence = seen.get(content) ?? 0;
    seen.set(content, occurrence + 1);
    return [finding, `${content}#${occurrence}`] as const;
  });
}

/**
 * A list of findings with each statement in it once: the first of those that share severity,
 * check and message, wherever they are filed.
 *
 * The analysis files a disagreement on each of the files it concerns - mirrored onto the
 * producer for every consumer that disagrees with it - so that an editor shows it in each. A list
 * that speaks of one variable across its files, as its panel's does, would say the same sentence
 * once per file.
 */
export function distinctFindings(findings: readonly Finding[]): Finding[] {
  const said = new Set<string>();
  return findings.filter((finding) => {
    const statement = JSON.stringify([finding.severity, finding.check, finding.message]);
    if (said.has(statement)) return false;
    said.add(statement);
    return true;
  });
}

/** One row of a table of findings drawn whole, as the Compare tab draws its own: a finding, a key
 * stable in the list, and the file's own name. */
export interface FindingRow {
  finding: Finding;
  key: string;
  file: string;
}

/** Each severity's word, singular then plural, and the noun `findingCounts` says it under. */
const COUNTED = [
  ["error", "error", "errors"],
  ["warning", "warning", "warnings"],
  ["info", "note", "notes"],
] as const satisfies readonly [keyof FindingCounts, string, string][];

/** How many findings the counts count, of every severity together. */
export function findingsTotal(counts: FindingCounts): number {
  return counts.error + counts.warning + counts.info;
}

/** How many findings of a list there are of each severity: what the Compare tab counts its own
 * reply's list by, as the state counts a revision's. One at `ignore` - which the server never
 * reports - is counted under none. */
export function countsOf(findings: readonly Finding[]): FindingCounts {
  const counts = { error: 0, warning: 0, info: 0 };
  for (const finding of findings) {
    if (finding.severity !== "ignore") counts[finding.severity] += 1;
  }
  return counts;
}

/** The line above a table of findings, from how many there are of each severity: the Findings
 * tab's from the state's counts, the Compare tab's from its own list's. `_updating` - whether the
 * counts are about to change - is taken, and not said yet: the line reads the same either way. */
export function findingCounts(counts: FindingCounts, _updating: boolean): string {
  const total = findingsTotal(counts);
  if (total === 0) return "Nothing to report";
  const parts = COUNTED.filter(([severity]) => counts[severity] > 0).map(
    ([severity, one, many]) => `${counts[severity]} ${counts[severity] === 1 ? one : many}`,
  );
  return `${total} finding${total === 1 ? "" : "s"} · ${parts.join(", ")}`;
}

/** What the panel of a selected finding shows once `reply` - the findings of its file and its
 * check, asked of the newest revision - has come: the finding of the same key as the reply reports
 * it, so that its notes and its route are that revision's, or `null` where the reply no longer
 * reports that key, when the panel closes; until the reply comes, the finding as it was selected.
 * Its key is the one thing a page of findings and a selection hold in common. */
export function selectedNow(
  selected: ListedFinding,
  reply: FindingsReply | undefined,
): ListedFinding | null {
  if (reply === undefined) return selected;
  return reply.findings.find((finding) => finding.key === selected.key) ?? null;
}

/** What the button that follows a finding says, or `null` when it leads nowhere. */
export function routeLabel(finding: Finding, state: State): string | null {
  const route = finding.route;
  if (route === null) return null;
  if (route.kind === "component") {
    const listed = state.files.find((file) => file.path === finding.file);
    return `Open ${listed?.name ?? baseName(finding.file)}`;
  }
  if (route.kind === "file" && route.name !== null) {
    // Unlike the component arm above, no listed file's own declared name is ever worth
    // preferring here - not because neither check's file ever has one (a project description's
    // own name reads through `SourceFile.name` too, `ddd.gui.session._name_in` keying off
    // `parsed[kind]["name"]`), but because neither check's *route* ever names a file that both
    // sits in `State.files` and carries a name: `include-empty` is filed wherever a pattern
    // cannot be expanded at all (`ddd.loading._expand`'s own words, "cannot expand pattern") or
    // expands to no file, so its route names that pattern either way, which `State.files` -
    // files the loader actually read - never lists; `empty-vocabulary`'s names the vocabulary
    // file it is filed on, which `State.files` does list, but a vocabulary's own top-level key
    // holds a list there, not the dict `_name_in` reads a name from - a component's and a
    // project's own both do, a vocabulary's alone does not. A row of the Files tab is one entry
    // among others the same directory can hold, so the path relative to the project - the very
    // shape an entry is itself written in (`sensors/a.ddd.json`) - says which one a `baseName`
    // alone, repeated across two directories, could not.
    return `Open ${relativeToProject(route.name, state.project)}`;
  }
  return `Open ${route.name}`;
}

/** A path named the way an `includes` entry would spell it - relative to the project
 * description's own directory - or, where it does not sit inside that directory at all, by its
 * base name: the fallback `routeLabel`'s `component` arm always takes, kept here for a path an
 * entry reached by a parent directory (`../`) rather than one beneath the project. Exported: the
 * Files tab's own `cellsOf` (`lib/files.ts`) names a pattern's matched file the very same way
 * (design §2, part 16), and imports this rather than a second copy of it. */
export function relativeToProject(path: string, project: string): string {
  const directory = project.slice(0, project.lastIndexOf("/") + 1);
  return path.startsWith(directory) ? path.slice(directory.length) : baseName(path);
}

/** The page's own route a finding leads to, or `null` when it leads nowhere.
 *
 * One answer in two forms: a screen navigates with the route, and a link carries the address
 * `routeHref` writes from it, the way `LinkTabs` already pairs an `href` with its `onFollow`. */
export function routeOf(finding: Finding): Route | null {
  const route = finding.route;
  if (route === null) return null;
  if (route.kind === "unit" && route.name !== null) {
    return { page: "project", view: "units", unit: route.name };
  }
  if (route.kind === "variable" && route.name !== null) {
    return { page: "component", file: finding.file, variable: route.name };
  }
  if (route.kind === "values" && route.name !== null) {
    return { page: "component", file: finding.file, variable: route.name, view: "values" };
  }
  if (route.kind === "type" && route.name !== null) {
    return { page: "project", view: "types", type: route.name };
  }
  if (
    (route.kind === "constant" || route.kind === "section" || route.kind === "raster") &&
    route.name !== null
  ) {
    // The one route kind, whether or not the name is declared (design §2 "the page decides"):
    // `SharedPage` asks `isDeclared` of its own table and opens the panel or the pre-filled add
    // form accordingly, which is also what `unknown-constant` and `unknown-section` need - the
    // name either carries names nothing yet. One tab for all three vocabularies is the design
    // decision this rests on, so a raster joining it widened this arm's condition, rather than
    // adding a third one beside it.
    return { page: "project", view: "shared", kind: route.kind, name: route.name };
  }
  if (route.kind === "file" && route.name !== null) {
    // The Files tab's own row, keyed by `route.name` exactly as `rowsOf` (lib/files.ts) keys a
    // row: the resolved path `ddd.finding_routes.route_of`'s `FILE_CHECKS` branch answers, an
    // entry's own key for `include-empty` or the file's own path for `empty-vocabulary`.
    return { page: "project", view: "files", path: route.name };
  }
  return { page: "component", file: finding.file };
}

/** The address that route is written as, or `null` when the finding leads nowhere. */
export function routeHref(finding: Finding): string | null {
  const route = routeOf(finding);
  return route === null ? null : hrefOf(route);
}

/** Whether a finding's route leads somewhere other than this very component's page - a link to
 * where the reader already is teaches nothing (spec 5.2). */
export function leadsElsewhere(finding: Finding, file: string): boolean {
  const route = routeOf(finding);
  return (
    route !== null &&
    !(route.page === "component" && route.file === file && route.variable === undefined)
  );
}

/** Whether a finding's route names this very variable - the place already being looked at, so
 * it stays text rather than becoming a link (spec 5.2). */
export function namesThisVariable(finding: Finding, name: string): boolean {
  const route = routeOf(finding);
  return route !== null && route.page === "component" && route.variable === name;
}

/** The files a tab's table cannot show the contents of, by name: those of the tab's own kinds
 * that did not load, and those that did not load without saying what kind they are.
 *
 * Two lists because the tab can only speak for the first. `ddd.gui.session.kind_of` reads a file's
 * kind off its own top-level key, so a file nobody could parse has none to read and the server
 * answers `unknown` - correctly, since a constants file and a types file cannot be told apart when
 * neither could be read. Filtering by kind alone, as both tabs did, missed the commonest way a file
 * fails: an editor saving it half-written. The reader saw a table missing entries and nothing
 * saying why.
 *
 * `kinds` rather than one: the Shared files tab holds three vocabularies in one table, each with
 * its own file kind, and a failed sections or rasters file must be named beside a failed constants
 * file rather than silently dropped because it was not the one kind the tab used to ask about
 * (ruling R1). Which three is not spelled here - `SharedPage` passes `SHARED_KINDS`, and that list
 * is the one fact saying which vocabularies the tab holds.
 *
 * Here rather than in each screen because a screen is a `.tsx` file, which no gate in this repo
 * executes - the filter that decides what a reader is told about a missing file belongs where its
 * tests can reach it. */
export function unreadable(
  state: State | null,
  kinds: readonly string[],
): { own: string[]; untold: string[] } {
  const missing = (state?.files ?? []).filter((file) => !file.loaded);
  return {
    own: missing.filter((file) => kinds.includes(file.kind)).map((file) => baseName(file.path)),
    untold: missing.filter((file) => file.kind === "unknown").map((file) => baseName(file.path)),
  };
}

/** The file kinds the page opens a screen on: a component's own page, and the tab each vocabulary
 * with one is listed in.
 *
 * Units, types, sections and rasters belong here and were missing in turn: each had a tab before
 * its own kind joined this set, and a reader whose finding led nowhere was told their file had no
 * page. What reaches this line for one of them now is a pointer the file has moved on from -
 * `duplicate-unit`, `duplicate-section` and `duplicate-raster`, the checks that used to arrive
 * here with somewhere to go, route to the unit, the section or the raster they name instead.
 * `empty-vocabulary` used to arrive here too, about the whole file; it no longer does, `routeOf`'s
 * own `file` arm (part 16) giving it a route to the Files tab before this line is ever read, the
 * same as `include-empty` already had nothing to do with this set - neither is filed inside a
 * component. */
const SHOWN = new Set(["component", "constants", "types", "units", "sections", "rasters"]);

/** Why a finding leads nowhere, in the words the panel says it.
 *
 * The three the server answers `null` for are said in its own terms (`ddd.finding_routes`): a
 * file that did not load, a kind of file the page has no screen for, and a finding that names
 * no place at all - a check about the project, whose pointer is empty. A pointer that is one
 * top level key names the file's own list - the shape `empty-vocabulary` was drawn at, the list
 * being empty, until part 16 gave it its own route to the Files tab (`routeOf`'s `file` arm) -
 * and so the whole of what the file declares, which no panel shows. What is left is a
 * finding that does name a place the file no longer has: a declaration moved since the
 * analysis read it, or a unit no longer stated where it was. Neither is about the project, and
 * neither is a sentence to guess at, so the reason says only what is certain of both. */
export function noRouteReason(finding: Finding, state: State): string {
  const name = baseName(finding.file);
  const listed = state.files.find((file) => file.path === finding.file);
  if (listed === undefined) return `${name} is not a file of this project`;
  if (!listed.loaded) return `${name} did not load`;
  if (!SHOWN.has(listed.kind)) return `${name} is a ${listed.kind} file, which has no page yet`;
  if (finding.pointer === "") return "it is about the project rather than a place in a file";
  if (!/[.[]/.test(finding.pointer)) {
    return `it is about the whole of ${name} rather than one entry of it`;
  }
  return "there is nothing at that place any more";
}

/** The edit the fix of that title comes to, exactly as `POST /api/edit` takes it, under the
 * label an undo of it would offer. */
export function fixEdit(reply: FixReply, title: string, label: string): Changes | null {
  const chosen = reply.fixes.find((fix) => fix.title === title);
  if (chosen === undefined) return null;
  const changes = nonEmpty(
    chosen.changes.flatMap(({ file, fingerprint, operations }) => {
      const made = nonEmpty(operations);
      return made === null ? [] : [{ file, fingerprint, operations: made }];
    }),
  );
  return changes === null ? null : { changes, label };
}

/** As `editOf` in `./units` narrows a preview's operations: `Changes`' own are a non-empty
 * tuple, which a fix's plain array cannot be assigned to without this proof. */
function nonEmpty<T>(items: readonly T[]): [T, ...T[]] | null {
  const [first, ...rest] = items;
  return first === undefined ? null : [first, ...rest];
}
