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
    signal: controller.signal,
  });
  expect(seen).toEqual([
    [3, 1],
    [4, 1],
  ]);
});

/** A follow whose requests answer, in turn, as `answers` says - a state, or `null` for a request
 * that goes unanswered - and which ends once they run out: what it reported, how long it waited
 * between requests, and what it handed on. */
async function followed(answers: readonly (State | null)[]) {
  const controller = new AbortController();
  const left = [...answers];
  const reports: boolean[] = [];
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
      return next;
    },
    onState: (current) => seen.push(current.version),
    onStopped: (stopped) => reports.push(stopped),
    signal: controller.signal,
    retryMs: 5,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
  });
  return { reports, sleeps, seen };
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

test("any other failure ends the follow with that failure", async () => {
  const follow = followStates({
    getState: async () => {
      throw new ApiError(409, "no-project", "no project is open");
    },
    onState: () => {},
    onStopped: () => {},
    signal: new AbortController().signal,
  });
  await expect(follow).rejects.toThrow("no project is open");
});

test("a follow aborted before it starts asks nothing", async () => {
  const controller = new AbortController();
  controller.abort();
  const getState = vi.fn();
  await followStates({
    getState,
    onState: () => {},
    onStopped: () => {},
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
