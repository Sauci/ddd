import type {
  Changes,
  EditReply,
  FileContent,
  Found,
  GraphReply,
  PlanReply,
  SessionInfo,
  SettleReply,
  State,
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

export const postEdit = (changes: Changes, fetchImpl: Fetch = fetch) =>
  request<EditReply>("/api/edit", post(changes), fetchImpl);

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
