/**
 * A file's path as the Table tab's File column shows it (part 17's task 9, Ruling T9-5): relative
 * to the directory of the project's own description, the way an `includes` entry is spelled -
 * `components/controller.ddd.json` - rather than absolute. An absolute path leads with every
 * directory down to the project, the same on every row, and a one-line cell cut at its end then
 * loses the part that differs, the file's own name; a relative one starts where the rows start to
 * differ. A file above that directory keeps a `../` for each level up, as an `includes` entry
 * reaching it would; a file on another root - another drive or another share, on Windows - has no
 * relative path at all, and keeps its absolute one.
 *
 * Both paths arrive absolute and posix-separated (`State.project`, `SourceFile.path`: the server
 * writes `as_posix()` of each), so a Windows path arrives as `C:/work/demo/a.ddd.json` and a
 * share's as `//server/share/demo/a.ddd.json`. A path's root is therefore its first part - `C:`,
 * or the empty part before a posix path's leading `/` - or, for a share, its first four: "", "",
 * the server and the share. Parts are compared as written, case included: the server writes
 * every path of one project the same way.
 *
 * Unlike `relativeToProject` (lib/findings.ts), which names a file outside that directory by its
 * base name alone, this keeps the whole way to it: a File cell names one file among a project's
 * components, and two of them may share a base name in different directories.
 */
export function shownPath(project: string, path: string): string {
  const from = project.split("/").slice(0, -1);
  const to = path.split("/");
  const root = rootLength(from);
  if (rootLength(to) !== root || from.slice(0, root).join("/") !== to.slice(0, root).join("/")) {
    return path;
  }
  let shared = root;
  while (shared < from.length && from[shared] === to[shared]) shared += 1;
  return [...from.slice(shared).map(() => ".."), ...to.slice(shared)].join("/");
}

/** How many of a path's parts make its root: four for a share (`//server/share/...` splits into
 * "", "", the server and the share), one otherwise (a drive, `C:`, or a posix path's empty first
 * part). */
function rootLength(parts: readonly string[]): number {
  return parts[0] === "" && parts[1] === "" ? 4 : 1;
}

/**
 * `path` as a sentence naming the files `among` names it - what the server's own sentences answer
 * (`ddd.lsp.navigation.told_apart`), so that one file is one name on the page and in a refusal:
 * by its name alone, as a sentence always named a file, unless another of `among` has that name
 * too, and then by its path from the first directory up that the two do not share, or in full
 * where nothing short of the root tells them apart.
 *
 * By their names alone, two files in two folders were one name twice, and a reader sent to repair
 * one opened whichever came first. Walked over the parts of the absolute posix path the server
 * writes, its root among them, so that all of them together spell the path in full; `path` itself
 * is not compared with, should `among` hold it.
 */
export function toldApart(path: string, among: readonly string[]): string {
  const parts = path.split("/");
  const others = among.filter((other) => other !== path).map((other) => other.split("/"));
  let depth = 1;
  while (depth < parts.length && others.some((theirs) => endsAlike(theirs, parts, depth))) {
    depth += 1;
  }
  return parts.slice(-depth).join("/");
}

/** Whether two paths end in the same `depth` parts - all of one that has fewer. */
function endsAlike(theirs: readonly string[], parts: readonly string[], depth: number): boolean {
  return theirs.slice(-depth).join("/") === parts.slice(-depth).join("/");
}
