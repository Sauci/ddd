import { describe, expect, test } from "vitest";
import type { RefusedBuild, SourceFile } from "../api/types";
import { loadBanner, namedFiles, type Part, RECORD_IGNORED, unloadedNames } from "./unloaded";

const PROJECT = "C:/work/demo/demo.ddd.json";

/** A file of the state, loaded or not: one that did not load names nothing and counts its one
 * error, as a file saved half-written does. */
const file = (path: string, loaded = true, kind = "component"): SourceFile => ({
  path,
  kind,
  name: loaded ? "Controller" : null,
  loaded,
  fingerprint: "0".repeat(64),
  findings: { error: loaded ? 0 : 1, warning: 0, info: 0 },
});

const CONTROLLER = "C:/work/demo/components/controller.ddd.json";
const SENSOR_HUB = "C:/work/demo/components/sensor_hub.ddd.json";

/** The state of a revision holding `files`. */
const analysed = (...files: SourceFile[]) => ({ revision: 4, files });

/** Whether ddd gui has stopped answering, as `useProjectState` says: running, in every test but
 * those of a server stopped. */
const RUNNING = false;
const STOPPED = true;

/** A line of the banner as a reader reads it: its words, a link's among them. */
const wordsOf = (line: readonly Part[]) =>
  line.map((part) => (typeof part === "string" ? part : part.text)).join("");

describe("the files that did not load, as a sentence names them", () => {
  test("each by its own name, in the state's order, and none that loaded", () => {
    expect(
      unloadedNames([
        file(PROJECT, true, "project"),
        file(CONTROLLER, false, "unknown"),
        file(SENSOR_HUB),
        file("C:/work/demo/units.ddd.json", false, "units"),
      ]),
    ).toEqual(["controller.ddd.json", "units.ddd.json"]);
    expect(unloadedNames([file(PROJECT, true, "project"), file(SENSOR_HUB)])).toEqual([]);
  });

  test("two of one name by as much of their paths as tells them apart, as a refusal does", () => {
    // Told apart among the files that did not load alone (`ddd.gui.api._unread`): the one that
    // loaded beside them, of that name too, is no name the reader is sent to repair.
    expect(
      unloadedNames([
        file("C:/work/demo/a/pump.ddd.json", false),
        file("C:/work/demo/b/pump.ddd.json", false),
        file("C:/work/demo/c/valve.ddd.json"),
        file("C:/work/demo/d/valve.ddd.json", false),
      ]),
    ).toEqual(["a/pump.ddd.json", "b/pump.ddd.json", "valve.ddd.json"]);
  });

  test("are listed as every sentence lists names, up to four of them", () => {
    expect(namedFiles(["a.ddd.json"])).toBe("a.ddd.json");
    expect(namedFiles(["a.ddd.json", "b.ddd.json"])).toBe("a.ddd.json and b.ddd.json");
    expect(namedFiles(["a.ddd.json", "b.ddd.json", "c.ddd.json"])).toBe(
      "a.ddd.json, b.ddd.json and c.ddd.json",
    );
    expect(namedFiles(["a.ddd.json", "b.ddd.json", "c.ddd.json", "d.ddd.json"])).toBe(
      "a.ddd.json, b.ddd.json, c.ddd.json and d.ddd.json",
    );
  });

  test("and past four, three of them and how many more, as a plan's files are counted", () => {
    const many = Array.from({ length: 3333 }, (_, at) => `c${at}.ddd.json`);
    expect(namedFiles(many.slice(0, 5))).toBe("c0.ddd.json, c1.ddd.json, c2.ddd.json and 2 more");
    expect(namedFiles(many)).toBe("c0.ddd.json, c1.ddd.json, c2.ddd.json and 3,330 more");
  });
});

