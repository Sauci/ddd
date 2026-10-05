import { describe, expect, test } from "vitest";
import type { FilesPlanRequest } from "../api/client";
import type { FilesPlanReply, FilesReply, IncludedEntryReply } from "../api/types";
import { type FilesHold, filesHoldAfter, filesHoldOf, filesShown } from "./filesHold";

const PROJECT = "/work/p/project.ddd.json";

/** What New file and Add are applied with beside their plans: the plan alone says what their
 * entry is. */
const CREATE: FilesPlanRequest = {
  action: "create",
  kind: "component",
  name: "bench",
  component: "Bench",
};
const ADD: FilesPlanRequest = { action: "add", path: "added/a1.ddd.json" };

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

/** A plan as `GET /api/files-plan` answers Remove's: the description's own change taking out
 * the entries at `indices`, the last first, as `remove_plan` orders them. */
function removal(...indices: number[]): FilesPlanReply {
  return {
    revision: 4,
    changes: [
      {
        file: PROJECT,
        fingerprint: "f1",
        operations: indices.map((index) => ({
          op: "remove",
          pointer: `project.includes[${index}]`,
          raw: null,
        })),
        hunks: [],
      } as FilesPlanReply["changes"][number],
    ],
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
    expect(filesHoldOf(7, applied, PROJECT, CREATE)).toEqual({
      edit: 7,
      entry: entry(2, "bench.ddd.json", "/work/p/bench.ddd.json"),
      landed: null,
    });
  });

  test("New file's key is the created file's path as the server names it, not the page's join", () => {
    // A description reached through a link: the server names the file it creates by the
    // directory the link leads to, and so keys the entry; the page's own join could not.
    const applied = plan("project.includes[2]", '"bench.ddd.json"', "/real/p/bench.ddd.json");
    expect(filesHoldOf(7, applied, PROJECT, CREATE)).toMatchObject({
      entry: { key: "/real/p/bench.ddd.json" },
    });
  });

  test("Add's: the entry as typed, keyed by the description's directory joined with it", () => {
    const applied = plan("project.includes[2]", '"added/a1.ddd.json"');
    expect(filesHoldOf(8, applied, PROJECT, ADD)).toEqual({
      edit: 8,
      entry: entry(2, "added/a1.ddd.json", "/work/p/added/a1.ddd.json"),
      landed: null,
    });
  });

  test("Add's key folds the entry's ., .. and doubled / as the path is read", () => {
    const applied = plan("project.includes[2]", '"./../shared/./x.ddd.json"');
    expect(filesHoldOf(8, applied, PROJECT, ADD)).toMatchObject({
      entry: { key: "/work/shared/x.ddd.json", entry: "./../shared/./x.ddd.json" },
    });
    const doubled = plan("project.includes[2]", '"sub//x.ddd.json"');
    expect(filesHoldOf(8, doubled, PROJECT, ADD)).toMatchObject({
      entry: { key: "/work/p/sub/x.ddd.json" },
    });
  });

  test("Add's key is an absolute entry itself, a drive's as a root's", () => {
    const rooted = plan("project.includes[2]", '"/elsewhere/x.ddd.json"');
    expect(filesHoldOf(8, rooted, PROJECT, ADD)).toMatchObject({
      entry: { key: "/elsewhere/x.ddd.json" },
    });
    const windows = "C:/work/p/project.ddd.json";
    const drive = plan("project.includes[2]", '"D:/x.ddd.json"');
    drive.changes[0] = {
      ...(drive.changes[0] as FilesPlanReply["changes"][number]),
      file: windows,
    };
    expect(filesHoldOf(8, drive, windows, ADD)).toMatchObject({ entry: { key: "D:/x.ddd.json" } });
  });

  test("a description with no includes is given the list whole: its one entry is the first", () => {
    const applied = plan("project.includes", '["bench.ddd.json"]', "/work/p/bench.ddd.json");
    expect(filesHoldOf(7, applied, PROJECT, CREATE)).toMatchObject({
      entry: entry(0, "bench.ddd.json", "/work/p/bench.ddd.json"),
    });
  });

  test("Remove's: the key it was asked with, every entry of which the plan takes out", () => {
    const request: FilesPlanRequest = { action: "remove", path: "/work/p/units.ddd.json" };
    expect(filesHoldOf(9, removal(3, 0), PROJECT, request)).toEqual({
      edit: 9,
      removed: "/work/p/units.ddd.json",
      landed: null,
    });
  });

  test("a plan of New file or Add whose change of the description writes nothing holds nothing", () => {
    expect(filesHoldOf(8, removal(1), PROJECT, ADD)).toBeNull();
  });

  test("a plan changing no description of this project's holds nothing", () => {
    const elsewhere = plan("project.includes[2]", '"x.ddd.json"');
    expect(filesHoldOf(8, elsewhere, "/other/project.ddd.json", ADD)).toBeNull();
    const request: FilesPlanRequest = { action: "remove", path: "/work/p/units.ddd.json" };
    expect(filesHoldOf(9, removal(0), "/other/project.ddd.json", request)).toBeNull();
  });
});

