import { describe, expect, test, vi } from "vitest";
import { OwnEdits, ownEdits } from "../state/edits";
import {
  ApiError,
  askedAgain,
  EDIT_BODY,
  getCellsPlan,
  getCompare,
  getConstant,
  getConstantPlan,
  getDeclarable,
  getDeclarationPlan,
  getDescriptionPlan,
  getFile,
  getFiles,
  getFilesPlan,
  getFindings,
  getFix,
  getGraph,
  getNames,
  getProjects,
  getRaster,
  getRasterPlan,
  getSection,
  getSectionPlan,
  getSession,
  getSettle,
  getShared,
  getState,
  getType,
  getTypePlan,
  getTypes,
  getUndo,
  getUnit,
  getUnitPlan,
  getUnits,
  getValuePlan,
  getValues,
  getValuesPlan,
  getVariable,
  openProject,
  postEdit,
  postUndo,
  request,
  ServerUnreachable,
  sentAgain,
} from "./client";
import { keeperOver, signedOutStore } from "./token";
import type { Changes } from "./types";

function answering(status: number, body: string) {
  return vi.fn(async (_path: string, _init?: RequestInit) => new Response(body, { status }));
}

/** A fetch answering `{}` to anything, exposing the calls it recorded - `getValuesPlan`'s own
 * test needs nothing richer than the one path it asked for. */
function recorded() {
  const fetch = answering(200, "{}");
  return { fetch, urls: fetch.mock.calls };
}

