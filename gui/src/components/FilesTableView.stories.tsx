import { useState } from "react";
import type { FilesReply, SourceFile } from "../api/types";
import {
  FILES_SHARED_KEY,
  FILES_SOURCE_MISSING,
  FILES_WITH_MISSING,
  FILES_WITH_PATTERN,
  FILES_WITH_PATTERN_SOURCES,
  FILES_WITH_SUBPROJECT,
  FILES_WITH_SUBPROJECT_SOURCES,
  NOTHING_AT_THAT_PATH,
  PROJECT_FILES,
  PROJECT_SOURCE_FILES,
  VOCABULARY_PUMP,
} from "../stories/fixtures";
import { FilesTableView } from "./FilesTableView";

export default { title: "Components / FilesTableView" };

/** Holds its own selection, as the tab would: `on` seeds it, a click in the table moves it. */
function Files({
  reply = PROJECT_FILES,
  files = PROJECT_SOURCE_FILES,
  on,
}: {
  reply?: FilesReply;
  files?: readonly SourceFile[];
  on?: string;
}) {
  const [selected, setSelected] = useState<string | undefined>(on);
  return <FilesTableView reply={reply} files={files} selected={selected} onSelect={setSelected} />;
}

/** PumpDevice's own five includes (true to examples/vocabulary, fixtures.ts says how): units,
 * sections, constants and rasters beside pump.ddd.json itself, every row a literal entry - blank
 * Kind and State cells nowhere among them, and blank Findings throughout since the real project
 * is clean. */
export const TheProjectsOwnList = () => <Files />;

/** "sensors/*.ddd.json" beside the project's own five (constructed: the shipped example has no
 * pattern of its own). The pattern's own row carries no file of its own - blank Kind and State -
 * and its two matches are indented beneath it, each by its own path relative to the project
 * (spec §2: "beneath it every file it matched" is a file, not Inlet or Outlet, the components
 * those two files happen to declare - `cellsOf`'s own reason, lib/files.ts). */
export const APatternWithItsMatchedFiles = () => (
  <Files reply={FILES_WITH_PATTERN} files={FILES_WITH_PATTERN_SOURCES} />
);

/** missing.ddd.json, naming nothing (constructed): blank Kind, "names no file" under State (spec
 * §2: "shows as such"), and the entry's own single `file-not-found` finding under Findings - a
 * plain path's own word, never `include-empty`'s, which is a pattern's (fixtures.ts says how this
 * was measured) - `rowsOf` gave the row no `SourceFile` to draw a kind from, `cellsOf` the
 * sentence that says so. */
export const AnEntryNamingNothing = () => <Files reply={FILES_WITH_MISSING} />;

/** pump.ddd.json, a literal entry `includes` still names, but its own file missing from those the
 * last analysis read (constructed: examples/vocabulary loads cleanly) - blank Kind, "not read by
 * the last analysis" under State: kept apart from AnEntryNamingNothing's own "names no file"
 * above, since this entry does name a file - the revision has simply not read it yet (Task 6's own
 * ruling, fixtures.ts says the two real causes). */
export const AFileTheLastAnalysisDidNotRead = () => <Files files={FILES_SOURCE_MISSING} />;

/** subsystem.ddd.json, a sub-project (constructed: the shipped example includes no other
 * project): Kind reads "project", drawn exactly as any other kind is - not expanded, its own
 * includes nowhere on this row. */
export const ASubProjectRow = () => (
  <Files reply={FILES_WITH_SUBPROJECT} files={FILES_WITH_SUBPROJECT_SOURCES} />
);

/** pump.ddd.json named twice - its own literal entry, and the one file "*.ddd.json" is thinned to
 * match (constructed, and deliberately narrow: fixtures.ts says why) - both rows sharing that key
 * marked, the pattern's own summary row (a different key) left bare. Which rows are highlighted is
 * the whole point of the photograph. */
export const ASelectedRow = () => <Files reply={FILES_SHARED_KEY} on={VOCABULARY_PUMP} />;

/** A path no row carries (constructed: what a sub-project's own `include-empty` or
 * `empty-vocabulary` would route to) - the table draws exactly as TheProjectsOwnList does,
 * nothing marked and nothing thrown. */
export const TheRouteNamesNoRow = () => <Files on={NOTHING_AT_THAT_PATH} />;
