import { describe, expect, test, vi } from "vitest";
import {
  ApiError,
  getFile,
  getProjects,
  getSession,
  getState,
  openProject,
  postEdit,
  request,
  ServerUnreachable,
} from "./client";

function answering(status: number, body: string) {
  return vi.fn(async (_path: string, _init?: RequestInit) => new Response(body, { status }));
}

describe("requests to the server", () => {
  test("a success is its parsed body, asked for with the page's own cookie", async () => {
    const fetchImpl = answering(200, '{"version": "0.10.0"}');
    await expect(request("/api/session", {}, fetchImpl)).resolves.toEqual({ version: "0.10.0" });
    expect(fetchImpl).toHaveBeenCalledWith("/api/session", { credentials: "same-origin" });
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

  test("each call asks the path and method the api expects", async () => {
    const fetchImpl = answering(200, "{}");
    const signal = new AbortController().signal;
    await getSession(fetchImpl);
    await getProjects(fetchImpl);
    await openProject("C:/p/p.ddd.json", fetchImpl);
    await getState(null, undefined, fetchImpl);
    await getState(3, signal, fetchImpl);
    await getFile("C:/p/a b.ddd.json", fetchImpl);
    await postEdit(
      { changes: [{ file: "a", fingerprint: "x", operations: [{ op: "remove", pointer: "a" }] }] },
      fetchImpl,
    );
    expect(fetchImpl.mock.calls).toEqual([
      ["/api/session", { credentials: "same-origin" }],
      ["/api/projects", { credentials: "same-origin" }],
      [
        "/api/open",
        {
          credentials: "same-origin",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: '{"path":"C:/p/p.ddd.json"}',
        },
      ],
      ["/api/state", { credentials: "same-origin" }],
      ["/api/state?after=3", { credentials: "same-origin", signal }],
      ["/api/file?path=C%3A%2Fp%2Fa%20b.ddd.json", { credentials: "same-origin" }],
      [
        "/api/edit",
        {
          credentials: "same-origin",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: '{"changes":[{"file":"a","fingerprint":"x","operations":[{"op":"remove","pointer":"a"}]}]}',
        },
      ],
    ]);
  });
});
