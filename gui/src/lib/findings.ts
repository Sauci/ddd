import type { Changes, Finding, FixReply, State } from "../api/types";
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

/** One row of the Findings tab: a finding, a key stable in the list, and the file's own name. */
export interface FindingRow {
  finding: Finding;
  key: string;
  file: string;
}

/** Worst first, and within a severity in the order the analysis filed them - which groups them
 * by file, since that is the order `GET /api/state` answers in. A stable sort is what keeps the
 * second half of that sentence true. `ignore` never reaches this list - that severity means a
 * finding is not reported at all - but `Record` still needs it named to index by severity. */
export function findingRows(state: State): FindingRow[] {
  const rank: Record<Finding["severity"], number> = { error: 0, warning: 1, info: 2, ignore: 3 };
  return keyedFindings(state.findings)
    .map(([finding, key]) => ({ finding, key, file: baseName(finding.file) }))
    .sort((one, other) => rank[one.finding.severity] - rank[other.finding.severity]);
}

/** Each severity's word, singular then plural, and the noun `findingCounts` says it under. */
const COUNTED = [
  ["error", "error", "errors"],
  ["warning", "warning", "warnings"],
  ["info", "note", "notes"],
] as const satisfies readonly [Finding["severity"], string, string][];

/** The tab's line above the table. */
export function findingCounts(findings: readonly Finding[]): string {
  if (findings.length === 0) return "Nothing to report";
  const of = (severity: Finding["severity"]) =>
    findings.filter((finding) => finding.severity === severity).length;
  const parts = COUNTED.map(([severity, one, many]) => [of(severity), one, many] as const)
    .filter(([count]) => count > 0)
    .map(([count, one, many]) => `${count} ${count === 1 ? one : many}`);
  const total = `${findings.length} finding${findings.length === 1 ? "" : "s"}`;
  return `${total} · ${parts.join(", ")}`;
}

/** What the button that follows a finding says, or `null` when it leads nowhere. */
export function routeLabel(finding: Finding, state: State): string | null {
  const route = finding.route;
  if (route === null) return null;
  if (route.kind === "component") {
    const listed = state.files.find((file) => file.path === finding.file);
    return `Open ${listed?.name ?? baseName(finding.file)}`;
  }
  return `Open ${route.name}`;
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

/** Why a finding leads nowhere, in the words the panel says it.
 *
 * The three the server answers `null` for are said in its own terms (`ddd.finding_routes`): a
 * file that did not load, a kind of file the page has no screen for, and a finding that names
 * no place at all - a check about the project, whose pointer is empty. What is left is a
 * finding that does name a place the file no longer has: a declaration moved since the
 * analysis read it, or a unit no longer stated where it was. Neither is about the project, and
 * neither is a sentence to guess at, so the reason says only what is certain of both. */
export function noRouteReason(finding: Finding, state: State): string {
  const name = baseName(finding.file);
  const listed = state.files.find((file) => file.path === finding.file);
  if (listed === undefined) return `${name} is not a file of this project`;
  if (!listed.loaded) return `${name} did not load`;
  if (listed.kind !== "component") return `${name} is a ${listed.kind} file, which has no page yet`;
  if (finding.pointer === "") return "it is about the project rather than a place in a file";
  return "there is nothing at that place any more";
}

/** The edit the fix of that title comes to, exactly as `POST /api/edit` takes it. */
export function fixEdit(reply: FixReply, title: string): Changes | null {
  const chosen = reply.fixes.find((fix) => fix.title === title);
  if (chosen === undefined) return null;
  const changes = nonEmpty(
    chosen.changes.flatMap(({ file, fingerprint, operations }) => {
      const made = nonEmpty(operations);
      return made === null ? [] : [{ file, fingerprint, operations: made }];
    }),
  );
  return changes === null ? null : { changes };
}

/** As `editOf` in `./units` narrows a preview's operations: `Changes`' own are a non-empty
 * tuple, which a fix's plain array cannot be assigned to without this proof. */
function nonEmpty<T>(items: readonly T[]): [T, ...T[]] | null {
  const [first, ...rest] = items;
  return first === undefined ? null : [first, ...rest];
}
