import { expect, test, vi } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import type { State } from "../api/types";
import { followStates, wait } from "./revisions";

const state = (version: number, revision = 1): State => ({
  revision,
  version,
  project: "/p.ddd.json",
  files: [],
  counts: { error: 0, warning: 0, info: 0 },
  statements: { error: 0, warning: 0, info: 0 },
  failed: null,
  refused: [],
  undoable: null,
  analysing: false,
  edits: 0,
});
const aborted = () => new DOMException("aborted", "AbortError");

test("each newer state is handed on once, and the next request asks for anything newer", async () => {
  const controller = new AbortController();
  const answers = [state(1), state(1), state(2, 2)];
  const asked: (number | null)[] = [];
  const seen: number[] = [];
  await followStates({
    getState: async (after) => {
      asked.push(after);
      const next = answers.shift();
      if (next === undefined) {
        controller.abort();
        throw aborted();
      }
      return next;
    },
    onState: (current) => seen.push(current.version),
    onStopped: () => {
      throw new Error("the server never stopped");
    },
    onFailed: () => {
      throw new Error("no answer failed");
    },
    signal: controller.signal,
  });
  expect(seen).toEqual([1, 2]);
  expect(asked).toEqual([null, 1, 1, 2]);
});

test("a state whose version grew and whose revision did not is handed on", async () => {
  // An analysis asked for, an edit written: what the page shows changes - the undo entry, the
  // findings about to - while the revision stays what it was.
  const controller = new AbortController();
  const answers = [state(3, 1), state(4, 1)];
  const seen: [number, number][] = [];
  await followStates({
    getState: async () => {
      const next = answers.shift();
      if (next === undefined) {
        controller.abort();
        throw aborted();
      }
      return next;
    },
    onState: (current) => seen.push([current.version, current.revision]),
    onStopped: () => {},
    onFailed: () => {},
    signal: controller.signal,
  });
  expect(seen).toEqual([
    [3, 1],
    [4, 1],
  ]);
});

/** What the server answers a connection past the most it answers at once (`BUSY`, gui/server.py),
 * as `request` reads it: a `503`, its own sentence saying to ask again in a moment. */
const BUSY = "ddd gui is answering as many connections as it takes at once; ask again in a moment";
const busy = () => new ApiError(503, "busy", BUSY);

/** An answer whose body does not parse - cut half way - as `request` reads it. */
const NOT_JSON = "ddd gui's answer to /api/state is not json";
const cut = () => new ApiError(200, "not-json", NOT_JSON);

/** A follow whose requests answer, in turn, as `answers` says - a state, `null` for a request
 * that goes unanswered, or what the request is refused or failed with - and which ends once they
 * run out: what it reported, how long it waited between requests, and what it handed on. `said`
 * is what it reported, stopped or failed, in the order it reported it. */
async function followed(answers: readonly (State | Error | null)[]) {
  const controller = new AbortController();
  const left = [...answers];
  const reports: boolean[] = [];
  const failures: (string | null)[] = [];
  const said: string[] = [];
  const sleeps: number[] = [];
  const seen: number[] = [];
  await followStates({
    getState: async () => {
      const next = left.shift();
      if (next === undefined) {
        controller.abort();
        throw aborted();
      }
      if (next === null) throw new ServerUnreachable(new TypeError("fetch failed"));
      if (next instanceof Error) throw next;
      return next;
    },
    onState: (current) => seen.push(current.version),
    onStopped: (stopped) => {
      reports.push(stopped);
      said.push(stopped ? "stopped" : "running");
    },
    onFailed: (failure) => {
      failures.push(failure);
      said.push(failure === null ? "lifted" : `failed: ${failure}`);
    },
    signal: controller.signal,
    retryMs: 5,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
  });
  return { reports, failures, said, sleeps, seen };
}

test("one unanswered request and then an answer: the server is never reported stopped", async () => {
  // Asked again a quarter of a second later, and answered: nothing on screen says it stopped, and
  // nothing is disabled for it.
  const { reports, sleeps, seen } = await followed([state(3), null, state(4)]);
  expect(reports).toEqual([]);
  expect(sleeps).toEqual([250]);
  expect(seen).toEqual([3, 4]);
});

test("two unanswered requests in a row: the server is reported stopped, once", async () => {
  // The prompt second ask goes unanswered too: the server is said to have stopped, and from then
  // on it is asked again at the follow's own pace, without being said to have stopped again.
  const { reports, sleeps } = await followed([state(3), null, null, null, null]);
  expect(reports).toEqual([true]);
  expect(sleeps).toEqual([250, 5, 5, 5]);
});

test("a server reported stopped that answers again is reported running", async () => {
  // And the answer starts this over: one request unanswered after it is asked again promptly,
  // and says nothing.
  const { reports, sleeps, seen } = await followed([
    state(3),
    null,
    null,
    state(4),
    null,
    state(5),
  ]);
  expect(reports).toEqual([true, false]);
  expect(sleeps).toEqual([250, 5, 250]);
  expect(seen).toEqual([3, 4, 5]);
});

