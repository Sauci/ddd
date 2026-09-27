import { useState } from "react";
import type { SharedReply } from "../api/types";
import {
  NO_SHARED,
  PROJECT_SHARED,
  SHARED_MISSING_FILE,
  SHARED_WITH_FINDING,
} from "../stories/fixtures";
import { SharedTableView } from "./SharedTableView";

export default { title: "Components / SharedTableView" };

/** Holds its own selection, as the tab would: `on` seeds it, a click in the table moves it. */
function Tab({
  reply = PROJECT_SHARED,
  on,
  unreadable = [],
}: {
  reply?: SharedReply;
  on?: string;
  unreadable?: readonly string[];
}) {
  const [selected, setSelected] = useState<string | undefined>(on);
  return (
    <SharedTableView
      reply={reply}
      selected={selected}
      onSelect={setSelected}
      unreadable={unreadable}
      // Task 8 gives this somewhere to open; no story here presses it, so what it does once
      // pressed is not this task's to show.
      onDeclare={() => undefined}
    />
  );
}

/** TREND_SAMPLES from constants.ddd.json beside PRESSURE_CELLS declared inline in pump.ddd.json,
 * indistinguishable in the row itself - the whole reason the tab lists both homes together. */
export const BothHomes = () => <Tab />;

/** TREND_SAMPLES carrying a finding: the dimension-value case, filed at the shape naming it
 * rather than at its own entry, and counted here all the same. */
export const ADimensionValueFinding = () => <Tab reply={SHARED_WITH_FINDING} />;

/** A project that declares none: the sentence alone, and the button that declares the first one. */
export const NothingDeclared = () => <Tab reply={NO_SHARED} />;

/** constants.ddd.json did not load: the warning above a table missing TREND_SAMPLES, PRESSURE_CELLS
 * still listed since it is declared inline rather than in the file that failed. */
export const AFileDidNotLoad = () => (
  <Tab reply={SHARED_MISSING_FILE} unreadable={["constants.ddd.json"]} />
);