describe("how long the tab holds what it added", () => {
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

describe("how long the tab holds what it removed", () => {
  const held: FilesHold = { edit: 9, removed: "/work/p/units.ddd.json", landed: null };
  const before = served(4, [UNITS, PATTERN]);
  const none: ReadonlyMap<number, number> = new Map();

  test("held while the answer still carries an entry of that key", () => {
    expect(filesHoldAfter(held, none, { revision: 4, edits: 8 }, before)).toBe(held);
  });

  test("an entry of that key at another place, or of other words, is one all the same", () => {
    const moved = served(4, [PATTERN, { ...UNITS, index: 1, entry: "./units.ddd.json" }]);
    expect(filesHoldAfter(held, none, { revision: 4, edits: 8 }, moved)).toBe(held);
  });

  test("ended, for good, once an answer carries no entry of that key", () => {
    const after = served(4, [{ ...PATTERN, index: 0 }]);
    expect(filesHoldAfter(held, none, { revision: 4, edits: 9 }, after)).toBeNull();
  });

  test("a pattern's file of that key is no entry of it: its row is the pattern's", () => {
    const kept = served(4, [{ ...PATTERN, index: 0, files: ["/work/p/units.ddd.json"] }]);
    expect(filesHoldAfter(held, none, { revision: 4, edits: 9 }, kept)).toBeNull();
  });

  test("ended at once by the page's own undo of the edit", () => {
    expect(filesHoldAfter(held, new Map([[9, 10]]), { revision: 4, edits: 8 }, before)).toBeNull();
  });

  test("stamped with the first revision the page sees include the edit", () => {
    expect(filesHoldAfter(held, none, { revision: 5, edits: 9 }, before)).toEqual({
      ...held,
      landed: 5,
    });
  });

  test("ended once an answer of that revision, or a later one, has come, whatever it says", () => {
    const stamped = { ...held, landed: 5 };
    expect(filesHoldAfter(stamped, none, { revision: 5, edits: 9 }, before)).toBe(stamped);
    expect(filesHoldAfter(stamped, none, { revision: 5, edits: 9 }, served(5, [UNITS]))).toBeNull();
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

  test("the answer without every entry of the key removed, the answer left as it was", () => {
    const twice = served(4, [UNITS, PATTERN, { ...UNITS, index: 2, entry: "./units.ddd.json" }]);
    const held: FilesHold = { edit: 9, removed: "/work/p/units.ddd.json", landed: null };
    expect(filesShown(held, twice)).toEqual(served(4, [PATTERN]));
    expect(twice.entries).toHaveLength(3);
  });

  test("a pattern matching the file removed keeps its own row and its child of that file", () => {
    const pattern = { ...PATTERN, files: ["/work/p/units.ddd.json"] };
    const held: FilesHold = { edit: 9, removed: "/work/p/units.ddd.json", landed: null };
    expect(filesShown(held, served(4, [UNITS, pattern]))).toEqual(served(4, [pattern]));
  });
});
