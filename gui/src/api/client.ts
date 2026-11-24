import type { Write } from "../lib/announcing";
import { type OwnEdits, ownEdits } from "../state/edits";
import { type Keeper, type SignedOut, signedOut, token } from "./token";
import type {
  CellsPlanQuery,
  Changes,
  CompareQuery,
  CompareReply,
  ConstantPlanQuery,
  ConstantQuery,
  ConstantReply,
  DeclarableQuery,
  DeclarableReply,
  DeclarationPlanQuery,
  DescriptionPlanQuery,
  EditReply,
  FileContent,
  FileQuery,
  FilesPlanQuery,
  FilesPlanReply,
  FilesReply,
  FindingsQuery,
  FindingsReply,
  FixQuery,
  FixReply,
  Found,
  GraphReply,
  NamesQuery,
  NamesReply,
  PlanReply,
  RasterPlanQuery,
  RasterQuery,
  RasterReply,
  SectionPlanQuery,
  SectionQuery,
  SectionReply,
  SessionInfo,
  SettleQuery,
  SettleReply,
  SharedReply,
  State,
  StateQuery,
  TypePlanQuery,
  TypeQuery,
  TypeReply,
  TypesReply,
  UndoPreview,
  UndoReply,
  UnitPlanQuery,
  UnitQuery,
  UnitReply,
  UnitsReply,
  ValuePlanQuery,
  ValuesPlanQuery,
  ValuesQuery,
  ValuesReply,
  VariableQuery,
  VariableReply,
} from "./types";

/** The `fetch` a request is sent through: the global by default, a stub in the tests. Declared
 * here and imported where else it is needed (`signIn.ts`), so the two cannot drift apart. */
export type Fetch = (path: string, init?: RequestInit) => Promise<Response>;

/** A refusal or a failure the server answered with, carrying its code for the page to act on - or
 * a refusal `request` makes itself, as the server would have answered it: of an address too long
 * to send, `414` and `too-long`, and of a body too large, `413` and `too-large`. */
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

/** The code of a success whose body does not parse (`request`): one that is not json at all, or one
 * cut on its way, which the browser reads as far as it came. */
const UNPARSED = "not-json";

/**
 * Whether the page asks again, after a delay, an ask that failed so (decision 15.4): one that got
 * no answer at all (`ServerUnreachable`); one the server failed on, a 5xx - its own failure on the
 * request, or a connection past the most it answers at once, refused `503` with words saying to ask
 * again in a moment (`BUSY`, gui/server.py); and one whose answer does not parse, cut on its way.
 * Ended there, the page's long poll followed nothing more, and a page whose ask of the session
 * failed as it loaded drew nothing, until it was reloaded. Never a refusal, a 4xx - one `request`
 * makes itself, as the server would answer it, among them - which is the server's answer to what
 * was asked, and is answered again; nor an abort, which the page asked for itself.
 */
export function askedAgain(error: unknown): error is ApiError | ServerUnreachable {
  if (error instanceof ServerUnreachable) return true;
  return error instanceof ApiError && (error.status >= 500 || error.code === UNPARSED);
}

/** What `request` is asked with: a `RequestInit` whose headers are a plain record, as every
 * caller here builds them, so that the token's header is added beside them; whose body is text,
 * as `post` makes it, so that `request` measures what is sent; and, where it is `named`, what a
 * refusal `request` makes of it calls it - an edit by its label - in place of its route. */
export type Ask = Omit<RequestInit, "headers" | "body"> & {
  headers?: Record<string, string>;
  body?: string;
  named?: string;
};

/** Whether a request whose fetch was rejected is sent once more (spec 2026-10-08 §6): a GET,
 * which asks and changes nothing, whose fetch got no answer at all. Never an abort, which the
 * page asked for itself, and never another method, whose effect may have happened before the
 * connection failed. An HTTP answer, a refusal included, never comes here: `fetch` resolves it. */
export function sentAgain(method: string | undefined, error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") return false;
  return (method ?? "GET").toUpperCase() === "GET";
}

/** The longest request line `ddd gui`'s server reads, its CRLF included: `BaseHTTPRequestHandler`
 * reads the line with `readline(65537)` and answers **414** to anything longer than 65536 bytes,
 * and `ddd gui`'s own server is one of those (`GuiServer`, a `ThreadingHTTPServer`). This and the
 * two limits of a body below are copies, each held to the server's by a test of its own suite
 * (`TestThePageHoldsThisServersLimits`, tests/test_gui_server.py). */