describe("requests to the server", () => {
  test("a success is its parsed body, asked for with no cookie", async () => {
    const fetchImpl = answering(200, '{"version": "0.10.0"}');
    await expect(request("/api/session", {}, fetchImpl)).resolves.toEqual({ version: "0.10.0" });
    expect(fetchImpl).toHaveBeenCalledWith("/api/session", { credentials: "omit" });
  });

  test("a refusal carries the code and message the server gave", async () => {
    const refused = request(
      "/api/edit",
      {},
      answering(409, '{"error": "stale", "message": "changed"}'),
    );
    await expect(refused).rejects.toMatchObject({ status: 409, code: "stale", message: "changed" });
    await expect(refused).rejects.toBeInstanceOf(ApiError);
  });

  test("a success whose body is not json is refused with a code of its own", async () => {
    // Read as null, it reached a screen that read a property of it, and the page went blank.
    const answered = request("/api/file?path=a.ddd.json", {}, answering(200, '{"limit": NaN}'));
    await expect(answered).rejects.toBeInstanceOf(ApiError);
    await expect(answered).rejects.toMatchObject({
      status: 200,
      code: "not-json",
      message: "ddd gui's answer to /api/file is not json",
    });
  });

  test("a success whose body is json's null is that null", async () => {
    await expect(request("/api/dictionary", {}, answering(200, "null"))).resolves.toBeNull();
  });

  test("a failure without the server's error shape is named by its status", async () => {
    const failed = request("/api/state", {}, answering(502, "Bad Gateway"));
    await expect(failed).rejects.toMatchObject({ status: 502, code: "http-502" });
  });

  test("a server that does not answer is unreachable", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(request("/api/state", {}, fetchImpl)).rejects.toBeInstanceOf(ServerUnreachable);
  });

  test("an aborted request stays aborted", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new DOMException("aborted", "AbortError");
    });
    await expect(request("/api/state", {}, fetchImpl)).rejects.toMatchObject({
      name: "AbortError",
    });
  });

  test("a GET whose first fetch got no answer is sent once more, and answered", async () => {
    let sends = 0;
    const fetchImpl = vi.fn(async () => {
      sends += 1;
      if (sends === 1) throw new TypeError("fetch failed");
      return new Response("{}", { status: 200 });
    });
    await expect(request("/api/state", {}, fetchImpl)).resolves.toEqual({});
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  test("a GET sent again carries the first send's very own init, signal included", async () => {
    let sends = 0;
    const fetchImpl = vi.fn(async (_path: string, _init?: RequestInit) => {
      sends += 1;
      if (sends === 1) throw new TypeError("fetch failed");
      return new Response("{}", { status: 200 });
    });
    const controller = new AbortController();
    const init = { headers: { "X-Test": "a" }, signal: controller.signal };
    await expect(request("/api/state", init, fetchImpl)).resolves.toEqual({});
    expect(fetchImpl.mock.calls[1]?.[1]).toEqual(fetchImpl.mock.calls[0]?.[1]);
    expect(fetchImpl.mock.calls[0]?.[1]?.signal).toBe(controller.signal);
  });

  test("a GET whose fetch got no answer twice is unreachable, after two sends", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(request("/api/state", {}, fetchImpl)).rejects.toBeInstanceOf(ServerUnreachable);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  test("a POST whose fetch got no answer is never sent again", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(
      request("/api/edit", { method: "POST", body: "{}" }, fetchImpl),
    ).rejects.toBeInstanceOf(ServerUnreachable);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("an aborted GET is never sent again", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new DOMException("aborted", "AbortError");
    });
    await expect(request("/api/state", {}, fetchImpl)).rejects.toMatchObject({
      name: "AbortError",
    });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("a GET answered with an error is never sent again", async () => {
    const fetchImpl = answering(500, JSON.stringify({ error: "internal", message: "failed" }));
    await expect(request("/api/state", {}, fetchImpl)).rejects.toMatchObject({ status: 500 });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("each call asks the path and method the api expects", async () => {
    // An empty answer to each, but for the files an edit's reply always lists.
    const fetchImpl = answering(200, '{"files": []}');
    const signal = new AbortController().signal;
    await getSession(fetchImpl);
    await getProjects(fetchImpl);
    await openProject("C:/p/p.ddd.json", fetchImpl);
    await getState(null, undefined, fetchImpl);
    await getState(3, signal, fetchImpl);
    await getFile("C:/p/a b.ddd.json", fetchImpl);
    await getGraph(fetchImpl);
    await getVariable("Value A", fetchImpl);
    await getUnits(fetchImpl);
    await getSettle("ValueA", "unit", '"%"', fetchImpl);
    await getSettle("ValueA", "unit", null, fetchImpl);
    await getFix("a.ddd.json", "component.interface[0].definition", "missing-id", fetchImpl);
    await getCompare("C:/p/baseline copy.json", fetchImpl);
    await getUnit("°C", fetchImpl);
    await getUnitPlan({ action: "rename", unit: "RPM", to: "rpm" }, fetchImpl);
    await getUnitPlan({ action: "add", unit: "m/s" }, fetchImpl);
    await getUnitPlan({ action: "remove", unit: "kPa" }, fetchImpl);
    await getUnitPlan(
      { action: "describe", unit: "rpm", description: "rotational speed, 1/min" },
      fetchImpl,
    );
    await getUnitPlan({ action: "adopt" }, fetchImpl);
    await getTypes(fetchImpl);
    await getType("Temperature_t", fetchImpl);
    await getTypePlan({ action: "set", name: "Temperature_t", key: "unit", raw: '"K"' }, fetchImpl);
    await getTypePlan({ action: "set", name: "Temperature_t", key: "unit", raw: null }, fetchImpl);
    await getTypePlan({ action: "rename", name: "Sensor_t", to: "Probe_t" }, fetchImpl);
    await getShared(fetchImpl);
    await getConstant("TREND SAMPLES#1", fetchImpl);
    await getConstantPlan(
      { action: "set", name: "TREND_SAMPLES", key: "value", raw: "16" },
      fetchImpl,
    );
    await getConstantPlan({ action: "set", name: "TREND_SAMPLES", key: "description" }, fetchImpl);
    await getConstantPlan(
      { action: "set", name: "TREND_SAMPLES", key: "description", raw: null },
      fetchImpl,
    );
    await getConstantPlan(
      { action: "rename", name: "TREND_SAMPLES", to: "TREND_SLOTS" },
      fetchImpl,
    );
    await getConstantPlan({ action: "add", name: "CELLS", raw: "8" }, fetchImpl);
    await getConstantPlan({ action: "remove", name: "CELLS" }, fetchImpl);
    // A section's name carries a leading dot, unlike a constant's, and may carry a `$` too
    // (`SECTION_NAME_PATTERN`) - `.calib$1` proves both that the dot survives encoding untouched
    // and that a character encoding must actually change (`$` to `%24`) is not skipped.
    await getSection(".calib$1", fetchImpl);
    await getSectionPlan(
      { action: "set", name: ".calib", key: "access", raw: '"read-only"' },
      fetchImpl,
    );
    await getSectionPlan({ action: "set", name: ".calib", key: "alignment" }, fetchImpl);
    await getSectionPlan({ action: "set", name: ".calib", key: "alignment", raw: null }, fetchImpl);
    await getSectionPlan({ action: "rename", name: ".calib", to: ".trend" }, fetchImpl);
    await getSectionPlan(
      { action: "add", name: ".calib", access: '"read-only"', alignment: "4" },
      fetchImpl,
    );
    await getSectionPlan({ action: "remove", name: ".calib" }, fetchImpl);
    await getRaster("10ms", fetchImpl);
    await getRasterPlan({ action: "set", name: "10ms", key: "cycle", raw: '"20ms"' }, fetchImpl);
    await getRasterPlan({ action: "set", name: "10ms", key: "description" }, fetchImpl);
    await getRasterPlan({ action: "set", name: "10ms", key: "description", raw: null }, fetchImpl);
    await getRasterPlan({ action: "rename", name: "10ms", to: "20ms" }, fetchImpl);
    await getRasterPlan({ action: "add", name: "10ms", event: "1" }, fetchImpl);
    await getRasterPlan({ action: "remove", name: "10ms" }, fetchImpl);
    await getFiles(fetchImpl);
    await getFilesPlan({ action: "create", kind: "types", name: "sizes" }, fetchImpl);
    await getFilesPlan(
      { action: "create", kind: "component", name: "pump", component: "Pump" },
      fetchImpl,
    );
    await getFilesPlan({ action: "add", path: "sensors/a.ddd.json" }, fetchImpl);
    await getFilesPlan({ action: "remove", path: "/tmp/p/a.ddd.json" }, fetchImpl);
    await getDeclarable("/tmp/c.ddd.json", fetchImpl);
    await getDeclarationPlan(
      { action: "read", file: "/tmp/c.ddd.json", name: "ValueC", scope: "input" },
      fetchImpl,
    );
    await getDeclarationPlan(
      { action: "remove", file: "/tmp/c.ddd.json", name: "ValueA" },
      fetchImpl,
    );
    await getDeclarationPlan(
      { action: "declare", file: "/tmp/c.ddd.json", scope: "output", definition: '{"name":"P"}' },
      fetchImpl,
    );
    await getDescriptionPlan(
      { file: "/tmp/c.ddd.json", name: "ParameterA", description: "a gain" },
      fetchImpl,
    );
    await getDescriptionPlan(
      { file: "/tmp/c.ddd.json", name: "ParameterA", description: "" },
      fetchImpl,
    );
    // Noted into an instance of their own: this fetch's answer carries no number.
    await postEdit(
      {
        changes: [{ file: "a", fingerprint: "x", operations: [{ op: "remove", pointer: "a" }] }],
        label: "the unit of ValueA",
      },
      fetchImpl,
      new OwnEdits(),
    );
    await getUndo(fetchImpl);
    await postUndo(3, fetchImpl, new OwnEdits());
    await getValues("CurveA", fetchImpl);
    await getValuePlan({ name: "CurveA", at: "[2]", raw: 750 }, fetchImpl);
    await getValuePlan({ name: "ParameterA", at: "", raw: 4000 }, fetchImpl);
    expect(fetchImpl.mock.calls).toEqual([
      ["/api/session", { credentials: "omit" }],
      ["/api/projects", { credentials: "omit" }],
      [
        "/api/open",
        {
          credentials: "omit",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: '{"path":"C:/p/p.ddd.json"}',
        },
      ],
      ["/api/state", { credentials: "omit" }],
      ["/api/state?after=3", { credentials: "omit", signal }],
      ["/api/file?path=C%3A%2Fp%2Fa%20b.ddd.json", { credentials: "omit" }],
      ["/api/graph", { credentials: "omit" }],
      ["/api/variable?name=Value%20A", { credentials: "omit" }],
      ["/api/units", { credentials: "omit" }],
      ["/api/settle?name=ValueA&key=unit&raw=%22%25%22", { credentials: "omit" }],
      ["/api/settle?name=ValueA&key=unit", { credentials: "omit" }],
      [
        "/api/fix?file=a.ddd.json&pointer=component.interface%5B0%5D.definition&check=missing-id",
        { credentials: "omit" },
      ],
      ["/api/compare?baseline=C%3A%2Fp%2Fbaseline%20copy.json", { credentials: "omit" }],
      ["/api/unit?name=%C2%B0C", { credentials: "omit" }],
      ["/api/unit-plan?action=rename&unit=RPM&to=rpm", { credentials: "omit" }],
      ["/api/unit-plan?action=add&unit=m%2Fs", { credentials: "omit" }],
      ["/api/unit-plan?action=remove&unit=kPa", { credentials: "omit" }],
      [
        "/api/unit-plan?action=describe&unit=rpm&description=rotational%20speed%2C%201%2Fmin",
        { credentials: "omit" },
      ],
      ["/api/unit-plan?action=adopt", { credentials: "omit" }],
      ["/api/types", { credentials: "omit" }],
      ["/api/type?name=Temperature_t", { credentials: "omit" }],
      [
        "/api/type-plan?action=set&name=Temperature_t&key=unit&raw=%22K%22",
        { credentials: "omit" },
      ],
      ["/api/type-plan?action=set&name=Temperature_t&key=unit", { credentials: "omit" }],
      ["/api/type-plan?action=rename&name=Sensor_t&to=Probe_t", { credentials: "omit" }],
      ["/api/shared", { credentials: "omit" }],
      ["/api/constant?name=TREND%20SAMPLES%231", { credentials: "omit" }],
      [
        "/api/constant-plan?action=set&name=TREND_SAMPLES&key=value&raw=16",
        { credentials: "omit" },
      ],
      ["/api/constant-plan?action=set&name=TREND_SAMPLES&key=description", { credentials: "omit" }],
      ["/api/constant-plan?action=set&name=TREND_SAMPLES&key=description", { credentials: "omit" }],
      [
        "/api/constant-plan?action=rename&name=TREND_SAMPLES&to=TREND_SLOTS",
        { credentials: "omit" },
      ],
      ["/api/constant-plan?action=add&name=CELLS&raw=8", { credentials: "omit" }],
      ["/api/constant-plan?action=remove&name=CELLS", { credentials: "omit" }],
      ["/api/section?name=.calib%241", { credentials: "omit" }],
      [
        "/api/section-plan?action=set&name=.calib&key=access&raw=%22read-only%22",
        { credentials: "omit" },
      ],
      ["/api/section-plan?action=set&name=.calib&key=alignment", { credentials: "omit" }],
      ["/api/section-plan?action=set&name=.calib&key=alignment", { credentials: "omit" }],
      ["/api/section-plan?action=rename&name=.calib&to=.trend", { credentials: "omit" }],
      [
        "/api/section-plan?action=add&name=.calib&access=%22read-only%22&alignment=4",
        { credentials: "omit" },
      ],
      ["/api/section-plan?action=remove&name=.calib", { credentials: "omit" }],
      ["/api/raster?name=10ms", { credentials: "omit" }],
      ["/api/raster-plan?action=set&name=10ms&key=cycle&raw=%2220ms%22", { credentials: "omit" }],
      ["/api/raster-plan?action=set&name=10ms&key=description", { credentials: "omit" }],
      ["/api/raster-plan?action=set&name=10ms&key=description", { credentials: "omit" }],
      ["/api/raster-plan?action=rename&name=10ms&to=20ms", { credentials: "omit" }],
      ["/api/raster-plan?action=add&name=10ms&event=1", { credentials: "omit" }],
      ["/api/raster-plan?action=remove&name=10ms", { credentials: "omit" }],
      ["/api/files", { credentials: "omit" }],
      ["/api/files-plan?action=create&kind=types&name=sizes", { credentials: "omit" }],
      [
        "/api/files-plan?action=create&kind=component&name=pump&component=Pump",
        { credentials: "omit" },
      ],
      ["/api/files-plan?action=add&path=sensors%2Fa.ddd.json", { credentials: "omit" }],
      ["/api/files-plan?action=remove&path=%2Ftmp%2Fp%2Fa.ddd.json", { credentials: "omit" }],
      ["/api/declarable?file=%2Ftmp%2Fc.ddd.json", { credentials: "omit" }],
      [
        "/api/declaration-plan?action=read&file=%2Ftmp%2Fc.ddd.json&name=ValueC&scope=input",
        { credentials: "omit" },
      ],
      [
        "/api/declaration-plan?action=remove&file=%2Ftmp%2Fc.ddd.json&name=ValueA",
        { credentials: "omit" },
      ],
      [
        "/api/declaration-plan?action=declare&file=%2Ftmp%2Fc.ddd.json&scope=output&definition=%7B%22name%22%3A%22P%22%7D",
        { credentials: "omit" },
      ],
      [
        "/api/description-plan?file=%2Ftmp%2Fc.ddd.json&name=ParameterA&description=a%20gain",
        { credentials: "omit" },
      ],
      [
        "/api/description-plan?file=%2Ftmp%2Fc.ddd.json&name=ParameterA&description=",
        { credentials: "omit" },
      ],
      [
        "/api/edit",
        {
          credentials: "omit",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body:
            '{"changes":[{"file":"a","fingerprint":"x","operations":[{"op":"remove","pointer":"a"}]}],' +
            '"label":"the unit of ValueA"}',
        },
      ],
      ["/api/undo", { credentials: "omit" }],
      [
        "/api/undo",
        {
          credentials: "omit",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: '{"at":3}',
        },
      ],
      ["/api/values?name=CurveA", { credentials: "omit" }],
      ["/api/value-plan?name=CurveA&at=%5B2%5D&raw=750", { credentials: "omit" }],
      ["/api/value-plan?name=ParameterA&at=&raw=4000", { credentials: "omit" }],
    ]);
  });

  test("getNames asks for the names holding a text, encoded", async () => {
    const calls = recorded();
    await getNames("C00530_O0000", calls.fetch);
    await getNames("Value E & 'x'", calls.fetch);
    expect(calls.urls).toEqual([
      ["/api/names?text=C00530_O0000", { credentials: "omit" }],
      ["/api/names?text=Value%20E%20%26%20%27x%27", { credentials: "omit" }],
    ]);
  });

  test("getFindings asks for a page, each of its parameters encoded and none it was not given", async () => {
    const calls = recorded();
    await getFindings({}, calls.fetch);
    await getFindings({ offset: 0, limit: 100 }, calls.fetch);
    await getFindings({ offset: 300 }, calls.fetch);
    await getFindings({ file: "C:/p/sensors/a b.ddd.json" }, calls.fetch);
    await getFindings({ file: "C:/p/a.ddd.json", check: "missing-id" }, calls.fetch);
    await getFindings(
      { offset: 100, limit: 100, severity: "error", file: "/p/a&b.ddd.json", check: "a/b" },
      calls.fetch,
    );
    await getFindings({ offset: 0, limit: 100, text: "C00500 & 'x'" }, calls.fetch);
    await getFindings({ check: "missing-id", text: "ValueE" }, calls.fetch);
    expect(calls.urls).toEqual([
      ["/api/findings", { credentials: "omit" }],
      ["/api/findings?offset=0&limit=100", { credentials: "omit" }],
      ["/api/findings?offset=300", { credentials: "omit" }],
      ["/api/findings?file=C%3A%2Fp%2Fsensors%2Fa%20b.ddd.json", { credentials: "omit" }],
      ["/api/findings?file=C%3A%2Fp%2Fa.ddd.json&check=missing-id", { credentials: "omit" }],
      [
        "/api/findings?offset=100&limit=100&severity=error&file=%2Fp%2Fa%26b.ddd.json&check=a%2Fb",
        { credentials: "omit" },
      ],
      ["/api/findings?offset=0&limit=100&text=C00500%20%26%20%27x%27", { credentials: "omit" }],
      ["/api/findings?check=missing-id&text=ValueE", { credentials: "omit" }],
    ]);
  });

  test("getCellsPlan asks for the cells alone, whatever the size of their object", async () => {
    // Two cells of a block of 10240 counts: two elements and two counts, where the block's whole
    // table needs more characters than one address holds.
    const calls = recorded();
    await getCellsPlan(
      {
        name: "Long",
        cells: [
          { at: "[3]", raw: 7 },
          { at: "[9000]", raw: 8 },
        ],
      },
      calls.fetch,
    );
    expect(calls.urls).toEqual([
      ["/api/cells-plan?name=Long&at=%5B3%5D%2C%5B9000%5D&raw=7%2C8", { credentials: "omit" }],
    ]);
  });

  test("getValuesPlan asks for a whole table's plan", async () => {
    const calls = recorded();
    await getValuesPlan({ name: "CurveA", raw: [1300, 950, 850, 800, 750, 700] }, calls.fetch);
    expect(calls.urls).toEqual([
      [
        "/api/values-plan?name=CurveA&raw=1300%2C950%2C850%2C800%2C750%2C700",
        { credentials: "omit" },
      ],
    ]);
  });

  test("a table whose counts outgrow one address is refused, and nothing is asked", async () => {
    // The server reads a request line of at most 65536 bytes and answers 414 beyond it, which
    // the grid would show as `Request-URI Too Long` - true, and no use to a reader holding a
    // table. Nine thousand five-digit counts cost five characters each and three more for the
    // `%2C` before them, which is past the line on its own. A table that large is not one
    // ddd gui takes (decision 3.6), and the sentence says how else to set it.
    const calls = recorded();
    const raw = Array.from({ length: 9000 }, () => 12345);
    const refused = getValuesPlan({ name: "Huge", raw }, calls.fetch);
    await expect(refused).rejects.toBeInstanceOf(ApiError);
    await expect(refused).rejects.toMatchObject({
      status: 414,
      code: "too-long",
      message:
        "'Huge' has too many values to plan at once: a table past about 10,000 counts is not " +
        "one ddd gui takes; set its values cell by cell, or in its file in an editor",
    });
    expect(calls.urls).toEqual([]);
  });

  test("a 90 by 90 table of five-digit counts is asked for, and a 91 by 91 one refused", async () => {
    // Where the values plan's comment says the address runs out: a count of five digits costs
    // eight characters, its `%2C` among them, and the line holds 8,186 of them beside `Map`.
    const calls = recorded();
    const square = (side: number) => ({
      name: "Map",
      raw: Array.from({ length: side * side }, () => 12345),
    });
    await getValuesPlan(square(90), calls.fetch);
    expect(calls.urls).toHaveLength(1);
    await expect(getValuesPlan(square(91), calls.fetch)).rejects.toMatchObject({
      status: 414,
      code: "too-long",
      message:
        "'Map' has too many values to plan at once: a table past about 10,000 counts is not one " +
        "ddd gui takes; set its values cell by cell, or in its file in an editor",
    });
    expect(calls.urls).toHaveLength(1);
  });

  test("any other ask whose address outgrows one request line is refused, naming its route", async () => {
    // A plan of any route asked by GET: a description of seventy thousand characters, which its
    // query carries as they are. Sent, it was answered 414 and shown as `http-414`.
    const calls = recorded();
    const description = "x".repeat(70_000);
    const refused = getDescriptionPlan(
      { file: "/tmp/c.ddd.json", name: "ParameterA", description },
      calls.fetch,
    );
    await expect(refused).rejects.toBeInstanceOf(ApiError);
    await expect(refused).rejects.toMatchObject({
      status: 414,
      code: "too-long",
      message:
        "/api/description-plan cannot be asked in one request: its address needs 70075 " +
        "characters, and ddd gui reads at most 65521",
    });
    expect(calls.urls).toEqual([]);
  });

  test("a GET's address of the line's own limit is sent, and one character more is not", async () => {
    // `GET `, the address, ` HTTP/1.1` and a CRLF: 65536 bytes at most, the address 65521 of them.
    const calls = recorded();
    const at = (length: number) => `/api/state?${"a".repeat(length - "/api/state?".length)}`;
    await request(at(65521), {}, calls.fetch);
    expect(calls.urls).toHaveLength(1);
    await expect(request(at(65522), {}, calls.fetch)).rejects.toMatchObject({
      status: 414,
      message:
        "/api/state cannot be asked in one request: its address needs 65522 characters, and " +
        "ddd gui reads at most 65521",
    });
    expect(calls.urls).toHaveLength(1);
  });

  test("an address its apostrophes carry past the line is refused, counted as it is sent", async () => {
    // A browser sends `'` in the query of an http address as `%27`, three bytes, where
    // `encodeURIComponent` leaves it as it is: counted as one, this address of 65,521 characters
    // as typed was let through, sent as 65,541 and answered 414.
    const calls = recorded();
    const head = "/api/description-plan?file=%2Ftmp%2Fc.ddd.json&name=ParameterA&description=";
    const description = `${"'".repeat(10)}${"x".repeat(65521 - head.length - 10)}`;
    const refused = getDescriptionPlan(
      { file: "/tmp/c.ddd.json", name: "ParameterA", description },
      calls.fetch,
    );
    await expect(refused).rejects.toMatchObject({
      status: 414,
      code: "too-long",
      message:
        "/api/description-plan cannot be asked in one request: its address needs 65541 " +
        "characters, and ddd gui reads at most 65521",
    });
    expect(calls.urls).toEqual([]);
  });

  test("an apostrophe in a query is asked for as %27, as a browser sends it", async () => {
    // Both builders of a query: the routes' own (`queryOf`) and the findings page's.
    const calls = recorded();
    await getDescriptionPlan(
      { file: "/tmp/c.ddd.json", name: "ParameterA", description: "the driver's" },
      calls.fetch,
    );
    await getFindings({ file: "C:/p/o'brien.ddd.json" }, calls.fetch);
    expect(calls.urls).toEqual([
      [
        "/api/description-plan?file=%2Ftmp%2Fc.ddd.json&name=ParameterA&description=the%20driver%27s",
        { credentials: "omit" },
      ],
      ["/api/findings?file=C%3A%2Fp%2Fo%27brien.ddd.json", { credentials: "omit" }],
    ]);
  });

  test("a POST's address is held to its own line, one byte shorter for its method", async () => {
    const calls = recorded();
    const address = `/api/edit?${"a".repeat(65521 - "/api/edit?".length)}`;
    await expect(request(address, { method: "POST" }, calls.fetch)).rejects.toMatchObject({
      status: 414,
      message:
        "/api/edit cannot be asked in one request: its address needs 65521 characters, and " +
        "ddd gui reads at most 65520",
    });
    expect(calls.urls).toEqual([]);
  });
});

describe("an edit's body", () => {
  /** The most ddd gui reads of `POST /api/edit`'s body: `EDIT_BODY`, gui/server.py, 8 MiB. */
  const LIMIT = 8_388_608;

  /** What the rename of a unit stated in many files is called, as the units panel labels it. */
  const LABEL = "the rename of 'Nm' to 'N·m'";

  /** An edit whose body, as `postEdit` sends it, is `bytes` bytes long, its one file's path
   * spelled with `filler` - one byte in UTF-8, or `·`, two - as far as it takes. */
  function editOf(bytes: number, filler = "x"): Changes {
    const of = (path: string): Changes => ({
      changes: [{ file: path, fingerprint: "x", operations: [{ op: "remove", pointer: "a" }] }],
      label: LABEL,
    });
    const rest = new TextEncoder().encode(JSON.stringify(of(""))).length;
    const each = new TextEncoder().encode(filler).length;
    return of(filler.repeat((bytes - rest) / each));
  }

  /** An edit's body as `postEdit` sends it, in UTF-8 bytes. */
  const sent = (changes: Changes) => new TextEncoder().encode(JSON.stringify(changes)).length;

  /** A fetch answering an edit as the server answers one it wrote. */
  const written = () => answering(200, '{"edit": 4, "files": []}');

  test("is at most what ddd gui reads of one", () => {
    expect(EDIT_BODY).toBe(LIMIT);
  });

  test("past that is refused before it is sent, naming the edit", async () => {
    // Sent, it was refused before the server read it, and the connection closed with the rest of
    // the body unread: on Windows a reset, which can lose the refusal, and the page read the
    // server as not answering.
    const fetch = written();
    const edit = editOf(LIMIT + 1);
    expect(sent(edit)).toBe(8_388_609);
    const refused = postEdit(edit, fetch, new OwnEdits());
    await expect(refused).rejects.toBeInstanceOf(ApiError);
    await expect(refused).rejects.toMatchObject({
      status: 413,
      code: "too-large",
      message:
        "the rename of 'Nm' to 'N·m' cannot be sent in one request: its body needs 8388609 " +
        "bytes, and ddd gui reads at most 8388608",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  test("of the limit's own size is sent, as written", async () => {
    const fetch = written();
    const edit = editOf(LIMIT);
    expect(sent(edit)).toBe(LIMIT);
    await postEdit(edit, fetch, new OwnEdits());
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[1]).toEqual({
      credentials: "omit",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(edit),
    });
  });

  test("is measured in the bytes it is sent in, where its characters are fewer", async () => {
    // A path of two-byte characters, past the limit only as UTF-8 bytes.
    const fetch = written();
    const edit = editOf(LIMIT + 1, "·");
    expect(sent(edit)).toBe(8_388_609);
    expect(JSON.stringify(edit).length).toBeLessThan(LIMIT);
    await expect(postEdit(edit, fetch, new OwnEdits())).rejects.toMatchObject({
      status: 413,
      message:
        "the rename of 'Nm' to 'N·m' cannot be sent in one request: its body needs 8388609 " +
        "bytes, and ddd gui reads at most 8388608",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  test("any other ask's body past it is refused the same way, naming its route", async () => {
    const fetch = written();
    const body = "x".repeat(LIMIT + 1);
    await expect(request("/api/undo", { method: "POST", body }, fetch)).rejects.toMatchObject({
      status: 413,
      code: "too-large",
      message:
        "/api/undo cannot be sent in one request: its body needs 8388609 bytes, and ddd gui " +
        "reads at most 8388608",
    });
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("askedAgain", () => {
  /** What `request` answers `body` with, at `status`: the error it throws. */
  async function failedWith(status: number, body: string): Promise<unknown> {
    return request("/api/state", {}, answering(status, body)).catch((error: unknown) => error);
  }

  test("a 503 carrying the server's own busy sentence is asked again", async () => {
    // A connection past the most ddd gui answers at once (`BUSY`, gui/server.py), whose words say
    // to ask again in a moment.
    const error = await failedWith(
      503,
      JSON.stringify({
        error: "busy",
        message:
          "ddd gui is answering as many connections as it takes at once; ask again in a moment",
      }),
    );
    expect(error).toMatchObject({ status: 503, code: "busy" });
    expect(askedAgain(error)).toBe(true);
  });

  test("any 5xx is asked again, the server's own error shape or none", async () => {
    expect(askedAgain(await failedWith(500, '{"error": "internal", "message": "failed"}'))).toBe(
      true,
    );
    expect(askedAgain(await failedWith(502, "Bad Gateway"))).toBe(true);
  });

  test("an answer cut half way, whose body does not parse, is asked again", async () => {
    const error = await failedWith(200, '{"revision": 3, "vers');
    expect(error).toMatchObject({ status: 200, code: "not-json" });
    expect(askedAgain(error)).toBe(true);
  });

  test("no answer at all is asked again", () => {
    expect(askedAgain(new ServerUnreachable(new TypeError("fetch failed")))).toBe(true);
  });

  test("a refusal, a 4xx, is not: asked again, it is answered again", async () => {
    expect(askedAgain(await failedWith(409, '{"error": "no-project", "message": "no"}'))).toBe(
      false,
    );
    expect(askedAgain(await failedWith(404, '{"error": "not-found", "message": "no"}'))).toBe(
      false,
    );
    // Cut or not json, a refusal is still one: its status says so.
    expect(askedAgain(await failedWith(400, "Bad Request"))).toBe(false);
    // Nor what `request` refuses itself, as the server would have answered it.
    expect(askedAgain(new ApiError(414, "too-long", "too long"))).toBe(false);
  });

  test("nor an abort, which the page asked for itself, nor anything else thrown", () => {
    expect(askedAgain(new DOMException("aborted", "AbortError"))).toBe(false);
    expect(askedAgain(new TypeError("x is undefined"))).toBe(false);
    expect(askedAgain("failed")).toBe(false);
  });
});

describe("sentAgain", () => {
  test("a GET whose fetch got no answer is sent again, its method named or not", () => {
    expect(sentAgain(undefined, new TypeError("x"))).toBe(true);
    expect(sentAgain("get", new TypeError("x"))).toBe(true);
  });

  test("a POST whose fetch got no answer is not", () => {
    expect(sentAgain("POST", new TypeError("x"))).toBe(false);
  });

  test("an abort is not, a GET's included", () => {
    expect(sentAgain(undefined, new DOMException("aborted", "AbortError"))).toBe(false);
  });
});

describe("the token, as a header", () => {
  const remembering = () =>
    keeperOver(() => {
      throw new Error("no storage here");
    });

  test("goes with every request once the page keeps one", async () => {
    const kept = remembering();
    kept.set("t");
    const fetchImpl = answering(200, "{}");
    await request("/api/session", {}, fetchImpl, kept);
    expect(fetchImpl).toHaveBeenCalledWith("/api/session", {
      credentials: "omit",
      headers: { Authorization: "Bearer t" },
    });
  });

  test("goes beside a post's own header", async () => {
    const kept = remembering();
    kept.set("t");
    const fetchImpl = answering(200, "{}");
    await request(
      "/api/undo",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
      fetchImpl,
      kept,
    );
    expect(fetchImpl).toHaveBeenCalledWith("/api/undo", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json", Authorization: "Bearer t" },
      body: "{}",
    });
  });

  test("a 401 clears it and signs the page out, and nothing asks again", async () => {
    const kept = remembering();
    kept.set("stale");
    const out = signedOutStore();
    const fetchImpl = answering(
      401,
      '{"error": "unauthorised", "message": "open the address ddd gui printed in its terminal"}',
    );
    await expect(request("/api/state", {}, fetchImpl, kept, out)).rejects.toMatchObject({
      status: 401,
      code: "unauthorised",
      message: "open the address ddd gui printed in its terminal",
    });
    expect(kept.get()).toBeNull();
    expect(out.current()).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("a 401 keeps a token stored since the ask went out, and still signs the page out", async () => {
    // Between this ask's send and its 401, another tab signed in and stored a newer token. The
    // 401 is about the token this ask carried, which is stale; the newer one must survive it, or
    // the tab that just signed in is signed straight back out (M-1).
    const kept = remembering();
    kept.set("stale");
    const out = signedOutStore();
    const fetchImpl = vi.fn(async () => {
      kept.set("newer");
      return new Response(
        '{"error": "unauthorised", "message": "open the address ddd gui printed in its terminal"}',
        { status: 401 },
      );
    });
    await expect(request("/api/state", {}, fetchImpl, kept, out)).rejects.toMatchObject({
      status: 401,
    });
    expect(kept.get()).toBe("newer");
    expect(out.current()).toBe(true);
  });

  test("any other refusal leaves the page signed in", async () => {
    const kept = remembering();
    kept.set("t");
    const out = signedOutStore();
    await expect(
      request(
        "/api/state",
        {},
        answering(409, '{"error": "no-project", "message": "m"}'),
        kept,
        out,
      ),
    ).rejects.toMatchObject({ status: 409 });
    expect(kept.get()).toBe("t");
    expect(out.current()).toBe(false);
  });
});

/** An edit as the page posts one: what it changes matters to none of the tests below. */
const CHANGES: Changes = {
  changes: [{ file: "a", fingerprint: "x", operations: [{ op: "remove", pointer: "a" }] }],
  label: "the unit of ValueA",
};

const REFUSED = '{"error": "stale", "message": "a.ddd.json changed on disk"}';

describe("the page's own edits", () => {
  test("an edit answered notes the number the server gave it", async () => {
    const edits = new OwnEdits();
    await postEdit(CHANGES, answering(200, '{"edit": 4, "files": []}'), edits);
    expect(edits.newest()).toBe(4);
  });

  test("an edit answered notes its label and the files it wrote, for the heading to say", async () => {
    const edits = new OwnEdits();
    const reply =
      '{"edit": 4, "files": [{"path": "/p/a.ddd.json", "fingerprint": "f"}, ' +
      '{"path": "/p/b.ddd.json", "fingerprint": "g"}]}';
    await postEdit(CHANGES, answering(200, reply), edits);
    expect(edits.last()).toEqual({
      edit: 4,
      write: {
        kind: "wrote",
        label: "the unit of ValueA",
        files: ["/p/a.ddd.json", "/p/b.ddd.json"],
      },
    });
  });

  test("an undo answered notes the number the server gave it, and the edit it put back", async () => {
    const edits = new OwnEdits();
    await postUndo(3, answering(200, '{"edit": 5}'), edits);
    expect(edits.newest()).toBe(5);
    expect(edits.undone()).toEqual(new Map([[3, 5]]));
    expect(edits.last()).toBeNull();
  });

  test("an undo answered notes what it put back, where told", async () => {
    const edits = new OwnEdits();
    const putBack = {
      kind: "put back",
      label: "the unit of ValueA",
      files: ["/p/a.ddd.json"],
    } as const;
    await postUndo(3, answering(200, '{"edit": 5}'), edits, putBack);
    expect(edits.last()).toEqual({ edit: 5, write: putBack });
  });

  test("an edit or an undo refused notes nothing", async () => {
    const edits = new OwnEdits();
    await expect(postEdit(CHANGES, answering(409, REFUSED), edits)).rejects.toBeInstanceOf(
      ApiError,
    );
    await expect(postUndo(3, answering(409, REFUSED), edits)).rejects.toBeInstanceOf(ApiError);
    expect(edits.newest()).toBe(0);
    expect(edits.undone()).toEqual(new Map());
  });

  test("by default each is noted into the page's own", async () => {
    await postEdit(CHANGES, answering(200, '{"edit": 2, "files": []}'));
    expect(ownEdits.newest()).toBe(2);
    await postUndo(2, answering(200, '{"edit": 3}'));
    expect(ownEdits.newest()).toBe(3);
  });
});
