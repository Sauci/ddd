import { expect, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import {
  askAgainIn,
  askingAgain,
  failureSaid,
  missedSaid,
  PROMPT_RETRY_MS,
  RETRY_MS,
} from "./asking";

/** A connection past the most ddd gui answers at once, as `request` reads its answer. */
const BUSY = "ddd gui is answering as many connections as it takes at once; ask again in a moment";
const busy = new ApiError(503, "busy", BUSY);

test("the first ask that fails is asked again a quarter of a second later, each later one at the follow's pace", () => {
  expect(PROMPT_RETRY_MS).toBe(250);
  expect(RETRY_MS).toBe(2000);
  expect(askAgainIn(1)).toBe(250);
  expect(askAgainIn(2)).toBe(2000);
  expect(askAgainIn(7)).toBe(2000);
  // A pace of the follow's own, as its tests give one.
  expect(askAgainIn(1, 5)).toBe(250);
  expect(askAgainIn(2, 5)).toBe(5);
});

test("why asks fail is said from the second in a row, never at the first", () => {
  expect(missedSaid(0)).toBe(false);
  expect(missedSaid(1)).toBe(false);
  expect(missedSaid(2)).toBe(true);
  expect(missedSaid(9)).toBe(true);
});

test("a query asked again is asked again for what the client asks again, at the same pace", () => {
  // React Query hands `retry` and `retryDelay` how many of the query's asks in a row failed
  // before the one that just did: none, at the first.
  expect(askingAgain.retry(0, busy)).toBe(true);
  expect(askingAgain.retry(4, new ServerUnreachable(new TypeError("fetch failed")))).toBe(true);
  expect(askingAgain.retry(0, new ApiError(404, "not-found", "no such route"))).toBe(false);
  expect(askingAgain.retryDelay(0)).toBe(250);
  expect(askingAgain.retryDelay(1)).toBe(2000);
  expect(askingAgain.retryDelay(6)).toBe(2000);
});

/** A query of the session as React Query holds it while its asks fail and are asked again. */
const asking = (failureCount: number, failureReason: Error | null = busy) => ({
  fetchStatus: "fetching" as const,
  failureCount,
  failureReason,
});

test("the session's ask failing is said while it is asked again, from the second in a row", () => {
  expect(failureSaid(null, asking(2))).toBe(BUSY);
  expect(failureSaid(null, asking(5))).toBe(BUSY);
  // Waited for in a tab hidden, React Query asks again once it is shown: it is still asked.
  expect(failureSaid(null, { ...asking(2), fetchStatus: "paused" })).toBe(BUSY);
});

test("but not at the first, asked again at once, nor once an ask is answered", () => {
  expect(failureSaid(null, asking(1))).toBeNull();
  // React Query counts nothing failed once an ask is answered.
  expect(
    failureSaid(null, { fetchStatus: "idle", failureCount: 0, failureReason: null }),
  ).toBeNull();
});

test("nor once a refusal ends the asking: the page says that refusal in its own place", () => {
  const refused = new ApiError(404, "not-found", "no such route");
  expect(
    failureSaid(null, { fetchStatus: "idle", failureCount: 3, failureReason: refused }),
  ).toBeNull();
});

test("the long poll's failure is said over the session's, which is never said twice", () => {
  // Both asked again at once, as the page opening a project may: one banner, the long poll's.
  const failed = "ddd gui failed on this request; the terminal it runs in shows why";
  expect(failureSaid(failed, asking(2))).toBe(failed);
  expect(failureSaid(failed, { fetchStatus: "idle", failureCount: 0, failureReason: null })).toBe(
    failed,
  );
});
