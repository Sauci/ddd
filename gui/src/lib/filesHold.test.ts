import { describe, expect, test } from "vitest";
import type { FilesPlanReply, FilesReply, IncludedEntryReply } from "../api/types";
import { type FilesHold, filesHoldAfter, filesHoldOf, filesShown } from "./filesHold";

const PROJECT = "/work/p/project.ddd.json";

/** A plan as `GET /api/files-plan` answers New file's or Add's: the description's own change
 * appending `raw` at `pointer`, after a created file's change where `created` names one. */
function plan(pointer: string, raw: string, created: string | null = null): FilesPlanReply {
  const description = {
    file: PROJECT,
    fingerprint: "f1",
    operations: [{ op: pointer.endsWith("]") ? "insert" : "set", pointer, raw }],
    hunks: [],
  } as FilesPlanReply["changes"][number];
  const made =
    created === null
      ? []
      : [
          {
            file: created,
            fingerprint: null,
            operations: [{ op: "set", pointer: "", raw: "{}" }],
            hunks: [],
          } as FilesPlanReply["changes"][number],
        ];
  return {
    revision: 4,
    changes: [...made, description],
    unjudged: null,
    brings: [],
    kept_by: null,
  };
}

function entry(index: number, text: string, key: string): IncludedEntryReply {
  return { index, entry: text, names: true, key, files: [key], findings: 0 };
}

const UNITS = entry(0, "units.ddd.json", "/work/p/units.ddd.json");
const PATTERN: IncludedEntryReply = {
  index: 1,
  entry: "components/*.ddd.json",
  names: false,
  key: "/work/p/components/*.ddd.json",
  files: ["/work/p/components/c00000.ddd.json"],
  findings: 0,
};

function served(revision: number, entries: IncludedEntryReply[]): FilesReply {
  return { revision, project: PROJECT, entries, creatable: ["component"] };
}

describe("what the Files tab holds of its own Apply", () => {
  test("New file's: the created file's own entry, appended where the plan inserts it", () => {
    const applied = plan("project.includes[2]", '"bench.ddd.json"', "/work/p/bench.ddd.json");
    expect(filesHoldOf(7, applied, PROJECT)).toEqual({
      edit: 7,
      entry: entry(2, "bench.ddd.json", "/work/p/bench.ddd.json"),
      landed: null,
    });
  });

  test("New file's key is the created file's path as the server names it, not the page's join", () => {
    // A description reached through a link: the server names the file it creates by the
    // directory the link leads to, and so keys the entry; the page's own join could not.
    const applied = plan("project.includes[2]", '"bench.ddd.json"', "/real/p/bench.ddd.json");
    expect(filesHoldOf(7, applied, PROJECT)?.entry.key).toBe("/real/p/bench.ddd.json");
  });

  test("Add's: the entry as typed, keyed by the description's directory joined with it", () => {
    const applied = plan("project.includes[2]", '"added/a1.ddd.json"');
    expect(filesHoldOf(8, applied, PROJECT)).toEqual({
      edit: 8,
      entry: entry(2, "added/a1.ddd.json", "/work/p/added/a1.ddd.json"),
      landed: null,
    });
  });

  test("Add's key folds the entry's ., .. and doubled / as the path is read", () => {
    const applied = plan("project.includes[2]", '"./../shared/./x.ddd.json"');
    const hold = filesHoldOf(8, applied, PROJECT);
    expect(hold?.entry.key).toBe("/work/shared/x.ddd.json");
    expect(hold?.entry.entry).toBe("./../shared/./x.ddd.json");
    const doubled = plan("project.includes[2]", '"sub//x.ddd.json"');
    expect(filesHoldOf(8, doubled, PROJECT)?.entry.key).toBe("/work/p/sub/x.ddd.json");
  });

  test("Add's key is an absolute entry itself, a drive's as a root's", () => {
    const rooted = plan("project.includes[2]", '"/elsewhere/x.ddd.json"');
    expect(filesHoldOf(8, rooted, PROJECT)?.entry.key).toBe("/elsewhere/x.ddd.json");
    const windows = "C:/work/p/project.ddd.json";
    const drive = plan("project.includes[2]", '"D:/x.ddd.json"');
    drive.changes[0] = {
      ...(drive.changes[0] as FilesPlanReply["changes"][number]),
      file: windows,
    };
    expect(filesHoldOf(8, drive, windows)?.entry.key).toBe("D:/x.ddd.json");
  });

  test("a description with no includes is given the list whole: its one entry is the first", () => {
    const applied = plan("project.includes", '["bench.ddd.json"]', "/work/p/bench.ddd.json");
    expect(filesHoldOf(7, applied, PROJECT)?.entry).toEqual(
      entry(0, "bench.ddd.json", "/work/p/bench.ddd.json"),
    );
  });

  test("a removal holds nothing: there is no row of its own to show", () => {
    const removal: FilesPlanReply = { ...plan("project.includes[1]", "null"), kept_by: null };
    removal.changes = [
      {
        file: PROJECT,
        fingerprint: "f1",
        operations: [{ op: "remove", pointer: "project.includes[1]", raw: null }],
        hunks: [],
      },
    ];
    expect(filesHoldOf(9, removal, PROJECT)).toBeNull();
  });

  test("a plan changing no description of this project's holds nothing", () => {
    const elsewhere = plan("project.includes[2]", '"x.ddd.json"');
    expect(filesHoldOf(8, elsewhere, "/other/project.ddd.json")).toBeNull();
  });
});

