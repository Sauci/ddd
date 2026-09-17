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

/**
 * How long a handshake may take before the test gives up and says so.
 *
 * `node:test` sets no timeout of its own, so a server that answers and then never exits used
 * to hang the run rather than fail it - which on CI is a job that has to be cancelled by hand
 * and locally a test that never comes back. Generous, because a cold python interpreter
 * importing the tool is most of it; the point is a bound, not a stopwatch.
 */
const HANDSHAKE_TIMEOUT_MS = 30_000;

function frame(message: unknown): Buffer {
  const body = Buffer.from(JSON.stringify(message), "utf8");
  return Buffer.concat([Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, "ascii"), body]);
}

/**
 * The first framed message on the stream, read by the length its own header states.
 *
 * The session sends more than one request, so everything after the first header is no longer
 * one json document: taking the length seriously is the only way to know where the answer to
 * `initialize` ends.
 */
function firstMessage(output: Buffer): Record<string, any> {
  const separator = output.indexOf("\r\n\r\n");
  if (separator === -1) {
    throw new Error(`the server framed nothing: ${JSON.stringify(output.toString("utf8"))}`);
  }
  const header = output.subarray(0, separator).toString("ascii");
  const stated = /content-length:\s*(\d+)/i.exec(header);
  if (stated === null) {
    throw new Error(`no Content-Length in ${JSON.stringify(header)}`);
  }
  const length = Number(stated[1]);
  return JSON.parse(output.subarray(separator + 4, separator + 4 + length).toString("utf8"));
}

/** Start a server the way the extension would, ask it who it is, and wind it down. */
async function handshake(settings: Settings): Promise<Record<string, any>> {
  const child = spawn(settings.executable, serverArguments(settings), { cwd: REPO });
  const chunks: Buffer[] = [];
  child.stdout.on("data", (chunk: Buffer) => chunks.push(chunk));
  child.stdin.write(frame({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} }));
  // Wound down before it is told to go. `exit` on its own is the protocol's unclean stop and
  // the server reports it as one, which is what a client watching the process wants to hear.
  child.stdin.write(frame({ jsonrpc: "2.0", id: 2, method: "shutdown" }));
  child.stdin.write(frame({ jsonrpc: "2.0", method: "exit" }));
  child.stdin.end();

  const code = await new Promise<number | null>((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`'${settings.executable}' did not exit within ${HANDSHAKE_TIMEOUT_MS} ms`));
    }, HANDSHAKE_TIMEOUT_MS);
    child.on("close", (status) => {
      clearTimeout(timer);
      resolve(status);
    });
  });
  assert.equal(code, 0, "the server did not exit cleanly");
  return firstMessage(Buffer.concat(chunks));
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
