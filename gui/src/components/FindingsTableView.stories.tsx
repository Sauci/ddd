import { useState } from "react";
import { findingRows } from "../lib/findings";
import { NO_FINDINGS, PROJECT_FINDINGS } from "../stories/fixtures";
import { FindingsTableView } from "./FindingsTableView";

export default { title: "Components / FindingsTableView" };

const ROWS = findingRows(PROJECT_FINDINGS);

/** Every severity, worst first, grouped by file within a severity. */
export const WorstFirst = () => {
  const [selected, setSelected] = useState<string | undefined>(undefined);
  return <FindingsTableView rows={ROWS} selected={selected} onSelect={setSelected} />;
};

/** The first row - the worst finding there is - with its panel open. */
export const Selected = () => {
  const [selected, setSelected] = useState<string | undefined>(ROWS[0]?.key);
  return <FindingsTableView rows={ROWS} selected={selected} onSelect={setSelected} />;
};

/** A project with nothing to report: the header alone, no row under it. */
export const NothingToReport = () => {
  const [selected, setSelected] = useState<string | undefined>(undefined);
  const rows = findingRows(NO_FINDINGS);
  return <FindingsTableView rows={rows} selected={selected} onSelect={setSelected} />;
};
