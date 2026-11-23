import type { RefusedBuild, SourceFile } from "../api/types";
import { type LoadBanner, loadBanner } from "../lib/unloaded";
import { LoadBannerView } from "./LoadBannerView";

export default { title: "Components / LoadBannerView" };

const DEMO = "C:/work/demo/demo.ddd.json";

/** A file of the demo as the state lists it: one that did not load names nothing and counts the
 * one error saying why, as a file saved half-written does. */
function file(path: string, name: string | null, loaded = true): SourceFile {
  return {
    path: `C:/work/demo/${path}`,
    kind: loaded ? "component" : "unknown",
    name: loaded ? name : null,
    loaded,
    fingerprint: "0".repeat(64),
    findings: { error: loaded ? 0 : 1, warning: 0, info: 0 },
  };
}

/** The demo with controller.ddd.json saved half-written: the one file that did not load. */
const CONTROLLER_CUT: readonly SourceFile[] = [
  { ...file("demo.ddd.json", "DemoDevice"), kind: "project" },
  file("components/controller.ddd.json", "Controller", false),
  file("components/sensor_hub.ddd.json", "SensorHub"),
  file("components/user_interface.ddd.json", "UserInterface"),
];

/** The demo with its own description saved half-written: nothing it includes is read, so the state
 * lists it alone. */
const DESCRIPTION_CUT: readonly SourceFile[] = [file("demo.ddd.json", "DemoDevice", false)];

/** Six files that did not load, two of them of one name in two folders. */
const SIX_CUT: readonly SourceFile[] = [
  { ...file("demo.ddd.json", "DemoDevice"), kind: "project" },
  file("pumps/front/pump.ddd.json", "Pump", false),
  file("pumps/rear/pump.ddd.json", "Pump", false),
  file("components/valve.ddd.json", "Valve", false),
  file("components/sensor_hub.ddd.json", "SensorHub", false),
  file("components/controller.ddd.json", "Controller", false),
  file("components/user_interface.ddd.json", "UserInterface", false),
];

/** A record a newer DDD's build wrote, beside the project. */
const NEWER: RefusedBuild = {
  record: "C:/work/demo/build/ddd/fw/ddd-build.json",
  reason: "written in format 3 by a newer DDD, and this one understands up to format 2",
};

/** The banner `loadBanner` makes, drawn: nothing where it says nothing. */
function View({ banner }: { banner: LoadBanner | null }) {
  return banner === null ? null : <LoadBannerView banner={banner} onFollow={() => undefined} />;
}

/** Whether ddd gui has stopped answering: running, in every story but the last. */
const RUNNING = false;

/** controller.ddd.json saved half-written: named, and leading to the finding saying why. */
export const AFileThatDidNotLoad = () => (
  <View banner={loadBanner(DEMO, { files: CONTROLLER_CUT }, null, [], RUNNING)} />
);

/** The project's own description saved half-written: named, and no file it includes read. */
export const ADescriptionThatDidNotLoad = () => (
  <View banner={loadBanner(DEMO, { files: DESCRIPTION_CUT }, null, [], RUNNING)} />
);

/** Six files that did not load: three named, two of one name told apart by their folders, and the
 * other three counted, leading to the Files tab. */
export const ManyFilesThatDidNotLoad = () => (
  <View banner={loadBanner(DEMO, { files: SIX_CUT }, null, [], RUNNING)} />
);

/** The project's first analysis failed: no revision stands, and ddd gui tries again about every
 * second. */
export const AFirstAnalysisThatFailed = () => (
  <View banner={loadBanner(DEMO, null, "embedded null byte", [], RUNNING)} />
);

/** A later analysis failed while a file did not load and a build record cannot be used: one banner,
 * a line each, an error for the failure. */
export const EverythingAtOnce = () => (
  <View
    banner={loadBanner(DEMO, { files: CONTROLLER_CUT }, "embedded null byte", [NEWER], RUNNING)}
  />
);

/** The same once ddd gui has stopped: no line promises an analysis, each saying what the last state
 * the page read holds. */
export const EverythingOnceStopped = () => (
  <View banner={loadBanner(DEMO, { files: CONTROLLER_CUT }, "embedded null byte", [NEWER], true)} />
);
