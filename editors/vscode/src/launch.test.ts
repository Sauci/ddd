/**
 * That the command this extension builds really starts the server.
 *
 * The one thing a unit test of the settings cannot tell us, and the one thing most likely to
 * break silently: the extension and the CLI are two halves of an agreement about a command
 * name and a flag, and nothing else in either repository half would notice the day they stop
 * agreeing. So the server is actually started here, by exactly the route the extension takes.
 *
 * What is deliberately not tested is anything VS Code does. Launching an editor to watch it
 * call `activate` proves the api exists, which it does; it says nothing about DDD.
 */

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import * as path from "node:path";
import { test } from "node:test";

import { serverArguments, Settings } from "./config";

const REPO = path.resolve(__dirname, "..", "..", "..");

function frame(message: unknown): Buffer {
  const body = Buffer.from(JSON.stringify(message), "utf8");
  return Buffer.concat([Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, "ascii"), body]);
}

/** Start a server the way the extension would, ask it who it is, and let it go. */
async function handshake(settings: Settings): Promise<Record<string, any>> {
  const child = spawn(settings.executable, serverArguments(settings), { cwd: REPO });
  const chunks: Buffer[] = [];
  child.stdout.on("data", (chunk: Buffer) => chunks.push(chunk));
  child.stdin.write(frame({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} }));
  child.stdin.write(frame({ jsonrpc: "2.0", method: "exit" }));
  child.stdin.end();

  const code = await new Promise<number | null>((resolve) => child.on("close", resolve));
  assert.equal(code, 0, "the server did not exit cleanly");
  const output = Buffer.concat(chunks).toString("utf8");
  return JSON.parse(output.slice(output.indexOf("\r\n\r\n") + 4));
}

test("the default command starts a server that identifies itself", async () => {
  const answer = await handshake({ executable: "ddd", buildDirectories: [] });
  assert.equal(answer.result.serverInfo.name, "ddd");
  assert.equal(answer.result.capabilities.definitionProvider, true);
  assert.equal(answer.result.capabilities.referencesProvider, true);
});

test("a configured build directory is a flag the server accepts", async () => {
  // The agreement this pins: rename the flag on either side and the extension stops working
  // for every project that configured one, silently.
  const answer = await handshake({ executable: "ddd", buildDirectories: ["build"] });
  assert.equal(answer.result.serverInfo.name, "ddd");
});