test("by default the follow waits on its own signal, and an abort ends the wait", async () => {
  vi.useFakeTimers();
  try {
    const controller = new AbortController();
    const follow = followStates({
      getState: async () => {
        throw new ServerUnreachable(new TypeError("fetch failed"));
      },
      onState: () => {},
      onStopped: () => controller.abort(),
      onFailed: () => {},
      signal: controller.signal,
      retryMs: 60_000,
    });
    // The prompt second ask, a quarter of a second after the first: refused too, so the server
    // is reported stopped, which aborts - and the minute's wait after it ends at once.
    await vi.advanceTimersByTimeAsync(250);
    await follow;
    expect(controller.signal.aborted).toBe(true);
  } finally {
    vi.useRealTimers();
  }
});

test("one answer the server failed, a 503, is asked again a quarter of a second later, and the follow goes on", async () => {
  // Answered `BUSY`, whose own words say to ask again in a moment: the follow ended there, and
  // nothing asked again but a reload. Asked again promptly and answered, it says nothing.
  const { reports, failures, sleeps, seen } = await followed([state(3), busy(), state(4)]);
  expect(seen).toEqual([3, 4]);
  expect(sleeps).toEqual([250]);
  expect(failures).toEqual([]);
  expect(reports).toEqual([]);
});

test("two failed answers in a row: the server's own words are said, once, until an answer lifts them", async () => {
  // The server answered each, so it has not stopped: no control is disabled for it, and the page
  // asks again at the follow's own pace until it answers.
  const { reports, failures, sleeps, seen } = await followed([
    state(3),
    busy(),
    busy(),
    busy(),
    state(4),
  ]);
  expect(failures).toEqual([BUSY, null]);
  expect(reports).toEqual([]);
  expect(sleeps).toEqual([250, 5, 5]);
  expect(seen).toEqual([3, 4]);
});

test("an answer whose body does not parse, cut half way, is asked again as a failed one is", async () => {
  const { failures, sleeps, seen } = await followed([state(3), cut(), cut(), state(4)]);
  expect(failures).toEqual([NOT_JSON, null]);
  expect(sleeps).toEqual([250, 5]);
  expect(seen).toEqual([3, 4]);
});

test("what is said follows the last ask: a failure gives way to stopped, and stopped to a failure", async () => {
  // Two asks in a row that failed, whatever their kind, and the second says what is said: a
  // server that failed and then answered nothing at all has stopped, and its failure is no longer
  // said; one said stopped that answers a failure has not stopped. An answer lifts it all.
  const { said, sleeps, seen } = await followed([state(3), busy(), busy(), null, busy(), state(4)]);
  expect(said).toEqual([
    `failed: ${BUSY}`,
    "stopped",
    "lifted",
    "running",
    `failed: ${BUSY}`,
    "lifted",
  ]);
  expect(sleeps).toEqual([250, 5, 5, 5]);
  expect(seen).toEqual([3, 4]);
});

test("a failed answer and then an unanswered ask are two in a row: the server is said stopped", async () => {
  const { said, sleeps } = await followed([state(3), busy(), null, state(4)]);
  expect(said).toEqual(["stopped", "running"]);
  expect(sleeps).toEqual([250, 5]);
});

test("a refusal, a 4xx, ends the follow with that refusal", async () => {
  // Asked again, a refusal is answered again: it is the server's answer to what was asked.
  const follow = followStates({
    getState: async () => {
      throw new ApiError(409, "no-project", "no project is open");
    },
    onState: () => {},
    onStopped: () => {},
    onFailed: () => {},
    signal: new AbortController().signal,
  });
  await expect(follow).rejects.toThrow("no project is open");
});

test("a refusal after failed answers ends the follow too, what was said of them left as it is", async () => {
  // The page says the refusal in that place itself (`useProjectState`), the follow having ended.
  const refused = new ApiError(404, "not-found", "no such route");
  const failures: (string | null)[] = [];
  const answers: Error[] = [busy(), busy(), refused];
  const follow = followStates({
    getState: async () => {
      throw answers.shift();
    },
    onState: () => {},
    onStopped: () => {
      throw new Error("the server never stopped");
    },
    onFailed: (failure) => failures.push(failure),
    signal: new AbortController().signal,
    retryMs: 5,
    sleep: async () => {},
  });
  await expect(follow).rejects.toBe(refused);
  expect(failures).toEqual([BUSY]);
});

test("a follow aborted before it starts asks nothing", async () => {
  const controller = new AbortController();
  controller.abort();
  const getState = vi.fn();
  await followStates({
    getState,
    onState: () => {},
    onStopped: () => {},
    onFailed: () => {},
    signal: controller.signal,
  });
  expect(getState).not.toHaveBeenCalled();
});

test("wait ends after its delay, when aborted, or at once when already aborted", async () => {
  vi.useFakeTimers();
  try {
    const controller = new AbortController();
    const timed = wait(1000, controller.signal);
    await vi.advanceTimersByTimeAsync(1000);
    await timed;
    const interrupted = wait(1000, controller.signal);
    controller.abort();
    await interrupted;
    await wait(1000, controller.signal);
  } finally {
    vi.useRealTimers();
  }
});
