import { useState } from "react";
import type { SharedReply } from "../api/types";
import type { SharedSelection } from "../lib/shared";
import {
  NO_SHARED,
  PROJECT_SHARED,
  SHARED_ALL_VOCABULARIES,
  SHARED_BOTH_KINDS,
  SHARED_MISSING_FILE,
  SHARED_ONE_OF_EACH,
  SHARED_ONE_SPELLING,
  SHARED_RASTER_CYCLES,
  SHARED_RASTER_FINDING,
  SHARED_SECTION_FINDING,
  SHARED_WITH_FINDING,
} from "../stories/fixtures";
import { SharedTableView } from "./SharedTableView";

export default { title: "Components / SharedTableView" };

/** Holds its own selection, as the tab would: `on` seeds it, a click in the table moves it. A
 * selection is a vocabulary and a name, not a name, which is what the last story below is for. */
function Tab({
  reply = PROJECT_SHARED,
  on,
  unreadable = [],
  untold = [],
}: {
  reply?: SharedReply;
  on?: SharedSelection;
  unreadable?: readonly string[];
  untold?: readonly string[];
}) {
  const [selected, setSelected] = useState<SharedSelection | undefined>(on);
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

/** sections.ddd.json did not load: TREND_SAMPLES and PRESSURE_CELLS still list, their own file
 * untouched, but neither section can - unlike a constant, a section has no second home to survive
 * in. Fix round 1's own reason to exist: every other "did not load" story here fails a constants
 * file, so a banner sentence hardcoding the word "constants" read correctly in all of them and
 * only this one - a failed *sections* file - could show it naming the wrong vocabulary. */
export const ASectionsFileDidNotLoad = () => (
  <Tab reply={PROJECT_SHARED} unreadable={["sections.ddd.json"]} />
);

/** .fast_ram and .calib beside TREND_SAMPLES and PRESSURE_CELLS: both vocabularies the tab holds,
 * in the one table - the story this tab exists for. A section's States cell ("read-write, align
 * 4") is nothing a constant's own ("16") could be mistaken for, so the two kinds read apart even
 * before a reader looks at the Vocabulary column beside them. */
export const BothVocabularies = () => <Tab reply={SHARED_BOTH_KINDS} />;

/** .fast_ram and .calib beside TREND_SAMPLES and PRESSURE_CELLS, and now 1ms, 10ms and 100ms too:
 * every vocabulary the tab holds, in the one table - the story this part exists for. A raster's
 * States cell ("event 1, 10ms") is nothing either of the other two ("16", "read-write, align 4")
 * could be mistaken for, so a third kind reads apart from the first two exactly as BothVocabularies'
 * own two already do. */
export const AllThreeVocabularies = () => <Tab reply={SHARED_ALL_VOCABULARIES} />;

/** .calib carrying a finding, counted on its own row exactly as TREND_SAMPLES's is in
 * ADimensionValueFinding - the Findings column is not a constant's alone. */
export const ASectionFinding = () => <Tab reply={SHARED_SECTION_FINDING} />;

/** 10ms carrying a finding, counted on its own row exactly as TREND_SAMPLES's is in
 * ADimensionValueFinding and .calib's is in ASectionFinding - the Findings column is not a
 * constant's or a section's alone. */
export const ARasterFinding = () => <Tab reply={SHARED_RASTER_FINDING} />;

/** 10ms beside crank: the only place a reader sees a raster's two States cell shapes together -
 * "event 1, 10ms" where an entry states a cycle, "event 2" alone where it does not. */
export const TwoRastersOneWithNoCycle = () => <Tab reply={SHARED_RASTER_CYCLES} />;

/** TREND_SAMPLES alone beside .fast_ram alone: the smallest table that still holds both
 * vocabularies, nothing else declared of either kind - not even TREND_SAMPLES's own other home,
 * the inline constant PROJECT_SHARED pairs it with. */
export const OneOfEachKind = () => <Tab reply={SHARED_ONE_OF_EACH} />;

/** A constant and a section both called FOO, the section's row selected. A section's name is a
 * linker string, so one spelling may belong to a row of either vocabulary, and a table keyed by
 * name alone gave the two rows one id: the mark would sit on the constant's row above, whichever
 * a reader clicked. Which row is highlighted here is the whole point of the photograph. */
export const OneSpellingTwoVocabularies = () => (
  <Tab reply={SHARED_ONE_SPELLING} on={{ kind: "section", name: "FOO" }} />
);
