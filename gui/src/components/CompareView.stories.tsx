import { useState } from "react";
import type { CompareReply } from "../api/types";
import { compareRows } from "../lib/compare";
import {
  BASELINE_ROOT,
  CAN_REPLACE,
  CANNOT_REPLACE,
  PROJECT_FINDINGS,
  REFUSED_OUTSIDE_ROOT,
} from "../stories/fixtures";
import { CompareView } from "./CompareView";

export default { title: "Components / CompareView" };

interface Props {
  baseline?: string;
  reply?: CompareReply | null;
  refusal?: string | null;
  busy?: boolean;
  /** Opens with the baseline's own finding already selected, so its row's possessive File
   * column and its own reason line are both in the picture beside `CompareTableView` and
   * `FindingPanelView`'s pairing - found among the reply's own rows the same structural way
   * `compareRows` itself tells the two sides apart, never a key spelled out by hand. */
  openBaseline?: boolean;
}

/** The Compare tab over one scenario's fixtures, with its own baseline field and selection -
 * `CompareView`'s own props, exactly as the tab itself supplies them (`ComparePage`). `state` is
 * the Findings tab's own fixture, which is what a row naming a place in the open project is
 * routed against; `onOpen` is where the app would navigate, and a story navigates nowhere. */
function View({
  baseline: typedAtFirst = "",
  reply = null,
  refusal = null,
  busy = false,
  openBaseline = false,
}: Props) {
  const [baseline, setBaseline] = useState(typedAtFirst);
  const rows = reply === null ? [] : compareRows(reply);
  const [selected, setSelected] = useState<string | undefined>(() =>
    openBaseline ? rows.find((row) => row.fromBaseline)?.key : undefined,
  );
  return (
    <CompareView
      state={PROJECT_FINDINGS}
      onOpen={() => undefined}
      baseline={baseline}
      onBaseline={setBaseline}
      onAsk={() => undefined}
      reply={reply}
      refusal={refusal}
      busy={busy}
      selected={selected}
      onSelect={setSelected}
    />
  );
}

/** Nothing typed yet: the field and its sentence, and nothing below them - what a reader sees on
 * opening the tab (spec §6). */
export const Empty = () => <View />;

/** A delivery examples/demo can stand in for cleanly: the verdict leads, no findings follow it,
 * and "Nothing was renamed." stands where the renames table would be. */
export const CanReplaceTheBaseline = () => (
  <View baseline={`${BASELINE_ROOT}/demo.ddd.json`} reply={CAN_REPLACE} />
);

/** A delivery it cannot: three of the thirteen comparison checks - `changed-interface`,
 * `removed-object`, `renamed-object` - and one of the baseline's own findings besides, filed on
 * a file that shares its display name with the candidate's own sensor_hub.ddd.json. Opens with
 * that row selected, so the File column's `the baseline's sensor_hub.ddd.json` and the panel's
 * own reason line ("it is the baseline's own finding...") are both on screen at once, beside
 * `FindingPanelView`'s own meta line - `baseName(finding.file)` alone, unmarked, the same bare
 * `sensor_hub.ddd.json` a comparison row's file would read. */
export const CannotReplaceTheBaseline = () => (
  <View baseline={`${BASELINE_ROOT}/demo.ddd.json`} reply={CANNOT_REPLACE} openBaseline />
);

/** A baseline named outside the session root: the reason said plainly, and no verdict beneath
 * it - one of the spec's own four refusals (§6). */
export const BaselineRefused = () => (
  <View baseline="C:/archives/demo.ddd.json" refusal={REFUSED_OUTSIDE_ROOT} />
);
