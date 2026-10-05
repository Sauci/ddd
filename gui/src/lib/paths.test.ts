import { describe, expect, test } from "vitest";
import { shownPath } from "./paths";

// Every expected path below is what Python's own `relpath` answers for the same two paths
// (`posixpath.relpath`, and `ntpath.relpath` for the Windows ones), checked when these were
// written; where `ntpath.relpath` raises instead - "path is on mount 'D:', start on mount 'C:'" -
// there is no relative path, and the File column keeps the absolute one.
describe("a file's path as the Table tab's File column shows it", () => {
  const project = "/home/reader/demo/demo.ddd.json";

  test("a file beside the project's description, by its name alone", () => {
    expect(shownPath(project, "/home/reader/demo/limits.ddd.json")).toBe("limits.ddd.json");
  });

  test("a file in a subdirectory, from the project's directory down", () => {
    expect(shownPath(project, "/home/reader/demo/components/controller.ddd.json")).toBe(
      "components/controller.ddd.json",
    );
    expect(shownPath(project, "/home/reader/demo/subsystems/logging/event_logger.ddd.json")).toBe(
      "subsystems/logging/event_logger.ddd.json",
    );
  });

  test("a file outside the project's directory, by a ../ for every level up", () => {
    expect(shownPath(project, "/home/reader/shared/pump.ddd.json")).toBe("../shared/pump.ddd.json");
    expect(shownPath(project, "/opt/parts/pump.ddd.json")).toBe("../../../opt/parts/pump.ddd.json");
  });

  test("a directory whose name only begins like the project's is another directory", () => {
    expect(shownPath(project, "/home/reader/demo2/a.ddd.json")).toBe("../demo2/a.ddd.json");
  });

  test("a project at the root of the file system", () => {
    expect(shownPath("/demo.ddd.json", "/components/a.ddd.json")).toBe("components/a.ddd.json");
  });

  test("a Windows path, posix-separated as the server sends it, on the project's own drive", () => {
    const windows = "C:/work/demo/demo.ddd.json";
    expect(shownPath(windows, "C:/work/demo/components/a.ddd.json")).toBe("components/a.ddd.json");
    expect(shownPath(windows, "C:/work/lib/b.ddd.json")).toBe("../lib/b.ddd.json");
  });

  test("a file on another drive has no relative path, and keeps its absolute one", () => {
    expect(shownPath("C:/work/demo/demo.ddd.json", "D:/lib/b.ddd.json")).toBe("D:/lib/b.ddd.json");
  });

  test("a share is a root of its own: relative within it, absolute beyond it", () => {
    const shared = "//server/share/demo/demo.ddd.json";
    expect(shownPath(shared, "//server/share/lib/x.ddd.json")).toBe("../lib/x.ddd.json");
    expect(shownPath(shared, "//server/other/x.ddd.json")).toBe("//server/other/x.ddd.json");
    expect(shownPath(shared, "C:/work/x.ddd.json")).toBe("C:/work/x.ddd.json");
    expect(shownPath("C:/work/demo/demo.ddd.json", "//server/share/x.ddd.json")).toBe(
      "//server/share/x.ddd.json",
    );
  });
});
