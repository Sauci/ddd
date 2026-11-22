import { expect, test } from "vitest";
import { projectName, sessionAskedFor } from "./session";

/** The session's open project, as `GET /api/session` names it. */
const DEMO = { path: "/work/demo/demo.ddd.json", name: "DemoDevice" };
/** The same project, its description giving no name. */
const UNNAMED = { path: DEMO.path, name: null };
/** Another project's description, as the state names the project it is of. */
const SECOND = "/work/second/second.ddd.json";
/** A third project's description, opened after `SECOND`. */
const THIRD = "/work/third/third.ddd.json";

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

test("the session is asked again, for the state's project, while the state is of another than it names", () => {
  expect(sessionAskedFor(DEMO, SECOND)).toBe(SECOND);
  expect(sessionAskedFor(UNNAMED, SECOND)).toBe(SECOND);
});

test("the session is not asked again while it names the state's project, nor before any state", () => {
  expect(sessionAskedFor(DEMO, DEMO.path)).toBeNull();
  expect(sessionAskedFor(DEMO, null)).toBeNull();
});

test("a session with no project open is not asked again, whatever state was followed last", () => {
  // The page follows no state while no project is open: the last one it followed is older than
  // the session's answer.
  expect(sessionAskedFor(null, SECOND)).toBeNull();
  expect(sessionAskedFor(null, null)).toBeNull();
});

test("a state of yet another project, coming while the session is asked, is asked for again", () => {
  // The page asks once for each answer here that changes: the ask made for SECOND may still
  // answer SECOND once the state is THIRD's, and THIRD then needs an ask of its own.
  expect(sessionAskedFor(DEMO, THIRD)).not.toBe(sessionAskedFor(DEMO, SECOND));
});

test("an answer naming another project than the state's asks nothing more for that state", () => {
  // Asked for THIRD while the session named DEMO, the page has asked for THIRD whatever the answer
  // names: one that disagrees in its turn, a project opened later, asks nothing more until the
  // state moves on.
  expect(sessionAskedFor({ path: SECOND, name: "SecondDevice" }, THIRD)).toBe(
    sessionAskedFor(DEMO, THIRD),
  );
});