describe("how long the tab holds it", () => {
  const held: FilesHold = {
    edit: 7,
    entry: entry(2, "bench.ddd.json", "/work/p/bench.ddd.json"),
    landed: null,
  };
  const before = served(4, [UNITS, PATTERN]);
  const none: ReadonlyMap<number, number> = new Map();

  test("nothing held, nothing to hold", () => {
    expect(filesHoldAfter(null, none, { revision: 4, edits: 6 }, before)).toBeNull();
  });

  test("held while the answer is the one from before the edit", () => {
    expect(filesHoldAfter(held, none, { revision: 4, edits: 6 }, before)).toBe(held);
  });

  test("ended, for good, once an answer carries the entry at its own place", () => {
    const after = served(4, [UNITS, PATTERN, entry(2, "bench.ddd.json", "/work/p/bench.ddd.json")]);
    expect(filesHoldAfter(held, none, { revision: 4, edits: 7 }, after)).toBeNull();
  });

  test("another entry at its place is not it", () => {
    const other = served(4, [UNITS, PATTERN, entry(2, "other.ddd.json", "/work/p/other.ddd.json")]);
    expect(filesHoldAfter(held, none, { revision: 4, edits: 6 }, other)).toBe(held);
  });

  test("with no state yet, held as it is", () => {
    expect(filesHoldAfter(held, none, null, before)).toBe(held);
  });

  test("an entry of the same words at another place is not it", () => {
    const named = served(4, [UNITS, entry(1, "bench.ddd.json", "/work/p/bench.ddd.json")]);
    expect(filesHoldAfter(held, none, { revision: 4, edits: 6 }, named)).toBe(held);
  });

  test("ended at once by the page's own undo of the edit", () => {
    expect(filesHoldAfter(held, new Map([[7, 8]]), { revision: 4, edits: 6 }, before)).toBeNull();
  });

  test("stamped with the first revision the page sees include the edit", () => {
    expect(filesHoldAfter(held, none, { revision: 5, edits: 7 }, before)).toEqual({
      ...held,
      landed: 5,
    });
  });

  test("ended once an answer of that revision, or a later one, has come, whatever it says", () => {
    const stamped = { ...held, landed: 5 };
    expect(filesHoldAfter(stamped, none, { revision: 5, edits: 7 }, before)).toBe(stamped);
    expect(filesHoldAfter(stamped, none, { revision: 5, edits: 7 }, served(5, [UNITS]))).toBeNull();
  });

  test("before any answer, held as it is", () => {
    expect(filesHoldAfter(held, none, { revision: 4, edits: 6 }, undefined)).toBe(held);
  });
});

describe("what the tab draws", () => {
  const before = served(4, [UNITS, PATTERN]);

  test("the answer itself while nothing is held", () => {
    expect(filesShown(null, before)).toBe(before);
  });

  test("the answer with the held entry after its own, the answer left as it was", () => {
    const held: FilesHold = {
      edit: 7,
      entry: entry(2, "bench.ddd.json", "/work/p/bench.ddd.json"),
      landed: null,
    };
    expect(filesShown(held, before)).toEqual(served(4, [UNITS, PATTERN, held.entry]));
    expect(before.entries).toEqual([UNITS, PATTERN]);
  });
});
