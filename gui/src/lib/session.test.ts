import { expect, test } from "vitest";
import { projectName, sessionAskedAgain } from "./session";

/** The session's open project, as `GET /api/session` names it. */
const DEMO = { path: "/work/demo/demo.ddd.json", name: "DemoDevice" };
/** The same project, its description giving no name. */
const UNNAMED = { path: DEMO.path, name: null };
/** Another project's description, as the state names the project it is of. */
const SECOND = "/work/second/second.ddd.json";

test("the page names the project by the session's name while the session names the state's project", () => {
  expect(projectName(DEMO, DEMO.path)).toBe("DemoDevice");
});

test("the page names the project by the session's name before it has followed any state", () => {
  expect(projectName(DEMO, null)).toBe("DemoDevice");
});

test("a project whose description gives no name is named by the path the session gives it", () => {
  expect(projectName(UNNAMED, DEMO.path)).toBe(DEMO.path);
  expect(projectName(UNNAMED, null)).toBe(DEMO.path);
});

test("a state of another project than the session names is named by its description's file", () => {
  // Another page of the same server opened it, and the session asked again has not answered: the
  // state carries the project's path and no name.
  expect(projectName(DEMO, SECOND)).toBe("second.ddd.json");
  expect(projectName(UNNAMED, SECOND)).toBe("second.ddd.json");
});

test("the session is asked again while the state is of another project than it names", () => {
  expect(sessionAskedAgain(DEMO, SECOND)).toBe(true);
  expect(sessionAskedAgain(UNNAMED, SECOND)).toBe(true);
});

test("the session is not asked again while it names the state's project, nor before any state", () => {
  expect(sessionAskedAgain(DEMO, DEMO.path)).toBe(false);
  expect(sessionAskedAgain(DEMO, null)).toBe(false);
});

test("a session with no project open is not asked again, whatever state was followed last", () => {
  // The page follows no state while no project is open: the last one it followed is older than
  // the session's answer.
  expect(sessionAskedAgain(null, SECOND)).toBe(false);
  expect(sessionAskedAgain(null, null)).toBe(false);
});
