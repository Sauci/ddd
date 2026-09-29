import type {
  Changes,
  CompareReply,
  ConstantReply,
  DeclarableReply,
  EditReply,
  FileContent,
  FilesPlanReply,
  FilesReply,
  FixReply,
  Found,
  GraphReply,
  PlanReply,
  RasterReply,
  SectionReply,
  SessionInfo,
  SettleReply,
  SharedReply,
  State,
  TypeReply,
  TypesReply,
  UndoPreview,
  UndoReply,
  UnitReply,
  UnitsReply,
  ValuesReply,
  VariableReply,
} from "./types";

type Fetch = (path: string, init?: RequestInit) => Promise<Response>;

/** A refusal or a failure the server answered with, carrying its code for the page to act on. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** The server did not answer at all: it stopped, or the connection was refused. */
export class ServerUnreachable extends Error {
  constructor(cause: unknown) {
    super("ddd gui is not answering", { cause });
    this.name = "ServerUnreachable";
  }
}

/** What a body that does not parse reads as, told apart from a body that is json's own `null`. */
const NOT_JSON = Symbol("not json");

export async function request<T>(
  path: string,
  init: RequestInit = {},
  fetchImpl: Fetch = fetch,
): Promise<T> {
  let response: Response;
  try {
    response = await fetchImpl(path, { credentials: "same-origin", ...init });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ServerUnreachable(error);
  }
  const body: unknown = await response.json().catch(() => NOT_JSON);
  if (!response.ok) {
    const code =
      isRecord(body) && typeof body.error === "string" ? body.error : `http-${response.status}`;
    const message =
      isRecord(body) && typeof body.message === "string" ? body.message : response.statusText;
    throw new ApiError(response.status, code, message);
  }
  // Refused rather than handed on: returned as null, it reached a screen that read a property
  // of it, and React unmounted the whole page.
  if (body === NOT_JSON) {
    throw new ApiError(
      response.status,
      "not-json",
      `ddd gui's answer to ${pathOf(path)} is not json`,
    );
  }
  return body as T;
}

export const getSession = (fetchImpl: Fetch = fetch) =>
  request<SessionInfo>("/api/session", {}, fetchImpl);

export const getProjects = (fetchImpl: Fetch = fetch) =>
  request<Found>("/api/projects", {}, fetchImpl);

export const openProject = (path: string, fetchImpl: Fetch = fetch) =>
  request<SessionInfo>("/api/open", post({ path }), fetchImpl);

export const getState = (after: number | null, signal?: AbortSignal, fetchImpl: Fetch = fetch) =>
  request<State>(
    after === null ? "/api/state" : `/api/state?after=${after}`,
    signal === undefined ? {} : { signal },
    fetchImpl,
  );

export const getFile = (path: string, fetchImpl: Fetch = fetch) =>
  request<FileContent>(`/api/file?path=${encodeURIComponent(path)}`, {}, fetchImpl);

export const getGraph = (fetchImpl: Fetch = fetch) =>
  request<GraphReply>("/api/graph", {}, fetchImpl);

export const getVariable = (name: string, fetchImpl: Fetch = fetch) =>
  request<VariableReply>(`/api/variable?name=${encodeURIComponent(name)}`, {}, fetchImpl);

export const getUnits = (fetchImpl: Fetch = fetch) =>
  request<UnitsReply>("/api/units", {}, fetchImpl);

export const getSettle = (
  name: string,
  key: string,
  raw: string | null,
  fetchImpl: Fetch = fetch,
) => request<SettleReply>(`/api/settle?${settleQuery(name, key, raw)}`, {}, fetchImpl);

/** The preview's query: without `raw`, the key is to go from every declaration. */
function settleQuery(name: string, key: string, raw: string | null): string {
  const query = `name=${encodeURIComponent(name)}&key=${encodeURIComponent(key)}`;
  return raw === null ? query : `${query}&raw=${encodeURIComponent(raw)}`;
}

export const getFix = (file: string, pointer: string, check: string, fetchImpl: Fetch = fetch) =>
  request<FixReply>(
    `/api/fix?file=${encodeURIComponent(file)}&pointer=${encodeURIComponent(pointer)}` +
      `&check=${encodeURIComponent(check)}`,
    {},
    fetchImpl,
  );

