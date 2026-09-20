import { useState } from "react";
import { PROJECT_UNITS } from "../stories/fixtures";
import { UnitsTableView } from "./UnitsTableView";

export default { title: "Components / UnitsTableView" };

/** The mockups' nine units with RPM selected: the rows with findings first and marked, then the
 * most stated, and kPa, which nothing states, last. */
export const WithFindings = () => {
  const [selected, setSelected] = useState<string | undefined>("RPM");
  return <UnitsTableView units={PROJECT_UNITS} selected={selected} onSelect={setSelected} />;
};