const LINE_LIMIT = 65536;

/** What one address may carry, asked with `method`: the line is the method, a space, the address,
 * ` HTTP/1.1` and a CRLF, so a `GET`'s address has 65521 bytes of it - and an address the page
 * builds is ascii, its query encoded as a browser sends it (`encoded`), so its length in
 * characters is the bytes sent. */
function addressLimit(method: string | undefined): number {
  return LINE_LIMIT - `${(method ?? "GET").toUpperCase()}  HTTP/1.1\r\n`.length;
}

/** The code of a refusal of an address too long to send (`tooLong`). */
const TOO_LONG = "too-long";

/** What is said of an ask whose address is longer than one request line carries, as `request`
 * refuses it, naming its route (3:I8): asked, it would be answered the standard library's 414 page,
 * whose `Request-URI Too Long` is true and tells a reader nothing of what they asked. */
function tooLong(address: string, limit: number): ApiError {
  return new ApiError(
    414,
    TOO_LONG,
    `${pathOf(address)} cannot be asked in one request: its address needs ${address.length} ` +
      `characters, and ddd gui reads at most ${limit}`,
  );
}

/** The most `ddd gui`'s server reads of an edit's body, `POST /api/edit`'s: `EDIT_BODY`
 * (gui/server.py), 8 MiB, since an Apply posts every change of its plan. */
export const EDIT_BODY = 8 * 1024 * 1024;

/** The most it reads of the body of any other route: `MAX_BODY` (gui/server.py), 1 MiB. */
export const MAX_BODY = 1024 * 1024;

/** The route whose body the server reads up to `EDIT_BODY`, and not `MAX_BODY`. */
const EDIT_ROUTE = "/api/edit";

/** The most the server reads of a body sent to `address`: chosen, as the server chooses it
 * (`_route`, gui/server.py), by the address's path alone, whatever its query. */
function bodyLimit(address: string): number {
  return pathOf(address) === EDIT_ROUTE ? EDIT_BODY : MAX_BODY;
}

/** The code of a refusal of a body too large to send (`tooLarge`), the server's own for it. */
const TOO_LARGE = "too-large";

/** What is said of an ask whose body is larger than its route's `limit`, as `request` refuses it,
 * by what it is (`named`): sent, it was refused before the server read it, and the connection
 * closed with the rest of the body unread - on Windows a reset, which can lose the refusal, and
 * the page then read the server as not answering. */
function tooLarge(named: string, size: number, limit: number): ApiError {
  return new ApiError(
    413,
    TOO_LARGE,
    `${named} cannot be sent in one request: its body needs ${size} bytes, and ddd gui reads ` +
      `at most ${limit}`,
  );
}

/** How many bytes `body` is sent as: its UTF-8, which `fetch` sends a string body in - what its
 * `Content-Length` counts, and what the server measures against its limit. */
function bytesOf(body: string | undefined): number {
  return body === undefined ? 0 : new TextEncoder().encode(body).byteLength;
}