describe("the banner under the masthead", () => {
  test("is not drawn while every file loaded, no analysis failed and no record is refused", () => {
    expect(
      loadBanner(PROJECT, analysed(file(PROJECT, true, "project")), null, [], RUNNING),
    ).toBeNull();
    // Nothing is known before the first state, nor of a first analysis still running.
    expect(loadBanner(null, null, null, [], RUNNING)).toBeNull();
    expect(loadBanner(PROJECT, null, null, [], RUNNING)).toBeNull();
    // Before the first state there is no project to say anything of, whatever else is handed on.
    expect(
      loadBanner(
        null,
        analysed(file(CONTROLLER, false)),
        "boom",
        [{ record: "C:/work/demo/build/ddd-build.json", reason: "unknown check 'nonesuch'" }],
        STOPPED,
      ),
    ).toBeNull();
  });

  test("names a file that did not load, leading to its finding, and says the project's checks wait for it", () => {
    // Asked of the Findings tab by its file's own name, which a finding of that file holds, and
    // the words of one filed at the entry naming a file that is not there hold too. A file that
    // does not load stops every check of the project, as `ddd check` stops at the read (`_run`,
    // lsp/diagnostics.py): the counts beside the banner are of no check, and the pages are drawn
    // from what the files that loaded declare.
    expect(loadBanner(PROJECT, analysed(file(CONTROLLER, false)), null, [], RUNNING)).toEqual({
      tone: "warning",
      lines: [
        [
          {
            text: "controller.ddd.json",
            to: { page: "project", view: "findings", text: "controller.ddd.json" },
          },
          " did not load, so the project's checks wait until it does, and the pages show what " +
            "the files that loaded declare.",
        ],
      ],
    });
  });

  test("says of the project's own description that did not load that no file it includes is read", () => {
    // Nothing past a description that does not load is read: the state lists it alone, and no
    // page has a file that loaded to draw.
    expect(
      loadBanner(PROJECT, analysed(file(PROJECT, false, "unknown")), null, [], RUNNING),
    ).toEqual({
      tone: "warning",
      lines: [
        [
          {
            text: "demo.ddd.json",
            to: { page: "project", view: "findings", text: "demo.ddd.json" },
          },
          " did not load, so the project's checks wait until it does, and no file it includes " +
            "is read.",
        ],
      ],
    });
  });

  test("names each of several, two of one name told apart, each leading to its own", () => {
    const banner = loadBanner(
      PROJECT,
      analysed(
        file("C:/work/demo/a/pump.ddd.json", false),
        file(SENSOR_HUB),
        file("C:/work/demo/b/pump.ddd.json", false),
      ),
      null,
      [],
      RUNNING,
    );
    expect(banner?.lines).toEqual([
      [
        {
          text: "a/pump.ddd.json",
          to: { page: "project", view: "findings", text: "pump.ddd.json" },
        },
        " and ",
        {
          text: "b/pump.ddd.json",
          to: { page: "project", view: "findings", text: "pump.ddd.json" },
        },
        " did not load, so the project's checks wait until they do, and the pages show what the " +
          "files that loaded declare.",
      ],
    ]);
  });

  test("names three of five and leads the rest to the Files tab, where each row says so", () => {
    const five = ["a", "b", "c", "d", "e"].map((name) =>
      file(`C:/work/demo/components/${name}.ddd.json`, false),
    );
    const finding = (name: string) => ({
      text: name,
      to: { page: "project", view: "findings", text: name },
    });
    expect(loadBanner(PROJECT, analysed(...five), null, [], RUNNING)?.lines).toEqual([
      [
        finding("a.ddd.json"),
        ", ",
        finding("b.ddd.json"),
        ", ",
        finding("c.ddd.json"),
        " and ",
        { text: "2 more", to: { page: "project", view: "files" } },
        " did not load, so the project's checks wait until they do, and the pages show what the " +
          "files that loaded declare.",
      ],
    ]);
    // Four are each named: a count standing for one file is no shorter than its name.
    const four = loadBanner(PROJECT, analysed(...five.slice(0, 4)), null, [], RUNNING);
    expect(four?.lines[0]?.filter((part) => typeof part !== "string")).toHaveLength(4);
  });

  test("counts the rest as every count of the page is written, past a thousand", () => {
    // A description format moved on: every component of a large project fails at once.
    const many = Array.from({ length: 3334 }, (_, at) =>
      file(`C:/work/large/components/c${at}.ddd.json`, false),
    );
    expect(loadBanner(PROJECT, analysed(...many), null, [], RUNNING)?.lines[0]?.[6]).toEqual({
      text: "3,331 more",
      to: { page: "project", view: "files" },
    });
  });

  test("says a first analysis failed, and that ddd gui tries again about every second, as an error", () => {
    // Before any revision: no file is known, and the reason is the whole of what there is to say.
    // A failure leaves every file it read stamped unknown (`Session._finished`, gui/session.py),
    // so each poll, a second apart, asks for another, a file changed on disk or none.
    expect(loadBanner(PROJECT, null, "boom", [], RUNNING)).toEqual({
      tone: "error",
      lines: [
        [
          "Analysing the project failed: boom. ddd gui tries again about every second, until an " +
            "analysis succeeds.",
        ],
      ],
    });
  });

  test("says a later analysis failed over the last one that finished, which every page shows", () => {
    expect(
      loadBanner(PROJECT, analysed(file(PROJECT, true, "project")), "boom", [], RUNNING),
    ).toEqual({
      tone: "error",
      lines: [
        [
          "Analysing the project failed: boom. The pages show the last analysis that finished, " +
            "and ddd gui tries again about every second, until one succeeds.",
        ],
      ],
    });
  });

  test("promises no analysis once ddd gui has stopped, and says what the last state holds", () => {
    // Stopped, ddd gui tries nothing again, and a file that loads is checked by nothing: under the
    // masthead's "ddd gui has stopped", the banner says only what the last state read holds.
    expect(loadBanner(PROJECT, null, "boom", [], STOPPED)).toEqual({
      tone: "error",
      lines: [["Analysing the project failed: boom."]],
    });
    const cut = analysed(
      file(PROJECT, true, "project"),
      file(CONTROLLER, false),
      file("C:/work/demo/units.ddd.json", false, "units"),
    );
    expect(loadBanner(PROJECT, cut, "boom", [], STOPPED)?.lines.map(wordsOf)).toEqual([
      "Analysing the project failed: boom. The pages show the last analysis that finished.",
      "controller.ddd.json and units.ddd.json did not load, so the project's checks did not run, " +
        "and the pages show what the files that loaded declare.",
    ]);
    expect(
      loadBanner(PROJECT, analysed(file(PROJECT, false, "unknown")), null, [], STOPPED)?.lines.map(
        wordsOf,
      ),
    ).toEqual([
      "demo.ddd.json did not load, so the project's checks did not run, and no file it includes " +
        "is read.",
    ]);
  });

  test("names each build record this DDD cannot use, with its reason, as the terminal does", () => {
    const refused: RefusedBuild[] = [
      {
        record: "C:/work/demo/build/ddd/fw/ddd-build.json",
        reason: "written in format 99 by a newer DDD, and this one understands up to format 2",
      },
      { record: "D:/builds/tests/ddd-build.json", reason: "unknown check 'nonesuch'" },
    ];
    expect(RECORD_IGNORED).toBe("this record is ignored, so its severities apply to no analysis");
    // By its path from the project's directory, as the Table tab's File column names a file; one
    // on another drive by its own.
    expect(
      loadBanner(PROJECT, analysed(file(PROJECT, true, "project")), null, refused, RUNNING),
    ).toEqual({
      tone: "warning",
      lines: [
        [
          "build/ddd/fw/ddd-build.json: written in format 99 by a newer DDD, and this one " +
            "understands up to format 2; this record is ignored, so its severities apply to no " +
            "analysis.",
        ],
        [
          "D:/builds/tests/ddd-build.json: unknown check 'nonesuch'; this record is ignored, so " +
            "its severities apply to no analysis.",
        ],
      ],
    });
  });

  test("says all three at once: the failure first, then the files, then the records", () => {
    const banner = loadBanner(
      PROJECT,
      analysed(file(CONTROLLER, false)),
      "boom",
      [{ record: "C:/work/demo/build/ddd-build.json", reason: "unknown check 'nonesuch'" }],
      RUNNING,
    );
    expect(banner?.tone).toBe("error");
    expect(banner?.lines.map(wordsOf)).toEqual([
      "Analysing the project failed: boom. The pages show the last analysis that finished, and " +
        "ddd gui tries again about every second, until one succeeds.",
      "controller.ddd.json did not load, so the project's checks wait until it does, and the " +
        "pages show what the files that loaded declare.",
      "build/ddd-build.json: unknown check 'nonesuch'; this record is ignored, so its severities " +
        "apply to no analysis.",
    ]);
  });
});