export const getCompare = (baseline: string, fetchImpl: Fetch = fetch) =>
  request<CompareReply>(`/api/compare?baseline=${encodeURIComponent(baseline)}`, {}, fetchImpl);

/** One change to the project's units, as `GET /api/unit-plan` takes it: what each action needs,
 * and nothing it does not. */
export type UnitPlanRequest =
  | { action: "rename"; unit: string; to: string }
  | { action: "add" | "remove"; unit: string }
  | { action: "describe"; unit: string; description: string }
  | { action: "adopt" };

export const getUnit = (name: string, fetchImpl: Fetch = fetch) =>
  request<UnitReply>(`/api/unit?name=${encodeURIComponent(name)}`, {}, fetchImpl);

export const getUnitPlan = (plan: UnitPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/unit-plan?${planQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action, then the unit and whichever of `to` and `description` it takes. */
function planQuery(plan: UnitPlanRequest): string {
  const parts: [string, string][] = [["action", plan.action]];
  if (plan.action !== "adopt") parts.push(["unit", plan.unit]);
  if (plan.action === "rename") parts.push(["to", plan.to]);
  if (plan.action === "describe") parts.push(["description", plan.description]);
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}

export const getTypes = (fetchImpl: Fetch = fetch) =>
  request<TypesReply>("/api/types", {}, fetchImpl);

export const getType = (name: string, fetchImpl: Fetch = fetch) =>
  request<TypeReply>(`/api/type?name=${encodeURIComponent(name)}`, {}, fetchImpl);

/** One change to a type, as `GET /api/type-plan` takes it: what each action needs. */
export type TypePlanRequest =
  | { action: "set"; name: string; key: string; raw: string | null }
  | { action: "rename"; name: string; to: string };

export const getTypePlan = (plan: TypePlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/type-plan?${typeQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action and the type, then whichever of `key`, `raw` and `to` it takes.
 * A `raw` of `null` is left out, which is how the server reads "leave the key out". */
function typeQuery(plan: TypePlanRequest): string {
  const parts: [string, string][] = [
    ["action", plan.action],
    ["name", plan.name],
  ];
  if (plan.action === "set") {
    parts.push(["key", plan.key]);
    if (plan.raw !== null) parts.push(["raw", plan.raw]);
  } else {
    parts.push(["to", plan.to]);
  }
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}

export const getShared = (fetchImpl: Fetch = fetch) =>
  request<SharedReply>("/api/shared", {}, fetchImpl);

export const getConstant = (name: string, fetchImpl: Fetch = fetch) =>
  request<ConstantReply>(`/api/constant?name=${encodeURIComponent(name)}`, {}, fetchImpl);

/** One change to a constant, as `GET /api/constant-plan` takes it: what each action needs, and
 * nothing it does not - `add`'s `raw` is a value it cannot go without, the way `set`'s can be
 * asked for before a reader has typed anything into the value field. */
export type ConstantPlanRequest =
  | { action: "set"; name: string; key: string; raw?: string | null }
  | { action: "rename"; name: string; to: string }
  | { action: "add"; name: string; raw: string }
  | { action: "remove"; name: string };

export const getConstantPlan = (plan: ConstantPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/constant-plan?${constantQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action and the name, then whichever of `key`, `raw` and `to` it takes.
 * `set`'s `raw` left out - whether omitted or given as `null` - is how the server reads "leave
 * the key out"; `add`'s `raw` is neither, so it always travels. */
function constantQuery(plan: ConstantPlanRequest): string {
  const parts: [string, string][] = [
    ["action", plan.action],
    ["name", plan.name],
  ];
  if (plan.action === "set") {
    parts.push(["key", plan.key]);
    if (plan.raw !== undefined && plan.raw !== null) parts.push(["raw", plan.raw]);
  } else if (plan.action === "rename") {
    parts.push(["to", plan.to]);
  } else if (plan.action === "add") {
    parts.push(["raw", plan.raw]);
  }
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}

export const getSection = (name: string, fetchImpl: Fetch = fetch) =>
  request<SectionReply>(`/api/section?name=${encodeURIComponent(name)}`, {}, fetchImpl);

/** One change to a section, as `GET /api/section-plan` takes it: the same four verbs as
 * `ConstantPlanRequest`, over the same three parameters, differing only in `add` - a section is
 * declared with one json text per required key (`access`, then `alignment`, the order
 * `ddd.gui.api._required_keys` reads off `Vocabulary.keys`) rather than a lone `raw`, because a
 * section the model gives no default for either key is one whose file would not load. */
export type SectionPlanRequest =
  | { action: "set"; name: string; key: string; raw?: string | null }
  | { action: "rename"; name: string; to: string }
  | { action: "add"; name: string; access: string; alignment: string }
  | { action: "remove"; name: string };

export const getSectionPlan = (plan: SectionPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/section-plan?${sectionQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action and the name, then whichever of `key`/`raw`, `to`, or `access`/
 * `alignment` it takes - as `constantQuery`'s, with `add`'s two required keys in place of the one
 * `raw` a constant's declaration takes. */
function sectionQuery(plan: SectionPlanRequest): string {
  const parts: [string, string][] = [
    ["action", plan.action],
    ["name", plan.name],
  ];
  if (plan.action === "set") {
    parts.push(["key", plan.key]);
    if (plan.raw !== undefined && plan.raw !== null) parts.push(["raw", plan.raw]);
  } else if (plan.action === "rename") {
    parts.push(["to", plan.to]);
  } else if (plan.action === "add") {
    parts.push(["access", plan.access], ["alignment", plan.alignment]);
  }
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}

export const getRaster = (name: string, fetchImpl: Fetch = fetch) =>
  request<RasterReply>(`/api/raster?name=${encodeURIComponent(name)}`, {}, fetchImpl);

/** One change to a raster, as `GET /api/raster-plan` takes it: the same four verbs as
 * `SectionPlanRequest`, over the same three parameters, differing only in `add` - a raster is
 * declared with the one json text for the one key the model gives no default for (`event`)
 * rather than the two `access`/`alignment` a section needs, because `RASTERS.required` is
 * `event` alone: `cycle` is optional and `description` defaults, so neither is `add`'s to supply. */
export type RasterPlanRequest =
  | { action: "set"; name: string; key: string; raw?: string | null }
  | { action: "rename"; name: string; to: string }
  | { action: "add"; name: string; event: string }
  | { action: "remove"; name: string };

export const getRasterPlan = (plan: RasterPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/raster-plan?${rasterQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action and the name, then whichever of `key`/`raw`, `to` or `event` it
 * takes - as `sectionQuery`'s, with `add`'s one required key in place of a section's two. */
function rasterQuery(plan: RasterPlanRequest): string {
  const parts: [string, string][] = [
    ["action", plan.action],
    ["name", plan.name],
  ];
  if (plan.action === "set") {
    parts.push(["key", plan.key]);
    if (plan.raw !== undefined && plan.raw !== null) parts.push(["raw", plan.raw]);
  } else if (plan.action === "rename") {
    parts.push(["to", plan.to]);
  } else if (plan.action === "add") {
    parts.push(["event", plan.event]);
  }
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}

export const getFiles = (fetchImpl: Fetch = fetch) =>
  request<FilesReply>("/api/files", {}, fetchImpl);

/** One change to the project's own files, as `GET /api/files-plan` takes it: what each action
 * needs, and nothing it does not - `create`'s `component` is a new component's own name, taken
 * only for a `kind` of `"component"` and ignored for every other, exactly as `FILE_PLANS` reads
 * it. `add`'s `path` is typed relative to the project description, the way a reader spells an
 * `includes` entry; `remove`'s is a row's own absolute key (`IncludedEntryReply.key`, or one of
 * a pattern's own `files`) - one field name, two different shapes of path, because that is what
 * the two actions each take a path *as*. */
export type FilesPlanRequest =
  | { action: "create"; kind: string; name: string; component?: string }
  | { action: "add"; path: string }
  | { action: "remove"; path: string };

export const getFilesPlan = (plan: FilesPlanRequest, fetchImpl: Fetch = fetch) =>
  request<FilesPlanReply>(`/api/files-plan?${filesQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action, then `create`'s `kind` and `name` (and `component`, where given),
 * or `add`'s and `remove`'s shared `path`. */
function filesQuery(plan: FilesPlanRequest): string {
  const parts: [string, string][] = [["action", plan.action]];
  if (plan.action === "create") {
    parts.push(["kind", plan.kind], ["name", plan.name]);
    if (plan.component !== undefined) parts.push(["component", plan.component]);
  } else {
    parts.push(["path", plan.path]);
  }
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}

export const getDeclarable = (file: string, fetchImpl: Fetch = fetch) =>
  request<DeclarableReply>(`/api/declarable?file=${encodeURIComponent(file)}`, {}, fetchImpl);

/** One change to a component's interface, as `GET /api/declaration-plan` takes it. */
export type DeclarationPlanRequest =
  | { action: "read"; file: string; name: string; scope: string }
  | { action: "declare"; file: string; scope: string; definition: string }
  | { action: "remove"; file: string; name: string };

export const getDeclarationPlan = (plan: DeclarationPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/declaration-plan?${declarationQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action and the file, then whichever of `name`, `scope` and `definition`
 * the action takes - the same three sets the server's DECLARATION_PLANS names. */
function declarationQuery(plan: DeclarationPlanRequest): string {
  const parts: [string, string][] = [
    ["action", plan.action],
    ["file", plan.file],
  ];
  if (plan.action === "read") parts.push(["name", plan.name], ["scope", plan.scope]);
  else if (plan.action === "remove") parts.push(["name", plan.name]);
  else parts.push(["scope", plan.scope], ["definition", plan.definition]);
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}

export const postEdit = (changes: Changes, fetchImpl: Fetch = fetch) =>
  request<EditReply>("/api/edit", post(changes), fetchImpl);

export const getUndo = (fetchImpl: Fetch = fetch) =>
  request<UndoPreview>("/api/undo", {}, fetchImpl);

export const postUndo = (at: number, fetchImpl: Fetch = fetch) =>
  request<UndoReply>("/api/undo", post({ at }), fetchImpl);

export const getValues = (name: string, fetchImpl: Fetch = fetch) =>
  request<ValuesReply>(`/api/values?name=${encodeURIComponent(name)}`, {}, fetchImpl);

/** One cell's change, as `GET /api/value-plan` takes it. */
export interface ValuePlanRequest {
  name: string;
  /** `[2]` or `[1][3]` - the element, as a json pointer suffix. */
  at: string;
  /** The raw count to store, already converted from what was typed. */
  raw: number;
}

export const getValuePlan = (plan: ValuePlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(
    `/api/value-plan?name=${encodeURIComponent(plan.name)}` +
      `&at=${encodeURIComponent(plan.at)}&raw=${encodeURIComponent(String(plan.raw))}`,
    {},
    fetchImpl,
  );

/** A whole table's change, as `GET /api/values-plan` takes it: the counts row-major, in one list. */
export interface ValuesPlanRequest {
  name: string;
  raw: readonly number[];
}

/** What one address may carry. `BaseHTTPRequestHandler` reads the request line with
 * `readline(65537)` and answers **414** to anything longer than 65536 bytes, and `ddd gui`'s
 * own server is one of those (`GuiServer`, a `ThreadingHTTPServer`). The line is `GET `, the
 * address, ` HTTP/1.1` and a CRLF, so the address itself has 65521 bytes of it - and every byte
 * of an encoded address is ascii, so its length in characters is its length in bytes. */
const ADDRESS_LIMIT = 65536 - "GET ".length - " HTTP/1.1\r\n".length;

export const getValuesPlan = async (plan: ValuesPlanRequest, fetchImpl: Fetch = fetch) => {
  const address =
    `/api/values-plan?name=${encodeURIComponent(plan.name)}` +
    `&raw=${encodeURIComponent(plan.raw.join(","))}`;
  // Refused before it is asked for, rather than sent and answered 414: a count costs its own
  // digits plus the three of the `%2C` before it, which is about 8 000 whole counts and about
  // 2 500 that carry decimals, `rawOf` answering an unrounded double for a float datatype. The
  // shape of the block cannot bound this - the object's own shape is what makes it large - and
  // the alternative is a reader meeting `Request-URI Too Long` under the grid, which is true
  // and tells them nothing about their table.
  if (address.length > ADDRESS_LIMIT) {
    throw new Error(
      `'${plan.name}' has too many values to plan in one request: its counts need ` +
        `${address.length} characters of address, and ddd gui reads at most ${ADDRESS_LIMIT}`,
    );
  }
  return request<PlanReply>(address, {}, fetchImpl);
};

function post(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** An address without its query, which for a file is the file's whole encoded path. */
function pathOf(address: string): string {
  return address.split("?", 1)[0] as string;
}
