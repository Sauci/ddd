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

/** controller.ddd.json saved half-written: named, and leading to the finding saying why. */
export const AFileThatDidNotLoad = () => (
  <View banner={loadBanner(DEMO, { files: CONTROLLER_CUT }, null, [])} />
);

/** Six files that did not load: three named, two of one name told apart by their folders, and the
 * other three counted, leading to the Files tab. */
export const ManyFilesThatDidNotLoad = () => (
  <View banner={loadBanner(DEMO, { files: SIX_CUT }, null, [])} />
);

/** The project's first analysis failed: no revision stands, and the next change of a file it reads
 * asks again. */
export const AFirstAnalysisThatFailed = () => (
  <View banner={loadBanner(DEMO, null, "embedded null byte", [])} />
);

/** A later analysis failed while a file did not load and a build record cannot be used: one banner,
 * a line each, an error for the failure. */
export const EverythingAtOnce = () => (
  <View banner={loadBanner(DEMO, { files: CONTROLLER_CUT }, "embedded null byte", [NEWER])} />
);
