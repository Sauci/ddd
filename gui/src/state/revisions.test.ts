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

test("a server that stops answering is reported once, retried, and reported back", async () => {
  const controller = new AbortController();
  const reports: boolean[] = [];
  const sleeps: number[] = [];
  let calls = 0;
  await followStates({
    getState: async () => {
      calls += 1;
      if (calls <= 2) throw new ServerUnreachable(new TypeError("fetch failed"));
      if (calls === 3) return state(4, 4);
      controller.abort();
      throw aborted();
    },
    onState: () => {},
    onStopped: (stopped) => reports.push(stopped),
    signal: controller.signal,
    retryMs: 5,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
  });
  expect(reports).toEqual([true, false]);
  expect(sleeps).toEqual([5, 5]);
});

test("by default the retry waits on the follow's own signal", async () => {
  const controller = new AbortController();
  await followStates({
    getState: async () => {
      throw new ServerUnreachable(new TypeError("fetch failed"));
    },
    onState: () => {},
    onStopped: () => controller.abort(),
    signal: controller.signal,
  });
  expect(controller.signal.aborted).toBe(true);
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
