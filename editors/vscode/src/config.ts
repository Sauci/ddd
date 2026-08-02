/**
 * How the settings become a command line.
 *
 * Deliberately free of any import of `vscode`: this is the only part of the extension with a
 * decision in it, and keeping it out of the editor api is what lets it be tested by running
 * it rather than by starting an editor around it. Everything in `extension.ts` is wiring.
 */

/** What the extension needs to know to start a server. */
export interface Settings {
  /** The `ddd` command, looked up on the PATH when it is a bare name. */
  executable: string;
  /** Directories holding a build; empty means "search the usual names". */
  buildDirectories: string[];
}

export const DEFAULT_EXECUTABLE = "ddd";

/** The smallest part of the vscode configuration api this needs, so a test can stand in. */
export interface Section {
  get<T>(key: string, fallback: T): T;
}

export function settingsFrom(section: Section): Settings {
  return {
    executable: section.get<string>("executable", DEFAULT_EXECUTABLE).trim() || DEFAULT_EXECUTABLE,
    buildDirectories: section.get<string[]>("buildDirectories", []),
  };
}

/**
 * The arguments to start the server with.
 *
 * Blank entries are dropped rather than passed on. A settings array is edited by hand and an
 * empty string is what a half-finished edit leaves behind; forwarding it would make the server
 * search a directory named "", which fails in a way that says nothing about the cause.
 */
export function serverArguments(settings: Settings): string[] {
  const args = ["lsp"];
  for (const directory of settings.buildDirectories) {
    const trimmed = directory.trim();
    if (trimmed.length > 0) {
      args.push("-b", trimmed);
    }
  }
  return args;
}
