/**
 * How the settings become a command line, and when the server is wanted.
 *
 * Deliberately free of any import of `vscode`: these are the only parts of the extension with a
 * decision in them, and keeping them out of the editor api is what lets them be tested by
 * running them rather than by starting an editor around them. Everything in `extension.ts` is
 * wiring.
 */

/** How the name of a description ends. */
const SUFFIX = ".ddd.json";

/** The documents the server is handed: a `*.ddd.json` on disk, read as json. */
export const DESCRIPTIONS = { scheme: "file", language: "json", pattern: `**/*${SUFFIX}` } as const;

/** The smallest part of a vscode document the decision needs, so a test can stand in. */
export interface Opened {
  readonly languageId: string;
  readonly uri: { readonly scheme: string; readonly path: string };
}

/** Whether a document is one the server is handed (`DESCRIPTIONS`). */
export function describes(document: Opened): boolean {
  return (
    document.uri.scheme === DESCRIPTIONS.scheme &&
    document.languageId === DESCRIPTIONS.language &&
    document.uri.path.endsWith(SUFFIX)
  );
}

/**
 * Whether the server is wanted yet: once a description is open, or the workspace holds one.
 *
 * The manifest activates the extension on any json document as well as on a workspace holding a
 * description, since a description opened outside a folder, or created after the window opened,
 * is announced by nothing else. Started on activation, the server ran for any json file of any
 * trusted workspace, and where `ddd` is not installed its error was shown there; so a json file
 * of another name, in a workspace holding no description, starts nothing. The workspace is
 * searched only where no open document settles it.
 */
export async function wanted(
  open: Iterable<Opened>,
  holdsADescription: () => PromiseLike<boolean>,
): Promise<boolean> {
  for (const document of open) {
    if (describes(document)) {
      return true;
    }
  }
  return holdsADescription();
}

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
