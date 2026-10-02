import { expect, test } from "vitest";
import type { GraphModule } from "../api/types";
import {
  INITIAL_LAYOUT_STATE,
  type LayoutState,
  layoutScreen,
  RANKS_ONLY_NOTE,
  withAnswer,
} from "./layoutAnswers";

const graphModule = (path: string): GraphModule => ({
  path,
  name: path,
  loaded: true,
  findings: { error: 0, warning: 0, info: 0 },
});

const placedAt = (path: string) => [{ module: graphModule(path), x: 0, y: 0 }];

test("a success for the wanted shape replaces placed and clears a previous error", () => {
  const state: LayoutState = { placed: null, ranksOnly: false, error: "earlier" };
  const placed = placedAt("/a.ddd.json");
  const next = withAnswer(state, { shape: "S1", placed }, "S1");
  expect(next).toEqual({ placed, ranksOnly: false, error: null });
});

test("a success marked ranksOnly carries that forward", () => {
  const placed = placedAt("/a.ddd.json");
  const next = withAnswer(INITIAL_LAYOUT_STATE, { shape: "S1", placed, ranksOnly: true }, "S1");
  expect(next).toEqual({ placed, ranksOnly: true, error: null });
});

test("an error for the wanted shape is kept, without touching an existing placement", () => {
  const placed = placedAt("/a.ddd.json");
  const state: LayoutState = { placed, ranksOnly: true, error: null };
  const next = withAnswer(state, { shape: "S2", error: "boom" }, "S2");
  expect(next).toEqual({ placed, ranksOnly: true, error: "boom" });
});

test("an answer for a shape no longer wanted is dropped, state unchanged", () => {
  const state: LayoutState = { placed: placedAt("/a.ddd.json"), ranksOnly: false, error: null };
  const stale = withAnswer(state, { shape: "S1", placed: placedAt("/b.ddd.json") }, "S2");
  expect(stale).toBe(state);
});

test("an answer naming neither placed nor error changes nothing", () => {
  const state: LayoutState = { placed: null, ranksOnly: false, error: null };
  expect(withAnswer(state, { shape: "S1" }, "S1")).toBe(state);
});

test("the screen waits when nothing has ever answered", () => {
  expect(layoutScreen(INITIAL_LAYOUT_STATE)).toEqual({ kind: "waiting" });
});

test("the screen shows the error alone when the first layout ever failed", () => {
  const state: LayoutState = {
    placed: null,
    ranksOnly: false,
    error: "Maximum call stack size exceeded",
  };
  expect(layoutScreen(state)).toEqual({
    kind: "failed",
    message: "Maximum call stack size exceeded",
  });
});

test("the screen draws the canvas plainly once a layout has succeeded", () => {
  const placed = placedAt("/a.ddd.json");
  const state: LayoutState = { placed, ranksOnly: false, error: null };
  expect(layoutScreen(state)).toEqual({
    kind: "drawn",
    placed,
    errorMessage: null,
    note: null,
  });
});

test("the screen draws the canvas with the error when a later layout failed", () => {
  const placed = placedAt("/a.ddd.json");
  const state: LayoutState = { placed, ranksOnly: false, error: "boom" };
  expect(layoutScreen(state)).toEqual({
    kind: "drawn",
    placed,
    errorMessage: "boom",
    note: null,
  });
});

test("the screen draws the canvas with the ranks-only note when the fallback made it", () => {
  const placed = placedAt("/a.ddd.json");
  const state: LayoutState = { placed, ranksOnly: true, error: null };
  expect(layoutScreen(state)).toEqual({
    kind: "drawn",
    placed,
    errorMessage: null,
    note: RANKS_ONLY_NOTE,
  });
});

test("the screen shows both the error and the ranks-only note when both apply at once", () => {
  const placed = placedAt("/a.ddd.json");
  const state: LayoutState = { placed, ranksOnly: true, error: "boom" };
  expect(layoutScreen(state)).toEqual({
    kind: "drawn",
    placed,
    errorMessage: "boom",
    note: RANKS_ONLY_NOTE,
  });
});
