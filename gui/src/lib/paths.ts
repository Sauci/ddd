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

/**
 * Each of `paths` as `toldApart` names it among all of them, in their order - by counting rather
 * than by comparing each with every other: how many of `paths` end in each run of parts is counted
 * once, and a path is named by its parts from the first depth at which no other path ends alike,
 * those equal to it aside, as `toldApart` sets `path` itself aside. Two runs of a different number
 * of parts never read alike (a part holds no `/`), so a path shorter than a depth ends alike with
 * none there, as `endsAlike` finds. The banner under the masthead names every file of the project
 * that did not load (lib/unloaded.ts), on each render: compared pair by pair, the 3,334 files of a
 * project whose every component failed took seconds to name.
 */
export function toldApartAll(paths: readonly string[]): string[] {
  const named = paths.map((path) => ({ path, ends: endsOf(path) }));
  const ending = new Map<string, number>();
  const listed = new Map<string, number>();
  for (const { path, ends } of named) {
    for (const end of ends) ending.set(end, counted(ending, end) + 1);
    listed.set(path, counted(listed, path) + 1);
  }
  return named.map(({ path, ends }) => {
    const itself = counted(listed, path);
    // The whole path, the last of its ends, is one no other path ends in: found at the latest.
    let name = path;
    for (const end of ends) {
      if (counted(ending, end) === itself) {
        name = end;
        break;
      }
    }
    return name;
  });
}

/** The runs of parts a path ends in, joined: its last part, then its last two, up to the whole of
 * it. */
function endsOf(path: string): string[] {
  const ends: string[] = [];
  let end: string | null = null;
  for (const part of path.split("/").reverse()) {
    end = end === null ? part : `${part}/${end}`;
    ends.push(end);
  }
  return ends;
}

/** How many times `key` is counted in `counts`: none where it is not. */
function counted(counts: ReadonlyMap<string, number>, key: string): number {
  return counts.get(key) ?? 0;
}

/** Whether two paths end in the same `depth` parts - all of one that has fewer. */
function endsAlike(theirs: readonly string[], parts: readonly string[], depth: number): boolean {
  return theirs.slice(-depth).join("/") === parts.slice(-depth).join("/");
}
