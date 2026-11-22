import { useState } from "react";
import { COMPONENTS, filterLine } from "../lib/filter";
import { FilterField } from "./FilterField";

export default { title: "UI / FilterField" };

/** The field over a table of 1,166 components, holding `typed` as the story opens: the line beside
 * it counts the three it leaves, as the Table tab's would. */
function Field({ typed }: { typed: string }) {
  const [value, setValue] = useState(typed);
  return (
    <FilterField
      label="Filter components"
      value={value}
      onChange={setValue}
      line={filterLine(value, value === "" ? 1166 : 3, 1166, COMPONENTS)}
    />
  );
}

/** Nothing typed: the field reads its name, and the line beside it says nothing. */
export const Empty = () => <Field typed="" />;

/** Three of the table's rows left, and the line saying so. */
export const Filtered = () => <Field typed="sensor" />;
