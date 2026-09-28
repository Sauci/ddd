import { useState } from "react";
import type { SharedReply } from "../api/types";
import {
  NO_SHARED,
  PROJECT_SHARED,
  SHARED_BOTH_KINDS,
  SHARED_MISSING_FILE,
  SHARED_ONE_OF_EACH,
  SHARED_SECTION_FINDING,
  SHARED_WITH_FINDING,
} from "../stories/fixtures";
import { SharedTableView } from "./SharedTableView";

export default { title: "Components / SharedTableView" };

/** Holds its own selection, as the tab would: `on` seeds it, a click in the table moves it. */
function Tab({
  reply = PROJECT_SHARED,
  on,
  unreadable = [],
  untold = [],
}: {
  reply?: SharedReply;
  on?: string;
  unreadable?: readonly string[];
  untold?: readonly string[];
}) {
  const [selected, setSelected] = useState<string | undefined>(on);
  return (
    <SharedTableView
      reply={reply}
      selected={selected}
      onSelect={setSelected}
      unreadable={unreadable}
      untold={untold}
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

/** A file nobody could parse - an editor saving it half-written. The server cannot say what kind
 * it is, so this tab cannot claim its entries were constants; it says only that whatever is
 * declared there is missing. Both this tab and the Types tab show the same sentence, because
 * neither can tell whose file it was. */
export const AFileOfNoTellableKind = () => (
  <Tab reply={SHARED_MISSING_FILE} untold={["sizes.ddd.json"]} />
);

/** .fast_ram and .calib beside TREND_SAMPLES and PRESSURE_CELLS: both vocabularies the tab holds,
 * in the one table - the story this tab exists for. A section's States cell ("read-write, align
 * 4") is nothing a constant's own ("16") could be mistaken for, so the two kinds read apart even
 * before a reader looks at the Vocabulary column beside them. */
export const BothVocabularies = () => <Tab reply={SHARED_BOTH_KINDS} />;

/** .calib carrying a finding, counted on its own row exactly as TREND_SAMPLES's is in
 * ADimensionValueFinding - the Findings column is not a constant's alone. */
export const ASectionFinding = () => <Tab reply={SHARED_SECTION_FINDING} />;

/** TREND_SAMPLES alone beside .fast_ram alone: the smallest table that still holds both
 * vocabularies, nothing else declared of either kind - not even TREND_SAMPLES's own other home,
 * the inline constant PROJECT_SHARED pairs it with. */
export const OneOfEachKind = () => <Tab reply={SHARED_ONE_OF_EACH} />;
