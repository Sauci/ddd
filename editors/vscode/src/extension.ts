/**
 * The launcher.
 *
 * VS Code has no way to start a language server without an extension, which is the whole
 * reason this exists: everything a user sees - the findings, going to a definition, finding
 * references - comes from `ddd lsp` and would work in any editor that can start it. Nothing
 * here adds a feature, so nothing here should grow one without a reason that could not be
 * served from the server instead.
 *
 * Only `*.ddd.json` is claimed. Those files are json and the json language service keeps
 * working on them: the published schemas go on doing structure while the server does meaning.
 */

import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
} from "vscode-languageclient/node";

import { serverArguments, settingsFrom } from "./config";

const SECTION = "ddd";
const DOCUMENTS = "**/*.ddd.json";

let client: LanguageClient | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  context.subscriptions.push(
    vscode.commands.registerCommand("ddd.restartServer", async () => {
      await stop();
      await start();
    }),
  );
  await start();
}

export async function deactivate(): Promise<void> {
  await stop();
}

async function start(): Promise<void> {
  const settings = settingsFrom(vscode.workspace.getConfiguration(SECTION));
  const server: ServerOptions = {
    command: settings.executable,
    args: serverArguments(settings),
  };
  const options: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "json", pattern: DOCUMENTS }],
    // The server reads the description files from disk rather than from the editor, so it is
    // the saves it has to hear about; watching them also covers a file changed by a build or
    // by a branch switch, which no document event would report.
    synchronize: { fileEvents: vscode.workspace.createFileSystemWatcher(DOCUMENTS) },
  };
  client = new LanguageClient(SECTION, "DDD", server, options);
  try {
    await client.start();
  } catch (reason) {
    client = undefined;
    // The overwhelmingly likely cause is that `ddd` is not on the PATH of the editor, which
    // is its own puzzle when it is on the PATH of a terminal, so the message says where to
    // put the answer rather than only what went wrong.
    void vscode.window.showErrorMessage(
      `DDD: could not start '${settings.executable}' (${String(reason)}). ` +
        `Install it, or set 'ddd.executable' to its full path.`,
    );
  }
}

async function stop(): Promise<void> {
  const running = client;
  client = undefined;
  await running?.stop();
}
