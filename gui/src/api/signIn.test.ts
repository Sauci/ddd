import { describe, expect, test, vi } from "vitest";
import { landingOf, secretOf, signInFrom } from "./signIn";
import { keeperOver } from "./token";
import type { SessionInfo } from "./types";

const STARTED: SessionInfo = {
  version: "0.11.0",
  preview: true,
  root: "/w",
  project: null,
  builds: [],
};
const OPENED: SessionInfo = { ...STARTED, project: { path: "/w/p.ddd.json", name: "P" } };

/** A keeper of the tab's own memory, as a browser refusing storage leaves the page. */
const remembering = () =>
  keeperOver(() => {
    throw new Error("no storage here");
  });

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });

describe("the secret an address carries", () => {
  test("a launch's code", () => expect(secretOf("/open", "?code=c")).toEqual({ code: "c" }));
  test("the printed address's token", () =>
    expect(secretOf("/open", "?token=t")).toEqual({ token: "t" }));
  test("the code, where an address carries both", () =>
    expect(secretOf("/open", "?token=t&code=c")).toEqual({ code: "c" }));
  test("nothing, where both are blank", () =>
    expect(secretOf("/open", "?code=&token=")).toBeNull());
  test("nothing, anywhere but /open", () => expect(secretOf("/project", "?token=t")).toBeNull());
});

describe("where the page lands once signed in", () => {
  test("on the open project", () => expect(landingOf(OPENED)).toBe("/project"));
  test("on the start page, with no project open", () => expect(landingOf(STARTED)).toBe("/"));
});

describe("signing in from the page's own address", () => {
  test("the address is cleaned before the secret is sent anywhere", async () => {
    const order: string[] = [];
    const replace = vi.fn((path: string) => order.push(`replace ${path}`));
    const fetchImpl = vi.fn(async (path: string) => {
      order.push(`fetch ${path}`);
      return path === "/open" ? json(200, { token: "t" }) : json(200, STARTED);
    });
    await signInFrom({ pathname: "/open", search: "?code=c" }, replace, remembering(), fetchImpl);
    expect(order.slice(0, 2)).toEqual(["replace /", "fetch /open"]);
  });

  test("the secret is posted as json, with no cookie", async () => {
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, STARTED),
    );
    await signInFrom({ pathname: "/open", search: "?code=c" }, vi.fn(), remembering(), fetchImpl);
    expect(fetchImpl).toHaveBeenNthCalledWith(1, "/open", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: '{"code":"c"}',
    });
  });

  test("the token answered is kept, and the page lands on the open project", async () => {
    const kept = remembering();
    const replace = vi.fn();
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, OPENED),
    );
    await signInFrom({ pathname: "/open", search: "?token=t" }, replace, kept, fetchImpl);
    expect(kept.get()).toBe("t");
    expect(replace.mock.calls).toEqual([["/"], ["/project"]]);
    expect(fetchImpl).toHaveBeenNthCalledWith(2, "/api/session", {
      credentials: "omit",
      headers: { Authorization: "Bearer t" },
    });
  });

  test("with no project open, the page lands on the start page", async () => {
    const replace = vi.fn();
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, STARTED),
    );
    await signInFrom({ pathname: "/open", search: "?token=t" }, replace, remembering(), fetchImpl);
    expect(replace.mock.calls).toEqual([["/"], ["/"]]);
  });

  test("a refusal clears whatever token was kept", async () => {
    const kept = remembering();
    kept.set("stale");
    const fetchImpl = vi.fn(async () =>
      json(403, {
        error: "forbidden",
        message: "open the address ddd gui printed in its terminal",
      }),
    );
    await signInFrom({ pathname: "/open", search: "?code=c" }, vi.fn(), kept, fetchImpl);
    expect(kept.get()).toBeNull();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("a refusal that is no json, as the gate's own page is, clears the token too", async () => {
    // The gate answers a path outside the API with its sign-in page, in html. Were that read as
    // json alone, the sign-in would throw, and the page, rendered only once the sign-in is done,
    // would stay blank.
    const kept = remembering();
    kept.set("stale");
    const page =
      '<!doctype html><html lang="en"><meta charset="utf-8"><title>ddd gui</title>' +
      "<p>Open the address <code>ddd gui</code> printed in its terminal.</p></html>";
    await signInFrom(
      { pathname: "/open", search: "?code=c" },
      vi.fn(),
      kept,
      async () => new Response(page, { status: 403 }),
    );
    expect(kept.get()).toBeNull();
  });

  test("an answer that holds no token keeps none", async () => {
    const kept = remembering();
    await signInFrom({ pathname: "/open", search: "?code=c" }, vi.fn(), kept, async () =>
      json(200, { other: "x" }),
    );
    expect(kept.get()).toBeNull();
  });

  test("a server not answering leaves what was kept as it was", async () => {
    const kept = remembering();
    kept.set("t");
    await signInFrom({ pathname: "/open", search: "?code=c" }, vi.fn(), kept, async () => {
      throw new TypeError("Failed to fetch");
    });
    expect(kept.get()).toBe("t");
  });

  test("a session that does not answer keeps the token, and lands nowhere new", async () => {
    const kept = remembering();
    const replace = vi.fn();
    const fetchImpl = vi.fn(async (path: string) => {
      if (path === "/open") return json(200, { token: "t" });
      throw new TypeError("Failed to fetch");
    });
    await signInFrom({ pathname: "/open", search: "?token=t" }, replace, kept, fetchImpl);
    expect(kept.get()).toBe("t");
    expect(replace.mock.calls).toEqual([["/"]]);
  });

  test("/open with no secret is cleaned, and nothing is asked", async () => {
    const replace = vi.fn();
    const fetchImpl = vi.fn();
    await signInFrom({ pathname: "/open", search: "" }, replace, remembering(), fetchImpl);
    expect(replace.mock.calls).toEqual([["/"]]);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("any other address is left alone, and nothing is asked", async () => {
    const replace = vi.fn();
    const fetchImpl = vi.fn();
    await signInFrom({ pathname: "/project", search: "" }, replace, remembering(), fetchImpl);
    expect(replace).not.toHaveBeenCalled();
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