export async function request<T>(
  path: string,
  init: Ask = {},
  fetchImpl: Fetch = fetch,
  kept: Keeper = token,
  out: SignedOut = signedOut,
): Promise<T> {
  // Refused before it is sent, as the server would refuse it: no line past its limit is sent, and
  // no body past the most the server reads of one sent to its route.
  const limit = addressLimit(init.method);
  if (path.length > limit) throw tooLong(path, limit);
  const { named, ...sent } = init;
  const size = bytesOf(sent.body);
  const most = bodyLimit(path);
  if (size > most) throw tooLarge(named ?? pathOf(path), size, most);
  // The token goes as a header, and no cookie goes at all: a browser sends a cookie to every
  // port of 127.0.0.1, so to every other server there too (part 18b).
  const held = kept.get();
  const headers =
    held === null ? sent.headers : { ...sent.headers, Authorization: `Bearer ${held}` };
  const send = () =>
    fetchImpl(path, {
      ...sent,
      credentials: "omit",
      ...(headers === undefined ? {} : { headers }),
    });
  let response: Response;
  try {
    // Once more where the first got no answer at all (`sentAgain`): on Windows a request was seen
    // refused a socket (`net::ERR_NO_BUFFER_SPACE`, part 19a) while the server answered every
    // other, and a second rejection is the server gone.
    response = await send().catch((error: unknown) => {
      if (!sentAgain(init.method, error)) throw error;
      return send();
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ServerUnreachable(error);
  }
  const body: unknown = await response.json().catch(() => NOT_JSON);
  if (!response.ok) {
    if (response.status === 401) {
      // Refused: the token this ask carried is stale, or there was none. Cleared only if the
      // keeper still holds that same token - between the send and this answer another tab may
      // have stored a newer one, which this ask's 401 says nothing about and must not clear
      // (M-1). The page is marked signed out either way; nothing asks again on its own, and
      // other tabs follow on their next ask, since they read the same storage.
      if (kept.get() === held) kept.clear();
      out.mark();
    }
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
      UNPARSED,
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

/** The open project's state: at once where `after` is `null`; else as soon as its version is past
 * `after` - a version, which moves at every change the state can say, not a revision - or once
 * the server has waited as long as it waits. */
export const getState = (after: number | null, signal?: AbortSignal, fetchImpl: Fetch = fetch) =>
  request<State>(
    `/api/state${queryOf<StateQuery>(after === null ? {} : { after })}`,
    signal === undefined ? {} : { signal },
    fetchImpl,
  );

/** Which of the newest revision's findings `GET /api/findings` answers - `FindingsQuery`, the
 * server's own model of the query: from `offset` - the first when left out - at most `limit` of
 * them, or every one from it when left out, of those `severity`, `file`, `check` and `text`
 * leave. */
export const getFindings = (query: FindingsQuery, fetchImpl: Fetch = fetch) =>
  request<FindingsReply>(`/api/findings${findingsQuery(query)}`, {}, fetchImpl);

/** A page's query: each parameter given, encoded, in a fixed order; nothing for one left out. */
function findingsQuery(query: FindingsQuery): string {
  const parts: [string, string][] = [];
  if (query.offset !== undefined) parts.push(["offset", String(query.offset)]);
  if (query.limit !== undefined) parts.push(["limit", String(query.limit)]);
  if (query.severity !== undefined) parts.push(["severity", query.severity]);
  if (query.file !== undefined) parts.push(["file", query.file]);
  if (query.check !== undefined) parts.push(["check", query.check]);
  if (query.text !== undefined) parts.push(["text", query.text]);
  if (parts.length === 0) return "";
  return `?${parts.map(([key, value]) => `${key}=${encoded(value)}`).join("&")}`;
}

export const getFile = (path: string, fetchImpl: Fetch = fetch) =>
  request<FileContent>(`/api/file${queryOf<FileQuery>({ path })}`, {}, fetchImpl);

export const getGraph = (fetchImpl: Fetch = fetch) =>
  request<GraphReply>("/api/graph", {}, fetchImpl);

export const getVariable = (name: string, fetchImpl: Fetch = fetch) =>
  request<VariableReply>(`/api/variable${queryOf<VariableQuery>({ name })}`, {}, fetchImpl);

/** The variables whose names hold `text`, whatever its case, as the masthead's go-to lists them:
 * the one it spells exactly first, at most fifty, and how many hold it in all. */
export const getNames = (text: string, fetchImpl: Fetch = fetch) =>
  request<NamesReply>(`/api/names${queryOf<NamesQuery>({ text })}`, {}, fetchImpl);

export const getUnits = (fetchImpl: Fetch = fetch) =>
  request<UnitsReply>("/api/units", {}, fetchImpl);

/** The preview of settling `key` on every declaration of `name`: without `raw`, the key is to go
 * from every declaration. */
export const getSettle = (
  name: string,
  key: string,
  raw: string | null,
  fetchImpl: Fetch = fetch,
) =>
  request<SettleReply>(
    `/api/settle${queryOf<SettleQuery>(raw === null ? { name, key } : { name, key, raw })}`,
    {},
    fetchImpl,
  );

export const getFix = (file: string, pointer: string, check: string, fetchImpl: Fetch = fetch) =>
  request<FixReply>(`/api/fix${queryOf<FixQuery>({ file, pointer, check })}`, {}, fetchImpl);

export const getCompare = (baseline: string, fetchImpl: Fetch = fetch) =>
  request<CompareReply>(`/api/compare${queryOf<CompareQuery>({ baseline })}`, {}, fetchImpl);

/** One change to the project's units, as `GET /api/unit-plan` takes it: `UnitPlanQuery`, the
 * server's own model of the query - one model per action, what each needs and nothing it does
 * not. */
export type UnitPlanRequest = UnitPlanQuery;

export const getUnit = (name: string, fetchImpl: Fetch = fetch) =>
  request<UnitReply>(`/api/unit${queryOf<UnitQuery>({ name })}`, {}, fetchImpl);

export const getUnitPlan = (plan: UnitPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/unit-plan${queryOf<UnitPlanQuery>(plan)}`, {}, fetchImpl);

export const getTypes = (fetchImpl: Fetch = fetch) =>
  request<TypesReply>("/api/types", {}, fetchImpl);

export const getType = (name: string, fetchImpl: Fetch = fetch) =>
  request<TypeReply>(`/api/type${queryOf<TypeQuery>({ name })}`, {}, fetchImpl);

/** A plan as the page holds one: its route's query - `Q`, the server's own model of it - but for a
 * `set`'s `raw`, which may be `null` as well as left out. Both mean the key is to go, which the
 * query says by carrying no `raw` at all (`held`). */
type Held<Q> = Q extends { action: "set" } ? Omit<Q, "raw"> & { raw?: string | null } : Q;

/** One change to a type, as `GET /api/type-plan` takes it: `TypePlanQuery`, the server's own model
 * of the query, a `set`'s `raw` given as `null` where the key is to go (`Held`). */
export type TypePlanRequest = Held<TypePlanQuery>;

export const getTypePlan = (plan: TypePlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/type-plan${queryOf(held<TypePlanQuery>(plan))}`, {}, fetchImpl);

export const getShared = (fetchImpl: Fetch = fetch) =>
  request<SharedReply>("/api/shared", {}, fetchImpl);

export const getConstant = (name: string, fetchImpl: Fetch = fetch) =>
  request<ConstantReply>(`/api/constant${queryOf<ConstantQuery>({ name })}`, {}, fetchImpl);

/** One change to a constant, as `GET /api/constant-plan` takes it: `ConstantPlanQuery`, the
 * server's own model of the query, a `set`'s `raw` given as `null` where the key is to go
 * (`Held`) - `add`'s `raw` is a value it cannot go without, the way `set`'s can be asked for
 * before a reader has typed anything into the value field. */
export type ConstantPlanRequest = Held<ConstantPlanQuery>;

export const getConstantPlan = (plan: ConstantPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/constant-plan${queryOf(held<ConstantPlanQuery>(plan))}`, {}, fetchImpl);

export const getSection = (name: string, fetchImpl: Fetch = fetch) =>
  request<SectionReply>(`/api/section${queryOf<SectionQuery>({ name })}`, {}, fetchImpl);

/** One change to a section, as `GET /api/section-plan` takes it: `SectionPlanQuery`, the server's
 * own model of the query, a `set`'s `raw` given as `null` where the key is to go (`Held`). The
 * same four verbs as `ConstantPlanRequest`, differing only in `add` - a section is declared with
 * one json text per required key (`access`, then `alignment`, the order
 * `ddd.gui.api._required_keys` reads off `Vocabulary.keys`) rather than a lone `raw`, because a
 * section the model gives no default for either key is one whose file would not load. */
export type SectionPlanRequest = Held<SectionPlanQuery>;

export const getSectionPlan = (plan: SectionPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/section-plan${queryOf(held<SectionPlanQuery>(plan))}`, {}, fetchImpl);

export const getRaster = (name: string, fetchImpl: Fetch = fetch) =>
  request<RasterReply>(`/api/raster${queryOf<RasterQuery>({ name })}`, {}, fetchImpl);

/** One change to a raster, as `GET /api/raster-plan` takes it: `RasterPlanQuery`, the server's own
 * model of the query, a `set`'s `raw` given as `null` where the key is to go (`Held`). The same
 * four verbs as `SectionPlanRequest`, differing only in `add` - a raster is declared with the one
 * json text for the one key the model gives no default for (`event`) rather than the two
 * `access`/`alignment` a section needs, because `RASTERS.required` is `event` alone: `cycle` is
 * optional and `description` defaults, so neither is `add`'s to supply. */
export type RasterPlanRequest = Held<RasterPlanQuery>;

export const getRasterPlan = (plan: RasterPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/raster-plan${queryOf(held<RasterPlanQuery>(plan))}`, {}, fetchImpl);

export const getFiles = (fetchImpl: Fetch = fetch) =>
  request<FilesReply>("/api/files", {}, fetchImpl);

/** One change to the project's own files, as `GET /api/files-plan` takes it: `FilesPlanQuery`,
 * the server's own model of the query - what each action needs, and nothing it does not.
 * `create`'s `component` is a new component's own name, read only for a `kind` of `"component"`
 * and ignored for every other: `ddd.file_plans.create_plan`'s own rule, stated in
 * `ddd.gui.queries.CreateFile`'s docstring. `add`'s `path` is typed relative to the project
 * description or absolute, the way a reader spells an `includes` entry; `remove`'s is a row's own
 * absolute key (`IncludedEntryReply.key`, or one of a pattern's own `files`) - one field name, two
 * different shapes of path, because that is what the two actions each take a path *as*. */
export type FilesPlanRequest = FilesPlanQuery;

export const getFilesPlan = (plan: FilesPlanRequest, fetchImpl: Fetch = fetch) =>
  request<FilesPlanReply>(`/api/files-plan${queryOf<FilesPlanQuery>(plan)}`, {}, fetchImpl);

export const getDeclarable = (file: string, fetchImpl: Fetch = fetch) =>
  request<DeclarableReply>(`/api/declarable${queryOf<DeclarableQuery>({ file })}`, {}, fetchImpl);

/** One change to a component's interface, as `GET /api/declaration-plan` takes it:
 * `DeclarationPlanQuery`, the server's own model of the query. */
export type DeclarationPlanRequest = DeclarationPlanQuery;

export const getDeclarationPlan = (plan: DeclarationPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/declaration-plan${queryOf<DeclarationPlanQuery>(plan)}`, {}, fetchImpl);

/** What describing one component's declaration of a variable takes, as `GET /api/description-plan`
 * takes it: `DescriptionPlanQuery`, the server's own model of the query - the description is the
 * declaration's own, in the file given, and the empty text takes it away. */
export type DescriptionPlanRequest = DescriptionPlanQuery;

export const getDescriptionPlan = (plan: DescriptionPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/description-plan${queryOf<DescriptionPlanQuery>(plan)}`, {}, fetchImpl);

/** An edit, answered once written: its number is noted into `edits`, the page's own by default, as
 * soon as the answer arrives, with its label and the files it wrote, for the heading to say - a
 * refused edit notes nothing. One whose body is larger than ddd gui reads is refused unsent, by
 * its label (`request`). */
export const postEdit = async (
  changes: Changes,
  fetchImpl: Fetch = fetch,
  edits: OwnEdits = ownEdits,
): Promise<EditReply> => {
  const reply = await request<EditReply>(
    "/api/edit",
    { ...post(changes), named: changes.label },
    fetchImpl,
  );
  edits.wrote(reply.edit, {
    kind: "wrote",
    label: changes.label,
    files: reply.files.map((file) => file.path),
  });
  return reply;
};

export const getUndo = (fetchImpl: Fetch = fetch) =>
  request<UndoPreview>("/api/undo", {}, fetchImpl);

/** An undo of the edit numbered `at`, answered once the files are back: its number is noted into
 * `edits` as an edit's is, with the edit it put back and, where told, what that was
 * (`putBack`: the preview's label and files), for the heading to say. */
export const postUndo = async (
  at: number,
  fetchImpl: Fetch = fetch,
  edits: OwnEdits = ownEdits,
  putBack?: Write,
): Promise<UndoReply> => {
  const reply = await request<UndoReply>("/api/undo", post({ at }), fetchImpl);
  edits.undid(at, reply.edit, putBack);
  return reply;
};

export const getValues = (name: string, fetchImpl: Fetch = fetch) =>
  request<ValuesReply>(`/api/values${queryOf<ValuesQuery>({ name })}`, {}, fetchImpl);

/** One cell's change, as `GET /api/value-plan` takes it. */
export interface ValuePlanRequest {
  name: string;
  /** `[2]` or `[1][3]` - the element, as a json pointer suffix. */
  at: string;
  /** The raw count to store, already converted from what was typed. */
  raw: number;
}

/** The cell's change as its query takes it - `ValuePlanQuery`, the server's own model of it - the
 * count spelled as the number it is. */
export const getValuePlan = (plan: ValuePlanRequest, fetchImpl: Fetch = fetch) => {
  const query = queryOf<ValuePlanQuery>({ name: plan.name, at: plan.at, raw: String(plan.raw) });
  return request<PlanReply>(`/api/value-plan${query}`, {}, fetchImpl);
};

/** Several cells' change, as `GET /api/cells-plan` takes it: each element, as `[2]` or `[1][3]`,
 * and the raw count to store there. */
export interface CellsPlanRequest {
  name: string;
  cells: readonly { at: string; raw: number }[];
}

/** The cells' change as its query takes it - `CellsPlanQuery`, the server's own model of it - the
 * elements and the counts each joined by commas, in the same order. It costs the cells' own
 * digits alone, whatever the size of their object, where a whole table's counts can outgrow an
 * address (`getValuesPlan`). */
export const getCellsPlan = (plan: CellsPlanRequest, fetchImpl: Fetch = fetch) => {
  const query = queryOf<CellsPlanQuery>({
    name: plan.name,
    at: plan.cells.map((cell) => cell.at).join(","),
    raw: plan.cells.map((cell) => String(cell.raw)).join(","),
  });
  return request<PlanReply>(`/api/cells-plan${query}`, {}, fetchImpl);
};

/** A whole table's change, as `GET /api/values-plan` takes it: the counts row-major, in one list. */
export interface ValuesPlanRequest {
  name: string;
  raw: readonly number[];
}

/** The table's change as its query takes it - `ValuesPlanQuery`, the server's own model of it - the
 * counts joined by commas. */
export const getValuesPlan = async (plan: ValuesPlanRequest, fetchImpl: Fetch = fetch) => {
  const query = queryOf<ValuesPlanQuery>({ name: plan.name, raw: plan.raw.join(",") });
  const address = `/api/values-plan${query}`;
  // Refused before it is asked for, as `request` refuses any address too long, but in a sentence
  // of its own: a table past about 10,000 counts is not one ddd gui takes (decision 3.6). A count
  // costs its own characters and the three of the `%2C` before it, so a table of five-digit
  // counts outgrows the address past about 8,000 of them - a 90 by 90 one is asked for, a 91 by
  // 91 one refused - and one of one-digit counts past about 16,000. A float's count is the
  // shortest spelling of its float (`rawCount`): about as long as the value typed, where a short
  // decimal reads back as it, and up to seventeen digits where none does. The shape of the
  // block cannot bound this - the object's own shape is what makes it large.
  if (address.length > addressLimit("GET")) {
    throw new ApiError(
      414,
      TOO_LONG,
      `'${plan.name}' has too many values to plan at once: a table past about 10,000 counts is ` +
        "not one ddd gui takes; set its values cell by cell, or in its file in an editor",
    );
  }
  return request<PlanReply>(address, {}, fetchImpl);
};

/** A plan as its query carries it: a `set`'s `raw` of `null` - the key to go - left out, which is
 * how the query says so (`Held`). */
function held<Q extends object>(plan: Held<Q>): Q {
  return Object.fromEntries(Object.entries(plan).filter(([, value]) => value !== null)) as Q;
}

/** A query string: `?`, then each parameter of `query` in the order it is written, its value
 * encoded - or nothing, for a query of none. Given the type of the route's query, the server's
 * own model of it (`ddd.gui.queries`), so that a parameter it does not take, or one it requires
 * left out, fails the type check rather than reaching the server. */
function queryOf<Q extends object>(query: Q): string {
  const parts = Object.entries(query).map(([key, value]) => `${key}=${encoded(String(value))}`);
  return parts.length === 0 ? "" : `?${parts.join("&")}`;
}

/** A query's value as a browser sends it: `encodeURIComponent`'s spelling, and `'` as `%27` - of
 * the characters `encodeURIComponent` leaves as they are, the one a browser encodes in the query of
 * an http address (the URL standard's special-query set). So the address the page holds is, byte
 * for byte, the one sent, and `request` measures what is sent (3:I8). */
function encoded(value: string): string {
  return encodeURIComponent(value).replace(/'/g, "%27");
}

function post(body: unknown): Ask {
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
