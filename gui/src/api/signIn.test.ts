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

/** A tab's history, recording each address the sign-in puts in place of the current one. */
const tab = () => ({ replaceState: vi.fn() });

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
    const history = {
      replaceState: vi.fn((_data: unknown, _unused: string, url?: string | URL | null) => {
        order.push(`replace ${String(url)}`);
      }),
    };
    const fetchImpl = vi.fn(async (path: string) => {
      order.push(`fetch ${path}`);
      return path === "/open" ? json(200, { token: "t" }) : json(200, STARTED);
    });
    await signInFrom({ pathname: "/open", search: "?code=c" }, history, remembering(), fetchImpl);
    expect(order.slice(0, 2)).toEqual(["replace /", "fetch /open"]);
  });

  test("the address is replaced, never pushed, so that no entry of the tab's history holds the secret", async () => {
    const history = { replaceState: vi.fn(), pushState: vi.fn() };
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, OPENED),
    );
    await signInFrom({ pathname: "/open", search: "?code=c" }, history, remembering(), fetchImpl);
    expect(history.replaceState.mock.calls).toEqual([
      [null, "", "/"],
      [null, "", "/project"],
    ]);
    expect(history.pushState).not.toHaveBeenCalled();
  });

  test("the secret is posted as json, with no cookie", async () => {
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, STARTED),
    );
    await signInFrom({ pathname: "/open", search: "?code=c" }, tab(), remembering(), fetchImpl);
    expect(fetchImpl).toHaveBeenNthCalledWith(1, "/open", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: '{"code":"c"}',
    });
  });

  test("the token answered is kept, and the page lands on the open project", async () => {
    const kept = remembering();
    const history = tab();
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, OPENED),
    );
    await signInFrom({ pathname: "/open", search: "?token=t" }, history, kept, fetchImpl);
    expect(kept.get()).toBe("t");
    expect(history.replaceState.mock.calls).toEqual([
      [null, "", "/"],
      [null, "", "/project"],
    ]);
    expect(fetchImpl).toHaveBeenNthCalledWith(2, "/api/session", {
      credentials: "omit",
      headers: { Authorization: "Bearer t" },
    });
  });

  test("with no project open, the page lands on the start page", async () => {
    const history = tab();
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, STARTED),
    );
    await signInFrom({ pathname: "/open", search: "?token=t" }, history, remembering(), fetchImpl);
    expect(history.replaceState.mock.calls).toEqual([
      [null, "", "/"],
      [null, "", "/"],
    ]);
  });

  test.each([
    [403, { error: "forbidden", message: "open the address ddd gui printed in its terminal" }],
    [
      503,
      {
        error: "busy",
        message:
          "ddd gui is answering as many connections as it takes at once; ask again in a moment",
      },
    ],
  ])("an answer of %i leaves the token held as it was", async (status, refusal) => {
    // Cleared, it would let any page sign the reader out of every tab, by sending this one to
    // /open with a wrong code; and the connection cap's 503 would do the same. A stale token is
    // cleared by the first 401 it meets anyway (ruling P18b-6).
    const kept = remembering();
    kept.set("held");
    const fetchImpl = vi.fn(async () => json(status, refusal));
    await signInFrom({ pathname: "/open", search: "?code=c" }, tab(), kept, fetchImpl);
    expect(kept.get()).toBe("held");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("a refusal that is no json, as the gate's own page is, is an answer like any other", async () => {
    // The gate answers a path outside the API, asked from elsewhere, with its sign-in page, in
    // html. Read as json alone, it would throw out of the sign-in.
    const kept = remembering();
    kept.set("held");
    const page =
      '<!doctype html><html lang="en"><meta charset="utf-8"><title>ddd gui</title>' +
      "<p>Open the address <code>ddd gui</code> printed in its terminal.</p></html>";
    await expect(
      signInFrom(
        { pathname: "/open", search: "?code=c" },
        tab(),
        kept,
        async () => new Response(page, { status: 403 }),
      ),
    ).resolves.toBeUndefined();
    expect(kept.get()).toBe("held");
  });

  test("an answer that holds no token keeps none", async () => {
    const kept = remembering();
    await signInFrom({ pathname: "/open", search: "?code=c" }, tab(), kept, async () =>
      json(200, { other: "x" }),
    );
    expect(kept.get()).toBeNull();
  });

  test("a server not answering leaves what was kept as it was", async () => {
    const kept = remembering();
    kept.set("t");
    await signInFrom({ pathname: "/open", search: "?code=c" }, tab(), kept, async () => {
      throw new TypeError("Failed to fetch");
    });
    expect(kept.get()).toBe("t");
  });

  test("a session that does not answer keeps the token, and lands nowhere new", async () => {
    const kept = remembering();
    const history = tab();
    const fetchImpl = vi.fn(async (path: string) => {
      if (path === "/open") return json(200, { token: "t" });
      throw new TypeError("Failed to fetch");
    });
    await signInFrom({ pathname: "/open", search: "?token=t" }, history, kept, fetchImpl);
    expect(kept.get()).toBe("t");
    expect(history.replaceState.mock.calls).toEqual([[null, "", "/"]]);
  });

  test("/open with no secret is cleaned, and nothing is asked", async () => {
    const history = tab();
    const fetchImpl = vi.fn();
    await signInFrom({ pathname: "/open", search: "" }, history, remembering(), fetchImpl);
    expect(history.replaceState.mock.calls).toEqual([[null, "", "/"]]);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("any other address is left alone, and nothing is asked", async () => {
    const history = tab();
    const fetchImpl = vi.fn();
    await signInFrom({ pathname: "/project", search: "" }, history, remembering(), fetchImpl);
    expect(history.replaceState).not.toHaveBeenCalled();
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
