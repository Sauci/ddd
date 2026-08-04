import assert from "node:assert/strict";
import { test } from "node:test";

import { DEFAULT_EXECUTABLE, Section, serverArguments, settingsFrom } from "./config";

function section(values: Record<string, unknown>): Section {
  return {
    get<T>(key: string, fallback: T): T {
      return (key in values ? values[key] : fallback) as T;
    },
  };
}

test("a project that configures nothing still gets a usable command", () => {
  const settings = settingsFrom(section({}));
  assert.equal(settings.executable, DEFAULT_EXECUTABLE);
  assert.deepEqual(serverArguments(settings), ["lsp"]);
});

test("each build directory becomes a flag the server understands", () => {
  const settings = settingsFrom(section({ buildDirectories: ["build", "out/arm"] }));
  assert.deepEqual(serverArguments(settings), ["lsp", "-b", "build", "-b", "out/arm"]);
});

test("a blank entry is dropped rather than passed on", () => {
  // What a half finished edit of the settings array leaves behind. Forwarded, it would make
  // the server search a directory named "", which fails saying nothing about the cause.
  const settings = settingsFrom(section({ buildDirectories: ["  ", "build", ""] }));
  assert.deepEqual(serverArguments(settings), ["lsp", "-b", "build"]);
});

test("an executable set to whitespace falls back rather than failing to spawn", () => {
  assert.equal(settingsFrom(section({ executable: "   " })).executable, DEFAULT_EXECUTABLE);
});

test("an executable is taken as written, so a virtual environment can be pointed at", () => {
  const settings = settingsFrom(section({ executable: " /opt/venv/bin/ddd " }));
  assert.equal(settings.executable, "/opt/venv/bin/ddd");
});
