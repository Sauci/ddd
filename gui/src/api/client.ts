import type {
  Changes,
  DeclarableReply,
  EditReply,
  FileContent,
  FixReply,
  Found,
  GraphReply,
  PlanReply,
  SessionInfo,
  SettleReply,
  State,
  TypeReply,
  TypesReply,
  UndoPreview,
  UndoReply,
  UnitReply,
  UnitsReply,
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
