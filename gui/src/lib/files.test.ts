import { describe, expect, test } from "vitest";
import type { FilesReply, IncludedEntryReply, SourceFile } from "../api/types";
import { rowsOf } from "./files";

const PROJECT = "C:/work/demo/demo.ddd.json";
const A = "C:/work/demo/a.ddd.json";
const SENSORS_X = "C:/work/demo/sensors/x.ddd.json";
const SENSORS_Y = "C:/work/demo/sensors/y.ddd.json";

function entry(fields: Partial<IncludedEntryReply> = {}): IncludedEntryReply {
  return {
    index: 0,
    entry: "a.ddd.json",
    names: true,
    key: A,
    files: [A],
    findings: 0,
    ...fields,
  };
}

function sourceFile(fields: Partial<SourceFile> = {}): SourceFile {
  return {
    path: A,
    kind: "component",
    name: "A",
    loaded: true,
    fingerprint: "x",
    findings: { error: 0, warning: 0, info: 0 },
    ...fields,
  };
}

function reply(entries: IncludedEntryReply[]): FilesReply {
  return {
    revision: 3,
    project: PROJECT,
    entries,
    creatable: ["component", "types", "units", "constants", "sections", "rasters"],
  };
}

describe("a literal entry", () => {
  test("its row is its file, and its count is the entry's plus the file's own", () => {
    const file = sourceFile({ findings: { error: 1, warning: 2, info: 0 } });
    const rows = rowsOf(reply([entry({ findings: 1 })]), [file]);
    expect(rows).toEqual([
      { entry: entry({ findings: 1 }), file, key: A, findings: 4, child: false },
    ]);
  });

  test("a file the revision did not read is a row naming it all the same, with `file: null`", () => {
    // A schema error in the root's own description stops its read before its includes, so no
    // file they bring is among `State.files` - the row still names the file, apart from a row
    // whose entry names nothing at all.
    const rows = rowsOf(reply([entry({ findings: 2 })]), []);
    expect(rows).toEqual([
      { entry: entry({ findings: 2 }), file: null, key: A, findings: 2, child: false },
    ]);
  });
});

describe("a pattern matching files", () => {
  test("its own row carries no file, and its children carry theirs, indented beneath it", () => {
    const x = sourceFile({
      path: SENSORS_X,
      name: "X",
      findings: { error: 1, warning: 0, info: 0 },
    });
    const y = sourceFile({
      path: SENSORS_Y,
      name: "Y",
      findings: { error: 0, warning: 1, info: 1 },
    });
    const pattern = entry({
      entry: "sensors/*.ddd.json",
      names: false,
      key: "C:/work/demo/sensors/*.ddd.json",
      files: [SENSORS_X, SENSORS_Y],
      findings: 0,
    });
    const rows = rowsOf(reply([pattern]), [x, y]);
    expect(rows).toEqual([
      { entry: pattern, file: null, key: pattern.key, findings: 3, child: false },
      { entry: pattern, file: x, key: SENSORS_X, findings: 1, child: true },
      { entry: pattern, file: y, key: SENSORS_Y, findings: 2, child: true },
    ]);
  });

  test("a matched file the revision did not read is a child row with `file: null`", () => {
    // A pattern can match a file created since the revision, which the revision never read.
    const pattern = entry({
      entry: "sensors/*.ddd.json",
      names: false,
      key: "C:/work/demo/sensors/*.ddd.json",
      files: [SENSORS_X],
      findings: 0,
    });
    const rows = rowsOf(reply([pattern]), []);
    expect(rows).toEqual([
      { entry: pattern, file: null, key: pattern.key, findings: 0, child: false },
      { entry: pattern, file: null, key: SENSORS_X, findings: 0, child: true },
    ]);
  });
});

describe("an entry naming nothing", () => {
  test("a pattern matching no file counts its own findings alone, and has no children", () => {
    const pattern = entry({
      entry: "nothing/*.ddd.json",
      names: false,
      key: "C:/work/demo/nothing/*.ddd.json",
      files: [],
      findings: 1,
    });
    const rows = rowsOf(reply([pattern]), []);
    expect(rows).toEqual([
      { entry: pattern, file: null, key: pattern.key, findings: 1, child: false },
    ]);
  });

  test("a plain path naming no file is the same shape as a pattern matching none", () => {
    const missing = entry({
      entry: "missing.ddd.json",
      names: false,
      key: "C:/work/demo/missing.ddd.json",
      files: [],
      findings: 1,
    });
    const rows = rowsOf(reply([missing]), []);
    expect(rows).toEqual([
      { entry: missing, file: null, key: missing.key, findings: 1, child: false },
    ]);
  });
});

test("every entry's rows are kept in the description's own order", () => {
  const literal = entry({ index: 0 });
  const pattern = entry({
    index: 1,
    entry: "sensors/*.ddd.json",
    names: false,
    key: "C:/work/demo/sensors/*.ddd.json",
    files: [SENSORS_X],
    findings: 0,
  });
  const nothing = entry({
    index: 2,
    entry: "missing.ddd.json",
    names: false,
    key: "C:/work/demo/missing.ddd.json",
    files: [],
    findings: 1,
  });
  const file = sourceFile();
  const x = sourceFile({ path: SENSORS_X, name: "X" });
  const rows = rowsOf(reply([literal, pattern, nothing]), [file, x]);
  expect(rows.map((row) => row.key)).toEqual([A, pattern.key, SENSORS_X, nothing.key]);
  expect(rows.map((row) => row.child)).toEqual([false, false, true, false]);
});

test("no entries at all is no rows", () => {
  expect(rowsOf(reply([]), [])).toEqual([]);
});
