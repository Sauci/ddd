import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_EXECUTABLE,
  DESCRIPTIONS,
  describes,
  Opened,
  Section,
  serverArguments,
  settingsFrom,
  wanted,
} from "./config";

function section(values: Record<string, unknown>): Section {
  return {
    get<T>(key: string, fallback: T): T {
      return (key in values ? values[key] : fallback) as T;
    },
  };
}

/** A document the editor has open, at `path`, read in `languageId`, under `scheme`. */
function document(path: string, languageId = "json", scheme = "file"): Opened {
  return { languageId, uri: { scheme, path } };
}

/** A workspace holding no description, and one holding one, as the search would answer. */
const holdingNone = async (): Promise<boolean> => false;
const holdingOne = async (): Promise<boolean> => true;

test("an open description wants the server, and the workspace is not searched for one", async () => {
  let searched = false;
  const search = async (): Promise<boolean> => {
    searched = true;
    return false;
  };
  const open = [document("/w/package.json"), document("/w/a.ddd.json")];
  assert.equal(await wanted(open, search), true);
  assert.equal(searched, false);
});

test("a json file of another name, in a workspace holding no description, starts nothing", async () => {
  // Started at once, the server ran for every json file of every trusted workspace, and where
  // ddd is not installed its error was shown there.
  assert.equal(await wanted([document("/w/package.json")], holdingNone), false);
  assert.equal(await wanted([], holdingNone), false);
});

test("a workspace holding a description wants the server with nothing open", async () => {
  assert.equal(await wanted([document("/w/package.json")], holdingOne), true);
});

test("only a *.ddd.json on disk, read as json, is handed to the server", () => {
  // What the client's document selector claims, and what the workspace is searched for.
  assert.deepEqual(DESCRIPTIONS, { scheme: "file", language: "json", pattern: "**/*.ddd.json" });
});

test("a description is a document the server is handed: a *.ddd.json on disk, read as json", () => {
  assert.equal(describes(document("/w/parts/a.ddd.json")), true);
  assert.equal(describes(document("/w/parts/a.json")), false);
  assert.equal(describes(document("/w/parts/ddd.json")), false);
  // A version of one from the source control history, and one read in another language: the
  // server is handed neither, so neither is a reason to start it.
  assert.equal(describes(document("/w/parts/a.ddd.json", "json", "git")), false);
  assert.equal(describes(document("/w/parts/a.ddd.json", "plaintext")), false);
});

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
