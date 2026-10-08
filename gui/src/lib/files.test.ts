import { describe, expect, test } from "vitest";
import type {
  FilesPlanReply,
  FilesReply,
  IncludedEntryReply,
  PlannedChange,
  SourceFile,
} from "../api/types";
import {
  asksComponentName,
  cellsOf,
  fileAdd,
  fileCreate,
  fileRemoval,
  previewOf,
  removalAsked,
  rowsOf,
  selectedIndices,
} from "./files";

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

  test("a file a literal entry also names keeps two rows of one key, each its own count", () => {
    // Rulings 16: `New file` appends a literal entry even where a pattern already matches the new
    // name, so the loader reads the file once but the tab still offers both entries as separate
    // rows - each its own request to act on, `FileRow.key`'s own doc says how. `rowsOf` never
    // de-duplicates by `key`: a later "don't show a file twice" tidy-up would silently take one
    // of the two rows away. The entries' own findings are synthetic, as the first literal-entry
    // test's are, chosen only to tell the two same-keyed rows' counts apart.
    const file = sourceFile({ findings: { error: 1, warning: 0, info: 0 } });
    const literal = entry({
      index: 0,
      entry: "a.ddd.json",
      names: true,
      key: A,
      files: [A],
      findings: 2,
    });
    const pattern = entry({
      index: 1,
      entry: "*.ddd.json",
      names: false,
      key: "C:/work/demo/*.ddd.json",
      files: [A],
      findings: 3,
    });
    const rows = rowsOf(reply([literal, pattern]), [file]);
    expect(rows).toEqual([
      { entry: literal, file, key: A, findings: 3, child: false },
      { entry: pattern, file: null, key: pattern.key, findings: 4, child: false },
      { entry: pattern, file, key: A, findings: 1, child: true },
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

describe("cellsOf", () => {
  // `rowsOf(...)[i]` would be `FileRow | undefined` under `noUncheckedIndexedAccess`, destructuring
  // included (measured: `tsc` refuses `cellsOf(row, PROJECT)` for a `const [row] = rowsOf(...)`
  // the same way `findings.test.ts`'s own comment warns index access would). `.map()` sidesteps it
  // and doubles as the whole-array assertion every arm below is pinned with.
  const cells = (entries: IncludedEntryReply[], files: SourceFile[]) =>
    rowsOf(reply(entries), files).map((row) => cellsOf(row, PROJECT));

  test("a literal entry's own row, loaded, draws its entry, kind and count", () => {
    const file = sourceFile({ findings: { error: 1, warning: 2, info: 0 } });
    expect(cells([entry({ findings: 1 })], [file])).toEqual([
      { entry: "a.ddd.json", kind: "component", state: "", findings: "4" },
    ]);
  });

  test('a literal entry\'s own row that did not load draws "did not load"', () => {
    const file = sourceFile({ loaded: false });
    expect(cells([entry()], [file])).toEqual([
      { entry: "a.ddd.json", kind: "component", state: "did not load", findings: "" },
    ]);
  });

  test('a literal entry\'s own row the revision did not read draws "not read by the last analysis"', () => {
    // A schema error in the root's own description stops its read before its includes, so no
    // file it brings is among `State.files` - a row naming a file all the same (`FileRow.file`'s
    // own doc), never the same as "an entry naming nothing" below, which draws differently.
    expect(cells([entry({ findings: 2 })], [])).toEqual([
      { entry: "a.ddd.json", kind: "", state: "not read by the last analysis", findings: "2" },
    ]);
  });

  test("a pattern's own row draws its own line; a loaded child draws its file's own path, never its name", () => {
    // Spec §2: "beneath it every file it matched" - a file, not the component SENSORS_X happens
    // to declare ("X"), which is why the child reads "sensors/x.ddd.json" and not "X". The
    // pattern's own row above it has no kind, state or count of its own to draw either.
    const x = sourceFile({ path: SENSORS_X, name: "X" });
    const pattern = entry({
      entry: "sensors/*.ddd.json",
      names: false,
      key: "C:/work/demo/sensors/*.ddd.json",
      files: [SENSORS_X],
      findings: 0,
    });
    expect(cells([pattern], [x])).toEqual([
      { entry: "sensors/*.ddd.json", kind: "", state: "", findings: "" },
      { entry: "sensors/x.ddd.json", kind: "component", state: "", findings: "" },
    ]);
  });

  test('a pattern\'s matched file the revision did not read draws "not read by the last analysis" too', () => {
    // A pattern can match a file created since the revision, which the revision never read - the
    // same sentence a literal's own unread row draws above, and for the same reason: this row
    // names a file all the same, `FileRow.file`'s own doc says so of a pattern's child exactly as
    // it does of a literal's own row.
    const pattern = entry({
      entry: "sensors/*.ddd.json",
      names: false,
      key: "C:/work/demo/sensors/*.ddd.json",
      files: [SENSORS_X],
      findings: 0,
    });
    expect(cells([pattern], [])).toEqual([
      { entry: "sensors/*.ddd.json", kind: "", state: "", findings: "" },
      {
        entry: "sensors/x.ddd.json",
        kind: "",
        state: "not read by the last analysis",
        findings: "",
      },
    ]);
  });

  test('a pattern matching no file draws "names no file"', () => {
    const pattern = entry({
      entry: "nothing/*.ddd.json",
      names: false,
      key: "C:/work/demo/nothing/*.ddd.json",
      files: [],
      findings: 1,
    });
    expect(cells([pattern], [])).toEqual([
      { entry: "nothing/*.ddd.json", kind: "", state: "names no file", findings: "1" },
    ]);
  });

  test('a plain path naming no file draws "names no file" too', () => {
    const missing = entry({
      entry: "missing.ddd.json",
      names: false,
      key: "C:/work/demo/missing.ddd.json",
      files: [],
      findings: 1,
    });
    expect(cells([missing], [])).toEqual([
      { entry: "missing.ddd.json", kind: "", state: "names no file", findings: "1" },
    ]);
  });
});

describe("selectedIndices", () => {
  test("two rows of one key are both selected", () => {
    // The literal-and-pattern-share-a-key shape "a file a literal entry also names keeps two
    // rows of one key" above already builds, now asked which positions A's own key selects.
    const file = sourceFile();
    const literal = entry({ index: 0, entry: "a.ddd.json", names: true, key: A, files: [A] });
    const pattern = entry({
      index: 1,
      entry: "*.ddd.json",
      names: false,
      key: "C:/work/demo/*.ddd.json",
      files: [A],
    });
    const rows = rowsOf(reply([literal, pattern]), [file]);
    // rows: [0] the literal's own (key A), [1] the pattern's own (key "*.ddd.json"), [2] the
    // pattern's one child (key A too) - position 1 must be left out, never only the first found.
    expect(selectedIndices(rows, A)).toEqual([0, 2]);
  });

  test("a key that no row holds selects none", () => {
    const rows = rowsOf(reply([entry()]), [sourceFile()]);
    expect(selectedIndices(rows, "C:/work/demo/nothing-any-row-carries.ddd.json")).toEqual([]);
  });
});

describe("asksComponentName", () => {
  test("a component is the one kind New file asks a second name for", () => {
    expect(asksComponentName("component")).toBe(true);
  });

  test.each(["types", "units", "constants", "sections", "rasters"])(
    "a %s file is created with its file's name alone",
    (kind) => {
      expect(asksComponentName(kind)).toBe(false);
    },
  );

  test.each(["", "comp", "Component"])(
    "text naming no kind the server creates, %j among it, asks for no component's name",
    (kind) => {
      // The kind field takes any text, and the server refuses what is not one of its own words
      // (`create_plan` compares with `in CREATABLE`, case and all): a field drawn for "Component"
      // would ask for a name the server then refuses the kind of.
      expect(asksComponentName(kind)).toBe(false);
    },
  );
});

describe("fileCreate", () => {
  test("nothing is asked while no kind is chosen", () => {
    expect(fileCreate("", "limits", "")).toBeNull();
  });

  test("nothing is asked while the file has no name", () => {
    expect(fileCreate("constants", "", "")).toBeNull();
  });

  test("a vocabulary file is asked for by its kind and name, and never with a component's name", () => {
    // The text typed into a Component name field left from an earlier choice is not sent: `toEqual`
    // alone would catch `component: "Left over"`, which the url would carry. `toStrictEqual` also
    // refuses a `component: undefined` key, which the url would carry too, as the text `undefined`
    // (`queryOf` sends every key of the request) - so it pins the object's own shape,
    // `FilesPlanRequest`'s, which is what the url is made of.
    expect(fileCreate("constants", "limits", "Left over")).toStrictEqual({
      action: "create",
      kind: "constants",
      name: "limits",
    });
  });

  test("a component is asked for with its own name beside its file's", () => {
    expect(fileCreate("component", "valve", "Valve")).toStrictEqual({
      action: "create",
      kind: "component",
      name: "valve",
      component: "Valve",
    });
  });

  test("a component is asked for while its own name is still empty, for the server to say why", () => {
    // `create_plan` answers "a new component needs a name, besides its file's" - the server's own
    // sentence - where the page withholding the request would say nothing at all.
    expect(fileCreate("component", "valve", "")).toStrictEqual({
      action: "create",
      kind: "component",
      name: "valve",
      component: "",
    });
  });

  test.each([
    ["a kind the server creates no file of", "project", "sub"],
    ["a name with a dot in it", "types", "a.b"],
    ["a name of spaces alone", "types", "  "],
  ])("%s is asked for as typed, for the server to judge", (_, kind, name) => {
    expect(fileCreate(kind, name, "")).toStrictEqual({ action: "create", kind, name });
  });
});

describe("fileAdd", () => {
  test("nothing is asked while the path is empty", () => {
    expect(fileAdd("")).toBeNull();
  });

  test.each(["b.ddd.json", "lib/l.ddd.json", "../outside.ddd.json", "  "])(
    "%j is asked for exactly as typed",
    (path) => {
      expect(fileAdd(path)).toStrictEqual({ action: "add", path });
    },
  );
});

describe("fileRemoval", () => {
  const literal = entry({ index: 0, entry: "./a.ddd.json", names: true, key: A, files: [A] });
  const pattern = entry({
    index: 1,
    entry: "sensors/*.ddd.json",
    names: false,
    key: "C:/work/demo/sensors/*.ddd.json",
    files: [SENSORS_X],
  });
  const rows = rowsOf(reply([literal, pattern]), [sourceFile()]);

  test("no row selected asks nothing", () => {
    expect(fileRemoval(rows, undefined, PROJECT)).toBeNull();
  });

  test("a key no row carries asks nothing, and opens no panel", () => {
    expect(fileRemoval(rows, "C:/work/demo/sub/nested.ddd.json", PROJECT)).toBeNull();
  });

  test("a literal entry's row is asked for by its key, and named as its entry is spelled", () => {
    expect(fileRemoval(rows, A, PROJECT)).toEqual({
      title: "./a.ddd.json",
      request: { action: "remove", path: A },
    });
  });

  test("a pattern's own row is asked for by the pattern's key, to take it out whole", () => {
    expect(fileRemoval(rows, "C:/work/demo/sensors/*.ddd.json", PROJECT)).toEqual({
      title: "sensors/*.ddd.json",
      request: { action: "remove", path: "C:/work/demo/sensors/*.ddd.json" },
    });
  });

  test("a pattern's matched file is asked for by its own path, for the server to refuse", () => {
    // `remove_plan` refuses a file no entry of its own names, naming the pattern: asked with the
    // child's own key, the refusal reaches the reader in the server's words.
    expect(fileRemoval(rows, SENSORS_X, PROJECT)).toEqual({
      title: "sensors/x.ddd.json",
      request: { action: "remove", path: SENSORS_X },
    });
  });

  test("of two rows of one key, the first names the panel", () => {
    // A literal entry and a pattern's child naming one file, the literal listed first here: its own
    // spelling - "./a.ddd.json", not the child's "a.ddd.json" - titles the panel, whichever of the
    // two rows was clicked.
    const catchAll = entry({
      index: 1,
      entry: "*.ddd.json",
      names: false,
      key: "C:/work/demo/*.ddd.json",
      files: [A],
    });
    const shared = rowsOf(reply([literal, catchAll]), [sourceFile()]);
    expect(selectedIndices(shared, A)).toEqual([0, 2]);
    expect(fileRemoval(shared, A, PROJECT)).toEqual({
      title: "./a.ddd.json",
      request: { action: "remove", path: A },
    });
  });

  test("a pattern listed before the literal puts its child first, and the child names the panel", () => {
    // `FileRemoval.title`'s own doc: either row of a shared key can come first. The request is the
    // one key either way, so which of the two names the panel changes nothing that is asked.
    const catchAll = entry({
      index: 0,
      entry: "*.ddd.json",
      names: false,
      key: "C:/work/demo/*.ddd.json",
      files: [A],
    });
    const later = entry({ index: 1, entry: "./a.ddd.json", names: true, key: A, files: [A] });
    const shared = rowsOf(reply([catchAll, later]), [sourceFile()]);
    expect(selectedIndices(shared, A)).toEqual([1, 2]);
    expect(fileRemoval(shared, A, PROJECT)).toEqual({
      title: "a.ddd.json",
      request: { action: "remove", path: A },
    });
  });
});

describe("removalAsked", () => {
  test("asks at once for a row the reader reached within the page", () => {
    expect(removalAsked(false, false)).toBe(true);
  });
  test("waits for the press on the row the page was loaded with", () => {
    expect(removalAsked(true, false)).toBe(false);
  });
  test("asks once the reader presses for it", () => {
    expect(removalAsked(true, true)).toBe(true);
  });
});

/** A plan as `GET /api/files-plan` answers one, changing the project description alone. */
function plan(fields: Partial<FilesPlanReply> = {}): FilesPlanReply {
  return {
    revision: 3,
    changes: [change(PROJECT)],
    unjudged: null,
    brings: [],
    kept_by: null,
    ...fields,
  };
}

function change(file: string): PlannedChange {
  return { file, fingerprint: "x", operations: [], hunks: [] };
}

describe("previewOf", () => {
  test("a New file's plan draws what it writes, and an Apply counting its files", () => {
    expect(previewOf(plan({ changes: [change(A), change(PROJECT)] }), PROJECT, null)).toEqual({
      brought: [],
      unjudged: null,
      kept: null,
      consequence: "Changes 2 files: a.ddd.json, demo.ddd.json",
      apply: "Apply to 2 files",
    });
  });

  test("an Add's errors are listed in the server's order, each file named as the table names a pattern's child", () => {
    const brings = [
      { file: SENSORS_X, check: "missing-producer", message: "'Torque' is read but not written" },
      { file: A, check: "multiple-producers", message: "'Speed' is written twice" },
    ];
    expect(previewOf(plan({ brings }), PROJECT, null)).toEqual({
      brought: [
        {
          key: "0",
          check: "missing-producer",
          message: "'Torque' is read but not written",
          file: "sensors/x.ddd.json",
        },
        {
          key: "1",
          check: "multiple-producers",
          message: "'Speed' is written twice",
          file: "a.ddd.json",
        },
      ],
      unjudged: null,
      kept: null,
      consequence: "Changes 1 file: demo.ddd.json",
      apply: "Apply to 1 file",
    });
  });

  test("two errors worded alike are two rows, each keyed apart", () => {
    // `new_errors` counts errors per place, and a `BroughtError` carries no place: two errors of
    // one check and one wording at two places of one file arrive as two equal entries.
    const same = {
      file: A,
      check: "missing-producer",
      message: "'Torque' is read but not written",
    };
    const brought = previewOf(plan({ brings: [same, same] }), PROJECT, null).brought;
    expect(brought.map((row) => row.key)).toEqual(["0", "1"]);
  });

  test("a change not judged carries the server's sentence exactly as it came", () => {
    const unjudged =
      "not every analysis of this project ran to its end, so what removing lib/b.ddd.json " +
      "leaves cannot be judged";
    expect(previewOf(plan({ unjudged }), PROJECT, A)).toEqual({
      brought: [],
      unjudged,
      kept: null,
      consequence: "Changes 1 file: demo.ddd.json",
      apply: "Remove from the includes",
    });
  });

  test("a removal a pattern keeps the file in through names the pattern, and the file it keeps", () => {
    expect(previewOf(plan({ kept_by: "*.ddd.json" }), PROJECT, A)).toEqual({
      brought: [],
      unjudged: null,
      kept: "a.ddd.json stays in the project all the same: the pattern '*.ddd.json' brings it in.",
      consequence: "Changes 1 file: demo.ddd.json",
      apply: "Remove from the includes",
    });
  });

  test("a file a pattern keeps in from a directory is named as the table names a pattern's child", () => {
    expect(previewOf(plan({ kept_by: "sensors/*.ddd.json" }), PROJECT, SENSORS_X).kept).toBe(
      "sensors/x.ddd.json stays in the project all the same: the pattern 'sensors/*.ddd.json' " +
        "brings it in.",
    );
  });

  test("a plan that changes nothing offers nothing to apply, a removal's no more than an add's", () => {
    // `consequence`'s own words for no change, and no button: `apply` is what decides that there
    // is one, so that the view draws Apply only where this says there is something to apply.
    const nothing = {
      brought: [],
      unjudged: null,
      kept: null,
      consequence: "Nothing to change",
      apply: null,
    };
    expect(previewOf(plan({ changes: [] }), PROJECT, null)).toEqual(nothing);
    expect(previewOf(plan({ changes: [] }), PROJECT, A)).toEqual(nothing);
  });

  test("a pattern named in a plan that is no removal's is not put into words", () => {
    // `kept_by` is always `None` for an add and a create (`FilesPlanReply.kept_by`'s own doc), and
    // the sentence needs the file a removal was asked with, which neither has.
    expect(previewOf(plan({ kept_by: "*.ddd.json" }), PROJECT, null).kept).toBeNull();
  });
});
